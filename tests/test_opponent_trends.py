import tempfile
import unittest
from pathlib import Path

import pandas as pd

from pipeline.scouting.features import MATCH_COLUMNS
from pipeline.scouting.opponent_trends import (
    _parse_match_report_text,
    build_opponent_trends,
    load_opponent_history,
    summarize_recent_form,
)


class OpponentTrendTests(unittest.TestCase):
    def test_parses_full_wyscout_match_report_text(self):
        cover = """MATCH REPORT
UNCW Seahawks
Elon Phoenix
1 – 0
05/09/2026 United States. NCAA D1 Coastal Athletic Association Round 2
"""
        stats = """Goals 1 0
xG 0.65 0.88
Shots / on target 9/4 7/3
Recoveries / low / medium / high 67/36/23/8 88/36/35/17
Losses / low / medium / high 107/19/40/48 114/9/39/66
Total duels / won 211/98 46% 211/107 51%
Possession % 45 55
Total passes / accurate 347/280 81% 489/410 84%
"""
        frame = _parse_match_report_text(cover, stats, "Elon Phoenix")
        self.assertEqual(list(frame["team"]), ["UNCW Seahawks", "Elon Phoenix"])
        self.assertEqual(list(frame["result"]), ["W", "L"])
        elon = frame.iloc[1]
        self.assertEqual(elon["xg"], 0.88)
        self.assertEqual(elon["shots_on_target"], 3)
        self.assertEqual(elon["recoveries_high"], 17)
        self.assertEqual(elon["passes_accurate"], 410)

    def _row(self, date, match, team, goals, xg):
        values = {column: 0 for column in MATCH_COLUMNS}
        values.update(
            date=date,
            match=match,
            competition="NCAA",
            duration=90,
            team=team,
            goals=goals,
            xg=xg,
            shots=10,
            shots_on_target=4,
            pass_accuracy_pct=80,
            possession_pct=50,
            recoveries=40,
            duels_won=25,
        )
        return values

    def test_cutoff_excludes_scouted_match_and_future_data(self):
        rows = [
            self._row("2026-08-01", "Eagles - Bears 2:0", "Eagles", 2, 1.5),
            self._row("2026-08-01", "Eagles - Bears 2:0", "Bears", 0, 0.4),
            self._row("2026-09-08", "Cougars - Eagles 1:1", "Cougars", 1, 1.0),
            self._row("2026-09-08", "Cougars - Eagles 1:1", "Eagles", 1, 0.9),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.csv"
            pd.DataFrame(rows).to_csv(path, index=False)
            history = load_opponent_history([path], "Eagles", "2026-09-08")
        self.assertEqual(set(history["match"]), {"Eagles - Bears 2:0"})

    def test_builds_leakage_safe_rolling_form_and_summary(self):
        rows = []
        for date, match, opponent, goals_for, goals_against in [
            ("2026-08-01", "Eagles - Bears 2:0", "Bears", 2, 0),
            ("2026-08-08", "Lions - Eagles 1:1", "Lions", 1, 1),
        ]:
            rows.append(self._row(date, match, "Eagles", goals_for, 1.4))
            rows.append(self._row(date, match, opponent, goals_against, 0.7))
        frame = pd.DataFrame(rows)
        frame["date"] = pd.to_datetime(frame["date"])
        frame["is_target_team"] = frame["team"].eq("Eagles")
        frame["result"] = ["W", "L", "D", "D"]
        trends = build_opponent_trends(frame, "Eagles")
        self.assertTrue(pd.isna(trends.loc[0, "rolling_points_last3"]))
        self.assertEqual(trends.loc[1, "rolling_points_last3"], 3)
        summary = summarize_recent_form(trends)
        self.assertEqual(summary["record"], {"W": 1, "D": 1, "L": 0})

    def test_rejects_single_team_match_exports(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.csv"
            pd.DataFrame(
                [self._row("2026-08-01", "Eagles - Bears 2:0", "Eagles", 2, 1.5)]
            ).to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, "exactly two team rows"):
                load_opponent_history([path], "Eagles")


if __name__ == "__main__":
    unittest.main()
