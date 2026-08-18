#!/usr/bin/env python3
"""Publish reviewed event-derived COUG match scores to Supabase.

The script deliberately reuses the reconciliation trace instead of maintaining
a second scoring engine. By default it only writes a review CSV; ``--apply``
is required before it upserts rows into ``coug_score``.

Examples:
    python pipeline/analytics/publish_event_derived_coug_scores.py \
      --season 2026 --slug 2026-08-20_opponent
    python pipeline/analytics/publish_event_derived_coug_scores.py \
      --season 2026 --slug 2026-08-20_opponent --apply
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ANALYTICS_DIR = Path(__file__).resolve().parent
if str(ANALYTICS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYTICS_DIR))

from reconcile_coug_scores import (  # noqa: E402
    build_event_trace,
    fetch_all,
    fetch_optional,
    get_client,
    slug_date,
    summarize_trace,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "pipeline" / "outputs" / "reports" / "score_publication"
REQUIRED_TABLES = [
    "athlete_event",
    "athlete",
    "metric_definition",
    "metric_category",
    "metric_weight",
    "session",
    "match",
    "data_source",
]
PUBLISHABLE_SCORE_BUCKETS = {"aset", "peak", "set_piece", "positional", "load"}


def load_tables(client) -> dict[str, pd.DataFrame]:
    tables = {name: fetch_all(client, name) for name in REQUIRED_TABLES}
    tables["athlete_alias"] = fetch_optional(client, "athlete_alias")
    return tables


def selected_trace(trace: pd.DataFrame, season: str, slug: str) -> pd.DataFrame:
    date = slug_date(slug)
    selected = trace[
        trace["season"].astype(str).eq(str(season))
        & trace["session_date"].astype(str).eq(date)
    ].copy()
    return selected.sort_values(["player", "event_time", "raw_metric_name"])


def validation_errors(trace: pd.DataFrame) -> list[str]:
    if trace.empty:
        return ["No athlete_event evidence rows found for the selected match."]

    errors: list[str] = []
    athlete_counts = trace.groupby(["session_id", "player_key"])["athlete_id"].nunique()
    ambiguous_athletes = athlete_counts[athlete_counts.ne(1)]
    if not ambiguous_athletes.empty:
        errors.append(f"{len(ambiguous_athletes)} player/session pair(s) resolve to multiple athlete IDs.")

    missing_metric = trace[trace["scoring_metric_name"].fillna("").eq("")]
    if not missing_metric.empty:
        errors.append(f"{len(missing_metric)} event row(s) have no scoring metric mapping.")

    missing_weight = trace[trace["weight_missing"].fillna(False)].copy()
    # A mapping can explicitly preserve an event as evidence without making it
    # scoreable yet (for example generic goalkeeper Saves). Those rows must
    # remain in the ledger but must not block unrelated player scores.
    intentionally_unscored = missing_weight[
        missing_weight["mapping_status"].fillna("").eq("unmapped")
        & missing_weight["default_include"].notna()
        & missing_weight["default_include"].eq(False)
    ]
    blocking_missing_weight = missing_weight.drop(index=intentionally_unscored.index)
    if not blocking_missing_weight.empty:
        errors.append(f"{len(blocking_missing_weight)} event row(s) have no active metric weight.")

    invalid_buckets = trace[~trace["score_bucket"].isin(PUBLISHABLE_SCORE_BUCKETS)]
    if not invalid_buckets.empty:
        labels = ", ".join(sorted(invalid_buckets["score_bucket"].fillna("missing").astype(str).unique()))
        errors.append(f"{len(invalid_buckets)} event row(s) use non-publishable score bucket(s): {labels}.")

    provisional_peak = trace[
        trace["candidate_peak_score"].fillna(0).ne(0)
        & ~trace["peak_official_status"].fillna("").eq("official")
    ]
    if not provisional_peak.empty:
        errors.append(
            f"{len(provisional_peak)} PEAK event row(s) contribute points without official normalization status."
        )

    return errors


def build_publish_summary(trace: pd.DataFrame) -> pd.DataFrame:
    """Produce one official match-score candidate per athlete/session."""
    summary = summarize_trace(trace).copy()
    if summary.empty:
        return summary

    athlete_ids = (
        trace.groupby(["session_id", "player_key"], as_index=False)["athlete_id"]
        .first()
    )
    summary = summary.merge(athlete_ids, on=["session_id", "player_key"], how="left")

    columns = [
        "pipeline_aset",
        "candidate_peak_score",
        "pipeline_set_piece",
        "pipeline_positional",
        "pipeline_load",
    ]
    for column in columns:
        summary[column] = pd.to_numeric(summary.get(column), errors="coerce").fillna(0.0)

    summary["aset_score"] = summary["pipeline_aset"]
    # Use the normalized PEAK calculation so Advance thresholds and the
    # Punish/Advance priority are consistent with the coach-confirmed fixture.
    summary["peak_score"] = summary["candidate_peak_score"]
    summary["set_piece_score"] = summary["pipeline_set_piece"]
    summary["positional_score"] = summary["pipeline_positional"]
    summary["load_score"] = summary["pipeline_load"]
    summary["total_score"] = summary[
        ["aset_score", "peak_score", "set_piece_score", "positional_score", "load_score"]
    ].sum(axis=1)
    return summary


def resolve_weight_version_id(client, version: str) -> str:
    rows = (
        client.table("metric_weight")
        .select("id, effective_from, created_at")
        .eq("version", version)
        .execute()
        .data
        or []
    )
    if not rows:
        raise ValueError(f"No metric_weight rows found for version '{version}'.")
    rows.sort(key=lambda row: (str(row.get("effective_from") or ""), str(row.get("created_at") or "")))
    return rows[-1]["id"]


def score_payloads(summary: pd.DataFrame, weight_version_id: str) -> list[dict[str, object]]:
    calculated_at = datetime.now(timezone.utc).isoformat()
    payloads: list[dict[str, object]] = []
    for _, row in summary.iterrows():
        payloads.append(
            {
                "athlete_id": row["athlete_id"],
                "session_id": row["session_id"],
                "weight_version_id": weight_version_id,
                "aset_score": round(float(row["aset_score"]), 4),
                "peak_score": round(float(row["peak_score"]), 4),
                "set_piece_score": round(float(row["set_piece_score"]), 4),
                "positional_score": round(float(row["positional_score"]), 4),
                "load_score": round(float(row["load_score"]), 4),
                "total_score": round(float(row["total_score"]), 4),
                "score_type": "match",
                "data_source_path": "xml",
                "calculated_at": calculated_at,
            }
        )
    return payloads


def write_review_csv(summary: pd.DataFrame, season: str, slug: str, output_root: Path) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    path = output_root / str(season) / f"{slug}_event_derived_score_review.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    summary.sort_values("player").to_csv(path, index=False)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Preview or publish event-derived COUG match scores from athlete_event evidence."
    )
    parser.add_argument("--season", required=True)
    parser.add_argument("--slug", required=True, help="Match slug, for example 2026-08-20_opponent")
    parser.add_argument("--weight-version", default="trial_1")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--apply", action="store_true", help="Upsert reviewed scores to public.coug_score")
    args = parser.parse_args()

    client = get_client()
    tables = load_tables(client)
    trace = selected_trace(build_event_trace(tables, args.weight_version), args.season, args.slug)
    errors = validation_errors(trace)
    if errors:
        print("Publication blocked:")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)

    summary = build_publish_summary(trace)
    review_path = write_review_csv(summary, args.season, args.slug, args.output_root)
    print(f"Wrote review: {review_path}")
    print(
        summary[[
            "player", "event_count", "aset_score", "peak_score", "set_piece_score",
            "positional_score", "load_score", "total_score",
        ]]
        .sort_values("player")
        .to_string(index=False)
    )

    if not args.apply:
        print("Dry run only. Review the CSV and rerun with --apply to publish these match scores.")
        return

    weight_version_id = resolve_weight_version_id(client, args.weight_version)
    payloads = score_payloads(summary, weight_version_id)
    client.table("coug_score").upsert(
        payloads,
        on_conflict="athlete_id,session_id,weight_version_id,score_type",
    ).execute()
    print(f"Published {len(payloads)} event-derived COUG score row(s) for {args.slug}.")


if __name__ == "__main__":
    main()
