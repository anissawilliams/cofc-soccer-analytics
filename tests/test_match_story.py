import unittest

from db import _match_story_peak_coverage


class MatchStoryCoverageTests(unittest.TestCase):
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
