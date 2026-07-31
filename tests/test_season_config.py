from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from backend.season_config import get_active_season, season_payload


class SeasonConfigTests(unittest.TestCase):
    def test_tracked_active_season_is_2026(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(get_active_season(), "2026")

    def test_environment_can_override_active_season(self) -> None:
        with patch.dict(os.environ, {"COFC_ACTIVE_SEASON": "2027"}, clear=True):
            self.assertEqual(get_active_season(), "2027")

    def test_payload_includes_active_season_first(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                season_payload(["2025", "2024"]),
                {
                    "active_season": "2026",
                    "seasons": ["2026", "2025", "2024"],
                },
            )


if __name__ == "__main__":
    unittest.main()
