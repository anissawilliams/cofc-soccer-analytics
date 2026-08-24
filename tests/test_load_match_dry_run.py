import unittest
import sys
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

INGESTION_DIR = Path(__file__).resolve().parents[1] / "pipeline" / "ingestion"
sys.path.insert(0, str(INGESTION_DIR))

from pipeline.ingestion.load_match import (
    _stint_timing,
    fuzzy_match_athlete,
    home_away_team_ids,
    load_bundle_manifest_row,
    load_or_create_match,
    load_stints,
)


class Query:
    def __init__(self, rows):
        self.rows = rows

    def select(self, _columns):
        return self

    def eq(self, column, value):
        self.rows = [row for row in self.rows if row.get(column) == value]
        return self

    def ilike(self, column, pattern):
        needle = pattern.strip("%").lower()
        self.rows = [row for row in self.rows if needle in str(row.get(column, "")).lower()]
        return self

    def execute(self):
        return SimpleNamespace(data=self.rows)


class Client:
    def __init__(self):
        self.tables = {
            "team": [
                {"id": "cofc", "is_cofc": True, "short_name": "Charleston"},
                {"id": "davidson", "is_cofc": False, "short_name": "Davidson"},
            ],
        }
        self.requested = []

    def table(self, name):
        self.requested.append(name)
        if name in {"match", "athlete_session_stint"}:
            raise AssertionError(f"dry run queried UUID-backed table: {name}")
        return Query(list(self.tables.get(name, [])))


class LoadMatchDryRunTests(unittest.TestCase):
    def test_reviewed_bundle_metadata_drives_new_match_load(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "2026-08-23_fgcu_metadata.json").write_text(json.dumps({
                "match_date": "2026-08-23",
                "opponent": "Florida Gulf Coast",
                "location": "home",
                "competition": "non-conference",
                "cofc_score": 3,
                "opponent_score": 2,
                "prepared_by": "Anissa",
            }))

            row = load_bundle_manifest_row(root, "2026-08-23_fgcu", "2026")

        self.assertEqual(row["competition"], "Non-Conference")
        self.assertEqual(row["cofc_goals"], 3)
        self.assertEqual(row["opp_goals"], 2)
        self.assertEqual(row["location"], "home")

    def test_reviewed_bundle_metadata_rejects_wrong_match_date(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "2026-08-23_fgcu_metadata.json").write_text(json.dumps({
                "match_date": "2026-08-24",
            }))

            with self.assertRaisesRegex(ValueError, "match_date"):
                load_bundle_manifest_row(root, "2026-08-23_fgcu", "2026")

    def test_away_metadata_places_opponent_in_home_team_column(self):
        self.assertEqual(
            home_away_team_ids("cofc", "opponent", {"location": "away"}),
            ("opponent", "cofc"),
        )

    def test_official_starter_flag_beats_minutes_heuristic(self):
        substitute = pd.Series({
            "player_name": "D. Toulson", "estimated_minutes": 58, "started": False
        })

        self.assertEqual(_stint_timing(substitute), (32, 90, False))

    def test_explicit_red_card_off_moment_wins(self):
        dismissed = pd.Series({
            "player_name": "J. Jordheim", "estimated_minutes": 83,
            "started": True, "off_minute": 82.5,
        })

        self.assertEqual(_stint_timing(dismissed), (0, 83, True))

    def test_fuzzy_match_uses_rapidfuzz_mapping_key_as_athlete_id(self):
        athletes = [
            {
                "id": "athlete-jordheim",
                "display_name": "J. Jordheim",
                "first_name": "Julian",
                "last_name": "Jordheim",
            },
            {
                "id": "athlete-lenert",
                "display_name": "M. Lenert",
                "first_name": "Matt",
                "last_name": "Lenert",
            },
        ]

        match, score = fuzzy_match_athlete("J Jordheim", athletes)

        self.assertEqual(match["id"], "athlete-jordheim")
        self.assertGreater(score, 80)

    def test_new_dry_run_session_does_not_query_match_with_fake_uuid(self):
        client = Client()

        match_id = load_or_create_match(
            client,
            "dry-run-session-id",
            "2026-08-20_davidson",
            scored_df=None,
            manifest_row={"cofc_goals": 1, "opp_goals": 1},
            dry_run=True,
        )

        self.assertEqual(match_id, "dry-run-match-id")
        self.assertNotIn("match", client.requested)

    def test_stint_dry_run_does_not_query_with_fake_ids(self):
        client = Client()
        minutes = pd.DataFrame([{"player_name": "M. Lenert", "estimated_minutes": 72}])

        load_stints(
            client,
            "dry-run-session-id",
            minutes,
            {"m. lenert": "dry-run-m. lenert"},
            dry_run=True,
        )

        self.assertNotIn("athlete_session_stint", client.requested)


if __name__ == "__main__":
    unittest.main()
