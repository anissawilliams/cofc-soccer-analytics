"""
Resolve raw source files from local disk or Supabase Storage.

Parsers should receive local Path objects. This module keeps that contract while
allowing Supabase Storage to become the durable source of truth for raw files.
Local files are always preferred; Storage downloads are cached.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from source_paths import get_source_paths


WYSCOUT_FILE_KINDS = {
    "sportscode": "{slug}_cfc_sportscode.xml",
    "effective_time": "{slug}_cfc_effective_time.xml",
    "player_events": "{slug}_cfc_player_events.xml",
    "team_events": "{slug}_cfc_team_events.xml",
}


@dataclass(frozen=True)
class ResolvedSourceFile:
    kind: str
    path: Path
    origin: str
    storage_path: str = ""


def storage_enabled() -> bool:
    load_dotenv()
    return bool(
        os.environ.get("SUPABASE_URL")
        and os.environ.get("SUPABASE_SERVICE_KEY")
        and os.environ.get("COFC_ENABLE_SUPABASE_STORAGE", "").lower() in {"1", "true", "yes"}
    )


def canonical_wyscout_storage_path(season: str, slug: str, kind: str) -> str:
    paths = get_source_paths()
    filename = WYSCOUT_FILE_KINDS[kind].format(slug=slug)
    prefix = paths.source_storage_prefix
    parts = [part for part in [prefix, str(season), slug, "wyscout", filename] if part]
    return "/".join(parts)


def _local_wyscout_path(season: str, slug: str, kind: str) -> Path:
    paths = get_source_paths()
    filename = WYSCOUT_FILE_KINDS[kind].format(slug=slug)
    return paths.matches_dir / str(season) / slug / filename


def _cache_path(storage_path: str) -> Path:
    return get_source_paths().source_cache_dir / storage_path


def _download_from_supabase(storage_path: str) -> Path:
    load_dotenv()
    try:
        from supabase import create_client
    except ImportError as exc:
        raise RuntimeError("Supabase Storage is enabled, but the 'supabase' package is not installed.") from exc

    paths = get_source_paths()
    client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
    payload = client.storage.from_(paths.source_storage_bucket).download(storage_path)
    if isinstance(payload, str):
        payload = payload.encode("utf-8")

    cache_path = _cache_path(storage_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(payload)
    return cache_path


def resolve_wyscout_file(
    season: str,
    slug: str,
    kind: str,
    *,
    required: bool = False,
    allow_storage: bool | None = None,
) -> ResolvedSourceFile | None:
    if kind not in WYSCOUT_FILE_KINDS:
        raise ValueError(f"Unknown Wyscout file kind '{kind}'. Expected one of: {sorted(WYSCOUT_FILE_KINDS)}")

    local_path = _local_wyscout_path(season, slug, kind)
    if local_path.exists():
        return ResolvedSourceFile(kind=kind, path=local_path, origin="local")

    use_storage = storage_enabled() if allow_storage is None else allow_storage
    storage_path = canonical_wyscout_storage_path(season, slug, kind)
    cached_path = _cache_path(storage_path)
    if cached_path.exists():
        return ResolvedSourceFile(kind=kind, path=cached_path, origin="cache", storage_path=storage_path)

    if use_storage:
        try:
            downloaded_path = _download_from_supabase(storage_path)
            return ResolvedSourceFile(kind=kind, path=downloaded_path, origin="supabase_storage", storage_path=storage_path)
        except Exception as exc:
            if required:
                raise FileNotFoundError(
                    f"Could not resolve {kind} for {slug}. Checked local path {local_path} "
                    f"and Supabase Storage path {storage_path}: {exc}"
                ) from exc

    if required:
        raise FileNotFoundError(
            f"Could not resolve {kind} for {slug}. Checked local path {local_path}"
            + (f" and cache/storage path {storage_path}" if use_storage else "")
        )
    return None
