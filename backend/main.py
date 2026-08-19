"""
main.py
=======
CofC Soccer Analytics — FastAPI Backend
Rewired to pull from Supabase via db.py.
Hardcoded/mock data removed. Endpoints return empty/null shapes
when data isn't available yet (XML pipeline pending).

DO NOT PUSH until XML scores are loaded into Supabase.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
import sys
from pathlib import Path
from typing import Optional
sys.path.insert(0, str(Path(__file__).parent.parent))
import db
from backend.schedule_data import load_api_schedule
from backend.season_config import get_active_season, season_payload
from backend.cache import ttl_cached
from backend.read_models import snapshot_value


app = FastAPI(title="Cougars Analytics API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=6)


@app.middleware("http")
async def add_dashboard_cache_headers(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith((
        "/api/coug-leaderboard-with-minutes/",
        "/api/coug-scores-with-minutes",
        "/api/player-match-history/",
        "/api/player-coug-trace/",
    )):
        response.headers["Cache-Control"] = (
            "private, max-age=300, stale-while-revalidate=300"
        )
    return response


# ── PLAYERS ───────────────────────────────────────────────────────────────────

@app.get("/api/players")
def get_players():
    """All active athletes."""
    return db.get_players()


@app.get("/api/player-stats")
def get_player_stats(season: Optional[str] = None):
    """Season stats per player. Event metrics null until XML loads."""
    return db.get_player_season_stats(season)


# ── TEAM LEADERS ──────────────────────────────────────────────────────────────

@app.get("/api/leaders/{metric}")
def get_team_leaders(metric: str, season: Optional[str] = None):
    """
    Players sorted by a given metric.
    Returns empty list if metric data not yet available.
    """
    stats = db.get_player_season_stats(season)
    valid_metrics = [
        "recoveries", "interceptions", "def_duels_won",
        "shots_on_target", "xg", "xa", "passes", "pass_pct",
        "minutes_played", "matches_played"
    ]
    if metric not in valid_metrics:
        raise HTTPException(status_code=400, detail=f"Unknown metric: {metric}. Valid: {valid_metrics}")

    result = []
    for p in stats:
        value = p.get(metric)
        if value is None:
            continue  # Skip players with no data for this metric yet
        result.append({
            "name":     p["name"],
            "position": p["position"],
            "value":    value,
        })

    return sorted(result, key=lambda x: x["value"], reverse=True)


# ── PASSING ───────────────────────────────────────────────────────────────────

@app.get("/api/team/passing")
def get_team_passing(season: Optional[str] = None):
    """Passing stats per player. Null until XML loads."""
    stats = db.get_player_season_stats(season)
    result = []
    for p in stats:
        mins = p.get("minutes_played", 0)
        passes = p.get("passes")
        passes_p90 = None
        if passes is not None and mins and mins > 0:
            passes_p90 = round((passes / mins) * 90, 1)

        result.append({
            "name":            p["name"],
            "position":        p["position"],
            "minutes":         mins,
            "passes":          passes,
            "passes_accurate": p.get("passes_accurate"),
            "pass_pct":        p.get("pass_pct"),
            "passes_p90":      passes_p90,
        })

    return sorted(result, key=lambda x: (x["pass_pct"] or 0), reverse=True)


# ── ROSTER DEVELOPMENT ────────────────────────────────────────────────────────

@app.get("/api/roster/development")
@ttl_cached()
def get_roster_development(season: Optional[str] = None):
    """
    Development targets by position.
    Status will be 'Pending Data' until XML pipeline populates event stats.
    """
    return db.get_roster_development(season)


# ── MATCHES ───────────────────────────────────────────────────────────────────

@app.get("/api/team/matches")
def get_matches(season: Optional[str] = None):
    """Match results from Supabase."""
    return db.get_match_results(season)


@app.get("/api/team/summary")
def get_team_summary(season: Optional[str] = None):
    """Aggregate W/D/L record and goal stats."""
    return db.get_team_summary(season)


# ── COUG SCORES ───────────────────────────────────────────────────────────────

@app.get("/api/coug-scores")
def get_coug_scores(season: Optional[str] = None, session_id: Optional[str] = None):
    """COUG Table scores. Empty until XML pipeline runs."""
    return db.get_coug_scores(session_id=session_id, season=season)


@app.get("/api/coug-leaderboard/{season}")
def get_coug_leaderboard(season: str):
    """Season COUG score leaderboard aggregated across all matches."""
    return db.get_season_coug_leaderboard(season)


# ── SHOTS BY TIME ─────────────────────────────────────────────────────────────

@app.get("/api/team/shots-by-time")
def get_shots_by_time(season: Optional[str] = None):
    """
    15-minute interval shot distribution.
    Returns null data until athlete_event is populated from XML.
    Frontend should handle null gracefully.
    """
    # TODO: calculate from athlete_event once XML loads
    # SELECT event_time bucket, COUNT(*) FROM athlete_event
    # JOIN metric_definition ON metric_id WHERE name = 'Shot' GROUP BY bucket
    return {
        "labels": ["1-15'", "16-30'", "31-45+'", "46-60'", "61-75'", "76-90+'"],
        "data":   [None, None, None, None, None, None],
        "available": False,
        "message": "Shot timing data available after XML pipeline runs"
    }


# ── FORMATIONS ────────────────────────────────────────────────────────────────

@app.get("/api/team/formations")
def get_formations(season: Optional[str] = None):
    """
    Formation performance data.
    Returns empty until formation tracking is added to session/match notes.
    """
    # TODO: add formation field to session table and calculate from match results
    return {
        "available": False,
        "data": [],
        "message": "Formation data available after session notes are structured"
    }


# ── HEALTH ────────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    """Quick connectivity check."""
    try:
        players = db.get_players()
        return {
            "status": "ok",
            "supabase": "connected",
            "players_loaded": len(players),
        }
    except Exception as e:
        return {
            "status": "error",
            "supabase": "disconnected",
            "detail": str(e)
        }


# ── CougTable v2 endpoints ────────────────────────────────────────────────────

@app.get("/api/seasons")
@ttl_cached(300)
def get_seasons():
    """Active season plus distinct seasons available in the database."""
    return season_payload(db.get_seasons())


@app.get("/api/schedule")
def get_schedule(season: Optional[str] = None):
    """Tracked season schedule used by staff-facing application views."""
    selected_season = season or get_active_season()
    return {
        "season": selected_season,
        "matches": load_api_schedule(selected_season),
    }


@app.get("/api/coug-scores-with-minutes")
@ttl_cached()
def get_coug_scores_with_minutes(session_id: str, season: Optional[str] = None):
    """COUG scores + minutes for a single match."""
    if season:
        snapshot = snapshot_value(season, "match_scores", session_id)
        if snapshot is not None:
            return snapshot
    return db.get_coug_scores_with_minutes(session_id)


@app.get("/api/match-story/{session_id}")
def get_match_story(session_id: str, weight_version: str = "trial_1"):
    """Chronological player-event story for one match session."""
    return db.get_match_story(session_id, weight_version)


@app.get("/api/coug-leaderboard-with-minutes/{season}")
@ttl_cached()
def get_coug_leaderboard_with_minutes(season: str):
    """Season leaderboard with aggregated scores and total minutes."""
    snapshot = snapshot_value(season, "leaderboard")
    if snapshot is not None:
        return snapshot
    return db.get_season_leaderboard_with_minutes(season)


@app.get("/api/player-match-history/{athlete_id}")
@ttl_cached()
def get_player_match_history(athlete_id: str, season: Optional[str] = None):
    """Per-match score + minutes history for a single player."""
    selected_season = season or get_active_season()
    snapshot = snapshot_value(selected_season, "players", athlete_id, "match_history")
    if snapshot is not None:
        return snapshot
    return db.get_player_match_history(athlete_id, selected_season)


@app.get("/api/player-coug-trace/{athlete_id}")
@ttl_cached()
def get_player_coug_trace(
    athlete_id: str,
    season: str = "2025",
    session_id: Optional[str] = None,
    weight_version: str = "trial_1",
):
    """Player-level COUG event ledger with scoring weights and source traceability."""
    if session_id is None:
        snapshot = snapshot_value(season, "players", athlete_id, "trace")
        if snapshot is not None and snapshot.get("weight_version") == weight_version:
            return snapshot
    return db.get_player_coug_trace(
        athlete_id=athlete_id,
        season=season,
        session_id=session_id,
        weight_version=weight_version,
    )
