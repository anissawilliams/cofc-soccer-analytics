"""
Pulls the full athlete_event data via the Supabase REST API (supabase-py client),
paginating past the default row cap, then joins athlete / metric_definition /
weights / match / team locally in pandas.

Setup:
  pip install supabase pandas python-dotenv

Uses the .env keys you already have:
  SUPABASE_URL
  SUPABASE_SERVICE_KEY

Run:
  python3 export_athlete_events.py
"""

import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from supabase import create_client

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
OUTPUT_PATH = "athlete_event_full_export.csv"
PAGE_SIZE = 1000  # supabase-py/PostgREST max rows per request


def fetch_all(client, table_name):
    """Pages through a table using .range() until fewer than PAGE_SIZE rows come back."""
    all_rows = []
    start = 0
    while True:
        resp = (
            client.table(table_name)
            .select("*")
            .range(start, start + PAGE_SIZE - 1)
            .execute()
        )
        batch = resp.data
        if not batch:
            break
        all_rows.extend(batch)
        print(f"  {table_name}: fetched {len(all_rows)} rows so far...")
        if len(batch) < PAGE_SIZE:
            break
        start += PAGE_SIZE
    return pd.DataFrame(all_rows)


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        sys.exit(
            "Missing SUPABASE_URL or SUPABASE_SERVICE_KEY. Check your .env file "
            "is in the same directory as this script and has both keys set."
        )

    client = create_client(SUPABASE_URL, SUPABASE_KEY)

    print("Fetching tables (paginated)...")
    try:
        athlete_event = fetch_all(client, "athlete_event")
        athlete = fetch_all(client, "athlete")
        metric_definition = fetch_all(client, "metric_definition")
        weights = fetch_all(client, "metric_weight")
        match = fetch_all(client, "match")
        team = fetch_all(client, "team")
    except Exception as e:
        sys.exit(
            f"Fetch failed: {e}\n"
            "Most likely a table name mismatch (check exact table names in "
            "Supabase Table Editor) or the service key doesn't have read access."
        )

    print(f"\nRow counts: athlete_event={len(athlete_event)}, athlete={len(athlete)}, "
          f"metric_definition={len(metric_definition)}, weights={len(weights)}, "
          f"match={len(match)}, team={len(team)}")

    # --- Join locally ---
    df = athlete_event.merge(
        athlete[["id", "display_name", "jersey_number", "position", "position_group"]],
        left_on="athlete_id", right_on="id", suffixes=("", "_athlete")
    )
    df = df.merge(
        metric_definition[["id", "name", "aset_letter", "peak_phase"]],
        left_on="metric_id", right_on="id", suffixes=("", "_metric")
    )
    df = df.merge(
        weights[["metric_id", "weight", "is_multiplier"]],
        on="metric_id", how="left"
    )
    df = df.merge(
        match[["session_id", "id", "home_team_id", "away_team_id", "result", "goals_for", "goals_against", "created_at"]],
        on="session_id", how="left", suffixes=("", "_match")
    )
    df = df.merge(
        team[["id", "name", "is_cofc"]].rename(columns={"id": "home_team_id", "name": "home_team_name", "is_cofc": "home_is_cofc"}),
        on="home_team_id", how="left"
    )
    df = df.merge(
        team[["id", "name", "is_cofc"]].rename(columns={"id": "away_team_id", "name": "away_team_name", "is_cofc": "away_is_cofc"}),
        on="away_team_id", how="left"
    )

    # Use team.is_cofc rather than athlete.team_id — more reliable since it doesn't
    # depend on every athlete row having team_id populated correctly.
    df["opponent"] = df.apply(
        lambda r: r["away_team_name"] if r["home_is_cofc"] else r["home_team_name"],
        axis=1,
    )
    df["venue"] = df.apply(
        lambda r: "home" if r["home_is_cofc"] else "away",
        axis=1,
    )

    out_cols = [
        "id", "match_id", "opponent", "venue", "result", "goals_for", "goals_against",
        "display_name", "jersey_number", "position", "position_group",
        "name", "aset_letter", "peak_phase",
        "raw_value", "raw_value_context", "weight", "is_multiplier",
        "collection_method", "manually_tagged", "coach_confirmed", "event_time",
    ]
    df = df.rename(columns={"id_match": "match_id", "name": "metric_name"})
    out_cols = [c if c != "name" else "metric_name" for c in out_cols]
    available_cols = [c for c in out_cols if c in df.columns]
    missing_cols = [c for c in out_cols if c not in df.columns]
    if missing_cols:
        print(f"Note: these expected columns weren't found after the join and will be skipped: {missing_cols}")

    df[available_cols].to_csv(OUTPUT_PATH, index=False)
    print(f"\nDone. {len(df)} rows written to {OUTPUT_PATH}.")


if __name__ == "__main__":
    main()