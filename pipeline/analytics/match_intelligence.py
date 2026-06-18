"""
match_intelligence.py
======================
CofC Soccer Analytics — Match Intelligence Summary
Parses three Wyscout XML exports for a given match and produces
a tactical summary: team shape, half-by-half breakdown, player
event volume, and substitution detection via event-span proxy.

Usage:
    python match_intelligence.py 2025-11-02_uncw

Output:
    Prints a formatted match intelligence report to stdout.
    Future: write to DB, generate PDF scouting report.

File naming convention (per match folder):
    {date}_{opponent}_cfc_team_events.xml
    {date}_{opponent}_cfc_player_events.xml
    {date}_{opponent}_cfc_effective_time.xml
"""

import re
import sys
from pathlib import Path
from collections import defaultdict, Counter

# ── Config ────────────────────────────────────────────────────────────────────

#DATA_DIR = Path(__file__).parent / "pipeline" / "data" / "matches"
DATA_DIR = Path("/Users/anissawilliams/PycharmProjects/cofc_soccer_analytics_2026/pipeline/data/matches")
# ── XML parsing ───────────────────────────────────────────────────────────────

def load_xml(path: Path) -> str:
    """Load XML file, handling both UTF-8 (converted) and UTF-16LE (raw Wyscout)."""
    # Try UTF-8 first (iconv-converted files)
    try:
        content = path.read_text(encoding="utf-8")
        if content.startswith("<"):
            return content
    except Exception:
        pass
    # Fall back to UTF-16LE (raw Wyscout export)
    try:
        return path.read_text(encoding="utf-16-le")
    except Exception:
        pass
    # Last resort - binary decode
    return path.read_bytes().decode("utf-8", errors="replace")


def parse_instances(content: str) -> list[dict]:
    """Extract all instances from Wyscout XML."""
    instances = []
    for block in re.findall(r'<instance>(.*?)</instance>', content, re.DOTALL):
        id_m    = re.search(r'<ID>(\d+)</ID>', block)
        start_m = re.search(r'<start>(\d+)</start>', block)
        end_m   = re.search(r'<end>(\d+)</end>', block)
        code_m  = re.search(r'<code>(.*?)</code>', block, re.DOTALL)
        label_m = re.search(r'<text>(.*?)</text>', block, re.DOTALL)
        if not all([id_m, start_m, end_m, code_m, label_m]):
            continue
        instances.append({
            "id":    int(id_m.group(1)),
            "start": int(start_m.group(1)),
            "end":   int(end_m.group(1)),
            "code":  code_m.group(1).strip(),
            "label": label_m.group(1).strip(),
        })
    return instances


def get_half_anchors(team_instances: list[dict]) -> dict:
    """Extract half start/end timestamps — look in labels or fallback to defaults."""
    anchors = {}
    for inst in team_instances:
        label = inst["label"]
        if label in ("First half start", "First half end",
                     "Second half start", "Second half end"):
            anchors[label] = inst["start"]

    # Fallback defaults if anchors not found in this file
    # (they may live in the main match XML, not the team-specific export)
    defaults = {
        "First half start":  2,
        "First half end":    2776,
        "Second half start": 2778,
        "Second half end":   6020,
    }
    for k, v in defaults.items():
        if k not in anchors:
            anchors[k] = v

    return anchors


def half_of(t: int, anchors: dict) -> int:
    half1_end = anchors.get("First half end", 2776)
    return 1 if t <= half1_end else 2


# ── Analysis ──────────────────────────────────────────────────────────────────

def team_shape(team_instances: list[dict], anchors: dict) -> dict:
    """Team event counts overall and by half."""
    by_label = defaultdict(lambda: [0, 0, 0])  # [total, h1, h2]
    for inst in team_instances:
        label = inst["label"]
        if label in ("First half start", "First half end",
                     "Second half start", "Second half end"):
            continue
        h = half_of(inst["start"], anchors)
        by_label[label][0] += 1
        by_label[label][h] += 1
    return dict(by_label)


def player_summary(player_instances: list[dict], anchors: dict) -> dict:
    """Per-player event counts and likely role (starter/sub/full 90)."""
    player_data = defaultdict(lambda: {"h1": 0, "h2": 0, "times": []})
    for inst in player_instances:
        code = inst["code"]
        h = half_of(inst["start"], anchors)
        player_data[code]["h1" if h == 1 else "h2"] += 1
        player_data[code]["times"].append((inst["start"], inst["end"]))

    half1_end  = anchors.get("First half end",    2776)
    match_end  = anchors.get("Second half end",   6020)
    half2_start = anchors.get("Second half start", 2778)

    result = {}
    for player, data in player_data.items():
        times  = data["times"]
        first  = min(t[0] for t in times)
        last   = max(t[1] for t in times)
        total  = data["h1"] + data["h2"]

        if first < 50 and last > match_end - 50:
            role = "Full 90"
        elif first < 50 and last < half1_end + 100:
            role = "Started → subbed ~HT"
        elif first > half2_start - 100 and last > match_end - 50:
            role = "Sub on ~HT → finished"
        elif first < 50:
            role = "Started → subbed off"
        elif first > 3600:
            role = "Late sub"
        else:
            role = "Partial minutes"

        result[player] = {
            "total_events": total,
            "h1_events": data["h1"],
            "h2_events": data["h2"],
            "first_event": first,
            "last_event":  last,
            "role": role,
        }

    return result


def effective_time_summary(eff_instances: list[dict]) -> dict:
    """Total ball-in-play time from effective time XML."""
    if not eff_instances:
        return {"segments": 0, "effective_seconds": 0, "effective_minutes": 0}
    total = sum(i["end"] - i["start"] for i in eff_instances)
    return {
        "segments":          len(eff_instances),
        "effective_seconds": total,
        "effective_minutes": round(total / 60, 1),
    }


