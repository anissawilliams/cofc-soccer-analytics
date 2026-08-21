import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline" / "ingestion"))

from pipeline.ingestion.load_match import (
    ALWAYS_COUNT,
    FWD_POS,
    NON_MINUS,
    PLUS_ONLY,
    WB_CROSS_THRESHOLD,
    WB_POS,
    WYSCOUT_SCORABLE_LABELS,
    _legacy_wyscout_scoring_rules,
    wyscout_event_passes_rule,
)


class MetricScoringRuleTests(unittest.TestCase):
    def test_free_kick_context_is_not_treated_as_a_scored_goal(self):
        self.assertNotIn("Free kick goal", WYSCOUT_SCORABLE_LABELS)
        self.assertNotIn("Free kick goal", _legacy_wyscout_scoring_rules())

    def test_legacy_rule_adapter_covers_the_exact_existing_taxonomy(self):
        rules = _legacy_wyscout_scoring_rules()

        self.assertEqual(set(rules), set(WYSCOUT_SCORABLE_LABELS))
        self.assertEqual(
            {label for label, rule in rules.items() if rule["outcome_rule"] == "plus_only"},
            PLUS_ONLY,
        )
        self.assertEqual(
            {label for label, rule in rules.items() if rule["outcome_rule"] == "non_minus"},
            NON_MINUS,
        )
        self.assertEqual(
            {label for label, rule in rules.items() if rule["outcome_rule"] == "always_count"},
            ALWAYS_COUNT,
        )

    def test_cross_rule_preserves_position_and_eight_event_threshold(self):
        rule = _legacy_wyscout_scoring_rules()["Cross"]

        self.assertEqual(set(rule["eligible_positions"]), WB_POS)
        self.assertEqual(rule["minimum_event_count"], WB_CROSS_THRESHOLD)
        self.assertEqual(
            wyscout_event_passes_rule(
                rule, position="WB", outcome="Unknown", event_count=8
            ),
            (True, None),
        )
        self.assertEqual(
            wyscout_event_passes_rule(
                rule, position="WB", outcome="Unknown", event_count=7
            ),
            (False, "threshold"),
        )
        self.assertEqual(
            wyscout_event_passes_rule(
                rule, position="CB", outcome="Unknown", event_count=8
            ),
            (False, "position"),
        )

    def test_shot_rule_preserves_forward_and_winger_positions(self):
        rule = _legacy_wyscout_scoring_rules()["Shots"]

        self.assertEqual(set(rule["eligible_positions"]), FWD_POS)
        for position in FWD_POS:
            self.assertEqual(
                wyscout_event_passes_rule(
                    rule, position=position, outcome="Unknown", event_count=1
                ),
                (True, None),
            )
        self.assertEqual(
            wyscout_event_passes_rule(
                rule, position="CB", outcome="Unknown", event_count=1
            ),
            (False, "position"),
        )

    def test_outcome_rules_preserve_plus_only_and_non_minus_behavior(self):
        rules = _legacy_wyscout_scoring_rules()

        self.assertEqual(
            wyscout_event_passes_rule(
                rules["Tackles"], position="CB", outcome="Plus", event_count=1
            ),
            (True, None),
        )
        self.assertEqual(
            wyscout_event_passes_rule(
                rules["Tackles"], position="CB", outcome="Unknown", event_count=1
            ),
            (False, "outcome"),
        )
        self.assertEqual(
            wyscout_event_passes_rule(
                rules["Pressing duel"], position="CB", outcome="Unknown", event_count=1
            ),
            (True, None),
        )
        self.assertEqual(
            wyscout_event_passes_rule(
                rules["Pressing duel"], position="CB", outcome="Minus", event_count=1
            ),
            (False, "outcome"),
        )

    def test_goalkeeper_include_and_exclude_rules_are_preserved(self):
        rules = _legacy_wyscout_scoring_rules()

        self.assertEqual(
            wyscout_event_passes_rule(
                rules["Saves"], position="GK", outcome="Unknown", event_count=1
            ),
            (True, None),
        )
        self.assertEqual(
            wyscout_event_passes_rule(
                rules["Saves"], position="CB", outcome="Unknown", event_count=1
            ),
            (False, "position"),
        )
        self.assertEqual(
            wyscout_event_passes_rule(
                rules["Goal"], position="GK", outcome="Unknown", event_count=1
            ),
            (False, "position"),
        )
        self.assertEqual(
            wyscout_event_passes_rule(
                rules["Goal"], position="F", outcome="Unknown", event_count=1
            ),
            (True, None),
        )

if __name__ == "__main__":
    unittest.main()
