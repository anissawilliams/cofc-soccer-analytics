# Score Reconciliation SOP

Purpose: make PEAK/ASET discrepancies explainable before changing weights.

## Source History

The Cougs Table started from Wyscout PDF match/player reports because that was the available source. Later, Wyscout event CSV/XML evidence became available, but some runs produced final score CSVs without durable `athlete_event` rows underneath. That made coach-vs-pipeline discrepancies hard to explain.

## Current Rule

Treat `athlete_event` as the official scoring evidence layer. Treat Wyscout
PDF reports as validation/comparison. Treat old PDF/Cougs CSV scores as
comparison baselines, not automatic truth.

Coach-confirmed PEAK rules as of 2026-07-13:

- Individual Wyscout events are sufficient.
- No sequence bonus.
- No coach/video confirmation gate.
- Advance = `0.5` points per `10` successful Advance actions.
- Punish and Advance should not double-count the same action.
- Punish takes priority.
- The 3-5 pass threshold divides Punish from Advance.

## Workflow

1. Inventory source files:

```bash
python pipeline/ingestion/inventory_sources.py --season 2025
```

2. Confirm event rows exist in Supabase for the match.

3. Generate reconciliation files:

```bash
python pipeline/analytics/reconcile_coug_scores.py --season 2025 --slug 2025-11-02_uncw
```

4. Review the output folder:

```text
pipeline/outputs/reports/score_reconciliation/2025/
```

Key files:

- `*_event_score_trace.csv`: one row per scored event, with raw Wyscout label, mapped COUG metric, bucket, raw value, weight, and event score.
- `*_pipeline_score_summary.csv`: event-derived player totals.
- `*_score_explainer.csv`: grouped player formulas, e.g. `11 x 0.25 = 2.75`, by raw label and mapped COUG metric. This is the best input for a future coach-facing drilldown view.
- `*_score_reconciliation.csv`: event-derived totals compared to legacy CSV and PDF-derived totals.

## Mapping Layer

Raw Wyscout labels are mapped to coach-facing COUG metrics in:

```text
pipeline/config/wyscout_coug_metric_map.csv
```

PEAK-specific normalization lives in:

```text
pipeline/config/wyscout_peak_normalization.csv
```

This file is intentionally reviewable. For PEAK, the scoring rule is now
confirmed, but the Wyscout label normalization table still needs to be tightened
so Advance, Punish, and the 3-5 pass threshold are encoded consistently. For
ASET and set pieces, rows marked `needs_coach_review` should still be discussed
before treating the score as final. For example, Wyscout `Pressing duel` can be
used as a review bridge to `Successful Counter Press`, but it is not identical
to a coach-defined counter press under five seconds.

## Granular Coach View

The future UI should be built from `*_score_explainer.csv` and `*_event_score_trace.csv`:

```text
Player -> bucket -> raw label -> mapped COUG metric -> event count -> raw value total -> weight -> score
```

Example:

```text
L. Gill | ASET | 1VS1 | Possession Regain | 11 events | 11 x 0.25 = 2.75
```

Then the event-level trace can show the timestamps and source context underneath that grouped value.

## How To Interpret Deltas

Large PEAK/ASET deltas usually mean one of these:

- Coach counted a manual concept that Wyscout cannot see, such as counter-press quality.
- PDF stat-report scoring used a different formula than the event-derived weights.
- A metric label maps to the wrong bucket or weight.
- Events were not loaded to `athlete_event` for that match.
- Spiideo/manual tags are missing for 2025 and should not be expected.

## Do Not Change Weights Blindly

Before changing a weight, identify whether the problem is source coverage, event mapping, positional filtering, or the actual coefficient.
