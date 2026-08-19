#!/usr/bin/env python3
"""Preview or apply a season roster sync to Supabase athlete records.

The parser roster is the source for Wyscout jersey-plus-name filtering. This
script makes the athlete table ready before the first match arrives, without
waiting for a match loader to create players incidentally.

The default mode is a review-only dry run. Use ``--apply`` only after checking
the generated report. Exact name matches are updated; non-matches become new
athletes. This script intentionally does not auto-merge fuzzy matches.
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv


INGESTION_DIR = Path(__file__).resolve().parent
if str(INGESTION_DIR) not in sys.path:
    sys.path.insert(0, str(INGESTION_DIR))

from source_paths import get_source_paths  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT_ROOT = REPO_ROOT / "pipeline" / "outputs" / "reports" / "roster_sync"
REQUIRED_COLUMNS = {"name", "number"}


def normalize_name(value: object) -> str:
    text = unicodedata.normalize("NFKD", clean_text(value))
    text = "".join(char for char in text if not unicodedata.combining(char)).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def clean_text(value: object) -> str:
    return "" if pd.isna(value) else str(value).strip()


def full_name_for_row(row: pd.Series) -> str:
    full_name = clean_text(row.get("full_name"))
    return full_name or clean_text(row["name"])


def display_name_for_row(row: pd.Series) -> str:
    display_name = clean_text(row.get("name"))
    if display_name:
        return display_name
    full_name = full_name_for_row(row)
    parts = full_name.split()
    return f"{parts[0][0]}. {' '.join(parts[1:])}" if len(parts) > 1 else full_name


def athlete_identity_keys(athlete: dict) -> set[str]:
    values = [
        athlete.get("display_name"),
        f"{athlete.get('first_name') or ''} {athlete.get('last_name') or ''}".strip(),
    ]
    return {normalize_name(value) for value in values if normalize_name(value)}


def validate_roster(roster: pd.DataFrame) -> list[str]:
    missing = REQUIRED_COLUMNS - set(roster.columns)
    if missing:
        return [f"Roster is missing required column(s): {', '.join(sorted(missing))}."]

    errors: list[str] = []
    normalized_names = roster.apply(full_name_for_row, axis=1).map(normalize_name)
    if normalized_names.eq("").any():
        errors.append("Roster contains an empty player name.")
    duplicate_names = normalized_names[normalized_names.duplicated()].unique().tolist()
    if duplicate_names:
        errors.append("Roster contains duplicate full-name entries: " + ", ".join(duplicate_names))
    if roster["number"].isna().any() or roster["number"].map(clean_text).eq("").any():
        errors.append("Roster contains a missing jersey number.")
    return errors


def build_sync_plan(
    roster: pd.DataFrame,
    athletes: list[dict],
    aliases: list[dict] | None = None,
) -> pd.DataFrame:
    """Classify exact identity matches into keep, update, or create actions."""
    identity_index: dict[str, dict] = {}
    athletes_by_id = {athlete["id"]: athlete for athlete in athletes}
    for athlete in athletes:
        for key in athlete_identity_keys(athlete):
            identity_index.setdefault(key, athlete)
    for alias in aliases or []:
        if alias.get("is_active") is False:
            continue
        athlete = athletes_by_id.get(alias.get("athlete_id"))
        key = normalize_name(alias.get("alias_name"))
        if athlete and key:
            identity_index.setdefault(key, athlete)

    plan_rows: list[dict[str, object]] = []
    for _, row in roster.iterrows():
        full_name = full_name_for_row(row)
        display_name = display_name_for_row(row)
        position = clean_text(row.get("pos")) or clean_text(row.get("position"))
        position_group = clean_text(row.get("group")) or clean_text(row.get("position_group"))
        match = identity_index.get(normalize_name(full_name)) or identity_index.get(normalize_name(display_name))

        base = {
            "roster_name": display_name,
            "roster_full_name": full_name,
            "jersey_number": str(row["number"]).strip(),
            "roster_position": position,
            "roster_position_group": position_group,
            "athlete_id": match.get("id") if match else "",
            "matched_display_name": match.get("display_name") if match else "",
        }
        if not match:
            parts = full_name.split()
            if len(parts) < 2:
                plan_rows.append({**base, "action": "blocked", "reason": "new athlete needs first and last name"})
                continue
            plan_rows.append({**base, "action": "create", "reason": "no exact athlete identity match"})
            continue

        changes: list[str] = []
        if position and position != str(match.get("position") or ""):
            changes.append("position")
        if position_group and position_group != str(match.get("position_group") or ""):
            changes.append("position_group")
        if str(match.get("status") or "") != "active":
            changes.append("status")
        action = "update" if changes else "keep"
        plan_rows.append({**base, "action": action, "reason": ", ".join(changes) or "exact identity match"})

    return pd.DataFrame(plan_rows)


def create_payload(row: pd.Series) -> dict[str, object]:
    parts = str(row["roster_full_name"]).strip().split()
    return {
        "first_name": parts[0],
        "last_name": " ".join(parts[1:]),
        "display_name": row["roster_name"],
        "position": row["roster_position"] or None,
        "position_group": row["roster_position_group"] or None,
        "status": "active",
    }


def update_payload(row: pd.Series) -> dict[str, object]:
    return {
        "position": row["roster_position"] or None,
        "position_group": row["roster_position_group"] or None,
        "status": "active",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def get_client():
    try:
        from supabase import create_client
    except ImportError as exc:
        raise SystemExit("Missing Python package 'supabase'. Install requirements before syncing the roster.") from exc

    load_dotenv()
    import os

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise EnvironmentError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")
    return create_client(url, key)


def main() -> None:
    paths = get_source_paths()
    parser = argparse.ArgumentParser(description="Preview or apply a season roster sync to public.athlete.")
    parser.add_argument("--season", required=True)
    parser.add_argument("--roster", type=Path, default=None)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--apply", action="store_true", help="Create/update athlete records after review")
    args = parser.parse_args()

    roster_path = args.roster or paths.pipeline_root / "ingestion" / f"roster_{args.season}.csv"
    if not roster_path.exists():
        raise SystemExit(f"Roster not found: {roster_path}")
    roster = pd.read_csv(roster_path, dtype={"number": str})
    errors = validate_roster(roster)
    if errors:
        raise SystemExit("Roster sync blocked:\n- " + "\n- ".join(errors))

    client = get_client()
    athletes = client.table("athlete").select(
        "id, first_name, last_name, display_name, position, position_group, status"
    ).execute().data or []
    try:
        aliases = client.table("athlete_alias").select("athlete_id, alias_name, is_active").execute().data or []
    except Exception as exc:
        print(f"Warning: athlete_alias lookup unavailable; using canonical athlete names only: {exc}")
        aliases = []
    plan = build_sync_plan(roster, athletes, aliases)
    blocked = plan[plan["action"].eq("blocked")]
    if not blocked.empty:
        print(blocked.to_string(index=False))
        raise SystemExit("Roster sync blocked; resolve the rows above.")

    report_path = args.report_root / str(args.season) / "roster_sync_plan.csv"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    plan.to_csv(report_path, index=False)
    print(f"Wrote roster sync plan: {report_path}")
    print(plan.groupby("action").size().rename("count").to_string())
    print(plan[["jersey_number", "roster_name", "matched_display_name", "action", "reason"]].to_string(index=False))

    if not args.apply:
        print("Dry run only. Review the plan and rerun with --apply to update public.athlete.")
        return

    created = updated = 0
    for _, row in plan.iterrows():
        if row["action"] == "create":
            client.table("athlete").insert(create_payload(row)).execute()
            created += 1
        elif row["action"] == "update":
            client.table("athlete").update(update_payload(row)).eq("id", row["athlete_id"]).execute()
            updated += 1
    print(f"Applied roster sync: {created} athlete(s) created, {updated} athlete(s) updated.")


if __name__ == "__main__":
    main()
