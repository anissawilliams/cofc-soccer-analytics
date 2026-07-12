from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = [
    "season",
    "match_date",
    "opponent",
    "home_away",
    "competition",
    "match_status",
]

OPTIONAL_COLUMNS = [
    "opponent_short",
    "conference_match",
    "neutral_site",
    "venue",
    "city",
    "state",
    "notes",
    "wyscout_match_id",
    "wyscout_team_id",
    "opponent_team_id",
]

VALID_HOME_AWAY = {"H", "A", "N"}
VALID_STATUSES = {"scheduled", "completed", "postponed", "cancelled"}


@dataclass(frozen=True)
class ScheduleValidation:
    errors: list[str]
    warnings: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors


def load_schedule(path: str | Path) -> pd.DataFrame:
    schedule = pd.read_csv(path, dtype=str).fillna("")
    schedule.columns = [column.strip() for column in schedule.columns]
    if "match_date" in schedule.columns:
        schedule["match_date"] = pd.to_datetime(schedule["match_date"], errors="coerce")
    for column in ["conference_match", "neutral_site"]:
        if column in schedule.columns:
            schedule[column] = schedule[column].map(_parse_bool)
    return schedule


def validate_schedule(schedule: pd.DataFrame, expected_season: str) -> ScheduleValidation:
    errors: list[str] = []
    warnings: list[str] = []

    missing_required = [column for column in REQUIRED_COLUMNS if column not in schedule.columns]
    if missing_required:
        errors.append(f"Missing required columns: {missing_required}")
        return ScheduleValidation(errors=errors, warnings=warnings)

    missing_optional = [column for column in OPTIONAL_COLUMNS if column not in schedule.columns]
    if missing_optional:
        warnings.append(f"Missing optional columns: {missing_optional}")

    if schedule.empty:
        errors.append("Schedule has no rows.")
        return ScheduleValidation(errors=errors, warnings=warnings)

    invalid_dates = schedule["match_date"].isna()
    if invalid_dates.any():
        errors.append(f"Rows with invalid match_date: {invalid_dates[invalid_dates].index.tolist()}")

    seasons = set(schedule["season"].astype(str).str.strip())
    if seasons != {str(expected_season)}:
        errors.append(f"Expected season {expected_season}; found seasons {sorted(seasons)}")

    invalid_home_away = ~schedule["home_away"].isin(VALID_HOME_AWAY)
    if invalid_home_away.any():
        errors.append(
            "Rows with invalid home_away values: "
            f"{invalid_home_away[invalid_home_away].index.tolist()}"
        )

    invalid_status = ~schedule["match_status"].str.lower().isin(VALID_STATUSES)
    if invalid_status.any():
        errors.append(
            "Rows with invalid match_status values: "
            f"{invalid_status[invalid_status].index.tolist()}"
        )

    missing_opponent = schedule["opponent"].str.strip().eq("")
    if missing_opponent.any():
        errors.append(f"Rows missing opponent: {missing_opponent[missing_opponent].index.tolist()}")

    duplicate_dates = schedule[schedule.duplicated(["match_date"], keep=False)]
    if not duplicate_dates.empty:
        warnings.append(
            "Multiple matches on the same date: "
            f"{duplicate_dates['match_date'].dt.strftime('%Y-%m-%d').tolist()}"
        )

    missing_opponent_ids = _missing_text_mask(schedule, "opponent_team_id")
    populated_wyscout_team_ids = _populated_text_mask(schedule, "wyscout_team_id")
    if len(missing_opponent_ids) and missing_opponent_ids.any():
        warnings.append(
            f"{int(missing_opponent_ids.sum())} rows are missing opponent_team_id. "
            "That is okay now, but fill it before automated opponent joins."
        )
    if (
        len(missing_opponent_ids)
        and missing_opponent_ids.all()
        and len(populated_wyscout_team_ids)
        and populated_wyscout_team_ids.any()
    ):
        warnings.append(
            f"{int(populated_wyscout_team_ids.sum())} rows have wyscout_team_id populated "
            "while opponent_team_id is blank. If those UUIDs are Supabase team ids, move "
            "them to opponent_team_id; if they are Wyscout ids, keep them where they are."
        )

    return ScheduleValidation(errors=errors, warnings=warnings)


def summarize_schedule(schedule: pd.DataFrame) -> dict[str, object]:
    ordered = schedule.sort_values("match_date").reset_index(drop=True)
    return {
        "matches": int(len(ordered)),
        "first_match": _date_string(ordered["match_date"].min()),
        "last_match": _date_string(ordered["match_date"].max()),
        "home_matches": int((ordered["home_away"] == "H").sum()),
        "away_matches": int((ordered["home_away"] == "A").sum()),
        "neutral_matches": int((ordered["home_away"] == "N").sum()),
        "conference_matches": int(ordered.get("conference_match", pd.Series(False)).fillna(False).sum()),
        "exhibitions": int(ordered["competition"].str.lower().eq("exhibition").sum()),
        "scheduled_matches": int(ordered["match_status"].str.lower().eq("scheduled").sum()),
        "rows_with_wyscout_team_id": int(_populated_text_mask(ordered, "wyscout_team_id").sum()),
        "rows_with_opponent_team_id": int(_populated_text_mask(ordered, "opponent_team_id").sum()),
    }


def write_schedule_report(
    schedule: pd.DataFrame,
    validation: ScheduleValidation,
    summary: dict[str, object],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Schedule QA Report",
        "",
        "## Summary",
        "",
        f"- Matches: {summary['matches']}",
        f"- Date range: {summary['first_match']} to {summary['last_match']}",
        f"- Home/Away/Neutral: {summary['home_matches']} / {summary['away_matches']} / {summary['neutral_matches']}",
        f"- Conference matches: {summary['conference_matches']}",
        f"- Exhibitions: {summary['exhibitions']}",
        f"- Scheduled matches: {summary['scheduled_matches']}",
        f"- Rows with Wyscout team ID: {summary['rows_with_wyscout_team_id']}",
        f"- Rows with opponent team ID: {summary['rows_with_opponent_team_id']}",
        "",
        "## Validation",
        "",
        f"- Status: {'PASS' if validation.ok else 'FAIL'}",
    ]

    if validation.errors:
        lines.extend(["", "### Errors", ""])
        lines.extend([f"- {error}" for error in validation.errors])
    if validation.warnings:
        lines.extend(["", "### Warnings", ""])
        lines.extend([f"- {warning}" for warning in validation.warnings])

    lines.extend(["", "## Matches", ""])
    for _, row in schedule.sort_values("match_date").iterrows():
        date_value = _date_string(row["match_date"])
        home_away = row["home_away"]
        opponent = row["opponent"]
        competition = row["competition"]
        venue = row.get("venue", "")
        lines.append(f"- {date_value}: {home_away} vs {opponent} ({competition}) - {venue}")

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _parse_bool(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _date_string(value: object) -> str:
    if pd.isna(value):
        return ""
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def _missing_text_mask(schedule: pd.DataFrame, column: str) -> pd.Series:
    if column not in schedule.columns:
        return pd.Series([], dtype=bool)
    return schedule[column].astype(str).str.strip().eq("")


def _populated_text_mask(schedule: pd.DataFrame, column: str) -> pd.Series:
    if column not in schedule.columns:
        return pd.Series([], dtype=bool)
    return ~_missing_text_mask(schedule, column)
