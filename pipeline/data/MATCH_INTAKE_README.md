# CofC Match File Intake

After each match, open the match menu in Wyscout and download these six files.

## Download These XML Files

| Wyscout menu choice | Extension | Why we keep it |
|---|---|---|
| `SPORTSCODE XML (NEW VERSION)` | `.xml` | COUG scoring — required |
| `DOWNLOAD XML – CHARLESTON COUGARS (PLAYER)` | `.xml` | CofC player-event archive |
| `DOWNLOAD XML – OPPONENT (PLAYER)` | `.xml` | Opponent player-event archive |
| `DOWNLOAD XML – CHARLESTON COUGARS (TEAM)` | `.xml` | Match Flow — required |
| `DOWNLOAD XML – OPPONENT (TEAM)` | `.xml` | Match Flow — required |
| `DOWNLOAD XML EFFECTIVE TIME` | `.xml` | Clock quality check |

Use `SPORTSCODE XML (NEW VERSION)`. If you also download the older
`DOWNLOAD SPORTSCODE XML`, put the older file in `05_source_archive`, not in
the source folder scanned by the notebook.

## Keep Wyscout's Filenames

Do not rename, edit, convert, combine, or resave the downloaded files. A name
ending in `(1)` is okay.

Names may look like:

```text
YYYY-MM-DD_HH_MM, Charleston Cougars - UNCW Seahawks.xml
UNCW Seahawks_player-events_02-11-2025_Charleston Cougars-UNCW Seahawks.xml
Charleston Cougars_team-events_02-11-2025_Charleston Cougars-UNCW Seahawks.xml
UNCW Seahawks_team-events_02-11-2025_Charleston Cougars-UNCW Seahawks.xml
```

Wyscout may use `DD-MM-YYYY` inside its filenames. Leave that unchanged. Our
match folder uses `YYYY-MM-DD`.

## Match Folder

Name the match folder:

```text
YYYY-MM-DD_opponent
```

Use lowercase letters and underscores. Do not add home or away to the folder
name. Example: `2026-08-20_davidson`.

```text
2026/matches/2026-08-20_davidson/
  00_source/
    wyscout/          <- six current XML downloads
    spiideo/          <- original Spiideo export, when available
  05_source_archive/ <- older or replaced downloads
  20_generated/      <- notebook output
```

Point the intake notebook at `00_source`, not the full match folder.

## Run the Notebook

1. Open `pipeline/notebooks/2026_match_intake.ipynb` in Google Colab.
2. Mount Drive and complete the setup cell, including your full name in
   `prepared_by`.
3. Run with `CREATE_REVIEW_BUNDLE = False` and read the readiness table.
4. After reviewing warnings, set it to `True` and create the staff review
   bundle.

The notebook does not publish to Supabase. `ready_for_staff_review` means the
files can be reviewed; it does not mean approved or coach-ready.

## Stop and Ask for Help

- A file is reported as `invalid_xml` or `unknown_xml`.
- More than one Sportscode scoring file is detected.
- A player does not match the current roster.
- The score or event totals disagree with Wyscout.
- You are unsure which corrected download is current.

Ask Anissa before changing an original file. Do not publish data or push
directly to `main`.

The printable version is
[`docs/xml_ingestion_guide.docx`](../../docs/xml_ingestion_guide.docx).
