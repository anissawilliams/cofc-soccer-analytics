# COUG Reconciliation Workflow Before Databricks

Last updated: 2026-07-31

## Purpose

Reconciliation answers one question:

> Can we explain the coach-facing COUG value from player events, active metric
> definitions, and active metric weights before we publish it?

It is a publication-control process. It is not a second scoring system, and it
does not make a PDF or legacy CSV authoritative.

## The Short Version

```text
Raw source files
  -> source inventory and registration
  -> parsing and athlete attribution
  -> athlete_event evidence in Supabase
  -> metric_category + metric_definition + active metric_weight
  -> event-derived candidate totals
  -> comparison with PDFs and legacy CSVs
  -> discrepancy triage
  -> analyst signoff
  -> preflight gate
  -> coach-facing publication
```

The source of scoring truth is the event path in Supabase. PDFs and legacy CSVs
are evidence used to find omissions, mapping errors, and historical rule
differences.

## What Each Layer Is For

| Layer | What it answers | Authoritative for scoring? |
| --- | --- | --- |
| Raw XML/CSV/vendor file | What did the source system record? | Evidence only |
| `source_file` / `data_source` | Where did the event come from? | Provenance |
| `athlete_event` | Which player event is available to score? | Yes: event evidence |
| `metric_category` | Which COUG family receives the event? | Yes |
| `metric_definition` | Which coach-defined metric does it represent? | Yes |
| active `metric_weight` | What coefficient or scoring rule applies? | Yes |
| `coug_score` | What official total is stored for the portal/table? | Publication value |
| PDF / legacy COUG CSV | What did an older or external process report? | No; comparison only |
| reconciliation output | Why do the candidate and comparison values differ? | Diagnostic only |
| signoff + preflight | Is a known difference explainable enough to publish? | Publication gate |

## Important Distinction: Calculate, Reconcile, Publish

These are separate actions.

1. **Calculate:** join `athlete_event` to its metric category, definition, and
   active weight to produce an event-derived candidate value.
2. **Reconcile:** compare that candidate value with stored/legacy/PDF evidence
   and explain every material difference.
3. **Publish:** update or expose coach-facing values only after the gate has
   zero blocks.

Running `reconcile_coug_scores.py` writes reports. It does **not** update
`coug_score`, change weights, or publish a new score.

## Normal Match Workflow

### 1. Inventory the evidence

```bash
.venv/bin/python pipeline/ingestion/inventory_sources.py \
  --season 2025 \
  --slug 2025-11-02_uncw
```

Confirm that expected sources are registered or explicitly documented as
missing. A missing source is not the same thing as a zero event count.

### 2. Validate scoring configuration and critical PEAK behavior

```bash
.venv/bin/python pipeline/analytics/validate_scoring_config.py
.venv/bin/python pipeline/analytics/check_peak_scoring_fixture.py
```

Expected baseline:

```text
Scoring config validation: 0 error(s), 0 warning(s)
PEAK scoring fixture: all checks passed
Candidate PEAK total: 5.9
```

These checks happen before interpreting a discrepancy. Otherwise a malformed
normalization file or broken scoring behavior can masquerade as missing data.

### 3. Parse/load event evidence when needed

Dry-run first:

```bash
.venv/bin/python pipeline/ingestion/batch_parse.py \
  --season 2025 \
  --slug 2025-11-02_uncw \
  --dry-run
```

Only perform the real load after source identity, athlete attribution, and
duplicate behavior look correct. Loading evidence and publishing a score are
different operations.

### 4. Generate reconciliation reports

For one match:

```bash
.venv/bin/python pipeline/analytics/reconcile_coug_scores.py \
  --season 2025 \
  --slug 2025-11-02_uncw
```

For the full season:

```bash
.venv/bin/python pipeline/analytics/reconcile_coug_scores.py \
  --season 2025 \
  --all
```

Use `--dry-run` to fetch and calculate without replacing report files:

```bash
.venv/bin/python pipeline/analytics/reconcile_coug_scores.py \
  --season 2025 \
  --slug 2025-11-02_uncw \
  --dry-run
```

The current CLI requires either `--slug <match_slug>` or `--all`. A bare
`--season 2025` command is incomplete.

`--all` also expects the season's local/cache match directories to be
available so it can enumerate match slugs. On a fresh clone, hydrate or restore
the registered source evidence first.

### 5. Read the reports in this order

Reports are written under:

```text
pipeline/outputs/reports/score_reconciliation/<season>/
```

1. `*_pipeline_score_summary.csv`
   - One player total per match from event evidence.
   - Start here to see the candidate ASET/PEAK/set-piece totals.
2. `*_score_reconciliation.csv`
   - Candidate totals beside legacy/PDF comparison values.
   - Use this to find the material deltas.
3. `*_score_explainer.csv`
   - Grouped formulas such as event count × weight = contribution.
   - Use this to determine which metric family creates the delta.
4. `*_event_score_trace.csv`
   - One row per event with source label, mapped metric, value, weight,
     timestamp, and contribution.
   - Use this for the final evidence-level explanation.

The investigation should move from total -> metric family -> individual event,
not begin by changing a coefficient.

### 6. Build season triage

