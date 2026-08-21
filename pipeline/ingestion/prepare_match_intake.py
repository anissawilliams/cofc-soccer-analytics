#!/usr/bin/env python3
"""Inspect loose Wyscout exports and prepare a canonical team-event timeline.

This command never writes to Supabase. It accepts vendor filenames as-is,
classifies XML files by their contents, and reports scoring readiness separately
from analytics readiness. When a complementary pair of team-event XML files is
available, it can merge their mirrored perspectives into one deduplicated CSV.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from parse_wyscout import load_cofc_roster, normalize_player_name, parse_sportscode, read_xml
from source_paths import get_source_paths


PLAYER_CODE = re.compile(r"\(\d+\)\s+.+")
PLAYER_CODE_PARTS = re.compile(r"\((\d+)\)\s+(.+)")
PERIOD_LABELS = {
    "First half start",
    "First half end",
    "Second half start",
    "Second half end",
}

# relation is from the perspective of the team named in the XML <code> field.
LABEL_MAP = {
    "Goals scored": ("goal", "self"),
    "Goals conceded": ("goal", "opponent"),
    "Shots": ("shot", "self"),
    "Shots conceded": ("shot", "opponent"),
    "Goal scoring opportunities": ("scoring_opportunity", "self"),
    "Goal scoring opportunities conceded": ("scoring_opportunity", "opponent"),
    "Attacking corners": ("corner", "self"),
    "Corners conceded": ("corner", "opponent"),
    "Crosses": ("cross", "self"),
    "Crosses conceded": ("cross", "opponent"),
    "Attacking throws in": ("throw_in", "self"),
    "Throws in conceded": ("throw_in", "opponent"),
    "Other free kicks": ("free_kick", "self"),
    "Other free kicks conceded": ("free_kick", "opponent"),
    "Attacking free kicks": ("free_kick", "self"),
    "Free kicks conceded": ("free_kick", "opponent"),
    "Attacking direct free kicks": ("direct_free_kick", "self"),
    "Direct free kicks conceded": ("direct_free_kick", "opponent"),
    "Counter-attacks": ("counter_attack", "self"),
    "Opposition counter-attacks": ("counter_attack", "opponent"),
    "Attacking style of play": ("attacking_phase", "self"),
    "Defending style of play": ("attacking_phase", "opponent"),
    "Goalkeeper's distribution": ("goalkeeper_distribution", "self"),
    "Opposition goalkeeper's distributions": ("goalkeeper_distribution", "opponent"),
}

MATCH_FLOW_PRESSURE_WEIGHTS = {
    "goal": 5.0,
    "scoring_opportunity": 3.0,
    "shot": 2.0,
    "counter_attack": 1.5,
    "corner": 1.0,
    "direct_free_kick": 0.8,
    "free_kick": 0.4,
    "cross": 0.25,
    "throw_in": 0.1,
    "goalkeeper_distribution": 0.08,
    "attacking_phase": 0.05,
}


@dataclass(frozen=True)
class XmlProfile:
    path: Path
    kind: str
    team: str
    instances: int
    player_events: int
    mapped_team_events: int
    period_markers: int
    error: str = ""


def _instances(path: Path) -> list[dict]:
    root = read_xml(path)
    rows = []
    for instance in root.findall(".//instance"):
        code = (instance.findtext("code") or "").strip()
        start = float(instance.findtext("start") or 0)
        end = float(instance.findtext("end") or 0)
        labels = [
            (node.text or "").strip()
            for node in instance.findall(".//text")
            if (node.text or "").strip()
        ]
        rows.append({"code": code, "start": start, "end": end, "labels": labels})
    return rows


def profile_xml(path: Path) -> XmlProfile:
    try:
        rows = _instances(path)
    except Exception as exc:
        return XmlProfile(
            path=path,
            kind="invalid_xml",
            team="",
            instances=0,
            player_events=0,
            mapped_team_events=0,
            period_markers=0,
            error=f"{type(exc).__name__}: {exc}",
        )
    player_events = sum(bool(PLAYER_CODE.fullmatch(row["code"])) for row in rows)
    mapped_team_events = sum(
        label in LABEL_MAP for row in rows for label in row["labels"]
    )
    period_markers = sum(
        label in PERIOD_LABELS for row in rows for label in row["labels"]
    )
    team_codes = Counter(
        row["code"]
        for row in rows
        if row["code"] and row["code"] != "Offsets" and not PLAYER_CODE.fullmatch(row["code"])
    )
    team = team_codes.most_common(1)[0][0] if team_codes else ""

    if player_events:
        kind = "scoring_event_xml" if period_markers else "player_event_xml"
    elif mapped_team_events and team:
        kind = "team_event_xml"
    elif rows and all(not row["labels"] for row in rows):
        kind = "effective_time_xml"
    else:
        kind = "unknown_xml"
    return XmlProfile(
        path=path,
        kind=kind,
        team=team,
        instances=len(rows),
        player_events=player_events,
        mapped_team_events=mapped_team_events,
        period_markers=period_markers,
    )


def discover_exports(input_dir: Path) -> list[XmlProfile]:
    return [profile_xml(path) for path in sorted(input_dir.rglob("*.xml"))]


def inventory_source_files(input_dir: Path) -> list[dict]:
    """Create a content-addressed inventory without changing vendor files."""
    inventory = []
    for path in sorted(candidate for candidate in input_dir.rglob("*") if candidate.is_file()):
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        inventory.append({
            "relative_path": path.relative_to(input_dir).as_posix(),
            "extension": path.suffix.lower(),
            "size_bytes": path.stat().st_size,
            "sha256": digest.hexdigest(),
        })
    return inventory


def _period_anchors(team_files: list[Path]) -> dict[str, float]:
    observed = defaultdict(list)
    for path in team_files:
        for row in _instances(path):
            for label in row["labels"]:
                if label in PERIOD_LABELS:
                    observed[label].append(row["start"])
    return {label: min(values) for label, values in observed.items()}


def _clock(start: float, anchors: dict[str, float]) -> tuple[int, float]:
    first_start = anchors.get("First half start", 0.0)
    second_start = anchors.get("Second half start")
    if second_start is not None and start >= second_start:
        return 2, 45.0 + max(0.0, start - second_start) / 60.0
    return 1, max(0.0, start - first_start) / 60.0


def merge_team_event_pair(team_files: list[Path], slug: str) -> tuple[list[dict], dict]:
    """Merge two mirrored team XMLs into one canonical, source-traceable stream."""
    if len(team_files) != 2:
        raise ValueError(f"Expected exactly two team-event XML files; found {len(team_files)}")

    profiles = [profile_xml(path) for path in team_files]
    teams = [profile.team for profile in profiles]
    if not all(teams) or len(set(teams)) != 2:
        raise ValueError(f"Team-event files must identify two distinct teams; found {teams}")

    anchors = _period_anchors(team_files)
    merged = {}
    unmapped = Counter()
    observations = 0

    for path, perspective_team in zip(team_files, teams):
        opponent = next(team for team in teams if team != perspective_team)
        for row in _instances(path):
            for label in row["labels"]:
                if label in PERIOD_LABELS:
                    continue
                mapping = LABEL_MAP.get(label)
                if mapping is None:
                    unmapped[label] += 1
                    continue
                event_type, relation = mapping
                actor_team = perspective_team if relation == "self" else opponent
                half, match_minute = _clock(row["start"], anchors)
                key = (row["start"], row["end"], event_type, actor_team)
                event = merged.setdefault(key, {
                    "event_id": hashlib.sha256(
                        f"{slug}|{row['start']}|{row['end']}|{event_type}|{actor_team}".encode("utf-8")
                    ).hexdigest()[:20],
                    "slug": slug,
                    "event_type": event_type,
                    "team": actor_team,
                    "start_seconds": row["start"],
                    "end_seconds": row["end"],
                    "half": half,
                    "match_minute": round(match_minute, 3),
                    "perspectives": set(),
                    "raw_labels": set(),
                    "source_files": set(),
                })
                event["perspectives"].add(perspective_team)
                event["raw_labels"].add(label)
                event["source_files"].add(path.name)
                observations += 1

    events = []
    for event in merged.values():
        event["perspectives"] = sorted(event["perspectives"])
        event["raw_labels"] = sorted(event["raw_labels"])
        event["source_files"] = sorted(event["source_files"])
        events.append(event)
    events.sort(key=lambda row: (row["start_seconds"], row["end_seconds"], row["event_type"], row["team"]))

    summary = {
        "teams": teams,
        "source_observations": observations,
        "canonical_events": len(events),
        "mirrored_events": sum(len(event["perspectives"]) == 2 for event in events),
        "event_types": dict(Counter(event["event_type"] for event in events)),
        "events_by_team": dict(Counter(event["team"] for event in events)),
        "unmapped_labels": dict(unmapped),
        "period_anchors": anchors,
    }
    return events, summary


def build_match_flow_snapshot(events: list[dict], summary: dict, slug: str) -> dict:
    """Aggregate canonical two-team events into reviewed five-minute pressure windows."""
    teams = summary.get("teams") or []
    if len(teams) != 2:
        raise ValueError(f"Match Flow requires two teams; found {teams}")

    end_minute = max(90.0, max((float(event.get("match_minute") or 0) for event in events), default=90.0))
    bin_count = max(18, math.ceil(end_minute / 5))
    bins = [
        {"start": index * 5, "home": 0.0, "away": 0.0, "event_counts": {}}
        for index in range(bin_count)
    ]
    goals = []

    for event in events:
        minute = max(0.0, float(event.get("match_minute") or 0))
        index = min(bin_count - 1, int(minute // 5))
        event_type = event.get("event_type") or "unknown"
        weight = MATCH_FLOW_PRESSURE_WEIGHTS.get(event_type, 0.0)
        side = "home" if event.get("team") == teams[0] else "away"
        bins[index][side] = round(bins[index][side] + weight, 2)
        count_key = f"{side}:{event_type}"
        bins[index]["event_counts"][count_key] = bins[index]["event_counts"].get(count_key, 0) + 1
        if event_type == "goal":
            goals.append({"minute": minute, "team": event.get("team")})

    for item in bins:
        highlights = sorted(item.pop("event_counts").items(), key=lambda pair: (-pair[1], pair[0]))[:3]
        item["note"] = " · ".join(
            f"{key.split(':', 1)[0].title()} {event_type.replace('_', ' ')} ×{count}"
            for key, count in highlights
            for event_type in [key.split(':', 1)[1]]
        ) or "No canonical team events"

    return {
        "version": "canonical_team_events_v1",
        "slug": slug,
        "home_team": teams[0],
        "away_team": teams[1],
        "window_minutes": 5,
        "pressure_weights": MATCH_FLOW_PRESSURE_WEIGHTS,
        "bins": bins,
        "goals": goals,
        "coverage": {
            "canonical_events": summary.get("canonical_events", len(events)),
            "mirrored_events": summary.get("mirrored_events", 0),
            "unmapped_labels": len(summary.get("unmapped_labels") or {}),
        },
    }


def write_events(path: Path, events: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "event_id", "slug", "event_type", "team", "start_seconds",
        "end_seconds", "half", "match_minute", "perspectives",
        "raw_labels", "source_files",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for event in events:
            writer.writerow({
                **event,
                "perspectives": json.dumps(event["perspectives"]),
                "raw_labels": json.dumps(event["raw_labels"]),
                "source_files": json.dumps(event["source_files"]),
            })


def write_rows(path: Path, rows: list[dict]) -> None:
    """Write parser dictionaries without requiring pandas."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        if not fieldnames:
            return
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                key: json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else value
                for key, value in row.items()
            })


