# FL511 → ArcGIS Live Closure Layer (Prototype)

**Purpose:** Create a URL-accessible GeoJSON layer with point locations, roadway names, county, severity, closure description, and update timestamps for current FL511 events categorized as **Closures** in the Panhandle and Northeast regions. No paid ArcGIS account needed to consume a publicly accessible GeoJSON URL.

## Important limitations

- This is an **independent prototype**, not a confirmed FDOT-licensed feed. The site endpoints may change or block automated use. Before scheduling unattended polling or republishing this data, review FL511/FDOT terms and obtain any necessary authorization. FDOT has a separate third-party feed and a data-use agreement process.
- Refreshes depend on both FL511 availability and GitHub Actions scheduling. A schedule can be delayed or skipped. **Do not describe the layer as guaranteed real-time.**
- The `FL511_REGIONS` default is `Panhandle,Northeast`, using exact FL511 region names. Check FL511 for whether your intended North Florida counties fall under these classifications.
- Not every road/bridge closure is necessarily present, and **a point is not a precise representation of a closed road segment**. Do not use this as the sole routing or dispatch authority.
- `isFullClosure` cannot safely be used alone. Some events categorized `Closures` have `isFullClosure: false` despite descriptions such as "All lanes blocked." The converter includes FL511's `Closures` category and carries the original flag and lane description separately.
- Website traffic list may omit certain closure incidents or rely on separate streams (construction closures, incidents that close lanes). Compare to FL511 and local agencies before relying on completeness.
- The output includes `retrieved_at_utc`. **Check it before every briefing**; if a run fails, GitHub retains the previous successful file (which becomes stale).

## First: Test locally (no GitHub required)

1. Install Python 3.10 or newer.
2. From the project folder, run: `python -m unittest discover -s tests -v`
3. When permitted to poll the source, run `python fl511_to_geojson.py`.
4. Inspect `docs/closures.geojson` and `docs/status.json`. An unsuccessful request leaves prior output intact.

## Publishing with GitHub Pages

1. Create a **public** GitHub repo named `fl511-closures-cop` (or choose a different name).
2. Upload the contents of this folder, preserving the `.github/workflows/update-closures.yml` location. Do not upload the ZIP as a single file.
3. In **Settings → Pages**, under **Build and deployment → Source**, choose **GitHub Actions**. Do **not** select "Deploy from a branch"; scheduled commits made with `GITHUB_TOKEN` do not trigger a Pages rebuild.
4. Open **Actions → Update FL511 closure GeoJSON → Run workflow**, then check the Build and Deploy jobs and verify the site's `closures.geojson` and `status.json` URLs.
5. The layer URL has the form:
   `https://YOUR-GITHUB-USERNAME.github.io/fl511-closures-cop/closures.geojson`
   The exact site URL is shown under **Settings → Pages**.
6. The workflow is configured for :07, :22, :37, :52 UTC (15-minute intervals), subject to GitHub delays. Each successful run **directly publishes to Pages**, with no additional repository commit. **Only leave scheduled collection enabled after confirming permission to automate FL511 requests**. To pause updates, disable the workflow in GitHub Actions or remove its `schedule` block.
7. If FL511 temporarily fails, the deployment job will not publish a new file. The previous deployment remains online and becomes **stale**; check `retrieved_at_utc` before using it for a briefing.

## Adding to ArcGIS Online Map Viewer

1. Open your saved operational map.
2. Use **Add → Add layer from URL**.
3. Paste the GitHub Pages URL ending in `closures.geojson` and select **GeoJSON**.
4. Add the layer. Put it above your power outage layer and symbolize the points red.
5. Open its layer **Properties → Refresh interval**; enable automatic refresh, for example **15 minutes**, if available. This fetches the current published GeoJSON—it does not force GitHub to run on time.
6. Configure popups to show `roadway`, `county`, `description`, `lane_description`, `last_updated_local`, `retrieved_at_utc`, and `details_url`.
7. Verify a known closure and confirm the source timestamps before using it operationally.

## Output format

- `docs/closures.geojson` — GeoJSON `FeatureCollection` with point geometry `[longitude, latitude]`
- `docs/status.json` — retrieval timestamp, number of events fetched, mapped closure count, and unmatched events
- `docs/index.html` — simple status webpage

## Scope changes

Change `FL511_REGIONS` in `.github/workflows/update-closures.yml` (e.g., `Panhandle,Northeast`). If a region label differs from FL511, events will be excluded. Retest after changing.

## Source

Website endpoints used by the prototype:

- `https://www.fl511.com/List/GetData/traffic` (requires an encoded `query` parameter)
- `https://www.fl511.com/map/mapIcons/Closures`

Official monitoring: https://www.fl511.com/map
