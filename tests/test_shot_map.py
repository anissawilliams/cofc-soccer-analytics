import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import db
from backend.shot_map import DEFAULT_SHOT_MAP_DIR, get_shot_map


class FakeMatchQuery:
    def select(self, *_args):
        return self

    def eq(self, *_args):
        return self

    def execute(self):
        return type("Response", (), {"data": [{
            "id": "match-1",
            "session_id": "session-1",
            "result": "W",
            "goals_for": 2,
            "goals_against": 1,
            "session": {"session_date": "2025-11-02", "season": "2025"},
            "home_team": {"name": "College of Charleston", "short_name": "CofC", "is_cofc": True},
            "away_team": {"name": "NC Wilmington", "short_name": "UNCW", "is_cofc": False},
        }]})()


class FakeMatchClient:
    def table(self, name):
        if name != "match":
            raise AssertionError(f"Unexpected table: {name}")
        return FakeMatchQuery()


class ShotMapTests(unittest.TestCase):
    def test_tracked_uncw_snapshot_has_reviewed_chances_for_both_teams(self):
        with patch.dict(os.environ, {"COFC_SHOT_MAP_DIR": str(DEFAULT_SHOT_MAP_DIR)}, clear=False):
            result = get_shot_map(
                "2025-11-02",
                "College of Charleston",
                "NC Wilmington",
                ("CofC",),
                ("UNCW",),
            )
        self.assertTrue(result["available"])
        self.assertEqual(len(result["shots"]), 17)
        self.assertEqual(result["team_summaries"]["College of Charleston"]["xg"], 1.09)
        self.assertEqual(result["coverage"]["located_shots"], 17)

    def test_db_short_names_load_and_remap_reviewed_snapshot(self):
        with patch.dict(os.environ, {"COFC_SHOT_MAP_DIR": str(DEFAULT_SHOT_MAP_DIR)}, clear=False):
            result = get_shot_map(
                "2025-11-02",
                "College of Charleston",
                "NC Wilmington",
                ("CofC",),
                ("UNCW",),
            )

        self.assertTrue(result["available"])
        self.assertEqual(result["home_team"], "College of Charleston")
        self.assertEqual(result["away_team"], "NC Wilmington")
        self.assertEqual(set(result["team_summaries"]), {"College of Charleston", "NC Wilmington"})
        self.assertEqual({shot["team"] for shot in result["shots"]}, {"College of Charleston", "NC Wilmington"})

    def test_missing_snapshot_is_explicit(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.dict(os.environ, {"COFC_SHOT_MAP_DIR": root}, clear=False):
                result = get_shot_map("2026-08-20")
        self.assertFalse(result["available"])
        self.assertIn("not been published", result["reason"])

    def test_invalid_coordinates_are_rejected(self):
        payload = {
            "home_team": "Charleston Cougars",
            "away_team": "Opponent",
            "shots": [{"shot_id": "shot-1", "sequence": 1, "team": "Charleston Cougars", "outcome": "goal", "minute": 2, "x": 120, "y": 80}],
            "team_summaries": {"Charleston Cougars": {}, "Opponent": {}},
            "source": {},
        }
        with tempfile.TemporaryDirectory() as root:
            Path(root, "2026-08-20_opponent.json").write_text(json.dumps(payload), encoding="utf-8")
            with patch.dict(os.environ, {"COFC_SHOT_MAP_DIR": root}, clear=False):
                result = get_shot_map("2026-08-20")
        self.assertFalse(result["available"])
        self.assertIn("invalid", result["reason"])

    def test_same_date_snapshot_must_match_fixture_teams(self):
        payload = {
            "home_team": "Different Team",
            "away_team": "Other Team",
            "shots": [],
            "team_summaries": {"Different Team": {}, "Other Team": {}},
            "source": {},
        }
        with tempfile.TemporaryDirectory() as root:
            Path(root, "2026-08-20_other.json").write_text(json.dumps(payload), encoding="utf-8")
            with patch.dict(os.environ, {"COFC_SHOT_MAP_DIR": root}, clear=False):
                result = get_shot_map("2026-08-20", "Charleston Cougars", "Davidson")
        self.assertFalse(result["available"])
        self.assertIn("do not match", result["reason"])


class ShotMapFrontendContractTests(unittest.TestCase):
    def test_component_exposes_chance_quality_and_pending_state(self):
        source = Path("frontend/src/ShotMap.jsx").read_text(encoding="utf-8")
        self.assertIn("SHOT MAP & CHANCE QUALITY", source)
        self.assertIn("SHOT DATA PENDING", source)
        self.assertIn("Marker area = xG", source)
        self.assertIn("staffApiFetch(`/api/shot-map/${sessionId}`)", source)


class ShotMapDatabaseContractTests(unittest.TestCase):
    def test_db_passes_canonical_names_and_short_names_to_snapshot_loader(self):
        with (
            patch.object(db, "get_client", return_value=FakeMatchClient()),
            patch.object(db, "load_shot_map", return_value={"available": True}) as loader,
        ):
            result = db.get_match_shot_map("session-1")

        self.assertTrue(result["shot_map"]["available"])
        loader.assert_called_once_with(
            "2025-11-02",
            "College of Charleston",
            "NC Wilmington",
            ("CofC",),
            ("UNCW",),
        )


if __name__ == "__main__":
    unittest.main()
