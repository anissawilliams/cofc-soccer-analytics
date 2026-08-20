"""Load compact, reviewed Wyscout shot-map snapshots."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path


DEFAULT_SHOT_MAP_DIR = Path(__file__).resolve().parents[1] / "pipeline" / "data" / "shot_maps"
VALID_OUTCOMES = {"goal", "on_goal", "wide", "blocked", "on_post"}
TEAM_ALIASES = {
    "charlestoncougars": "cofc",
    "collegeofcharleston": "cofc",
    "cofc": "cofc",
    "ncwilmington": "uncw",
    "uncw": "uncw",
    "uncwseahawks": "uncw",
}


def _unavailable(reason: str) -> dict:
    return {"available": False, "reason": reason}


def _team_key(name: str | None) -> str:
    normalized = re.sub(r"[^a-z0-9]", "", (name or "").lower())
    return TEAM_ALIASES.get(normalized, normalized)


def _use_requested_team_names(payload: dict, home_team: str, away_team: str) -> dict:
    """Map reviewed snapshot aliases to the canonical names stored in Supabase."""
    requested = {_team_key(home_team): home_team, _team_key(away_team): away_team}
    snapshot_names = (payload["home_team"], payload["away_team"])
    mapping = {name: requested[_team_key(name)] for name in snapshot_names}
    payload["home_team"] = mapping[snapshot_names[0]]
    payload["away_team"] = mapping[snapshot_names[1]]
    payload["shots"] = [
        {**shot, "team": mapping[shot["team"]]}
        for shot in payload["shots"]
    ]
    payload["team_summaries"] = {
        mapping[team]: summary
        for team, summary in payload["team_summaries"].items()
    }
    return payload


def _valid_payload(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    if not {"home_team", "away_team", "shots", "team_summaries", "source"}.issubset(payload):
        return False
    if not isinstance(payload["shots"], list) or not isinstance(payload["team_summaries"], dict):
        return False

    teams = {payload["home_team"], payload["away_team"]}
    if set(payload["team_summaries"]) != teams:
        return False
    shot_ids = set()
    for shot in payload["shots"]:
        if not isinstance(shot, dict) or not {"shot_id", "sequence", "team", "outcome", "minute", "x", "y"}.issubset(shot):
            return False
        if shot["shot_id"] in shot_ids or shot.get("team") not in teams:
            return False
        shot_ids.add(shot["shot_id"])
        if shot.get("outcome") not in VALID_OUTCOMES:
            return False
        try:
            x = float(shot["x"])
            y = float(shot["y"])
            float(shot["minute"])
        except (KeyError, TypeError, ValueError):
            return False
        if not 0 <= x <= 100 or not 0 <= y <= 100:
            return False
    return True


def get_shot_map(
    session_date: str | None,
    home_team: str | None = None,
    away_team: str | None = None,
) -> dict:
    """Return the reviewed snapshot that matches a date and, when known, both teams."""
    if not session_date:
        return _unavailable("match date unavailable")

    root = Path(os.getenv("COFC_SHOT_MAP_DIR", str(DEFAULT_SHOT_MAP_DIR)))
    candidates = sorted(root.glob(f"{session_date}_*.json"))
    if not candidates:
        return _unavailable("reviewed shot locations have not been published for this match")

    requested_teams = {_team_key(home_team), _team_key(away_team)} if home_team and away_team else None
    saw_invalid = False
    for path in candidates:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            saw_invalid = True
            continue
        if not _valid_payload(payload):
            saw_invalid = True
            continue
        payload_teams = {_team_key(payload["home_team"]), _team_key(payload["away_team"])}
        if requested_teams and payload_teams != requested_teams:
            continue

        if home_team and away_team:
            payload = _use_requested_team_names(payload, home_team, away_team)
        return {"available": True, **payload}

    if saw_invalid:
        return _unavailable("published shot-map snapshot is invalid")
    return _unavailable("reviewed shot locations do not match this fixture")
