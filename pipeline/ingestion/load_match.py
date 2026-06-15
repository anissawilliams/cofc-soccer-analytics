"""
load_match.py
=============
CofC Soccer Analytics — Match Data Loader (Stage 2)
Loads all CSV outputs for a given match slug into Supabase.

Load order for a slug:
  1. session + match  (from manifest or filename)
  2. athletes         (upsert from minutes.csv + players.csv)
  3. stints           (from minutes.csv)
  4. athlete_event    (from attributed.csv → XML pipeline, highest trust)
  5. athlete_event    (from players.csv → Wyscout events, fills gaps)
  6. athlete_event    (from scored CSV → raw Wyscout stats only, lowest trust)

Scores (coug_score) are intentionally NOT loaded here.
Scoring runs separately once metric weights are coach-confirmed.

Usage:
    python load_match.py --slug 2025-11-02_uncw --season 2025
    python load_match.py --slug 2025-11-02_uncw --season 2025 --dry-run

Environment variables (or .env file):
    SUPABASE_URL
    SUPABASE_SERVICE_KEY
"""

import os
import re
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime

import pandas as pd
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "pipeline/"))
OUTPUTS_DIR  = PROJECT_ROOT / "pipeline" / "data" / "outputs"
MATCHES_DIR  = PROJECT_ROOT / "matches"
MANIFEST_PATH = PROJECT_ROOT / "pipeline" / "data" / "manifests" / "matches_manifest.csv"

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

# Source priority: higher = more trusted. XML pipeline wins over CSV summary.
SOURCE_PRIORITY = {
    "xml_attributed": 3,
    "xml_players":    2,
    "csv_summary":    1,
}

# Fuzzy match confidence threshold (0-100). Below this = log for manual review.
FUZZY_THRESHOLD = 80

# ── Supabase client ───────────────────────────────────────────────────────────

def get_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise EnvironmentError(
            "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.\n"
            "Add them to your .env file or Colab secrets."
        )
    return create_client(SUPABASE_URL, SUPABASE_KEY)


# ── Athlete matching ──────────────────────────────────────────────────────────

def normalize_name(name: str) -> str:
    """Lowercase, strip extra whitespace."""
    return " ".join(name.strip().lower().split())


def fuzzy_match_athlete(name: str, athletes: list[dict]) -> tuple[dict | None, int]:
    """
    Try to match a name string against existing athlete rows.
    Returns (best_match_dict, confidence_score).
    Tries exact display_name match first, then fuzzy on last name + first initial.
    """
    try:
        from rapidfuzz import process, fuzz
    except ImportError:
        # Fallback: exact match only
        norm = normalize_name(name)
        for a in athletes:
            if normalize_name(a.get("display_name", "")) == norm:
                return a, 100
            full = normalize_name(f"{a['first_name']} {a['last_name']}")
            if full == norm:
                return a, 100
        return None, 0

    norm = normalize_name(name)
    candidates = {}
    for a in athletes:
        candidates[a["id"]] = normalize_name(
            a.get("display_name") or f"{a['first_name']} {a['last_name']}"
        )

    if not candidates:
        return None, 0

    result = process.extractOne(norm, candidates, scorer=fuzz.token_sort_ratio)
    if result is None:
        return None, 0

    best_id, score, _ = result
    if score >= FUZZY_THRESHOLD:
        match = next(a for a in athletes if a["id"] == best_id)
        return match, score
    return None, score


def build_display_name(full_name: str) -> str:
    """
    'Julian Jordheim' → 'J. Jordheim'
    Handles multi-word last names gracefully.
    """
    parts = full_name.strip().split()
    if len(parts) < 2:
        return full_name
    return f"{parts[0][0]}. {' '.join(parts[1:])}"


# ── Session / match ───────────────────────────────────────────────────────────

def parse_slug(slug: str) -> tuple[str, str]:
    """
    '2025-11-02_uncw' → ('2025-11-02', 'uncw')
    """
    parts = slug.split("_", 1)
    if len(parts) != 2:
        raise ValueError(f"Cannot parse slug: {slug}")
    return parts[0], parts[1]


