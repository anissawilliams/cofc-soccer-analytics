"""
write_db.py — All Supabase write operations
Handles players, matches, events, and coug_scores
All writes are idempotent (upsert safe to re-run)
"""

import json
from collections import defaultdict
from typing import Optional

from config import supabase, INGESTION_VERSION, HOME_TEAM_NAME, MIN_MINUTES_PER90


# ── Team lookups ──────────────────────────────────────────────

def get_team_id(name: str) -> Optional[str]:
    """Get team_id by name. Returns None if not found."""
    result = (supabase.table("teams")
              .select("team_id")
              .eq("name", name)
              .execute())
    return result.data[0]["team_id"] if result.data else None


def get_or_create_team(name: str, abbreviation: str = "") -> str:
    """Get or create a team. Returns team_id."""
    existing = get_team_id(name)
    if existing:
        return existing
    result = (supabase.table("teams")
              .insert({"name": name, "abbreviation": abbreviation or name[:4].upper()})
              .execute())
    print(f"  Created team: {name}")
    return result.data[0]["team_id"]


# ── Player lookups ────────────────────────────────────────────

def get_or_create_player(
    name:    str,
    jersey:  str,
    team_id: str
) -> str:
    """
    Get player_id by name + team, or create if not exists.
    Upserts on name + team_id combination.
    """
    result = (supabase.table("players")
              .select("player_id")
              .eq("name", name)
              .eq("team_id", team_id)
              .execute())
    if result.data:
        return result.data[0]["player_id"]

    new = (supabase.table("players")
           .insert({"name": name, "jersey": jersey, "team_id": team_id})
           .execute())
    return new.data[0]["player_id"]


# ── Subtype lookups ───────────────────────────────────────────

_subtype_cache: dict = {}   # avoid repeated DB hits per ingestion run

def get_or_create_subtype(category: str, name: str) -> tuple[str, float]:
    """
    Get subtype_id and weight by category + name.
    Creates unknown subtypes on the fly with weight 1.0.
    Returns (subtype_id, weight).
    """
    cache_key = f"{category}:{name}"
    if cache_key in _subtype_cache:
        return _subtype_cache[cache_key]

    result = (supabase.table("event_subtypes")
              .select("subtype_id, weight")
              .eq("category", category)
              .eq("name", name)
              .execute())

    if result.data:
        val = (result.data[0]["subtype_id"], float(result.data[0]["weight"]))
    else:
        new = (supabase.table("event_subtypes")
               .insert({"category": category, "name": name, "weight": 1.0})
               .execute())
        val = (new.data[0]["subtype_id"], 1.0)
        print(f"  Created new subtype: {category} / {name}")

    _subtype_cache[cache_key] = val
    return val


# ── Match writes ──────────────────────────────────────────────

def create_match(
    meta,           # MatchMeta from manifest
    home_team_id:   str,
    away_team_id:   str,
    wyscout_blob:   Optional[str] = None,
    spiideo_blob:   Optional[str] = None,
    spiideo_offset: Optional[int] = None,
) -> str:
    """
    Insert a match record. Returns match_id.
    Checks for existing match first (idempotent).
    """
    # Check if match already exists for this date + teams
    existing = (supabase.table("matches")
                .select("match_id")
                .eq("date", meta.date)
                .eq("home_team_id", home_team_id)
                .eq("away_team_id", away_team_id)
                .execute())

    if existing.data:
        match_id = existing.data[0]["match_id"]
        print(f"  Match already exists: {match_id} — updating blob paths")
        # Update blob paths if re-ingesting
        supabase.table("matches").update({
            "wyscout_blob_path": wyscout_blob,
            "spiideo_blob_path": spiideo_blob,
            "spiideo_offset":    spiideo_offset,
            "ingestion_version": INGESTION_VERSION,
        }).eq("match_id", match_id).execute()
        return match_id

    row = {
        "date":             meta.date,
        "season":           meta.season,
        "competition":      meta.competition,
        "round":            meta.round,
        "home_team_id":     home_team_id,
        "away_team_id":     away_team_id,
        "home_score":       meta.home_score,
        "away_score":       meta.away_score,
        "wyscout_blob_path": wyscout_blob,
        "spiideo_blob_path": spiideo_blob,
        "spiideo_offset":   spiideo_offset,
        "spiideo_recording_start": meta.spiideo_recording_start,
        "ingestion_version": INGESTION_VERSION,
    }
    result = supabase.table("matches").insert(row).execute()
    match_id = result.data[0]["match_id"]
    print(f"  Created match: {match_id}")
    return match_id


# ── Event + score writes ───────────────────────────────────────

