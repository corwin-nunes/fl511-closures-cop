#!/usr/bin/env python3
"""Convert the public FL511 map/list responses into a Panhandle/North FL GeoJSON.

Prototype using website endpoints, not FDOT's licensed third-party feed.
For operational use, obtain FDOT's permission/authorized data access and verify accuracy.
"""
from __future__ import annotations

import gzip
import html
import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = "https://www.fl511.com"
EVENT_URL = BASE + "/List/GetData/traffic"
LOCATION_URL = BASE + "/map/mapIcons/Closures"
COLS = ("", "region", "county", "roadwayName", "direction", "type",
        "severity", "description", "startDate", "lastUpdated", "")
PAGE_SIZE = 25  # tested FL511 website format; keep small to avoid server load
MAX_PAGES = 200
REGIONS = {region.strip().casefold() for region in
           os.environ.get("FL511_REGIONS", "Panhandle,Northeast").split(",") if region.strip()}
OUT_DIR = Path(os.environ.get("OUT_DIR", "docs"))


def get_json(url: str, params: dict | None = None) -> dict:
    if params:
        url = url + "?" + urlencode(params)
    req = Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "FL511-COP-Prototype/0.1 (read-only open-data evaluation)",
    })
    try:
        with urlopen(req, timeout=25) as response:
            if response.status != 200:
                raise RuntimeError(f"Unexpected HTTP {response.status} from {url.split('?')[0]}")
            raw = response.read(8_000_001)
    except (HTTPError, URLError) as exc:
        raise RuntimeError(f"Could not retrieve {url.split('?')[0]}: {exc}") from exc
    if len(raw) > 8_000_000:
        raise RuntimeError("FL511 response exceeds safe 8 MB limit")
    # Some FL511 endpoints return a GZIP body even if the client did not
    # explicitly request compression. Recognize it by its magic bytes.
    if raw.startswith(b"\x1f\x8b"):
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(raw), mode="rb") as stream:
                raw = stream.read(8_000_001)
        except (OSError, EOFError) as exc:
            raise RuntimeError("FL511 returned invalid GZIP data") from exc
        if len(raw) > 8_000_000:
            raise RuntimeError("Decompressed FL511 response exceeds safe 8 MB limit")
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise RuntimeError(f"FL511 returned non-JSON content from {url.split('?')[0]}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"Unexpected JSON response type from {url.split('?')[0]}")
    return payload


def query_for_page(start: int) -> dict:
    return {
        "columns": [({"data": None, "name": ""} if i == 0 else
                     {"data": 10, "name": ""} if i == 10 else {"name": name})
                    for i, name in enumerate(COLS)],
        "order": [{"column": 9, "dir": "desc"}],
        "start": start, "length": PAGE_SIZE, "search": {"value": ""},
    }


def collect_events(request_fn=get_json) -> list[dict]:
    events: list[dict] = []
    total: int | None = None
    for i in range(MAX_PAGES):
        payload = request_fn(EVENT_URL, {"query": json.dumps(query_for_page(i * PAGE_SIZE), separators=(",", ":")), "lang": "en"})
        rows = payload.get("data")
        if not isinstance(rows, list):
            raise RuntimeError("FL511 traffic response is missing data array")
        if total is None:
            count = payload.get("recordsFiltered", payload.get("recordsTotal"))
            if not isinstance(count, int) or count < 0:
                raise RuntimeError("FL511 traffic response is missing record count")
            total = count
            if total == 0:
                raise RuntimeError("Unusually empty statewide FL511 feed; refusing to replace last good file")
        if not rows and len(events) < total:
            raise RuntimeError(f"FL511 pagination stopped early at {len(events)}/{total}")
        events.extend(rows)
        if len(events) >= total:
            return events
    raise RuntimeError(f"Exceeded maximum pages while fetching events ({len(events)})")


def coordinates_map(location_payload: dict) -> dict[str, list[float]]:
    items = location_payload.get("item2")
    if not isinstance(items, list):
        raise RuntimeError("FL511 locations response is missing item2 array")
    found = {}
    for item in items:
        try:
            event_id = str(item["itemId"])
            lat, lon = item["location"]  # FL511 uses [latitude, longitude]
            lat, lon = float(lat), float(lon)
        except (KeyError, TypeError, ValueError):
            continue
        if 24 <= lat <= 32 and -89 <= lon <= -79:
            found[event_id] = [lon, lat]  # GeoJSON REQUIRES [longitude, latitude]
    return found


def clean_text(value: object) -> str:
    return html.unescape(str(value or "")).strip()


def build_feature_collection(events: list[dict], locations: dict[str, list[float]], generated_utc: str) -> tuple[dict, dict]:
    features = []
    candidate_ids = []
    for event in events:
        if not isinstance(event, dict):
            continue
        if clean_text(event.get("type")).casefold() != "closures":
            continue  # Include only FL511 closure category, not every incident
        if REGIONS and clean_text(event.get("region")).casefold() not in REGIONS:
            continue
        if event.get("showOnMap") is False:
            continue
        event_id = str(event.get("id") or "")
        if not event_id:
            continue
        candidate_ids.append(event_id)
        coord = locations.get(event_id)
        if not coord:
            continue
        props = {
            "event_id": event_id,
            "roadway": clean_text(event.get("roadwayName")),
            "county": clean_text(event.get("county")),
            "region": clean_text(event.get("region")),
            "direction": clean_text(event.get("direction")),
            "severity": clean_text(event.get("severity")),
            "event_type": clean_text(event.get("type")),
            "description": clean_text(event.get("description")),
            "lane_description": clean_text(event.get("laneDescription")),
            "is_full_closure_flag": bool(event.get("isFullClosure") is True),
            "last_updated_local": clean_text(event.get("lastUpdated")),
            "retrieved_at_utc": generated_utc,
            "details_url": BASE + "/tooltip/Closures/" + event_id + "?lang=en-US",
        }
        features.append({"type": "Feature", "id": event_id, "geometry": {"type": "Point", "coordinates": coord}, "properties": props})
    features.sort(key=lambda f: (f["properties"]["county"], f["properties"]["event_id"]))
    if candidate_ids and not features:
        raise RuntimeError("No event IDs matched the closure-coordinate feed. Refusing to publish empty map.")
    meta = {
        "source": "FL511 (Florida Department of Transportation)",
        "source_events_url": EVENT_URL,
        "source_locations_url": LOCATION_URL,
        "retrieved_at_utc": generated_utc,
        "selected_regions": sorted(REGIONS),
        "statewide_events_fetched": len(events),
        "regional_closure_events": len(candidate_ids),
        "mapped_closure_points": len(features),
        "unmapped_closure_events": len(candidate_ids) - len(features),
        "prototype_warning": "Website endpoints are not an authorized operational data feed; verify against official FL511 and FDOT before routing responders.",
    }
    return {"type": "FeatureCollection", "features": features}, meta


def main() -> None:
    generated_utc = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    events = collect_events()
    raw_locations = get_json(LOCATION_URL)
    fc, meta = build_feature_collection(events, coordinates_map(raw_locations), generated_utc)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # Do not truncate the last known good file on failed fetch/validation.
    for name, value in (("closures.geojson", fc), ("status.json", meta)):
        temp = OUT_DIR / (name + ".tmp")
        temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temp.replace(OUT_DIR / name)
    print(f"Updated {OUT_DIR / 'closures.geojson'} with {len(fc['features'])} points "
          f"({meta['unmapped_closure_events']} regional closure events lacking coordinates)")


if __name__ == "__main__":
    main()
