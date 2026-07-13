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
    python pipeline/ingestion/inventory_sources.py --season 2025 --require-spiideo
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from dotenv import load_dotenv

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
    sportscode_source: str
    player_events_source: str
    team_events_source: str
    effective_time_source: str
    wyscout_pdf_source: str
    spiideo_source: str
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


def get_client_or_none():
    load_dotenv()
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        return None
    try:
        from supabase import create_client
    except ImportError:
        return None
    return create_client(url, key)


def fetch_source_file_rows(season: str) -> dict[tuple[str, str], dict]:
    client = get_client_or_none()
    if client is None:
        return {}
    try:
        response = (
            client.table("source_file")
            .select("match_slug,source_type,storage_bucket,storage_path,upload_status,parse_status")
            .eq("season", str(season))
            .eq("is_active", True)
            .execute()
        )
    except Exception as exc:
        print(f"Warning: could not fetch source_file rows: {exc}", file=sys.stderr)
        return {}
    rows = {}
    for row in response.data or []:
        key = (str(row.get("match_slug") or ""), str(row.get("source_type") or ""))
        if key[0] and key[1]:
            rows[key] = row
    return rows


def source_status(local_exists: bool, storage_row: dict | None) -> str:
    if local_exists:
        return "local+storage" if storage_row else "local"
    if storage_row:
        status = storage_row.get("upload_status") or "registered"
        return "storage" if status == "uploaded" else f"storage_{status}"
    return "missing"


def inventory_match(
    season: str,
    slug: str,
    require_spiideo: bool = False,
    source_file_rows: dict[tuple[str, str], dict] | None = None,
) -> MatchInventory:
    paths = get_source_paths()
    match_dir = paths.matches_dir / str(season) / slug
    output_dir = paths.parsed_outputs_dir / str(season) / slug
    legacy_output_dir = paths.legacy_data_outputs_dir / str(season) / slug

    source_file_rows = source_file_rows or {}

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

    sportscode_source = source_status(sportscode, source_file_rows.get((slug, "sportscode")))
    player_events_source = source_status(player_events, source_file_rows.get((slug, "player_events")))
    team_events_source = source_status(team_events, source_file_rows.get((slug, "team_events")))
    effective_time_source = source_status(effective_time, source_file_rows.get((slug, "effective_time")))
    wyscout_pdf_source = source_status(wyscout_pdf, source_file_rows.get((slug, "pdf_report")))
    spiideo_source = "local" if spiideo else "missing"

    players_csv = (output_dir / f"{slug}_players.csv").exists()
    minutes_csv = (output_dir / f"{slug}_minutes.csv").exists()
    attributed_csv = (output_dir / f"{slug}_attributed.csv").exists()
    coug_scores_csv = (output_dir / f"{slug}_coug_scores.csv").exists()

    notes = []
    if not match_dir.exists() and not any(
        source != "missing"
        for source in [
            sportscode_source, player_events_source, team_events_source,
            effective_time_source, wyscout_pdf_source, spiideo_source,
        ]
    ):
        notes.append("missing match dir")
    if sportscode_source != "missing" and player_events_source == "missing":
        notes.append("sportscode present; player-events XML missing/optional")
    if sportscode_source == "missing":
        notes.append("missing sportscode XML")
    if effective_time_source == "missing":
        notes.append("missing effective-time XML")
    if wyscout_pdf_source == "missing":
        notes.append("missing Wyscout PDF report")
    if require_spiideo and spiideo_source == "missing":
        notes.append("missing Spiideo XML")
    if legacy_output_dir.exists() and not output_dir.exists():
        notes.append("only legacy pipeline/data/outputs exists")

    if sportscode_source != "missing" and (players_csv or output_dir.exists()):
        status = "ready_or_parsed"
    elif sportscode_source != "missing":
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
        sportscode_source=sportscode_source,
        player_events_source=player_events_source,
        team_events_source=team_events_source,
        effective_time_source=effective_time_source,
        wyscout_pdf_source=wyscout_pdf_source,
        spiideo_source=spiideo_source,
        parsed_output_dir=output_dir.exists(),
        legacy_output_dir=legacy_output_dir.exists(),
        players_csv=players_csv,
        minutes_csv=minutes_csv,
        attributed_csv=attributed_csv,
        coug_scores_csv=coug_scores_csv,
        source_status=status,
        notes="; ".join(notes),
    )


def _manifest_slugs(manifest_path: Path, season: str) -> list[str]:
    if not manifest_path.exists():
        return []
    with manifest_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return sorted(
            row["slug"]
            for row in reader
            if str(row.get("season", "")).strip() == str(season)
            and row.get("slug")
        )


def _dir_has_source_files(path: Path) -> bool:
    return path.exists() and any(child.is_file() for child in path.rglob("*"))


def find_slugs(
    season: str,
    slug: str | None,
    include_empty_dirs: bool = False,
) -> list[str]:
    paths = get_source_paths()
    if slug:
        return [slug]
    season_dir = paths.matches_dir / str(season)

    slugs = set(_manifest_slugs(paths.manifest_path, season))
    if season_dir.exists():
        for path in season_dir.iterdir():
            if not path.is_dir() or path.name.startswith("."):
                continue
            if include_empty_dirs or _dir_has_source_files(path):
                slugs.add(path.name)
    return sorted(slugs)


def find_slugs_from_storage(source_file_rows: dict[tuple[str, str], dict]) -> list[str]:
    return sorted({slug for slug, _ in source_file_rows.keys() if slug})


def print_table(rows: list[MatchInventory]) -> None:
    cols = [
        "slug", "source_status", "sportscode_xml", "player_events_xml",
        "effective_time_xml", "wyscout_pdf_report", "spiideo_xml",
        "sportscode_source", "player_events_source", "effective_time_source", "wyscout_pdf_source",
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
    parser.add_argument(
        "--require-spiideo",
        action="store_true",
        help="Treat missing Spiideo files as a current-source warning instead of future/optional.",
    )
    parser.add_argument(
        "--include-empty-dirs",
        action="store_true",
        help="Include empty match directories that are not listed in the manifest.",
    )
    args = parser.parse_args()

    source_file_rows = fetch_source_file_rows(args.season)
    slugs = set(find_slugs(args.season, args.slug, include_empty_dirs=args.include_empty_dirs))
    if not args.slug:
        slugs.update(find_slugs_from_storage(source_file_rows))
    slugs = sorted(slugs)

    rows = [
        inventory_match(args.season, slug, require_spiideo=args.require_spiideo, source_file_rows=source_file_rows)
        for slug in slugs
    ]
    if not rows:
        raise SystemExit(f"No matches found for season {args.season}")

    if args.csv:
        writer = csv.DictWriter(sys.stdout, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))
    else:
        print_table(rows)


if __name__ == "__main__":
    main()