def _roster_match_summary(profile: XmlProfile, roster: dict[str, set[str]]) -> dict:
    matched = 0
    for row in _instances(profile.path):
        match = PLAYER_CODE_PARTS.fullmatch(row["code"])
        if not match:
            continue
        jersey, name = match.groups()
        if normalize_player_name(name) in roster.get(jersey, set()):
            matched += 1
    return {
        "file": profile.path.name,
        "player_events": profile.player_events,
        "roster_matched_events": matched,
        "roster_match_ratio": matched / profile.player_events if profile.player_events else 0.0,
    }


def validate_scoring_candidate(profiles: list[XmlProfile], roster_path: Path) -> tuple[dict, dict | None]:
    scoring_files = [profile for profile in profiles if profile.kind == "scoring_event_xml"]
    if not scoring_files:
        return {
            "ready": False,
            "reason": "missing player-coded Sportscode XML; do not publish COUG scores",
            "candidate_files": [],
        }, None
    if not roster_path.exists():
        return {
            "ready": False,
            "reason": f"player-coded XML found but roster is missing: {roster_path}",
            "candidate_files": [profile.path.name for profile in scoring_files],
        }, None

    roster = load_cofc_roster(roster_path)
    evaluations = [_roster_match_summary(profile, roster) for profile in scoring_files]
    viable = [item for item in evaluations if item["roster_matched_events"] > 0]
    if not viable:
        return {
            "ready": False,
            "reason": "player-coded XML found but no candidate matched the season roster",
            "candidate_files": [profile.path.name for profile in scoring_files],
            "candidate_evaluations": evaluations,
        }, None

    best_quality = max(
        (item["roster_match_ratio"], item["roster_matched_events"])
        for item in viable
    )
    selected = [
        item for item in viable
        if (item["roster_match_ratio"], item["roster_matched_events"]) == best_quality
    ]
    if len(selected) != 1:
        return {
            "ready": False,
            "reason": f"found {len(selected)} equally strong roster-matched scoring candidates; staff selection required",
            "candidate_files": [profile.path.name for profile in scoring_files],
            "candidate_evaluations": evaluations,
        }, None

    selected_name = selected[0]["file"]
    scoring_file = next(profile for profile in scoring_files if profile.path.name == selected_name)

    parsed = parse_sportscode(scoring_file.path, roster_path=roster_path)
    player_events = parsed["player_events"]
    roster_players = {event["name"] for event in player_events}
    status = {
        "ready": bool(player_events),
        "reason": (
            "roster-filtered scoring parse passed; review counts before loading"
            if player_events
            else "player-coded XML parsed but no events matched the roster"
        ),
        "candidate_files": [profile.path.name for profile in scoring_files],
        "candidate_evaluations": evaluations,
        "selected_file": scoring_file.path.name,
        "roster": str(roster_path),
        "roster_players": len(roster_players),
        "scoring_events": len(player_events),
        "all_player_events": len(parsed["all_player_events"]),
        "team_events": len(parsed["team_events"]),
    }
    return status, parsed


