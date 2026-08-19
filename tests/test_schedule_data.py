from __future__ import annotations

import unittest

from backend.schedule_data import load_api_schedule


class ScheduleDataTests(unittest.TestCase):
    def test_2026_schedule_is_loaded_from_tracked_config(self) -> None:
        matches = load_api_schedule("2026")

        self.assertEqual(len(matches), 19)
        self.assertEqual(matches[0]["id"], "2026-08-07_wofford")
        self.assertEqual(matches[0]["opponent"], "Wofford")
        self.assertEqual(matches[-1]["opponent"], "Mercer")

    def test_schedule_rows_have_frontend_contract(self) -> None:
        match = load_api_schedule("2026")[5]

        self.assertEqual(match["opponent"], "Campbell")
        self.assertEqual(match["homeAway"], "H")
        self.assertTrue(match["conference"])
        self.assertEqual(match["competition"], "CAA")

    def test_season_without_configured_schedule_is_empty(self) -> None:
        self.assertEqual(load_api_schedule("2025"), [])


if __name__ == "__main__":
    unittest.main()
