import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import db
from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


class FakeQuery:
    def __init__(self, rows, inserted):
        self.rows = list(rows)
        self.inserted = inserted

    def select(self, _columns):
        return self

    def eq(self, column, value):
        self.rows = [row for row in self.rows if row.get(column) == value]
        return self

    def insert(self, payload):
        self.inserted.append(payload)
        self.rows = [{"id": "event-1", **payload}]
        return self

    def execute(self):
        return SimpleNamespace(data=self.rows)


class FakeDbClient:
    def __init__(self, tables):
        self.tables = tables
        self.inserted = []

    def table(self, name):
        return FakeQuery(self.tables.get(name, []), self.inserted)


def staff_headers():
    login = client.post("/api/staff/login", json={"passcode": "correct"})
    return {"Authorization": f"Bearer {login.json()['token']}"}


class SessionEventApiTests(unittest.TestCase):
    def test_event_log_routes_are_staff_only(self):
        self.assertEqual(client.get("/api/staff/session-events").status_code, 401)
        self.assertEqual(client.get("/api/staff/session-events/options").status_code, 401)
        self.assertEqual(
            client.post("/api/staff/session-events", json={
                "session_id": "session-1",
                "event_type": "yellow_card",
            }).status_code,
            401,
        )

    def test_staff_can_create_informational_event(self):
        created = {"id": "event-1", "score_status": "informational"}
        with (
            patch.dict(os.environ, {"COFC_STAFF_PASSCODE": "correct"}, clear=True),
            patch("backend.main.db.create_session_event", return_value=created) as create,
        ):
            response = client.post(
                "/api/staff/session-events",
                headers=staff_headers(),
                json={
                    "session_id": "session-1",
                    "event_type": "coach_observation",
                    "notes": "Good response after losing possession.",
                },
            )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), created)
        payload = create.call_args.args[0]
        self.assertIsNone(payload["metric_weight_id"])
        self.assertEqual(payload["raw_value"], 1.0)

    def test_database_validation_is_returned_as_bad_request(self):
        with (
            patch.dict(os.environ, {"COFC_STAFF_PASSCODE": "correct"}, clear=True),
            patch("backend.main.db.create_session_event", side_effect=ValueError(
                "A weighted event must be assigned to an athlete."
            )),
        ):
            response = client.post(
                "/api/staff/session-events",
                headers=staff_headers(),
                json={
                    "session_id": "session-1",
                    "event_type": "yellow_card",
                    "metric_weight_id": "weight-1",
                },
            )
        self.assertEqual(response.status_code, 400)
        self.assertIn("assigned to an athlete", response.json()["detail"])


class SessionEventDatabaseTests(unittest.TestCase):
    def test_weighted_event_resolves_exact_active_weight_and_stays_pending(self):
        fake = FakeDbClient({
            "session": [{"id": "session-1", "session_type": "match"}],
            "athlete": [{"id": "athlete-1"}],
            "metric_weight": [{
                "id": "weight-1",
                "version": db.COUG_TABLE_WEIGHT_VERSION,
                "effective_to": None,
                "metric": {"applies_to_session_type": "match"},
            }],
        })
        with patch.object(db, "get_client", return_value=fake):
            result = db.create_session_event({
                "session_id": "session-1",
                "athlete_id": "athlete-1",
                "event_type": "yellow_card",
                "metric_weight_id": "weight-1",
                "raw_value": 1,
                "event_time": 3840,
                "notes": "Tactical foul",
                "recorded_by": "AW",
            })
        self.assertEqual(result["score_status"], "pending_review")
        self.assertEqual(fake.inserted[0]["metric_weight_id"], "weight-1")
        self.assertEqual(fake.inserted[0]["event_time"], 3840)

    def test_weighted_event_rejects_metric_for_wrong_session_type(self):
        fake = FakeDbClient({
            "session": [{"id": "training-1", "session_type": "training"}],
            "athlete": [{"id": "athlete-1"}],
            "metric_weight": [{
                "id": "weight-1",
                "version": db.COUG_TABLE_WEIGHT_VERSION,
                "effective_to": None,
                "metric": {"applies_to_session_type": "match"},
            }],
        })
        with patch.object(db, "get_client", return_value=fake):
            with self.assertRaisesRegex(ValueError, "does not apply to a training session"):
                db.create_session_event({
                    "session_id": "training-1",
                    "athlete_id": "athlete-1",
                    "event_type": "training_action",
                    "metric_weight_id": "weight-1",
                })
        self.assertEqual(fake.inserted, [])


class SessionEventContractTests(unittest.TestCase):
    def test_migration_keeps_weighted_events_pending_review(self):
        sql = Path("schema/2026_08_session_event.sql").read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE IF NOT EXISTS public.session_event", sql)
        self.assertIn("metric_weight_id    UUID REFERENCES public.metric_weight(id)", sql)
        self.assertIn("metric_weight_id IS NULL OR athlete_id IS NOT NULL", sql)
        self.assertIn("pending_review", sql)
        self.assertIn("ENABLE ROW LEVEL SECURITY", sql)

    def test_red_card_metric_migration_is_idempotent_and_weighted(self):
        sql = Path("schema/2026_08_red_card_metric.sql").read_text(encoding="utf-8")
        self.assertIn("'Red Card'", sql)
        self.assertIn("-2", sql)
        self.assertIn("NOT EXISTS", sql)
        self.assertIn("information_schema.columns", sql)
        self.assertIn("column_name = 'scoring_version_id'", sql)

    def test_staff_page_uses_approved_weight_and_review_language(self):
        source = Path("frontend/src/SessionEventLog.jsx").read_text(encoding="utf-8")
        self.assertIn("Propose a COUG score contribution", source)
        self.assertIn("Select approved weight", source)
        self.assertIn("Pending review—not yet added to the published table", source)
        self.assertIn("staffApiFetch('/api/staff/session-events'", source)

    def test_staff_portal_exposes_event_log_tab(self):
        source = Path("frontend/src/StaffPortal.jsx").read_text(encoding="utf-8")
        self.assertIn("['events', 'Event Log']", source)
        self.assertIn("section === 'events' && <SessionEventLog />", source)


if __name__ == "__main__":
    unittest.main()