def build_intake_report(input_dir: Path, slug: str) -> tuple[dict, list[dict]]:
    profiles = discover_exports(input_dir)
    source_manifest = inventory_source_files(input_dir)
    team_profiles = [profile for profile in profiles if profile.kind == "team_event_xml"]
    distinct_teams = {profile.team for profile in team_profiles if profile.team}

    events = []
    analytics_reason = "requires exactly two complementary team-event XML files"
    analytics_ready = len(team_profiles) == 2 and len(distinct_teams) == 2
    team_summary = None
    if analytics_ready:
        events, team_summary = merge_team_event_pair([profile.path for profile in team_profiles], slug)
        analytics_reason = "paired team-event XMLs merged successfully"

    report = {
        "slug": slug,
        "input_dir": str(input_dir),
        "source_manifest": source_manifest,
        "scoring": {"ready": False, "reason": "not yet roster-validated"},
        "analytics": {"ready": analytics_ready, "reason": analytics_reason},
        "files": [
            {
                "name": profile.path.name,
                "relative_path": profile.path.relative_to(input_dir).as_posix(),
                "kind": profile.kind,
                "team": profile.team,
                "instances": profile.instances,
                "player_events": profile.player_events,
                "mapped_team_events": profile.mapped_team_events,
                "period_markers": profile.period_markers,
                "error": profile.error,
            }
            for profile in profiles
        ],
        "team_event_summary": team_summary,
    }
    return report, events


