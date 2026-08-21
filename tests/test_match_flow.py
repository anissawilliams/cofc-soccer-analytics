import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.match_flow import DEFAULT_MATCH_FLOW_DIR, get_match_flow


class MatchFlowTests(unittest.TestCase):
    def test_tracked_uncw_snapshot_has_two_team_pressure(self):
        with patch.dict(os.environ, {"COFC_MATCH_FLOW_DIR": str(DEFAULT_MATCH_FLOW_DIR)}, clear=False):
            flow = get_match_flow("2025-11-02")
        self.assertTrue(flow["available"])
        self.assertEqual(flow["home_team"], "Charleston Cougars")
        self.assertEqual(flow["away_team"], "UNCW Seahawks")
        self.assertEqual(len(flow["bins"]), 20)
        self.assertEqual(flow["coverage"]["canonical_events"], 265)

    def test_tracked_davidson_snapshot_has_reviewed_two_team_pressure(self):
        with patch.dict(os.environ, {"COFC_MATCH_FLOW_DIR": str(DEFAULT_MATCH_FLOW_DIR)}, clear=False):
            flow = get_match_flow("2026-08-20")
        self.assertTrue(flow["available"])
        self.assertEqual(flow["home_team"], "Charleston Cougars")
        self.assertEqual(flow["away_team"], "Davidson Wildcats")
        self.assertEqual(len(flow["bins"]), 19)
        self.assertEqual(flow["coverage"]["canonical_events"], 240)

    def test_missing_snapshot_is_explicit(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.dict(os.environ, {"COFC_MATCH_FLOW_DIR": root}, clear=False):
                flow = get_match_flow("2026-08-20")
        self.assertFalse(flow["available"])

    def test_reviewed_snapshot_is_loaded(self):
        payload = {
            "home_team": "Charleston Cougars",
            "away_team": "Opponent",
            "bins": [{"start": 0, "home": 2, "away": 1}],
            "goals": [],
            "coverage": {"canonical_events": 1},
        }
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "2026-08-20_opponent.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with patch.dict(os.environ, {"COFC_MATCH_FLOW_DIR": root}, clear=False):
                flow = get_match_flow("2026-08-20")
        self.assertTrue(flow["available"])
        self.assertEqual(flow["bins"][0]["home"], 2)

    def test_snapshot_is_reoriented_to_match_home_and_away(self):
        payload = {
            "home_team": "Opponent",
            "away_team": "Charleston Cougars",
            "bins": [{"start": 0, "home": 2, "away": 1}],
            "goals": [],
            "coverage": {},
        }
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "2026-08-20_opponent.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with patch.dict(os.environ, {"COFC_MATCH_FLOW_DIR": root}, clear=False):
                flow = get_match_flow("2026-08-20", "Charleston Cougars", "Opponent")
        self.assertEqual(flow["home_team"], "Charleston Cougars")
        self.assertEqual(flow["bins"][0]["home"], 1)


if __name__ == "__main__":
    unittest.main()
