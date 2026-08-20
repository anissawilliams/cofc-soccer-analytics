"""Load compact, reviewed two-team Match Flow snapshots."""

from __future__ import annotations

import json
import os
from pathlib import Path


DEFAULT_MATCH_FLOW_DIR = Path(__file__).resolve().parents[1] / "pipeline" / "data" / "match_flow"


def get_match_flow(
    session_date: str | None,
    home_team: str | None = None,
    away_team: str | None = None,
) -> dict:
    if not session_date:
        return {"available": False, "reason": "match date unavailable"}

    root = Path(os.getenv("COFC_MATCH_FLOW_DIR", str(DEFAULT_MATCH_FLOW_DIR)))
    candidates = sorted(root.glob(f"{session_date}_*.json"))
    if not candidates:
        return {
            "available": False,
            "reason": "paired canonical team events have not been published for this match",
        }

    try:
        payload = json.loads(candidates[0].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"available": False, "reason": "published Match Flow snapshot is invalid"}

    required = {"home_team", "away_team", "bins", "goals", "coverage"}
    if not required.issubset(payload) or not isinstance(payload["bins"], list):
        return {"available": False, "reason": "published Match Flow snapshot is incomplete"}

    if (
        home_team
        and away_team
        and payload["home_team"] == away_team
        and payload["away_team"] == home_team
    ):
        payload["home_team"], payload["away_team"] = home_team, away_team
        payload["bins"] = [
            {**item, "home": item.get("away", 0), "away": item.get("home", 0)}
            for item in payload["bins"]
        ]
    return {"available": True, **payload}
