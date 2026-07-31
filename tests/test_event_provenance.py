from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


INGESTION_DIR = Path(__file__).resolve().parents[1] / "pipeline" / "ingestion"
sys.path.insert(0, str(INGESTION_DIR))

from load_match import get_exact_source_file_id, insert_athlete_event_if_new


class FakeQuery:
    def __init__(self, client: "FakeClient", table: str):
        self.client = client
        self.table = table
        self.action = "select"
        self.payload = None

    def select(self, *_args):
        return self

    def eq(self, *_args):
        return self

    def limit(self, *_args):
        return self

    def update(self, payload):
        self.action = "update"
        self.payload = payload
        return self

    def insert(self, payload):
        self.action = "insert"
        self.payload = payload
        return self

    def execute(self):
        if self.action == "update":
            self.client.updates.append(self.payload)
            return SimpleNamespace(data=[self.payload])
        if self.action == "insert":
            self.client.inserts.append(self.payload)
            return SimpleNamespace(data=[self.payload])
        return SimpleNamespace(data=self.client.rows.get(self.table, []))


class FakeClient:
    def __init__(self, rows=None):
        self.rows = rows or {}
        self.updates = []
        self.inserts = []

    def table(self, name):
        return FakeQuery(self, name)


class EventProvenanceTests(unittest.TestCase):
    def test_exact_registered_file_is_resolved(self) -> None:
        client = FakeClient(
            {"source_file": [{"id": "file-1", "storage_path": "cofc/2026/match/source.xml"}]}
        )

        self.assertEqual(
            get_exact_source_file_id(client, "2026", "match", "sportscode"),
            "file-1",
        )

    def test_ambiguous_registered_files_are_not_attached(self) -> None:
        client = FakeClient(
            {
                "source_file": [
                    {"id": "file-1", "storage_path": "one.xml"},
                    {"id": "file-2", "storage_path": "two.xml"},
                ]
            }
        )

        self.assertIsNone(get_exact_source_file_id(client, "2026", "match", "sportscode"))

    def test_duplicate_event_gets_missing_provenance_backfilled(self) -> None:
        payload = {
            "athlete_id": "athlete-1",
            "session_id": "session-1",
            "metric_id": "metric-1",
            "source_id": "source-1",
            "source_file_id": "file-1",
            "collection_method": "auto",
            "event_time": 12.5,
            "raw_value_context": {"wyscout_label": "Goal"},
        }
        client = FakeClient(
            {
                "athlete_event": [
                    {
                        "id": "event-1",
                        "event_time": 12.5,
                        "raw_value_context": {"wyscout_label": "Goal"},
                        "source_file_id": None,
                    }
                ]
            }
        )

        inserted = insert_athlete_event_if_new(client, payload, dry_run=False)

        self.assertFalse(inserted)
        self.assertEqual(client.updates, [{"source_file_id": "file-1"}])
        self.assertFalse(client.inserts)


if __name__ == "__main__":
    unittest.main()