```bash
.venv/bin/python pipeline/analytics/build_reconciliation_triage.py \
  --season 2025
```

Triage groups differences into useful causes such as:

- source evidence missing;
- player appears only in legacy/PDF evidence;
- candidate is below or above the comparison value;
- legacy PEAK exists without normalized PEAK events;
- difference is within the accepted threshold.

Triage is a work queue, not a verdict that the candidate or legacy value is
automatically correct.

### 7. Diagnose before changing anything

Use this order:

1. Is the raw source file present and registered?
2. Did parsing create the expected player events?
3. Was the player identity/alias resolved correctly?
4. Did the raw label map to the intended COUG metric?
5. Did position, outcome, threshold, or duplicate rules filter it correctly?
6. Did the active database weight apply?
7. Is the PDF/legacy value based on an older or different rule?
8. Only then: is the official mapping or weight actually wrong?

Do not make the candidate match a PDF by adjusting a weight without answering
the earlier questions.

### 8. Record analyst signoff

Known discrepancies are recorded in:

```text
pipeline/config/reconciliation_signoffs.csv
```

| Disposition | Meaning | Gate effect |
| --- | --- | --- |
| `cleared` | Investigated and resolved | Pass |
| `source_missing` | Required evidence is not available yet | Warning |
| `known_gap` | Difference is understood and intentionally deferred | Warning |
| `under_review` | Investigation is incomplete | Block |
| No matching signoff | New/unreviewed discrepancy | Block |

A warning is not the same as “everything matches.” It means the difference is
documented and accepted for the stated purpose.

### 9. Run the publication gate

```bash
.venv/bin/python pipeline/analytics/preflight_check.py --season 2025
```

Interpretation:

- **0 blocks:** publication may proceed, with warnings disclosed where
  relevant.
- **1 or more blocks:** do not publish changed coach-facing scores.

Current documented 2025 baseline:

```text
PASSED WITH WARNINGS — 18 documented issues, 0 blocks
```

That baseline should not be treated as a universal expected result. New source
files, mappings, weights, or regenerated triage can legitimately change the
counts.

### 10. Publish deliberately

Before publishing, retain:

- the scoring config validation result;
- the PEAK fixture result;
- reconciliation reports;
- triage and signoffs;
- the zero-block preflight report;
- the code/config/weight version used.

The staff trace endpoint is explanation-only. It should mirror official
calculated values and evidence; it must not become another scoring engine.

## When a Score Change Is Allowed

A coach-facing score change is ready only when all are true:

- event evidence exists or the evidence limitation is explicit;
- metric mapping and active weight are identified;
- no prohibited PEAK double-counting is present;
- the candidate/legacy difference is explained;
- any reviewable ASET proxy remains labeled as such;
- preflight has zero blocks;
- the intended publication action is separate from report generation.

## Current Incomplete Work Before Databricks

### Operational priorities

1. Deploy the current backend. The observed backend was still on commit
   `255d572`, while newer trace and normalized-metadata code is merged on
   `main`.
2. Apply and validate `schema/2026_07_metric_scoring_rule.sql` in Supabase.
   The migration is additive and has not yet been run.
3. Profile the player trace endpoint. It works but is slow; measure cold-start
   time and query timings before adding indexes or caching.
4. Verify current indexes for event trace, weights, stored scores, stints, and
   match lookup.

### Evidence and reconciliation priorities

1. Register missing W&M supplemental player/team XML when it becomes
   available, then rerun reconciliation and triage.
2. Confirm every future match has durable `athlete_event` and exact
   `source_file_id` provenance where known.
3. Re-run 2025 reconciliation after normalized metadata is applied and confirm
   the 18-warning/0-block baseline remains explainable.
4. Keep ASET mappings such as tackles, pressing duels, and clearances labeled
   as reviewable proxies until coach definitions are finalized.
5. Resolve the remaining set-piece normalization questions, including normal
   Goal/Assist credit versus set-piece bonus credit.
6. Verify the running PEAK implementation—not only the config—enforces Punish
   priority, no double-counting, and Advance at `0.5` per 10 successful
   actions.

### Other project lanes

1. Finish 2026 source intake, opponent shells, and match-by-match operating
   cadence.
2. Add Catapult first as a supporting evidence/readiness lane; do not let it
   silently rewrite ASET/PEAK.
3. Recruiting similarity remains blocked until internal and recruit profile
   inputs exist.
4. Keep predictive modeling separate from rule-based COUG scoring.

## What Databricks Would Change Later

Databricks can replace or augment the transformation/orchestration layer, but
it should not change the governance logic above.

- Bronze: immutable raw files and source metadata.
- Silver: normalized players, matches, events, metric rules, and weights.
- Gold: official COUG rollups, reconciliation outputs, and coach-facing
  explanations.

The pre-Databricks workflow is therefore the contract Databricks must preserve:
same evidence, same active rules, explainable differences, and a zero-block
publication gate.

## Related References

- `docs/analytics/sop/scoring_and_weights_sop.md`
- `docs/analytics/sop/score_reconciliation_sop.md`
- `docs/analytics/pipeline_at_a_glance.md`
- `docs/analytics/normalized_scoring_metadata.md`
- `pipeline/config/reconciliation_signoffs.csv`
