import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


INGESTION_DIR = Path(__file__).resolve().parents[1] / "pipeline" / "ingestion"
sys.path.insert(0, str(INGESTION_DIR))

from staff_events import inspect_staff_events, parse_staff_events, parse_minute  # noqa: E402
from load_staff_events import load_events  # noqa: E402


class FakeQuery:
    def __init__(self, client, table, rows):
        self.client = client
        self.table = table
        self.rows = list(rows)
        self.payload = None
        self.operation = "select"

    def select(self, _columns):
        return self

    def eq(self, column, value):
        self.rows = [row for row in self.rows if row.get(column) == value]
        return self

    def is_(self, column, value):
        expected = None if value == "null" else value
        self.rows = [row for row in self.rows if row.get(column) == expected]
        return self

    def insert(self, payload):
        self.operation = "insert"
        self.payload = payload
        return self

    def update(self, payload):
        self.operation = "update"
        self.payload = payload
        return self

    def execute(self):
        if self.operation in {"insert", "update"}:
            self.client.writes.append((self.table, self.operation, self.payload))
            return SimpleNamespace(data=[self.payload])
        return SimpleNamespace(data=self.rows)


class FakeClient:
    def __init__(self, tables):
        self.tables = tables
        self.writes = []

    def table(self, name):
        return FakeQuery(self, name, self.tables.get(name, []))


class StaffEventTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.staff_dir = self.root / "staff"
        self.staff_dir.mkdir()
        self.roster = self.root / "roster.csv"
        self.roster.write_text(
            "number,name\n3,J. Jordheim\n31,A. Butts\n", encoding="utf-8"
        )

    def write_events(self, rows):
        path = self.staff_dir / "staff_events.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=[
                "player_name", "jersey", "event_type", "minute",
                "weight", "notes", "entered_by",
            ])
            writer.writeheader()
            writer.writerows(rows)
        return path

    def test_red_card_captures_exact_off_moment_and_weight(self):
        source = self.write_events([{
            "player_name": "Julian Jordheim",
            "jersey": "3",
            "event_type": "red_card",
            "minute": "82:30",
            "weight": "-2",
            "notes": "Unsporting behavior",
            "entered_by": "AW",
        }])

        events = parse_staff_events(
            source, self.roster, slug="2026-08-20_davidson", season="2026"
        )

        self.assertEqual(events[0]["player_name"], "J. Jordheim")
        self.assertEqual(events[0]["event_time"], 4950)
        self.assertEqual(events[0]["minute"], 82.5)
        self.assertEqual(events[0]["proposed_weight"], -2)
        self.assertTrue(events[0]["player_off"])

    def test_red_card_rejects_wrong_weight(self):
        source = self.write_events([{
            "player_name": "J. Jordheim", "jersey": "3", "event_type": "red_card",
            "minute": "82.5", "weight": "-1", "notes": "", "entered_by": "AW",
        }])
        with self.assertRaisesRegex(ValueError, "must be -2"):
            parse_staff_events(
                source, self.roster, slug="2026-08-20_davidson", season="2026"
            )

    def test_yellow_card_has_cumulative_weight_without_off_moment(self):
        source = self.write_events([{
            "player_name": "A. Butts", "jersey": "31", "event_type": "yellow_card",
            "minute": "34:12", "weight": "-0.4", "notes": "Caution", "entered_by": "AW",
        }])

        events = parse_staff_events(
            source, self.roster, slug="2026-08-23_fgcu", season="2026"
        )

        self.assertEqual(events[0]["metric_name"], "Yellow Card")
        self.assertEqual(events[0]["proposed_weight"], -0.4)
        self.assertEqual(events[0]["event_time"], 2052.0)
        self.assertFalse(events[0]["player_off"])

    def test_yellow_card_rejects_wrong_weight(self):
        source = self.write_events([{
            "player_name": "A. Butts", "jersey": "31", "event_type": "yellow_card",
            "minute": "34:12", "weight": "-1", "notes": "", "entered_by": "AW",
        }])
        with self.assertRaisesRegex(ValueError, "must be -0.4"):
            parse_staff_events(
                source, self.roster, slug="2026-08-23_fgcu", season="2026"
            )

    def test_optional_missing_csv_is_ready(self):
        status, events = inspect_staff_events(
            None, self.roster, slug="2026-08-20_davidson", season="2026"
        )
        self.assertTrue(status["ready"])
        self.assertFalse(status["supplied"])
        self.assertEqual(events, [])

    def test_standalone_cli_needs_no_match_exports(self):
        self.write_events([{
            "player_name": "J. Jordheim", "jersey": "3", "event_type": "red_card",
            "minute": "82:30", "weight": "-2", "notes": "", "entered_by": "AW",
        }])
        output = self.root / "20_generated"
        result = subprocess.run([
            sys.executable, str(INGESTION_DIR / "prepare_staff_events.py"),
            "--season", "2026", "--slug", "2026-08-20_davidson",
            "--staff-dir", str(self.staff_dir), "--roster", str(self.roster),
            "--output-dir", str(output),
        ], check=True, capture_output=True, text=True)

        self.assertIn("Prepared staff events", result.stdout)
        self.assertTrue((output / "2026-08-20_davidson_staff_events.csv").is_file())
        self.assertTrue((output / "2026-08-20_davidson_staff_events_report.json").is_file())

    def test_minute_parser_accepts_decimal_and_clock(self):
        self.assertEqual(parse_minute("82:30"), (82.5, 4950.0))
        self.assertEqual(parse_minute("82.5"), (82.5, 4950.0))

    def test_staff_event_loader_dry_run_resolves_weight_and_off_moment(self):
        client = FakeClient({
            "athlete": [{"id": "athlete-3", "display_name": "J. Jordheim"}],
            "metric_weight": [{
                "id": "red-weight", "weight": -2, "version": "trial_1",
                "effective_to": None,
                "metric": {"id": "red-metric", "name": "Red Card", "applies_to_session_type": "match"},
            }],
            "data_source": [],
            "session_event": [],
            "athlete_event": [],
            "athlete_session_stint": [{
                "id": "stint-3", "session_id": "session-1",
                "athlete_id": "athlete-3", "minutes_off": 83,
            }],
        })
        event = {
            "match_slug": "2026-08-20_davidson",
            "player_name": "J. Jordheim", "event_type": "red_card",
            "event_time": 4950.0, "minute": 82.5, "metric_name": "Red Card",
            "proposed_weight": -2, "player_off": True, "notes": "Dismissed",
            "entered_by": "AW",
        }

        report = load_events(client, "session-1", [event], apply=False)

        self.assertEqual(report["events_would_insert"], 1)
        self.assertEqual(report["off_moments_would_update"], 1)
        self.assertEqual(report["scoring_events_would_insert"], 1)
        self.assertEqual(client.writes, [])

    def test_dry_run_with_missing_source_does_not_query_placeholder_uuid(self):
        client = FakeClient({
            "athlete": [{"id": "athlete-3", "display_name": "J. Jordheim"}],
            "metric_weight": [{
                "id": "red-weight", "weight": -2, "version": "trial_1",
                "effective_to": None,
                "metric": {"id": "red-metric", "name": "Red Card"},
            }],
            "data_source": [],
            "session_event": [],
            "athlete_session_stint": [],
            "athlete_event": [{"source_id": "some-real-uuid"}],
        })
        event = {
            "match_slug": "2026-08-20_davidson",
            "player_name": "J. Jordheim", "event_type": "red_card",
            "event_time": 4950.0, "minute": 82.5, "metric_name": "Red Card",
            "proposed_weight": -2, "player_off": True, "notes": "Dismissed",
            "entered_by": "AW",
        }

        report = load_events(client, "session-1", [event], apply=False)

        self.assertEqual(report["scoring_events_would_insert"], 1)

    def test_existing_red_card_is_updated_not_duplicated(self):
        client = FakeClient({
            "athlete": [{"id": "athlete-3", "display_name": "J. Jordheim"}],
            "metric_weight": [{
                "id": "red-weight", "weight": -2, "version": "trial_1",
                "effective_to": None, "metric": {"id": "red-metric", "name": "Red Card"},
            }],
            "data_source": [{
                "id": "staff-source", "platform": "csv",
                "name": "Staff events — 2026-08-20_davidson",
            }],
            "session_event": [{
                "id": "event-3", "session_id": "session-1",
                "athlete_id": "athlete-3", "event_type": "red_card",
                "event_time": 4980.0,
            }],
            "athlete_session_stint": [],
            "athlete_event": [{
                "id": "score-event-3", "session_id": "session-1",
                "athlete_id": "athlete-3", "metric_id": "red-metric",
                "source_id": "staff-source",
            }],
        })
        event = {
            "match_slug": "2026-08-20_davidson",
            "player_name": "J. Jordheim", "event_type": "red_card",
            "event_time": 4950.0, "minute": 82.5, "metric_name": "Red Card",
            "proposed_weight": -2, "player_off": True, "notes": "Corrected",
            "entered_by": "AW",
        }

        report = load_events(client, "session-1", [event], apply=True)

        self.assertEqual(report["events_updated"], 1)
        self.assertEqual(report["events_inserted"], 0)
        self.assertEqual(report["scoring_events_updated"], 1)
        self.assertEqual([write[1] for write in client.writes], ["update", "update"])

    def test_two_yellow_cards_create_two_timestamped_scoring_events(self):
        client = FakeClient({
            "athlete": [{"id": "athlete-31", "display_name": "A. Butts"}],
            "metric_weight": [{
                "id": "yellow-weight", "weight": -0.4, "version": "trial_1",
                "effective_to": None,
                "metric": {"id": "yellow-metric", "name": "Yellow Card"},
            }],
            "data_source": [{
                "id": "staff-source", "platform": "csv",
                "name": "Staff events — 2026-08-23_fgcu",
            }],
            "session_event": [],
            "athlete_session_stint": [],
            "athlete_event": [{
                "id": "existing-yellow", "session_id": "session-1",
                "athlete_id": "athlete-31", "metric_id": "yellow-metric",
                "source_id": "staff-source", "event_time": 1200.0,
            }],
        })
        base = {
            "match_slug": "2026-08-23_fgcu", "player_name": "A. Butts",
            "event_type": "yellow_card", "metric_name": "Yellow Card",
            "proposed_weight": -0.4, "player_off": False, "notes": "Caution",
            "entered_by": "AW",
        }
        events = [
            {**base, "event_time": 1200.0, "minute": 20.0},
            {**base, "event_time": 4200.0, "minute": 70.0},
        ]

        report = load_events(client, "session-1", events, apply=True)

        self.assertEqual(report["events_inserted"], 2)
        self.assertEqual(report["scoring_events_updated"], 1)
        self.assertEqual(report["scoring_events_inserted"], 1)
        athlete_writes = [payload for table, operation, payload in client.writes
                          if table == "athlete_event"]
        self.assertEqual([row["event_time"] for row in athlete_writes], [1200.0, 4200.0])
        self.assertEqual(report["off_moments_updated"], 0)


if __name__ == "__main__":
    unittest.main()
