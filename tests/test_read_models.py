import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend import read_models
from pipeline.analytics.build_dashboard_read_model import validate_read_model, write_read_model


class ReadModelTests(unittest.TestCase):
    def setUp(self):
        read_models._file_cache.clear()

    def test_snapshot_value_reads_nested_player_data(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "coug_2025.json"
            path.write_text(json.dumps({"players": {"p1": {"match_history": [1]}}}))
            with patch.dict(os.environ, {"COFC_READ_MODEL_DIR": directory}):
                self.assertEqual(
                    read_models.snapshot_value("2025", "players", "p1", "match_history"),
                    [1],
                )

    def test_missing_or_invalid_snapshot_falls_back(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"COFC_READ_MODEL_DIR": directory}):
                self.assertIsNone(read_models.load_season_read_model("2025"))
                (Path(directory) / "coug_2025.json").write_text("not-json")
                self.assertIsNone(read_models.load_season_read_model("2025"))

    def test_empty_snapshot_is_rejected_by_default(self):
        payload = {"schema_version": 1, "season": "2025", "leaderboard": []}
        with self.assertRaises(RuntimeError):
            validate_read_model(payload)
        validate_read_model(payload, allow_empty=True)

    def test_split_snapshot_loads_index_and_player_independently(self):
        payload = {
            "schema_version": 1,
            "season": "2025",
            "leaderboard": [{"athlete_id": "p1"}],
            "players": {"p1": {"match_history": [1], "trace": {"events": [2]}}},
            "match_scores": {},
        }
        with tempfile.TemporaryDirectory() as directory:
            write_read_model(payload, Path(directory))
            with patch.dict(os.environ, {"COFC_READ_MODEL_DIR": directory}):
                read_models._file_cache.clear()
                index = read_models.load_season_read_model("2025")
                self.assertEqual(index["schema_version"], 2)
                self.assertNotIn("players", index)
                self.assertEqual(
                    read_models.snapshot_value("2025", "players", "p1", "trace"),
                    {"events": [2]},
                )


if __name__ == "__main__":
    unittest.main()
