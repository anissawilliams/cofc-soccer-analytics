"""Canonical public COUG Table response shaping."""

from __future__ import annotations

from typing import Any


MINIMUM_PER_90_MINUTES = 20


def public_score_rows(rows: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Add backend-owned derived fields without mutating source rows."""
    result = []
    for source in rows or []:
        row = dict(source)
        minutes = row.get("minutes_played") or 0
        score = row.get("total_score") or 0
        row["total_per90"] = (
            (score / minutes) * 90
            if minutes >= MINIMUM_PER_90_MINUTES
            else None
        )
        result.append(row)
    return result
