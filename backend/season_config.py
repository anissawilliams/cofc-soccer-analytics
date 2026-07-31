"""Shared active-season configuration for the application layer."""

from __future__ import annotations

import json
import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ORG_CONFIG_PATH = REPO_ROOT / "configs" / "organizations" / "cofc.json"


def get_active_season() -> str:
    """Return the environment override or the tracked organization default."""
    override = os.getenv("COFC_ACTIVE_SEASON", "").strip()
    if override:
        return override
    try:
        config = json.loads(ORG_CONFIG_PATH.read_text(encoding="utf-8"))
        active_season = str(config.get("active_season", "")).strip()
        if active_season:
            return active_season
    except (OSError, json.JSONDecodeError):
        pass
    return "2026"


def season_payload(available_seasons: list[str]) -> dict[str, object]:
    """Build a stable API payload with the active season listed first."""
    active_season = get_active_season()
    normalized = {
        str(season).strip()
        for season in available_seasons
        if str(season).strip()
    }
    normalized.add(active_season)
    seasons = sorted(normalized, reverse=True)
    seasons.remove(active_season)
    seasons.insert(0, active_season)
    return {"active_season": active_season, "seasons": seasons}
