# Next Work Queue

Last updated: 2026-07-13

## Stable Checkpoint

The project now has a cleaner operating model:

- Git tracks code, configs, docs, schedules, manifests, mapping tables, and the
  small parser roster lookup.
- Supabase Storage bucket `source-files` stores raw XML/PDF source evidence.
- `public.source_file` stores concrete file metadata, checksums, Storage paths,
  and parse status.
- Local machines use `pipeline/.cache/source_files/` plus generated outputs.
- Fresh-clone parsing has been tested through Storage-backed hydration.

This is the baseline to preserve.

## Immediate Smoke Tests

Run these after any new clone or setup change:

```bash
python pipeline/ingestion/inventory_sources.py --season 2025 --slug 2025-09-27_william_mary
python pipeline/ingestion/batch_parse.py --season 2025 --slug 2025-09-27_william_mary --dry-run
python pipeline/ingestion/batch_parse.py --season 2025 --slug 2025-09-27_william_mary
```

Expected fresh-clone behavior:

- Old local booleans such as `sportscode_xml` can be `False`.
- New `*_source` columns should show `storage` or `cache` for registered files.
- Parsed output should appear under `pipeline/outputs/2025/<slug>/`.
- `git status --short` should remain clean after generated outputs are written.

## Next Engineering Tasks

1. **Storage-only parse verification**

   Confirm one match can parse on the new computer when no local raw source
   folder exists. Keep this as the standard portability test.

2. **Register new raw XML as it arrives**

   Missing player/team XML is not a current blocker. The pipeline should keep
   parsing available Sportscode/effective-time/PDF evidence and should label
   source coverage limitations in reconciliation. When undergrads download
   missing Wyscout XMLs, add them locally or to the intake folder, then run:

   ```bash
   python pipeline/ingestion/register_source_files.py --season 2025 --slug <match_slug>
   ```

   Priority files for W&M/Watson investigation:

   - `2025-09-27_william_mary` player-events XML
   - `2025-09-27_william_mary` team-events XML
   - `2025-10-25_william_mary` player-events XML
   - `2025-10-25_william_mary` team-events XML

3. **Source-aware inventory polish**

   Add optional inventory columns for `source_file.parse_status`,
   `source_file.sha256`, and `source_file.storage_path` when `--csv` is used.

4. **Loader provenance**

   When `load_match.py` writes `athlete_event`, pass through
   `source_file_id` where the exact source file is known.

5. **Score reconciliation triage**

   Build source-aware triage from the reconciliation outputs we already have.
   Rows with positive legacy/PDF PEAK but zero event-derived PEAK should be
   flagged as source review items when player/team XML is missing.

   Focus first on:

   - `2025-09-27_william_mary` J. Watson: legacy PEAK 19.0 vs event-derived 0.0
   - `2025-10-25_william_mary` R. Watson: legacy PEAK 3.0 vs event-derived 0.0
   - Any `legacy_only_player` rows with positive PEAK

   Rerun this section after W&M raw XMLs land to see whether the source review
   flags clear or become true scoring/mapping questions.

## Analytics Tasks After Source Stability

1. Run the scoring guardrails before any coach-facing report:

   ```bash
   python pipeline/analytics/validate_scoring_config.py
   python pipeline/analytics/check_peak_scoring_fixture.py
   ```

   Expected status:

   - `Scoring config validation: 0 error(s), 0 warning(s)`
   - `PEAK scoring fixture: all checks passed`

2. Tighten PEAK implementation using `pipeline/config/wyscout_peak_normalization.csv`.
3. Implement Advance threshold scoring with the confirmed `0.5 per 10` rule.
4. Add double-count priority so Punish wins over Advance.
5. Rebuild reconciliation reports and compare candidate PEAK vs legacy/PDF.
6. Move coach-facing drilldown toward:

   ```text
   Player -> bucket -> raw label -> mapped COUG metric -> count -> weight -> score -> source file
   ```

## Scouting / Modeling Queue

1. Keep 2026 schedule QA current.
2. Populate opponent scouting shells as 2026 data arrives.
3. Add prior-season data if/when Wyscout access returns.
4. Keep ML out of COUG scoring; use ML for scouting, simulation, and recruiting similarity.

## Frontend Readiness

1. Before 2026 match reporting goes live, update the frontend COUG Table views
   to default to the active season (`2026`) instead of historical/calibration
   season data.
2. Add an explicit season selector or config-driven active season so the app
   can show 2025 calibration data without accidentally presenting it as current
   coach-facing output.

## Commit Hygiene

Before ending a work session:

```bash
git status --short
python pipeline/ingestion/inventory_sources.py --season 2025 --slug 2025-09-27_william_mary
```

Commit only code/config/docs/small operating tables. Raw source files and
generated outputs should stay in Storage/local cache, not Git.
