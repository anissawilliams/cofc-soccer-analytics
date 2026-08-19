import sys
import tempfile
import unittest
from pathlib import Path


INGESTION_DIR = Path(__file__).resolve().parents[1] / "pipeline" / "ingestion"
sys.path.insert(0, str(INGESTION_DIR))

from prepare_match_intake import build_intake_report, merge_team_event_pair, profile_xml  # noqa: E402


def team_xml(team, rows):
    instances = []
    for index, (start, end, label, code) in enumerate(rows, 1):
        instances.append(
            f"<instance><ID>{index}</ID><start>{start}</start><end>{end}</end>"
            f"<code>{code if code is not None else team}</code>"
            f"<label><text>{label}</text></label></instance>"
        )
    return "<file><ALL_INSTANCES>" + "".join(instances) + "</ALL_INSTANCES></file>"


class MatchIntakeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        common_markers = [
            (2, 2, "First half start", ""),
            (2702, 2702, "First half end", ""),
            (2800, 2800, "Second half start", ""),
            (5500, 5500, "Second half end", ""),
        ]
        cofc_rows = common_markers + [
            (602, 606, "Shots", None),
            (3400, 3405, "Goals conceded", None),
        ]
        opponent_rows = common_markers + [
            (602, 606, "Shots conceded", None),
            (3400, 3405, "Goals scored", None),
        ]
        self.cofc = self.root / "whatever-one.xml"
        self.opponent = self.root / "another export.xml"
        self.cofc.write_text(team_xml("Charleston Cougars", cofc_rows), encoding="utf-8")
        self.opponent.write_text(team_xml("Opponent FC", opponent_rows), encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_team_xml_is_classified_from_contents_not_filename(self):
        profile = profile_xml(self.cofc)
        self.assertEqual(profile.kind, "team_event_xml")
        self.assertEqual(profile.team, "Charleston Cougars")

    def test_mirrored_perspectives_are_deduplicated(self):
        events, summary = merge_team_event_pair([self.cofc, self.opponent], "2026-08-20_opponent")
        self.assertEqual(len(events), 2)
        self.assertEqual(summary["source_observations"], 4)
        self.assertEqual(summary["mirrored_events"], 2)
        shot = next(event for event in events if event["event_type"] == "shot")
        goal = next(event for event in events if event["event_type"] == "goal")
        self.assertEqual(shot["team"], "Charleston Cougars")
        self.assertEqual(shot["match_minute"], 10.0)
        self.assertEqual(goal["team"], "Opponent FC")
        self.assertEqual(goal["half"], 2)
        self.assertEqual(goal["match_minute"], 55.0)

    def test_intake_separates_analytics_from_scoring_readiness(self):
        report, events = build_intake_report(self.root, "2026-08-20_opponent")
        self.assertTrue(report["analytics"]["ready"])
        self.assertFalse(report["scoring"]["ready"])
        self.assertIn("do not publish", report["scoring"]["reason"])
        self.assertEqual(len(events), 2)


if __name__ == "__main__":
    unittest.main()
