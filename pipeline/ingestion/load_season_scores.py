"""
load_season_scores.py
=====================
Loads season COUG score outputs into Supabase and refreshes the dashboard read
model after successful writes.

Load order per match:
  1. Session (upsert from manifest)
  2. Match   (upsert from manifest)
  3. Athletes (upsert by display_name)
  4. Stints  (insert into athlete_session_stint from minutes column)
  5. COUG scores (insert into coug_score table)

Usage:
    python load_season_scores.py --season 2025
    python load_season_scores.py --season 2025 --slug 2025-11-02_uncw
    python load_season_scores.py --season 2025 --dry-run

Environment (.env):
    SUPABASE_URL
    SUPABASE_SERVICE_KEY
    PROJECT_ROOT
"""

from __future__ import annotations

import os
import csv
import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime

import pandas as pd
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
PROJECT_ROOT  = Path(os.environ.get("PROJECT_ROOT", "."))
OUTPUTS_DIR   = PROJECT_ROOT / "pipeline" / "data" / "outputs"
MANIFEST_PATH = PROJECT_ROOT / "pipeline" / "data" / "manifests" / "matches_manifest.csv"
SKIP_FOLDERS  = {"catapult", "spiideo", "wyscout"}

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")


def get_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise EnvironmentError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def normalize(name: str) -> str:
    return " ".join(str(name).strip().lower().split())


# ── Manifest ──────────────────────────────────────────────────────────────────
def load_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        log.warning(f"Manifest not found: {MANIFEST_PATH}")
        return {}
    df = pd.read_csv(MANIFEST_PATH)
    return {row["slug"]: row.to_dict() for _, row in df.iterrows()}


# ── Session ───────────────────────────────────────────────────────────────────
def upsert_session(sb: Client, slug: str, manifest_row: dict, dry_run: bool) -> str:
    date_str    = slug.split("_")[0]
    competition = manifest_row.get("competition", "Unknown")
    venue       = manifest_row.get("venue", None)
    season      = str(manifest_row.get("season", date_str[:4]))

    existing = sb.table("session").select("id").eq("session_date", date_str).eq("competition", competition).execute()
    if existing.data:
        sid = existing.data[0]["id"]
        log.info(f"  Session exists: {sid}")
        return sid

    payload = {
        "session_date": date_str,
        "session_type": "match",
        "season":       season,
        "competition":  competition,
        "venue":        venue,
        "notes":        f"slug: {slug}",
    }
    if dry_run:
        log.info(f"  [DRY RUN] Would create session: {date_str} {competition}")
        return "dry-run-session-id"

    result = sb.table("session").insert(payload).execute()
    sid = result.data[0]["id"]
    log.info(f"  Created session: {sid}")
    return sid


# ── Match ─────────────────────────────────────────────────────────────────────
def upsert_match(sb: Client, session_id: str, slug: str, manifest_row: dict, dry_run: bool) -> str:
    existing = sb.table("match").select("id").eq("session_id", session_id).execute()
    if existing.data:
        mid = existing.data[0]["id"]
        log.info(f"  Match exists: {mid}")
        return mid

    # Get team IDs
    cofc_team = sb.table("team").select("id").eq("is_cofc", True).execute()
    cofc_id   = cofc_team.data[0]["id"] if cofc_team.data else None

    opponent  = str(manifest_row.get("opponent", "")).lower().replace(" ", "%")
    opp_team  = sb.table("team").select("id").filter("name", "ilike", f"%{opponent}%").execute()
    opp_id    = opp_team.data[0]["id"] if opp_team.data else None

    if not opp_id:
        log.warning(f"  Team not found for opponent '{manifest_row.get('opponent')}' — proceeding without away_team_id")

    gf = manifest_row.get("cofc_goals")
    ga = manifest_row.get("opp_goals")
    goals_for     = int(float(gf)) if gf != "" and gf is not None else None
    goals_against = int(float(ga)) if ga != "" and ga is not None else None

    result_str = None
    if goals_for is not None and goals_against is not None:
        result_str = "W" if goals_for > goals_against else ("L" if goals_for < goals_against else "D")

    venue    = manifest_row.get("venue", "")
    home_id  = cofc_id if "away" not in str(venue).lower() else opp_id
    away_id  = opp_id  if "away" not in str(venue).lower() else cofc_id

    payload = {
        "session_id":    session_id,
        "home_team_id":  home_id,
        "away_team_id":  away_id,
        "result":        result_str,
        "goals_for":     goals_for,
        "goals_against": goals_against,
    }

    if dry_run:
        log.info(f"  [DRY RUN] Would create match: {result_str} {goals_for}-{goals_against}")
        return "dry-run-match-id"

    result = sb.table("match").insert(payload).execute()
    mid = result.data[0]["id"]
    log.info(f"  Created match: {mid} ({result_str} {goals_for}-{goals_against})")
    return mid


