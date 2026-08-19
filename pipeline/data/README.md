# Pipeline Data Directory

This folder is the default local data mount for the pipeline. It should contain
small, intentional repo inputs only.

## Versioned In Git

- `schedules/*.csv`: season schedules and stable team identifiers
- `manifests/*.csv`: match/source manifests used by inventory and ingestion
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
  --dry-run
```

Remove `--dry-run` only after reviewing the report. This writes a source report
and, when two complementary team XMLs are present, a deduplicated canonical
team-event CSV under the parsed outputs directory. It never writes to Supabase.

`scoring.ready` must be true before the COUG scoring workflow begins. Paired
team-event XMLs can power Match Flow but cannot replace the player-coded
Sportscode XML required for player scoring.
