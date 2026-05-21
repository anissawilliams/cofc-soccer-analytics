"""
manifest.py — Reads matches_manifest.csv for match metadata
Each row is one match with date, opponent, scores, competition, round.
The ingestion script uses this to populate the matches table.
"""

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class MatchMeta:
    date:            str        # YYYY-MM-DD
    opponent_slug:   str        # e.g. uncw, william_mary
    opponent_name:   str        # e.g. UNCW Seahawks
    home_away:       str        # home or away
    home_score:      int
    away_score:      int
    competition:     str        # NCAA D1 CAA, Non-Conference, etc.
    round:           Optional[str]
    season:          str        # 2025
    spiideo_recording_start: Optional[str]  # ISO datetime wall-clock start
    notes:           Optional[str]


def load_manifest(path: Path) -> dict[str, MatchMeta]:
    """
    Load matches_manifest.csv.
    Returns dict keyed by folder slug: {date}_{opponent_slug}
    e.g. "2025-11-02_uncw" → MatchMeta(...)
    """
    manifest = {}
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = f"{row['date']}_{row['opponent_slug']}"
            manifest[key] = MatchMeta(
                date=row["date"],
                opponent_slug=row["opponent_slug"],
                opponent_name=row["opponent_name"],
                home_away=row["home_away"],
                home_score=int(row["home_score"]),
                away_score=int(row["away_score"]),
                competition=row.get("competition", "NCAA D1"),
                round=row.get("round") or None,
                season=row.get("season", "2025"),
                spiideo_recording_start=row.get("spiideo_recording_start") or None,
                notes=row.get("notes") or None,
            )
    print(f"  Loaded {len(manifest)} matches from manifest")
    return manifest


def infer_slug_from_folder(folder_name: str) -> str:
    """
    Extract slug from folder name.
    e.g. "2025-11-02_uncw" → "2025-11-02_uncw"
    Strips any trailing path separators.
    """
    return Path(folder_name).name
