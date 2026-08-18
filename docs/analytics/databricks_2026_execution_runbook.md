# Databricks 2026 Execution Runbook

Purpose: provide the operational checklist for loading the 2026 roster and
running a traceable CofC match pipeline in Databricks without changing the
COUG scoring contract.

This runbook uses 2025 as the parity baseline. Start with one representative
2026 match, prove the player/event trace, then expand to the full season.

## 1. Roster Is A Required Parser Input

The Wyscout Sportscode export contains both teams. The parser must retain an
event only when **both** its jersey number and normalized player name appear
on the CofC roster. Do not filter on jersey number alone; opponents can wear
the same number.

Create this file before parsing any 2026 data:

```text
pipeline/ingestion/roster_2026.csv
```

Required CSV shape:

```csv
number,name
7,First Last
14,First Last
```

Rules:

- Use the name form emitted in Wyscout's `(<jersey>) <name>` event code.
- One row represents one valid `(number, name)` pair.
- Keep multiple rows for a legitimate midseason name or jersey change.
- Do not use display-name abbreviations unless Wyscout emits them that way.
- Review unmatched Wyscout names before adding aliases; do not loosen the
  roster filter to admit unknown names.

The existing parser behavior to preserve is in
`pipeline/ingestion/parse_wyscout.py`:

```text
Wyscout XML event
  -> parse jersey and name
  -> require roster jersey + normalized name match
  -> write CofC-only _players.csv
  -> build athlete_event evidence rows
```

Before the first match, sync the roster into `public.athlete`. This keeps new
players and position changes reviewable before event ingestion. The athlete
table stores player identity and position; the roster CSV remains the source
for jersey-number parsing.

```bash
# Preview exact identity matches, new-player inserts, and position updates.
.venv/bin/python pipeline/ingestion/sync_roster.py \
  --season 2026 \
  --roster pipeline/ingestion/roster_2026.csv

# Apply only after reviewing pipeline/outputs/reports/roster_sync/2026/.
.venv/bin/python pipeline/ingestion/sync_roster.py \
  --season 2026 \
  --roster pipeline/ingestion/roster_2026.csv \
  --apply
```

The roster sync does not fuzzy-merge players. Any name that does not exactly
match an existing athlete is shown as a proposed new record, preventing a new
player from being attached to a returning player's history.

## 2. Land Each Source With Stable Metadata

For every file uploaded to the Databricks volume or external location, record:

| Field | Required use |
| --- | --- |
| `source_file_id` | Stable source identity used downstream |
| `content_hash` | Skip identical reruns; detect changed exports |
| `season` and `slug` | Match/session identity |
| `source_system` | `wyscout`, `spiideo`, `catapult`, or `legacy_csv` |
| `source_path` and `file_name` | Provenance back to the raw file |
| `ingested_at` | Run lineage |

Suggested 2026 raw layout:

```text
/Volumes/cofc_soccer_dev/bronze/raw_files/2026/
  roster/roster_2026.csv
  matches/<slug>/<slug>_cfc_sportscode.xml
  matches/<slug>/<slug>_player_events.xml
  matches/<slug>/<slug>_team_events.xml
  catapult/<session-date>_<export-name>.csv
```

Use the Sportscode XML as the initial event source. Supplemental player/team
XML is valuable evidence, but absence of those files must be recorded as a
coverage gap rather than silently replaced with PDF totals.

## 3. Databricks Job Parameters

Define these job parameters once and pass them to every task:

```text
catalog                 = cofc_soccer_dev
season                  = 2026
slug                    = 2026-MM-DD_opponent
raw_root                = /Volumes/cofc_soccer_dev/bronze/raw_files
roster_path             = /Volumes/cofc_soccer_dev/bronze/raw_files/2026/roster/roster_2026.csv
weight_version          = trial_1
publish                 = false
```

Keep `publish=false` through parity testing. Only the preflight task may
permit publication after all blocking checks pass.

## 4. Ordered Pipeline Tasks

Create one Databricks Job with these notebook or Python-wheel tasks:

```text
01_register_raw_files
02_parse_wyscout_sportscode
03_normalize_roster_and_athletes
04_build_sessions_and_matches
05_build_athlete_event
06_build_athlete_load                 # no-op when no Catapult file exists
07_validate_event_evidence
08_score_coug_table
09_build_player_coug_trace
10_reconcile_against_baseline
11_run_preflight
12_publish_gold_outputs               # conditional on preflight success
```

Task contracts:

| Task | Output | Guardrail |
| --- | --- | --- |
| `02_parse_wyscout_sportscode` | CofC-only normalized event rows | Log opponent-filtered and roster-unmatched counts |
| `05_build_athlete_event` | `silver.athlete_event` | Preserve raw labels, outcome, timestamp, source ID, and raw context |
| `06_build_athlete_load` | `silver.athlete_load` | Keep Catapult separate from ASET/PEAK totals |
| `07_validate_event_evidence` | validation report | Fail on missing athlete IDs, metric IDs, or duplicate natural keys |
| `08_score_coug_table` | `gold.coug_score` | Join events to versioned metric weights; do not hard-code weights |
| `09_build_player_coug_trace` | `gold.player_coug_trace` | One explainable row per counted event contribution |
| `11_run_preflight` | `gold.preflight_report` | Block publication on unresolved reconciliation issues |

