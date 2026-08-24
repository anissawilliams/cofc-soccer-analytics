# CofC Match File Intake

After each match, collect the six Wyscout XML files and the media team's official
final box score PDF. Keep the two sources in separate folders.

## Download These XML Files

| Wyscout menu choice | Extension | Why we keep it |
|---|---|---|
| `SPORTSCODE XML (NEW VERSION)` | `.xml` | COUG scoring — required |
| `DOWNLOAD XML – CHARLESTON COUGARS (PLAYER)` | `.xml` | CofC player-event archive |
| `DOWNLOAD XML – OPPONENT (PLAYER)` | `.xml` | Opponent player-event archive |
| `DOWNLOAD XML – CHARLESTON COUGARS (TEAM)` | `.xml` | Match Flow — required |
| `DOWNLOAD XML – OPPONENT (TEAM)` | `.xml` | Match Flow — required |
| `DOWNLOAD XML EFFECTIVE TIME` | `.xml` | Clock quality check |

## Add the Official Box Score

Put the final box score PDF from the media team in `00_source/official/`. This
is separate from Wyscout and is required for official player minutes and
starter status. It also gives staff an authoritative score, goal, card, and
lineup check.

Do not substitute the Wyscout match-report PDF for this file. Wyscout event
times are useful for event analysis, but the media-team box score is the source
of record for official minutes.

Use `SPORTSCODE XML (NEW VERSION)`. If you also download the older
`DOWNLOAD SPORTSCODE XML`, put the older file in `05_source_archive`, not in
the source folder scanned by the notebook.

## Filenames Are Flexible

The parser identifies each XML by its contents, not its filename. You may keep
Wyscout's downloaded names or rename the files consistently. A name ending in
`(1)` is also okay.

Names may look like:

```text
YYYY-MM-DD_HH_MM, Charleston Cougars - UNCW Seahawks.xml
UNCW Seahawks_player-events_02-11-2025_Charleston Cougars-UNCW Seahawks.xml
Charleston Cougars_team-events_02-11-2025_Charleston Cougars-UNCW Seahawks.xml
UNCW Seahawks_team-events_02-11-2025_Charleston Cougars-UNCW Seahawks.xml
```

Wyscout may use `DD-MM-YYYY` inside its filenames. If you keep the vendor name,
that is fine; our match folder still uses `YYYY-MM-DD`.

If your team prefers cleaner names, use this optional convention:

```text
2026-08-20_davidson_wyscout_sportscode.xml
2026-08-20_davidson_wyscout_cofc_player-events.xml
2026-08-20_davidson_wyscout_opponent_player-events.xml
2026-08-20_davidson_wyscout_cofc_team-events.xml
2026-08-20_davidson_wyscout_opponent_team-events.xml
2026-08-20_davidson_wyscout_effective-time.xml
```

The hard rules are:

- Keep the `.xml` extension.
- Put all current files for one match in that match's `00_source` folder.
- Never overwrite an older source file. Move it to `05_source_archive` or add a
  clear version suffix such as `_v2`.
- Do not edit, convert, combine, or resave the XML contents.

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
    official/         <- final media-team box score PDF
    spiideo/          <- original Spiideo export, when available
  staff/
    staff_events.csv  <- shared manual incidents/off moments, when needed
  05_source_archive/ <- older or replaced downloads
  20_generated/      <- notebook output
```

Point the intake notebook at `00_source`, not the full match folder.

## Staff Events and Off Moments

Copy [`staff_events_template.csv`](staff_events_template.csv) into the match's
`staff/` folder and name it `staff_events.csv`. A red card row looks like:

```csv
player_name,jersey,event_type,minute,weight,notes,entered_by
J. Jordheim,3,red_card,82:30,-2,Unsporting behavior,AW
```

The parser roster-matches the player, preserves the exact 82:30 off moment, and
requires the approved red-card proposal of `-2`. The row is queued for staff
review; it does not silently change a published score.

Staff events can be prepared retroactively without any Wyscout or PDF parsing:

```bash
.venv/bin/python pipeline/ingestion/prepare_staff_events.py \
  --season 2026 --slug 2026-08-20_davidson \
  --staff-dir "/path/to/2026-08-20_davidson/staff" \
  --output-dir "/path/to/2026-08-20_davidson/20_generated"
```

After staff runs `schema/2026_08_red_card_metric.sql`, preview or apply only the
staff events with:

```bash
.venv/bin/python pipeline/ingestion/load_staff_events.py \
  --season 2026 --slug 2026-08-20_davidson \
  --staff-dir "/path/to/2026-08-20_davidson/staff"

