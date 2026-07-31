from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


INGESTION_DIR = Path(__file__).resolve().parents[1] / "pipeline" / "ingestion"
sys.path.insert(0, str(INGESTION_DIR))

from inventory_sources import source_metadata_json, source_status


class SourceInventoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = {
            ("match-a", "sportscode"): {
                "id": "file-1",
                "parse_status": "parsed",
                "sha256": "a" * 64,
                "storage_path": "cofc/2026/match-a/sportscode.xml",
            },
            ("match-a", "effective_time"): {
                "id": "file-2",
                "parse_status": "pending",
                "sha256": "",
                "storage_path": "cofc/2026/match-a/effective-time.xml",
            },
            ("match-b", "sportscode"): {
                "id": "file-3",
                "parse_status": "parsed",
                "storage_path": "cofc/2026/match-b/sportscode.xml",
            },
        }

    def test_metadata_is_scoped_and_keyed_by_source_type(self) -> None:
        value = json.loads(source_metadata_json(self.rows, "match-a", "parse_status"))

        self.assertEqual(value, {"effective_time": "pending", "sportscode": "parsed"})

    def test_empty_metadata_values_are_omitted(self) -> None:
        value = json.loads(source_metadata_json(self.rows, "match-a", "sha256"))

        self.assertEqual(value, {"sportscode": "a" * 64})

    def test_source_status_distinguishes_local_and_storage(self) -> None:
        storage_row = {"upload_status": "uploaded"}

        self.assertEqual(source_status(True, storage_row), "local+storage")
        self.assertEqual(source_status(False, storage_row), "storage")
        self.assertEqual(source_status(False, None), "missing")


if __name__ == "__main__":
    unittest.main()
