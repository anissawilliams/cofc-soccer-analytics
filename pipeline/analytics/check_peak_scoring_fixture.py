#!/usr/bin/env python3
"""
Run fixture-based checks for candidate PEAK scoring behavior.

The config validator checks that the rule table is well-formed. This script
checks that the scoring code applies the most important PEAK rules correctly:
Goal, Assist, Punish proxy, Advance threshold, contextual Shots, and excluded
labels.

Examples:
    python pipeline/analytics/check_peak_scoring_fixture.py
"""

from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


ANALYTICS_DIR = Path(__file__).resolve().parent
if str(ANALYTICS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYTICS_DIR))

from reconcile_coug_scores import (  # noqa: E402
    candidate_peak_event,
    load_peak_normalization,
    normalize_metric_name,
    summarize_trace,
)


def assert_close(actual: float, expected: float, label: str) -> None:
    if abs(float(actual) - float(expected)) > 1e-9:
        raise AssertionError(f"{label}: expected {expected}, got {actual}")


def make_event(raw_metric_name: str, raw_value: float = 1.0, context: dict | None = None) -> dict:
    return {
        "session_id": "fixture-session",
        "session_date": "2026-08-01",
        "season": "2026",
        "player": "Fixture Player",
        "player_key": "fixture player",
        "score_bucket": "peak",
        "event_score": 0.0,
        "raw_metric_name": raw_metric_name,
        "raw_value": raw_value,
        "raw_value_context": context or {},
    }


def build_fixture_trace() -> pd.DataFrame:
    events = [
        make_event("Goal"),
        make_event("Assist"),
        make_event("Opportunity"),
        make_event("Shots"),
        make_event("Shots", context={"all_labels": ["Opportunity"]}),
        make_event("Free kick shot"),
    ]
    events.extend(make_event("Smart pass") for _ in range(10))
    trace = pd.DataFrame(events)

    rules = load_peak_normalization()
    rules_by_key = {
        normalize_metric_name(row["raw_label_key"]): row
        for _, row in rules.iterrows()
    }
    scored = trace.apply(lambda row: candidate_peak_event(row, rules_by_key), axis=1)
    return pd.concat([trace, scored], axis=1)


def main() -> None:
    trace = build_fixture_trace()

    by_label = (
        trace.groupby("raw_metric_name")
        .agg(
            event_rows=("raw_metric_name", "size"),
            event_peak_score=("candidate_peak_score", "sum"),
            advance_actions=("candidate_advance_action", "sum"),
        )
        .reset_index()
    )
    score_by_label = dict(zip(by_label["raw_metric_name"], by_label["event_peak_score"]))
    actions_by_label = dict(zip(by_label["raw_metric_name"], by_label["advance_actions"]))

    assert_close(score_by_label["Goal"], 3.0, "Goal scorer PEAK")
    assert_close(score_by_label["Assist"], 2.0, "Assist PEAK")
    assert_close(score_by_label["Opportunity"], 0.2, "Punish Opportunity PEAK")
    assert_close(score_by_label["Shots"], 0.2, "Only contextual Shots should score as Punish")
    assert_close(score_by_label["Free kick shot"], 0.0, "Free kick shot should be excluded")
    assert_close(score_by_label["Smart pass"], 0.0, "Advance should not score per event")
    assert_close(actions_by_label["Smart pass"], 10.0, "Smart pass Advance actions")

    summary = summarize_trace(trace)
    if len(summary) != 1:
        raise AssertionError(f"Fixture should summarize to one player row, got {len(summary)}")
    row = summary.iloc[0]
    assert_close(row["candidate_base_peak_score"], 5.4, "Base candidate PEAK before Advance threshold")
    assert_close(row["candidate_advance_actions"], 10.0, "Advance action count")
    assert_close(row["candidate_advance_score"], 0.5, "Advance threshold score")
    assert_close(row["candidate_peak_score"], 5.9, "Total candidate PEAK")

    print("PEAK scoring fixture: all checks passed")
    print(f"Candidate PEAK total: {row['candidate_peak_score']:.1f}")


if __name__ == "__main__":
    main()
