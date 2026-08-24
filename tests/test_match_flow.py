import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.match_flow import DEFAULT_MATCH_FLOW_DIR, get_match_flow


class RemoteQuery:
    def __init__(self, rows):
        self.rows = rows

    def select(self, _columns):
        return self

    def eq(self, column, value):
        self.rows = [row for row in self.rows if row.get(column) == value]
        return self

    def order(self, _column, desc=False):
        return self

    def limit(self, count):
        self.rows = self.rows[:count]
        return self

    def execute(self):
        return SimpleNamespace(data=self.rows)


class RemoteBucket:
    def __init__(self, content):
        self.content = content

    def download(self, _path):
        return self.content


class RemoteStorage:
    def __init__(self, content):
        self.content = content

    def from_(self, _bucket):
        return RemoteBucket(self.content)


class RemoteClient:
    def __init__(self, rows, content):
        self.rows = rows
        self.storage = RemoteStorage(content)

    def table(self, name):
        if name != "source_file":
            raise AssertionError(name)
        return RemoteQuery(list(self.rows))


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

    def test_promoted_storage_snapshot_is_loaded_without_git_copy(self):
        payload = {
            "home_team": "Charleston Cougars",
            "away_team": "FGCU Eagles",
            "bins": [{"start": 0, "home": 3, "away": 2}],
            "goals": [],
            "coverage": {"canonical_events": 5},
        }
        content = json.dumps(payload).encode("utf-8")
        import hashlib
        client = RemoteClient([{
            "session_id": "session-1",
            "source_type": "match_flow",
            "is_active": True,
            "storage_bucket": "source-files",
            "storage_path": "cofc/2026/fgcu/match-flow.json",
            "sha256": hashlib.sha256(content).hexdigest(),
        }], content)

        with tempfile.TemporaryDirectory() as root:
            with patch.dict(os.environ, {"COFC_MATCH_FLOW_DIR": root}, clear=False):
                flow = get_match_flow(
                    "2026-08-23",
                    "Charleston Cougars",
                    "FGCU Eagles",
                    client=client,
                    session_id="session-1",
                )

        self.assertTrue(flow["available"])
        self.assertEqual(flow["coverage"]["canonical_events"], 5)


if __name__ == "__main__":
    unittest.main()
