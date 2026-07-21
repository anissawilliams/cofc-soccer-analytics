# Predictive Modeling Source Plan

This document describes the source data needed to mature the scouting/predictive modeling lane from a CofC-only prototype into a real opponent-aware forecasting system.

The database is already close to supporting this. The main missing pieces are:

- a clear source-file inventory for opponent match histories
- parser support for opponent team/event files
- reconciliation checks that prove match, team, and source-file identity before model features are trusted

## Modeling Questions To Support

The predictive pipeline should eventually answer:

- What is the expected win/draw/loss probability for a future CofC match?
- Which matchup factors are driving the probability?
- What is the most likely scoreline range?
- How does the opponent perform recently?
- How does the opponent perform against teams or formations similar to CofC?
- Are fatigue, travel, weather, or congestion likely to matter?
- How confident should coaches be in the model output?

## Required Source Families

### 1. CofC Historical Match Stats

Purpose:

- Train and validate CofC-side match outcome features.
- Build rolling CofC form, shot, xG, possession, and defensive trends.

Current source:

- `pipeline/data/raw/cofc_matches_2025.xlsx`

Current status:

- Available for 2025.
- Used by `pipeline/scouting/build_match_model.py`.
- Produces 16 historical match rows in the current model run.

Needed next:

- 2024 CofC match stats if Wyscout access returns.
- 2026 match stats as matches are played.

Database mapping:

- `session`
- `match`
- `team`
- future aggregate table or output feature matrix

### 2. Opponent Historical Match Stats

Purpose:

- Build opponent rolling momentum features.
- Compare CofC current form against opponent current form.
- Reduce the current sparsity in opponent rolling features.

Needed files:

- Wyscout match/team reports for each 2026 opponent.
- Ideally one row per opponent match from the current or prior season.
- Minimum useful window: last 5-10 opponent matches.

Preferred structure:

```text
source-files/
  cofc/
    2026/
      opponents/
        william_mary/
          wyscout/
            2026_william_mary_match_stats.xlsx
            2026_william_mary_match_report_<date>.pdf
        uncw/
          wyscout/
            2026_uncw_match_stats.xlsx
```

Database mapping:

- `team` stores opponent identity.
- `source_file` stores every uploaded opponent report/workbook.
- A future `team_match_feature` or `opponent_match_summary` table could persist parsed opponent match aggregates.

Short-term path:

- Parse opponent workbooks/PDFs into CSV outputs under `pipeline/outputs/reports/scouting`.
- Use those outputs to build opponent rolling features.

Long-term path:

- Persist parsed opponent match aggregates in Supabase so Staff portal and model training do not depend on local files.

### 3. Wyscout Event XML / Sportscode XML

Purpose:

- Produce richer match features than PDF/workbook summaries.
- Support event-derived opponent tendencies.
- Support tactical scouting by phase, pressure, and set piece.

Needed files:

- `sportscode.xml`
- `player_events.xml`
- `team_events.xml`
- `effective_time.xml`

Current parser support:

- `pipeline/ingestion/parse_wyscout.py` handles Sportscode, player events, team events, and effective time.
- Current roster filtering was built primarily for CofC player attribution.

Needed parser changes:

- Add an opponent/team mode that does not discard non-CofC rows.
- Parse team-level events for either side.
- Preserve `team_id`, `team_name`, `opponent_team_id`, and source-file provenance.
- Support source types where player identity is unavailable but team event context is still useful.

Database mapping:

- `athlete_event` for player-attributed event rows when athlete identity is known.
- `possession_sequence` for future sequence-aware features.
- `source_file.source_file_id` for exact file provenance.
- Existing `data_source` for vendor/system-level source identity.

Possible schema gap:

- A true `team_event` or `match_event` table may be useful for opponent/team-level events that do not belong to a known CofC athlete.
- Avoid forcing opponent team events into `athlete_event` unless a player identity can be resolved.

### 4. Wyscout PDF Match Reports

Purpose:

- Fastest practical source for opponent scouting features while XML access is inconsistent.
- Useful for validation against parsed event outputs.

Useful extracted fields:

- Goals for/against
- xG for/against
- Shots and shots on target
- Possession
- Pass accuracy
- Recoveries
- Duels and aerial duels
- Set-piece shots
- Formation
- Starting lineup, if present

Parser need:

- A PDF-to-structured-row parser for opponent match reports.
- Output should be one row per team-match, not just one narrative report.

Suggested output:

```text
pipeline/outputs/reports/scouting/<season>/opponent_history/
  opponent_match_stats.csv
  opponent_source_reconciliation.csv
```

