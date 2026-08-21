"""
parse_wyscout.py — Parse all Wyscout Sportscode XML types
Handles: sportscode, player events, team events, effective time
"""

import re
import csv
import sys
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path


def _log(message: str) -> None:
    """Keep parser diagnostics separate from machine-readable stdout."""
    print(message, file=sys.stderr)


# ── Roster loading ────────────────────────────────────────────

def load_cofc_roster(path: Path) -> dict:
    """
    Load CofC roster CSV.
    Returns:
        cofc_roster — dict {jersey: set(valid_names)}.

    A jersey number can have more than one valid name if a player's jersey
    number changed mid-season but is still the same person (e.g. jersey 14
    legitimately maps to both "E. Goetzke" and "E. Emanuele" for the 2025
    season — same athlete, name changed when their number changed).

    Roster CSV format: number,name — one row per (jersey, name) pair.
    A player with multiple valid names just gets multiple rows with the
    same jersey number.

    IMPORTANT: jersey number alone is NOT a safe filter key. Jersey numbers
    are not unique across two teams on the same pitch — an opponent can
    wear the same number as a CofC player. Filtering must check that BOTH
    the jersey number AND the name match a CofC roster entry, otherwise
    opponent events silently pass through.
    """
    cofc_roster = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            if row.get("number"):
                jersey = str(row["number"]).strip()
                name = row["name"].strip()
                cofc_roster.setdefault(jersey, set()).add(normalize_player_name(name))
    return cofc_roster


def normalize_player_name(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name)
    return "".join(char for char in normalized if not unicodedata.combining(char)).strip().lower()


# ── Encoding detection ────────────────────────────────────────

def read_xml(path: Path) -> ET.Element:
    """Read XML file, handling UTF-16 or UTF-8 encoding."""
    raw = path.read_bytes()
    for enc in ("utf-16", "utf-8", "latin-1"):
        try:
            content = raw.decode(enc)
            return ET.fromstring(content)
        except (UnicodeDecodeError, ET.ParseError):
            continue
    raise ValueError(f"Could not parse XML: {path}")


# ── Sportscode XML (richest — use this as primary) ────────────

def parse_sportscode(path: Path, roster_path: Path = None) -> dict:
    """
    Parse Wyscout Sportscode XML.
    Returns player events, team events, and half markers.

    If roster_path is provided, filters player_events to CofC players only
    using jersey number + player-name matching. Without it, both teams'
    players are included.
    """
    root = read_xml(path)

    cofc_roster = None
    if roster_path and Path(roster_path).exists():
        cofc_roster = load_cofc_roster(Path(roster_path))
        _log(f"  Roster filter: {len(cofc_roster)} CofC players loaded")

    halves        = {}
    player_events = []
    all_player_events = []
    team_events   = []
    skipped       = 0
    player_re     = re.compile(r"\((\d+)\)\s+(.+)")

    for inst in root.findall(".//instance"):
        code   = inst.find("code").text  if inst.find("code")  is not None else ""
        start  = float(inst.find("start").text) if inst.find("start") is not None else 0
        end    = float(inst.find("end").text)   if inst.find("end")   is not None else 0
        labels = [l.text for l in inst.findall(".//text") if l.text]

        # Half offset markers
        if code == "Offsets":
            for label in labels:
                if "First half start"  in label: halves["first_start"]  = start
                if "First half end"    in label: halves["first_end"]    = end
                if "Second half start" in label: halves["second_start"] = start
                if "Second half end"   in label: halves["second_end"]   = end
            continue

        # Player events — code matches "(jersey) Name" pattern
        m = player_re.match(code or "")
        if m:
            jersey  = m.group(1)
            name    = m.group(2).strip()

            event = {
                "jersey":   jersey,
                "name":     name,
                "start":    start,
                "end":      end,
                "labels":   labels,
                "outcome": (
                    "Plus"    if "Plus"    in labels else
                    "Minus"   if "Minus"   in labels else
                    "Neutral" if "Neutral" in labels else
                    "Unknown"
                ),
                "raw_code": code,
            }

            if cofc_roster is not None:
                valid_names = cofc_roster.get(jersey)
                event["roster_match"] = valid_names is not None and normalize_player_name(name) in valid_names
                all_player_events.append(event)
                if not event["roster_match"]:
                    skipped += 1
                    continue
                # name already matches — never overwrite a name that didn't match
            else:
                event["roster_match"] = None
                all_player_events.append(event)

            player_events.append(event)
        elif code:
            team_events.append({
                "code":   code,
                "start":  start,
                "end":    end,
                "labels": labels,
            })

    first_start = halves.get("first_start", 0.0)
    second_start = halves.get("second_start")
    for event in all_player_events:
        if second_start is not None and event["start"] >= second_start:
            event["half"] = 2
            event["match_minute"] = 45.0 + max(0.0, event["start"] - second_start) / 60.0
        else:
            event["half"] = 1
            event["match_minute"] = max(0.0, event["start"] - first_start) / 60.0

    for event in team_events:
        if second_start is not None and event["start"] >= second_start:
            event["half"] = 2
            event["match_minute"] = 45.0 + max(0.0, event["start"] - second_start) / 60.0
        else:
            event["half"] = 1
            event["match_minute"] = max(0.0, event["start"] - first_start) / 60.0

    filter_msg = f" | {skipped} opponent events filtered out" if cofc_roster else " | ⚠️  no roster filter applied"
    _log(f"  Sportscode: {len(player_events)} player events, "
         f"{len(team_events)} team events | halves: {halves}{filter_msg}")
    return {
        "halves":        halves,
        "player_events": player_events,
        "all_player_events": all_player_events,
        "team_events":   team_events,
    }


