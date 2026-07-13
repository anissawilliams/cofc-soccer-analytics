# Coach Questions To Unblock The 2026 Analytics Workflow

Last updated: 2026-07-13

This list is organized by what each question unlocks. The goal is to avoid
getting blocked mid-season because a scoring rule, report expectation, or data
handoff assumption was unclear.

## Highest Priority

### 1. What should be the official source of truth for COUG Table scores? — Answered

Decision:

- Event-derived scoring is primary.
- Wyscout PDFs are validation/comparison, not the official score source.

Why this matters:

- Determines what gets published to coaches
- Determines what counts as a discrepancy
- Prevents us from chasing legacy outputs that were never meant to be final

### 2. Should PEAK be scored from event actions, PDF report values, or coach-reviewed tags? — Answered

Decision:

- Individual Wyscout events are sufficient across PEAK.
- No sequence bonus.
- No coach/video confirmation gate required for PEAK scoring.
- Wyscout label mapping still needs a normalization table.

Why this matters:

- PEAK is where the biggest score discrepancies have appeared
- We need to know whether Wyscout-derived events are sufficient or whether
  coach/video validation is required

### 3. What is the final rule for Advance? — Answered

Decision:

- Advance = `0.5` points per `10` successful Advance actions

Still needed:

- Which Wyscout labels count as Advance?
- Build/confirm the normalization table.

### 4. How should Punish and Advance interact? — Answered

Decision:

- Do not double-count the same action as both Punish and Advance
- Punish takes priority
- The 3-5 pass threshold is the dividing line between Punish and Advance.

Still needed:

- Encode the threshold rule in the PEAK mapping/scoring logic.

### 5. What should be player-facing versus coach-only? — Open

Questions:

- Which COUG scores can players see?
- Should players see ASET/PEAK/Set Piece totals, category breakdowns, or only
  selected coaching messages?
- Should scouting reports have separate coach and player versions?

Why this matters:

- Impacts dashboards, report design, and language

## COUG Table Scoring

### 6. Should all ASET events require positive/successful outcomes?

Questions:

- Which defensive actions count even if the Wyscout outcome is unknown?
- Which defensive actions require `Plus`, success, or coach confirmation?
- Are failed defensive duels ever scored negatively?

### 7. How should unknown Wyscout outcomes be handled?

Current issue:

- Parsed Wyscout rows often have `outcome=Unknown`
- Earlier ingestion skipped some events because of outcome filtering

Questions:

- Which labels are countable even with unknown outcome?
- Which labels must be reviewed manually?
- Should unknowns enter the database with `coach_confirmed=false`?

### 8. What are the official Set Piece scoring rules?

Questions:

- Confirm attacking set-piece positive actions
- Confirm defensive set-piece positive actions
- Confirm negative scoring for set-piece concessions
- Confirm whether the set-piece concession penalty is team-wide, player-specific,
  or assigned only to players on the field

### 9. How should team-level events be assigned to players?

Examples:

- Clean sheet
- Goals conceded
- Set-piece goals conceded
- Team pressing/possession outcomes

Questions:

- Credit all players on the field?
- Credit starters only?
- Credit players by minutes threshold?
- Exclude goalkeepers or include everyone?

### 10. Should COUG scores be raw totals, per-90 values, or both?

Questions:

- Which version should coaches see first?
- Should substitutions/minutes affect ranking?
- Should there be a minimum minutes threshold for match rankings?

### 11. What should happen when a player has multiple names or aliases?

Examples:

- Goetzke / Emanuele
- Nicknames in coach workbook

Questions:

- Who owns alias approval?
- Should aliases be season-specific?
- Should aliases be allowed from Wyscout, coach workbook, or both?

## Data Sources and Handoff

### 12. Which files will we reliably receive after each match?

For each match, confirm whether we expect:

- Wyscout `sportscode.xml`
- Wyscout `player_events.xml`
- Wyscout `team_events.xml`
- Wyscout `effective_time.xml`
- Wyscout PDF player report
- Spiideo tags
- Catapult/GPS export
- Coach spreadsheet or manual tags

### 13. Who is responsible for downloading and placing raw files?

Questions:

- Who downloads Wyscout files?
- Who downloads Spiideo files?
- Who exports Catapult data?
- Where should files be placed?
- What is the deadline after each match?

### 14. Where should shared files live long-term?

Options:

- Google Drive folder
- Local project folder
- Supabase storage
- GitHub for non-sensitive configs only

Questions:

- Who needs access?
- Should raw data stay out of Git?
- Should generated coach reports be versioned in Git?

### 15. What is the acceptable turnaround time after each match?

Questions:

