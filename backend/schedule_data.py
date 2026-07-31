"""Read validated, tracked season schedules for API consumers."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _season_config_path(season: str) -> Path:
    return REPO_ROOT / "configs" / "seasons" / f"cofc_{season}.json"


def _as_bool(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def load_api_schedule(season: str) -> list[dict[str, object]]:
    """Load a season's configured schedule and return frontend-safe rows."""
    config_path = _season_config_path(season)
    if not config_path.exists():
        return []
    config = json.loads(config_path.read_text(encoding="utf-8"))
    configured_path = config.get("schedule_path")
    if not configured_path:
        return []

    schedule_path = Path(str(configured_path))
    if not schedule_path.is_absolute():
        schedule_path = REPO_ROOT / schedule_path
    if not schedule_path.exists():
        return []

    matches: list[dict[str, object]] = []
    with schedule_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if str(row.get("season", "")).strip() != str(season):
                continue
            date = str(row.get("match_date", "")).strip()
            opponent = str(row.get("opponent", "")).strip()
            if not date or not opponent:
                continue
            matches.append(
                {
                    "id": f"{date}_{_slug(opponent)}",
                    "season": str(season),
                    "date": date,
                    "opponent": opponent,
                    "short": str(row.get("opponent_short", "")).strip() or opponent,
                    "homeAway": str(row.get("home_away", "")).strip(),
                    "competition": str(row.get("competition", "")).strip(),
                    "conference": _as_bool(row.get("conference_match")),
                    "venue": str(row.get("venue", "")).strip(),
                    "city": str(row.get("city", "")).strip(),
                    "state": str(row.get("state", "")).strip(),
                    "status": str(row.get("match_status", "")).strip(),
                    "opponentTeamId": str(row.get("opponent_team_id", "")).strip() or None,
                }
            )
    return sorted(matches, key=lambda match: (str(match["date"]), str(match["opponent"])))