# ── Athletes ──────────────────────────────────────────────────────────────────
def upsert_athletes(sb: Client, names: list[str], dry_run: bool) -> dict[str, str]:
    existing = sb.table("athlete").select("id, display_name, first_name, last_name").execute()
    athlete_map = {}

    for a in (existing.data or []):
        dn = normalize(a.get("display_name") or f"{a['first_name']} {a['last_name']}")
        athlete_map[dn] = a["id"]

    for name in names:
        norm = normalize(name)
        if norm in athlete_map:
            continue

        # Build first/last from display name (e.g. "L. Gill" → first="L.", last="Gill")
        parts = name.strip().split()
        first = parts[0] if parts else name
        last  = " ".join(parts[1:]) if len(parts) > 1 else ""

        if dry_run:
            log.info(f"  [DRY RUN] Would create athlete: {name}")
            athlete_map[norm] = f"dry-run-{norm}"
            continue

        result = sb.table("athlete").insert({
            "first_name":   first,
            "last_name":    last,
            "display_name": name,
            "status":       "active",
        }).execute()
        aid = result.data[0]["id"]
        athlete_map[norm] = aid
        log.info(f"  Created athlete: {name} ({aid})")

    return athlete_map


# ── Stints ───────────────────────────────────────────────────────────────────
def load_stints(
    sb: Client,
    session_id: str,
    scores_df: pd.DataFrame,
    athlete_map: dict,
    dry_run: bool,
):
    """
    Load athlete_session_stint rows from the minutes column in coug_scores.csv.
    One row per athlete per session.
    minutes column = total minutes played that match.
    """
    inserted = skipped = 0

    for _, row in scores_df.iterrows():
        norm       = normalize(str(row["player"]))
        athlete_id = athlete_map.get(norm)

        if not athlete_id:
            skipped += 1
            continue

        minutes = float(row.get("minutes", 0) or 0)
        if minutes <= 0:
            skipped += 1
            continue

        # Check for existing stint
        existing = sb.table("athlete_session_stint").select("id") \
            .eq("athlete_id", athlete_id) \
            .eq("session_id", session_id) \
            .execute()
        if existing.data:
            skipped += 1
            continue

        # Determine if starter (played >= 60 minutes)
        started = minutes >= 60

        # minutes_on = 0 (started from beginning assumed)
        # minutes_off = minutes played (when they came off)
        payload = {
            "athlete_id":   athlete_id,
            "session_id":   session_id,
            "minutes_on":   0,
            "minutes_off":  int(round(minutes)),
            "started":      started,
            "participated": True,
        }

        if dry_run:
            log.info(f"  [DRY RUN] Would insert stint: {row['player']} {minutes:.0f} min")
            inserted += 1
            continue

        sb.table("athlete_session_stint").insert(payload).execute()
        inserted += 1

    log.info(f"  Stints: {inserted} inserted | {skipped} skipped")


# ── COUG Scores ───────────────────────────────────────────────────────────────
def load_coug_scores(
    sb: Client,
    session_id: str,
    scores_df: pd.DataFrame,
    athlete_map: dict,
    weight_version_id: str,
    dry_run: bool,
):
    inserted = skipped = 0

    for _, row in scores_df.iterrows():
        norm       = normalize(str(row["player"]))
        athlete_id = athlete_map.get(norm)

        if not athlete_id:
            log.warning(f"  No athlete_id for '{row['player']}' — skipping")
            skipped += 1
            continue

        # Check if score already exists for this athlete + session
        existing = sb.table("coug_score").select("id").eq("athlete_id", athlete_id).eq("session_id", session_id).execute()
        if existing.data:
            skipped += 1
            continue

        payload = {
            "athlete_id":       athlete_id,
            "session_id":       session_id,
            "weight_version_id": weight_version_id,
            "aset_score":       float(row.get("aset", 0) or 0),
            "peak_score":       float(row.get("peak", 0) or 0),
            "set_piece_score":  0.0,
            "positional_score": 0.0,
            "load_score":       0.0,
            "total_score":      float(row.get("total", 0) or 0),
            "score_type":       "match",
            "data_source_path": "csv",
            "calculated_at":    datetime.now().isoformat(),
        }

        if dry_run:
            log.info(f"  [DRY RUN] Would insert score: {row['player']} total={row.get('total', 0):.2f}")
            inserted += 1
            continue

        sb.table("coug_score").insert(payload).execute()
        inserted += 1

    log.info(f"  COUG scores: {inserted} inserted | {skipped} skipped")


