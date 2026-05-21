"""
attribute.py — Timestamp offset resolution + player attribution
Merges Spiideo COUG events with Wyscout player events
"""

from config import MERGE_WINDOW_SECONDS, ASET_RELEVANT_LABELS, PEAK_RELEVANT_LABELS
from parse_wyscout import wyscout_to_match_minute


# ── Offset calculation ────────────────────────────────────────

def calculate_offset(
    wyscout_halves: dict,
    spiideo_all_events: list,
    spiideo_recording_start: str = None,
    manual_offset: int = None
) -> float:
    """
    Calculate timestamp offset between Wyscout and Spiideo.
    Strategy:
      1. Use manual_offset if provided (most accurate)
      2. Use wall-clock recording start times if available
      3. Fall back to earliest event heuristic

    offset = spiideo_time - wyscout_time
    i.e. wyscout_time = spiideo_time - offset
    """

    # 1. Manual override
    if manual_offset is not None:
        print(f"  Offset: {manual_offset}s (manual)")
        return float(manual_offset)

    # 2. Wall-clock alignment
    # TODO: implement when Spiideo provides recording start timestamp
    # from datetime import datetime
    # if spiideo_recording_start and wyscout_match_start:
    #     spiideo_dt = datetime.fromisoformat(spiideo_recording_start)
    #     delta = (wyscout_match_start - spiideo_dt).total_seconds()
    #     return delta

    # 3. Heuristic — earliest meaningful Spiideo event vs Wyscout first half start
    wyscout_first_start = wyscout_halves.get("first_start", 2.0)

    # Skip very early Spiideo events (pre-match setup tags)
    meaningful = sorted(
        [e for e in spiideo_all_events if e["start"] > 10],
        key=lambda e: e["start"]
    )
    if not meaningful:
        print("  Offset: 0s (no meaningful Spiideo events found)")
        return 0.0

    earliest_spiideo = meaningful[0]["start"]
    offset = earliest_spiideo - wyscout_first_start

    print(f"  Offset: {offset:.1f}s "
          f"(Spiideo {earliest_spiideo}s - Wyscout {wyscout_first_start}s)")
    return offset


# ── Player attribution ────────────────────────────────────────

def score_candidate(
    candidate: dict,
    wyscout_t: float,
    category: str
) -> float:
    """
    Score a Wyscout player event as a candidate for attribution.
    Higher = more likely to be the player who triggered the COUG event.
    """
    relevant = ASET_RELEVANT_LABELS if category == "ASET" else PEAK_RELEVANT_LABELS
    label_overlap = len(set(candidate["labels"]) & relevant)
    time_score    = 1.0 / (abs(candidate["start"] - wyscout_t) + 1)
    outcome_bonus = 0.5 if candidate["outcome"] == "Plus" else 0
    return label_overlap * 2 + time_score + outcome_bonus


def attribute_players(
    coug_events:     list,
    player_events:   list,
    offset:          float,
    first_half_start: float,
) -> list:
    """
    Merge Spiideo COUG events with Wyscout player events.
    For each COUG event, find the best matching player within
    the merge window and attach their info.

    Returns attributed events — each event has a 'player' field
    (or None if no match found within window).
    """
    attributed   = []
    unattributed = 0

    for ev in coug_events:
        wyscout_t = ev["spiideo_t"] - offset

        # Find candidates within time window
        candidates = [
            p for p in player_events
            if abs(p["start"] - wyscout_t) <= MERGE_WINDOW_SECONDS
        ]

        if not candidates:
            unattributed += 1
            attributed.append({
                **ev,
                "player":            None,
                "wyscout_t":         wyscout_t,
                "match_minute":      wyscout_to_match_minute(wyscout_t, first_half_start),
                "attribution_score": 0.0,
            })
            continue

        # Score and pick best candidate
        scored  = [(score_candidate(p, wyscout_t, ev["category"]), p)
                   for p in candidates]
        best_s, best = max(scored, key=lambda x: x[0])

        # Normalize to 0-1
        attribution_score = min(best_s / 5.0, 1.0)

        attributed.append({
            **ev,
            "player":            best,
            "wyscout_t":         wyscout_t,
            "match_minute":      wyscout_to_match_minute(wyscout_t, first_half_start),
            "attribution_score": round(attribution_score, 4),
        })

    total      = len(coug_events)
    match_rate = (total - unattributed) / max(total, 1) * 100
    print(f"  Attribution: {total - unattributed}/{total} "
          f"({match_rate:.0f}% match rate)")

    return attributed
