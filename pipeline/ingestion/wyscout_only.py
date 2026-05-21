"""
modes/wyscout_only.py — Mode 1: Wyscout XMLs only
Used for fall 2025 matches where Spiideo is not available.
Ingests player data, minutes, and match metadata.
No COUG attribution — seeds the DB for when Spiideo arrives.
"""

from pathlib import Path

from compress import compress_and_upload, build_blob_path
from parse_wyscout import (
    parse_sportscode,
    parse_effective_time,
    estimate_minutes_played,
)
from write_db import (
    get_or_create_team,
    create_match,
    write_wyscout_player_stats,
)


def run(
    match_dir: Path,
    meta,           # MatchMeta from manifest
    upload_blobs: bool = True,
):
    """
    Mode 1 ingestion — Wyscout XMLs only.
    Finds files by convention in match_dir.
    """
    slug = match_dir.name

    print(f"\n  Mode: Wyscout Only")
    print(f"  Match: {meta.home_team if hasattr(meta,'home_team') else 'CFC'} "
          f"vs {meta.opponent_name} | {meta.date}")

    # ── Find files ────────────────────────────────────────────
    sportscode_file   = match_dir / f"{slug}_cfc_sportscode.xml"
    effective_file    = match_dir / f"{slug}_cfc_effective_time.xml"

    if not sportscode_file.exists():
        raise FileNotFoundError(f"Sportscode XML not found: {sportscode_file}")

    # ── Upload blobs ──────────────────────────────────────────
    wyscout_blob = None
    if upload_blobs and sportscode_file.exists():
        wyscout_blob = compress_and_upload(
            sportscode_file,
            build_blob_path(meta.season, slug, sportscode_file.name)
        )

    # ── Parse ─────────────────────────────────────────────────
    print("\n  Parsing Wyscout Sportscode XML...")
    wyscout_data = parse_sportscode(sportscode_file)

    effective_data = None
    if effective_file.exists():
        print("  Parsing effective time XML...")
        effective_data = parse_effective_time(effective_file)

    # ── Minutes played ────────────────────────────────────────
    minutes_lookup = estimate_minutes_played(wyscout_data["player_events"])

    # ── Resolve teams ─────────────────────────────────────────
    from config import HOME_TEAM_NAME
    home_team_id = get_or_create_team(HOME_TEAM_NAME, "CFC")
    away_team_id = get_or_create_team(meta.opponent_name)

    # ── Determine home/away ───────────────────────────────────
    if meta.home_away == "home":
        home_id, away_id = home_team_id, away_team_id
    else:
        home_id, away_id = away_team_id, home_team_id

    # ── Write match ───────────────────────────────────────────
    match_id = create_match(
        meta=meta,
        home_team_id=home_id,
        away_team_id=away_id,
        wyscout_blob=wyscout_blob,
        spiideo_blob=None,
        spiideo_offset=None,
    )

    # ── Write player stats ────────────────────────────────────
    print("  Writing player records...")
    write_wyscout_player_stats(
        match_id=match_id,
        player_events=wyscout_data["player_events"],
        home_team_id=home_team_id,
        minutes_lookup=minutes_lookup,
    )

    print(f"\n  ✓ Mode 1 complete — match_id: {match_id}")
    print(f"    Players seeded: {len(minutes_lookup)}")
    print(f"    COUG attribution: pending Spiideo data")
    return match_id
