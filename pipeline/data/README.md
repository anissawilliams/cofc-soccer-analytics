# Pipeline Data Directory

This folder is the default local data mount for the pipeline. It should contain
small, intentional repo inputs only.

## Versioned In Git

- `schedules/*.csv`: season schedules and stable team identifiers
- `manifests/*.csv`: match/source manifests used by inventory and ingestion
- `match_flow/*.json`: compact, reviewed two-team pressure snapshots derived from canonical team events
- `shot_maps/*.json`: compact, reviewed shot locations and chance-quality snapshots
- `../ingestion/roster_2025.csv`: small parser roster lookup

## Local Or External

The following should normally stay out of Git and live either on the local
machine or in a shared Google Drive/data store:

- `matches/`: raw Wyscout/Sportscode XML exports by match
- `raw/`: PDFs, workbooks, and original vendor exports
- `outputs/`: legacy generated COUG score CSVs

Use `.env` path overrides when data lives outside the repo:

```bash
COFC_MATCHES_DIR=/path/to/google-drive/data/matches
COFC_RAW_DIR=/path/to/google-drive/data/raw
COFC_WYSCOUT_PDF_DIR=/path/to/google-drive/data/raw/player_reports
COFC_LEGACY_DATA_OUTPUTS_DIR=/path/to/google-drive/data/outputs
```

## Supabase Storage

For durable source storage, use bucket `source-files` by default:

```text
source-files/
  cofc/
    2025/
      2025-09-27_william_mary/
        wyscout/
          2025-09-27_william_mary_cfc_sportscode.xml
          2025-09-27_william_mary_cfc_effective_time.xml
          2025-09-27_william_mary_cfc_player_events.xml
          2025-09-27_william_mary_cfc_team_events.xml
```

Enable Storage fallback only when needed:

```bash
COFC_ENABLE_SUPABASE_STORAGE=true
COFC_SOURCE_STORAGE_BUCKET=source-files
COFC_SOURCE_STORAGE_PREFIX=cofc
```

When enabled, parsers download missing Storage files into
`COFC_SOURCE_CACHE_DIR` and then parse the cached local copy.

Register each Storage object in `public.source_file`. The schema migration is:

```text
schema/2026_07_source_file.sql
```

The pipeline defaults still point here so a fully local setup works, but the
repo should not grow every time new match exports arrive.

## Loose Match Intake

Vendor filenames do not need to be renamed before inspection. Use the intake
command to classify XML files from their contents and keep scoring readiness
separate from team-analysis readiness:

```bash
.venv/bin/python pipeline/ingestion/prepare_match_intake.py \
  --input-dir /path/to/one-match-exports \
  --season 2026 \
  --slug 2026-08-20_davidson \
  --roster pipeline/ingestion/roster_2026.csv \
  --dry-run
```

Remove `--dry-run` only after reviewing the report. This writes a source report
and, when two complementary team XMLs are present, a deduplicated canonical
team-event CSV under the parsed outputs directory. When one player-coded XML
and a valid roster are present, it also writes roster-filtered scoring events
plus the complete raw player/team streams. It never writes to Supabase.

`scoring.ready` must be true before the COUG scoring workflow begins. Paired
team-event XMLs can power Match Flow but cannot replace the player-coded
Sportscode XML required for player scoring.

Reviewed Match Flow snapshots use the paired canonical team stream, never the
player scoring stream. Publish the compact JSON to `pipeline/data/match_flow`
or point the backend at an external published directory with
`COFC_MATCH_FLOW_DIR`.

## Shot Map Intake

The team-event XML identifies shots and their timing but does not contain xG or
pitch coordinates. Those richer fields come from the Wyscout match report or a
Wyscout CSV export and must be reviewed before publication.

Use `shot_map_template.csv` for one row per shot. Coordinates are normalized:
`x=0` is the left touchline, `x=100` the right touchline, `y=0` the shooting
team's own goal line, and `y=100` the opponent goal line. Allowed outcomes are
`goal`, `on_goal`, `on_post`, `blocked`, and `wide`. Keep a literal `<0.01` in
`xg_display` when Wyscout reports a bounded value instead of replacing it with
an invented exact value. Put the official team totals in `team_xg_total` and
`team_psxg_total` on at least one row per team when bounded values mean the
visible shot rows cannot be summed exactly.

After review, publish the compact snapshot:

```bash
.venv/bin/python pipeline/ingestion/prepare_shot_map.py \
  --input-csv pipeline/data/shot_map_template.csv \
  --home-team "Charleston Cougars" \
  --away-team "Davidson Wildcats" \
  --source-label "Wyscout Match Report" \
  --source-file "Charleston Cougars - Davidson Wildcats.pdf" \
  --output pipeline/data/shot_maps/2026-08-20_davidson.json
```

Reviewed snapshots are published to `pipeline/data/shot_maps`, or the backend
can read an external directory configured by `COFC_SHOT_MAP_DIR`. This keeps raw
PDFs and XML outside Git while allowing the small dashboard-ready snapshot to
deploy with the application.