def load_or_create_session(
    sb: Client,
    slug: str,
    manifest_row: dict | None,
    scored_df: pd.DataFrame | None,
    dry_run: bool,
) -> str:
    """
    Upsert a session row. Returns session_id (UUID string).
    Priority: manifest > scored CSV filename > slug parsing.
    """
    date_str, opponent_slug = parse_slug(slug)

    # Pull metadata from whatever source is available
    if manifest_row:
        season      = str(manifest_row.get("season", "2025"))
        competition = manifest_row.get("competition", "unknown")
        venue       = manifest_row.get("venue", None)
        session_type = manifest_row.get("session_type", "match")
    else:
        season       = date_str[:4]
        competition  = "unknown"
        venue        = None
        session_type = "match"

    # Check if session already exists for this date + competition
    existing = (
        sb.table("session")
        .select("id")
        .eq("session_date", date_str)
        .eq("competition", competition)
        .execute()
    )
    if existing.data:
        session_id = existing.data[0]["id"]
        log.info(f"  Session exists: {session_id}")
        return session_id

    payload = {
        "session_date": date_str,
        "session_type": session_type,
        "season":       season,
        "competition":  competition,
        "venue":        venue,
        "notes":        f"slug: {slug}",
    }

    if dry_run:
        log.info(f"  [DRY RUN] Would insert session: {payload}")
        return "dry-run-session-id"

    result = sb.table("session").insert(payload).execute()
    session_id = result.data[0]["id"]
    log.info(f"  Created session: {session_id}")
    return session_id


def load_or_create_match(
    sb: Client,
    session_id: str,
    slug: str,
    scored_df: pd.DataFrame | None,
    manifest_row: dict | None,
    dry_run: bool,
) -> str:
    """
    Upsert a match row linked to session_id. Returns match_id.
    """
    existing = (
        sb.table("match")
        .select("id")
        .eq("session_id", session_id)
        .execute()
    )
    if existing.data:
        match_id = existing.data[0]["id"]
        log.info(f"  Match exists: {match_id}")
        return match_id

    # Resolve team IDs
    _, opponent_slug = parse_slug(slug)
    cofc_team   = sb.table("team").select("id").eq("is_cofc", True).execute()
    opp_team    = (
        sb.table("team")
        .select("id")
        .ilike("short_name", f"%{opponent_slug}%")
        .execute()
    )

    cofc_id = cofc_team.data[0]["id"] if cofc_team.data else None
    opp_id  = opp_team.data[0]["id"]  if opp_team.data  else None

    if not opp_id:
        log.warning(f"  Team not found for slug '{opponent_slug}' — match.away_team_id will be null")

    # Goals from manifest
    goals_for = None
    goals_against = None
    if manifest_row:
        gf = manifest_row.get("cofc_goals")
        ga = manifest_row.get("opp_goals")
        if gf != "" and ga != "" and gf is not None and ga is not None:
            goals_for = int(float(gf))
            goals_against = int(float(ga))

    result_str = None
    if goals_for is not None and goals_against is not None:
        if goals_for > goals_against:
            result_str = "W"
        elif goals_for < goals_against:
            result_str = "L"
        else:
            result_str = "D"

    payload = {
        "session_id":    session_id,
        "home_team_id":  cofc_id,
        "away_team_id":  opp_id,
        "result":        result_str,
        "goals_for":     goals_for,
        "goals_against": goals_against,
    }

    if dry_run:
        log.info(f"  [DRY RUN] Would insert match: {payload}")
        return "dry-run-match-id"

    result = sb.table("match").insert(payload).execute()
    match_id = result.data[0]["id"]
    log.info(f"  Created match: {match_id}")
    return match_id


# ── Athletes ──────────────────────────────────────────────────────────────────

def upsert_athletes(
    sb: Client,
    names: list[str],
    dry_run: bool,
) -> dict[str, str]:
    """
    For each name string, find or create an athlete row.
    Returns {normalized_name: athlete_id}.
    Logs anything that couldn't be confidently matched for manual review.
    """
    existing = sb.table("athlete").select("*").execute().data
    mapping  = {}
    unmatched = []

    for name in names:
        if not name or pd.isna(name):
            continue

        norm = normalize_name(name)
        match, score = fuzzy_match_athlete(name, existing)

        if match:
            if score < 100:
                log.info(f"  Fuzzy match: '{name}' → '{match['display_name']}' (score={score})")
            mapping[norm] = match["id"]
            continue

        # No match — create new athlete
        parts = name.strip().split()
        if len(parts) < 2:
            log.warning(f"  Cannot parse name '{name}' — skipping")
            unmatched.append(name)
            continue

        first = parts[0]
        last  = " ".join(parts[1:])
        display = build_display_name(name)

        payload = {
            "first_name":    first,
            "last_name":     last,
            "display_name":  display,
            "status":        "active",
        }

        if dry_run:
            log.info(f"  [DRY RUN] Would create athlete: {payload}")
            mapping[norm] = f"dry-run-{norm}"
            continue

        result = sb.table("athlete").insert(payload).execute()
        new_id = result.data[0]["id"]
        existing.append(result.data[0])   # keep local cache fresh
        mapping[norm] = new_id
        log.info(f"  Created athlete: {display} ({new_id})")

    if unmatched:
        log.warning(f"  ⚠️  Unmatched names (manual review needed): {unmatched}")

    return mapping


