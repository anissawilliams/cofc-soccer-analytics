import sys
import tempfile
import unittest
from pathlib import Path


INGESTION_DIR = Path(__file__).resolve().parents[1] / "pipeline" / "ingestion"
sys.path.insert(0, str(INGESTION_DIR))

from parse_wyscout import parse_sportscode  # noqa: E402


class WyscoutTimelineTests(unittest.TestCase):
    def test_events_receive_half_relative_match_minutes(self):
        xml = """<root><instances>
          <instance><code>Offsets</code><start>100</start><end>100</end><label><text>First half start</text></label></instance>
          <instance><code>Offsets</code><start>4000</start><end>4000</end><label><text>Second half start</text></label></instance>
          <instance><code>(3) J. Jordheim</code><start>700</start><end>702</end><label><text>Plus</text></label></instance>
          <instance><code>(9) M. Takanashi</code><start>4600</start><end>4602</end><label><text>Goal</text></label></instance>
        </instances></root>"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "match.xml"
            path.write_text(xml, encoding="utf-8")
            events = parse_sportscode(path)["player_events"]

        self.assertEqual(events[0]["half"], 1)
        self.assertEqual(events[0]["match_minute"], 10.0)
        self.assertEqual(events[1]["half"], 2)
        self.assertEqual(events[1]["match_minute"], 55.0)

    def test_blank_code_half_markers_are_detected_from_labels(self):
        xml = """<root><instances>
          <instance><code></code><start>1</start><end>4</end><label><text>First half start</text></label></instance>
          <instance><code></code><start>3197</start><end>3200</end><label><text>Second half start</text></label></instance>
          <instance><code>(3) J. Jordheim</code><start>3797</start><end>3799</end><label><text>Plus</text></label></instance>
        </instances></root>"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "team-scoped-player-events.xml"
            path.write_text(xml, encoding="utf-8")
            parsed = parse_sportscode(path)

        self.assertEqual(parsed["halves"]["first_start"], 1.0)
        self.assertEqual(parsed["halves"]["second_start"], 3197.0)
        self.assertEqual(parsed["player_events"][0]["half"], 2)
        self.assertEqual(parsed["player_events"][0]["match_minute"], 55.0)

    def test_roster_filter_preserves_non_roster_events_in_raw_stream(self):
        xml = """<root><instances>
          <instance><code>Offsets</code><start>0</start><end>0</end><label><text>First half start</text></label></instance>
          <instance><code>(3) J. Jordheim</code><start>60</start><end>62</end><label><text>Plus</text></label></instance>
          <instance><code>(7) Opponent Player</code><start>90</start><end>92</end><label><text>Minus</text></label></instance>
          <instance><code>Team transition</code><start>95</start><end>97</end><label><text>Counter</text></label></instance>
        </instances></root>"""
        roster = "number,name\n3,J. Jordheim\n"
        with tempfile.TemporaryDirectory() as directory:
            xml_path = Path(directory) / "match.xml"
            roster_path = Path(directory) / "roster.csv"
            xml_path.write_text(xml, encoding="utf-8")
            roster_path.write_text(roster, encoding="utf-8")
            parsed = parse_sportscode(xml_path, roster_path=roster_path)

        self.assertEqual([event["name"] for event in parsed["player_events"]], ["J. Jordheim"])
        self.assertEqual(len(parsed["all_player_events"]), 2)
        self.assertTrue(parsed["all_player_events"][0]["roster_match"])
        self.assertFalse(parsed["all_player_events"][1]["roster_match"])
        self.assertEqual(len(parsed["team_events"]), 1)


if __name__ == "__main__":
    unittest.main()