def write_events_and_scores(
    match_id:       str,
    attributed:     list,
    home_team_id:   str,
    minutes_lookup: dict,   # {player_name: minutes_played}
):
    """
    Write attributed events to events table.
    Calculate and upsert coug_scores per player.
    Deletes existing events for this match first (clean re-ingest).
    """
    # Clean existing events for this match (idempotent re-ingest)
    supabase.table("events").delete().eq("match_id", match_id).execute()

    event_rows  = []
    score_accum = defaultdict(lambda: {
        "player_id":      None,
        "aset":           0.0,
        "peak":           0.0,
        "aset_breakdown": defaultdict(float),
        "peak_breakdown": defaultdict(float),
    })

    for ev in attributed:
        subtype_id, weight = get_or_create_subtype(ev["category"], ev["subtype"])

        player_id = None
        outcome   = "Unknown"

        if ev.get("player"):
            p         = ev["player"]
            player_id = get_or_create_player(p["name"], p["jersey"], home_team_id)
            outcome   = p["outcome"]

            # Accumulate weighted scores
            acc = score_accum[player_id]
            acc["player_id"] = player_id
            if ev["category"] == "ASET":
                acc["aset"] += weight
                acc["aset_breakdown"][ev["subtype"]] += weight
            else:
                acc["peak"] += weight
                acc["peak_breakdown"][ev["subtype"]] += weight

        event_rows.append({
            "match_id":            match_id,
            "player_id":           player_id,
            "subtype_id":          subtype_id,
            "timestamp_wyscout":   ev.get("wyscout_t"),
            "timestamp_spiideo":   ev["spiideo_t"],
            "match_minute":        round(ev.get("match_minute", 0), 2),
            "outcome":             outcome,
            "attribution_score":   ev.get("attribution_score", 0),
            "wyscout_labels":      json.dumps(ev["player"]["labels"])
                                   if ev.get("player") else None,
            "spiideo_code":        ev["spiideo_code"],
            "wyscout_player_code": ev["player"]["raw_code"]
                                   if ev.get("player") else None,
        })

    if event_rows:
        supabase.table("events").insert(event_rows).execute()
        print(f"  Inserted {len(event_rows)} events")

    # ── Write coug_scores ─────────────────────────────────────
    score_rows = []
    for player_id, acc in score_accum.items():
        minutes = minutes_lookup.get(player_id, 90.0)
        aset    = round(acc["aset"], 2)
        peak    = round(acc["peak"], 2)
        total   = round(aset + peak, 2)

        def per90(pts):
            return round((pts / minutes) * 90, 4) if minutes >= MIN_MINUTES_PER90 else None

        score_rows.append({
            "match_id":          match_id,
            "player_id":         player_id,
            "season":            "2025",
            "aset_points":       aset,
            "peak_points":       peak,
            "total_points":      total,
            "minutes_played":    minutes,
            "aset_per90":        per90(aset),
            "peak_per90":        per90(peak),
            "total_per90":       per90(total),
            "aset_breakdown":    json.dumps(dict(acc["aset_breakdown"])),
            "peak_breakdown":    json.dumps(dict(acc["peak_breakdown"])),
            "ingestion_version": INGESTION_VERSION,
        })

    if score_rows:
        supabase.table("coug_scores").upsert(
            score_rows,
            on_conflict="match_id,player_id"
        ).execute()
        print(f"  Upserted {len(score_rows)} player COUG scores")


def write_wyscout_player_stats(
    match_id:     str,
    player_events: list,
    home_team_id: str,
    minutes_lookup: dict,
):
    """
    For Wyscout-only mode — write player presence to coug_scores
    with zero COUG points but correct minutes_played.
    This seeds the player roster and minutes data for the season view
    even before Spiideo COUG attribution is available.
    """
    from collections import Counter
    player_counts = Counter()
    player_jerseys = {}

    for ev in player_events:
        player_counts[ev["name"]] += 1
        player_jerseys[ev["name"]] = ev["jersey"]

    rows = []
    for name, count in player_counts.items():
        player_id = get_or_create_player(name, player_jerseys[name], home_team_id)
        minutes   = minutes_lookup.get(name, 90.0)
        rows.append({
            "match_id":          match_id,
            "player_id":         player_id,
            "season":            "2025",
            "aset_points":       0.0,
            "peak_points":       0.0,
            "total_points":      0.0,
            "minutes_played":    minutes,
            "ingestion_version": INGESTION_VERSION,
        })

    if rows:
        supabase.table("coug_scores").upsert(
            rows, on_conflict="match_id,player_id"
        ).execute()
        print(f"  Seeded {len(rows)} player records (Wyscout only mode)")
