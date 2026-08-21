import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd


ANALYTICS_DIR = Path(__file__).resolve().parents[1] / "pipeline" / "analytics"
sys.path.insert(0, str(ANALYTICS_DIR))

from publish_event_derived_coug_scores import (  # noqa: E402
    resolve_legacy_weight_id,
    resolve_scoring_version_id,
    resolve_session_id,
    publish_score_payloads,
    score_payloads,
    selected_trace,
)


class Query:
    def __init__(self, rows):
        self.rows = rows

    def select(self, _columns):
        return self

    def eq(self, column, value):
        self.rows = [row for row in self.rows if str(row.get(column)) == str(value)]
        return self

    def execute(self):
        return SimpleNamespace(data=self.rows)


class Client:
    def __init__(self, tables):
        self.tables = tables

    def table(self, name):
        return Query(list(self.tables.get(name, [])))


class EventScorePublicationTests(unittest.TestCase):
    def test_legacy_publication_inserts_when_score_does_not_exist(self):
        table = MagicMock()
        table.select.return_value = table
        table.eq.return_value = table
        table.insert.return_value = table
        table.execute.side_effect = [SimpleNamespace(data=[]), SimpleNamespace(data=[{"id": "new"}])]
        client = MagicMock()
        client.table.return_value = table
        payload = {
            "athlete_id": "athlete-1", "session_id": "session-1",
            "weight_version_id": "weight-1", "score_type": "match",
        }

        publish_score_payloads(client, [payload], None)

        table.insert.assert_called_once_with(payload)

    def test_legacy_publication_updates_one_existing_score(self):
        table = MagicMock()
        table.select.return_value = table
        table.eq.return_value = table
        table.update.return_value = table
        table.execute.side_effect = [SimpleNamespace(data=[{"id": "score-1"}]), SimpleNamespace(data=[])]
        client = MagicMock()
        client.table.return_value = table
        payload = {
            "athlete_id": "athlete-1", "session_id": "session-1",
            "weight_version_id": "weight-1", "score_type": "match",
        }

        publish_score_payloads(client, [payload], None)

        table.update.assert_called_once_with(payload)

    def test_legacy_schema_payload_omits_unavailable_scoring_version(self):
        summary = pd.DataFrame([{
            "athlete_id": "athlete-1", "session_id": "session-1",
            "aset_score": 1.0, "peak_score": 2.0, "set_piece_score": 0.0,
            "positional_score": 0.0, "load_score": 0.0, "total_score": 3.0,
        }])
        payload = score_payloads(summary, None, "weight-1")[0]

        self.assertNotIn("scoring_version_id", payload)
        self.assertEqual(payload["weight_version_id"], "weight-1")

    def test_slug_resolves_exact_match_session(self):
        client = Client({
            "session": [
                {"id": "match-1", "session_date": "2026-08-20", "season": "2026",
                 "session_type": "match", "notes": "slug: 2026-08-20_davidson"},
                {"id": "training-1", "session_date": "2026-08-20", "season": "2026",
                 "session_type": "training", "notes": "morning session"},
            ],
            "match": [{"id": "m1", "session_id": "match-1"}],
        })
        self.assertEqual(
            resolve_session_id(client, "2026", "2026-08-20_davidson"),
            "match-1",
        )

    def test_slug_resolution_blocks_ambiguous_sessions(self):
        duplicate = {"session_date": "2026-08-20", "season": "2026", "session_type": "match",
                     "notes": "slug: 2026-08-20_davidson"}
        client = Client({"session": [{"id": "one", **duplicate}, {"id": "two", **duplicate}]})
        with self.assertRaisesRegex(ValueError, "found 2"):
            resolve_session_id(client, "2026", "2026-08-20_davidson")

    def test_trace_selection_uses_session_not_date(self):
        trace = pd.DataFrame([
            {"session_id": "match-1", "season": "2026", "player": "A", "event_time": 1,
             "raw_metric_name": "Goal"},
            {"session_id": "training-1", "season": "2026", "player": "B", "event_time": 1,
             "raw_metric_name": "Goal"},
        ])
        selected = selected_trace(trace, "2026", "match-1")
        self.assertEqual(selected["session_id"].tolist(), ["match-1"])

    def test_scoring_version_requires_one_stable_row(self):
        client = Client({"scoring_version": [{"id": "sv1", "version": "trial_1"}]})
        self.assertEqual(resolve_scoring_version_id(client, "trial_1"), "sv1")

    def test_legacy_weight_fk_is_deterministic_for_compatibility(self):
        client = Client({"metric_weight": [
            {"id": "newer", "version": "trial_1", "created_at": "2026-01-02"},
            {"id": "original", "version": "trial_1", "created_at": "2026-01-01"},
        ]})
        self.assertEqual(resolve_legacy_weight_id(client, "trial_1"), "original")


if __name__ == "__main__":
    unittest.main()