# ── Get weight version ────────────────────────────────────────────────────────
def get_weight_version_id(sb: Client, version: str = "trial_1") -> str:
    result = sb.table("metric_weight").select("id").eq("version", version).limit(1).execute()
    if result.data:
        return result.data[0]["id"]
    raise ValueError(f"Weight version '{version}' not found in metric_weight table")


# ── Per-match loader ──────────────────────────────────────────────────────────
def load_match_scores(sb: Client, slug: str, season: str, manifest: dict, weight_version_id: str, dry_run: bool):
    log.info(f"\n{'='*55}")
    log.info(f"  {slug}")
    log.info(f"{'='*55}")

    output_dir  = OUTPUTS_DIR / season / slug
    scores_path = output_dir / f"{slug}_coug_scores.csv"

    if not scores_path.exists():
        log.warning(f"  No coug_scores.csv found — skipping")
        return False

    scores_df   = pd.read_csv(scores_path)
    manifest_row = manifest.get(slug, {})

    if not manifest_row:
        log.warning(f"  No manifest entry for {slug} — session/match metadata will be minimal")

    # 1. Session
    session_id = upsert_session(sb, slug, manifest_row, dry_run)

    # 2. Match
    match_id = upsert_match(sb, session_id, slug, manifest_row, dry_run)

    # 3. Athletes
    names       = scores_df["player"].dropna().tolist()
    athlete_map = upsert_athletes(sb, names, dry_run)

    # 4. Stints (minutes played per athlete)
    load_stints(sb, session_id, scores_df, athlete_map, dry_run)

    # 5. COUG scores
    load_coug_scores(sb, session_id, scores_df, athlete_map, weight_version_id, dry_run)

    log.info(f"  ✅ Done: {slug}")
    return True


# ── Season loader ─────────────────────────────────────────────────────────────
def load_season(
    season: str,
    slug_filter: str | None,
    dry_run: bool,
    refresh_read_model: bool = True,
):
    sb       = get_client() if not dry_run else get_client()  # need client even for dry run for lookups
    manifest = load_manifest()

    # Get weight version once
    weight_version_id = get_weight_version_id(sb, "trial_1")
    log.info(f"Using weight version: trial_1 ({weight_version_id})")

    # Find all match folders
    season_dir = OUTPUTS_DIR / season
    if not season_dir.exists():
        raise FileNotFoundError(f"Season directory not found: {season_dir}")

    slugs = sorted([
        d.name for d in season_dir.iterdir()
        if d.is_dir() and d.name not in SKIP_FOLDERS
    ])

    if slug_filter:
        slugs = [s for s in slugs if s == slug_filter]
        if not slugs:
            raise ValueError(f"Slug '{slug_filter}' not found in {season_dir}")

    log.info(f"\nSeason {season} — {len(slugs)} match(es) to process")
    if dry_run:
        log.info("[DRY RUN — no writes to Supabase]\n")

    success = fail = skip = 0
    for slug in slugs:
        try:
            result = load_match_scores(sb, slug, season, manifest, weight_version_id, dry_run)
            if result:
                success += 1
            else:
                skip += 1
        except Exception as e:
            log.error(f"  ❌ Error loading {slug}: {e}")
            fail += 1
            continue

    log.info(f"\n{'='*55}")
    log.info(f"SEASON LOAD COMPLETE — {season}")
    log.info(f"  ✅ Success: {success}")
    log.info(f"  ⏭️  Skipped: {skip}")
    log.info(f"  ❌ Failed:  {fail}")
    log.info(f"{'='*55}")

    if not dry_run and success > 0 and refresh_read_model:
        log.info(f"Refreshing dashboard read model for {season}...")
        try:
            from pipeline.analytics.build_dashboard_read_model import (
                refresh_dashboard_read_model,
            )

            path = refresh_dashboard_read_model(season)
            log.info(f"  ✅ Dashboard read model published: {path}")
        except Exception as exc:
            raise RuntimeError(
                f"Scores loaded, but the {season} dashboard read model failed to refresh"
            ) from exc


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Load season COUG scores and refresh dashboard read models"
    )
    parser.add_argument("--season",  default="2025")
    parser.add_argument("--slug",    default=None, help="Load single match only")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--no-refresh-read-model",
        action="store_true",
        help="Skip the automatic dashboard JSON refresh after database writes",
    )
    args = parser.parse_args()

    load_season(
        season=args.season,
        slug_filter=args.slug,
        dry_run=args.dry_run,
        refresh_read_model=not args.no_refresh_read_model,
    )
