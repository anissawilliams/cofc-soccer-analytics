"""
modes/full_pipeline.py — Mode 3: Full pipeline
Wyscout + Spiideo both available.
Full COUG attribution — the money mode. Fall 2026 onwards.
"""

from pathlib import Path

from compress import compress_and_upload, build_blob_path
from parse_wyscout import parse_sportscode, parse_effective_time, estimate_minutes_played
from parse_spiideo import parse_spiideo
from attribute import calculate_offset, attribute_players
from write_db import (
    get_or_create_team,
    create_match,
    write_events_and_scores,
)
from config import HOME_TEAM_NAME


def run(
    match_dir:     Path,
    meta,
    upload_blobs:  bool = True,
    manual_offset: int  = None,
):
    """
    Mode 3 ingestion — full Wyscout + Spiideo pipeline.
    Full player attribution and COUG scoring.
    """
    slug = match_dir.name

    print(f"\n  Mode: Full Pipeline")
    print(f"  Match: CFC vs {meta.opponent_name} | {meta.date}")

    # ── Find files ────────────────────────────────────────────
    sportscode_file = match_dir / f"{slug}_cfc_sportscode.xml"
    effective_file  = match_dir / f"{slug}_cfc_effective_time.xml"
    spiideo_file    = match_dir / f"{slug}_spiideo.xml"

    for f in [sportscode_file, spiideo_file]:
        if not f.exists():
            raise FileNotFoundError(f"Required file not found: {f}")

    # ── Upload blobs ──────────────────────────────────────────
    wyscout_blob = None
    spiideo_blob = None
    if upload_blobs:
        print("  Uploading XMLs to blob storage...")
        wyscout_blob = compress_and_upload(
            sportscode_file,
            build_blob_path(meta.season, slug, sportscode_file.name)
        )
        spiideo_blob = compress_and_upload(
            spiideo_file,
            build_blob_path(meta.season, slug, spiideo_file.name)
        )

    # ── Parse ─────────────────────────────────────────────────
    print("  Parsing Wyscout Sportscode XML...")
    wyscout_data = parse_sportscode(sportscode_file)

    if effective_file.exists():
        print("  Parsing effective time XML...")
        parse_effective_time(effective_file)   # stored for future use

    print("  Parsing Spiideo XML...")
    spiideo_data = parse_spiideo(spiideo_file)

    # ── Resolve offset ────────────────────────────────────────
    print("  Resolving timestamp offset...")
    offset = calculate_offset(
        wyscout_halves=wyscout_data["halves"],
        spiideo_all_events=spiideo_data["all_events"],
        spiideo_recording_start=meta.spiideo_recording_start,
        manual_offset=manual_offset,
    )

    # ── Attribute players ─────────────────────────────────────
    print("  Attributing players...")
    first_half_start = wyscout_data["halves"].get("first_start", 2.0)
    attributed = attribute_players(
        coug_events=spiideo_data["coug_events"],
        player_events=wyscout_data["player_events"],
        offset=offset,
        first_half_start=first_half_start,
    )

    # ── Minutes played ────────────────────────────────────────
    minutes_by_name = estimate_minutes_played(wyscout_data["player_events"])

    # ── Resolve teams ─────────────────────────────────────────
    home_team_id = get_or_create_team(HOME_TEAM_NAME, "CFC")
    away_team_id = get_or_create_team(meta.opponent_name)

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
        spiideo_blob=spiideo_blob,
        spiideo_offset=int(offset),
    )

    # ── Write events + scores ─────────────────────────────────
    print("  Writing events and COUG scores...")
    write_events_and_scores(
        match_id=match_id,
        attributed=attributed,
        home_team_id=home_team_id,
        minutes_lookup=minutes_by_name,
    )

    attributed_count = sum(1 for e in attributed if e.get("player"))
    print(f"\n  ✓ Mode 3 complete — match_id: {match_id}")
    print(f"    Offset: {offset:.1f}s")
    print(f"    COUG events attributed: {attributed_count}/{len(attributed)}")
    return match_id
