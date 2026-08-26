import unittest
from pathlib import Path

from db import _match_story_peak_coverage, _published_match_totals


class MatchStoryCoverageTests(unittest.TestCase):
    def test_match_story_reads_the_canonical_weight_version_relationship(self):
        source = (Path(__file__).resolve().parents[1] / "db.py").read_text(encoding="utf-8")
        self.assertIn(
            '"weight_version:weight_version_id(version)"',
            source,
        )
        self.assertNotIn("scoring_version:scoring_version_id(version)", source)

    def test_published_totals_use_only_match_rows_for_selected_version(self):
        rows = [
            {
                "aset_score": 2,
                "peak_score": 3,
                "set_piece_score": 4,
                "positional_score": 5,
                "load_score": 6,
                "total_score": 20,
                "score_type": "match",
                "weight_version": {"version": "trial_1"},
            },
            {
                "aset_score": 100,
                "total_score": 100,
                "score_type": "legacy",
                "weight_version": {"version": "trial_1"},
            },
            {
                "aset_score": 200,
                "total_score": 200,
                "score_type": "match",
                "weight_version": {"version": "old"},
            },
        ]

        self.assertEqual(
            _published_match_totals(rows, "trial_1"),
            {
                "published": True,
                "published_score_rows": 1,
                "aset": 2.0,
                "peak": 3.0,
                "set_piece": 4.0,
                "positional": 5.0,
                "load": 6.0,
                "total": 20.0,
            },
        )

    def test_no_published_rows_does_not_promote_event_evidence_to_score(self):
        totals = _published_match_totals([], "trial_1")
        self.assertFalse(totals["published"])
        self.assertEqual(totals["total"], 0)

    def test_partial_timed_peak_reports_honest_gap(self):
        self.assertEqual(
            _match_story_peak_coverage(3.4, 4.0),
            {
                "published_peak": 4.0,
                "untimed_peak": 0.6,
                "peak_coverage_ratio": 0.85,
            },
        )

    def test_no_published_peak_has_no_ratio(self):
        self.assertEqual(
            _match_story_peak_coverage(0, 0),
            {
                "published_peak": 0.0,
                "untimed_peak": 0.0,
                "peak_coverage_ratio": None,
            },
        )

    def test_timed_evidence_above_rollup_never_creates_negative_gap(self):
        coverage = _match_story_peak_coverage(5, 4)
        self.assertEqual(coverage["untimed_peak"], 0)
        self.assertEqual(coverage["peak_coverage_ratio"], 1.0)


if __name__ == "__main__":
    unittest.main()
