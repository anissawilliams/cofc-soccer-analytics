#!/usr/bin/env python3
"""
Validate local COUG scoring configuration files.

This guardrail checks the raw-label normalization tables that sit between
Wyscout evidence and database-backed metric definitions/weights. It is meant to
catch broken config before a match report is sent to coaches; it does not decide
the soccer logic by itself.

Examples:
    python pipeline/analytics/validate_scoring_config.py
    python pipeline/analytics/validate_scoring_config.py --fail-on-warnings
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "pipeline" / "config"
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "analytics" / "scoring_config_validation.md"

PEAK_PATH = CONFIG_DIR / "wyscout_peak_normalization.csv"
METRIC_MAP_PATH = CONFIG_DIR / "wyscout_coug_metric_map.csv"

PEAK_REQUIRED_COLUMNS = {
    "raw_label",
    "raw_label_key",
    "normalized_metric",
    "peak_phase",
    "score_bucket",
    "score_policy",
    "event_weight",
    "threshold_count",
    "threshold_score",
    "requires_success",
    "success_rule",
    "double_count_priority",
    "pass_threshold_rule",
    "official_status",
    "implementation_status",
    "notes",
}
METRIC_MAP_REQUIRED_COLUMNS = {
    "raw_metric_name",
    "mapped_metric_name",
    "mapped_score_bucket",
    "mapping_status",
    "default_include",
    "notes",
}
ALLOWED_SCORE_POLICIES = {"per_event", "contextual_event", "threshold_count", "exclude"}
ALLOWED_OFFICIAL_STATUSES = {"official", "provisional", "excluded"}
ALLOWED_IMPLEMENTATION_STATUSES = {
    "ready",
    "needs_context_rule",
    "needs_success_filter",
    "needs_set_piece_policy",
    "blocked",
}
ALLOWED_BUCKETS = {"aset", "peak", "set_piece", "positional", ""}
ALLOWED_MAPPING_STATUSES = {"reviewed_candidate", "needs_coach_review", "unmapped"}
NORMALIZED_INPUT_ALIASES = {"assist", "goal (scorer)"}


@dataclass
class Finding:
    severity: str
    check: str
    detail: str


def clean_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value).strip()


def normalize_key(value: object) -> str:
    return " ".join(clean_text(value).lower().split())


def as_number(value: object) -> float | None:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return None
    return float(number)


def boolish(value: object) -> bool:
    return clean_text(value).lower() in {"true", "1", "yes", "y"}


def add(finding_list: list[Finding], severity: str, check: str, detail: str) -> None:
    finding_list.append(Finding(severity=severity, check=check, detail=detail))


def require_columns(
    findings: list[Finding],
    name: str,
    df: pd.DataFrame,
    required_columns: set[str],
) -> bool:
    missing = sorted(required_columns.difference(df.columns))
    if missing:
        add(findings, "error", f"{name} columns", f"Missing required columns: {', '.join(missing)}")
        return False
    return True


def validate_peak_normalization(df: pd.DataFrame, findings: list[Finding]) -> None:
    if not require_columns(findings, "PEAK normalization", df, PEAK_REQUIRED_COLUMNS):
        return

    working = df.copy()
    working["raw_label_key_normalized"] = working["raw_label_key"].fillna(working["raw_label"]).map(normalize_key)

    duplicate_keys = sorted(
        key for key, count in working["raw_label_key_normalized"].value_counts().items()
        if key and count > 1
    )
    if duplicate_keys:
        add(findings, "error", "PEAK duplicate raw labels", f"Duplicate raw_label_key values: {', '.join(duplicate_keys)}")

    for idx, row in working.iterrows():
        row_id = f"row {idx + 2} ({clean_text(row.get('raw_label'))})"
        policy = clean_text(row.get("score_policy"))
        official_status = clean_text(row.get("official_status"))
        implementation_status = clean_text(row.get("implementation_status"))
        metric = clean_text(row.get("normalized_metric"))
        requires_success = boolish(row.get("requires_success"))
        event_weight = as_number(row.get("event_weight"))
        threshold_count = as_number(row.get("threshold_count"))
        threshold_score = as_number(row.get("threshold_score"))
        priority = as_number(row.get("double_count_priority"))

        if policy not in ALLOWED_SCORE_POLICIES:
            add(findings, "error", "PEAK score_policy", f"{row_id}: unsupported score_policy `{policy}`.")
        if official_status not in ALLOWED_OFFICIAL_STATUSES:
            add(findings, "error", "PEAK official_status", f"{row_id}: unsupported official_status `{official_status}`.")
        if implementation_status not in ALLOWED_IMPLEMENTATION_STATUSES:
            add(
                findings,
                "warning",
                "PEAK implementation_status",
                f"{row_id}: unexpected implementation_status `{implementation_status}`.",
            )
        if priority is None or priority <= 0:
            add(findings, "error", "PEAK double_count_priority", f"{row_id}: priority must be a positive number.")

        if policy in {"per_event", "contextual_event"}:
            if not metric:
                add(findings, "error", "PEAK normalized metric", f"{row_id}: scoring row needs normalized_metric.")
            if event_weight is None or event_weight <= 0:
                add(findings, "error", "PEAK event weight", f"{row_id}: `{policy}` needs event_weight > 0.")
        elif policy == "threshold_count":
            if not metric:
                add(findings, "error", "PEAK normalized metric", f"{row_id}: threshold row needs normalized_metric.")
            if threshold_count is None or threshold_count <= 0:
                add(findings, "error", "PEAK threshold_count", f"{row_id}: threshold_count must be > 0.")
            if threshold_score is None or threshold_score <= 0:
                add(findings, "error", "PEAK threshold_score", f"{row_id}: threshold_score must be > 0.")
            if event_weight not in {None, 0.0}:
                add(findings, "warning", "PEAK threshold event_weight", f"{row_id}: threshold rows should not score per event.")
        elif policy == "exclude":
            if official_status != "excluded":
                add(findings, "warning", "PEAK excluded status", f"{row_id}: excluded row should use official_status `excluded`.")

        if requires_success and not clean_text(row.get("success_rule")):
            add(findings, "error", "PEAK success rule", f"{row_id}: requires_success is true but success_rule is blank.")

    advance = working[working["normalized_metric"].map(clean_text).eq("Advance")]
    if advance.empty:
        add(findings, "error", "Advance rule", "No Advance rows exist in PEAK normalization.")
    else:
        bad_advance = advance[
            ~advance["score_policy"].map(clean_text).eq("threshold_count")
            | pd.to_numeric(advance["threshold_count"], errors="coerce").ne(10)
            | pd.to_numeric(advance["threshold_score"], errors="coerce").ne(0.5)
        ]
        if not bad_advance.empty:
            labels = ", ".join(bad_advance["raw_label"].map(clean_text).tolist())
            add(findings, "error", "Advance rule", f"Advance rows must score 0.5 per 10 actions: {labels}.")

    punish_priority = pd.to_numeric(
        working.loc[working["peak_phase"].map(clean_text).eq("Punish"), "double_count_priority"],
        errors="coerce",
    ).min()
    advance_priority = pd.to_numeric(
        working.loc[working["peak_phase"].map(clean_text).eq("Advance"), "double_count_priority"],
        errors="coerce",
    ).min()
    if not pd.isna(punish_priority) and not pd.isna(advance_priority) and punish_priority >= advance_priority:
        add(
            findings,
            "error",
            "Punish priority",
            "Punish double_count_priority must be lower than Advance so Punish wins double-count conflicts.",
        )


def validate_metric_map(df: pd.DataFrame, findings: list[Finding]) -> None:
    if not require_columns(findings, "Wyscout metric map", df, METRIC_MAP_REQUIRED_COLUMNS):
        return

    working = df.copy()
    working["raw_metric_key"] = working["raw_metric_name"].map(normalize_key)

    duplicate_keys = sorted(
        key for key, count in working["raw_metric_key"].value_counts().items()
        if key and count > 1
    )
    if duplicate_keys:
        add(findings, "error", "Metric map duplicate raw labels", f"Duplicate raw_metric_name values: {', '.join(duplicate_keys)}")

    for idx, row in working.iterrows():
        row_id = f"row {idx + 2} ({clean_text(row.get('raw_metric_name'))})"
        bucket = clean_text(row.get("mapped_score_bucket"))
        status = clean_text(row.get("mapping_status"))
        include = boolish(row.get("default_include"))
        metric = clean_text(row.get("mapped_metric_name"))

        if bucket not in ALLOWED_BUCKETS:
            add(findings, "error", "Metric map bucket", f"{row_id}: unsupported mapped_score_bucket `{bucket}`.")
        if status not in ALLOWED_MAPPING_STATUSES:
            add(findings, "warning", "Metric map status", f"{row_id}: unexpected mapping_status `{status}`.")
        if include and status == "unmapped":
            add(findings, "error", "Metric map include", f"{row_id}: default_include true but mapping_status is unmapped.")
        if include and bucket != "peak" and not metric:
            add(findings, "error", "Metric map mapped metric", f"{row_id}: included non-PEAK row needs mapped_metric_name.")


def validate_cross_table(peak: pd.DataFrame, metric_map: pd.DataFrame, findings: list[Finding]) -> None:
    if peak.empty or metric_map.empty:
        return
    if not PEAK_REQUIRED_COLUMNS.issubset(peak.columns) or not METRIC_MAP_REQUIRED_COLUMNS.issubset(metric_map.columns):
        return

    peak_keys = set(peak["raw_label_key"].fillna(peak["raw_label"]).map(normalize_key))
    peak_keys.discard("")
    all_metric_map_keys = set(metric_map["raw_metric_name"].map(normalize_key))
    all_metric_map_keys.discard("")
    mapped_peak_keys = set(
        metric_map.loc[
            metric_map["mapped_score_bucket"].map(clean_text).eq("peak"),
            "raw_metric_name",
        ].map(normalize_key)
    )
    mapped_peak_keys.discard("")

    missing_from_metric_map = sorted(peak_keys.difference(all_metric_map_keys).difference(NORMALIZED_INPUT_ALIASES))
    if missing_from_metric_map:
        add(
            findings,
            "warning",
            "PEAK cross-table coverage",
            "PEAK normalization labels missing from wyscout_coug_metric_map.csv: "
            + ", ".join(missing_from_metric_map),
        )

    missing_from_peak = sorted(mapped_peak_keys.difference(peak_keys))
    if missing_from_peak:
        add(
            findings,
            "warning",
            "PEAK cross-table coverage",
            "Metric-map PEAK labels missing from wyscout_peak_normalization.csv: "
            + ", ".join(missing_from_peak),
        )


def markdown_table(findings: list[Finding]) -> str:
    if not findings:
        return "_No findings._"
    lines = [
        "| severity | check | detail |",
        "| --- | --- | --- |",
    ]
    for finding in findings:
        detail = finding.detail.replace("\n", " ").replace("|", "\\|")
        lines.append(f"| {finding.severity} | {finding.check} | {detail} |")
    return "\n".join(lines)


def write_report(output_path: Path, findings: list[Finding], peak_rows: int, metric_map_rows: int) -> None:
    errors = sum(1 for finding in findings if finding.severity == "error")
    warnings = sum(1 for finding in findings if finding.severity == "warning")
    lines = [
        "# Scoring Config Validation",
        "",
        "This report validates local Wyscout-to-COUG scoring configuration files.",
        "",
        "## Summary",
        "",
        f"- PEAK normalization rows: `{peak_rows}`",
        f"- Wyscout metric-map rows: `{metric_map_rows}`",
        f"- Errors: `{errors}`",
        f"- Warnings: `{warnings}`",
        "",
        "## Findings",
        "",
        markdown_table(findings),
        "",
        "## Validated Files",
        "",
        f"- `{PEAK_PATH.relative_to(REPO_ROOT)}`",
        f"- `{METRIC_MAP_PATH.relative_to(REPO_ROOT)}`",
        "",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate local scoring config files")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fail-on-warnings", action="store_true")
    args = parser.parse_args()

    findings: list[Finding] = []

    if not PEAK_PATH.exists():
        add(findings, "error", "PEAK file", f"Missing {PEAK_PATH.relative_to(REPO_ROOT)}")
        peak = pd.DataFrame()
    else:
        peak = pd.read_csv(PEAK_PATH)
        validate_peak_normalization(peak, findings)

    if not METRIC_MAP_PATH.exists():
        add(findings, "error", "Metric map file", f"Missing {METRIC_MAP_PATH.relative_to(REPO_ROOT)}")
        metric_map = pd.DataFrame()
    else:
        metric_map = pd.read_csv(METRIC_MAP_PATH)
        validate_metric_map(metric_map, findings)

    validate_cross_table(peak, metric_map, findings)
    write_report(args.output, findings, len(peak), len(metric_map))

    errors = sum(1 for finding in findings if finding.severity == "error")
    warnings = sum(1 for finding in findings if finding.severity == "warning")
    print(f"Scoring config validation: {errors} error(s), {warnings} warning(s)")
    print(f"Wrote {args.output}")

    if errors or (warnings and args.fail_on_warnings):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
