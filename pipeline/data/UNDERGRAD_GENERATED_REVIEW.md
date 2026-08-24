# Undergraduate Generated-Bundle Review

Use this checklist after the notebook creates `20_generated/`. This is a
quality-control review only. Students do not approve, reconcile, or publish
data.

## Folder check

The match folder should look like:

```text
YYYY-MM-DD_opponent/
  00_source/
    wyscout/
    official/
  staff/
  20_generated/
```

`20_generated` belongs beside `00_source`, not inside it. Do not edit or move
the original XML or PDF files after the bundle is created.

## Review in this order

### 1. Validation report

Open `*_validation_report.md` first.

Continue only when:

- Status is `ready_for_staff_review`.
- Match analytics, COUG player scoring, and official minutes/lineups are all
  marked `ready`.
- Staff events are `ready`. "No staff event CSV supplied" is acceptable only
  after confirming that staff did not report a manual incident or off moment.
- The source inventory contains the expected current files and no duplicate or
  unknown source.

Stop and ask if any section is false, blocked, unknown, or names the wrong
match.

### 2. Match metadata

Open `*_metadata.json` and compare it with the official box score:

- Match date and opponent
- Home, away, or neutral location
- Competition
- Final score
- `prepared_by`

Stop if any value is wrong. Do not fix a generated file by hand; correct the
notebook setup and regenerate the bundle.

### 3. Intake report

Open `*_intake_report.json` and check:

- `blocking_issues` and `items_for_review` are empty.
- No duplicate source is reported.
- The selected scoring file is the `SPORTSCODE XML (NEW VERSION)` export.
- Roster-matched player count is plausible for the match.
- The two team-event files resolve to Charleston and the opponent.
- `unmapped_labels` is empty.
- Goal count and team split match the official result.

An opponent player-event file showing zero CofC roster matches is expected.
That confirms the roster filter is excluding opponent players. A CofC scoring
file showing unmatched CofC players is not expected.

### 4. Official minutes and starters

Open `*_minutes.csv` and compare it with the official box score:

- Exactly 11 players have `started=True`.
- Every player who appeared is present once.
- Names and jersey numbers match the roster.
- Goalkeeper and starter minutes look correct.
- Substitute minutes are plausible.
- Total team minutes are plausible for the match format. For a standard
  90-minute match, the total should normally be 990 player-minutes.

Blank positions for substitutes may reflect the source box score and are not
by themselves a blocker.

### 5. Event coverage

Use the intake report and generated event files to spot-check:

- Both teams have team events.
- Canonical event count is nonzero.
- Mirrored-event count is close to the canonical count.
- Shot, goal, corner, free-kick, and scoring-opportunity counts are plausible.
- Goal timestamps and teams follow the match story.
- Player-event rows are not all assigned to one player.

Counts vary by match. Compare them with the video and official box score; do
not use a previous match's exact count as a required target.

### 6. Approval gate

Open `*_approval.json` only to confirm it exists and all approvals are still
`false`. Students do not enter the reviewer name, change approvals, run
reconciliation, or publish to Supabase.

## FGCU example — 2026-08-23

The reviewed FGCU bundle is a useful example of a healthy result:

- Final score: Charleston 3, Florida Gulf Coast 2
- Sources inventoried: 8 (six XML files and two PDFs)
- Roster players found: 17
- Official starters: 11
- Official player-minutes: 990
- Canonical team events: 237
- Events by team: Charleston 132, FGCU 105
- Goals found: 5, split 3–2
- Unmapped labels: 0
- Blocking issues: 0
- Items for review: 0

These figures describe this match only. Future matches should be judged for
internal consistency, not whether they reproduce FGCU's numbers.

## Handoff to staff

Send the staff reviewer:

- The complete `20_generated/` folder
- A note confirming the opponent, score, 11 starters, participant count, and
  any warning reviewed
- Any incident or discrepancy that requires a staff decision

If something is questionable, stop. Preserve the source files and send the
validation output to staff rather than guessing or editing generated data.