# ── Stints ────────────────────────────────────────────────────────────────────

def load_stints(
    sb: Client,
    session_id: str,
    minutes_df: pd.DataFrame,
    athlete_map: dict[str, str],
    dry_run: bool,
):
    """Load athlete_session_stint rows from minutes CSV."""
    inserted = 0
    for _, row in minutes_df.iterrows():
        norm = normalize_name(str(row["player_name"]))
        athlete_id = athlete_map.get(norm)
        if not athlete_id:
            log.warning(f"  Stint: no athlete_id for '{row['player_name']}'")
            continue

        # Check if stint already exists
        existing = (
            sb.table("athlete_session_stint")
            .select("id")
            .eq("athlete_id", athlete_id)
            .eq("session_id", session_id)
            .execute()
        )
        if existing.data:
            continue

        mins = float(row.get("estimated_minutes", 90))
        payload = {
            "athlete_id":   athlete_id,
            "session_id":   session_id,
            "minutes_on":   0,
            "minutes_off":  int(mins),
            "started":      mins > 45,
            "participated": True,
        }

        if not dry_run:
            sb.table("athlete_session_stint").insert(payload).execute()
        inserted += 1

    log.info(f"  Stints loaded: {inserted}")


# ── Athlete events ────────────────────────────────────────────────────────────

def get_or_create_source(sb: Client, platform: str, label: str, priority: int, dry_run: bool) -> str:
    existing = (
        sb.table("data_source")
        .select("id")
        .eq("platform", platform)
        .eq("name", label)
        .execute()
    )
    if existing.data:
        return existing.data[0]["id"]

    payload = {
        "name":            label,
        "platform":        platform,
        "source_type":     "file",
        "source_priority": priority,
    }
    if dry_run:
        return f"dry-run-source-{platform}"
    result = sb.table("data_source").insert(payload).execute()
    return result.data[0]["id"]


def load_attributed_events(
    sb: Client,
    session_id: str,
    attributed_df: pd.DataFrame,
    athlete_map: dict[str, str],
    metric_map: dict[str, str],
    source_id: str,
    dry_run: bool,
):
    """
    Load events from the attributed CSV (highest trust — XML pipeline output).
    Each row = one COUG event tagged by Spiideo, attributed to a player.
    """
    # Normalize Spiideo codes via spiideo_tag_map
    tag_map_rows = sb.table("spiideo_tag_map").select("*").execute().data
    tag_lookup   = {
        r["raw_code"].lower(): r for r in tag_map_rows
    }

    inserted = skipped_unscoreable = skipped_no_athlete = skipped_no_metric = 0

    for _, row in attributed_df.iterrows():
        raw_code = str(row.get("subtype", "")).strip()
        tag_entry = tag_lookup.get(raw_code.lower())

        # Skip non-scorable tags
        if tag_entry and not tag_entry["is_scorable"]:
            skipped_unscoreable += 1
            continue

        # Resolve athlete
        player_name = row.get("player_name")
        if not player_name or pd.isna(player_name):
            skipped_no_athlete += 1
            continue
        norm = normalize_name(str(player_name))
        athlete_id = athlete_map.get(norm)
        if not athlete_id:
            log.warning(f"  Attributed: no athlete_id for '{player_name}'")
            skipped_no_athlete += 1
            continue

        # Resolve metric
        metric_id = tag_entry["metric_id"] if tag_entry else None
        if not metric_id:
            # Try direct name lookup as fallback
            metric_id = metric_map.get(normalize_name(raw_code))
        if not metric_id:
            log.warning(f"  Attributed: no metric for tag '{raw_code}'")
            skipped_no_metric += 1
            continue

        payload = {
            "athlete_id":         athlete_id,
            "session_id":         session_id,
            "metric_id":          metric_id,
            "source_id":          source_id,
            "raw_value":          1.0,
            "collection_method":  "manual",
            "manually_tagged":    True,
            "event_time":         float(row["spiideo_t"]) if pd.notna(row.get("spiideo_t")) else None,
            "raw_value_context":  {
                "minute":           row.get("minute"),
                "attribution_score": row.get("attribution_score"),
                "spiideo_code":     raw_code,
            },
        }

        if not dry_run:
            sb.table("athlete_event").insert(payload).execute()
        inserted += 1

    log.info(
        f"  Attributed events: {inserted} loaded | "
        f"{skipped_unscoreable} non-scorable | "
        f"{skipped_no_athlete} no athlete | "
        f"{skipped_no_metric} no metric"
    )