Database mapping:

- `source_file` for every PDF.
- future opponent/team aggregate table, or staged CSV until schema is finalized.

### 5. Schedule and Match Context

Purpose:

- Provide future match anchors for forecasting and Staff portal selection.

Current source:

- `pipeline/data/schedules/2026_schedule.csv`

Fields already useful:

- `match_date`
- `opponent`
- `opponent_short`
- `home_away`
- `competition`
- `conference_match`
- `venue`
- `city`
- `state`
- `opponent_team_id`

Needed next:

- Travel distance
- Rest days
- Match congestion flags
- Weather join keys

Database mapping:

- `session`
- `match`
- `team`

### 6. Catapult / Load Data

Purpose:

- Add fatigue and availability features.
- Make the model CofC-specific instead of only public-stat based.

Useful features:

- Team rolling player load
- High-speed distance trend
- Sprint efforts trend
- Minutes concentration
- Short-rest load risk
- Projected starter availability

Database mapping:

- `athlete_load`
- `athlete_session_stint`
- `source_file`

Model use:

- Start as CofC-only fatigue/context flags.
- Avoid opponent fatigue features unless reliable opponent data exists.

### 7. Weather Data

Purpose:

- Add match context after core features are stable.

Useful fields:

- Temperature
- Humidity
- Wind speed
- Precipitation

Database mapping:

- Could start as a CSV joined to schedule by date and venue.
- Later can become a small `match_context` table.

Priority:

- Lower than opponent history and rolling form.

## Reconciliation Strategy

Every predictive feature should be traceable back to:

- season
- match slug
- team id
- source system
- source file id
- parser version
- parse timestamp

### Source File Reconciliation

Use `public.source_file` as the exact file registry.

Minimum checks:

- One row per concrete file.
- Unique `storage_bucket + storage_path`.
- `season` and `match_slug` populated.
- `source_system` and `source_type` populated.
- `sha256` populated when file is available locally or in Storage.
- `parse_status` updated after parser runs.

### Team Identity Reconciliation

Use `public.team` as the canonical team table.

Checks:

- Schedule `opponent_team_id` must exist in `team`.
- Wyscout team name/id should map to one `team.id`.
- Ambiguous team names should fail preflight.
- Opponent aliases should be explicit, not fuzzy-matched silently.

### Match Identity Reconciliation

Checks:

- One `session` per match date/opponent.
- One `match` row per match session.
- Source files should connect to the correct `session_id` once the session exists.
- Future opponent-history matches may not be CofC sessions; either store them as scouting-only source rows first or add a general match-history table.

### Feature Reconciliation

Before a feature is promoted into the active model config:

- Coverage should be reported in `match_feature_coverage.csv`.
- Feature should be computed using only pre-match data.
- Feature should have a documented source.
- Feature should be marked CofC-only, opponent-only, or differential.
- Missingness behavior should be explicit.

## Parser Build Plan

### Step 1: Opponent Source Inventory

Create an inventory command that reports, per 2026 opponent:

- schedule row exists
- team id exists
- opponent history files found
- source_file rows registered
- parse status
- usable match rows

Suggested command:

```bash
.venv/bin/python pipeline/scouting/inventory_opponent_sources.py --season 2026
```

### Step 2: Opponent PDF Parser

Build the easiest high-value parser first.

Inputs:

- Wyscout PDF match reports

Outputs:

- `opponent_match_stats.csv`
- `opponent_source_reconciliation.csv`

### Step 3: Opponent Workbook Parser

If Wyscout exports opponent match-stat workbooks:

- Normalize to the same columns as CofC match stats.
- Preserve Wyscout team id and source file id.
- Emit one row per team-match.

### Step 4: Opponent XML/Event Parser Mode

Extend Wyscout XML parsing to support:

- CofC-only mode
- opponent-only mode
- both-teams mode
- team-level event summary mode

This is the path toward true event-derived opponent scouting.

### Step 5: Feature Promotion Gate

Only add a new feature to `configs/seasons/cofc_2025.json` or future model configs when:

- coverage is acceptable
- no leakage is detected
- feature source is documented
- model comparison shows value

## Recommended Next Build

Best next engineering task:

1. Create `pipeline/scouting/inventory_opponent_sources.py`.
2. Define `pipeline/config/opponent_history_schema.csv`.
3. Add a sample/staged `opponent_match_stats.csv` output contract.
4. Update model readiness report to include opponent-history readiness.

This keeps the work grounded before building a complex parser.
