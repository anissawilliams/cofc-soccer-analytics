#!/usr/bin/env python3
"""
batch_parse.py — Re-parse all CofC matches in one pass
=======================================================
Replaces the notebook's cell-by-cell workflow with a single
local script. No Colab, no Drive sync, no manual MATCH_SLUG editing.

Usage:
    # Parse all matches in a season
    python batch_parse.py --season 2025

    # Parse a single match
    python batch_parse.py --season 2025 --slug 2025-11-02_uncw

    # Dry run (show what would be parsed, don't write files)
    python batch_parse.py --season 2025 --dry-run

Expects this directory structure (same as the notebook):
    PROJECT_ROOT/
    ├── src/
    │   └── parse_wyscout.py  (the FIXED version with jersey+name filter)
    ├── roster_2025.csv
    ├── matches/
    │   └── 2025/
    │       ├── 2025-08-22_south_carolina/
    │       │   └── 2025-08-22_south_carolina_cfc_sportscode.xml
    │       ├── 2025-11-02_uncw/
    │       │   └── 2025-11-02_uncw_cfc_sportscode.xml
    │       └── ...
    └── outputs/
        └── 2025/
            └── (generated here)
"""

import sys
import argparse
import ast
import csv
import warnings
from pathlib import Path
from collections import defaultdict

import pandas as pd

warnings.filterwarnings("ignore")


# ── Defaults ─────────────────────────────────────────────────────────────────
from source_paths import get_source_paths
from source_files import resolve_wyscout_file

PATHS = get_source_paths()
DEFAULT_PROJECT_ROOT = PATHS.pipeline_root
DEFAULT_ROSTER = PATHS.roster_path


def setup_imports(project_root: Path):
    """Import parser helpers from this ingestion package directory."""
    ingestion_path = str(Path(__file__).resolve().parent)
    if ingestion_path not in sys.path:
        sys.path.insert(0, ingestion_path)

    from parse_wyscout import parse_sportscode, parse_effective_time, estimate_minutes_played
    return parse_sportscode, parse_effective_time, estimate_minutes_played


def find_matches(project_root: Path, season: str, slug: str = None) -> list[Path]:
    """Find all match folders for a season, or a single one if slug is given."""
    matches_dir = get_source_paths().matches_dir / str(season)
    if not matches_dir.exists() and not slug:
        print(f"❌ Matches directory not found: {matches_dir}")
        sys.exit(1)

    if slug:
        match_dir = matches_dir / slug
        return [match_dir]

    dirs = sorted([
        d for d in matches_dir.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    ])
    print(f"Found {len(dirs)} match folders in {matches_dir}")
    return dirs


def parse_one_match(
    match_dir: Path,
    project_root: Path,
    roster_path: Path,
    parse_sportscode,
    season: str,
    dry_run: bool = False,
) -> dict:
    """Parse a single match folder and save clean CSVs. Returns summary dict."""
    slug = match_dir.name

    # Locate files. The resolver prefers local disk and can fall back to a
    # Supabase Storage-backed local cache when enabled.
    sportscode_source = resolve_wyscout_file(season, slug, "sportscode", required=False)
    spiideo_file    = match_dir / f"{slug}_spiideo.xml"

    if sportscode_source is None:
        return {"slug": slug, "status": "SKIPPED", "reason": "no sportscode XML"}
    sportscode_file = sportscode_source.path

    output_dir = get_source_paths().parsed_outputs_dir / str(season) / slug
    if dry_run:
        return {"slug": slug, "status": "DRY RUN", "reason": f"would write to {output_dir}"}

    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Parse ──────────────────────────────────────────────────────────────
    print(f"\nProcessing: {slug}")
    print("=" * 55)

    print("\n[1/2] Parsing Wyscout XML...")
    print(f"      Source: {sportscode_source.origin} | {sportscode_file}")
    wyscout_data = parse_sportscode(sportscode_file, roster_path=roster_path)
    df_players = pd.DataFrame(wyscout_data["player_events"])
    n_players = df_players["name"].nunique()
    n_events = len(df_players)
    print(f"      {n_events} player events | {n_players} players")

    # ── Save ───────────────────────────────────────────────────────────────
    print("\n[2/2] Saving CSVs...")
    players_path = output_dir / f"{slug}_players.csv"
    df_players.to_csv(players_path, index=False)
    print(f"      ✅ {players_path.name}")

    print()
    print("=" * 55)
    print(f"DONE — {slug}")
    print(f"  Players parsed:    {n_players}")
    print(f"  Events:            {n_events}")
    print(f"  Files saved to:    {output_dir}")
    print("=" * 55)

    return {
        "slug": slug,
        "status": "OK",
        "players": n_players,
        "events": n_events,
        "output": str(output_dir),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Batch re-parse all CofC matches with the fixed roster filter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--season", default="2025", help="Season folder name (default: 2025)")
    parser.add_argument("--slug", default=None, help="Single match slug to parse (omit for all)")
    parser.add_argument("--project-root", type=Path, default=DEFAULT_PROJECT_ROOT,
                        help=f"Project root (default: {DEFAULT_PROJECT_ROOT})")
    parser.add_argument("--roster", type=Path, default=DEFAULT_ROSTER,
                        help=f"Roster CSV path (default: {DEFAULT_ROSTER})")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be parsed without writing")
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    roster_path = args.roster if args.roster.is_absolute() else project_root / args.roster

    if not roster_path.exists():
        print(f"❌ Roster not found: {roster_path}")
        sys.exit(1)

    print(f"Project root: {project_root}")
    print(f"Roster:       {roster_path}")
    print()

    # Import the fixed parser
    parse_sportscode, parse_effective_time, estimate_minutes_played = setup_imports(project_root)

    # Find matches
    match_dirs = find_matches(project_root, args.season, args.slug)

    # Parse each
    results = []
    for match_dir in match_dirs:
        try:
            result = parse_one_match(
                match_dir=match_dir,
                project_root=project_root,
                roster_path=roster_path,
                parse_sportscode=parse_sportscode,
                season=args.season,
                dry_run=args.dry_run,
            )
            results.append(result)
        except Exception as e:
            print(f"\n❌ Failed: {match_dir.name} — {e}")
            results.append({"slug": match_dir.name, "status": "FAILED", "reason": str(e)})

    # ── Summary ────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"BATCH SUMMARY — {args.season}")
    print(f"{'='*60}")

    ok      = [r for r in results if r["status"] == "OK"]
    skipped = [r for r in results if r["status"] == "SKIPPED"]
    failed  = [r for r in results if r["status"] == "FAILED"]
    dry     = [r for r in results if r["status"] == "DRY RUN"]

    if dry:
        print(f"  Would parse: {len(dry)} matches")
        for r in dry:
            print(f"    {r['slug']}")
    else:
        print(f"  ✅ Success:  {len(ok)}")
        total_events = sum(r.get("events", 0) for r in ok)
        total_players = sum(r.get("players", 0) for r in ok)
        print(f"     Total events: {total_events} | Total player-matches: {total_players}")

    if skipped:
        print(f"  ⚠️  Skipped: {len(skipped)}")
        for r in skipped:
            print(f"    {r['slug']}: {r['reason']}")

    if failed:
        print(f"  ❌ Failed:  {len(failed)}")
        for r in failed:
            print(f"    {r['slug']}: {r['reason']}")

    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