# Wyscout stat columns in scored CSV → metric name mapping
WYSCOUT_STAT_METRIC_MAP = {
    "goals":                "Goal (scorer)",
    "shots":                None,   # no direct metric — informational
    "shots_on_target":      "Shots on Target (FWD)",
    "key_passes":           None,
    "dribbles":             None,
    "duels_won":            None,
    "defensive_duels_won":  None,
    "interceptions":        "Possession Regain",
    "clearances":           "Clearance from Danger",
    "sliding_tackles":      None,
    "passes":               None,
    "passes_accurate":      None,
    "pass_accuracy_pct":    "Pass Success Rate (MID)",
    "progressive_passes":   "Advance",
}


def load_wyscout_stat_events(
    sb: Client,
    session_id: str,
    scored_df: pd.DataFrame,
    athlete_map: dict[str, str],
    metric_map: dict[str, str],
    source_id: str,
    dry_run: bool,
):
    """
    Load raw Wyscout stat columns from scored CSV as athlete_event rows.
    Skips scores (aset_score, peak_score etc.) — those are derived, not loaded.
    Only loads columns that map to a metric_definition.
    """
    inserted = skipped = 0

    for _, row in scored_df.iterrows():
        norm = normalize_name(str(row["player"]))
        athlete_id = athlete_map.get(norm)
        if not athlete_id:
            log.warning(f"  Stats: no athlete_id for '{row['player']}'")
            continue

        for col, metric_name in WYSCOUT_STAT_METRIC_MAP.items():
            if metric_name is None:
                continue
            val = row.get(col)
            if pd.isna(val) or float(val) == 0:
                continue

            metric_id = metric_map.get(normalize_name(metric_name))
            if not metric_id:
                skipped += 1
                continue

            # Check for existing event (avoid double-load if XML already loaded it)
            existing = (
                sb.table("athlete_event")
                .select("id, source_id")
                .eq("athlete_id", athlete_id)
                .eq("session_id", session_id)
                .eq("metric_id", metric_id)
                .execute()
            )
            if existing.data:
                # XML pipeline already loaded this — only overwrite if we have higher priority
                # CSV summary is always lower priority than XML, so skip
                skipped += 1
                continue

            payload = {
                "athlete_id":        athlete_id,
                "session_id":        session_id,
                "metric_id":         metric_id,
                "source_id":         source_id,
                "raw_value":         float(val),
                "collection_method": "auto",
                "manually_tagged":   False,
                "raw_value_context": {"source_column": col},
            }

            if not dry_run:
                sb.table("athlete_event").insert(payload).execute()
            inserted += 1

    log.info(f"  Wyscout stat events: {inserted} loaded | {skipped} skipped (duplicate or no metric)")


# ── Manifest loader ───────────────────────────────────────────────────────────

def load_manifest(path: Path) -> dict:
    if not path.exists():
        return {}
    df = pd.read_csv(path)
    return {row["slug"]: row.to_dict() for _, row in df.iterrows()}


# ── Main ──────────────────────────────────────────────────────────────────────

