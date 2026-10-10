"""Run with python -m unittest discover -s tests -v (no Internet needed)."""
import unittest
from fl511_to_geojson import build_feature_collection, collect_events, coordinates_map


class ConverterTests(unittest.TestCase):
    def test_coordinates_are_reversed(self):
        loc = {"item2": [{"itemId": "897913", "location": [30.72395, -86.71907]}]}
        self.assertEqual(coordinates_map(loc)["897913"], [-86.71907, 30.72395])

    def test_closure_is_included_even_if_flag_false(self):
        events = [
            {"id": 897913, "type": "Closures", "region": "Panhandle", "county": "Okaloosa", "roadwayName": "US-90", "description": "All lanes blocked", "isFullClosure": False, "showOnMap": True},
            {"id": 42, "type": "Incidents", "region": "Panhandle", "county": "Walton", "roadwayName": "I-10", "description": "Crash"},
            {"id": 56, "type": "Closures", "region": "Southeast", "county": "Miami-Dade", "roadwayName": "I-95"},
        ]
        locs = {"897913": [-86.71907, 30.72395], "42": [-86.2, 30.7], "56": [-80.1, 25.7]}
        fc, meta = build_feature_collection(events, locs, "2026-10-10T04:00:00Z")
        self.assertEqual(len(fc["features"]), 1)
        self.assertEqual(fc["features"][0]["properties"]["event_id"], "897913")
        self.assertFalse(fc["features"][0]["properties"]["is_full_closure_flag"])
        self.assertEqual(meta["mapped_closure_points"], 1)

    def test_fetches_all_pages(self):
        calls = []
        def fake_get(url, params):
            calls.append(params)
            return {"recordsFiltered": 26, "data": [{"id": x} for x in (range(25) if len(calls) == 1 else [25])]}
        self.assertEqual(len(collect_events(fake_get)), 26)
        self.assertEqual(len(calls), 2)

    def test_refuses_missing_coordinate_matches(self):
        with self.assertRaisesRegex(RuntimeError, "No event IDs matched"):
            build_feature_collection([{"id": 1, "type": "Closures", "region": "Panhandle"}], {}, "2026-10-10T04:00:00Z")


if __name__ == "__main__":
    unittest.main()
