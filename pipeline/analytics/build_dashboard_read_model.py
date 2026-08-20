#!/usr/bin/env python3
"""Build a JSON read model for COUG Table and Player Development.

Supabase remains the source of truth. Run this after score/event ingestion so
dashboard requests read one local snapshot instead of rebuilding joins.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import db  # noqa: E402
from backend.read_models import read_model_dir  # noqa: E402


def build_read_model(season: str, weight_version: str = "trial_1") -> dict:
    leaderboard = db.get_season_leaderboard_with_minutes(season, weight_version)
    players = {}
    session_ids = set()

    for player in leaderboard:
        athlete_id = player.get("athlete_id")
        if not athlete_id:
            continue
        history = db.get_player_match_history(athlete_id, season, weight_version)
        session_ids.update(row.get("session_id") for row in history if row.get("session_id"))
        players[athlete_id] = {
            "match_history": history,
            "trace": db.get_player_coug_trace(
                athlete_id=athlete_id,
                season=season,
                weight_version=weight_version,
            ),
        }

    match_scores = {
        session_id: db.get_coug_scores_with_minutes(session_id, weight_version)
        for session_id in sorted(session_ids)
    }
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "season": season,
        "weight_version": weight_version,
        "leaderboard": leaderboard,
        "players": players,
        "match_scores": match_scores,
    }


def validate_read_model(payload: dict, allow_empty: bool = False) -> None:
    if payload.get("schema_version") not in {1, 2} or not payload.get("season"):
        raise ValueError("Invalid dashboard read-model metadata")
    if not allow_empty and not payload.get("leaderboard"):
        raise RuntimeError(
            "Refusing to write an empty dashboard snapshot. Check database "
            "connectivity/data, or pass --allow-empty intentionally."
        )


def _atomic_json_write(payload: dict, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=destination.parent, delete=False, suffix=".tmp"
    ) as handle:
        json.dump(payload, handle, separators=(",", ":"), default=str)
        temporary = Path(handle.name)
    temporary.replace(destination)


def write_read_model(payload: dict, output_dir: Path, allow_empty: bool = False) -> Path:
    validate_read_model(payload, allow_empty=allow_empty)
    output_dir.mkdir(parents=True, exist_ok=True)
    season = payload["season"]
    player_dir = output_dir / f"coug_{season}" / "players"
    player_files = {}
    for athlete_id, player_payload in payload.get("players", {}).items():
        relative_path = Path(f"coug_{season}") / "players" / f"{athlete_id}.json"
        _atomic_json_write(player_payload, output_dir / relative_path)
        player_files[athlete_id] = relative_path.as_posix()

    index_payload = {
        key: value for key, value in payload.items() if key != "players"
    }
    index_payload["schema_version"] = 2
    index_payload["player_files"] = player_files
    destination = output_dir / f"coug_{season}.json"
    # Publish the compact index last so readers never observe missing player files.
    _atomic_json_write(index_payload, destination)
    return destination


def refresh_dashboard_read_model(
    season: str,
    weight_version: str = "trial_1",
    output_dir: Path | None = None,
    allow_empty: bool = False,
) -> Path:
    """Rebuild and atomically publish one season's dashboard read model."""
    payload = build_read_model(season, weight_version)
    return write_read_model(
        payload,
        output_dir or read_model_dir(),
        allow_empty=allow_empty,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", required=True)
    parser.add_argument("--weight-version", default="trial_1")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--allow-empty", action="store_true")
    args = parser.parse_args()

    path = refresh_dashboard_read_model(
        args.season,
        args.weight_version,
        output_dir=args.output_dir,
        allow_empty=args.allow_empty,
    )
    index = json.loads(path.read_text(encoding="utf-8"))
    print(f"Wrote {path} ({len(index.get('player_files', {}))} players)")


if __name__ == "__main__":
    main()
