"""
generate_manifest.py
====================
Generates matches_manifest.csv from output folder names + real match scores.
Run from repo root:
    python generate_manifest.py
"""

import csv
from pathlib import Path
from datetime import datetime
import os

PROJECT_ROOT  = Path(os.environ.get("PROJECT_ROOT", "/Users/anissawilliams/PycharmProjects/cofc_soccer_analytics_2026"))
OUTPUTS_DIR   = PROJECT_ROOT / "pipeline" / "data" / "outputs" / "2025"
MANIFEST_PATH = PROJECT_ROOT / "pipeline" / "data" / "manifests" / "matches_manifest.csv"

SKIP_FOLDERS = {"catapult", "spiideo", "wyscout"}

# date → (cofc_goals, opp_goals, competition, venue)
MATCH_DETAILS = {
    "2025-11-02_uncw":             (2, 1,  "CAA",             "Patriots Point"),
    "2025-10-25_william_mary":     (3, 1,  "CAA",             "Away"),
    "2025-10-18_elon":             (0, 0,  "CAA",             "Patriots Point"),
    "2025-10-15_winthrop":         (1, 1,  "Non-Conference",  "Away"),
    "2025-10-08_north_florida":    (0, 3,  "Non-Conference",  "Patriots Point"),
    "2025-10-05_campbell":         (2, 3,  "CAA",             "Away"),
    "2025-09-27_william_mary":     (3, 1,  "CAA",             "Patriots Point"),
    "2025-09-24_georgia_southern": (0, 1,  "Non-Conference",  "Patriots Point"),
    "2025-09-17_furman":           (1, 0,  "Non-Conference",  "Away"),
    "2025-09-13_campbell":         (0, 0,  "CAA",             "Patriots Point"),
    "2025-09-10_usc_upstate":      (1, 0,  "Non-Conference",  "Patriots Point"),
    "2025-09-06_elon":             (0, 1,  "CAA",             "Away"),
    "2025-09-02_north_carolina":   (2, 0,  "Non-Conference",  "Patriots Point"),
    "2025-08-30_boston":           (1, 5,  "Non-Conference",  "Patriots Point"),
    "2025-08-26_davidson":         (2, 3,  "Non-Conference",  "Away"),
    "2025-08-22_south_carolina":   (2, 3,  "Non-Conference",  "Patriots Point"),
}

def slug_to_opponent_name(opponent_slug: str) -> str:
    return " ".join(w.capitalize() for w in opponent_slug.split("_"))

def get_result(cofc, opp):
    if cofc is None or opp is None: return ""
    if cofc > opp: return "W"
    if cofc < opp: return "L"
    return "D"

def generate():
    slugs = sorted([
        d.name for d in OUTPUTS_DIR.iterdir()
        if d.is_dir() and d.name not in SKIP_FOLDERS
    ])

    rows = []
    for slug in slugs:
        parts = slug.split("_", 1)
        if len(parts) != 2:
            continue

        date_str, opp_slug = parts
        details = MATCH_DETAILS.get(slug, (None, None, "Unknown", "Unknown"))
        cofc_goals, opp_goals, competition, venue = details
        result = get_result(cofc_goals, opp_goals)

        rows.append({
            "slug":         slug,
            "session_type": "match",
            "competition":  competition,
            "venue":        venue,
            "season":       date_str[:4],
            "opponent":     slug_to_opponent_name(opp_slug),
            "cofc_goals":   cofc_goals if cofc_goals is not None else "",
            "opp_goals":    opp_goals  if opp_goals  is not None else "",
            "result":       result,
            "added_at":     datetime.now().strftime("%Y-%m-%d"),
        })

    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["slug", "session_type", "competition", "venue", "season",
                  "opponent", "cofc_goals", "opp_goals", "result", "added_at"]

    with open(MANIFEST_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"✅ Generated manifest with {len(rows)} matches → {MANIFEST_PATH}")
    for r in rows:
        status = f"{r['result']} {r['cofc_goals']}-{r['opp_goals']}" if r['result'] else "⚠️  no score"
        print(f"  {r['slug']:<35} {status}")

if __name__ == "__main__":
    generate()