# CofC Match Data Intake — Student Instructions

Use this checklist after every match. Your job is to preserve the original
exports, run the intake notebook, review the results, and send the generated
bundle to a staff reviewer. The notebook does not publish data.

## Match Folder Name

Name the match folder with this exact pattern:

```text
YYYY-MM-DD_opponent
```

Rules:

- Use the scheduled match date in year-month-day format.
- Use lowercase letters for the opponent.
- Replace spaces and punctuation with underscores.
- Do not add home/away to the folder name; that belongs in match metadata.

Examples:

```text
2026-08-20_davidson
2026-09-05_william_mary
2026-10-13_north_florida
```

## Folder Layout

```text
2026/
  matches/
    2026-08-20_davidson/
      00_source/
        wyscout/
        spiideo/
      05_source_archive/
      20_generated/
```

- Put the current original downloads in `00_source`.
- Put an older or superseded download in `05_source_archive`; do not delete it.
- Point the notebook at `00_source`, never the full match folder.
- The notebook writes only to `20_generated`.

## Wyscout Files

Download every export that is available. Wyscout filenames may vary, so **do
not rename the downloaded files**. The intake reads XML contents rather than
depending on filenames.

| File | Extension | Needed for | Requirement |
|---|---|---|---|
| Player-coded Sportscode export | `.xml` | COUG player scoring | Required for player scores |
| CofC team-events export | `.xml` | Match Flow and tactical events | Required for Match Flow |
| Opponent team-events export | `.xml` | Match Flow and tactical events | Required for Match Flow |
| Effective-time export | `.xml` | Clock and playing-time QA | Keep when available |
| Players in Match report | `.pdf` | Player-statistics QA | Keep when available |
| Full Match report | `.pdf` | Score, shots, xG, and team-total QA | Keep when available |
| Structured event export | `.csv`, `.xlsx`, or `.json` | Richer event and dashboard data | Keep every available export |
| Download bundle | `.zip` | Original vendor package | Keep the ZIP and extract a working copy |

The two team-events XML files do not replace the player-coded Sportscode XML.
It is normal for Match Flow to be ready while COUG player scoring is not ready.

## Spiideo Files

Keep the original Spiideo export in `00_source/spiideo/`. The expected first
format is `.xml`, but also retain `.csv`, `.json`, or `.zip` files when Spiideo
provides them. Do not convert Spiideo data into Wyscout columns. The sources will
be aligned later after their clocks and identifiers have been reviewed.

Do not place video files such as `.mp4` or `.mov` in the match-data intake
folder. Store video in the team's normal video location and record its link in
the match notes if needed.

## Do Not Change Original Files

- Do not rename, edit, resave, or convert XML, PDF, CSV, XLSX, JSON, or ZIP files.
- A filename ending in `(1)` is acceptable; keep it unchanged.
- Do not open an XML in Excel and save it again.
- Do not combine two exports manually.
- If Wyscout sends a corrected version, move the older file to
  `05_source_archive` and document which version is current.

## Complete the Notebook Setup

Open `pipeline/notebooks/2026_match_intake.ipynb` and complete:

- `SEASON`
- `MATCH_SLUG`
- `SOURCE_FOLDER`
- `OUTPUT_FOLDER`
- match date
- opponent
- home, away, or neutral location
- competition
- final score, when known
- `prepared_by` with your full name
- notes about missing or revised exports

Run the inspection with:

```python
CREATE_REVIEW_BUNDLE = False
```

After reviewing the results, change it to `True` to create the review bundle.

## Stop and Ask for Help When

- A file is classified as `invalid_xml` or `unknown_xml`.
- More than one player-coded Sportscode XML is detected.
- A player does not match the current roster.
- The Wyscout score or totals disagree with the generated report.
- You are uncertain which corrected export is current.
- You think an original source file needs to be edited.

`ready_for_staff_review` means the bundle can be reviewed. It does not mean the
data has been approved, published, or delivered to coaches.
