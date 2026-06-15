"""
main.py
=======
CofC Soccer Analytics — FastAPI Backend
Rewired to pull from Supabase via db.py.
Hardcoded/mock data removed. Endpoints return empty/null shapes
when data isn't available yet (XML pipeline pending).

DO NOT PUSH until XML scores are loaded into Supabase.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import db

app = FastAPI(title="Cougars Analytics API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── PLAYERS ───────────────────────────────────────────────────────────────────

@app.get("/api/players")
def get_players():
    """All active athletes."""
    return db.get_players()


@app.get("/api/player-stats")
def get_player_stats(season: str | None = None):
    """Season stats per player. Event metrics null until XML loads."""
    return db.get_player_season_stats(season)


# ── TEAM LEADERS ──────────────────────────────────────────────────────────────

@app.get("/api/leaders/{metric}")
def get_team_leaders(metric: str, season: str | None = None):
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
def get_team_passing(season: str | None = None):
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
def get_roster_development(season: str | None = None):
    """
    Development targets by position.
    Status will be 'Pending Data' until XML pipeline populates event stats.
    """
    return db.get_roster_development(season)


# ── MATCHES ───────────────────────────────────────────────────────────────────

@app.get("/api/team/matches")
def get_matches(season: str | None = None):
    """Match results from Supabase."""
    return db.get_match_results(season)


@app.get("/api/team/summary")
def get_team_summary(season: str | None = None):
    """Aggregate W/D/L record and goal stats."""
    return db.get_team_summary(season)


# ── COUG SCORES ───────────────────────────────────────────────────────────────

@app.get("/api/coug-scores")
def get_coug_scores(season: str | None = None, session_id: str | None = None):
    """COUG Table scores. Empty until XML pipeline runs."""
    return db.get_coug_scores(session_id=session_id, season=season)


@app.get("/api/coug-leaderboard/{season}")
def get_coug_leaderboard(season: str):
    """Season COUG score leaderboard aggregated across all matches."""
    return db.get_season_coug_leaderboard(season)


# ── SHOTS BY TIME ─────────────────────────────────────────────────────────────

@app.get("/api/team/shots-by-time")
def get_shots_by_time(season: str | None = None):
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
def get_formations(season: str | None = None):
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