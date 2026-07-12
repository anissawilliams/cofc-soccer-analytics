#!/usr/bin/env python3
"""
inventory_sources.py
====================
Report which raw/source files and parsed outputs exist for each match.

This is intentionally read-only. Run it before parse/load/score steps when the
pipeline feels suspicious.

Examples:
    python pipeline/ingestion/inventory_sources.py --season 2025
    python pipeline/ingestion/inventory_sources.py --season 2025 --slug 2025-11-02_uncw
    python pipeline/ingestion/inventory_sources.py --season 2025 --csv
"""

from __future__ import annotations

import argparse
import csv
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from source_paths import get_source_paths


@dataclass
class MatchInventory:
    season: str
    slug: str
    match_dir: str
    sportscode_xml: bool
    player_events_xml: bool
    team_events_xml: bool
    effective_time_xml: bool
    wyscout_pdf_report: bool
    spiideo_xml: bool
    parsed_output_dir: bool
    legacy_output_dir: bool
    players_csv: bool
    minutes_csv: bool
    attributed_csv: bool
    coug_scores_csv: bool
    source_status: str
    notes: str


def _slug_pdf_key(slug: str) -> str:
    # 2025-11-02_uncw -> 20251102uncw
    return re.sub(r"[^a-z0-9]", "", slug.lower())


def _pdf_key(path: Path) -> str:
    # players_2025_11_02_UNCW.pdf -> 20251102uncw
    name = path.stem.lower().replace("players_", "")
    return re.sub(r"[^a-z0-9]", "", name)


def _has_pdf_for_slug(pdf_dir: Path, slug: str) -> bool:
    if not pdf_dir.exists():
        return False
    target = _slug_pdf_key(slug)
    for pdf in pdf_dir.glob("players_*.pdf"):
        if _pdf_key(pdf) == target:
            return True
    return False


def _exists_any(match_dir: Path, names: list[str], patterns: list[str] | None = None) -> bool:
    for name in names:
        if (match_dir / name).exists():
            return True
    for pattern in patterns or []:
        if any(match_dir.glob(pattern)):
            return True
    return False


def inventory_match(season: str, slug: str) -> MatchInventory:
    paths = get_source_paths()
    match_dir = paths.matches_dir / str(season) / slug
    output_dir = paths.parsed_outputs_dir / str(season) / slug
    legacy_output_dir = paths.legacy_data_outputs_dir / str(season) / slug

    sportscode = _exists_any(match_dir, [f"{slug}_cfc_sportscode.xml"])
    player_events = _exists_any(
        match_dir,
        [f"{slug}_cfc_player_events.xml"],
        patterns=["*player-events*.xml", "*player_events*.xml"],
    )
    team_events = _exists_any(match_dir, [f"{slug}_cfc_team_events.xml"])
    effective_time = _exists_any(match_dir, [f"{slug}_cfc_effective_time.xml"])
    spiideo = _exists_any(match_dir, [f"{slug}_spiideo.xml"])
    wyscout_pdf = _has_pdf_for_slug(paths.wyscout_pdf_dir, slug)

    players_csv = (output_dir / f"{slug}_players.csv").exists()
    minutes_csv = (output_dir / f"{slug}_minutes.csv").exists()
    attributed_csv = (output_dir / f"{slug}_attributed.csv").exists()
    coug_scores_csv = (output_dir / f"{slug}_coug_scores.csv").exists()

    notes = []
    if not match_dir.exists():
        notes.append("missing match dir")
    if sportscode and not player_events:
        notes.append("sportscode present; player-events XML missing/optional")
    if not sportscode:
        notes.append("missing sportscode XML")
    if not effective_time:
        notes.append("missing effective-time XML")
    if not wyscout_pdf:
        notes.append("missing Wyscout PDF report")
    if not spiideo:
        notes.append("Spiideo absent/future source")
    if legacy_output_dir.exists() and not output_dir.exists():
        notes.append("only legacy pipeline/data/outputs exists")

    if sportscode and (players_csv or output_dir.exists()):
        status = "ready_or_parsed"
    elif sportscode:
        status = "raw_ready"
    else:
        status = "incomplete"

    return MatchInventory(
        season=str(season),
        slug=slug,
        match_dir=str(match_dir),
        sportscode_xml=sportscode,
        player_events_xml=player_events,
        team_events_xml=team_events,
        effective_time_xml=effective_time,
        wyscout_pdf_report=wyscout_pdf,
        spiideo_xml=spiideo,
        parsed_output_dir=output_dir.exists(),
        legacy_output_dir=legacy_output_dir.exists(),
        players_csv=players_csv,
        minutes_csv=minutes_csv,
        attributed_csv=attributed_csv,
        coug_scores_csv=coug_scores_csv,
        source_status=status,
        notes="; ".join(notes),
    )


def find_slugs(season: str, slug: str | None) -> list[str]:
    paths = get_source_paths()
    if slug:
        return [slug]
    season_dir = paths.matches_dir / str(season)
    if not season_dir.exists():
        raise FileNotFoundError(f"Match season directory not found: {season_dir}")
    return sorted(p.name for p in season_dir.iterdir() if p.is_dir() and not p.name.startswith("."))


def print_table(rows: list[MatchInventory]) -> None:
    cols = [
        "slug", "source_status", "sportscode_xml", "player_events_xml",
        "effective_time_xml", "wyscout_pdf_report", "spiideo_xml",
        "players_csv", "minutes_csv", "attributed_csv", "coug_scores_csv", "notes",
    ]
    widths = {col: max(len(col), *(len(str(getattr(row, col))) for row in rows)) for col in cols}
    header = "  ".join(col.ljust(widths[col]) for col in cols)
    print(header)
    print("  ".join("-" * widths[col] for col in cols))
    for row in rows:
        print("  ".join(str(getattr(row, col)).ljust(widths[col]) for col in cols))


def main() -> None:
    parser = argparse.ArgumentParser(description="Inventory raw source files and parsed outputs")
    parser.add_argument("--season", default="2025", help="Season folder, e.g. 2025")
    parser.add_argument("--slug", default=None, help="Single match slug")
    parser.add_argument("--csv", action="store_true", help="Emit CSV instead of a terminal table")
    args = parser.parse_args()

    rows = [inventory_match(args.season, slug) for slug in find_slugs(args.season, args.slug)]
    if args.csv:
        writer = csv.DictWriter(__import__("sys").stdout, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))
    else:
        print_table(rows)


if __name__ == "__main__":
    main()