def build_validation_summary(report: dict) -> dict:
    invalid_xml = [row for row in report.get("files", []) if row.get("kind") == "invalid_xml"]
    unknown_xml = [row for row in report.get("files", []) if row.get("kind") == "unknown_xml"]
    unmapped = (report.get("team_event_summary") or {}).get("unmapped_labels") or {}
    source_count = len(report.get("source_manifest") or [])

    blocking = []
    attention = []
    if source_count == 0:
        blocking.append("No source files were found.")
    if invalid_xml:
        blocking.append(f"{len(invalid_xml)} XML file(s) could not be read.")
    if unknown_xml:
        attention.append(f"{len(unknown_xml)} XML file(s) need classification.")
    if unmapped:
        attention.append(f"{len(unmapped)} Wyscout label(s) are not mapped yet.")
    if not report.get("analytics", {}).get("ready"):
        attention.append(report.get("analytics", {}).get("reason", "Match analytics are not ready."))
    if not report.get("scoring", {}).get("ready"):
        attention.append(report.get("scoring", {}).get("reason", "Player scoring is not ready."))

    has_usable_output = bool(
        report.get("analytics", {}).get("ready") or report.get("scoring", {}).get("ready")
    )
    if blocking:
        status = "blocked"
    elif has_usable_output:
        status = "ready_for_staff_review"
    else:
        status = "incomplete"
    return {
        "status": status,
        "source_files": source_count,
        "blocking_issues": blocking,
        "items_for_review": attention,
        "staff_approval_required": True,
        "published": False,
    }


