from __future__ import annotations

import csv
import importlib.util
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd


MODULE_PATH = Path(__file__).resolve().parents[1] / "pipeline" / "analytics" / "preflight_check.py"
SPEC = importlib.util.spec_from_file_location("preflight_check", MODULE_PATH)
assert SPEC and SPEC.loader
preflight = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = preflight
SPEC.loader.exec_module(preflight)


class PreflightCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.triage_path = self.root / "triage.csv"
        self.signoffs_path = self.root / "signoffs.csv"
        pd.DataFrame(
            [
                {
                    "slug": "2025-01-01_example",
                    "triage_status": "needs_source_review",
                    "triage_player": "A. Player",
                    "legacy_peak": 3,
                },
                {
                    "slug": "2025-01-01_example",
                    "triage_status": "within_threshold",
                    "triage_player": "B. Player",
                    "legacy_peak": 0,
                },
                {
                    "slug": "2025-01-01_example",
                    "triage_status": "legacy_only_player",
                    "triage_player": "C. Player",
                    "legacy_peak": 0,
                },
            ]
        ).to_csv(self.triage_path, index=False)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_signoffs(self, rows: list[dict[str, str]]) -> None:
        with self.signoffs_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=preflight.SIGNOFF_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)

    def test_documented_source_gap_passes_with_warning(self) -> None:
        self.write_signoffs(
            [
                {
                    "season": "2025",
                    "slug": "2025-01-01_example",
                    "player_key": "A. Player",
                    "issue_type": "needs_source_review",
                    "disposition": "source_missing",
                    "note": "Supplemental XML is unavailable.",
                    "reviewed_by": "analyst",
                    "reviewed_date": "2026-07-27",
                }
            ]
        )

        issues = preflight.load_actionable_issues(self.triage_path, "2025")
        signoffs, errors = preflight.load_signoffs(self.signoffs_path)

        self.assertEqual(len(issues), 1)
        self.assertFalse(errors)
        self.assertEqual(signoffs[issues[0].key]["disposition"], "source_missing")

    def test_missing_signoff_is_detectable_as_a_block(self) -> None:
        self.write_signoffs([])

        issues = preflight.load_actionable_issues(self.triage_path, "2025")
        signoffs, errors = preflight.load_signoffs(self.signoffs_path)

        self.assertEqual(len(issues), 1)
        self.assertFalse(errors)
        self.assertNotIn(issues[0].key, signoffs)

    def test_positive_legacy_only_player_requires_review(self) -> None:
        triage = pd.read_csv(self.triage_path)
        triage.loc[triage["triage_player"].eq("C. Player"), "legacy_peak"] = 2
        triage.to_csv(self.triage_path, index=False)

        issues = preflight.load_actionable_issues(self.triage_path, "2025")

        self.assertEqual(
            {(issue.player_key, issue.issue_type) for issue in issues},
            {
                ("A. Player", "needs_source_review"),
                ("C. Player", "legacy_only_player"),
            },
        )


if __name__ == "__main__":
    unittest.main()
