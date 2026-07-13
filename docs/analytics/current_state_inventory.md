# Current State Inventory

Last updated: 2026-07-13

This document explains what the repo currently has, what each layer can power,
and what is still missing for fully automated COUG Table, scouting, and modeling
workflows.

## Big Picture

The project now has three separate lanes:

1. COUG Table scoring and reconciliation
2. Scouting, match outcome modeling, and simulation
3. Schedule and season operations

These should stay related but separate. COUG Table scoring is a coach-defined
rules framework. Scouting/modeling is where machine learning and probability
belong.

## 2025 Data We Have

### Match Manifest

Path: `pipeline/data/manifests/matches_manifest.csv`

This lists 16 2025 matches with slug, opponent, competition, venue, score, and
result. It is useful as a season index and ingestion checklist.

### Wyscout XML Match Folders

Path: `pipeline/data/matches/2025/`

Current state:

- Most 2025 match folders have `sportscode.xml`
- Most 2025 match folders have `effective_time.xml`
- Only UNCW currently has local `player_events.xml`
- Only UNCW currently has local `team_events.xml`

What this powers:

- Current source inventory checks
- Sportscode/effective-time parsing
- Partial event parsing where raw XML exists

What is missing:

- Full `player_events.xml` and `team_events.xml` for the rest of 2025
- Spiideo source files for 2025, if coaches want video-tag validation. This is
  a future source and is not treated as a current Wyscout-ingestion blocker.
- Catapult/load source files, if physical load becomes part of automated score

### Wyscout Player PDF Reports

Path: `pipeline/data/raw/player_reports/`

These exist for most 2025 matches and include player-level report values.

What this powers:

- Legacy COUG Table comparison
- Score reconciliation against PDF-derived reports
- A fallback/reference source when event XML is incomplete

Important note:

- PDFs are not the ideal long-term source of truth for PEAK/ASET scoring.
- They are useful for reconciliation and coach-facing sanity checks.

### Parsed Player Event CSVs

Path: `pipeline/outputs/2025/<match_slug>/<match_slug>_players.csv`

These are parsed outputs from earlier Wyscout processing. They include player,
time range, labels, outcome, and raw code.

What this powers:

- Evidence that PEAK-ish labels exist in parsed data
- Review of actions like `Smart passes`, `Key passes`, `Opportunity`, `Shots`,
  `Goal`, and `Assists`

Important caveat:

- Many rows have `outcome=Unknown`, which is why earlier ingestion skipped or
  under-counted some events. This is one reason PEAK reconciliation matters.

### Legacy COUG Score CSVs

Path: `pipeline/data/outputs/2025/<match_slug>/<match_slug>_coug_scores.csv`

These are earlier COUG score outputs. They are useful for comparison but should
not be treated as final truth because some weights were experimental/made up.

What this powers:

- Reconciliation against current database-derived event scoring
- Identifying where old PEAK/ASET values came from

### Season COUG Outputs

Path: `pipeline/outputs/2025/coug_table/`

These include match-level and season-level COUG Table files and figures.

What this powers:

- Coach-facing historical report artifacts
- Season trend summaries
- Player trend exploration

Important caveat:

- These should be regenerated after the scoring path and event ingestion are
  fully stabilized.

## Supabase/Data Model State

The database has the core tables needed for the intended system:

- `team`
- `athlete`
- `session`
- `match`
- `athlete_session_stint`
- `metric_category`
- `metric_definition`
- `metric_weight`
- `data_source`
- `possession_sequence`
- `athlete_event`
- `athlete_load`
- `coug_score`
- `spiideo_tag_map`
- `athlete_alias` was added by the project team for nickname/name matching

What this powers:

- Persistent player, match, event, metric, source, and score storage
- Idempotent ingestion and upserts
- Explaining where scores came from at event/source level

Key current issue:

- The `athlete_event` path now exists, but we still need to make sure every
  required 2025 and future match event source is parsed and loaded reliably.

## COUG Reconciliation We Have

Path: `pipeline/analytics/reconcile_coug_scores.py`

Outputs:

- `pipeline/outputs/reports/score_reconciliation/2025/*`

What this powers:

- Pipeline score summary from Supabase events
- Event score trace
- Legacy score comparison
- PDF score comparison
- Candidate PEAK review fields
- Alias-aware player matching

Current interpretation:

- ASET/PEAK differences are mostly source/weighting/mapping questions, not just
  code bugs.
