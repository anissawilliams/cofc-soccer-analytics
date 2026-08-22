"""
db.py
=====
Unified Supabase query layer for CofC Soccer Analytics.
Used by both the FastAPI backend (main.py) and Streamlit app.

All functions return plain Python dicts/lists — no Supabase types leak out.
If data isn't in Supabase yet, functions return empty lists or None cleanly.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from supabase import create_client, Client
from dotenv import load_dotenv
from backend.match_flow import get_match_flow
from backend.shot_map import get_shot_map as load_shot_map

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY")
        if not url or not key:
            raise EnvironmentError(
                "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env"
            )
        _client = create_client(url, key)
    return _client


# ── ATHLETES ─────────────────────────────────────────────────────────────────

def get_players() -> list[dict]:
    """All athletes, ordered by last name."""
    try:
        res = get_client().table("athlete").select(
            "id, first_name, last_name, display_name, position, position_group, status"
        ).eq("status", "active").order("last_name").execute()
        return [
            {
                "player_id":    r["id"],
                "name":         r["display_name"] or f"{r['first_name']} {r['last_name']}",
                "position":     r["position"] or "",
                "position_group": r["position_group"] or "",
            }
            for r in (res.data or [])
        ]
    except Exception as e:
        print(f"[db] get_players error: {e}")
        return []


def get_player_by_id(player_id: str) -> dict | None:
    """Single athlete by UUID."""
    try:
        res = get_client().table("athlete").select("*").eq("id", player_id).single().execute()
        return res.data
    except Exception as e:
        print(f"[db] get_player_by_id error: {e}")
        return None


# ── STAFF SESSION EVENT LOG ──────────────────────────────────────────────────

def _session_event_label(row: dict, opponent: str | None = None) -> str:
    session_type = str(row.get("session_type") or "session").title()
    context = opponent or row.get("competition") or row.get("notes") or "Team session"
    if opponent:
        context = f"vs {opponent}"
    return f"{row.get('session_date') or 'Date pending'} · {session_type} · {context}"


def get_session_event_options(season: str | None = None) -> dict:
    """Return validated form choices without exposing direct database access."""
    client = get_client()
    session_query = client.table("session").select(
        "id, session_date, session_type, season, competition, venue, notes"
    )
    if season:
        session_query = session_query.eq("season", season)
    sessions = session_query.order("session_date", desc=True).execute().data or []
    opponent_by_session = {
        row["session_id"]: row.get("opponent")
        for row in get_match_results(season)
        if row.get("session_id")
    }

    athletes = client.table("athlete").select(
        "id, display_name, first_name, last_name, position, position_group"
    ).eq("status", "active").order("last_name").execute().data or []

    weights = (
        client.table("metric_weight")
        .select(
            "id, weight, version, weight_type, is_multiplier, coach_notes, "
            "metric:metric_id(id, name, applies_to_session_type, "
            "category:category_id(code, label))"
        )
        .eq("version", COUG_TABLE_WEIGHT_VERSION)
        .is_("effective_to", "null")
        .execute()
        .data
        or []
    )

    return {
        "season": season,
        "weight_version": COUG_TABLE_WEIGHT_VERSION,
        "sessions": [
            {
                **row,
                "opponent": opponent_by_session.get(row["id"]),
                "label": _session_event_label(row, opponent_by_session.get(row["id"])),
            }
            for row in sessions
        ],
        "athletes": [
            {
                "id": row["id"],
                "name": row.get("display_name")
                or f"{row.get('first_name', '')} {row.get('last_name', '')}".strip(),
                "position": row.get("position") or "",
                "position_group": row.get("position_group") or "",
            }
            for row in athletes
        ],
        "weights": [
            {
                "id": row["id"],
                "weight": row.get("weight"),
                "version": row.get("version"),
                "weight_type": row.get("weight_type"),
                "is_multiplier": row.get("is_multiplier"),
                "coach_notes": row.get("coach_notes"),
                "metric_id": (row.get("metric") or {}).get("id"),
                "metric_name": (row.get("metric") or {}).get("name"),
                "applies_to_session_type": (row.get("metric") or {}).get("applies_to_session_type"),
                "category_code": ((row.get("metric") or {}).get("category") or {}).get("code"),
                "category_label": ((row.get("metric") or {}).get("category") or {}).get("label"),
            }
            for row in weights
            if row.get("metric")
        ],
    }


def get_session_events(season: str | None = None, limit: int = 50) -> list[dict]:
    query = get_client().table("session_event").select(
        "id, event_type, raw_value, event_time, notes, recorded_by, score_status, created_at, "
        "session:session_id!inner(id, session_date, session_type, season, competition), "
        "athlete:athlete_id(id, display_name, first_name, last_name, position), "
        "metric_weight:metric_weight_id(id, weight, version, metric:metric_id(name, category:category_id(code, label)))"
    ).order("created_at", desc=True)
    if season:
        query = query.eq("session.season", season)
    rows = query.limit(limit).execute().data or []
    result = []
    for row in rows:
        session = row.get("session") or {}
        if season and str(session.get("season")) != str(season):
            continue
        athlete = row.get("athlete") or {}
        weight = row.get("metric_weight") or {}
        metric = weight.get("metric") or {}
        result.append({
            "id": row.get("id"),
            "event_type": row.get("event_type"),
            "raw_value": row.get("raw_value"),
            "event_time": row.get("event_time"),
            "notes": row.get("notes"),
            "recorded_by": row.get("recorded_by"),
            "score_status": row.get("score_status"),
            "created_at": row.get("created_at"),
            "session": session,
            "athlete": {
                **athlete,
                "name": athlete.get("display_name")
                or f"{athlete.get('first_name', '')} {athlete.get('last_name', '')}".strip(),
            } if athlete else None,
            "weight": weight.get("weight"),
            "weight_version": weight.get("version"),
            "metric_name": metric.get("name"),
            "category_code": (metric.get("category") or {}).get("code"),
            "category_label": (metric.get("category") or {}).get("label"),
            "proposed_score": (
                round(float(row.get("raw_value") or 1) * float(weight["weight"]), 4)
                if weight.get("weight") is not None else None
            ),
        })
    return result


def create_session_event(payload: dict) -> dict:
    """Create an informational or weighted event after resolving every FK exactly."""
    client = get_client()
    session_rows = client.table("session").select(
        "id, session_type"
    ).eq("id", payload["session_id"]).execute().data or []
    if len(session_rows) != 1:
        raise ValueError("Select a valid session.")

    athlete_id = payload.get("athlete_id") or None
    weight_id = payload.get("metric_weight_id") or None
    if athlete_id:
        athlete_rows = client.table("athlete").select("id").eq("id", athlete_id).execute().data or []
        if len(athlete_rows) != 1:
            raise ValueError("Select a valid athlete.")

    if weight_id:
        if not athlete_id:
            raise ValueError("A weighted event must be assigned to an athlete.")
        weight_rows = client.table("metric_weight").select(
            "id, version, effective_to, metric:metric_id(applies_to_session_type)"
        ).eq("id", weight_id).execute().data or []
        if len(weight_rows) != 1:
            raise ValueError("Select a valid scoring weight.")
        weight = weight_rows[0]
        if weight.get("version") != COUG_TABLE_WEIGHT_VERSION or weight.get("effective_to"):
            raise ValueError("That scoring weight is not active for the current COUG version.")
        applies_to = (weight.get("metric") or {}).get("applies_to_session_type")
        session_type = session_rows[0].get("session_type")
        if applies_to not in (None, "both", session_type):
            raise ValueError(f"That metric does not apply to a {session_type} session.")

    insert_payload = {
        "session_id": payload["session_id"],
        "athlete_id": athlete_id,
        "event_type": payload["event_type"].strip(),
        "metric_weight_id": weight_id,
        "raw_value": payload.get("raw_value") or 1.0,
        "event_time": payload.get("event_time"),
        "notes": (payload.get("notes") or "").strip() or None,
        "recorded_by": (payload.get("recorded_by") or "Staff portal").strip(),
        "score_status": "pending_review" if weight_id else "informational",
    }
    created = client.table("session_event").insert(insert_payload).execute().data or []
    if len(created) != 1:
        raise RuntimeError("The event could not be saved.")
    return {"id": created[0]["id"], "score_status": insert_payload["score_status"]}


# ── MATCHES ───────────────────────────────────────────────────────────────────

def get_match_results(season: str | None = None) -> list[dict]:
    """
    Match results joined with session and team data.
    Returns CofC perspective: result W/D/L, goals_for, goals_against.
    """
    try:
        query = get_client().table("match").select(
            "id, session_id, result, goals_for, goals_against, "
            "session:session_id(session_date, season, competition, venue), "
            "home_team:home_team_id(name, short_name, is_cofc), "
            "away_team:away_team_id(name, short_name, is_cofc)"
        )
        res = query.execute()

        results = []
        for r in (res.data or []):
            s = r.get("session") or {}
            home = r.get("home_team") or {}
            away = r.get("away_team") or {}

            if season and s.get("season") != season:
                continue

            # Determine opponent from CofC perspective
            if home.get("is_cofc"):
                opponent = away.get("name", "Unknown")
                home_game = True
            else:
                opponent = home.get("name", "Unknown")
                home_game = False

            results.append({
                "match_id":     r["id"],
                "session_id":   r.get("session_id"),
                "date":         s.get("session_date"),
                "season":       s.get("season"),
                "competition":  s.get("competition"),
                "venue":        s.get("venue"),
                "opponent":     opponent,
                "home":         home_game,
                "goals_for":    r.get("goals_for"),
                "goals_against": r.get("goals_against"),
                "result":       r.get("result"),
            })

        return sorted(results, key=lambda x: x["date"] or "", reverse=True)
    except Exception as e:
        print(f"[db] get_match_results error: {e}")
        return []


def get_team_summary(season: str | None = None) -> dict:
    """Aggregate team record and goal stats from match results."""
    matches = get_match_results(season)
    if not matches:
        return {
            "matches": 0, "wins": 0, "draws": 0, "losses": 0,
            "points": 0, "goals_for": 0, "goals_against": 0,
            "goal_difference": 0, "clean_sheets": 0, "record": "0W-0D-0L"
        }

    wins    = sum(1 for m in matches if m["result"] == "W")
    draws   = sum(1 for m in matches if m["result"] == "D")
    losses  = sum(1 for m in matches if m["result"] == "L")
    gf      = sum((m["goals_for"] or 0) for m in matches)
    ga      = sum((m["goals_against"] or 0) for m in matches)

    return {
        "matches":         len(matches),
        "wins":            wins,
        "draws":           draws,
        "losses":          losses,
        "points":          wins * 3 + draws,
        "goals_for":       gf,
        "goals_against":   ga,
        "goal_difference": gf - ga,
        "clean_sheets":    sum(1 for m in matches if (m["goals_against"] or 0) == 0),
        "record":          f"{wins}W-{draws}D-{losses}L"
    }


# ── COUG SCORES ───────────────────────────────────────────────────────────────

def get_coug_scores(session_id: str | None = None, season: str | None = None) -> list[dict]:
    """
    COUG Table scores. Filter by session or season.
    Returns empty list if scores not yet calculated (XML pending).
    """
    try:
        query = get_client().table("coug_score").select(
            "id, aset_score, peak_score, set_piece_score, positional_score, "
            "load_score, total_score, score_type, data_source_path, calculated_at, "
            "athlete:athlete_id(id, display_name, first_name, last_name, position, position_group), "
            "session:session_id(session_date, season, competition)"
        )
        if session_id:
            query = query.eq("session_id", session_id)

        res = query.execute()

        results = []
        for r in (res.data or []):
            s = r.get("session") or {}
            a = r.get("athlete") or {}

            if season and s.get("season") != season:
                continue

            results.append({
                "score_id":       r["id"],
                "athlete_id":     a.get("id"),
                "name":           a.get("display_name") or f"{a.get('first_name','')} {a.get('last_name','')}",
                "position":       a.get("position"),
                "position_group": a.get("position_group"),
                "session_date":   s.get("session_date"),
                "season":         s.get("season"),
                "competition":    s.get("competition"),
                "aset_score":     r.get("aset_score", 0),
                "peak_score":     r.get("peak_score", 0),
                "set_piece_score": r.get("set_piece_score", 0),
                "positional_score": r.get("positional_score", 0),
                "load_score":     r.get("load_score", 0),
                "total_score":    r.get("total_score", 0),
                "score_type":     r.get("score_type"),
                "data_source_path": r.get("data_source_path"),
            })

        return sorted(results, key=lambda x: x["total_score"] or 0, reverse=True)
    except Exception as e:
        print(f"[db] get_coug_scores error: {e}")
        return []


def get_season_coug_leaderboard(season: str) -> list[dict]:
    """
    Aggregate COUG scores across all matches for a season.
    Returns per-player totals sorted by total_score.
    """
    scores = get_coug_scores(season=season)
    if not scores:
        return []

    from collections import defaultdict
    totals: dict = defaultdict(lambda: {
        "name": "", "position": "", "position_group": "",
        "matches": 0, "aset_score": 0, "peak_score": 0,
        "set_piece_score": 0, "positional_score": 0,
        "load_score": 0, "total_score": 0
    })

    for s in scores:
        aid = s["athlete_id"]
        totals[aid]["name"]           = s["name"]
        totals[aid]["position"]       = s["position"]
        totals[aid]["position_group"] = s["position_group"]
        totals[aid]["matches"]        += 1
        totals[aid]["aset_score"]     += s["aset_score"] or 0
        totals[aid]["peak_score"]     += s["peak_score"] or 0
        totals[aid]["set_piece_score"] += s["set_piece_score"] or 0
        totals[aid]["positional_score"] += s["positional_score"] or 0
        totals[aid]["load_score"]     += s["load_score"] or 0
        totals[aid]["total_score"]    += s["total_score"] or 0

    return sorted(totals.values(), key=lambda x: x["total_score"], reverse=True)


# ── PLAYER STATS (from athlete_session_stint + athlete_event) ────────────────

def get_player_season_stats(season: str | None = None) -> list[dict]:
    """
    Per-player season aggregates from athlete_session_stint.
    Minutes played, matches played. Event-level stats come later via XML.
    Returns empty stats shape so frontend doesn't break.
    """
    try:
        query = get_client().table("athlete_session_stint").select(
            "athlete_id, minutes_on, minutes_off, started, participated, "
            "session:session_id(season)"
        )
        res = query.execute()

        from collections import defaultdict
        stats: dict = defaultdict(lambda: {
            "matches_played": 0, "minutes_played": 0, "starts": 0
        })

        for r in (res.data or []):
            s = r.get("session") or {}
            if season and s.get("season") != season:
                continue
            aid = r["athlete_id"]
            mins_on  = r.get("minutes_on") or 0
            mins_off = r.get("minutes_off") or 90
            stats[aid]["matches_played"] += 1
            stats[aid]["minutes_played"] += (mins_off - mins_on)
            if r.get("started"):
                stats[aid]["starts"] += 1

        players = get_players()
        result = []
        for p in players:
            pid = p["player_id"]
            s = stats.get(pid, {})
            result.append({
                **p,
                "matches_played":  s.get("matches_played", 0),
                "minutes_played":  s.get("minutes_played", 0),
                "starts":          s.get("starts", 0),
                # Event stats — null until XML pipeline runs
                "xg":              None,
                "xa":              None,
                "shots_on_target": None,
                "passes":          None,
                "passes_accurate": None,
                "pass_pct":        None,
                "def_duels_won":   None,
                "interceptions":   None,
                "recoveries":      None,
            })

        return result
    except Exception as e:
        print(f"[db] get_player_season_stats error: {e}")
        return []


def get_roster_development(season: str | None = None) -> list[dict]:
    """
    Development targets by position group.
    Returns null values for event-based metrics until XML pipeline runs.
    Targets are defined here — coaches set these, they don't come from DB yet.
    """
    stats = get_player_season_stats(season)
    result = []

    POSITION_TARGETS = {
        # Defenders: recoveries/90
        ("LCB", "RCB", "CB", "LB", "RB"): {
            "metric": "Recoveries/90", "key": "recoveries", "goal": 10.0, "per90": True
        },
        # Midfielders: pass accuracy
        ("DMF", "CMF", "LCMF", "RCMF"): {
            "metric": "Pass Accuracy %", "key": "pass_pct", "goal": 80.0, "per90": False
        },
        # Attackers: xG/90
        ("LW", "RW", "CF", "AMF"): {
            "metric": "xG / 90", "key": "xg", "goal": 0.25, "per90": True
        },
    }

    def get_target(position):
        for positions, target in POSITION_TARGETS.items():
            if position in positions:
                return target
        return {"metric": "Minutes", "key": "minutes_played", "goal": 90, "per90": False}

    for p in stats:
        mins = p.get("minutes_played", 0)
        if mins < 50:
            continue

        pos = p.get("position", "")
        target = get_target(pos)
        raw_val = p.get(target["key"])

        # If data not yet available, show null status
        if raw_val is None:
            result.append({
                "name":     p["name"],
                "position": pos,
                "minutes":  mins,
                "Metric":   target["metric"],
                "Value":    None,
                "Goal":     target["goal"],
                "Status":   "Pending Data",
            })
            continue

        if target["per90"] and mins > 0:
            value = round((raw_val / mins) * 90, 2)
        else:
            value = raw_val

        result.append({
            "name":     p["name"],
            "position": pos,
            "minutes":  mins,
            "Metric":   target["metric"],
            "Value":    value,
            "Goal":     target["goal"],
            "Status":   "On Target" if value >= target["goal"] else "Developing",
        })

    return result


# ── ATHLETE LOAD (Catapult) ───────────────────────────────────────────────────

def get_athlete_load(session_id: str | None = None, athlete_id: str | None = None) -> list[dict]:
    """Catapult GPS load data. Returns empty if not yet ingested."""
    try:
        query = get_client().table("athlete_load").select(
            "*, athlete:athlete_id(display_name, position)"
        )
        if session_id:
            query = query.eq("session_id", session_id)
        if athlete_id:
            query = query.eq("athlete_id", athlete_id)
        res = query.execute()
        return res.data or []
    except Exception as e:
        print(f"[db] get_athlete_load error: {e}")
        return []


# ── New endpoints for CougTable v2 ────────────────────────────────────────────

COUG_TABLE_WEIGHT_VERSION = "trial_1"


def _is_published_match_score(row: dict, weight_version: str) -> bool:
    """Keep the public table on one reviewed match-score definition."""
    return (
        row.get("score_type") == "match"
        and (row.get("weight_version") or {}).get("version") == weight_version
    )


def get_seasons() -> list[str]:
    """Distinct seasons from session table."""
    try:
        res = get_client().table("session").select("season").execute()
        seasons = sorted(set(
            r["season"] for r in (res.data or []) if r.get("season")
        ), reverse=True)
        return seasons
    except Exception as e:
        print(f"[db] get_seasons error: {e}")
        return ["2025"]


def get_coug_scores_with_minutes(
    session_id: str,
    weight_version: str = COUG_TABLE_WEIGHT_VERSION,
) -> list[dict]:
    """
    COUG scores joined with minutes from athlete_session_stint for one match.
    """
    try:
        scores = get_client().table("coug_score").select(
            "id, aset_score, peak_score, set_piece_score, positional_score, "
            "load_score, total_score, calculated_at, score_type, "
            "weight_version:weight_version_id(version), "
            "athlete:athlete_id(id, display_name, first_name, last_name, position, position_group), "
            "session:session_id(session_date, season, competition)"
        ).eq("session_id", session_id).execute()

        stints = get_client().table("athlete_session_stint").select(
            "athlete_id, minutes_on, minutes_off, started"
        ).eq("session_id", session_id).execute()

        stint_map = {
            r["athlete_id"]: r for r in (stints.data or [])
        }

        result = []
        for r in (scores.data or []):
            if not _is_published_match_score(r, weight_version):
                continue
            a = r.get("athlete") or {}
            s = r.get("session") or {}
            stint = stint_map.get(a.get("id"), {})
            minutes = (stint.get("minutes_off", 0) or 0) - (stint.get("minutes_on", 0) or 0)

            result.append({
                "athlete_id":       a.get("id"),
                "name":             a.get("display_name") or f"{a.get('first_name','')} {a.get('last_name','')}",
                "position":         a.get("position"),
                "position_group":   a.get("position_group"),
                "session_date":     s.get("session_date"),
                "competition":      s.get("competition"),
                "aset_score":       r.get("aset_score", 0),
                "peak_score":       r.get("peak_score", 0),
                "set_piece_score":  r.get("set_piece_score", 0),
                "positional_score": r.get("positional_score", 0),
                "load_score":       r.get("load_score", 0),
                "total_score":      r.get("total_score", 0),
                "minutes_played":   minutes,
                "minutes_on":       stint.get("minutes_on", 0),
                "started":          (stint.get("minutes_on") or 0) == 0 and minutes > 0,
            })

        return sorted(result, key=lambda x: x["total_score"] or 0, reverse=True)
    except Exception as e:
        print(f"[db] get_coug_scores_with_minutes error: {e}")
        return []


def get_season_leaderboard_with_minutes(
    season: str,
    weight_version: str = COUG_TABLE_WEIGHT_VERSION,
) -> list[dict]:
    """
    Season leaderboard — aggregated scores + total minutes across all matches.
    """
    try:
        scores = get_client().table("coug_score").select(
            "aset_score, peak_score, set_piece_score, positional_score, "
            "load_score, total_score, score_type, "
            "weight_version:weight_version_id(version), "
            "athlete:athlete_id(id, display_name, first_name, last_name, position, position_group), "
            "session:session_id(season)"
        ).execute()

        stints = get_client().table("athlete_session_stint").select(
            "athlete_id, minutes_on, minutes_off, started, "
            "session:session_id(season)"
        ).execute()

        from collections import defaultdict

        score_totals: dict = defaultdict(lambda: {
            "name": "", "position": "", "position_group": "",
            "matches": 0, "aset_score": 0, "peak_score": 0,
            "set_piece_score": 0, "positional_score": 0,
            "load_score": 0, "total_score": 0,
        })

        for r in (scores.data or []):
            if not _is_published_match_score(r, weight_version):
                continue
            s = r.get("session") or {}
            if s.get("season") != season:
                continue
            a = r.get("athlete") or {}
            aid = a.get("id")
            if not aid:
                continue
            score_totals[aid]["name"]           = a.get("display_name") or f"{a.get('first_name','')} {a.get('last_name','')}".strip()
            score_totals[aid]["position"]       = a.get("position")
            score_totals[aid]["position_group"] = a.get("position_group")
            score_totals[aid]["matches"]        += 1
            score_totals[aid]["aset_score"]     += r.get("aset_score") or 0
            score_totals[aid]["peak_score"]     += r.get("peak_score") or 0
            score_totals[aid]["set_piece_score"] += r.get("set_piece_score") or 0
            score_totals[aid]["positional_score"] += r.get("positional_score") or 0
            score_totals[aid]["load_score"]     += r.get("load_score") or 0
            score_totals[aid]["total_score"]    += r.get("total_score") or 0

        stint_totals: dict = defaultdict(lambda: {"minutes": 0, "starts": 0, "apps": 0})
        for r in (stints.data or []):
            s = r.get("session") or {}
            if s.get("season") != season:
                continue
            aid = r["athlete_id"]
            mins = (r.get("minutes_off") or 0) - (r.get("minutes_on") or 0)
            stint_totals[aid]["minutes"] += mins
            stint_totals[aid]["apps"]    += 1
            if r.get("started"):
                stint_totals[aid]["starts"] += 1

        result = []
        for aid, sc in score_totals.items():
            st = stint_totals.get(aid, {})
            result.append({
                "athlete_id":       aid,
                **sc,
                "minutes_played":   st.get("minutes", 0),
                "starts":           st.get("starts", 0),
                "started":          st.get("starts", 0) > 0,
            })

        return sorted(result, key=lambda x: x["total_score"], reverse=True)
    except Exception as e:
        print(f"[db] get_season_leaderboard_with_minutes error: {e}")
        return []


def get_player_match_history(
    athlete_id: str,
    season: str,
    weight_version: str = COUG_TABLE_WEIGHT_VERSION,
) -> list[dict]:
    """Per-match scores + minutes for a single player, with opponent name."""
    try:
        scores = get_client().table("coug_score").select(
            "aset_score, peak_score, set_piece_score, total_score, score_type, "
            "weight_version:weight_version_id(version), "
            "session:session_id(id, session_date, season, competition)"
        ).eq("athlete_id", athlete_id).execute()

        stints = get_client().table("athlete_session_stint").select(
            "session_id, minutes_on, minutes_off, started"
        ).eq("athlete_id", athlete_id).execute()

        # Get match data to find opponents
        matches = get_client().table("match").select(
            "session_id, result, goals_for, goals_against, "
            "home_team:home_team_id(name, short_name, is_cofc), "
            "away_team:away_team_id(name, short_name, is_cofc)"
        ).execute()

        # Build session_id → opponent name map
        match_map = {}
        for m in (matches.data or []):
            home = m.get("home_team") or {}
            away = m.get("away_team") or {}
            if home.get("is_cofc"):
                opponent = away.get("short_name") or away.get("name") or "Unknown"
            else:
                opponent = home.get("short_name") or home.get("name") or "Unknown"
            match_map[m["session_id"]] = {
                "opponent": opponent,
                "result":   m.get("result"),
                "goals_for": m.get("goals_for"),
                "goals_against": m.get("goals_against"),
            }

        stint_map = {r["session_id"]: r for r in (stints.data or [])}

        result = []
        for r in (scores.data or []):
            if not _is_published_match_score(r, weight_version):
                continue
            s = r.get("session") or {}
            if s.get("season") != season:
                continue
            sid     = s.get("id")
            stint   = stint_map.get(sid, {})
            match   = match_map.get(sid, {})
            mins_on  = stint.get("minutes_on") or 0
            mins_off = stint.get("minutes_off") or 0
            minutes  = mins_off - mins_on

            result.append({
                "session_id":      sid,
                "session_date":    s.get("session_date"),
                "opponent":        match.get("opponent", s.get("competition", "Unknown")),
                "result":          match.get("result"),
                "goals_for":       match.get("goals_for"),
                "goals_against":   match.get("goals_against"),
                "aset_score":      r.get("aset_score", 0),
                "peak_score":      r.get("peak_score", 0),
                "set_piece_score": r.get("set_piece_score", 0),
                "total_score":     r.get("total_score", 0),
                "minutes_played":  minutes,
                "minutes_on":      mins_on,
                "started":         mins_on == 0 and minutes > 0,
            })

        return sorted(result, key=lambda x: x["session_date"] or "", reverse=True)
    except Exception as e:
        print(f"[db] get_player_match_history error: {e}")
        return []


def get_player_coug_trace(
    athlete_id: str,
    season: str = "2025",
    session_id: str | None = None,
    weight_version: str = "trial_1",
) -> dict:
    """
    Player-level COUG score explainability.
    Returns the event rows that contributed to ASET/PEAK/Set Piece scores,
    joined with metric definitions, weights, source metadata, and category totals.
    """
    empty = {
        "athlete_id": athlete_id,
        "season": season,
        "session_id": session_id,
        "weight_version": weight_version,
        "player": None,
        "summary": {
            "event_count": 0,
            "weighted_event_count": 0,
            "aset": 0,
            "peak": 0,
            "set_piece": 0,
            "positional": 0,
            "load": 0,
            "team": 0,
            "total": 0,
        },
        "events": [],
        "score_rules": COUG_SCORE_RULES,
    }

    try:
        client = get_client()
        player = get_player_by_id(athlete_id)

        event_query = client.table("athlete_event").select(
            "id, raw_value, raw_value_context, collection_method, manually_tagged, "
            "coach_confirmed, tag_notes, event_time, created_at, session_id, "
            "session:session_id(id, session_date, season, competition), "
            "metric:metric_id(id, name, peak_phase, aset_letter, collection_method, "
            "manual_tag_required, coach_confirmed, notes, category:category_id(code, label)), "
            "source:source_id(name, platform, source_type, source_priority, file_path)"
        ).eq("athlete_id", athlete_id)

        if session_id:
            event_query = event_query.eq("session_id", session_id)

        event_res = event_query.execute()
        raw_events = event_res.data or []

        metric_ids = sorted({
            (row.get("metric") or {}).get("id")
            for row in raw_events
            if (row.get("metric") or {}).get("id")
        })

        weights_by_metric = {}
        rules_by_metric = {}
        rules_by_metric_source = {}
        if metric_ids:
            weight_res = client.table("metric_weight").select(
                "metric_id, weight, weight_type, is_multiplier, version, coach_notes"
            ).eq("version", weight_version).in_("metric_id", metric_ids).execute()
            weights_by_metric = {
                row["metric_id"]: row
                for row in (weight_res.data or [])
            }
            try:
                rule_res = client.table("metric_scoring_rule").select(
                    "metric_id, source_platform, source_event_label, outcome_rule, "
                    "eligible_positions, excluded_positions, minimum_event_count, "
                    "aggregation_rule, raw_value_per_event, review_status, "
                    "relationship_type, related_metric_id, coach_explanation, "
                    "technical_notes"
                ).eq("is_active", True).is_("effective_to", "null").in_(
                    "metric_id", metric_ids
                ).execute()
                rules_by_metric = {
                    row["metric_id"]: row
                    for row in (rule_res.data or [])
                }
                rules_by_metric_source = {
                    (row["metric_id"], row.get("source_event_label")): row
                    for row in (rule_res.data or [])
                    if row.get("source_event_label")
                }
            except Exception:
                # Backward-compatible until the schema migration is applied.
                rules_by_metric = {}
                rules_by_metric_source = {}

        summary = empty["summary"].copy()
        events = []

        for row in raw_events:
            session = row.get("session") or {}
            if season and session.get("season") != season:
                continue

            metric = row.get("metric") or {}
            category = metric.get("category") or {}
            metric_id = metric.get("id")
            weight = weights_by_metric.get(metric_id, {})
            raw_value_context = row.get("raw_value_context") or {}
            source_event_label = raw_value_context.get("wyscout_label")
            scoring_rule = rules_by_metric_source.get(
                (metric_id, source_event_label)
            ) or rules_by_metric.get(metric_id, {})
            raw_value = row.get("raw_value")
            raw_value = 1 if raw_value is None else raw_value
            weight_value = weight.get("weight")
            weight_source = "metric_weight" if weight_value is not None else None
            if weight_value is None:
                weight_value = _extract_weight_from_notes(metric.get("notes"))
                weight_source = "metric_definition.notes" if weight_value is not None else None
            calculated_score = None
            if weight_value is not None:
                calculated_score = round(float(raw_value) * float(weight_value), 4)

            bucket = _score_bucket(category.get("code"))
            if calculated_score is not None:
                summary[bucket] = round(summary.get(bucket, 0) + calculated_score, 4)
                summary["total"] = round(summary["total"] + calculated_score, 4)
                summary["weighted_event_count"] += 1

            summary["event_count"] += 1

            events.append({
                "event_id": row.get("id"),
                "session_id": row.get("session_id"),
                "session_date": session.get("session_date"),
                "competition": session.get("competition"),
                "event_time": row.get("event_time"),
                "metric_name": metric.get("name"),
                "category_code": category.get("code"),
                "category_label": category.get("label"),
                "score_bucket": bucket,
                "aset_letter": metric.get("aset_letter"),
                "peak_phase": metric.get("peak_phase"),
                "raw_value": raw_value,
                "weight": weight_value,
                "weight_source": weight_source,
                "calculated_score": calculated_score,
                "weight_type": weight.get("weight_type"),
                "is_multiplier": weight.get("is_multiplier"),
                "weight_notes": weight.get("coach_notes"),
                "metric_notes": metric.get("notes"),
                "coach_explanation": scoring_rule.get("coach_explanation"),
                "technical_notes": scoring_rule.get("technical_notes"),
                "review_status": scoring_rule.get("review_status"),
                "relationship_type": scoring_rule.get("relationship_type"),
                "related_metric_id": scoring_rule.get("related_metric_id"),
                "source_event_label": scoring_rule.get("source_event_label"),
                "outcome_rule": scoring_rule.get("outcome_rule"),
                "eligible_positions": scoring_rule.get("eligible_positions") or [],
                "excluded_positions": scoring_rule.get("excluded_positions") or [],
                "minimum_event_count": scoring_rule.get("minimum_event_count"),
                "aggregation_rule": scoring_rule.get("aggregation_rule"),
                "collection_method": row.get("collection_method") or metric.get("collection_method"),
                "manual_tag_required": metric.get("manual_tag_required"),
                "manually_tagged": row.get("manually_tagged"),
                "coach_confirmed": row.get("coach_confirmed") or metric.get("coach_confirmed"),
                "source_name": (row.get("source") or {}).get("name"),
                "source_platform": (row.get("source") or {}).get("platform"),
                "source_type": (row.get("source") or {}).get("source_type"),
                "source_priority": (row.get("source") or {}).get("source_priority"),
                "source_file_path": (row.get("source") or {}).get("file_path"),
                "raw_value_context": raw_value_context,
                "tag_notes": row.get("tag_notes"),
            })

        events.sort(key=lambda item: (
            item.get("session_date") or "",
            item.get("event_time") if item.get("event_time") is not None else 999999,
            item.get("metric_name") or "",
        ), reverse=True)

        return {
            **empty,
            "player": _format_player(player),
            "summary": summary,
            "events": events,
        }
    except Exception as e:
        print(f"[db] get_player_coug_trace error: {e}")
        return empty


def get_match_story(session_id: str, weight_version: str = "trial_1") -> dict:
    """Chronological, source-traceable event story for one match session."""
    empty = {
        "session_id": session_id,
        "match": None,
        "flow": {"available": False, "reason": "match metadata unavailable"},
        "summary": {
            "events": 0,
            "players": 0,
            "aset": 0,
            "peak": 0,
            "set_piece": 0,
            "total": 0,
            "published_peak": 0,
            "untimed_peak": 0,
            "peak_coverage_ratio": None,
        },
        "events": [],
    }
    try:
        client = get_client()
        match_rows = (
            client.table("match")
            .select(
                "id, session_id, result, goals_for, goals_against, "
                "session:session_id(session_date, season, competition, venue), "
                "home_team:home_team_id(name, short_name, is_cofc), "
                "away_team:away_team_id(name, short_name, is_cofc)"
            )
            .eq("session_id", session_id)
            .execute()
            .data
            or []
        )
        if len(match_rows) != 1:
            return empty

        match_row = match_rows[0]
        session = match_row.get("session") or {}
        home = match_row.get("home_team") or {}
        away = match_row.get("away_team") or {}
        opponent = away if home.get("is_cofc") else home

        raw_events = (
            client.table("athlete_event")
            .select(
                "id, athlete_id, raw_value, raw_value_context, collection_method, "
                "manually_tagged, coach_confirmed, event_time, "
                "athlete:athlete_id(display_name, first_name, last_name, position, position_group), "
                "metric:metric_id(id, name, peak_phase, aset_letter, category:category_id(code, label)), "
                "source:source_id(name, platform, source_type, source_priority)"
            )
            .eq("session_id", session_id)
            .execute()
            .data
            or []
        )

        metric_ids = sorted({
            (row.get("metric") or {}).get("id") for row in raw_events
            if (row.get("metric") or {}).get("id")
        })
        weights = {}
        if metric_ids:
            weight_rows = (
                client.table("metric_weight")
                .select("metric_id, weight, version")
                .eq("version", weight_version)
                .in_("metric_id", metric_ids)
                .execute()
                .data
                or []
            )
            weights = {row["metric_id"]: row.get("weight") for row in weight_rows}

        events = []
        player_ids = set()
        totals = {"aset": 0.0, "peak": 0.0, "set_piece": 0.0, "total": 0.0}
        for row in raw_events:
            athlete = row.get("athlete") or {}
            metric = row.get("metric") or {}
            category = metric.get("category") or {}
            context = row.get("raw_value_context") or {}
            bucket = _score_bucket(category.get("code"))
            raw_value = 1.0 if row.get("raw_value") is None else float(row.get("raw_value"))
            weight = weights.get(metric.get("id"))
            contribution = round(raw_value * float(weight), 4) if weight is not None else None
            if bucket in totals and contribution is not None:
                totals[bucket] = round(totals[bucket] + contribution, 4)
                totals["total"] = round(totals["total"] + contribution, 4)

            athlete_id = row.get("athlete_id")
            if athlete_id:
                player_ids.add(athlete_id)
            source_time = row.get("event_time")
            match_minute = context.get("match_minute")
            if match_minute is None and source_time is not None:
                match_minute = max(0.0, float(source_time) / 60.0)
            events.append({
                "event_id": row.get("id"),
                "athlete_id": athlete_id,
                "player": athlete.get("display_name") or f"{athlete.get('first_name') or ''} {athlete.get('last_name') or ''}".strip(),
                "position": athlete.get("position"),
                "position_group": athlete.get("position_group"),
                "metric_name": metric.get("name"),
                "category_code": category.get("code"),
                "category_label": category.get("label"),
                "score_bucket": bucket,
                "raw_value": raw_value,
                "weight": weight,
                "contribution": contribution,
                "source_time": source_time,
                "match_minute": round(float(match_minute), 2) if match_minute is not None else None,
                "half": context.get("half"),
                "outcome": context.get("outcome"),
                "labels": context.get("all_labels") or [],
                "source_name": (row.get("source") or {}).get("name"),
                "source_platform": (row.get("source") or {}).get("platform"),
                "collection_method": row.get("collection_method"),
                "coach_confirmed": row.get("coach_confirmed"),
            })

        events.sort(key=lambda event: (
            event.get("match_minute") if event.get("match_minute") is not None else 9999,
            event.get("player") or "",
        ))

        published_peak = 0.0
        try:
            score_rows = (
                client.table("coug_score")
                .select("peak_score, score_type, weight_version:weight_version_id(version)")
                .eq("session_id", session_id)
                .execute()
                .data
                or []
            )
            published_peak = round(sum(
                float(row.get("peak_score") or 0)
                for row in score_rows
                if row.get("score_type") == "match"
                and (row.get("weight_version") or {}).get("version") == weight_version
            ), 4)
        except Exception as exc:
            # Coverage is supplemental. A missing score rollup must not hide the
            # source-traceable event story during a rolling deployment.
            print(f"[db] get_match_story peak coverage error: {exc}")

        peak_coverage = _match_story_peak_coverage(totals["peak"], published_peak)

        return {
            "session_id": session_id,
            "match": {
                "match_id": match_row.get("id"),
                "date": session.get("session_date"),
                "season": session.get("season"),
                "competition": session.get("competition"),
                "venue": session.get("venue"),
                "opponent": opponent.get("name") or "Unknown",
                "home": bool(home.get("is_cofc")),
                "result": match_row.get("result"),
                "goals_for": match_row.get("goals_for"),
                "goals_against": match_row.get("goals_against"),
            },
            "summary": {
                "events": len(events),
                "players": len(player_ids),
                **totals,
                **peak_coverage,
            },
            "flow": get_match_flow(
                session.get("session_date"),
                home.get("name"),
                away.get("name"),
            ),
            "events": events,
        }
    except Exception as exc:
        print(f"[db] get_match_story error: {exc}")
        return empty


def get_match_shot_map(session_id: str) -> dict:
    """Reviewed shot locations and chance quality for one match session."""
    empty = {
        "session_id": session_id,
        "match": None,
        "shot_map": {"available": False, "reason": "match metadata unavailable"},
    }
    try:
        rows = (
            get_client().table("match")
            .select(
                "id, session_id, result, goals_for, goals_against, "
                "session:session_id(session_date, season, competition, venue), "
                "home_team:home_team_id(name, short_name, is_cofc), "
                "away_team:away_team_id(name, short_name, is_cofc)"
            )
            .eq("session_id", session_id)
            .execute()
            .data
            or []
        )
        if len(rows) != 1:
            return empty

        row = rows[0]
        session = row.get("session") or {}
        home = row.get("home_team") or {}
        away = row.get("away_team") or {}
        opponent = away if home.get("is_cofc") else home
        return {
            "session_id": session_id,
            "match": {
                "match_id": row.get("id"),
                "date": session.get("session_date"),
                "season": session.get("season"),
                "competition": session.get("competition"),
                "venue": session.get("venue"),
                "opponent": opponent.get("name") or "Unknown",
                "home": bool(home.get("is_cofc")),
                "result": row.get("result"),
                "goals_for": row.get("goals_for"),
                "goals_against": row.get("goals_against"),
            },
            "shot_map": load_shot_map(
                session.get("session_date"),
                home.get("name"),
                away.get("name"),
                tuple(filter(None, [home.get("short_name")])),
                tuple(filter(None, [away.get("short_name")])),
            ),
        }
    except Exception as exc:
        print(f"[db] get_match_shot_map error: {exc}")
        return empty


def _score_bucket(category_code: str | None) -> str:
    return {
        "ASET_DEF": "aset",
        "PEAK_OFF": "peak",
        "SET_PIECE": "set_piece",
        "POSITIONAL": "positional",
        "LOAD": "load",
        "TEAM": "team",
    }.get(category_code or "", "team")


def _match_story_peak_coverage(timed_peak: float, published_peak: float) -> dict:
    """Compare timestamped PEAK evidence with the published match rollup."""
    timed = round(float(timed_peak or 0), 4)
    published = round(float(published_peak or 0), 4)
    difference = round(published - timed, 4)
    ratio = None if published <= 0 else round(min(timed / published, 1.0), 4)
    return {
        "published_peak": published,
        "untimed_peak": max(difference, 0),
        "peak_coverage_ratio": ratio,
    }


def _format_player(player: dict | None) -> dict | None:
    if not player:
        return None
    return {
        "athlete_id": player.get("id"),
        "name": player.get("display_name") or f"{player.get('first_name','')} {player.get('last_name','')}".strip(),
        "position": player.get("position"),
        "position_group": player.get("position_group"),
    }


def _extract_weight_from_notes(notes: str | None) -> float | None:
    if not notes:
        return None
    match = re.search(r"Weight\s+(-?\d+(?:\.\d+)?)", notes)
    if not match:
        return None
    return float(match.group(1))


COUG_SCORE_RULES = [
    {
        "bucket": "ASET",
        "label": "All in, Sprint, Engage, Trust",
        "events": [
            "Possession Regain",
            "Successful Counter Press (<5s)",
            "Block in Box",
            "Clearance from Danger",
            "Concede Goal (on field)",
        ],
    },
    {
        "bucket": "PEAK",
        "label": "Punish, Establish, Advance, Kill",
        "events": [
            "Punish Action after Regain",
            "Establishing Possession",
            "Advance",
            "Goal (scorer)",
            "Goal (on field)",
            "Assist",
        ],
    },
    {
        "bucket": "Set Piece",
        "label": "Restart-specific credit and penalties",
        "events": [
            "Win 1st Header (offensive)",
            "Win 1st Header (defensive)",
            "Set Piece Goal (1st phase)",
            "Set Piece Goal (2nd phase)",
            "Penalty Save",
            "Freekick Save/Block",
            "Concede from Set Piece (on field)",
        ],
    },
]
