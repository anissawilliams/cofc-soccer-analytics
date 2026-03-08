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
        # 1. Map stats to include player names
        all_data = []
        for s in stats:
            player = next((p for p in players if p["player_id"] == s["player_id"]), None)
            if player and metric in s:
                all_data.append({
                    "name": player["name"],
                    "fullName": player["name"],
                    "position": player["position"],
                    "value": s[metric]
                })

        # 2. Sort the entire roster by the metric (highest first)
        sorted_data = sorted(all_data, key=lambda x: x["value"], reverse=True)
        return sorted_data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Add this to your main.py

@app.get("/api/roster/development")
def get_roster_development():
    players = db.get("players", [])
    stats = db.get("player_stats", [])

    development_data = []

    for p in players:
        p_stats = next((s for s in stats if s["player_id"] == p["player_id"]), None)
        if not p_stats: continue

        # Calculate Per-90s for fair benchmarking
        mins = p_stats["minutes_played"]

        def p90(val):
            return round((val / mins) * 90, 2) if mins > 0 else 0

        # Position-Specific Benchmarks
        pos = p["position"]
        targets = {}

        if pos in ["LCB", "RCB", "CB", "LB", "RB"]:
            # Defensive Standards
            rec_p90 = p90(p_stats["recoveries"])
            targets = {"Metric": "Recoveries/90", "Value": rec_p90, "Goal": 10.0,
                       "Status": "Target" if rec_p90 >= 10 else "Developing"}
        elif pos in ["DMF", "CMF", "LCMF", "RCMF"]:
            # Midfield Standards
            pass_acc = (p_stats["passes_accurate"] / (p_stats.get("passes", 100))) * 100  # Approx
            targets = {"Metric": "Pass Accuracy", "Value": round(pass_acc, 1), "Goal": 80.0,
                       "Status": "Target" if pass_acc >= 80 else "Developing"}
        else:
            # Attacking Standards (Lenert's group)
            xg_p90 = p90(p_stats["xg"])
            targets = {"Metric": "xG/90", "Value": xg_p90, "Goal": 0.25,
                       "Status": "Target" if xg_p90 >= 0.25 else "Developing"}

        development_data.append({
            "name": p["name"],
            "position": pos,
            "minutes": mins,
            **targets
        })

    return development_data

# Make sure this is exactly /api/team/formations (plural)
@app.get("/api/team/formations")
def get_formations():
    return [
        {"name": "4-3-3", "gd": -1, "minutes": 290},
        {"name": "4-1-3-2", "gd": 2, "minutes": 90},
        {"name": "4-4-2", "gd": 0, "minutes": 70}
    ]