- The current reconciliation tool is the right place to show where values are
  being created.

## Scouting and Modeling We Have

### 2025 Match Outcome Model

Command:

```bash
.venv/bin/python pipeline/scouting/build_match_model.py --org cofc --season 2025
```

Outputs:

- `pipeline/outputs/reports/scouting/2025/models/match_model_predictions.csv`
- `pipeline/outputs/reports/scouting/2025/models/match_model_feature_importance.csv`
- `pipeline/outputs/reports/scouting/2025/models/match_model_metrics.json`
- `pipeline/outputs/reports/scouting/2025/models/match_simulation_backtest.csv`
- `pipeline/outputs/reports/scouting/2025/models/match_model_summary.md`

Current metrics:

- 16 matches
- Leave-one-out accuracy: 0.625
- Log loss: 1.295

What this powers:

- Objective 2 machine learning workflow
- Feature importance discussion
- Backtested match prediction baseline
- Simulation and probability outputs

Important caveat:

- 16 matches is a small sample. This is a valid professional workflow, but it
  should be presented as an early model until 2024 and/or more seasons are added.

### Existing Prototype Analytics

Path: `pipeline/analytics/`

Useful files:

- `ingest.py`
- `model.py`
- `simulate.py`
- `simulate_bootstrap.py`
- `match_intelligence.py`

Current interpretation:

- These are useful prototypes.
- The new `pipeline/scouting/` package is the cleaner, more portable lane to
  grow going forward.

## 2026 Schedule We Have

Path: `pipeline/data/schedules/2026_schedule.csv`

Config:

- `configs/seasons/cofc_2026.json`

Command:

```bash
.venv/bin/python pipeline/scouting/build_schedule_report.py --org cofc --season 2026
```

Outputs:

- `pipeline/outputs/reports/scouting/2026/schedule/schedule_clean.csv`
- `pipeline/outputs/reports/scouting/2026/schedule/schedule_qa_report.md`
- `pipeline/outputs/reports/scouting/2026/schedule/schedule_summary.json`

Current state:

- 19 scheduled matches
- Date range: 2026-08-07 to 2026-10-30
- 9 home, 10 away, 0 neutral
- 8 conference matches
- 3 exhibitions
- 14 rows have Supabase opponent team IDs
- 5 rows still need Supabase opponent team IDs

Missing opponent IDs:

- Wofford
- USC Lancaster
- Jacksonville
- Florida Gulf Coast
- Mercer

What this powers now:

- Schedule QA
- Season planning
- Pre-match report shells
- Opponent/team joins once IDs are complete

What it cannot power by itself:

- True 2026 prediction from 2026 performance data
- Opponent-specific tactical scouting without opponent history or Wyscout data
- 2026 COUG Table output before matches are played and ingested

## How 2026 Data Will Accumulate

Before matches are played:

- Schedule exists
- Opponent IDs can be joined
- Reports can be shells/planning docs
- Model can use 2025 or 2024+2025 history only

After each 2026 match:

1. Add raw Wyscout/Spiideo/Catapult files to the expected source folder.
2. Run source inventory.
3. Parse source files.
4. Load/upsert session, match, athlete stints, events, and sources.
5. Reconcile COUG scores.
6. Append match stats/features for modeling.
7. Regenerate scouting/model outputs.
8. Publish coach-facing report/dashboard.

## Most Important Next Data To Gather

Highest priority:

1. Full 2025 `player_events.xml` and `team_events.xml` files
2. 2024 match stats/results, ideally in the same shape as `cofc_matches_2025.xlsx`
3. Missing 2026 Supabase opponent team IDs
4. 2026 match files as the season progresses

Nice to have:

1. Spiideo tags for validation
2. Catapult exports for load scoring
3. Historical opponent Wyscout team/event data for scouting reports
4. Recruiting/prospect Wyscout exports for similarity modeling

## Practical Answer

Do we have enough data to run 2026 scouting?

Yes for schedule QA and pre-match report structure.

Not yet for true 2026 scouting intelligence. For that, we need either historical
opponent data or new 2026 match data as it arrives.

Do we have enough for Objective 2 machine learning?

Yes for a first supervised learning workflow using 2025 match stats. It becomes
much stronger once 2024 is added.

Do we have enough for reliable COUG Table automation?

Partially. The database design and reconciliation path are in place, but the
full event source path needs the remaining XML files and stricter ingestion QA.
