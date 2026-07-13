# 2025 Source Inventory Summary

Last updated: 2026-07-13

Command:

```bash
.venv/bin/python pipeline/ingestion/inventory_sources.py --season 2025 --csv
```

## Interpretation

Spiideo is intentionally treated as a future source. Missing Spiideo files do
not currently count as a data-quality issue for 2025 Wyscout-only ingestion.

## Current 2025 Coverage

- 16 real 2025 matches are included in the default inventory.
- All 16 have Wyscout `sportscode.xml`.
- All 16 have Wyscout `effective_time.xml`.
- 15 of 16 have Wyscout PDF player reports in the expected folder.
- 16 of 16 have parsed player CSV outputs.
- 1 of 16 has raw `player_events.xml` locally.
- 1 of 16 has raw `team_events.xml` locally.
- Spiideo is missing for all matches and is expected-missing for now.

## Current Gaps

### Missing Wyscout PDF

- `2025-08-30_boston`

The inventory did not find a matching `players_2025_08_30_Boston.pdf` in
`pipeline/data/raw/player_reports/`.

### Missing Raw Player/Team Events XML

The following matches have parsed player CSV outputs but do not currently have
raw `player_events.xml` or `team_events.xml` in the local match folder:

- `2025-08-22_south_carolina`
- `2025-08-26_davidson`
- `2025-08-30_boston`
- `2025-09-02_north_carolina`
- `2025-09-06_elon`
- `2025-09-10_usc_upstate`
- `2025-09-13_campbell`
- `2025-09-17_furman`
- `2025-09-24_georgia_southern`
- `2025-09-27_william_mary`
- `2025-10-05_campbell`
- `2025-10-08_north_florida`
- `2025-10-15_winthrop`
- `2025-10-18_elon`
- `2025-10-25_william_mary`

UNCW (`2025-11-02_uncw`) currently has both raw `player_events.xml` and
`team_events.xml`.

### Empty/Stray Match Folder

There is an empty folder:

- `pipeline/data/matches/2025/2025-09-20_uncw`

It is not included in the default inventory because it is not in the manifest
and has no source files. It can still be inspected explicitly with:

```bash
.venv/bin/python pipeline/ingestion/inventory_sources.py --season 2025 --slug 2025-09-20_uncw --include-empty-dirs
```

## What This Means For PEAK

We should not say that all raw Wyscout event sources are present locally yet.
The safer statement is:

- Parsed player-event CSV outputs exist for the 2025 season.
- Raw `player_events.xml` and `team_events.xml` are currently present locally
  only for UNCW.
- PEAK can continue as candidate/review-only until event source completeness and
  coach mapping rules are confirmed.

## Undergrad / Data Collection Ask

For the missing 15 matches, download and place the raw Wyscout files if
available:

- `player_events.xml`
- `team_events.xml`

Also locate or export the Boston player PDF report:

- `players_2025_08_30_Boston.pdf`

Spiideo can remain out of scope until that source becomes available.
