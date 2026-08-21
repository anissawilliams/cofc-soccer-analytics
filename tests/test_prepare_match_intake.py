import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


INGESTION_DIR = Path(__file__).resolve().parents[1] / "pipeline" / "ingestion"
sys.path.insert(0, str(INGESTION_DIR))

from prepare_match_intake import (  # noqa: E402
    build_approval_template,
    build_match_flow_snapshot,
    build_intake_report,
    build_validation_summary,
    discover_exports,
    inventory_source_files,
    merge_team_event_pair,
    profile_xml,
    render_validation_report,
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


def scoring_xml(player_codes):
    markers = [
        ("First half start", 0),
        ("First half end", 2700),
        ("Second half start", 2800),
        ("Second half end", 5500),
    ]
    instances = [
        f"<instance><code>Offsets</code><start>{start}</start><end>{start}</end>"
        f"<label><text>{label}</text></label></instance>"
        for label, start in markers
    ]
    instances.extend(
        f"<instance><code>{code}</code><start>{60 + index}</start><end>{62 + index}</end>"
        f"<label><text>Plus</text></label></instance>"
        for index, code in enumerate(player_codes)
    )
    return "<root><instances>" + "".join(instances) + "</instances></root>"


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
        self.assertEqual(len(report["source_manifest"]), 2)
        self.assertEqual(
            {row["relative_path"] for row in report["source_manifest"]},
            {"whatever-one.xml", "another export.xml"},
        )

    def test_source_inventory_fingerprints_vendor_files_without_renaming(self):
        pdf = self.root / "Wyscout report (final).pdf"
        pdf.write_bytes(b"sample report")

        manifest = inventory_source_files(self.root)
        item = next(row for row in manifest if row["relative_path"] == pdf.name)

        self.assertEqual(item["extension"], ".pdf")
        self.assertEqual(item["size_bytes"], 13)
        self.assertEqual(len(item["sha256"]), 64)

    def test_invalid_xml_is_reported_instead_of_crashing_intake(self):
        broken = self.root / "broken export.xml"
        broken.write_text("<not-closed>", encoding="utf-8")

        profile = profile_xml(broken)
        report, _ = build_intake_report(self.root, "2026-08-20_opponent")
        report["scoring"] = {"ready": False, "reason": "missing scoring export"}
        report["validation"] = build_validation_summary(report)

        self.assertEqual(profile.kind, "invalid_xml")
        self.assertTrue(profile.error)
        self.assertEqual(report["validation"]["status"], "blocked")
        self.assertIn("could not be read", report["validation"]["blocking_issues"][0])

    def test_validation_report_makes_staff_review_boundary_explicit(self):
        report, _ = build_intake_report(self.root, "2026-08-20_opponent")
        report["scoring"] = {"ready": False, "reason": "missing scoring export"}
        report["validation"] = build_validation_summary(report)

        rendered = render_validation_report(report)

        self.assertIn("ready_for_staff_review", rendered)
        self.assertIn("has not been published", rendered)
        self.assertIn("SHA-256", rendered)

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

    def test_scoring_candidate_prefers_unique_roster_scoped_export(self):
        (self.root / "combined.xml").write_text(
            scoring_xml(["(3) J. Jordheim", "(7) Opponent Player"]),
            encoding="utf-8",
        )
        cofc_path = self.root / "cofc-player-events.xml"
        cofc_path.write_text(
            scoring_xml(["(3) J. Jordheim", "(3) J. Jordheim"]),
            encoding="utf-8",
        )
        (self.root / "opponent-player-events.xml").write_text(
            scoring_xml(["(7) Opponent Player", "(8) Other Opponent"]),
            encoding="utf-8",
        )
        roster = self.root / "roster.csv"
        roster.write_text("number,name\n3,J. Jordheim\n", encoding="utf-8")

        status, parsed = validate_scoring_candidate(discover_exports(self.root), roster)

        self.assertTrue(status["ready"])
        self.assertEqual(status["selected_file"], cofc_path.name)
        self.assertEqual(len(parsed["player_events"]), 2)
        evaluations = {item["file"]: item for item in status["candidate_evaluations"]}
        self.assertEqual(evaluations[cofc_path.name]["roster_match_ratio"], 1.0)
        self.assertEqual(evaluations[cofc_path.name]["roster_matched_players"], 1)
        self.assertEqual(evaluations["opponent-player-events.xml"]["roster_matched_events"], 0)

    def test_scoring_candidate_prioritizes_roster_coverage_over_tiny_perfect_file(self):
        complete_path = self.root / "combined.xml"
        complete_path.write_text(
            scoring_xml([
                "(3) J. Jordheim",
                "(17) R. Watson",
                "(7) Opponent Player",
            ]),
            encoding="utf-8",
        )
        (self.root / "tiny.xml").write_text(
            scoring_xml(["(3) J. Jordheim"]),
            encoding="utf-8",
        )
        roster = self.root / "roster.csv"
        roster.write_text(
            "number,name\n3,J. Jordheim\n17,R. Watson\n",
            encoding="utf-8",
        )

        status, parsed = validate_scoring_candidate(discover_exports(self.root), roster)

        self.assertTrue(status["ready"])
        self.assertEqual(status["selected_file"], complete_path.name)
        self.assertEqual({event["name"] for event in parsed["player_events"]}, {"J. Jordheim", "R. Watson"})

    def test_scoring_candidate_uses_profile_identity_not_duplicate_basename(self):
        weak_dir = self.root / "weak"
        strong_dir = self.root / "strong"
        weak_dir.mkdir()
        strong_dir.mkdir()
        filename = "player-events.xml"
        (weak_dir / filename).write_text(
            scoring_xml(["(3) J. Jordheim", "(7) Opponent Player"]),
            encoding="utf-8",
        )
        strong_path = strong_dir / filename
        strong_path.write_text(
            scoring_xml(["(3) J. Jordheim", "(17) R. Watson"]),
            encoding="utf-8",
        )
        roster = self.root / "roster.csv"
        roster.write_text(
            "number,name\n3,J. Jordheim\n17,R. Watson\n",
            encoding="utf-8",
        )

        status, parsed = validate_scoring_candidate(discover_exports(self.root), roster)

        self.assertTrue(status["ready"])
        self.assertEqual(status["selected_file"], filename)
        self.assertEqual(status["selected_path"], strong_path.as_posix())
        self.assertEqual({event["name"] for event in parsed["player_events"]}, {"J. Jordheim", "R. Watson"})

    def test_equally_strong_scoring_candidates_fail_closed(self):
        for directory in (self.root / "one", self.root / "two"):
            directory.mkdir()
            (directory / "player-events.xml").write_text(
                scoring_xml(["(3) J. Jordheim"]),
                encoding="utf-8",
            )
        roster = self.root / "roster.csv"
        roster.write_text("number,name\n3,J. Jordheim\n", encoding="utf-8")

        status, parsed = validate_scoring_candidate(discover_exports(self.root), roster)

        self.assertFalse(status["ready"])
        self.assertIsNone(parsed)
        self.assertIn("staff selection required", status["reason"])

    def test_cli_creates_review_bundle_without_publishing(self):
        output_temp = tempfile.TemporaryDirectory()
        self.addCleanup(output_temp.cleanup)
        output_dir = Path(output_temp.name)
        metadata = self.root / "metadata.json"
        metadata.write_text(json.dumps({"opponent": "Opponent FC"}), encoding="utf-8")
        roster = self.root / "roster.csv"
        roster.write_text("number,name\n3,J. Jordheim\n", encoding="utf-8")
        script = INGESTION_DIR / "prepare_match_intake.py"

        completed = subprocess.run([
            sys.executable,
            str(script),
            "--input-dir", str(self.root),
            "--output-dir", str(output_dir),
            "--season", "2026",
            "--slug", "2026-08-20_opponent",
            "--roster", str(roster),
            "--metadata", str(metadata),
        ], check=True, capture_output=True, text=True)

        self.assertEqual(json.loads(completed.stdout)["slug"], "2026-08-20_opponent")
        self.assertIn("Prepared intake outputs:", completed.stderr)

        saved = json.loads(
            (output_dir / "2026-08-20_opponent_intake_report.json").read_text(encoding="utf-8")
        )
        self.assertEqual(saved["validation"]["status"], "ready_for_staff_review")
        self.assertFalse(saved["validation"]["published"])
        self.assertEqual(saved["metadata"]["opponent"], "Opponent FC")
        self.assertTrue((output_dir / "2026-08-20_opponent_validation_report.md").exists())
        self.assertTrue((output_dir / "2026-08-20_opponent_match_flow.json").exists())
        approval_path = output_dir / "2026-08-20_opponent_approval.json"
        approval = json.loads(approval_path.read_text(encoding="utf-8"))
        self.assertEqual(approval, build_approval_template(saved, output_dir / "2026-08-20_opponent_intake_report.json"))
        self.assertFalse(any(approval["approvals"].values()))

    def test_dry_run_stdout_remains_valid_json_when_scoring_is_ready(self):
        (self.root / "cofc-player-events.xml").write_text(
            scoring_xml(["(3) J. Jordheim"]),
            encoding="utf-8",
        )
        roster = self.root / "roster.csv"
        roster.write_text("number,name\n3,J. Jordheim\n", encoding="utf-8")
        script = INGESTION_DIR / "prepare_match_intake.py"

        completed = subprocess.run([
            sys.executable,
            str(script),
            "--input-dir", str(self.root),
            "--season", "2026",
            "--slug", "2026-08-20_opponent",
            "--roster", str(roster),
            "--dry-run",
        ], check=True, capture_output=True, text=True)

        report = json.loads(completed.stdout)
        self.assertTrue(report["scoring"]["ready"])
        self.assertIn("Sportscode:", completed.stderr)


if __name__ == "__main__":
    unittest.main()
