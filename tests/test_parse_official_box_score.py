import sys
import tempfile
import unittest
from pathlib import Path


INGESTION_DIR = Path(__file__).resolve().parents[1] / "pipeline" / "ingestion"
sys.path.insert(0, str(INGESTION_DIR))

from parse_official_box_score import parse_official_minutes_text  # noqa: E402


class OfficialBoxScoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.roster = Path(self.temp.name) / "roster.csv"
        names = ["A. One", "B. Two", "C. Three", "D. Four", "E. Five", "F. Six",
                 "G. Seven", "H. Eight", "I. Nine", "J. Ten", "K. Eleven", "L. Twelve"]
        self.roster.write_text(
            "number,name\n" + "".join(f"{index},{name}\n" for index, name in enumerate(names, 1)),
            encoding="utf-8",
        )

    def _box_score_text(self, cofc_on_right=True):
        opponent_rows = [f"def  {index:<4} Opp {index:<20} - - - - - 90" for index in range(1, 12)]
        cofc_rows = [
            f"def  {index:<4} {chr(64 + index)}. {word:<18} - - - - - {90 if index < 12 else 25}"
            for index, word in enumerate(
                ["One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven"], 1
            )
        ]
        left_team, right_team = (
            ("Opponent FC", "Col. of Charleston")
            if cofc_on_right else ("Col. of Charleston", "Opponent FC")
        )
        left_rows, right_rows = (
            (opponent_rows, cofc_rows) if cofc_on_right else (cofc_rows, opponent_rows)
        )
        lines = [
            "Official Soccer Box Score - Final",
            left_team.ljust(80) + right_team,
            "Pos  ##    Player                 Sh SO G A Fo Min".ljust(80)
            + "Pos  ##    Player                 Sh SO G A Fo Min",
        ]
        lines.extend(left.ljust(80) + right for left, right in zip(left_rows, right_rows))
        lines.append("           -- Substitutes --".ljust(80) + "           -- Substitutes --")
        substitute = "     12    L. Twelve          - - - - - 25"
        lines.append("".ljust(80) + substitute if cofc_on_right else substitute.ljust(80))
        lines.append("## Goalkeepers".ljust(80) + "## Goalkeepers")
        return "\n".join(lines)

    def test_parses_right_hand_cofc_column_and_substitutes(self):
        rows = parse_official_minutes_text(
            self._box_score_text(cofc_on_right=True), self.roster, "official.pdf"
        )

        self.assertEqual(len(rows), 12)
        self.assertEqual(sum(row["started"] for row in rows), 11)
        self.assertEqual(rows[-1]["player_name"], "L. Twelve")
        self.assertEqual(rows[-1]["official_name"], "L. Twelve")
        self.assertEqual(rows[-1]["estimated_minutes"], 25)

    def test_parses_left_hand_cofc_column(self):
        rows = parse_official_minutes_text(
            self._box_score_text(cofc_on_right=False), self.roster, "official.pdf"
        )

        self.assertEqual(len(rows), 12)
        self.assertEqual(sum(row["started"] for row in rows), 11)

    def test_rejects_non_official_pdf_text(self):
        with self.assertRaisesRegex(ValueError, "not an official"):
            parse_official_minutes_text("Wyscout match report", self.roster, "wyscout.pdf")
