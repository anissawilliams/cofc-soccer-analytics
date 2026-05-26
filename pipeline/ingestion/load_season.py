"""
load_season.py
==============
CofC Soccer Analytics — Season Batch Loader
Loops over all slugs in the matches manifest and calls load_match()
for each one. Tracks results and writes a load report.

Usage:
    python load_season.py --season 2025
    python load_season.py --season 2025 --dry-run
    python load_season.py --season 2025 --slug 2025-11-02_uncw   # single match
    python load_season.py --season 2025 --since 2025-10-01       # only matches after date

Manifest format (matches/matches_manifest.csv):
    slug,session_type,competition,venue,season,cofc_goals,opp_goals
    2025-11-02_uncw,match,CAA,Patriots Point,2025,2,1
    2025-10-15_campbell,match,CAA,Patriots Point,2025,1,1
    ...
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime, date

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

PIPELINE_ROOT = Path(os.environ.get(
    "PIPELINE_ROOT",
    Path(__file__).resolve().parent.parent   # ingestion/ → pipeline/
))

MANIFESTS_DIR = PIPELINE_ROOT / "data" / "manifests"
OUTPUTS_DIR   = PIPELINE_ROOT / "outputs"
REPORTS_DIR   = PIPELINE_ROOT / "outputs" / "reports"

def manifest_path(season: str) -> Path:
    return MANIFESTS_DIR / f"matches_manifest_{season}.csv"


# ── Load report ───────────────────────────────────────────────────────────────

class LoadReport:
    def __init__(self, season: str, dry_run: bool):
        self.season   = season
        self.dry_run  = dry_run
        self.started  = datetime.now()
        self.results: list[dict] = []

    def record(self, slug: str, status: str, error: str | None = None):
        self.results.append({
            "slug":      slug,
            "status":    status,   # success | skipped | error
            "error":     error,
            "timestamp": datetime.now().isoformat(),
        })

    def summary(self) -> str:
        total    = len(self.results)
        success  = sum(1 for r in self.results if r["status"] == "success")
        skipped  = sum(1 for r in self.results if r["status"] == "skipped")
        errors   = sum(1 for r in self.results if r["status"] == "error")
        elapsed  = (datetime.now() - self.started).seconds

        lines = [
            "",
            "=" * 60,
            f"  LOAD SEASON REPORT — {self.season}"
            + (" [DRY RUN]" if self.dry_run else ""),
            "=" * 60,
            f"  Total matches:  {total}",
            f"  ✅ Success:      {success}",
            f"  ⏭️  Skipped:      {skipped}",
            f"  ❌ Errors:       {errors}",
            f"  Elapsed:        {elapsed}s",
            "=" * 60,
        ]

        if errors:
            lines.append("\n  Failed slugs:")
            for r in self.results:
                if r["status"] == "error":
                    lines.append(f"    {r['slug']}: {r['error']}")

        return "\n".join(lines)

    def save(self):
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        ts   = self.started.strftime("%Y%m%d_%H%M%S")
        path = REPORTS_DIR / f"load_report_{self.season}_{ts}.csv"
        pd.DataFrame(self.results).to_csv(path, index=False)
        log.info(f"  Report saved: {path}")
        return path


# ── Manifest helpers ──────────────────────────────────────────────────────────

def load_manifest(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Manifest not found: {path}\n"
            "Create matches/matches_manifest.csv with columns:\n"
            "  slug, session_type, competition, venue, season, cofc_goals, opp_goals"
        )
    df = pd.read_csv(path)
    required = ["slug", "season"]
    missing  = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Manifest missing required columns: {missing}")
    return df


def filter_manifest(
    df: pd.DataFrame,
    season: str,
    slug_filter: str | None,
    since: str | None,
) -> pd.DataFrame:
    df = df[df["season"].astype(str) == season].copy()

    if slug_filter:
        df = df[df["slug"] == slug_filter]
        if df.empty:
            raise ValueError(f"Slug '{slug_filter}' not found in manifest for season {season}")

    if since:
        since_date = date.fromisoformat(since)
        df["_date"] = pd.to_datetime(
            df["slug"].str.extract(r"^(\d{4}-\d{2}-\d{2})")[0]
        ).dt.date
        df = df[df["_date"] >= since_date].drop(columns=["_date"])

    return df.reset_index(drop=True)


# ── Season loader ─────────────────────────────────────────────────────────────

def load_season(
    season: str,
    dry_run: bool = False,
    slug_filter: str | None = None,
    since: str | None = None,
    skip_existing: bool = True,
):
    # Import here so load_match.py can also be used standalone
    try:
        from load_match import load_match
    except ImportError:
        log.error("load_match.py not found. Make sure it is in the same directory.")
        sys.exit(1)

    manifest = load_manifest(manifest_path(season))
    queue    = filter_manifest(manifest, season, slug_filter, since)
    report   = LoadReport(season, dry_run)

    log.info(f"Season {season} — {len(queue)} match(es) to process")
    if dry_run:
        log.info("[DRY RUN MODE — no writes to Supabase]")

    for i, row in queue.iterrows():
        slug = row["slug"]
        log.info(f"\n[{i+1}/{len(queue)}] {slug}")

        # Check output directory exists
        output_dir = OUTPUTS_DIR / season / slug
        if not output_dir.exists():
            log.warning(f"  Output directory missing: {output_dir} — skipping")
            report.record(slug, "skipped", "output directory not found")
            continue

        # Check if any files exist
        csvs = list(output_dir.glob("*.csv"))
        if not csvs:
            log.warning(f"  No CSV files in {output_dir} — skipping")
            report.record(slug, "skipped", "no CSV files found")
            continue

        try:
            load_match(slug=slug, season=season, dry_run=dry_run)
            report.record(slug, "success" if not dry_run else "skipped")
        except Exception as e:
            log.error(f"  ❌ Error loading {slug}: {e}")
            report.record(slug, "error", str(e))
            # Continue to next match rather than aborting the whole season
            continue

    # Print and save report
    print(report.summary())
    if not dry_run:
        report.save()


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load all matches for a season into Supabase")
    parser.add_argument("--season",  default="2025",  help="Season year e.g. 2025")
    parser.add_argument("--slug",    default=None,    help="Load a single slug only")
    parser.add_argument("--since",   default=None,    help="Only load matches on/after this date (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="Report what would happen without writing")
    parser.add_argument("--no-skip", action="store_true", help="Load even if session already exists")
    args = parser.parse_args()

    load_season(
        season=args.season,
        dry_run=args.dry_run,
        slug_filter=args.slug,
        since=args.since,
        skip_existing=not args.no_skip,
    )
