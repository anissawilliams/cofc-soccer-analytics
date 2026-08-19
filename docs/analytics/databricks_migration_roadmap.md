# Databricks Migration Roadmap

Last updated: 2026-07-27

Purpose: migrate the CofC Soccer Analytics pipeline toward a cleaner,
maintainable lakehouse-style architecture while preserving the score logic and
traceability that make COUG Table values defensible.

For the operational 2026 roster and match execution sequence, see
[`databricks_2026_execution_runbook.md`](databricks_2026_execution_runbook.md).

## Recommendation

Moving toward Databricks is the right direction if the goal is maintainability,
lineage, and clearer handoff. The win is not "big data." The win is organizing
raw sources, event evidence, score outputs, and reconciliation in durable tables
with a visible path from file to player score.

Because the current plan uses the free/community Databricks tier, the first
migration should stay modest:

```text
Raw files
  -> normalized event/load tables
  -> explainable score outputs
  -> reconciliation/preflight report
```

Do not replace the staff portal backend on day one. Keep FastAPI/Supabase
working while Databricks proves that it can reproduce the current score outputs.

## Target Architecture

Use a bronze/silver/gold data design.

Databricks describes the medallion architecture as a pattern that progressively
improves data quality from bronze raw data, to silver validated data, to gold
business-ready outputs:

https://docs.databricks.com/aws/en/lakehouse/medallion

Recommended structure:

```text
cofc_soccer_dev.bronze.raw_wyscout_files
cofc_soccer_dev.bronze.raw_wyscout_events
cofc_soccer_dev.bronze.raw_spiideo_tags
cofc_soccer_dev.bronze.raw_catapult_load
cofc_soccer_dev.bronze.raw_legacy_coug_scores

cofc_soccer_dev.silver.athlete
cofc_soccer_dev.silver.session
cofc_soccer_dev.silver.match
cofc_soccer_dev.silver.athlete_session_stint
cofc_soccer_dev.silver.metric_category
cofc_soccer_dev.silver.metric_definition
cofc_soccer_dev.silver.metric_weight
cofc_soccer_dev.silver.athlete_event
cofc_soccer_dev.silver.athlete_load

cofc_soccer_dev.gold.coug_score
cofc_soccer_dev.gold.player_coug_trace
cofc_soccer_dev.gold.score_explainer
cofc_soccer_dev.gold.score_reconciliation
cofc_soccer_dev.gold.reconciliation_triage
cofc_soccer_dev.gold.preflight_report
cofc_soccer_dev.gold.staff_portal_player_summary
```

If Unity Catalog is available, use it for governed tables, permissions, and
lineage. Databricks positions Unity Catalog as the governance layer for data and
AI assets:

https://docs.databricks.com/aws/en/data-governance/

Avoid building new workflows around DBFS root or DBFS mounts. Databricks
recommends Unity Catalog volumes, external locations, or workspace files instead:

https://docs.databricks.com/aws/en/dbfs/unity-catalog

## Migration Strategy

### Phase 0 — Freeze Current Truth

Goal: make the current system reproducible before moving it.

Tasks:

- Commit the staff portal traceability work.
- Commit `pipeline/analytics/preflight_check.py`.
- Run current validation commands.
- Save current score reconciliation outputs.
- Identify which 2025 scores are legacy/PDF-derived vs event-derived.
- Document known warnings in `reconciliation_signoffs.csv`.

Exit criteria:

- Current local pipeline can produce reconciliation artifacts.
- Staff portal can show official totals and player trace rows.
- Preflight has zero blocking issues for any output that will be shown.

### Phase 1 — Land Raw Files In Databricks

Goal: preserve raw evidence first.

Bronze targets:

- Wyscout player/team/event XML or CSV exports
- Spiideo XML tag exports
- Catapult CSV/XLSX exports
- roster files
- schedule files
- legacy COUG CSV/PDF-derived score files

Minimum raw metadata:

| Field | Purpose |
| --- | --- |
| `source_file_id` | Stable file identifier |
| `source_system` | `wyscout`, `spiideo`, `catapult`, `legacy_csv`, `manual` |
| `season` | Season |
| `slug` | Match/session slug |
| `file_name` | Original file name |
| `file_path` | Databricks volume/external path |
| `ingested_at` | Load timestamp |
| `content_hash` | Duplicate/idempotency check |

Databricks Auto Loader can incrementally process new files in cloud storage and
supports CSV, JSON, and XML schema inference/evolution. XML support requires
Databricks Runtime 14.3 LTS or above:

https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/schema

Free-tier note: if Auto Loader or Unity Catalog volumes are not available in the
current workspace, use manual upload and batch notebook ingestion first. Keep
the table design the same.

### Phase 2 — Rebuild Silver Tables

Goal: reproduce the current normalized schema.

Port or recreate these tables:

- `athlete`
- `session`
- `match`
- `athlete_session_stint`
- `metric_category`
- `metric_definition`
- `metric_weight`
- `data_source` or `source_file`
- `athlete_event`
- `athlete_load`

Critical logic to preserve:

- player name normalization
- roster/source ID matching
- match slug parsing
- source priority
- event de-duplication
- metric alias mapping
- Wyscout label normalization
- Spiideo tag parsing
- raw context preservation
- coach-confirmed/manual-review flags

Do not flatten away `raw_value_context`. It is where the system explains edge
cases: Wyscout label, outcome, all labels, location, subtype, source code, and
review notes.

### Phase 3 — Port COUG Scoring

Goal: produce Databricks-native event-derived COUG totals.

Gold outputs:

