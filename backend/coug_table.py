"""Canonical public COUG Table response shaping."""

from __future__ import annotations

from typing import Any


MINIMUM_PER_90_MINUTES = 20


def _number(value: Any) -> float:
    """Normalize numeric database values for a stable JSON response."""
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def public_score_rows(rows: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Add backend-owned derived fields without mutating source rows."""
    result = []
    for source in rows or []:
        row = dict(source)
        minutes = _number(row.get("minutes_played"))
        score = _number(row.get("total_score"))
        row["total_per90"] = (
            round((score / minutes) * 90, 2)
            if minutes >= MINIMUM_PER_90_MINUTES
            else None
        )
        result.append(row)
    return result
