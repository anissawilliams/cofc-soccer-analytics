import os
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.main import app
from backend.staff_auth import (
    StaffAuthNotConfigured,
    authenticate_staff,
    require_staff,
    verify_staff_token,
)


client = TestClient(app)


class StaffAuthTests(unittest.TestCase):
    def test_missing_server_passcode_blocks_login(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(StaffAuthNotConfigured):
                authenticate_staff("anything", now=100)

    def test_valid_token_does_not_contain_passcode(self):
        with patch.dict(os.environ, {"COFC_STAFF_PASSCODE": "private-value"}, clear=True):
            token = authenticate_staff("private-value", now=100)
            self.assertNotIn("private-value", token)
            self.assertTrue(verify_staff_token(token, now=101))

    def test_wrong_passcode_and_tampered_token_are_rejected(self):
        with patch.dict(os.environ, {"COFC_STAFF_PASSCODE": "correct"}, clear=True):
            self.assertIsNone(authenticate_staff("wrong", now=100))
            token = authenticate_staff("correct", now=100)
            self.assertFalse(verify_staff_token(token + "x", now=101))

    def test_expired_token_is_rejected(self):
        env = {"COFC_STAFF_PASSCODE": "correct", "COFC_STAFF_TOKEN_TTL_SECONDS": "10"}
        with patch.dict(os.environ, env, clear=True):
            token = authenticate_staff("correct", now=100)
            self.assertFalse(verify_staff_token(token, now=111))

    def test_dependency_requires_bearer_token(self):
        with patch.dict(os.environ, {"COFC_STAFF_PASSCODE": "correct"}, clear=True):
            token = authenticate_staff("correct", now=100)
            with patch("backend.staff_auth.time.time", return_value=101):
                self.assertIsNone(require_staff(f"Bearer {token}"))
                with self.assertRaises(HTTPException) as raised:
                    require_staff("Bearer invalid")
                self.assertEqual(raised.exception.status_code, 401)

    def test_api_login_and_protected_route(self):
        with patch.dict(os.environ, {"COFC_STAFF_PASSCODE": "correct"}, clear=True):
            protected_paths = [
                "/api/player-stats",
                "/api/leaders/recoveries",
                "/api/team/passing",
                "/api/team/shots-by-time",
                "/api/team/formations",
                "/api/roster/development",
                "/api/match-story/session-1",
                "/api/shot-map/session-1",
                "/api/player-coug-trace/player-1?season=2026",
                "/api/staff/session-events",
                "/api/staff/session-events/options",
            ]
            for path in protected_paths:
                with self.subTest(path=path):
                    response = client.get(path)
                    self.assertEqual(response.status_code, 401)
                    self.assertEqual(response.headers["cache-control"], "no-store")
            self.assertEqual(
                client.post("/api/staff/login", json={"passcode": "wrong"}).status_code,
                401,
            )
            login = client.post("/api/staff/login", json={"passcode": "correct"})
            self.assertEqual(login.status_code, 200)
            token = login.json()["token"]
            with patch("backend.main.db.get_match_story", return_value={"events": []}):
                response = client.get(
                    "/api/match-story/session-1",
                    headers={"Authorization": f"Bearer {token}"},
                )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["cache-control"], "no-store")
            with patch("backend.main.db.get_match_shot_map", return_value={"shot_map": {"available": True}}):
                response = client.get(
                    "/api/shot-map/session-1",
                    headers={"Authorization": f"Bearer {token}"},
                )
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()["shot_map"]["available"])
            self.assertEqual(response.headers["cache-control"], "no-store")

    def test_published_player_history_remains_public(self):
        with patch("backend.main.db.get_player_match_history", return_value=[]):
            response = client.get("/api/player-match-history/player-1?season=2026")
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
