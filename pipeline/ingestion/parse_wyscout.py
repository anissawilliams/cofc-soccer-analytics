"""
parse_wyscout.py — Parse all Wyscout Sportscode XML types
Handles: sportscode, player events, team events, effective time
"""

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional


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

def parse_sportscode(path: Path) -> dict:
    """
    Parse Wyscout Sportscode XML.
    Returns player events, team events, and half markers.
    """
    root = ET.fromstring(path.read_bytes().decode("utf-16"))

    halves        = {}
    player_events = []
    team_events   = []
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
            outcome = (
                "Plus"    if "Plus"    in labels else
                "Minus"   if "Minus"   in labels else
                "Neutral" if "Neutral" in labels else
                "Unknown"
            )
            player_events.append({
                "jersey":   jersey,
                "name":     name,
                "start":    start,
                "end":      end,
                "labels":   labels,
                "outcome":  outcome,
                "raw_code": code,
            })
        elif code:
            team_events.append({
                "code":   code,
                "start":  start,
                "end":    end,
                "labels": labels,
            })

    print(f"  Sportscode: {len(player_events)} player events, "
          f"{len(team_events)} team events | halves: {halves}")
    return {
        "halves":        halves,
        "player_events": player_events,
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

    print(f"  Player XML: {len(events)} instances")
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

    print(f"  Team XML: {len(events)} instances")
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

    print(f"  Effective time: {len(segments)} segments, "
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
