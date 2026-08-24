"""Load compact, reviewed two-team Match Flow snapshots."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


DEFAULT_MATCH_FLOW_DIR = Path(__file__).resolve().parents[1] / "pipeline" / "data" / "match_flow"


def normalize_match_flow(
    payload: object,
    home_team: str | None = None,
    away_team: str | None = None,
) -> dict:
    required = {"home_team", "away_team", "bins", "goals", "coverage"}
    if not isinstance(payload, dict) or not required.issubset(payload) or not isinstance(payload["bins"], list):
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


def _stored_match_flow(client, session_id: str) -> tuple[dict | None, bool]:
    """Read the latest staff-promoted Match Flow artifact from Supabase Storage."""
    try:
        rows = (
            client.table("source_file")
            .select("storage_bucket,storage_path,sha256")
            .eq("session_id", session_id)
            .eq("source_type", "match_flow")
            .eq("is_active", True)
            .order("created_at", desc=True)
            .limit(5)
            .execute()
            .data
            or []
        )
    except Exception:
        return None, False

    saw_invalid = False
    for row in rows:
        try:
            content = client.storage.from_(row["storage_bucket"]).download(row["storage_path"])
            if row.get("sha256") and hashlib.sha256(content).hexdigest() != row["sha256"]:
                saw_invalid = True
                continue
            return json.loads(content.decode("utf-8")), saw_invalid
        except Exception:
            saw_invalid = True
    return None, saw_invalid


def get_match_flow(
    session_date: str | None,
    home_team: str | None = None,
    away_team: str | None = None,
    *,
    client=None,
    session_id: str | None = None,
) -> dict:
    if not session_date:
        return {"available": False, "reason": "match date unavailable"}

    root = Path(os.getenv("COFC_MATCH_FLOW_DIR", str(DEFAULT_MATCH_FLOW_DIR)))
    candidates = sorted(root.glob(f"{session_date}_*.json"))
    for path in candidates:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        normalized = normalize_match_flow(payload, home_team, away_team)
        if normalized["available"]:
            return normalized

    if client is not None and session_id:
        payload, saw_invalid = _stored_match_flow(client, session_id)
        if payload is not None:
            return normalize_match_flow(payload, home_team, away_team)
        if saw_invalid:
            return {"available": False, "reason": "published Match Flow snapshot is invalid"}

    return {
        "available": False,
        "reason": "paired canonical team events have not been published for this match",
    }
