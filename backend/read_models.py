"""File-backed read models generated from Supabase for dashboard hot paths."""

from __future__ import annotations

import json
import os
from pathlib import Path
from threading import RLock
from typing import Any


DEFAULT_READ_MODEL_DIR = Path(__file__).resolve().parents[1] / "pipeline" / "outputs" / "read_models"
_file_cache: dict[Path, tuple[int, dict[str, Any]]] = {}
_lock = RLock()


def read_model_dir() -> Path:
    return Path(os.getenv("COFC_READ_MODEL_DIR", DEFAULT_READ_MODEL_DIR)).expanduser()


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        modified_ns = path.stat().st_mtime_ns
        with _lock:
            cached = _file_cache.get(path)
            if cached and cached[0] == modified_ns:
                return cached[1]
        payload = json.loads(path.read_text(encoding="utf-8"))
        with _lock:
            _file_cache[path] = (modified_ns, payload)
        return payload
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def load_season_read_model(season: str) -> dict[str, Any] | None:
    """Load a compact season index once per file version."""
    return _load_json(read_model_dir() / f"coug_{season}.json")


def load_player_read_model(season: str, athlete_id: str) -> dict[str, Any] | None:
    season_model = load_season_read_model(season)
    if not season_model or season_model.get("schema_version") != 2:
        return None
    relative_path = (season_model.get("player_files") or {}).get(athlete_id)
    if not relative_path:
        return None
    base_dir = read_model_dir().resolve()
    path = (base_dir / relative_path).resolve()
    if base_dir not in path.parents:
        return None
    return _load_json(path)


def snapshot_value(season: str, *keys: str) -> Any | None:
    value: Any = load_season_read_model(season)
    remaining_keys = keys
    if (
        value
        and value.get("schema_version") == 2
        and len(keys) >= 2
        and keys[0] == "players"
    ):
        value = load_player_read_model(season, keys[1])
        remaining_keys = keys[2:]
    for key in remaining_keys:
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value
