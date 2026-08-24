"""Validate match-level staff events without requiring vendor match parsing."""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Optional

from parse_wyscout import normalize_player_name


EVENT_TYPES = {
    "red_card", "yellow_card", "injury", "training_action",
    "coach_observation", "other",
}
REQUIRED_COLUMNS = {
    "player_name", "jersey", "event_type", "minute", "weight", "notes", "entered_by",
}


def parse_minute(value: str) -> tuple[float, float]:
    """Return display minute and elapsed seconds from 82.5 or 82:30."""
    text = str(value or "").strip()
    if not text:
        raise ValueError("minute is required")
    if ":" in text:
        minute_text, second_text = text.split(":", 1)
        minute = int(minute_text)
        second = int(second_text)
        if second < 0 or second > 59:
            raise ValueError(f"invalid minute value: {text}")
        seconds = float(minute * 60 + second)
    else:
        seconds = float(text) * 60
    if seconds < 0 or seconds > 130 * 60:
        raise ValueError(f"minute is outside the supported 0-130 range: {text}")
    return round(seconds / 60, 4), seconds


def _name_matches(roster_name: str, supplied_name: str) -> bool:
    expected = re.findall(r"[a-z]+", normalize_player_name(roster_name))
    supplied = re.findall(r"[a-z]+", normalize_player_name(supplied_name))
    if not expected or not supplied or expected[-1] != supplied[-1]:
        return False
    return expected[0][0] == supplied[0][0]


def load_roster(path: Path) -> dict[str, list[str]]:
    roster: dict[str, list[str]] = {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            jersey = str(row.get("number") or "").strip()
            name = str(row.get("name") or "").strip()
            if jersey and name:
                roster.setdefault(jersey, []).append(name)
    return roster


def parse_staff_events(
    csv_path: Path,
    roster_path: Path,
    *,
    slug: str,
    season: str,
) -> list[dict]:
    """Validate a shared staff CSV and return canonical, roster-matched rows."""
    roster = load_roster(roster_path)
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        missing = sorted(REQUIRED_COLUMNS - columns)
        if missing:
            raise ValueError(f"staff_events.csv is missing columns: {', '.join(missing)}")
        source_rows = list(reader)

    events = []
    for index, row in enumerate(source_rows, 2):
        event_type = str(row.get("event_type") or "").strip().lower()
        if event_type not in EVENT_TYPES:
            raise ValueError(f"row {index}: unsupported event_type {event_type!r}")
        jersey = str(row.get("jersey") or "").strip()
        supplied_name = str(row.get("player_name") or "").strip()
        roster_name = next(
            (name for name in roster.get(jersey, []) if _name_matches(name, supplied_name)),
            None,
        )
        if not roster_name:
            raise ValueError(
                f"row {index}: player does not match the {season} roster: "
                f"#{jersey} {supplied_name}"
            )
        minute, event_time = parse_minute(row.get("minute"))
        entered_by = str(row.get("entered_by") or "").strip()
        if not entered_by:
            raise ValueError(f"row {index}: entered_by is required")
        weight_text = str(row.get("weight") or "").strip()
        weight = float(weight_text) if weight_text else None
        metric_name = "Red Card" if event_type == "red_card" else None
        if event_type == "red_card" and weight != -2:
            raise ValueError(f"row {index}: red_card weight must be -2")
        if event_type != "red_card" and weight is not None:
            raise ValueError(
                f"row {index}: only red_card has an approved CSV weight; leave weight blank"
            )
        events.append({
            "match_slug": slug,
            "season": str(season),
            "player_name": roster_name,
            "jersey": jersey,
            "event_type": event_type,
            "minute": minute,
            "event_time": event_time,
            "metric_name": metric_name or "",
            "proposed_weight": weight if weight is not None else "",
            "player_off": event_type == "red_card",
            "notes": str(row.get("notes") or "").strip(),
            "entered_by": entered_by,
            "source_file": csv_path.name,
        })
    return events


def inspect_staff_events(
    csv_path: Optional[Path],
    roster_path: Path,
    *,
    slug: str,
    season: str,
) -> tuple[dict, list[dict]]:
    if csv_path is None or not csv_path.is_file():
        return {
            "ready": True,
            "supplied": False,
            "reason": "no staff event CSV supplied",
            "events": 0,
            "off_moments": 0,
        }, []
    try:
        events = parse_staff_events(
            csv_path, roster_path, slug=slug, season=season
        )
    except (OSError, ValueError) as exc:
        return {
            "ready": False,
            "supplied": True,
            "reason": str(exc),
            "events": 0,
            "off_moments": 0,
        }, []
    return {
        "ready": True,
        "supplied": True,
        "reason": "staff events validated against the season roster",
        "selected_file": str(csv_path),
        "events": len(events),
        "off_moments": sum(bool(row["player_off"]) for row in events),
    }, events
