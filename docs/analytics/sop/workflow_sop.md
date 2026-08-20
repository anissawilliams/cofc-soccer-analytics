# Post-Match Data Workflow

## Purpose

This is the repeatable handoff from original Wyscout exports to reviewed match
data. Google Drive remains the shared workspace. Tested repository code performs
the parsing, and only approved canonical data is published.

## Ownership

| Stage | Undergraduate analyst | Staff reviewer |
|---|---|---|
| Download and archive | Responsible | Available for questions |
| Inspect and parse | Responsible | Reviews exceptions |
| Enrich and QA | Responsible | Resolves ambiguous mappings |
| Create review bundle | Responsible | Approves or returns |
| Publish | No production access | Responsible |

## 1. Create the Match Folder

Use the match slug `YYYY-MM-DD_opponent`, with the opponent in lowercase and
underscores between words. A minimal Drive layout is:

```text
2026/matches/YYYY-MM-DD_opponent/
  00_source/
    wyscout/
    spiideo/       # optional until a real export is available
  05_source_archive/  # older corrected/replaced downloads
  20_generated/
```

Existing Drive folders may be used. The only hard rule is that generated files
must not be written inside the source folder.

Give student analysts the copyable
[`MATCH_INTAKE_README.md`](../../../pipeline/data/MATCH_INTAKE_README.md) for the
complete extension and download checklist.

## 2. Preserve the Original Exports

Download every available Wyscout export into `00_source/wyscout/`. Do not rename,
edit, convert, or overwrite vendor files. The intake creates a SHA-256 fingerprint
for every source file so revised downloads can be identified later.

## 3. Run the Student Intake

Open `pipeline/notebooks/2026_match_intake.ipynb` in Colab, mount Drive, and fill
in the setup cell. Run the inspection first with:

```python
CREATE_REVIEW_BUNDLE = False
```

The classifier uses XML contents rather than filenames. Review the readiness
table and all warnings before continuing.

## 4. Understand Readiness

- Two complementary team-event XMLs can produce canonical team events and Match
  Flow.
- A player-coded Sportscode XML that matches the season roster is required for
  COUG player-scoring preparation.
- Match reports or richer Wyscout exports may still require reviewed shot-map
  enrichment.
- Spiideo is archived independently until its real clock and event structure has
  been validated. Do not force it into the Wyscout schema.

One ready output does not imply every output is ready.

## 5. Create the Review Bundle

After resolving or documenting inspection results, set
`CREATE_REVIEW_BUNDLE = True`. The generated folder may contain:

- match metadata
- source inventory and checksums
- intake report
- human-readable validation report
- canonical two-team events and Match Flow snapshot
- roster-filtered player events, when eligible
- complete player/team parser streams for QA

The bundle is not published and must not be presented as coach-ready.

## 6. Staff Review

The reviewer checks source completeness, roster matches, event counts, unmapped
labels, score/lineup context, and any manual enrichment. Corrections must be
recorded explicitly. Parser or mapping changes require tests and code review.

## 7. Publish

Publication is a separate, credentialed staff action. The generated
`<slug>_approval.json` begins with every approval set to `false`. A staff reviewer:

1. reads `<slug>_validation_report.md` and checks the generated outputs;
2. enters their name and a timezone-aware ISO timestamp, such as
   `2026-08-20T18:30:00-04:00`;
3. changes only the approved products to `true` and records any notes;
4. runs the promotion command without `--apply`;
5. reads `<slug>_promotion_receipt.json`; and
6. reruns with `--apply` only when the preview is correct.

```bash
.venv/bin/python pipeline/ingestion/promote_match_intake.py \
  --source-dir "/path/to/00_source" \
  --bundle-dir "/path/to/20_generated"

.venv/bin/python pipeline/ingestion/promote_match_intake.py \
  --source-dir "/path/to/00_source" \
  --bundle-dir "/path/to/20_generated" \
  --apply
```

The apply step requires staff-controlled `SUPABASE_URL` and
`SUPABASE_SERVICE_KEY` values. It uploads raw sources and approved artifacts to
the private `source-files` bucket, then upserts one `public.source_file` row per
object. Paths include the SHA-256 fingerprint, so revised downloads do not
overwrite earlier files and rerunning the same bundle is idempotent. If a
matching season/date session exists, the rows are linked to it; otherwise they
remain traceable by season and match slug and the receipt prints a warning.

This step archives and registers the approved intake. COUG score calculation is
still a separate staff publication after coach-confirmed scoring rules. Raw
Wyscout and Spiideo files remain outside Git; only intentional compact inputs,
configuration, code, tests, and approved snapshots are versioned.

## Change Log

- v1.0 — Replaced the scaffold with the 2026 Drive/Colab review workflow.
