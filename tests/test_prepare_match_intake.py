import sys
import tempfile
import unittest
from pathlib import Path


INGESTION_DIR = Path(__file__).resolve().parents[1] / "pipeline" / "ingestion"
sys.path.insert(0, str(INGESTION_DIR))

from prepare_match_intake import (  # noqa: E402
    build_match_flow_snapshot,
    build_intake_report,
    discover_exports,
    merge_team_event_pair,
    profile_xml,
    validate_scoring_candidate,
)


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

    def test_match_flow_uses_two_team_canonical_pressure(self):
        events, summary = merge_team_event_pair([self.cofc, self.opponent], "2026-08-20_opponent")
        flow = build_match_flow_snapshot(events, summary, "2026-08-20_opponent")
        self.assertEqual(flow["home_team"], "Charleston Cougars")
        self.assertEqual(flow["away_team"], "Opponent FC")
        self.assertEqual(flow["bins"][2]["home"], 2.0)
        self.assertEqual(flow["bins"][11]["away"], 5.0)
        self.assertEqual(flow["goals"], [{"minute": 55.0, "team": "Opponent FC"}])

    def test_intake_separates_analytics_from_scoring_readiness(self):
        report, events = build_intake_report(self.root, "2026-08-20_opponent")
        self.assertTrue(report["analytics"]["ready"])
        self.assertFalse(report["scoring"]["ready"])
        self.assertEqual(len(events), 2)

    def test_scoring_candidate_is_roster_validated_before_ready(self):
        scoring_xml = """<root><instances>
          <instance><code>Offsets</code><start>0</start><end>0</end><label><text>First half start</text></label></instance>
          <instance><code>(3) J. Jordheim</code><start>60</start><end>62</end><label><text>Plus</text></label></instance>
          <instance><code>(7) Opponent Player</code><start>90</start><end>92</end><label><text>Minus</text></label></instance>
        </instances></root>"""
        (self.root / "random.xml").write_text(scoring_xml, encoding="utf-8")
        roster = self.root / "roster.csv"
        roster.write_text("number,name\n3,J. Jordheim\n", encoding="utf-8")

        status, parsed = validate_scoring_candidate(discover_exports(self.root), roster)

        self.assertTrue(status["ready"])
        self.assertEqual(status["scoring_events"], 1)
        self.assertEqual(status["all_player_events"], 2)
        self.assertEqual([event["name"] for event in parsed["player_events"]], ["J. Jordheim"])


if __name__ == "__main__":
    unittest.main()
