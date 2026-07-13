from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class OpponentShellPaths:
    match_dir: Path
    executive_brief: Path
    data_profile: Path
    simulation: Path
    set_pieces: Path
    match_day_observation: Path
    post_match_validation: Path
    qa_report: Path


def build_match_slug(row: pd.Series) -> str:
    date_part = pd.Timestamp(row["match_date"]).strftime("%Y-%m-%d")
    opponent_part = _slugify(str(row["opponent"]))
    home_away = str(row.get("home_away", "")).lower()
    return f"{date_part}_{home_away}_{opponent_part}"


def write_opponent_shells(
    schedule: pd.DataFrame,
    output_root: Path,
    org_short_name: str,
) -> list[OpponentShellPaths]:
    paths: list[OpponentShellPaths] = []
    for _, row in schedule.sort_values("match_date").iterrows():
        match_dir = output_root / build_match_slug(row)
        match_dir.mkdir(parents=True, exist_ok=True)
        shell_paths = OpponentShellPaths(
            match_dir=match_dir,
            executive_brief=match_dir / "executive_brief.md",
            data_profile=match_dir / "data_profile.md",
            simulation=match_dir / "simulation.md",
            set_pieces=match_dir / "set_pieces.md",
            match_day_observation=match_dir / "match_day_observation.md",
            post_match_validation=match_dir / "post_match_validation.md",
            qa_report=match_dir / "qa_report.md",
        )

        _write(shell_paths.executive_brief, _executive_brief(row, org_short_name))
        _write(shell_paths.data_profile, _data_profile(row, org_short_name))
        _write(shell_paths.simulation, _simulation(row, org_short_name))
        _write(shell_paths.set_pieces, _set_pieces(row, org_short_name))
        _write(shell_paths.match_day_observation, _match_day_observation(row, org_short_name))
        _write(shell_paths.post_match_validation, _post_match_validation(row, org_short_name))
        _write(shell_paths.qa_report, _qa_report(row, shell_paths))
        paths.append(shell_paths)
    return paths


def _executive_brief(row: pd.Series, org_short_name: str) -> str:
    context = _context(row)
    return f"""# Executive Opposition Brief

## Match Context

- Opponent: {context['opponent']}
- Match date: {context['date']}
- Location: {context['location']}
- Competition: {context['competition']}
- Venue: {context['venue']}
- Opponent team ID: {context['opponent_team_id']}
- Match status: {context['status']}

## Opponent Identity

- Probable formation:
- Alternative formation or defensive shape:
- General style:
- Primary attacking threat:
- Primary defensive strength:
- Primary vulnerability:

## Three Match Priorities

1.
2.
3.

## Three Recognition Cues

1. When ..., expect ...
2. When ..., expect ...
3. When ..., expect ...

## Player-Facing Message

Keep this to three or four major messages.

- Expect:
- Recognize:
- Do:
- Avoid:
- Exploit:

## Coach-Only Notes

-
"""


def _data_profile(row: pd.Series, org_short_name: str) -> str:
    context = _context(row)
    return f"""# Data Profile

Opponent: {context['opponent']}
Match date: {context['date']}

## Opponent Summary

| Metric | Opponent Value | Comparison | Interpretation |
| --- | ---: | ---: | --- |
| Goals per match |  |  |  |
| Expected goals per match |  |  |  |
| Goals conceded per match |  |  |  |
| Expected goals conceded |  |  |  |
| Shots per match |  |  |  |
| Shots conceded per match |  |  |  |
| Possession |  |  |  |
| Field tilt / territory |  |  |  |
| Set-piece shots |  |  |  |
| Transition shots |  |  |  |

## Shot Profile

- Most common shot locations:
- Primary shot-creation method:
- Share from set pieces:
- Share from transition:
- High-value chance pattern:
- Low-value or inefficient pattern:

## Possession and Territory

- Possession profile:
- Field tilt or territory profile:
- Preferred progression side:
- Most active passing combination:
- Primary final-third entry method:

## Data and Video Agreement

### Findings Supported By Both

-
-
-

### Findings Where Data And Video Differ

-
-
-
"""


def _simulation(row: pd.Series, org_short_name: str) -> str:
    context = _context(row)
    return f"""# Simulation and Match Scenarios

Opponent: {context['opponent']}
Match date: {context['date']}

The simulation should identify match conditions that materially improve or
reduce {org_short_name}'s probability of success. It should not be treated as an
exact prediction.

## Baseline Scenario

- Expected {org_short_name} xG:
- Expected opponent xG:
- Estimated win probability:
- Estimated draw probability:
- Estimated loss probability:
- Most common scorelines:

## Scenario A: Reduced Opponent Transition Chances

- Assumption:
- Result:
- Tactical interpretation:

## Scenario B: Increased {org_short_name} Box Entries

- Assumption:
- Result:
- Tactical interpretation:

## Scenario C: Increased Set-Piece Production

- Assumption:
- Result:
- Tactical interpretation:

## Simulation-Based Match Objective

The baseline simulation changes materially in {org_short_name}'s favor when we:

1.
2.
3.
"""


