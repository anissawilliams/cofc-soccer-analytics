"""
modes/spiideo_only.py — Mode 2: Spiideo only
Used for spring 2026 scrimmages where Wyscout video is not available.
Ingests COUG events as team-level moments without player attribution.
Useful for coaching review and team-level ASET/PEAK trends.
"""

from pathlib import Path

from compress import compress_and_upload, build_blob_path
from parse_spiideo import parse_spiideo
from write_db import get_or_create_team, create_match
from config import supabase, HOME_TEAM_NAME, INGESTION_VERSION
import json


def run(
    match_dir: Path,
    meta,
    upload_blobs: bool = True,
):
    """
    Mode 2 ingestion — Spiideo only.
    Stores COUG moments at team level, no individual attribution.
    """
    slug = match_dir.name

    print(f"\n  Mode: Spiideo Only (scrimmage)")
    print(f"  Match: CFC vs {meta.opponent_name} | {meta.date}")

    # ── Find Spiideo file ─────────────────────────────────────
    spiideo_file = match_dir / f"{slug}_spiideo.xml"
    if not spiideo_file.exists():
        raise FileNotFoundError(f"Spiideo XML not found: {spiideo_file}")

    # ── Upload blob ───────────────────────────────────────────
    spiideo_blob = None
    if upload_blobs:
        spiideo_blob = compress_and_upload(
            spiideo_file,
            build_blob_path(meta.season, slug, spiideo_file.name)
        )

    # ── Parse ─────────────────────────────────────────────────
    print("  Parsing Spiideo XML...")
    spiideo_data = parse_spiideo(spiideo_file)

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
        wyscout_blob=None,
        spiideo_blob=spiideo_blob,
        spiideo_offset=None,
    )

    # ── Write events (team-level, no player attribution) ──────
    from write_db import get_or_create_subtype

    print("  Writing team-level COUG events...")
    event_rows = []
    aset_count = 0
    peak_count = 0

    for ev in spiideo_data["coug_events"]:
        subtype_id, _ = get_or_create_subtype(ev["category"], ev["subtype"])
        event_rows.append({
            "match_id":          match_id,
            "player_id":         None,       # no attribution in this mode
            "subtype_id":        subtype_id,
            "timestamp_spiideo": ev["spiideo_t"],
            "match_minute":      round(ev["spiideo_t"] / 60, 2),  # rough estimate
            "outcome":           "Unknown",
            "attribution_score": 0.0,
            "spiideo_code":      ev["spiideo_code"],
        })
        if ev["category"] == "ASET": aset_count += 1
        else: peak_count += 1

    if event_rows:
        supabase.table("events").insert(event_rows).execute()

    print(f"\n  ✓ Mode 2 complete — match_id: {match_id}")
    print(f"    ASET events: {aset_count}")
    print(f"    PEAK events: {peak_count}")
    print(f"    Player attribution: not available (no Wyscout)")
    return match_id
