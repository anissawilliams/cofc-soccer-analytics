# Normalized Scoring Metadata

## Why this exists

`metric_definition.notes` currently mixes source labels, outcome filters,
position eligibility, thresholds, review status, metric relationships, raw-value
behavior, weights, and prose. Those concepts need independent fields so that
ingestion, reconciliation, Databricks transformations, and coach-facing
explanations use the same vocabulary.

The migration in `schema/2026_07_metric_scoring_rule.sql` creates
`metric_scoring_rule`. It does not alter any score, weight, event, or legacy
note.

## Ownership

- `metric_definition` identifies the canonical metric and category.
- `metric_weight` remains the sole authoritative weight source.
- `metric_scoring_rule` defines source-event normalization and eligibility.
- `athlete_event` remains the event evidence.
- `metric_definition.notes` remains legacy migration evidence until a later
  audited cleanup.

## Normalized fields

| Field | Meaning |
| --- | --- |
| `source_platform` | Source system, initially `wyscout` |
| `source_event_label` | Exact incoming event label |
| `outcome_rule` | `always_count`, `plus_only`, or `non_minus` |
| `eligible_positions` | Allowed position codes; empty means all |
| `excluded_positions` | Explicitly excluded position codes |
| `minimum_event_count` | Match-level qualification threshold |
| `aggregation_rule` | `per_event` or `threshold_qualifier` |
| `raw_value_per_event` | Evidence value written to `athlete_event` |
| `review_status` | Confirmation/review state |
| `relationship_type` | Alias or duplicate relationship |
| `related_metric_id` | Canonical/related metric |
| `coach_explanation` | Plain-language portal explanation |
| `technical_notes` | Technical nuance not needed in the main UI |
| `legacy_note` | Verbatim pre-migration note |

## Migration sequence

1. Run the scoring config validator and PEAK fixture.
2. Run season reconciliation in dry-run mode and confirm preflight has zero
   blocks.
3. Validate the migration seed locally and against Supabase:

   ```bash
   .venv/bin/python pipeline/analytics/validate_scoring_metadata_migration.py
   .venv/bin/python pipeline/analytics/validate_scoring_metadata_migration.py --check-live
   ```

   Before the migration, `--check-live` is expected to fail because the live
   `metric_scoring_rule` table is absent. Run it again after applying the SQL;
   success then confirms all 21 active rules are present.

4. Review and run `schema/2026_07_metric_scoring_rule.sql` in Supabase.
5. Confirm the SQL verification queries return 21 rules and 0 missing labels.
6. Deploy the backend. It reads normalized metadata when present and falls back
   safely while schema caches refresh.
7. Run ingestion in `--dry-run` mode and compare filter counts to the previous
   loader.
8. Run reconciliation and preflight again before publishing coach-facing score
   changes.

Do not delete or rewrite `metric_definition.notes` during this migration.

## Databricks mapping

- Bronze retains the original source label, original notes, and source-file
  provenance.
- Silver joins `athlete_event`, `metric_definition`,
  `metric_scoring_rule`, and the active `metric_weight`.
- Gold exposes coach-facing event explanations and official COUG rollups.

Databricks must not infer weights or eligibility by parsing `legacy_note`.