# Staff only, after reviewing the dry run:
.venv/bin/python pipeline/ingestion/load_staff_events.py \
  --season 2026 --slug 2026-08-20_davidson \
  --staff-dir "/path/to/2026-08-20_davidson/staff" --apply
```

The apply step records the reviewed incident, updates an existing stint's exact
off minute, and creates/updates the scoring event used by the normal COUG score
publication. Rebuild/publish the affected match score afterward; other match
parsing is not required.

## Run the Notebook

1. Open `pipeline/notebooks/2026_match_intake.ipynb` in Google Colab.
2. Mount Drive and complete the setup cell, including your full name in
   `prepared_by`.
3. Run with `CREATE_REVIEW_BUNDLE = False` and read the readiness table.
4. After reviewing warnings, set it to `True` and create the staff review
   bundle.

The notebook does not publish to Supabase. `ready_for_staff_review` means the
files can be reviewed; it does not mean approved or coach-ready.

## Staff Review and Supabase Promotion

The preferred staff workflow is
[`2026_match_publish.ipynb`](../notebooks/2026_match_publish.ipynb). It runs
directly against the shared Drive match folder, pulls current code from GitHub,
reads Supabase credentials from Colab Secrets, and keeps separate confirmation
gates for approval, evidence loading, archive/Match Flow promotion, and final
COUG score publication. No local download or Git data commit is required.

The commands below document the same stages for recovery or local use.

The notebook creates `<slug>_approval.json` with all three decisions set to
`false`:

```json
{
  "reviewed_by": "",
  "reviewed_at": "",
  "approvals": {
    "source_archive": false,
    "match_analytics": false,
    "coug_scoring": false
  },
  "notes": ""
}
```

Staff—not students—complete this file after reviewing the validation report.
Use a timestamp with timezone, for example `2026-08-20T18:30:00-04:00`. It is
valid to approve the source archive and match analytics while leaving COUG
scoring false.

Preview the exact Supabase operations first:

```bash
.venv/bin/python pipeline/ingestion/promote_match_intake.py \
  --source-dir "/path/to/00_source" \
  --bundle-dir "/path/to/20_generated"
```

Review `<slug>_promotion_receipt.json`. Before applying the archive promotion,
preview the database evidence load directly from the generated Drive folder:

```bash
.venv/bin/python pipeline/ingestion/load_match.py \
  --slug YYYY-MM-DD_opponent --season 2026 \
  --bundle-dir "/path/to/20_generated" --dry-run
```

The loader reads the reviewed `*_metadata.json` from the bundle; a separate
match-manifest edit is not required. If the dry run is correct, apply the
evidence load first:

```bash
.venv/bin/python pipeline/ingestion/load_match.py \
  --slug YYYY-MM-DD_opponent --season 2026 \
  --bundle-dir "/path/to/20_generated"
```

Then apply the archive promotion with staff credentials. Running promotion
after the evidence load lets its `source_file` rows reference the new session:

```bash
.venv/bin/python pipeline/ingestion/promote_match_intake.py \
  --source-dir "/path/to/00_source" \
  --bundle-dir "/path/to/20_generated" \
    --apply
```

Finally, preview the COUG scores. This reads the loaded evidence and writes a
review CSV, but does not update the public table:

```bash
.venv/bin/python pipeline/analytics/publish_event_derived_coug_scores.py \
  --season 2026 --slug YYYY-MM-DD_opponent
```

After reviewing every player's proposed total, publish with:

```bash
.venv/bin/python pipeline/analytics/publish_event_derived_coug_scores.py \
  --season 2026 --slug YYYY-MM-DD_opponent --apply
```

Promotion stops if a source file or intake report changed after review, an
approved product is not ready, or an approved artifact is missing. Filenames
are preserved as metadata; classification and collision-safe Storage paths do
not depend on students renaming vendor files.

## Stop and Ask for Help

- A file is reported as `invalid_xml` or `unknown_xml`.
- More than one Sportscode scoring file is detected.
- Official minutes/lineups are not ready after adding the final box score PDF.
- A supplied `staff_events.csv` row does not match the roster or approved weight.
- A player does not match the current roster.
- The score or event totals disagree with Wyscout.
- You are unsure which corrected download is current.

Ask Anissa before changing an original file. Do not publish data or push
directly to `main`.

The printable version is
[`docs/xml_ingestion_guide.docx`](../../docs/xml_ingestion_guide.docx).

For the shortest run-day handoff, use
[`TOMORROW_MATCH_CHECKLIST.md`](TOMORROW_MATCH_CHECKLIST.md).