def render_validation_report(report: dict) -> str:
    validation = report["validation"]
    lines = [
        f"# Match intake review: {report['slug']}",
        "",
        f"**Status:** `{validation['status']}`",
        "",
        "This bundle has not been published. Staff approval is required.",
        "",
        "## Readiness",
        "",
        f"- Match analytics: {'ready' if report['analytics']['ready'] else 'not ready'} — {report['analytics']['reason']}",
        f"- COUG player scoring: {'ready' if report['scoring']['ready'] else 'not ready'} — {report['scoring']['reason']}",
        f"- Source files inventoried: {validation['source_files']}",
        "",
    ]
    if validation["blocking_issues"]:
        lines.extend(["## Blocking issues", ""])
        lines.extend(f"- {item}" for item in validation["blocking_issues"])
        lines.append("")
    if validation["items_for_review"]:
        lines.extend(["## Items for staff review", ""])
        lines.extend(f"- {item}" for item in validation["items_for_review"])
        lines.append("")
    lines.extend([
        "## Source files",
        "",
        "| File | Size (bytes) | SHA-256 |",
        "|---|---:|---|",
    ])
    lines.extend(
        f"| `{item['relative_path']}` | {item['size_bytes']} | `{item['sha256']}` |"
        for item in report.get("source_manifest", [])
    )
    lines.append("")
    return "\n".join(lines)


def build_approval_template(report: dict, report_path: Path) -> dict:
    """Create a locked-down-by-default staff approval record."""
    digest = hashlib.sha256(report_path.read_bytes()).hexdigest()
    return {
        "schema_version": 1,
        "match_slug": report["slug"],
        "season": str(report["season"]),
        "intake_report_sha256": digest,
        "reviewed_by": "",
        "reviewed_at": "",
        "approvals": {
            "source_archive": False,
            "match_analytics": False,
            "coug_scoring": False,
        },
        "notes": "",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True, help="Folder containing loose vendor exports")
    parser.add_argument("--season", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--roster", type=Path, default=None, help="Season roster CSV used for scoring validation")
    parser.add_argument("--metadata", type=Path, default=None, help="Optional match metadata JSON")
    parser.add_argument("--dry-run", action="store_true", help="Inspect and parse in memory without writing files")
    args = parser.parse_args()

    input_dir = args.input_dir.resolve()
    report, events = build_intake_report(input_dir, args.slug)
    profiles = discover_exports(input_dir)
    roster_path = args.roster or (Path(__file__).resolve().parent / f"roster_{args.season}.csv")
    scoring_status, scoring_data = validate_scoring_candidate(profiles, roster_path.resolve())
    report["scoring"] = scoring_status
    report["season"] = str(args.season)
    if args.metadata:
        metadata = json.loads(args.metadata.read_text(encoding="utf-8"))
        if not isinstance(metadata, dict):
            raise ValueError("Match metadata must be a JSON object")
        report["metadata"] = metadata
    report["validation"] = build_validation_summary(report)
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.dry_run:
        return

    output_dir = args.output_dir or (
        get_source_paths().parsed_outputs_dir / str(args.season) / args.slug
    )
    output_dir = output_dir.resolve()
    if output_dir == input_dir or input_dir in output_dir.parents:
        raise ValueError("Output directory must not be inside the source directory")
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"{args.slug}_intake_report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    (output_dir / f"{args.slug}_validation_report.md").write_text(
        render_validation_report(report),
        encoding="utf-8",
    )
    (output_dir / f"{args.slug}_approval.json").write_text(
        json.dumps(build_approval_template(report, report_path), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    if events:
        write_events(output_dir / f"{args.slug}_canonical_team_events.csv", events)
        flow = build_match_flow_snapshot(events, report["team_event_summary"], args.slug)
        (output_dir / f"{args.slug}_match_flow.json").write_text(
            json.dumps(flow, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    if scoring_data:
        write_rows(output_dir / f"{args.slug}_players.csv", scoring_data["player_events"])
        write_rows(output_dir / f"{args.slug}_all_player_events.csv", scoring_data["all_player_events"])
        write_rows(output_dir / f"{args.slug}_sportscode_team_events.csv", scoring_data["team_events"])
    print(f"Prepared intake outputs: {output_dir}")


if __name__ == "__main__":
    main()
