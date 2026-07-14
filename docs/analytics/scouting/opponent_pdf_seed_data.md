# Opponent PDF Seed Data

Last updated: 2026-07-14

## Purpose

Until Wyscout access is restored, use the 2025 Wyscout PDFs from CofC matches
against 2026 opponents as seed scouting data. This is not full opponent-history
coverage. It is a structured way to capture what we already know from direct
head-to-heads and make it useful for 2026 opposition reports.

## What This Can Support Now

- Prior head-to-head summary
- Opponent shape/formation observed against CofC
- How the opponent performed against CofC's formation or formation family
- Team stat profile from the match PDF
- Set-piece and shot profile notes if available in the PDF
- Evidence-backed questions for coaches and video review

## What This Cannot Support Yet

- Reliable opponent season trends
- Rolling form
- Opponent performance against many formation types
- Strong predictive modeling against 2026 opponents
- Lineup availability or tactical changes after the 2025 match

## Extraction Target

For each usable Wyscout PDF, extract one row per team-match into a tidy table.
Prefer this column shape:

```text
source_season
source_match_date
source_match_slug
source_file
team
opponent
is_cofc
home_away
competition
team_formation
opponent_formation
team_formation_family
opponent_formation_family
goals_for
goals_against
xg_for
xg_against
shots_for
shots_against
shots_on_target_for
shots_on_target_against
possession_pct
pass_accuracy_pct
recoveries
duels_won
set_piece_shots_for
set_piece_shots_against
notes
```

Use blanks when a PDF does not expose a field. Do not invent values to fill the
table.

## Formation Families

Use these simple families unless coaches give a better taxonomy:

| family | formations |
| --- | --- |
| `back_four` | `4-3-3`, `4-2-3-1`, `4-4-2`, `4-1-4-1` |
| `back_three` | `3-5-2`, `3-4-3`, `5-3-2`, `5-4-1` |
| `diamond` | `4-4-2 diamond`, `4-1-2-1-2` |
| `unknown` | blank, unclear, or not listed |

For CofC-specific scouting, the key comparison is:

```text
How did the opponent perform against a shape similar to ours?
```

That can be answered from seed PDFs when the PDF contains both formations or
when the analyst can confidently enter CofC's formation for that match.

## 2026 Opponents With Likely Immediate Seed Value

Start with repeated opponents and CAA opponents from 2025 where CofC already has
PDFs or parsed reports:

- William & Mary
- UNCW
- Campbell
- Elon

Then add any other 2026 opponents where a 2025 CofC match PDF exists.

## Analyst Rules

- Mark all values as `source_type = wyscout_pdf_seed` in downstream outputs.
- Keep `source_file` populated so each row is traceable.
- Treat seed data as prior evidence, not current-form truth.
- Prefer "unknown" over guessing formations.
- Add a short `notes` value for any manual interpretation.

## Future Upgrade

When Wyscout access returns, add full opponent match histories:

- 2025 full season for each 2026 opponent
- Early 2026 matches as the season unfolds
- Formation faced and formation used
- Rolling 3-match and 5-match features
- Opponent performance by formation family

That upgrade will move the scouting lane from head-to-head seed evidence toward
true opponent profiling.
