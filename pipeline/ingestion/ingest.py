"""
ingest.py — COUGS Ingestion CLI
================================
Detects which files are present in a match folder,
selects the appropriate mode, and runs ingestion.

Usage:
    # Single match
    python ingest.py --match-dir matches/2025/2025-11-02_uncw/

    # Full season (all folders in a directory)
    python ingest.py --season-dir matches/2025/ --manifest matches_manifest.csv

    # Force a specific mode
    python ingest.py --match-dir matches/2025/2025-11-02_uncw/ --mode wyscout_only

    # Skip blob upload (dev/test)
    python ingest.py --match-dir matches/2025/2025-11-02_uncw/ --no-upload

    # Manual offset override
    python ingest.py --match-dir matches/2025/2025-11-02_uncw/ --offset 385
"""

import argparse
import sys
from pathlib import Path

from manifest import load_manifest, infer_slug_from_folder

# Mode imports
sys.path.insert(0, str(Path(__file__).parent))
from modes import wyscout_only, spiideo_only, full_pipeline


# ── Mode detection ────────────────────────────────────────────

def detect_mode(match_dir: Path) -> str:
    """
    Detect which ingestion mode to use based on files present.
    Returns: 'full', 'wyscout_only', or 'spiideo_only'
    """
    slug         = match_dir.name
    has_wyscout  = (match_dir / f"{slug}_cfc_sportscode.xml").exists()
    has_spiideo  = (match_dir / f"{slug}_spiideo.xml").exists()

    if has_wyscout and has_spiideo:
        return "full"
    elif has_wyscout:
        return "wyscout_only"
    elif has_spiideo:
        return "spiideo_only"
    else:
        raise FileNotFoundError(
            f"No recognizable XML files found in {match_dir}\n"
            f"Expected: {slug}_cfc_sportscode.xml or {slug}_spiideo.xml"
        )


# ── Single match ingestion ────────────────────────────────────

def ingest_match(
    match_dir:     Path,
    manifest:      dict,
    mode_override: str  = None,
    upload_blobs:  bool = True,
    manual_offset: int  = None,
):
    slug = infer_slug_from_folder(match_dir)

    # Get metadata from manifest
    if slug not in manifest:
        print(f"  ⚠️  No manifest entry for '{slug}' — skipping")
        print(f"     Add a row to matches_manifest.csv for this match")
        return None

    meta = manifest[slug]
    mode = mode_override or detect_mode(match_dir)

    print(f"\n{'='*60}")
    print(f"  {slug}")
    print(f"  Mode detected: {mode.upper()}")
    print(f"{'='*60}")

    if mode == "full":
        return full_pipeline.run(
            match_dir=match_dir,
            meta=meta,
            upload_blobs=upload_blobs,
            manual_offset=manual_offset,
        )
    elif mode == "wyscout_only":
        return wyscout_only.run(
            match_dir=match_dir,
            meta=meta,
            upload_blobs=upload_blobs,
        )
    elif mode == "spiideo_only":
        return spiideo_only.run(
            match_dir=match_dir,
            meta=meta,
            upload_blobs=upload_blobs,
        )
    else:
        raise ValueError(f"Unknown mode: {mode}")


# ── Season ingestion ──────────────────────────────────────────

def ingest_season(
    season_dir:    Path,
    manifest:      dict,
    mode_override: str  = None,
    upload_blobs:  bool = True,
):
    """Ingest all match folders in a season directory."""
    match_dirs = sorted([
        d for d in season_dir.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    ])

    print(f"\nFound {len(match_dirs)} match folders in {season_dir}")

    results = {"success": [], "skipped": [], "failed": []}

    for match_dir in match_dirs:
        try:
            match_id = ingest_match(
                match_dir=match_dir,
                manifest=manifest,
                mode_override=mode_override,
                upload_blobs=upload_blobs,
            )
            if match_id:
                results["success"].append(match_dir.name)
            else:
                results["skipped"].append(match_dir.name)
        except Exception as e:
            print(f"\n  ❌ Failed: {match_dir.name}")
            print(f"     {e}")
            results["failed"].append(match_dir.name)

    # Summary
    print(f"\n{'='*60}")
    print(f"Season ingestion complete")
    print(f"  ✓ Success:  {len(results['success'])}")
    print(f"  ⚠️  Skipped: {len(results['skipped'])}")
    print(f"  ❌ Failed:  {len(results['failed'])}")
    if results["failed"]:
        print(f"\n  Failed matches:")
        for f in results["failed"]:
            print(f"    - {f}")
    print(f"{'='*60}\n")
    return results


# ── CLI ───────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="COUGS XML Ingestion",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--match-dir",
        type=Path,
        help="Path to a single match folder"
    )
    group.add_argument(
        "--season-dir",
        type=Path,
        help="Path to a season folder containing all match subfolders"
    )

    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("../data/manifests/matches_manifest.csv"),
        help="Path to matches_manifest.csv (default: matches_manifest.csv)"
    )
    parser.add_argument(
        "--mode",
        choices=["full", "wyscout_only", "spiideo_only"],
        default=None,
        help="Force a specific ingestion mode (auto-detected if not set)"
    )
    parser.add_argument(
        "--no-upload",
        action="store_true",
        help="Skip blob storage upload (useful for local testing)"
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=None,
        help="Manual timestamp offset in seconds (overrides auto-detection)"
    )

    args = parser.parse_args()

    # Load manifest
    if not args.manifest.exists():
        print(f"❌ Manifest not found: {args.manifest}")
        print("   Create matches_manifest.csv with match metadata")
        sys.exit(1)

    manifest = load_manifest(args.manifest)

    upload_blobs = not args.no_upload

    if args.match_dir:
        ingest_match(
            match_dir=args.match_dir,
            manifest=manifest,
            mode_override=args.mode,
            upload_blobs=upload_blobs,
            manual_offset=args.offset,
        )
    elif args.season_dir:
        ingest_season(
            season_dir=args.season_dir,
            manifest=manifest,
            mode_override=args.mode,
            upload_blobs=upload_blobs,
        )


if __name__ == "__main__":
    main()
