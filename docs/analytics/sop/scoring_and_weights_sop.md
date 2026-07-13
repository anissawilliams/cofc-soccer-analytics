# Scoring & Weights SOP

Last updated: 2026-07-13

Purpose: document the current scoring source of truth, confirmed coach rules,
and what still needs implementation/normalization.

## 1. Source Of Truth

Official COUG Table scoring should be event-derived.

- Primary source: database-backed `athlete_event` rows
- Validation/comparison source: Wyscout PDF player reports
- Legacy CSVs/spreadsheets: useful for reconciliation, not automatic truth

The reconciliation workflow should explain differences between event-derived
scores and validation sources before any weights or mappings are changed.

## 2. Weighting System

Weights live in Supabase:

- `metric_category`
- `metric_definition`
- `metric_weight`

The scoring code should join event rows to metric definitions and active metric
weights. Local mapping files are allowed for raw Wyscout label normalization, but
the long-term scoring truth should remain database-backed and auditable.

## 3. PEAK Rules

Confirmed by coaches:

- Individual Wyscout events are sufficient for PEAK scoring.
- No sequence bonus should be added.
- No coach/video confirmation gate is required for PEAK.
- Advance = `0.5` points per `10` successful Advance actions.
- Punish and Advance should not double-count the same action.
- Punish takes priority over Advance.
- The 3-5 pass threshold is the dividing line between Punish and Advance.

Still to implement/confirm:

- Wyscout label normalization table for Advance and Punish.
- Encoding the 3-5 pass threshold in scoring logic.
- Ensuring successful Advance actions are counted in groups of 10, not as
  `0.5` per single action.

The current PEAK normalization table lives at:

```text
pipeline/config/wyscout_peak_normalization.csv
```

See also:

```text
docs/analytics/peak_normalization.md
```

## 4. ASET Rules

ASET remains event-derived, but some Wyscout label mappings still need review.

Known review areas:

- Whether all defensive actions require positive/successful outcomes
- How to handle `outcome=Unknown`
- Which Wyscout labels count as true coach-defined counter press events
- Which clearances qualify as Clearance from Danger

## 5. Set Piece Rules

Set-piece scoring is event-derived, but final normalization still needs to be
checked against coach definitions.

Known review areas:

- Attacking set-piece goals and first-phase actions
- Defensive set-piece wins/actions
- Set-piece concessions and whether penalties are team-wide or player-specific
- Whether set-piece goal events also receive standard Goal/Assist credit

## 6. On-Field Logic

Open questions:

- How team-level events should be assigned to players
- Whether a minutes threshold should apply
- Whether match outputs should emphasize raw totals, per-90 values, or both

Until finalized, reconciliation outputs should show enough context for coach
review rather than hiding assumptions.

## 7. Regenerating Historical Scores

Standard flow:

1. Inventory sources.
2. Parse/load event evidence.
3. Confirm `athlete_event` rows exist for the match.
4. Run score reconciliation.
5. Review event trace and score explainer.
6. Only then regenerate official score outputs.

Useful commands:

```bash
.venv/bin/python pipeline/ingestion/inventory_sources.py --season 2025
.venv/bin/python pipeline/analytics/reconcile_coug_scores.py --season 2025
```

## 8. Change Log

- v0.2 — Added coach-confirmed source-of-truth and PEAK rules.
- v0.1 — Scaffold created.
