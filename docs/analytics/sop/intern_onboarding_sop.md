# Undergraduate Match-Data Onboarding

## Purpose

Undergraduate analysts help acquire, inspect, enrich, and validate match data.
They produce a review bundle; a staff reviewer approves and publishes it.

## Access

Required:

- CofC shared Google Drive match-data folder
- Wyscout access appropriate to the analyst's role
- Access to the media team's final box score PDF
- Google Colab
- GitHub read access to this repository

Not required:

- Supabase service credentials
- Render access
- production environment variables

Never paste a password, API key, `.env` value, or service credential into a
notebook, Drive file, issue, or chat.

## First Match

1. Read the [weekly workflow](workflow_sop.md) and
   [validation SOP](data_validation_sop.md).
2. Open `pipeline/notebooks/2026_match_intake.ipynb` in Google Colab.
3. Work with a staff member on one completed match.
4. Put Wyscout XMLs in `00_source/wyscout/` and the media-team final box score
   PDF in `00_source/official/`.
5. Run the notebook inspection with `CREATE_REVIEW_BUNDLE = False`.
6. Explain which analytics are ready, which are not, and why.
7. After review, set `CREATE_REVIEW_BUNDLE = True` and create the bundle.
8. Send the validation report to the assigned staff reviewer.

## Weekly Responsibilities

- Preserve original vendor exports and filenames.
- Enter complete match metadata.
- Inspect file classification and event counts.
- Identify missing, unreadable, or unknown exports.
- Review unmatched players and unmapped event labels.
- Enrich shot or event fields only in the designated review template.
- Record questions and corrections rather than silently changing generated data.
- Add staff-supplied incidents only through the shared `staff_events.csv`
  template; include your initials and an exact match clock.

## Safety Rules

- Never edit or delete an original source export.
- Keep generated output outside the source folder.
- Never interpret `ready_for_staff_review` as published or coach-ready.
- Never load data into Supabase or merge directly to `main`.
- Do not change scoring weights, player mappings, or parser code as a data fix.
- Stop and escalate when a player identity is ambiguous or an XML file is unknown.

## Escalate When

- Wyscout does not provide the expected player-coded Sportscode XML.
- An XML file is reported as unreadable or unknown.
- A player name or number does not match the season roster.
- Wyscout totals disagree with generated totals.
- The official minutes/lineups readiness row is false.
- The same source file appears in two match folders.
- A correction would change a published match.

## Completion Standard

A student's work is complete when the review bundle and validation report exist,
metadata is filled in, warnings are documented, and a staff reviewer has been
notified. Publication is a separate staff-owned step.

## Change Log

- v1.1 — Added the separate official-box-score source and minutes check.
- v1.0 — Added the 2026 Colab intake and staff-review boundary.
