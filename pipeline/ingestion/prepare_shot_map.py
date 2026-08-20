#!/usr/bin/env python3
"""Validate a reviewed shot CSV and publish a compact dashboard snapshot."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


VALID_OUTCOMES = {"goal", "on_goal", "wide", "blocked", "on_post"}


def _number(value: str | None) -> float | None:
    text = (value or "").strip()
    return float(text) if text else None


def _integer(value: str | None, field: str) -> int:
    try:
        return int(float((value or "").strip()))
    except ValueError as exc:
        raise ValueError(f"{field} must be numeric") from exc


def build_snapshot(
    csv_path: Path,
    home_team: str,
    away_team: str,
    source_label: str,
    source_file: str = "",
) -> dict:
    teams = {home_team, away_team}
    shots = []
    seen_ids = set()
    total_overrides = {team: {"xg": None, "psxg": None} for team in teams}

    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        for row_number, row in enumerate(csv.DictReader(handle), start=2):
            shot_id = (row.get("shot_id") or "").strip()
            team = (row.get("team") or "").strip()
            outcome = (row.get("outcome") or "").strip().lower()
            if not shot_id or shot_id in seen_ids:
                raise ValueError(f"row {row_number}: shot_id is missing or duplicated")
            if team not in teams:
                raise ValueError(f"row {row_number}: team must be {home_team!r} or {away_team!r}")
            if outcome not in VALID_OUTCOMES:
                raise ValueError(f"row {row_number}: unsupported outcome {outcome!r}")

            x = _number(row.get("x"))
            y = _number(row.get("y"))
            if x is None or y is None or not 0 <= x <= 100 or not 0 <= y <= 100:
                raise ValueError(f"row {row_number}: x and y must be between 0 and 100")

            xg = _number(row.get("xg"))
            psxg = _number(row.get("psxg"))
            minute = _number(row.get("minute"))
            if minute is None or minute < 0:
                raise ValueError(f"row {row_number}: minute must be zero or greater")

            for metric, column in (("xg", "team_xg_total"), ("psxg", "team_psxg_total")):
                override = _number(row.get(column))
                if override is not None:
                    existing = total_overrides[team][metric]
                    if existing is not None and existing != override:
                        raise ValueError(f"row {row_number}: conflicting {column} for {team}")
                    total_overrides[team][metric] = override

            seen_ids.add(shot_id)
            shots.append({
                "shot_id": shot_id,
                "team": team,
                "sequence": _integer(row.get("sequence"), f"row {row_number} sequence"),
                "player": (row.get("player") or "").strip(),
                "minute": minute,
                "minute_label": (row.get("minute_label") or str(int(minute))).strip(),
                "outcome": outcome,
                "shot_type": (row.get("shot_type") or "").strip(),
                "xg": xg,
                "xg_display": (row.get("xg_display") or (f"{xg:.2f}" if xg is not None else "")).strip() or None,
                "psxg": psxg,
                "psxg_display": (row.get("psxg_display") or (f"{psxg:.2f}" if psxg is not None else "")).strip() or None,
                "x": round(x, 2),
                "y": round(y, 2),
            })

    summaries = {}
    for team in (home_team, away_team):
        team_shots = [shot for shot in shots if shot["team"] == team]
        numeric_xg = round(sum(shot["xg"] or 0 for shot in team_shots), 2)
        numeric_psxg = round(sum(shot["psxg"] or 0 for shot in team_shots), 2)
        summaries[team] = {
            "shots": len(team_shots),
            "xg": total_overrides[team]["xg"] if total_overrides[team]["xg"] is not None else numeric_xg,
            "on_goal": sum(shot["outcome"] in {"goal", "on_goal"} for shot in team_shots),
            "goals": sum(shot["outcome"] == "goal" for shot in team_shots),
            "big_chances": sum((shot["xg"] or 0) >= 0.25 for shot in team_shots),
            "psxg": total_overrides[team]["psxg"] if total_overrides[team]["psxg"] is not None else numeric_psxg,
        }

    return {
        "version": "reviewed_shot_csv_v1",
        "home_team": home_team,
        "away_team": away_team,
        "coordinate_system": {
            "x": "0 left touchline to 100 right touchline",
            "y": "0 own goal line to 100 opponent goal line",
            "precision": "reviewed normalized source coordinates",
        },
        "team_summaries": summaries,
        "shots": sorted(shots, key=lambda shot: (shot["minute"], shot["team"], shot["sequence"])),
        "coverage": {
            "shots": len(shots),
            "located_shots": len(shots),
            "xg_labeled_shots": sum(bool(shot["xg"] is not None or shot["xg_display"]) for shot in shots),
            "psxg_labeled_shots": sum(bool(shot["psxg"] is not None or shot["psxg_display"]) for shot in shots),
        },
        "source": {
            "label": source_label,
            "file": source_file or csv_path.name,
            "reviewed": True,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", type=Path, required=True)
    parser.add_argument("--home-team", required=True)
    parser.add_argument("--away-team", required=True)
    parser.add_argument("--source-label", required=True)
    parser.add_argument("--source-file", default="")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    snapshot = build_snapshot(
        args.input_csv,
        args.home_team,
        args.away_team,
        args.source_label,
        args.source_file,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Published {len(snapshot['shots'])} reviewed shots: {args.output}")


if __name__ == "__main__":
    main()