## 5. Local Reference Commands

Run these locally against a single 2026 match before porting the same logic.
They are the behavioral reference, not the production Databricks execution
surface.

```bash
# Inspect source coverage first.
.venv/bin/python pipeline/ingestion/inventory_sources.py --season 2026 --slug <slug>

# Produce a CofC-only players file using the new roster.
.venv/bin/python pipeline/ingestion/batch_parse.py \
  --season 2026 \
  --slug <slug> \
  --roster pipeline/ingestion/roster_2026.csv

# Inspect before writing. Confirm inserted/skipped counts make sense.
.venv/bin/python pipeline/ingestion/load_match.py \
  --season 2026 \
  --slug <slug> \
  --dry-run

# Load traceable event evidence only after the dry run is clean.
.venv/bin/python pipeline/ingestion/load_match.py --season 2026 --slug <slug>

# Build the reviewed event-derived score summary. This does not write to the
# live COUG Table until --apply is supplied after review/preflight.
.venv/bin/python pipeline/analytics/publish_event_derived_coug_scores.py \
  --season 2026 --slug <slug>
```

For 2025 parity checks:

```bash
.venv/bin/python pipeline/analytics/validate_scoring_config.py
.venv/bin/python pipeline/analytics/check_peak_scoring_fixture.py
.venv/bin/python pipeline/analytics/reconcile_coug_scores.py --season 2025 --slug 2025-11-02_uncw
.venv/bin/python pipeline/analytics/preflight_check.py --season 2025
```

For a 2026 first-match release, run the publisher without `--apply`, review
the generated CSV and player trace, then rerun the exact command with `--apply`.
The publisher uses the same event-trace and normalized PEAK logic as
reconciliation; it does not read legacy/PDF totals as score inputs.

## 6. Critical SQL/Dataframe Checks

These checks should be implemented in the validation and reconciliation tasks.

```sql
-- No event may refer to an unknown athlete, session, or metric.
SELECT COUNT(*) AS invalid_event_rows
FROM cofc_soccer_dev.silver.athlete_event e
LEFT JOIN cofc_soccer_dev.silver.athlete a ON e.athlete_id = a.athlete_id
LEFT JOIN cofc_soccer_dev.silver.session s ON e.session_id = s.session_id
LEFT JOIN cofc_soccer_dev.silver.metric_definition m ON e.metric_id = m.metric_id
WHERE a.athlete_id IS NULL OR s.session_id IS NULL OR m.metric_id IS NULL;

-- The source-aware event natural key must be unique.
SELECT athlete_id, session_id, metric_id, source_file_id, collection_method,
       event_time, raw_value_context, COUNT(*) AS duplicate_count
FROM cofc_soccer_dev.silver.athlete_event
GROUP BY athlete_id, session_id, metric_id, source_file_id, collection_method,
         event_time, raw_value_context
HAVING COUNT(*) > 1;

-- See exactly what will be shown in a player trace before publishing.
SELECT athlete_id, session_id, raw_metric_name, scoring_metric_name,
       raw_value, metric_weight, event_score, source_file_id, event_time,
       review_status
FROM cofc_soccer_dev.gold.player_coug_trace
WHERE season = '2026' AND athlete_id = :athlete_id
ORDER BY session_date, event_time;
```

Adapt column names only when necessary; retain this evidence shape even if the
physical schema changes.

## 7. Score Rules That Must Not Drift

These are implementation requirements, not presentation copy:

- Event-derived `athlete_event` rows are the scoring truth.
- Legacy CSVs and PDFs are validation/comparison sources only.
- Goal scorer = `3.0`; Assist = `2.0`; Punish = `0.2`.
- Advance = `0.5` per 10 successful actions.
- Punish has priority over Advance; one action cannot receive both credits.
- Do not score every attacking Wyscout label without the PEAK normalization
  and priority rules.
- Keep ASET proxy mappings and `needs_coach_review` status visible.
- Catapult provides load context first. It must not silently change ASET or
  PEAK totals.

## 8. Pilot Exit Checklist

Do not expand from one match to the full 2026 season until all are true:

- [ ] New roster filters out opponents and retains every expected CofC player.
- [ ] Parsed event count and unique player count are plausible.
- [ ] Each `athlete_event` has athlete, session, metric, source, and context.
- [ ] Re-running the same inputs does not create duplicate events.
- [ ] A selected player has an event ledger with source, weight, and score.
- [ ] Catapult rows link to the correct athlete/session but do not change COUG totals.
- [ ] PEAK fixture and 2025 reconciliation checks still pass.
- [ ] Preflight has zero blocks before publishing coach-facing values.

## 9. First-Day Order Of Operations

1. Add the 2026 roster CSV and manually verify the Wyscout spellings.
2. Upload roster plus one complete match folder to the bronze location.
3. Run tasks 01 through 07 only and inspect the event evidence.
4. Run scoring and player trace generation with `publish=false`.
5. Compare against the 2025 reference workflow and document every difference.
6. Add Catapult as a separate load lane.
7. Enable gold-output publication only after preflight passes.
