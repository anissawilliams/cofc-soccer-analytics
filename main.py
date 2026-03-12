from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import json

app = FastAPI(title="Cougars Analytics API")

# Ensure CORS is enabled so the React frontend (port 5173) can talk to this API (port 8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Load the mock database generated from cofc_data.py
def load_db():
    try:
        with open('db_ready_schema.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"players": [], "player_stats": []}


db = load_db()


@app.get("/api/players")
def get_players():
    return db.get("players", [])


@app.get("/api/player-stats")
def get_player_stats():
    """Returns all player stats joined with player names."""
    stats = db.get("player_stats", [])
    players = db.get("players", [])

    result = []
    for s in stats:
        player = next((p for p in players if p["player_id"] == s["player_id"]), None)
        if player:
            result.append({
                **s,
                "name": player["name"],
                "position": player["position"]
            })
    return result


@app.get("/api/team/shots-by-time")
def get_shots_by_time():
    """Returns the 15-minute interval data used in the Area Chart"""
    return {
        "labels": ["1-15'", "16-30'", "31-45+'", "46-60'", "61-75'", "76-90+'"],
        "data": [8, 6, 4, 9, 6, 13]
    }


@app.get("/api/leaders/{metric}")
def get_team_leaders(metric: str):
    """Returns ALL players for a specific metric, sorted by value."""
    stats = db.get("player_stats", [])
    players = db.get("players", [])

    try:
        all_data = []
        for s in stats:
            player = next((p for p in players if p["player_id"] == s["player_id"]), None)
            if player and metric in s:
                value = s[metric]
                # Handle null values
                if value is None:
                    value = 0
                all_data.append({
                    "name": player["name"],
                    "fullName": player["name"],
                    "position": player["position"],
                    "value": value
                })

        # Sort the entire roster by the metric (highest first)
        sorted_data = sorted(all_data, key=lambda x: x["value"], reverse=True)
        return sorted_data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/team/passing")
def get_team_passing():
    """
    Returns passing stats for all players.
    Includes: passes, passes_accurate, pass_pct, and per-90 rates.
    """
    stats = db.get("player_stats", [])
    players = db.get("players", [])

    result = []
    for s in stats:
        player = next((p for p in players if p["player_id"] == s["player_id"]), None)
        if not player:
            continue

        mins = s.get("minutes_played", 0)
        passes = s.get("passes", 0)
        passes_accurate = s.get("passes_accurate", 0)
        pass_pct = s.get("pass_pct", 0)

        # Calculate per-90 if we have minutes
        passes_p90 = round((passes / mins) * 90, 1) if mins > 0 else 0

        result.append({
            "name": player["name"],
            "position": player["position"],
            "minutes": mins,
            "passes": passes,
            "passes_accurate": passes_accurate,
            "pass_pct": pass_pct,
            "passes_p90": passes_p90
        })

    # Sort by pass_pct descending (best passers first)
    result = sorted(result, key=lambda x: x["pass_pct"], reverse=True)
    return result


@app.get("/api/roster/development")
def get_roster_development():
    """
    Returns development targets for each player based on position.
    Uses actual pass_pct from the data instead of calculating.
    """
    players = db.get("players", [])
    stats = db.get("player_stats", [])

    development_data = []

    for p in players:
        p_stats = next((s for s in stats if s["player_id"] == p["player_id"]), None)
        if not p_stats:
            continue

        mins = p_stats.get("minutes_played", 0)
        if mins < 50:  # Skip players with very few minutes
            continue

        def p90(val):
            if val is None:
                val = 0
            return round((val / mins) * 90, 2) if mins > 0 else 0

        pos = p["position"]
        targets = {}

        if pos in ["LCB", "RCB", "CB", "LB", "RB"]:
            # Defensive Standards - Recoveries per 90
            rec_p90 = p90(p_stats.get("recoveries", 0))
            targets = {
                "metric": "Recoveries/90",
                "value": rec_p90,
                "goal": 10.0,
                "status": "On Target" if rec_p90 >= 10 else "Developing"
            }
        elif pos in ["DMF", "CMF", "LCMF", "RCMF"]:
            # Midfield Standards - Pass Accuracy (use actual pass_pct)
            pass_acc = p_stats.get("pass_pct", 0)
            targets = {
                "metric": "Pass Accuracy",
                "value": pass_acc,
                "goal": 80.0,
                "status": "On Target" if pass_acc >= 80 else "Developing"
            }
        elif pos in ["LW", "RW", "CF", "AMF"]:
            # Attacking Standards - xG per 90
            xg = p_stats.get("xg", 0) or 0
            xg_p90 = p90(xg)
            targets = {
                "metric": "xG/90",
                "value": xg_p90,
                "goal": 0.25,
                "status": "On Target" if xg_p90 >= 0.25 else "Developing"
            }
        else:
            # Default/GK
            targets = {
                "metric": "Minutes",
                "value": mins,
                "goal": 90,
                "status": "On Target" if mins >= 90 else "Developing"
            }

        development_data.append({
            "name": p["name"],
            "position": pos,
            "minutes": mins,
            # Capitalized keys to match frontend expectations
            "Metric": targets.get("metric", ""),
            "Value": targets.get("value", 0),
            "Goal": targets.get("goal", 0),
            "Status": targets.get("status", "")
        })

    return development_data


@app.get("/api/team/formations")
def get_formations():
    """
    Returns formation performance data.
    Based on actual Wyscout data from the 5-game sample.
    """
    return [
        {
            "name": "5-3-2",
            "usage_pct": 41,
            "goals_for": 3,
            "goals_against": 2,
            "gd": 1,
            "xg_for": 2.39,
            "xg_against": 1.35,
            "possession": 44.59,
            "pass_accuracy": 72.94,
            "ppda": 8.73
        },
        {
            "name": "4-1-3-2",
            "usage_pct": 20,
            "goals_for": 3,
            "goals_against": 1,
            "gd": 2,
            "xg_for": 1.75,
            "xg_against": 2.26,
            "possession": 39.59,
            "pass_accuracy": 70.35,
            "ppda": 6.04
        },
        {
            "name": "4-5-1",
            "usage_pct": 20,
            "goals_for": 0,
            "goals_against": 3,
            "gd": -3,
            "xg_for": 0.64,
            "xg_against": 2.43,
            "possession": 44.8,
            "pass_accuracy": 81.51,
            "ppda": 10.75
        },
        {
            "name": "3-4-3",
            "usage_pct": 20,
            "goals_for": 0,
            "goals_against": 0,
            "gd": 0,
            "xg_for": 0.4,
            "xg_against": 0.53,
            "possession": 46.96,
            "pass_accuracy": 69.91,
            "ppda": 8.03
        }
    ]


@app.get("/api/team/matches")
def get_matches():
    """Returns match results."""
    return [
        {"date": "2025-11-02", "opponent": "UNCW Seahawks", "home": True, "goals_for": 2, "goals_against": 1,
         "result": "W", "competition": "CAA"},
        {"date": "2025-10-25", "opponent": "William & Mary", "home": False, "goals_for": 3, "goals_against": 1,
         "result": "W", "competition": "CAA"},
        {"date": "2025-10-18", "opponent": "Elon Phoenix", "home": True, "goals_for": 0, "goals_against": 0,
         "result": "D", "competition": "CAA"},
        {"date": "2025-10-15", "opponent": "Winthrop Eagles", "home": False, "goals_for": 1, "goals_against": 1,
         "result": "D", "competition": "Non-Conference"},
        {"date": "2025-10-08", "opponent": "North Florida", "home": True, "goals_for": 0, "goals_against": 3,
         "result": "L", "competition": "Non-Conference"},
    ]


@app.get("/api/team/summary")
def get_team_summary():
    """Returns overall team summary stats."""
    matches = get_matches()

    wins = sum(1 for m in matches if m["result"] == "W")
    draws = sum(1 for m in matches if m["result"] == "D")
    losses = sum(1 for m in matches if m["result"] == "L")
    goals_for = sum(m["goals_for"] for m in matches)
    goals_against = sum(m["goals_against"] for m in matches)

    return {
        "matches": len(matches),
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "points": wins * 3 + draws,
        "goals_for": goals_for,
        "goals_against": goals_against,
        "goal_difference": goals_for - goals_against,
        "clean_sheets": sum(1 for m in matches if m["goals_against"] == 0),
        "record": f"{wins}W-{draws}D-{losses}L"
    }