def load_match(slug: str, season: str, dry_run: bool = False):
    log.info(f"{'='*60}")
    log.info(f"Loading match: {slug}  (dry_run={dry_run})")
    log.info(f"{'='*60}")

    sb = get_client() if not dry_run else None

    # Locate files
    output_dir = OUTPUTS_DIR / season / slug
    if not output_dir.exists():
        raise FileNotFoundError(f"Output directory not found: {output_dir}")

    files = {
        "attributed": output_dir / f"{slug}_attributed.csv",
        "players":    output_dir / f"{slug}_players.csv",
        "minutes":    output_dir / f"{slug}_minutes.csv",
        "coug":       output_dir / f"{slug}_coug_events.csv",
    }

    # Also look for scored summary CSV (any file matching coug_table_*_SLUG pattern)
    scored_path = output_dir / f"{slug}_coug_scores.csv"
    if not scored_path.exists():
        scored_path = None

    log.info("Files found:")
    for name, path in files.items():
        log.info(f"  {name:<15} {'✅' if path.exists() else '❌ MISSING'}  {path.name}")
    log.info(f"  {'scored CSV':<15} {'✅' if scored_path else '⚠️  not found'}  {scored_path.name if scored_path else ''}")

    # Load dataframes
    attributed_df = pd.read_csv(files["attributed"]) if files["attributed"].exists() else None
    minutes_df    = pd.read_csv(files["minutes"])    if files["minutes"].exists()    else None
    players_df    = pd.read_csv(files["players"])    if files["players"].exists()    else None
    scored_df     = pd.read_csv(scored_path)         if scored_path                  else None

    manifest      = load_manifest(MANIFEST_PATH)
    manifest_row  = manifest.get(slug)

    if dry_run:
        log.info("\n[DRY RUN MODE — no writes to Supabase]\n")
        # Just report what would happen
        if minutes_df is not None:
            log.info(f"  Would upsert {len(minutes_df)} athletes from minutes.csv")
        if attributed_df is not None:
            log.info(f"  Would load {len(attributed_df)} attributed events")
        if scored_df is not None:
            log.info(f"  Would load raw stats for {len(scored_df)} players from scored CSV")
        return

    # ── 1. Session + match ─────────────────────────────────────────────────
    log.info("\n→ Session + Match")
    session_id = load_or_create_session(sb, slug, manifest_row, scored_df, dry_run)
    match_id   = load_or_create_match(sb, session_id, slug, scored_df, manifest_row, dry_run)

    # ── 2. Athletes ────────────────────────────────────────────────────────
    log.info("\n→ Athletes")
    all_names = set()
    if minutes_df is not None:
        all_names.update(minutes_df["player_name"].dropna().tolist())
    if attributed_df is not None:
        all_names.update(attributed_df["player_name"].dropna().tolist())
    if scored_df is not None:
        all_names.update(scored_df["player"].dropna().tolist())

    athlete_map = upsert_athletes(sb, list(all_names), dry_run)
    log.info(f"  Athlete map: {len(athlete_map)} entries")

    # ── 3. Stints ──────────────────────────────────────────────────────────
    if minutes_df is not None:
        log.info("\n→ Stints")
        load_stints(sb, session_id, minutes_df, athlete_map, dry_run)

    # ── 4. Metric lookup map ───────────────────────────────────────────────
    metric_rows = sb.table("metric_definition").select("id, name").execute().data
    metric_map  = {normalize_name(r["name"]): r["id"] for r in metric_rows}

    # ── 5. Attributed events (XML pipeline — highest trust) ────────────────
    if attributed_df is not None:
        log.info("\n→ Attributed Events (XML pipeline)")
        source_id = get_or_create_source(sb, "spideo", f"Spiideo XML — {slug}", SOURCE_PRIORITY["xml_attributed"], dry_run)
        load_attributed_events(sb, session_id, attributed_df, athlete_map, metric_map, source_id, dry_run)

    # ── 6. Wyscout stat events (scored CSV — fills gaps, lower trust) ──────
    if scored_df is not None:
        log.info("\n→ Wyscout Stat Events (scored CSV)")
        source_id = get_or_create_source(sb, "csv", f"Scored CSV — {slug}", SOURCE_PRIORITY["csv_summary"], dry_run)
        load_wyscout_stat_events(sb, session_id, scored_df, athlete_map, metric_map, source_id, dry_run)

    log.info(f"\n{'='*60}")
    log.info(f"✅ Done: {slug}")
    log.info(f"   session_id: {session_id}")
    log.info(f"   match_id:   {match_id}")
    log.info(f"{'='*60}\n")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load a match slug into Supabase")
    parser.add_argument("--slug",    required=True, help="Match slug e.g. 2025-11-02_uncw")
    parser.add_argument("--season",  default="2025", help="Season folder e.g. 2025")
    parser.add_argument("--dry-run", action="store_true", help="Report what would happen without writing")
    args = parser.parse_args()

    load_match(slug=args.slug, season=args.season, dry_run=args.dry_run)