def _set_pieces(row: pd.Series, org_short_name: str) -> str:
    context = _context(row)
    return f"""# Set-Piece Report

Opponent: {context['opponent']}
Match date: {context['date']}

## Opponent Attacking Corners

- Primary delivery type:
- Primary deliverer:
- Starting structure:
- Primary target:
- Secondary target:
- Blockers or screens:
- Second-ball structure:
- Players held back:
- Recommended {org_short_name} response:
- Clips:

## Opponent Defending Corners

- Defensive system:
- Players in zonal line:
- Man-marking assignments:
- Players on posts:
- Players left high:
- Primary vulnerable area:
- Response to screens or late runners:
- Potential {org_short_name} routine:
- Clips:

## Wide Free Kicks

- Delivery tendency:
- Starting structure:
- Primary targets:
- Offside-line behavior:
- Second-ball behavior:
- Recommended response:

## Long Throws

- Primary thrower:
- Target area:
- Primary target:
- Second-ball setup:
- Recommended response:
"""


def _match_day_observation(row: pd.Series, org_short_name: str) -> str:
    context = _context(row)
    return f"""# Match-Day Observation Sheet

Opponent: {context['opponent']}
Match date: {context['date']}
Location: {context['location']}

## Pre-Match Expectations

- Expected opponent formation:
- Expected buildup shape:
- Expected defensive shape:
- Primary threat:
- Primary opportunity:
- Set-piece priority:

## First 15 Minutes

- Opponent formation confirmed:
- Opponent pressing approach:
- {org_short_name} buildup success:
- Opponent progression pattern:
- Key matchup:
- Unexpected change:

## Halftime Notes

### What Is Working?

-
-

### What Is Not Working?

-
-

### Opponent Adjustment

-

### Recommended {org_short_name} Adjustment

1.
2.
3.

## Second-Half Notes

- Opponent substitution impact:
- Formation change:
- Transition pattern:
- Set-piece change:
- Potential final adjustment:
"""


def _post_match_validation(row: pd.Series, org_short_name: str) -> str:
    context = _context(row)
    return f"""# Post-Match Validation

Opponent: {context['opponent']}
Match date: {context['date']}

## Prediction and Observation Review

| Pre-Match Finding | Occurred? | Impact | Evidence | Future Adjustment |
| --- | --- | --- | --- | --- |
|  |  |  |  |  |
|  |  |  |  |  |
|  |  |  |  |  |

## Questions

- Which opponent patterns were correctly identified?
- Which expected patterns did not appear?
- Did the opponent change formation or personnel?
- Which {org_short_name} recommendations worked?
- Which recommendations were ineffective?
- Were the player-facing messages clear?
- Did the video clips accurately represent the patterns?
- Did the data add useful information?
- Did the simulation identify meaningful match conditions?
- What should change in next week's process?

## Process Metrics

- Time required to ingest data:
- Number of ingestion errors:
- Number of unresolved player or team identifiers:
- Time required to produce first opponent profile:
- Total matches reviewed:
- Total clips coded:
- Clips used in player presentation:
- Findings accepted by coaches:
- Findings that appeared during the match:
- Coach feedback:
- Player feedback:
- Report sections not used:
"""


def _qa_report(row: pd.Series, paths: OpponentShellPaths) -> str:
    context = _context(row)
    missing = []
    if not context["opponent_team_id"]:
        missing.append("opponent_team_id")
    return f"""# Opponent Report QA

## Match

- Opponent: {context['opponent']}
- Match date: {context['date']}
- Competition: {context['competition']}
- Location: {context['location']}
- Venue: {context['venue']}
- Opponent team ID: {context['opponent_team_id'] or 'MISSING'}

## Shell Files

- executive_brief.md
- data_profile.md
- simulation.md
- set_pieces.md
- match_day_observation.md
- post_match_validation.md

## Data Readiness

- Schedule context: PASS
- Opponent team ID: {'PASS' if context['opponent_team_id'] else 'MISSING'}
- Historical opponent data: TODO
- Recent lineup evidence: TODO
- Video/tag evidence: TODO
- Simulation baseline: TODO
- Coach review: TODO

## Missing Required Items

{_missing_list(missing)}
"""


def _context(row: pd.Series) -> dict[str, str]:
    home_away = str(row.get("home_away", "")).upper()
    location = {
        "H": "Home",
        "A": "Away",
        "N": "Neutral",
    }.get(home_away, home_away or "Unknown")
    return {
        "opponent": str(row.get("opponent", "")).strip(),
        "date": pd.Timestamp(row["match_date"]).strftime("%Y-%m-%d"),
        "location": location,
        "competition": str(row.get("competition", "")).strip(),
        "venue": str(row.get("venue", "")).strip(),
        "status": str(row.get("match_status", "")).strip(),
        "opponent_team_id": str(row.get("opponent_team_id", "")).strip(),
    }


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _slugify(value: str) -> str:
    value = value.lower().replace("&", "and")
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def _missing_list(items: list[str]) -> str:
    if not items:
        return "- None"
    return "\n".join(f"- {item}" for item in items)
