from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


PAGE_SIZE = 1000
DEFAULT_CONFIG = REPO_ROOT / "configs" / "organizations" / "cofc_recruiting.json"
DEFAULT_SCHEMA = REPO_ROOT / "pipeline" / "config" / "recruiting_player_profile_schema.csv"
DEFAULT_OUTPUT = REPO_ROOT / "pipeline" / "data" / "recruiting" / "internal_player_profiles.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export internal CofC recruiting profiles from Supabase.")
    parser.add_argument("--season", default="2025", help="Season to aggregate from Supabase sessions.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--include-inactive", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = read_json(args.config)
    schema_columns = pd.read_csv(args.schema)["column"].tolist()
    client = get_client()

    athletes = fetch_all(client, "athlete")
    sessions = fetch_all(client, "session")
    stints = fetch_all(client, "athlete_session_stint")
    scores = fetch_all(client, "coug_score")

    profiles = build_profiles(
        athletes=athletes,
        sessions=sessions,
        stints=stints,
        scores=scores,
        season=str(args.season),
        config=config,
        include_inactive=args.include_inactive,
    )
    profiles = profiles.reindex(columns=schema_columns)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    profiles.to_csv(args.output, index=False)

    print(f"Exported internal recruiting profiles: {len(profiles)} rows")
    print(f"Season: {args.season}")
    print(f"Output: {args.output}")


def get_client():
    try:
        from supabase import create_client
    except ImportError as exc:
        raise SystemExit(
            "Missing Python package 'supabase'. Install project dependencies before running this export."
        ) from exc

    load_dotenv()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise EnvironmentError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")
    return create_client(url, key)


def fetch_all(client, table_name: str) -> pd.DataFrame:
    rows = []
    start = 0
    while True:
        response = client.table(table_name).select("*").range(start, start + PAGE_SIZE - 1).execute()
        batch = response.data or []
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        start += PAGE_SIZE
    return pd.DataFrame(rows)


def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def build_profiles(
    athletes: pd.DataFrame,
    sessions: pd.DataFrame,
    stints: pd.DataFrame,
    scores: pd.DataFrame,
    season: str,
    config: dict,
    include_inactive: bool,
) -> pd.DataFrame:
    if athletes.empty:
        return pd.DataFrame()

    athletes = athletes.copy()
    if not include_inactive and "status" in athletes.columns:
        athletes = athletes[athletes["status"].fillna("active").astype(str).str.lower().eq("active")]

    season_sessions = sessions[sessions["season"].astype(str).eq(str(season))].copy()
    session_ids = set(season_sessions["id"].astype(str)) if not season_sessions.empty else set()

    minutes_by_athlete, matches_by_athlete = aggregate_minutes(stints, session_ids)
    score_by_athlete = aggregate_scores(scores, session_ids)

    rows = []
    for _, athlete in athletes.iterrows():
        athlete_id = str(athlete.get("id", ""))
        minutes = float(minutes_by_athlete.get(athlete_id, 0.0))
        matches = int(matches_by_athlete.get(athlete_id, 0))
        score_row = score_by_athlete.get(athlete_id, {})
        position = clean_text(athlete.get("position"))
        raw_position_group = clean_text(athlete.get("position_group"))
        normalized_group = normalize_position_group(position, raw_position_group, config)
        notes = []
        if raw_position_group and raw_position_group != normalized_group:
            notes.append(f"position_group normalized from `{raw_position_group}`")
        if not minutes:
            notes.append(f"no recorded minutes for season {season}")

        rows.append({
            "player_id": athlete_id,
            "player_name": display_name(athlete),
            "source_system": "supabase_internal",
            "source_file": "",
            "season": season,
            "team": config.get("program_name", "College of Charleston Men's Soccer"),
            "competition": "",
            "country": clean_text(athlete.get("nationality")),
            "date_of_birth": clean_text(athlete.get("dob")),
            "age": "",
            "primary_position": position or raw_position_group,
            "secondary_positions": "",
            "position_group": normalized_group,
            "dominant_foot": "",
            "height_cm": "",
            "minutes": round(minutes, 3),
            "matches": matches,
            "aset_per90": per90(score_row.get("aset_score", 0.0), minutes),
            "peak_per90": per90(score_row.get("peak_score", 0.0), minutes),
            "set_piece_per90": per90(score_row.get("set_piece_score", 0.0), minutes),
            "coug_total_per90": per90(score_row.get("total_score", 0.0), minutes),
            "notes": "; ".join(notes),
        })

    return pd.DataFrame(rows).sort_values(["position_group", "player_name"]).reset_index(drop=True)


def aggregate_minutes(stints: pd.DataFrame, session_ids: set[str]) -> tuple[dict[str, float], dict[str, int]]:
    if stints.empty or not session_ids:
        return {}, {}
    df = stints[stints["session_id"].astype(str).isin(session_ids)].copy()
    if df.empty:
        return {}, {}
    df["minutes_on"] = pd.to_numeric(df.get("minutes_on"), errors="coerce").fillna(0.0)
    df["minutes_off"] = pd.to_numeric(df.get("minutes_off"), errors="coerce").fillna(90.0)
    df["minutes"] = (df["minutes_off"] - df["minutes_on"]).clip(lower=0.0)
    if "participated" in df.columns:
        df = df[df["participated"].fillna(True).astype(bool)]
    minutes = df.groupby("athlete_id")["minutes"].sum().to_dict()
    matches = df.groupby("athlete_id")["session_id"].nunique().to_dict()
    return {str(k): float(v) for k, v in minutes.items()}, {str(k): int(v) for k, v in matches.items()}


def aggregate_scores(scores: pd.DataFrame, session_ids: set[str]) -> dict[str, dict[str, float]]:
    if scores.empty or not session_ids:
        return {}
    df = scores[scores["session_id"].astype(str).isin(session_ids)].copy()
    if df.empty:
        return {}
    score_cols = ["aset_score", "peak_score", "set_piece_score", "total_score"]
    for col in score_cols:
        df[col] = pd.to_numeric(df.get(col), errors="coerce").fillna(0.0)
    grouped = df.groupby("athlete_id")[score_cols].sum().reset_index()
    return {
        str(row["athlete_id"]): {col: float(row[col]) for col in score_cols}
        for _, row in grouped.iterrows()
    }


def normalize_position_group(position: str, raw_group: str, config: dict) -> str:
    value = clean_text(position) or clean_text(raw_group)
    value_lower = value.lower()
    for group, payload in config.get("position_groups", {}).items():
        labels = [str(label).lower() for label in payload.get("labels", [])]
        if value_lower in labels:
            return group
    position_tokens = {
        token.strip().upper()
        for token in value.replace("-", "/").replace(",", "/").split("/")
        if token.strip()
    }
    if position_tokens.intersection({"GK", "GOALKEEPER"}):
        return "GK"
    if position_tokens.intersection({"ST", "CF", "F", "FW", "FORWARD", "STRIKER"}):
        return "ST"
    if position_tokens.intersection({"W", "LW", "RW", "AM", "CAM", "ATT"}):
        return "AM_W"
    if position_tokens.intersection({"MF", "MID", "CM", "DM", "CDM"}):
        return "DM_CM"
    if position_tokens.intersection({"LB", "RB", "LWB", "RWB", "FB", "WB"}):
        return "FB_WB"
    if position_tokens.intersection({"D", "DEF", "CB", "LCB", "RCB"}):
        return "CB"
    raw_upper = clean_text(raw_group).upper()
    fallback = {
        "GK": "GK",
        "DEF": "CB",
        "MID": "DM_CM",
        "MF": "DM_CM",
        "ATT": "AM_W",
        "FWD": "ST",
        "FOR": "ST",
    }
    return fallback.get(raw_upper, "unknown")


def display_name(athlete: pd.Series) -> str:
    existing = clean_text(athlete.get("display_name"))
    if existing:
        return existing
    return " ".join(
        part
        for part in [clean_text(athlete.get("first_name")), clean_text(athlete.get("last_name"))]
        if part
    )


def per90(value: float, minutes: float) -> float | str:
    if not minutes:
        return ""
    return round(float(value) / float(minutes) * 90.0, 6)


def clean_text(value: object) -> str:
    if value is None:
        return ""
    if pd.isna(value):
        return ""
    return str(value).strip()


if __name__ == "__main__":
    main()
