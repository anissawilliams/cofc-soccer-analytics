"""
db.py
=====
Unified Supabase query layer for CofC Soccer Analytics.
Used by both the FastAPI backend (main.py) and Streamlit app.

All functions return plain Python dicts/lists — no Supabase types leak out.
If data isn't in Supabase yet, functions return empty lists or None cleanly.
"""

import os
import re
from pathlib import Path
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

def get_env(key):
    val = os.getenv(key)
    if val:
        return val
    try:
        import streamlit as st
        return st.secrets[key]
    except Exception:
        return None

url = get_env("SUPABASE_URL")
key = get_env("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(url, key)

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


def get_coug_scores_with_minutes(session_id: str) -> list[dict]:
    """
    COUG scores joined with minutes from athlete_session_stint for one match.
    """
    try:
        scores = get_client().table("coug_score").select(
            "id, aset_score, peak_score, set_piece_score, positional_score, "
            "load_score, total_score, calculated_at, "
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


def get_season_leaderboard_with_minutes(season: str) -> list[dict]:
    """
    Season leaderboard — aggregated scores + total minutes across all matches.
    """
    try:
        scores = get_client().table("coug_score").select(
            "aset_score, peak_score, set_piece_score, positional_score, "
            "load_score, total_score, "
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


def get_player_match_history(athlete_id: str, season: str) -> list[dict]:
    """Per-match scores + minutes for a single player, with opponent name."""
    try:
        scores = get_client().table("coug_score").select(
            "aset_score, peak_score, set_piece_score, total_score, "
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
        if metric_ids:
            weight_res = client.table("metric_weight").select(
                "metric_id, weight, weight_type, is_multiplier, version, coach_notes"
            ).eq("version", weight_version).in_("metric_id", metric_ids).execute()
            weights_by_metric = {
                row["metric_id"]: row
                for row in (weight_res.data or [])
            }

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
                "collection_method": row.get("collection_method") or metric.get("collection_method"),
                "manual_tag_required": metric.get("manual_tag_required"),
                "manually_tagged": row.get("manually_tagged"),
                "coach_confirmed": row.get("coach_confirmed") or metric.get("coach_confirmed"),
                "source_name": (row.get("source") or {}).get("name"),
                "source_platform": (row.get("source") or {}).get("platform"),
                "source_type": (row.get("source") or {}).get("source_type"),
                "source_priority": (row.get("source") or {}).get("source_priority"),
                "source_file_path": (row.get("source") or {}).get("file_path"),
                "raw_value_context": row.get("raw_value_context") or {},
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


def _score_bucket(category_code: str | None) -> str:
    return {
        "ASET_DEF": "aset",
        "PEAK_OFF": "peak",
        "SET_PIECE": "set_piece",
        "POSITIONAL": "positional",
        "LOAD": "load",
        "TEAM": "team",
    }.get(category_code or "", "team")


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
