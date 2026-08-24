#!/usr/bin/env python3
"""Load only a match's validated staff events; Wyscout parsing is not required."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import db  # noqa: E402
from staff_events import parse_staff_events  # noqa: E402
from parse_wyscout import normalize_player_name  # noqa: E402


def resolve_session_id(client, season: str, slug: str) -> str:
    match_date = slug.split("_", 1)[0]
    rows = (
        client.table("session")
        .select("id, session_date, season, session_type, notes")
        .eq("session_date", match_date)
        .eq("season", str(season))
        .execute()
        .data
        or []
    )
    marker = f"slug: {slug}"
    matches = [
        row for row in rows
        if row.get("session_type") in {"match", "scrimmage"}
        and marker in str(row.get("notes") or "").splitlines()
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Expected one match session with '{marker}' in season {season}; "
            f"found {len(matches)}."
        )
    return matches[0]["id"]


def athlete_map(client) -> dict[str, str]:
    rows = client.table("athlete").select("id, display_name").execute().data or []
    return {
        normalize_player_name(row.get("display_name") or ""): row["id"]
        for row in rows
        if row.get("display_name")
    }


def active_weights(client) -> dict[str, dict]:
    rows = (
        client.table("metric_weight")
        .select("id, weight, version, metric:metric_id(id, name, applies_to_session_type)")
        .eq("version", db.COUG_TABLE_WEIGHT_VERSION)
        .is_("effective_to", "null")
        .execute()
        .data
        or []
    )
    return {
        (row.get("metric") or {}).get("name"): row
        for row in rows
        if (row.get("metric") or {}).get("name")
    }


def resolve_source_id(client, slug: str, *, apply: bool) -> str:
    label = f"Staff events — {slug}"
    rows = (
        client.table("data_source")
        .select("id")
        .eq("platform", "csv")
        .eq("name", label)
        .execute()
        .data
        or []
    )
    if rows:
        return rows[0]["id"]
    if not apply:
        return "dry-run-staff-events-source"
    created = client.table("data_source").insert({
        "name": label,
        "platform": "csv",
        "source_type": "file",
        "source_priority": 2,
    }).execute().data or []
    if len(created) != 1:
        raise RuntimeError("Could not create the staff-event data source.")
    return created[0]["id"]


def load_events(client, session_id: str, events: list[dict], *, apply: bool) -> dict:
    athletes = athlete_map(client)
    weights = active_weights(client)
    inserted = 0
    updated = 0
    duplicates = 0
    stint_updates = 0
    scoring_inserts = 0
    scoring_updates = 0
    source_id = resolve_source_id(client, events[0]["match_slug"], apply=apply) if events else None
    for event in events:
        athlete_id = athletes.get(normalize_player_name(event["player_name"]))
        if not athlete_id:
            raise ValueError(f"No database athlete matches {event['player_name']}")
        weight_id = None
        if event.get("metric_name"):
            weight = weights.get(event["metric_name"])
            if not weight:
                raise ValueError(
                    f"No active {db.COUG_TABLE_WEIGHT_VERSION} weight exists for "
                    f"{event['metric_name']}. Run the red-card metric migration first."
                )
            if float(weight.get("weight")) != float(event["proposed_weight"]):
                raise ValueError(
                    f"CSV weight {event['proposed_weight']} does not match the active "
                    f"database weight {weight.get('weight')} for {event['metric_name']}."
                )
            weight_id = weight["id"]

        existing_query = (
            client.table("session_event")
            .select("id")
            .eq("session_id", session_id)
            .eq("athlete_id", athlete_id)
            .eq("event_type", event["event_type"])
        )
        if event["event_type"] != "red_card":
            existing_query = existing_query.eq("event_time", event["event_time"])
        existing = existing_query.execute().data or []

        payload = {
            "session_id": session_id,
            "athlete_id": athlete_id,
            "event_type": event["event_type"],
            "metric_weight_id": weight_id,
            "raw_value": 1.0,
            "event_time": event["event_time"],
            "notes": event.get("notes") or None,
            "recorded_by": event["entered_by"],
            "score_status": (
                "applied" if weight_id and apply
                else "pending_review" if weight_id
                else "informational"
            ),
        }
        if existing and event["event_type"] == "red_card":
            if len(existing) != 1:
                raise ValueError("More than one red card row already exists for this player/match.")
            if apply:
                (
                    client.table("session_event")
                    .update(payload)
                    .eq("id", existing[0]["id"])
                    .execute()
                )
            updated += 1
        elif existing:
            duplicates += 1
        else:
            if apply:
                client.table("session_event").insert(payload).execute()
            inserted += 1

        if event.get("player_off"):
            stints = (
                client.table("athlete_session_stint")
                .select("id, minutes_off")
                .eq("session_id", session_id)
                .eq("athlete_id", athlete_id)
                .execute()
                .data
                or []
            )
            if len(stints) == 1:
                if apply:
                    (
                        client.table("athlete_session_stint")
                        .update({"minutes_off": int(math.ceil(event["minute"]))})
                        .eq("id", stints[0]["id"])
                        .execute()
                    )
                stint_updates += 1

        if weight_id:
            metric_id = (weights[event["metric_name"]].get("metric") or {}).get("id")
            if not metric_id:
                raise ValueError(f"The active weight for {event['metric_name']} has no metric id.")
            context = {
                "source": "staff_events.csv",
                "event_type": event["event_type"],
                "player_off": bool(event.get("player_off")),
                "entered_by": event["entered_by"],
            }
            scoring_rows = [] if source_id == "dry-run-staff-events-source" else (
                client.table("athlete_event")
                .select("id")
                .eq("session_id", session_id)
                .eq("athlete_id", athlete_id)
                .eq("metric_id", metric_id)
                .eq("source_id", source_id)
                .execute()
                .data
                or []
            )
            scoring_payload = {
                "athlete_id": athlete_id,
                "session_id": session_id,
                "metric_id": metric_id,
                "source_id": source_id,
                "raw_value": 1.0,
                "raw_value_context": context,
                "collection_method": "manual",
                "manually_tagged": True,
                "coach_confirmed": True,
                "tag_notes": event.get("notes") or "Staff event CSV",
                "event_time": event["event_time"],
            }
            if len(scoring_rows) > 1:
                raise ValueError("More than one scoring event already exists for this staff incident.")
            if scoring_rows:
                if apply:
                    (
                        client.table("athlete_event")
                        .update(scoring_payload)
                        .eq("id", scoring_rows[0]["id"])
                        .execute()
                    )
                scoring_updates += 1
            else:
                if apply:
                    client.table("athlete_event").insert(scoring_payload).execute()
                scoring_inserts += 1
    return {
        "mode": "apply" if apply else "dry_run",
        "events_would_insert" if not apply else "events_inserted": inserted,
        "events_would_update" if not apply else "events_updated": updated,
        "duplicates": duplicates,
        "off_moments_would_update" if not apply else "off_moments_updated": stint_updates,
        "scoring_events_would_insert" if not apply else "scoring_events_inserted": scoring_inserts,
        "scoring_events_would_update" if not apply else "scoring_events_updated": scoring_updates,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--staff-dir", type=Path, required=True)
    parser.add_argument("--roster", type=Path, default=None)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    roster = (
        args.roster
        or Path(__file__).resolve().parent / f"roster_{args.season}.csv"
    ).resolve()
    source = args.staff_dir.resolve() / "staff_events.csv"
    events = parse_staff_events(
        source, roster, slug=args.slug, season=str(args.season)
    )
    client = db.get_client()
    session_id = resolve_session_id(client, str(args.season), args.slug)
    report = load_events(client, session_id, events, apply=args.apply)
    print(json.dumps({"slug": args.slug, "session_id": session_id, **report}, indent=2))


if __name__ == "__main__":
    main()
