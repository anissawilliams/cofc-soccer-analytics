# Opposition Report Product Spec

Source template: `Weekly Opposition Analysis and Match Preparation.docx`

This document translates the weekly opposition workflow into buildable pipeline
requirements. The goal is not to automate tactical judgment. The goal is to
automate the repeatable data, QA, reporting, and evidence organization so the
analyst and coaches can spend time deciding what matters.

## North Star

The weekly opposition product should help staff and players know:

- What to expect
- What to recognize
- What to do
- What to avoid
- What to exploit

## Core Deliverables

The Word workflow expects these recurring outputs:

1. Executive opposition brief
2. Probable lineup and personnel report
3. Four-phase tactical analysis
4. Data profile
5. Simulation and match scenarios
6. Set-piece report
7. How We Can Play Them recommendations
8. Player video presentation
9. Coaching video playlist
10. Match-day observation sheet
11. Post-match validation table

## Automation Map

| Report Section | Pipeline Can Generate | Analyst/Coach Must Add | Data Needed |
| --- | --- | --- | --- |
| Executive brief | opponent, date, location, match context, prior results, baseline model summary | three match priorities, recognition cues, tactical tone | 2026 schedule, team IDs, historical match stats |
| Probable lineup | shell table, recent starters if opponent data exists, player IDs if available | likely XI, availability, tactical changes | opponent match reports/events/lineups |
| Four-phase tactical analysis | candidate metrics and timestamp candidates by phase | actual tactical interpretation and clip selection | Wyscout/Spiideo events plus video |
| Data profile | standard team metrics, shot profile, possession, progression, comparisons | which data points matter tactically | Wyscout team/event data, match stats |
| Simulation scenarios | baseline win/draw/loss, xG sensitivity, scenario tables | scenario assumptions and game-plan meaning | 2024/2025 history, opponent data, current form |
| Set-piece report | set-piece counts and candidate timestamps | structure, targets, routines, diagrams | event tags/video, Spiideo/Wyscout set-piece tags |
| How We Can Play Them | structured prompt shell and candidate opportunities | final coaching recommendations | data profile, video review, coach alignment |
| Player video presentation | clip list shell and labels | final 8-12 clips, player-facing language | tagged video clips |
| Coaching playlist | folder structure and candidate clips | deeper evidence selection | video/tagging workflow |
| Match-day observation sheet | prefilled expectations and checklist | live observations | final opposition brief |
| Post-match validation | validation table and process metrics | whether findings appeared and what changes | match data, analyst notes, coach feedback |

## Minimum Viable 2026 Opponent Report

For the first 2026 opponent, build only the complete repeatable cycle:

1. One-page executive brief
2. Probable lineup shell
3. Four-phase tactical summary shell
4. One-page data profile
5. One-page set-piece report shell
6. Three How We Can Play Them recommendations
7. Player-facing clip list
8. Coaching playlist folders
9. Match-day observation sheet
10. Post-match validation table

## Build Order

### Phase 1: Report Shells From Schedule

Use `pipeline/data/schedules/2026_schedule.csv` to generate one folder per
match under:

`pipeline/outputs/reports/scouting/2026/opponents/<match_slug>/`

Each folder should contain:

- `executive_brief.md`
- `data_profile.md`
- `simulation.md`
- `set_pieces.md`
- `match_day_observation.md`
- `post_match_validation.md`
- `qa_report.md`

This phase can run now.

### Phase 2: Historical Baseline

Use 2025, then 2024+2025, to create:

- CofC baseline model
- conference/opponent comparisons where available
- baseline simulation assumptions
- prior head-to-head summaries for repeated opponents

This phase improves as 2024 data is added.

While Wyscout access is unavailable, use existing 2025 CofC-vs-opponent PDFs as
seed evidence for repeated 2026 opponents. See:

`docs/analytics/scouting/opponent_pdf_seed_data.md`

This seed data should be labeled as prior head-to-head evidence, not full
opponent-history coverage.

### Phase 3: Opponent Data Integration

For each opponent, ingest available Wyscout/Spiideo/video data to populate:

- recent match list
- team metrics
- likely lineup evidence
- shot profile
- progression profile
- transition profile
- set-piece profile
- timestamp candidates for analyst review

This requires opponent-specific source files or Wyscout exports.

### Phase 4: Coach-Facing Outputs

Generate polished outputs after analyst and coach review:

- player one-page brief
- coaching report
- playlist manifest
- match-day card
- post-match validation report

The pipeline should version these outputs so pre-match assumptions can be
compared against post-match reality.

## Commands Already Available

Schedule QA:

```bash
.venv/bin/python pipeline/scouting/build_schedule_report.py --org cofc --season 2026
```

2025 baseline match model:

```bash
.venv/bin/python pipeline/scouting/build_match_model.py --org cofc --season 2025
```

## Next Command To Build

The next high-value command is:

```bash
.venv/bin/python pipeline/scouting/build_opponent_shells.py --org cofc --season 2026
```

It should create one structured report folder per scheduled 2026 opponent,
prefilled with schedule context, known team IDs, empty analyst fields, and QA
status.
