from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from pipeline.scouting.opponent_shells import write_opponent_shells


class OpponentShellTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.output_root = Path(self.temp_dir.name)
        self.schedule = pd.DataFrame(
            [
                {
                    "match_date": "2026-08-07",
                    "opponent": "Wofford",
                    "home_away": "A",
                    "competition": "Exhibition",
                    "venue": "Spartanburg",
                    "match_status": "scheduled",
                    "opponent_team_id": "team-1",
                }
            ]
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_existing_staff_report_is_preserved_by_default(self) -> None:
        paths = write_opponent_shells(self.schedule, self.output_root, "CofC")
        paths[0].executive_brief.write_text("staff edits", encoding="utf-8")

        write_opponent_shells(self.schedule, self.output_root, "CofC")

        self.assertEqual(paths[0].executive_brief.read_text(encoding="utf-8"), "staff edits")

    def test_force_rebuilds_existing_report(self) -> None:
        paths = write_opponent_shells(self.schedule, self.output_root, "CofC")
        paths[0].executive_brief.write_text("staff edits", encoding="utf-8")

        write_opponent_shells(self.schedule, self.output_root, "CofC", force=True)

        self.assertNotEqual(paths[0].executive_brief.read_text(encoding="utf-8"), "staff edits")


if __name__ == "__main__":
    unittest.main()