- Same night?
- Next morning?
- Before Monday staff meeting?
- Different timelines for COUG Table, scouting, and video?

## Scouting Reports

### 16. What is the minimum viable scouting report for the first 2026 opponent?

Proposed MVP:

- One-page executive brief
- Probable lineup shell
- Four-phase tactical summary
- One-page data profile
- One-page set-piece report
- Three How We Can Play Them recommendations
- Player-facing clip list
- Coaching playlist
- Match-day observation sheet
- Post-match validation table

Questions:

- Is this too much for week one?
- Which pieces are essential?
- Which pieces can be coach-only?

### 17. How many opponent matches should be reviewed each week?

Current workflow says:

- Review three to five opponent matches

Questions:

- Is three enough during tight turnarounds?
- Which matches should be prioritized?
- Should CAA matches matter more than non-conference matches?

### 18. What standard phases should every scouting report use?

Proposed four phases:

- Opponent in possession
- Opponent out of possession
- Opponent attacking transition
- Opponent defensive transition

Questions:

- Is this the preferred coaching language?
- Should set pieces be a fifth standalone phase?
- Should goal kicks/buildout be separated?

### 19. What does the staff want from simulation?

Questions:

- Do they want win/draw/loss probabilities?
- Do they want scenario comparisons instead?
- What kinds of scenarios are useful?
- What probability language should be avoided with players?

### 20. What belongs in the player-facing brief?

Questions:

- Maximum length?
- Maximum number of messages?
- Should data appear at all?
- Should it include opponent player names/numbers?
- Should it include set-piece reminders?

### 21. What belongs in the coach-only report?

Questions:

- Deeper data tables?
- Uncertainty notes?
- Model/simulation outputs?
- Full tactical alternatives?
- Individual matchup concerns?

## Video and Tagging

### 22. What video platform/tags will be used for opponent scouting?

Questions:

- Spiideo?
- Wyscout clips?
- Manually tagged video?
- A mix?

### 23. What are the required scouting video tags?

Proposed tag groups:

- In-possession
- Out-of-possession
- Transition
- Set pieces
- Key individuals

Questions:

- Do coaches want these exact labels?
- Should tags mirror the weekly report sections?
- Should tags be simple enough for undergrads to apply consistently?

### 24. How many clips should be player-facing?

Current workflow says:

- 8 to 12 player-facing clips
- 6 to 10 minute presentation
- 3 to 4 major messages

Questions:

- Is that right?
- Who approves final clips?
- Should unit-specific clips be separate?

### 25. How should clips be linked to reports?

Questions:

- File paths?
- Spiideo links?
- Wyscout links?
- Shared Drive links?
- Timestamp references only?

## Match-Day and Post-Match Validation

### 26. What should be tracked live on match day?

Proposed live questions:

- Is the opponent using the expected formation?
- Are expected pressing triggers occurring?
- Where are CofC entries coming from?
- Are transition opportunities developing as predicted?
- Has the opponent changed set-piece structure?

Questions:

- Who fills this out?
- Paper, tablet, spreadsheet, or Streamlit?
- What needs to be ready for halftime?

### 27. What does a successful post-match validation look like?

Questions:

- Which pre-match findings appeared?
- Which recommendations worked?
- Which were wrong or irrelevant?
- Did the data help?
- Did the simulation help?
- What changes next week?

### 28. What process metrics should we track?

Proposed metrics:

- Time to ingest data
- Ingestion errors
- Unresolved identifiers
- Time to first opponent profile
- Matches reviewed
- Clips coded
- Findings accepted by coaches
- Findings that appeared in match
- Coach/player feedback

Questions:

- Which of these matter to staff?
- Which are useful for practicum evaluation?

## Recruiting / Similarity Model

### 29. Which position group should be the first recruiting similarity prototype?

Questions:

- Center backs?
- Fullbacks?
- Defensive midfielders?
- Wingers?
- Forwards?
- Goalkeepers?

Why this matters:

- Keeps the first model focused and explainable

### 30. What defines a good tactical fit by position?

Questions:

- Which COUG Table dimensions matter most by position?
- Which Wyscout metrics matter most by position?
- Should the model identify similar current players or ideal role profiles?

### 31. What should the recruiting output look like?

Options:

- Ranked shortlist
- Similarity radar
- Player comparison table
- Role-fit score
- Watchlist report

## Decisions To Capture In Writing

After coach discussion, document:

- Official COUG scoring source of truth
- Official PEAK/ASET/Set Piece rules
- Event outcome handling
- Weekly file handoff process
- Scouting report MVP
- Player-facing versus coach-only boundaries
- Match-day validation workflow
- First recruiting similarity position group
