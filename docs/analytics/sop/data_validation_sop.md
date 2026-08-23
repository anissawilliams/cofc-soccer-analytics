# Match Intake Validation

## Status Meanings

- `blocked`: no source files were found or an XML file could not be read.
- `incomplete`: files were inventoried, but neither match analytics nor player
  scoring has the required inputs.
- `ready_for_staff_review`: at least one supported output can be generated. This
  does not mean approved, published, or coach-ready.

## Student Checklist

- Confirm season, date, opponent, location, competition, and score.
- Confirm every downloaded source appears in the source manifest.
- Check that every XML has a recognized classification.
- Confirm the two team-event files identify two distinct teams.
- Review canonical event counts and all unmapped labels.
- For COUG scoring, confirm the player-coded file was detected and players match
  the current roster.
- Confirm official minutes/lineups are ready, with 11 starters and the expected
  participant count.
- Compare visible score, goal, shot, card, and lineup totals with the media-team
  final box score and Wyscout.
- Record discrepancies in the handoff instead of editing parser output.

## Staff Checklist

- Resolve unknown labels and ambiguous player identities.
- Confirm the correct match export and roster were used.
- Spot-check timestamps across both halves.
- Confirm corrections preserve raw-source provenance.
- Review any shot coordinates, xG bounds, or manually entered fields.
- Run scoring preflight checks before coach-facing publication.

## Spiideo Validation

Retain Spiideo XML as a separate raw source. Until real exports establish the
contract, validate its identifiers, periods, timestamps, and clock behavior
before matching it to Wyscout events. Store reconciliation confidence and do not
invent missing event detail.

## Change Log

- v1.1 — Added official minutes, starters, and box-score checks.
- v1.0 — Defined intake statuses and 2026 review checks.