- `player_coug_trace`
- `score_explainer`
- `coug_score`
- `score_reconciliation`
- `reconciliation_triage`

Scoring join:

```text
athlete_event
  -> metric_definition
  -> metric_category
  -> active metric_weight
  -> raw_value * weight
```

Important PEAK logic:

- Goal scorer = `3.0`.
- Assist = `2.0`.
- Punish = `0.2`.
- Advance = `0.5` per `10` successful Advance actions.
- Punish takes priority over Advance.
- Punish and Advance do not double-count.
- Free kick shot remains excluded unless coach approves a metric.

Important ASET logic:

- possession regains and interceptions need outcome/location review
- pressing duel is a proxy, not identical to coach-defined counter press
- clearance is broader than Clearance from Danger
- some ASET rows should remain `needs_coach_review`

Databricks SQL window functions can support rolling totals, grouped thresholds,
and recent-form calculations:

https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-window-functions

### Phase 4 — Add Catapult Cleanly

Goal: incorporate load data without corrupting ASET/PEAK meaning.

Bronze:

```text
raw_catapult_load
```

Silver:

```text
athlete_load
```

Gold:

```text
load_features
player_availability_context
counter_press_validation_features
```

Recommended Catapult fields:

- `distance`
- `player_load`
- `high_metabolic_load_distance`
- `accel_decel_efforts`
- `player_load_per_minute`
- `accel_decel_per_minute`
- `hi_distance_pct`
- `max_velocity`
- `sprint_distance`
- `sprint_efforts`
- `max_acceleration`
- `max_deceleration`

Derived fields:

- within-session z-score
- rolling athlete z-score
- acute load, such as 7-day
- chronic load, such as 28-day
- acute-to-chronic ratio
- matchday-minus-one freshness
- high-speed/sprint exposure trend

Initial uses:

- display load context in staff portal
- validate whether counter press tags involve sprint/acceleration evidence
- goalkeeper load scoring after thresholds are approved
- feed scouting model fatigue/readiness features

Important rule: Catapult should start beside COUG scoring, not inside ASET
totals. Only add `load_score` after thresholds and score effects are confirmed.

### Phase 5 — Reconcile Databricks Against Current Outputs

Goal: prove parity before switching systems.

Checks:

- player count by season
- match count by season
- minutes by player/match
- event counts by raw label
- metric counts by bucket
- PEAK totals by player/match
- ASET totals by player/match
- set-piece totals by player/match
- official `coug_score` vs Databricks-derived score
- preflight blocks/warnings

Expected output:

```text
Databricks score_reconciliation
Databricks score_explainer
Databricks preflight_report
```

Switch readiness:

- zero unresolved preflight blocks
- known warnings signed off
- top player totals match or are explained
- no unexplained duplicate event inflation
- Staff Portal trace can be produced from Databricks gold tables

### Phase 6 — Decide How The Staff Portal Reads Data

Options:

| Option | Description | Best When |
| --- | --- | --- |
| Sync Databricks gold tables back to Supabase | FastAPI continues reading Supabase | simplest production path |
| Export gold CSV/Parquet to app-readable storage | FastAPI reads static outputs | lightweight/free-tier friendly |
| Query Databricks directly from backend | FastAPI calls Databricks SQL/API | mature Databricks workspace available |

Recommended first production path:

```text
Databricks gold outputs
  -> synced/exported to Supabase
  -> existing FastAPI endpoints
  -> Staff Portal
```

This keeps the UI stable while the pipeline improves.

## Orchestration

When available, use Databricks jobs for repeatable match workflows. Databricks
Lakeflow Jobs support scheduled, file-arrival, table-update, model-update, and
continuous triggers:

https://docs.databricks.com/aws/en/jobs/triggers

Suggested job:

```text
Match Ingestion Job
  1. ingest_raw_sources
  2. normalize_wyscout
  3. normalize_spiideo
  4. normalize_catapult
  5. build_athlete_event
  6. build_athlete_load
  7. score_coug_table
  8. reconcile_scores
  9. run_preflight
  10. publish_gold_outputs if preflight passes
```

## Free-Tier Practical Path

If the free Databricks environment limits jobs, Auto Loader, Unity Catalog, or
external integrations, use this staged approach:

1. Upload one match worth of Wyscout, Spiideo, Catapult, roster, and score files.
2. Build bronze Delta/parquet tables manually in notebooks.
3. Port parser logic for that one match.
4. Build silver `athlete_event` and `athlete_load`.
5. Build gold `player_coug_trace`.
6. Compare against existing Supabase/staff portal outputs.
7. Repeat for three representative matches.
8. Only then generalize.

This still proves the architecture without overbuilding.

## Critical Logic Checklist

Do not migrate without these:

- [ ] source file IDs and file hashes
- [ ] source system and source priority
- [ ] player identity matching
- [ ] session/match identity matching
- [ ] Wyscout raw labels preserved
- [ ] Spiideo raw tag codes preserved
- [ ] Catapult raw columns preserved
- [ ] `raw_value_context` equivalent
- [ ] `metric_definition` table
- [ ] `metric_weight` table with versions
- [ ] PEAK priority rules
- [ ] Advance threshold rule
- [ ] ASET review flags
- [ ] duplicate/idempotency logic
- [ ] score explainer output
- [ ] reconciliation triage output
- [ ] analyst signoff table
- [ ] preflight publication gate
- [ ] Staff Portal trace output

## Definition Of Done

The migration is successful when a coach can open a player and see:

```text
Official score
Event-derived score
Every counted event
Raw source
Weight
Score contribution
Review status
Known gaps
```

The final score matters. The defensible trail matters more.
