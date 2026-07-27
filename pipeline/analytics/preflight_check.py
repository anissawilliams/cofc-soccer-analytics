#!/usr/bin/env python3
"""
Pre-publication gate for COUG score reconciliation outputs.

The gate reads the reconciliation triage CSV and checks every blocking triage
row against the tracked analyst signoff file. It exits with code 0 only when
all publish-blocking issues are either resolved or documented as acceptable
warnings.
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT_ROOT = REPO_ROOT / "pipeline" / "outputs" / "reports" / "score_reconciliation"
DEFAULT_SIGNOFF_PATH = REPO_ROOT / "pipeline" / "config" / "reconciliation_signoffs.csv"

PASS_DISPOSITIONS = {"cleared"}
WARN_DISPOSITIONS = {"source_missing", "known_gap"}
BLOCK_DISPOSITIONS = {"under_review"}
DEFAULT_BLOCKING_STATUSES = {
    "needs_source_review",
    "legacy_peak_without_normalized_peak_events",
    "legacy_peak_without_candidate_total",
    "candidate_below_legacy",
    "legacy_only_player",
    "pdf_only_player",
    "needs_review",
}


@dataclass(frozen=True)
class GateCounts:
    cleared: int
    warnings: int
    blocks: int
    ignored: int


def clean_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value).strip()


def read_csv(path: Path, required: bool = True) -> pd.DataFrame:
    if not path.exists():
        if required:
            raise SystemExit(f"Required file not found: {path}")
        return pd.DataFrame()
    return pd.read_csv(path)


def issue_player(row: pd.Series) -> str:
    for column in ("triage_player", "player_key", "player", "legacy_player_raw", "pdf_player_raw"):
        value = clean_text(row.get(column))
        if value:
            return value
    return ""


def normalize_issue_key(season: str, row: pd.Series) -> tuple[str, str, str, str]:
    return (
        clean_text(season),
        clean_text(row.get("slug")),
        issue_player(row),
        clean_text(row.get("triage_status") or row.get("issue_type")),
    )


def normalize_signoff_key(row: pd.Series) -> tuple[str, str, str, str]:
    return (
        clean_text(row.get("season")),
        clean_text(row.get("slug")),
        clean_text(row.get("player_key")),
        clean_text(row.get("issue_type")),
    )


def build_signoff_index(signoffs: pd.DataFrame) -> dict[tuple[str, str, str, str], pd.Series]:
    if signoffs.empty:
        return {}
    required = {"season", "slug", "player_key", "issue_type", "disposition"}
    missing = sorted(required - set(signoffs.columns))
    if missing:
        raise SystemExit(f"Signoff file is missing required column(s): {', '.join(missing)}")
    index: dict[tuple[str, str, str, str], pd.Series] = {}
    for _, row in signoffs.iterrows():
        index[normalize_signoff_key(row)] = row
    return index


def classify_gate_row(
    season: str,
    row: pd.Series,
    signoff_index: dict[tuple[str, str, str, str], pd.Series],
    blocking_statuses: set[str],
) -> dict[str, object]:
    status = clean_text(row.get("triage_status"))
    key = normalize_issue_key(season, row)
    signoff = signoff_index.get(key)
    disposition = clean_text(signoff.get("disposition")) if signoff is not None else ""
    note = clean_text(signoff.get("note")) if signoff is not None else ""
    reviewed_by = clean_text(signoff.get("reviewed_by")) if signoff is not None else ""
    reviewed_date = clean_text(signoff.get("reviewed_date")) if signoff is not None else ""

    is_blocking_status = status in blocking_statuses
    if not is_blocking_status:
        gate_status = "ignored"
    elif disposition in PASS_DISPOSITIONS:
        gate_status = "cleared"
    elif disposition in WARN_DISPOSITIONS:
        gate_status = "warning"
    elif disposition in BLOCK_DISPOSITIONS:
        gate_status = "block"
    else:
        gate_status = "block"

    return {
        "season": season,
        "slug": key[1],
        "player_key": key[2],
        "issue_type": key[3],
        "gate_status": gate_status,
        "disposition": disposition or "unsigned",
        "reviewed_by": reviewed_by,
        "reviewed_date": reviewed_date,
        "note": note,
        "candidate_peak_score": row.get("candidate_peak_score", ""),
        "legacy_peak": row.get("legacy_peak", ""),
        "pdf_peak": row.get("pdf_peak", ""),
        "delta_candidate_peak_score_vs_legacy_peak": row.get("delta_candidate_peak_score_vs_legacy_peak", ""),
        "source_coverage_status": row.get("source_coverage_status", ""),
        "source_review_reason": row.get("source_review_reason", ""),
    }


def markdown_table(df: pd.DataFrame, columns: list[str], max_rows: int = 30) -> str:
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

    def escape(value: str) -> str:
        return value.replace("\n", " ").replace("|", "\\|")

    lines = [
        "| " + " | ".join(escape(column) for column in columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in display.astype(str).values.tolist():
        lines.append("| " + " | ".join(escape(value) for value in row) + " |")
    return "\n".join(lines)


def write_report(report: pd.DataFrame, output: Path, counts: GateCounts) -> None:
    status_line = (
        "PASSED"
        if counts.blocks == 0 and counts.warnings == 0
        else "PASSED WITH WARNINGS"
        if counts.blocks == 0
        else "FAILED"
    )
    lines = [
        "# COUG Score Preflight Report",
        "",
        f"## Gate Status: {status_line}",
        "",
        f"- Cleared: {counts.cleared}",
        f"- Warnings: {counts.warnings}",
        f"- Blocks: {counts.blocks}",
        f"- Ignored within-threshold/non-blocking rows: {counts.ignored}",
        "",
        "## Blocking Issues",
        "",
        markdown_table(
            report[report["gate_status"].eq("block")],
            [
                "slug",
                "player_key",
                "issue_type",
                "disposition",
                "delta_candidate_peak_score_vs_legacy_peak",
                "source_coverage_status",
                "source_review_reason",
                "note",
            ],
        ),
        "",
        "## Warning Issues",
        "",
        markdown_table(
            report[report["gate_status"].eq("warning")],
            [
                "slug",
                "player_key",
                "issue_type",
                "disposition",
                "delta_candidate_peak_score_vs_legacy_peak",
                "source_coverage_status",
                "note",
                "reviewed_by",
                "reviewed_date",
            ],
        ),
        "",
        "## Cleared Issues",
        "",
        markdown_table(
            report[report["gate_status"].eq("cleared")],
            ["slug", "player_key", "issue_type", "disposition", "note", "reviewed_by", "reviewed_date"],
        ),
        "",
        "## Disposition Reference",
        "",
        "| Disposition | Preflight effect | When to use |",
        "| --- | --- | --- |",
        "| `cleared` | Silent pass | Issue investigated and confirmed resolved |",
        "| `source_missing` | Warn-level pass | Raw XML / source file not yet available |",
        "| `known_gap` | Warn-level pass | Gap understood; will be addressed in future scoring revision |",
        "| `under_review` | Block | Investigation started but not complete |",
        "| _(no entry)_ | Block | Issue has never been reviewed |",
        "",
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Gate COUG reconciliation output before coach-facing publication.")
    parser.add_argument("--season", default="2025")
    parser.add_argument("--triage-csv", type=Path)
    parser.add_argument("--signoffs", type=Path, default=DEFAULT_SIGNOFF_PATH)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--blocking-status",
        action="append",
        default=[],
        help="Additional triage_status to treat as blocking. Can be repeated.",
    )
    args = parser.parse_args()

    report_dir = DEFAULT_REPORT_ROOT / str(args.season)
    triage_path = args.triage_csv or report_dir / f"{args.season}_reconciliation_triage.csv"
    output_path = args.output or report_dir / "preflight_report.md"
    blocking_statuses = DEFAULT_BLOCKING_STATUSES | set(args.blocking_status)

    triage = read_csv(triage_path)
    signoffs = read_csv(args.signoffs, required=False)
    signoff_index = build_signoff_index(signoffs)

    rows = [
        classify_gate_row(args.season, row, signoff_index, blocking_statuses)
        for _, row in triage.iterrows()
    ]
    report = pd.DataFrame(rows)
    counts = GateCounts(
        cleared=int(report["gate_status"].eq("cleared").sum()),
        warnings=int(report["gate_status"].eq("warning").sum()),
        blocks=int(report["gate_status"].eq("block").sum()),
        ignored=int(report["gate_status"].eq("ignored").sum()),
    )
    write_report(report, output_path, counts)

    status = "PASSED" if counts.blocks == 0 and counts.warnings == 0 else "PASSED WITH WARNINGS" if counts.blocks == 0 else "FAILED"
    print(f"{status} — {counts.warnings} warning(s), {counts.blocks} block(s)")
    print(f"Wrote {output_path}")
    raise SystemExit(1 if counts.blocks else 0)


if __name__ == "__main__":
    main()
