"""
config.py — Shared configuration, constants, and Supabase client
"""

import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

# ── Supabase ──────────────────────────────────────────────────
SUPABASE_URL        = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# ── Blob storage ──────────────────────────────────────────────
BLOB_BUCKET = "match-xmls"

# ── Ingestion ─────────────────────────────────────────────────
INGESTION_VERSION    = "1.0.0"
MERGE_WINDOW_SECONDS = 15       # ± seconds for player attribution
MIN_MINUTES_PER90    = 45       # minimum minutes to show per-90 stat

# ── Teams ─────────────────────────────────────────────────────
HOME_TEAM_NAME = "Charleston Cougars"
HOME_TEAM_ABBR = "CFC"

# ── Wyscout label sets for attribution scoring ────────────────
ASET_RELEVANT_LABELS = {
    "Vol_Interception", "Tackles", "Clearances",
    "Defensive duel", "1VS1", "Loose ball duel",
    "Pressing duel", "Smart passes", "Link up play",
    "Key passes", "Through pass", "Recovery"
}

PEAK_RELEVANT_LABELS = {
    "Goal", "Shots", "Opportunity", "1VS1",
    "Offensive duel", "Heading", "Vol_Interception",
    "Tackles", "Accelerations", "Bring the ball"
}

# ── File type suffixes (parsed from filename convention) ──────
FILE_TYPES = {
    "sportscode":    "cfc_sportscode",
    "player":        "cfc_player",
    "team":          "cfc_team",
    "effective_time": "cfc_effective_time",
    "spiideo":       "spiideo",
}
