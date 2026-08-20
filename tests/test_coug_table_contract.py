import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from db import (
    _is_published_match_score,
    get_coug_scores_with_minutes,
    get_player_match_history,
    get_season_leaderboard_with_minutes,
)


ROOT = Path(__file__).resolve().parents[1]


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def execute(self):
        return SimpleNamespace(data=self.rows)


class FakeClient:
    def __init__(self, tables):
        self.tables = tables

    def table(self, name):
        return FakeQuery(self.tables.get(name, []))


def score_row(*, score_type="match", version="trial_1", session_id="session-1"):
    return {
        "aset_score": 1,
        "peak_score": 2,
        "set_piece_score": 3,
        "positional_score": 4,
        "load_score": 5,
        "total_score": 15,
        "score_type": score_type,
        "weight_version": {"version": version},
        "athlete": {
            "id": "athlete-1",
            "display_name": "Test Player",
            "position": "MF",
            "position_group": "Midfielder",
        },
        "session": {
            "id": session_id,
            "session_date": "2025-02-11",
            "season": "2025",
            "competition": "Test Match",
        },
    }


class CougTableDataContractTests(unittest.TestCase):
    def test_public_table_accepts_only_reviewed_match_scores_for_one_version(self):
        reviewed = {
            "score_type": "match",
            "weight_version": {"version": "trial_1"},
        }
        rolling = {**reviewed, "score_type": "rolling"}
        other_version = {
            **reviewed,
            "weight_version": {"version": "experimental"},
        }

        self.assertTrue(_is_published_match_score(reviewed, "trial_1"))
        self.assertFalse(_is_published_match_score(rolling, "trial_1"))
        self.assertFalse(_is_published_match_score(other_version, "trial_1"))

    def test_all_public_table_queries_exclude_non_published_scores(self):
        rows = [
            score_row(),
            score_row(score_type="rolling"),
            score_row(version="experimental"),
        ]
        client = FakeClient({
            "coug_score": rows,
            "athlete_session_stint": [{
                "athlete_id": "athlete-1",
                "session_id": "session-1",
                "minutes_on": 0,
                "minutes_off": 90,
                "started": True,
                "session": {"season": "2025"},
            }],
            "match": [],
        })

        with patch("db.get_client", return_value=client):
            match_scores = get_coug_scores_with_minutes("session-1")
            leaderboard = get_season_leaderboard_with_minutes("2025")
            history = get_player_match_history("athlete-1", "2025")

        self.assertEqual(len(match_scores), 1)
        self.assertEqual(leaderboard[0]["matches"], 1)
        self.assertEqual(len(history), 1)


class CougTableFrontendContractTests(unittest.TestCase):
    def test_public_navigation_exposes_only_the_current_coug_table(self):
        app = (ROOT / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")
        self.assertNotIn("COUGDashboardLegacy", app)
        self.assertNotIn("COUG Table v2", app)
        self.assertEqual(app.count("label: 'COUG Table'"), 1)

    def test_season_changes_clear_old_data_and_match_fetch_tracks_season(self):
        source = (ROOT / "frontend" / "src" / "CougTable.jsx").read_text(encoding="utf-8")
        self.assertIn("function changeSeason(nextSeason)", source)
        self.assertIn("setSeasonData([])", source)
        self.assertIn("setMatchData([])", source)
        self.assertIn("}, [selectedMatch, tab, season]);", source)


if __name__ == "__main__":
    unittest.main()
