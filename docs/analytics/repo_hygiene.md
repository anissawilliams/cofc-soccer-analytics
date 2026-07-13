# Repo Hygiene

Last updated: 2026-07-13

## Goal

Keep the repository portable, reviewable, and reproducible without turning Git
into the long-term storage system for vendor exports and generated reports.

## Git Should Track

- Application and pipeline code
- Config files under `configs/` and `pipeline/config/`
- Small operating tables such as schedules and manifests
- Documentation and SOPs
- Selected Markdown report shells or human-readable summaries

## Git Should Not Track

- Raw Wyscout XML exports
- Wyscout PDF reports
- Spiideo/Catapult exports
- Parsed player CSV outputs
- Generated score reconciliation CSVs
- Generated figures and dashboard images
- Local cache files such as `__pycache__`, `.DS_Store`, and notebook checkpoints

## Canonical Local Shape

```text
pipeline/data/
  schedules/                 tracked
  manifests/                 tracked
  matches/                   local or Google Drive
  raw/                       local or Google Drive
  outputs/                   local legacy outputs

pipeline/outputs/
  reports/scouting/**/*.md   tracked report shells
  reports/**/*.csv           generated, ignored
  2025/                      generated, ignored
```

## New Computer Setup

1. Clone the repo.
2. Create `.env` from `env.example`.
3. If source data lives in Google Drive, set the `COFC_*` path overrides.
4. If source data lives in Supabase Storage, set:

```bash
COFC_ENABLE_SUPABASE_STORAGE=true
COFC_SOURCE_STORAGE_BUCKET=source-files
COFC_SOURCE_STORAGE_PREFIX=cofc
```

Files are cached locally under `COFC_SOURCE_CACHE_DIR` so parsing still works
with ordinary file paths.

5. Run source inventory before ingestion:

```bash
.venv/bin/python pipeline/ingestion/inventory_sources.py --season 2025
```

## Cleanup Rule

If a file can be reproduced by a pipeline command, keep it ignored unless it is
a deliberately curated Markdown artifact for coaches or handoff.
