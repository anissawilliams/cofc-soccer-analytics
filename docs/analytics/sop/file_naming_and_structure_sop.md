# Match File Naming and Structure

## Canonical Match Slug

Use `YYYY-MM-DD_opponent`, for example `2026-08-20_davidson`. Use lowercase,
underscores, and the scheduled match date.

## Vendor Source Files

Do not rename vendor exports. Wyscout filenames are not a reliable data contract,
so the intake classifies XML files by their contents. Preserve revised downloads
as separate files and tell the reviewer which is authoritative.

## Drive Layout

```text
SEASON/matches/MATCH_SLUG/
  00_source/
    wyscout/
    spiideo/
  20_generated/
```

This is the recommended minimum, not a migration requirement. Existing folders
are valid if original and generated files remain separate.

## Generated Names

The intake writes predictable, slug-based names such as:

- `<slug>_metadata.json`
- `<slug>_intake_report.json`
- `<slug>_validation_report.md`
- `<slug>_canonical_team_events.csv`
- `<slug>_match_flow.json`
- `<slug>_players.csv`

Generated files can be recreated. Original source files cannot.

## Change Log

- v1.0 — Added content-based classification and the minimal Drive layout.