# ── Report printing ───────────────────────────────────────────────────────────

def print_report(match_key: str, team: dict, players: dict, eff: dict, anchors: dict):
    sep  = "─" * 60
    sep2 = "═" * 60

    print(f"\n{sep2}")
    print(f"  MATCH INTELLIGENCE — {match_key.upper()}")
    print(f"{sep2}")

    # Half timing
    h1_dur = (anchors.get("First half end", 2776) - anchors.get("First half start", 2)) / 60
    h2_dur = (anchors.get("Second half end", 6020) - anchors.get("Second half start", 2778)) / 60
    print(f"\n  MATCH CLOCK")
    print(f"  {'H1 duration:':<28} {h1_dur:.1f} min")
    print(f"  {'H2 duration:':<28} {h2_dur:.1f} min")
    print(f"  {'Effective playing time:':<28} {eff['effective_minutes']} min  ({eff['segments']} segments)")
    print(f"  {'Stoppage estimate:':<28} {round(h1_dur + h2_dur - eff['effective_minutes'], 1)} min")

    # Key team stats
    KEY_STATS = [
        ("Goals scored",                  "goals_scored"),
        ("Goals conceded",                "goals_conceded"),
        ("Shots",                         "shots"),
        ("Shots conceded",                "shots_conceded"),
        ("Goal scoring opportunities",    "gso"),
        ("Goal scoring opportunities conceded", "gso_conceded"),
        ("Crosses",                       "crosses"),
        ("Crosses conceded",              "crosses_conceded"),
        ("Attacking style of play",       "att_style"),
        ("Defending style of play",       "def_style"),
    ]

    label_map = {
        "Goals scored":                       "Goals scored",
        "Goals conceded":                     "Goals conceded",
        "Shots":                              "Shots",
        "Shots conceded":                     "Shots conceded",
        "Goal scoring opportunities":         "Goal scoring opportunities",
        "Goal scoring opportunities conceded":"Goal scoring opportunities conceded",
        "Crosses":                            "Crosses",
        "Crosses conceded":                   "Crosses conceded",
        "Attacking style of play":            "Attacking style of play",
        "Defending style of play":            "Defending style of play",
    }

    print(f"\n{sep}")
    print(f"  TEAM SHAPE                          TOTAL    H1    H2")
    print(sep)
    for display, _ in KEY_STATS:
        data = team.get(display)
        if data:
            print(f"  {display:<38} {data[0]:<6}   {data[1]:<4}  {data[2]}")

    # Tactical flags
    print(f"\n{sep}")
    print(f"  TACTICAL NOTES")
    print(sep)
    shots    = (team.get("Shots") or [0])[0]
    shots_c  = (team.get("Shots conceded") or [0])[0]
    crosses  = (team.get("Crosses") or [0])[0]
    crosses_c = (team.get("Crosses conceded") or [0])[0]
    def_h1   = (team.get("Defending style of play") or [0, 0, 0])[1]
    def_h2   = (team.get("Defending style of play") or [0, 0, 0])[2]

    if shots > 0 and shots_c > 0:
        ratio = shots_c / shots
        flag = "⚠️  opponent outshot us" if ratio > 1.5 else "✓  shot volume balanced"
        print(f"  Shot ratio (conceded/created): {ratio:.1f}  {flag}")

    if crosses_c > 0 and crosses > 0:
        ratio = crosses_c / crosses
        flag = "⚠️  opponent heavy on wide play" if ratio > 1.8 else "✓  cross balance ok"
        print(f"  Cross ratio (conceded/created): {ratio:.1f}  {flag}")

    if def_h2 > def_h1 * 1.3:
        print(f"  ⚠️  Defensive pressure increased in H2 ({def_h1} → {def_h2} defending tags)")
    else:
        print(f"  ✓  Defensive shape consistent across halves ({def_h1} H1 / {def_h2} H2)")

    # Player summary
    print(f"\n{sep}")
    print(f"  PLAYER ACTIVITY                     ROLE                H1    H2   TOTAL")
    print(sep)
    sorted_players = sorted(players.items(), key=lambda x: -x[1]["total_events"])
    for player, data in sorted_players:
        print(f"  {player:<36} {data['role']:<20} {data['h1_events']:<5} {data['h2_events']:<5} {data['total_events']}")

    print(f"\n{sep2}\n")


# ── Main ──────────────────────────────────────────────────────────────────────

def run(match_key: str):
    match_dir = DATA_DIR / "2025" / match_key

    if not match_dir.exists():
        print(f"ERROR: match folder not found: {match_dir}")
        sys.exit(1)

    # Find files by suffix
    def find_file(suffix):
        matches = list(match_dir.glob(f"*{suffix}"))
        if not matches:
            print(f"WARNING: no file matching *{suffix} in {match_dir}")
            return None
        return matches[0]

    team_file   = find_file("team_events.xml")
    player_file = find_file("player_events.xml")
    eff_file    = find_file("effective_time.xml")

    team_instances   = parse_instances(load_xml(team_file))   if team_file   else []
    player_instances = parse_instances(load_xml(player_file)) if player_file else []
    eff_instances    = parse_instances(load_xml(eff_file))    if eff_file    else []

    anchors = get_half_anchors(team_instances)
    team    = team_shape(team_instances, anchors)
    players = player_summary(player_instances, anchors)
    eff     = effective_time_summary(eff_instances)

    print_report(match_key, team, players, eff, anchors)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python match_intelligence.py <match_key>")
        print("Example: python match_intelligence.py 2025-11-02_uncw")
        sys.exit(1)
    run(sys.argv[1])