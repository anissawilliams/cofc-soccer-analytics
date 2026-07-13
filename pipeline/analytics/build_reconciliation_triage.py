#!/usr/bin/env python3
"""
Build a triage report from generated COUG score reconciliation outputs.

This script is intentionally downstream-only: it reads the CSVs produced by
reconcile_coug_scores.py and does not query Supabase. Use it when reconciliation
has already run and the question is, "Which deltas should we investigate first?"

Examples:
    python pipeline/analytics/build_reconciliation_triage.py --season 2025
    python pipeline/analytics/build_reconciliation_triage.py --season 2025 --slug 2025-09-27_william_mary
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT_ROOT = REPO_ROOT / "pipeline" / "outputs" / "reports" / "score_reconciliation"


def clean_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value).strip()


def as_number(value: object, default: float = 0.0) -> float:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return default
    return float(number)


def first_present(row: pd.Series, columns: list[str]) -> str:
    for column in columns:
        if column in row.index:
            value = clean_text(row.get(column))
            if value:
                return value
    return ""


def list_join(values: pd.Series, max_items: int = 8) -> str:
    cleaned = [clean_text(v) for v in values if clean_text(v)]
    unique = list(dict.fromkeys(cleaned))
    if len(unique) > max_items:
        return ", ".join(unique[:max_items]) + f", +{len(unique) - max_items} more"
    return ", ".join(unique)


def discover_slugs(report_dir: Path, requested_slugs: list[str]) -> list[str]:
    if requested_slugs:
        return requested_slugs
    slugs = []
    for path in sorted(report_dir.glob("*_score_reconciliation.csv")):
        slug = path.name.removesuffix("_score_reconciliation.csv")
        if slug == "season":
            continue
        slugs.append(slug)
    return slugs


def read_csv_if_exists(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def summarize_trace(trace: pd.DataFrame) -> pd.DataFrame:
    if trace.empty:
        return pd.DataFrame(columns=[
            "slug", "player_key", "trace_event_rows", "trace_raw_labels",
            "trace_candidate_peak_labels", "trace_candidate_peak_score",
            "trace_advance_actions", "trace_peak_statuses",
        ])

    candidate_mask = pd.to_numeric(trace.get("candidate_peak_score"), errors="coerce").fillna(0).ne(0)
    if "candidate_advance_action" in trace.columns:
        advance_mask = pd.to_numeric(trace["candidate_advance_action"], errors="coerce").fillna(0).ne(0)
    else:
        advance_mask = pd.Series(False, index=trace.index)
    candidate_or_advance = trace[candidate_mask | advance_mask].copy()

    grouped = (
        trace.groupby(["slug", "player_key"], dropna=False)
        .agg(
            trace_event_rows=("raw_metric_name", "size"),
            trace_raw_labels=("raw_metric_name", list_join),
        )
        .reset_index()
    )

    if candidate_or_advance.empty:
        grouped["trace_candidate_peak_labels"] = ""
        grouped["trace_candidate_peak_score"] = 0.0
        grouped["trace_advance_actions"] = 0.0
        grouped["trace_peak_statuses"] = ""
        return grouped

    candidate_grouped = (
        candidate_or_advance.groupby(["slug", "player_key"], dropna=False)
        .agg(
            trace_candidate_peak_labels=("candidate_peak_metric", list_join),
            trace_candidate_peak_score=("candidate_peak_score", "sum"),
            trace_advance_actions=("candidate_advance_action", "sum"),
            trace_peak_statuses=("peak_implementation_status", list_join),
        )
        .reset_index()
    )
    return grouped.merge(candidate_grouped, on=["slug", "player_key"], how="left").fillna({
        "trace_candidate_peak_labels": "",
        "trace_candidate_peak_score": 0.0,
        "trace_advance_actions": 0.0,
        "trace_peak_statuses": "",
    })


def classify_row(row: pd.Series, threshold: float) -> str:
    player = clean_text(row.get("player"))
    legacy = clean_text(row.get("legacy_player_raw"))
    pdf = clean_text(row.get("pdf_player_raw"))
    candidate_peak = as_number(row.get("candidate_peak_score"))
    legacy_peak_raw = row.get("legacy_peak")
    legacy_peak = as_number(legacy_peak_raw)
    candidate_delta = as_number(row.get("delta_candidate_peak_score_vs_legacy_peak"))
    trace_candidate = as_number(row.get("trace_candidate_peak_score"))
    trace_advance = as_number(row.get("trace_advance_actions"))

    if not player and legacy:
        return "legacy_only_player"
    if not player and pdf:
        return "pdf_only_player"
    if player and not legacy and candidate_peak:
        return "candidate_without_legacy"
    if pd.isna(pd.to_numeric(legacy_peak_raw, errors="coerce")):
        return "no_legacy_peak_baseline"
    if abs(candidate_delta) < threshold:
        return "within_threshold"
    if legacy_peak > 0 and candidate_peak == 0:
        if trace_candidate == 0 and trace_advance == 0:
            return "legacy_peak_without_normalized_peak_events"
        return "legacy_peak_without_candidate_total"
    if candidate_peak < legacy_peak:
        return "candidate_below_legacy"
    if candidate_peak > legacy_peak:
        return "candidate_above_legacy"
    return "needs_review"


def build_triage(slug: str, reconciliation: pd.DataFrame, trace_summary: pd.DataFrame, threshold: float) -> pd.DataFrame:
    if reconciliation.empty:
        return pd.DataFrame()
    df = reconciliation.copy()
    df["slug"] = df.get("slug", slug).fillna(slug)
    if "player_key" not in df.columns:
        df["player_key"] = ""
    df = df.merge(trace_summary, on=["slug", "player_key"], how="left")

    for column in [
        "pipeline_peak", "candidate_peak_score", "legacy_peak", "pdf_peak",
        "delta_candidate_peak_score_vs_legacy_peak", "delta_candidate_peak_score_vs_pdf_peak",
        "event_count", "trace_event_rows", "trace_candidate_peak_score", "trace_advance_actions",
    ]:
        if column not in df.columns:
            df[column] = pd.NA

    df["triage_status"] = df.apply(lambda row: classify_row(row, threshold), axis=1)
    df["triage_player"] = df.apply(
        lambda row: first_present(row, ["player", "legacy_player_raw", "pdf_player_raw", "player_key"]),
        axis=1,
    )
    df["abs_candidate_legacy_peak_delta"] = (
        pd.to_numeric(df["delta_candidate_peak_score_vs_legacy_peak"], errors="coerce")
        .abs()
        .fillna(0.0)
    )
    df["abs_candidate_pdf_peak_delta"] = (
        pd.to_numeric(df["delta_candidate_peak_score_vs_pdf_peak"], errors="coerce")
        .abs()
        .fillna(0.0)
    )

    columns = [
        "slug", "triage_status", "triage_player", "player", "legacy_player_raw",
        "legacy_player_match_method", "pdf_player_raw", "pdf_player_match_method",
        "pipeline_peak", "candidate_peak_score", "legacy_peak", "pdf_peak",
        "delta_candidate_peak_score_vs_legacy_peak", "delta_candidate_peak_score_vs_pdf_peak",
        "abs_candidate_legacy_peak_delta", "abs_candidate_pdf_peak_delta",
        "event_count", "trace_event_rows",
        "trace_candidate_peak_score", "trace_advance_actions", "trace_raw_labels",
        "trace_candidate_peak_labels", "trace_peak_statuses", "legacy_peak_breakdown",
        "legacy_source_file", "pdf_source_file",
    ]
    available = [column for column in columns if column in df.columns]
    return df[available].sort_values(
        ["abs_candidate_legacy_peak_delta", "abs_candidate_pdf_peak_delta", "slug", "triage_player"],
        ascending=[False, False, True, True],
    )


def markdown_table(df: pd.DataFrame, columns: list[str], max_rows: int) -> str:
    if df.empty:
        return "_No rows._"
    display = df.head(max_rows).copy()
    for column in columns:
        if column not in display.columns:
            display[column] = ""
    display = display[columns]
    for column in display.columns:
        if pd.api.types.is_numeric_dtype(display[column]):
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{float(value):.3g}")
        else:
            display[column] = display[column].fillna("").astype(str)
    headers = list(display.columns)
    rows = display.astype(str).values.tolist()

    def escape_cell(value: str) -> str:
        return value.replace("\n", " ").replace("|", "\\|")

    lines = [
        "| " + " | ".join(escape_cell(header) for header in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(escape_cell(value) for value in row) + " |")
    return "\n".join(lines)


def write_markdown(triage: pd.DataFrame, output_path: Path, threshold: float, top: int) -> None:
    lines = [
        "# COUG Score Reconciliation Triage",
        "",
        f"Generated from reconciliation CSVs with a PEAK delta threshold of `{threshold:g}`.",
        "",
        "This report is diagnostic only. It does not decide whether the coach/legacy, PDF, or event-derived value is correct.",
        "",
        "## Status Counts",
        "",
    ]

    counts = (
        triage["triage_status"].value_counts()
        .rename_axis("triage_status")
        .reset_index(name="rows")
        if not triage.empty else pd.DataFrame(columns=["triage_status", "rows"])
    )
    lines.append(markdown_table(counts, ["triage_status", "rows"], max_rows=50))

    lines.extend([
        "",
        "## Highest PEAK Deltas",
        "",
        markdown_table(
            triage,
            [
                "slug", "triage_status", "triage_player", "candidate_peak_score",
                "legacy_peak", "pdf_peak", "delta_candidate_peak_score_vs_legacy_peak",
                "trace_candidate_peak_labels", "legacy_peak_breakdown",
            ],
            max_rows=top,
        ),
        "",
        "## Legacy-Only Players",
        "",
        markdown_table(
            triage[triage["triage_status"].eq("legacy_only_player")],
            ["slug", "triage_player", "legacy_peak", "legacy_player_match_method", "legacy_peak_breakdown"],
            max_rows=top,
        ),
        "",
        "## Normalized PEAK Event Evidence",
        "",
        markdown_table(
            triage[triage["trace_candidate_peak_score"].fillna(0).ne(0) | triage["trace_advance_actions"].fillna(0).ne(0)],
            [
                "slug", "triage_player", "candidate_peak_score", "trace_candidate_peak_score",
                "trace_advance_actions", "trace_candidate_peak_labels", "trace_peak_statuses",
            ],
            max_rows=top,
        ),
        "",
        "## How To Use This",
        "",
        "- Start with `legacy_peak_without_normalized_peak_events` and `candidate_below_legacy` rows.",
        "- For each top row, inspect the matching `*_event_score_trace.csv` by `player_key` and `raw_metric_name`.",
        "- Treat legacy/PDF values as comparison baselines. The official path is event-derived scoring once source coverage and mapping are verified.",
        "",
    ])
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a triage report from generated COUG reconciliation CSVs")
    parser.add_argument("--season", default="2025")
    parser.add_argument("--report-dir", type=Path)
    parser.add_argument("--slug", action="append", default=[], help="Match slug to include. Can be repeated.")
    parser.add_argument("--threshold", type=float, default=1.0, help="Minimum absolute PEAK delta to flag as a mismatch.")
    parser.add_argument("--top", type=int, default=25)
    args = parser.parse_args()

    report_dir = args.report_dir or DEFAULT_REPORT_ROOT / str(args.season)
    slugs = discover_slugs(report_dir, args.slug)
    if not slugs:
        raise SystemExit(f"No per-match reconciliation files found in {report_dir}")

    triage_frames = []
    for slug in slugs:
        reconciliation_path = report_dir / f"{slug}_score_reconciliation.csv"
        trace_path = report_dir / f"{slug}_event_score_trace.csv"
        reconciliation = read_csv_if_exists(reconciliation_path)
        trace = read_csv_if_exists(trace_path)
        if not trace.empty:
            trace["slug"] = slug
        trace_summary = summarize_trace(trace)
        triage = build_triage(slug, reconciliation, trace_summary, args.threshold)
        if not triage.empty:
            triage_frames.append(triage)

    if not triage_frames:
        raise SystemExit("No triage rows could be built from the selected reconciliation files.")

    triage_all = pd.concat(triage_frames, ignore_index=True, sort=False)
    triage_all = triage_all.sort_values(
        ["abs_candidate_legacy_peak_delta", "abs_candidate_pdf_peak_delta", "slug", "triage_player"],
        ascending=[False, False, True, True],
    )

    output_csv = report_dir / f"{args.season}_reconciliation_triage.csv"
    output_md = report_dir / f"{args.season}_reconciliation_triage.md"
    output_docs_md = REPO_ROOT / "docs" / "analytics" / f"reconciliation_triage_{args.season}.md"
    report_dir.mkdir(parents=True, exist_ok=True)
    output_docs_md.parent.mkdir(parents=True, exist_ok=True)

    triage_all.to_csv(output_csv, index=False)
    write_markdown(triage_all, output_md, args.threshold, args.top)
    write_markdown(triage_all, output_docs_md, args.threshold, args.top)

    print(f"Wrote {output_csv}")
    print(f"Wrote {output_md}")
    print(f"Wrote {output_docs_md}")


if __name__ == "__main__":
    main()
