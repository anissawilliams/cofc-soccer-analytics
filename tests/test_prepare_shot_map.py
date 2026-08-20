import tempfile
import unittest
from pathlib import Path

from pipeline.ingestion.prepare_shot_map import build_snapshot


HEADER = "shot_id,team,sequence,player,minute,minute_label,outcome,shot_type,xg,xg_display,psxg,psxg_display,x,y,team_xg_total,team_psxg_total\n"


class PrepareShotMapTests(unittest.TestCase):
    def test_builds_reviewed_snapshot_and_preserves_official_totals(self):
        rows = (
            "home-1,Charleston Cougars,1,A Player,12,12,goal,Right foot,0.30,,0.50,,50,88,0.31,0.50\n"
            "away-1,Davidson Wildcats,1,B Player,20,20,wide,Left foot,,<0.01,,,42,71,0.01,0\n"
        )
        with tempfile.TemporaryDirectory() as root:
            path = Path(root, "shots.csv")
            path.write_text(HEADER + rows, encoding="utf-8")
            snapshot = build_snapshot(path, "Charleston Cougars", "Davidson Wildcats", "Wyscout")

        self.assertEqual(len(snapshot["shots"]), 2)
        self.assertEqual(snapshot["team_summaries"]["Charleston Cougars"]["xg"], 0.31)
        self.assertEqual(snapshot["shots"][1]["xg_display"], "<0.01")
        self.assertEqual(snapshot["coverage"]["xg_labeled_shots"], 2)

    def test_rejects_unknown_outcomes_and_out_of_range_coordinates(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root, "shots.csv")
            path.write_text(
                HEADER + "home-1,Charleston Cougars,1,A Player,12,12,saved,Right foot,0.3,,,,101,88,,\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "unsupported outcome"):
                build_snapshot(path, "Charleston Cougars", "Davidson Wildcats", "Wyscout")


if __name__ == "__main__":
    unittest.main()