# ── Player XML ────────────────────────────────────────────────

def parse_player_xml(path: Path) -> list:
    """
    Parse Wyscout player-level XML export.
    Returns list of player event instances.
    Simpler structure than sportscode — used as supplementary.
    """
    root   = read_xml(path)
    events = []
    for inst in root.findall(".//instance"):
        code   = inst.find("code").text  if inst.find("code")  is not None else ""
        start  = float(inst.find("start").text) if inst.find("start") is not None else 0
        end    = float(inst.find("end").text)   if inst.find("end")   is not None else 0
        labels = [l.text for l in inst.findall(".//text") if l.text]
        events.append({"code": code, "start": start, "end": end, "labels": labels})

    _log(f"  Player XML: {len(events)} instances")
    return events


# ── Team XML ──────────────────────────────────────────────────

def parse_team_xml(path: Path) -> list:
    """
    Parse Wyscout team-level XML export.
    Returns list of team event instances.
    """
    root   = read_xml(path)
    events = []
    for inst in root.findall(".//instance"):
        code   = inst.find("code").text  if inst.find("code")  is not None else ""
        start  = float(inst.find("start").text) if inst.find("start") is not None else 0
        end    = float(inst.find("end").text)   if inst.find("end")   is not None else 0
        labels = [l.text for l in inst.findall(".//text") if l.text]
        events.append({"code": code, "start": start, "end": end, "labels": labels})

    _log(f"  Team XML: {len(events)} instances")
    return events


# ── Effective Time XML ────────────────────────────────────────

def parse_effective_time(path: Path) -> dict:
    """
    Parse effective time XML.
    Returns segments of actual playing time (excludes stoppages).
    """
    root     = read_xml(path)
    segments = []
    total_s  = 0.0

    for inst in root.findall(".//instance"):
        start = float(inst.find("start").text) if inst.find("start") is not None else 0
        end   = float(inst.find("end").text)   if inst.find("end")   is not None else 0
        dur   = end - start
        total_s += dur
        segments.append({"start": start, "end": end, "duration": dur})

    _log(f"  Effective time: {len(segments)} segments, "
         f"{total_s/60:.1f} effective minutes")
    return {"segments": segments, "total_seconds": total_s}


# ── Minutes played (from effective time + player events) ──────

def estimate_minutes_played(player_events: list) -> dict[str, float]:
    """
    Estimate minutes played per player from their event timestamps.
    Uses first → last event as a rough proxy until we get
    player match report CSVs from Wyscout.
    Returns {player_name: minutes}
    """
    from collections import defaultdict
    player_times = defaultdict(list)

    for ev in player_events:
        player_times[ev["name"]].append(ev["start"])

    minutes = {}
    for name, times in player_times.items():
        span = (max(times) - min(times)) / 60
        # Floor at 5 min, cap at 100 min
        minutes[name] = max(5.0, min(span, 100.0))

    return minutes


# ── Helpers ───────────────────────────────────────────────────

def wyscout_to_match_minute(
    timestamp: float,
    first_half_start: float
) -> float:
    """Convert Wyscout timestamp (seconds) to match minute."""
    return (timestamp - first_half_start) / 60.0
