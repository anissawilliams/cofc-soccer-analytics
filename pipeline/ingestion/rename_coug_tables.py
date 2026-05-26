"""
rename_coug_tables.py
=====================
One-time script to normalize coug_table CSV filenames
to the convention: coug_table_YYYY_MM_DD_Opponent.csv

Run from the coug_table/ directory:
    python rename_coug_tables.py --dir pipeline/outputs/2025/coug_table
    python rename_coug_tables.py --dir pipeline/outputs/2025/coug_table --dry-run

Known issues this fixes:
  - coug_table_2025_11_02_UNCW_Seahawks.csv  → coug_table_2025_11_02_UNCW.csv
  - coug_table_ELON_match.csv                → needs date — will flag for manual fix
"""

import argparse
import re
from pathlib import Path


# Map messy opponent strings → clean canonical name
# Add entries here if more edge cases appear
OPPONENT_ALIASES = {
    "SouthCarolina":   "SouthCarolina",
    "NorthCarolina":   "NorthCarolina",
    "USCUpstate":      "USCUpstate",
    "GeorgiaSouthern": "GeorgiaSouthern",
    "WilliamMary":     "WilliamMary",
    "NorthFlorida":    "NorthFlorida",
    "UNCW_Seahawks":   "UNCW",          # strip nickname
    "UNCW":            "UNCW",
    "Elon":            "Elon",
    "Campbell":        "Campbell",
    "Wofford":         "Wofford",
    "Davidson":        "Davidson",
    "Furman":          "Furman",
    "Winthrop":        "Winthrop",
}

# Files that are missing dates — flag for manual resolution
# Format: {current_stem: (YYYY, MM, DD, opponent)}
MANUAL_FIXES = {
    "coug_table_ELON_match": None,   # date unknown — needs manual fix
}


def parse_filename(stem: str) -> tuple[str, str, str, str] | None:
    """
    Try to extract (YYYY, MM, DD, opponent) from a coug_table stem.
    Returns None if it can't be parsed confidently.
    """
    # Standard pattern: coug_table_YYYY_MM_DD_Opponent
    m = re.match(r"coug_table_(\d{4})_(\d{2})_(\d{2})_(.+)$", stem)
    if m:
        yyyy, mm, dd, opp_raw = m.groups()
        opp = OPPONENT_ALIASES.get(opp_raw, opp_raw)
        return yyyy, mm, dd, opp
    return None


def build_target_name(yyyy: str, mm: str, dd: str, opp: str) -> str:
    return f"coug_table_{yyyy}_{mm}_{dd}_{opp}.csv"


def run(directory: Path, dry_run: bool):
    csvs = sorted(directory.glob("coug_table_*.csv"))

    if not csvs:
        print(f"No coug_table_*.csv files found in {directory}")
        return

    print(f"{'DRY RUN — ' if dry_run else ''}Scanning {len(csvs)} files in {directory}\n")

    renamed = skipped = flagged = 0

    for f in csvs:
        stem = f.stem

        # Check manual fixes first
        if stem in MANUAL_FIXES:
            fix = MANUAL_FIXES[stem]
            if fix is None:
                print(f"  ⚠️  NEEDS MANUAL FIX: {f.name}")
                print(f"       Date unknown — rename manually to coug_table_YYYY_MM_DD_Opponent.csv")
                flagged += 1
                continue
            else:
                yyyy, mm, dd, opp = fix
        else:
            parsed = parse_filename(stem)
            if parsed is None:
                print(f"  ❓ Cannot parse: {f.name} — skipping")
                flagged += 1
                continue
            yyyy, mm, dd, opp = parsed

        target_name = build_target_name(yyyy, mm, dd, opp)
        target_path = f.parent / target_name

        if f.name == target_name:
            print(f"  ✅ OK:      {f.name}")
            skipped += 1
            continue

        print(f"  ✏️  RENAME:  {f.name}")
        print(f"       →      {target_name}")

        if not dry_run:
            if target_path.exists():
                print(f"       ⚠️  Target already exists — skipping to avoid overwrite")
                flagged += 1
                continue
            f.rename(target_path)
            renamed += 1
        else:
            renamed += 1

    print(f"\n{'─'*50}")
    print(f"  {'Would rename' if dry_run else 'Renamed'}:  {renamed}")
    print(f"  Already OK:  {skipped}")
    print(f"  Flagged:     {flagged}")
    if dry_run:
        print("\n  Run without --dry-run to apply changes.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir",     required=True, help="Path to coug_table/ directory")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    run(Path(args.dir), dry_run=args.dry_run)