from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline.core.config_loader import load_project_config  # noqa: E402
from pipeline.scouting.features import (  # noqa: E402
    build_match_features,
    feature_matrix,
    load_wyscout_match_stats,
)
from pipeline.scouting.schedule import (  # noqa: E402
    load_schedule,
    summarize_schedule,
    validate_schedule,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a scouting/ML readiness report across training data, model outputs, and target schedule."
    )
    parser.add_argument("--org", default="cofc", help="Organization config key.")
    parser.add_argument("--train-season", default="2025", help="Season used for model training/evaluation.")
    parser.add_argument("--target-season", default="2026", help="Season being prepared for scouting reports.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    train_config = load_project_config(args.org, args.train_season, repo_root=REPO_ROOT)
    target_config = load_project_config(args.org, args.target_season, repo_root=REPO_ROOT)

    training = assess_training_data(train_config)
    model_outputs = assess_model_outputs(train_config)
    schedule = assess_schedule(target_config)

    output_dir = target_config.output_path("scouting_dir")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "model_readiness_report.md"
    output_path.write_text(
        build_markdown(
            train_config=train_config,
            target_config=target_config,
            training=training,
            model_outputs=model_outputs,
            schedule=schedule,
        ),
        encoding="utf-8",
    )

    overall_status = "READY_WITH_LIMITATIONS"
    if training["blocking_errors"] or model_outputs["blocking_errors"] or schedule["blocking_errors"]:
        overall_status = "BLOCKED"
    elif training["warnings"] or model_outputs["warnings"] or schedule["warnings"]:
        overall_status = "CAUTION"

    print(f"Model readiness: {overall_status}")
    print(f"Training matches: {training['n_matches']}")
    print(f"Target schedule matches: {schedule['matches']}")
    print(f"Wrote {output_path}")

    if overall_status == "BLOCKED":
        raise SystemExit(1)


def assess_training_data(config) -> dict[str, object]:
    model_config = config.season["modeling"]
    feature_columns = list(model_config["feature_columns"])
    minimum_recommended = int(model_config.get("minimum_recommended_matches", 30))
    labels = list(model_config["outcome_labels"])
    path_value = config.season.get("team_match_stats_path")

    result = {
        "source_file": path_value or "",
        "exists": False,
        "n_matches": 0,
        "labels": {},
        "feature_columns": feature_columns,
        "missing_features": [],
        "null_feature_counts": {},
        "minimum_recommended_matches": minimum_recommended,
        "blocking_errors": [],
        "warnings": [],
    }
    if not path_value:
        result["blocking_errors"].append("No team_match_stats_path configured.")
        return result

    path = config.resolve_path(path_value)
    result["exists"] = path.exists()
    if not path.exists():
        result["blocking_errors"].append(f"Training source file missing: {path.relative_to(config.repo_root)}")
        return result

    raw_matches = load_wyscout_match_stats(path, config.org["team_name"])
    features = build_match_features(raw_matches)
    result["n_matches"] = int(len(features))
    result["labels"] = {
        str(label): int(count)
        for label, count in features["result"].value_counts(dropna=False).sort_index().items()
    }

    missing_features = [column for column in feature_columns if column not in features.columns]
    result["missing_features"] = missing_features
    if missing_features:
        result["blocking_errors"].append(f"Missing configured feature columns: {missing_features}")
        return result

    X, y = feature_matrix(features, feature_columns)
    result["n_model_rows"] = int(len(X))
    result["null_feature_counts"] = {
        column: int(pd.to_numeric(features[column], errors="coerce").isna().sum())
        for column in feature_columns
    }

    observed_labels = set(y.astype(str))
    missing_labels = sorted(set(labels).difference(observed_labels))
    if missing_labels:
        result["warnings"].append(f"No training examples for labels: {missing_labels}")
    if len(X) < minimum_recommended:
        result["warnings"].append(
            f"Only {len(X)} usable matches; configured minimum recommendation is {minimum_recommended}."
        )
    if len(observed_labels) < 2:
        result["blocking_errors"].append("Training data has fewer than two outcome classes.")
    return result


def assess_model_outputs(config) -> dict[str, object]:
    model_dir = config.output_path("model_dir")
    required = [
        "match_model_predictions.csv",
        "match_model_feature_importance.csv",
        "match_model_metrics.json",
        "match_simulation_backtest.csv",
        "match_model_summary.md",
    ]
    result = {
        "model_dir": str(model_dir.relative_to(config.repo_root)),
        "required_outputs": required,
        "missing_outputs": [],
        "metrics": {},
        "blocking_errors": [],
        "warnings": [],
    }
    missing = [name for name in required if not (model_dir / name).exists()]
    result["missing_outputs"] = missing
    if missing:
        result["blocking_errors"].append(f"Missing model outputs: {missing}")
        return result

    metrics_path = model_dir / "match_model_metrics.json"
    with metrics_path.open("r", encoding="utf-8") as handle:
        metrics = json.load(handle)
    result["metrics"] = metrics
    if metrics.get("small_sample_warning"):
        result["warnings"].append("Model metrics carry a small-sample warning.")
    return result


def assess_schedule(config) -> dict[str, object]:
    path_value = config.season.get("schedule_path")
    result = {
        "source_file": path_value or "",
        "exists": False,
        "matches": 0,
        "summary": {},
        "validation_errors": [],
        "validation_warnings": [],
        "blocking_errors": [],
        "warnings": [],
    }
    if not path_value:
        result["blocking_errors"].append("No schedule_path configured.")
        return result

    path = config.resolve_path(path_value)
    result["exists"] = path.exists()
    if not path.exists():
        result["blocking_errors"].append(f"Schedule source file missing: {path.relative_to(config.repo_root)}")
        return result

    schedule = load_schedule(path)
    validation = validate_schedule(schedule, expected_season=config.season_label)
    summary = summarize_schedule(schedule)
    result["matches"] = int(summary["matches"])
    result["summary"] = summary
    result["validation_errors"] = validation.errors
    result["validation_warnings"] = validation.warnings
    if validation.errors:
        result["blocking_errors"].extend(validation.errors)
    if validation.warnings:
        result["warnings"].extend(validation.warnings)
    return result


def build_markdown(train_config, target_config, training: dict, model_outputs: dict, schedule: dict) -> str:
    lines = [
        "# Scouting / ML Readiness Report",
        "",
        f"Organization: {train_config.org['display_name']}",
        f"Training season: `{train_config.season_label}`",
        f"Target scouting season: `{target_config.season_label}`",
        "",
        "## Executive Status",
        "",
    ]
    blocking = training["blocking_errors"] + model_outputs["blocking_errors"] + schedule["blocking_errors"]
    warnings = training["warnings"] + model_outputs["warnings"] + schedule["warnings"]
    if blocking:
        lines.append("- Status: `BLOCKED`")
    elif warnings:
        lines.append("- Status: `CAUTION`")
    else:
        lines.append("- Status: `READY_WITH_LIMITATIONS`")
    lines.extend([
        f"- Blocking errors: `{len(blocking)}`",
        f"- Warnings: `{len(warnings)}`",
        "",
        "## Training Data",
        "",
        f"- Source file: `{training['source_file']}`",
        f"- Source exists: `{training['exists']}`",
        f"- Feature rows: `{training['n_matches']}`",
        f"- Usable model rows: `{training.get('n_model_rows', 0)}`",
        f"- Minimum recommended matches: `{training['minimum_recommended_matches']}`",
        f"- Outcome labels: `{training['labels']}`",
        "",
        "## Model Outputs",
        "",
        f"- Model directory: `{model_outputs['model_dir']}`",
        f"- Missing outputs: `{model_outputs['missing_outputs']}`",
    ])
    metrics = model_outputs.get("metrics") or {}
    if metrics:
        lines.extend([
            f"- Accuracy: `{float(metrics.get('accuracy', 0.0)):.3f}`",
            f"- Log loss: `{float(metrics.get('log_loss', 0.0)):.3f}`",
            f"- Small-sample warning: `{metrics.get('small_sample_warning', False)}`",
        ])
    lines.extend([
        "",
        "## Target Schedule",
        "",
        f"- Source file: `{schedule['source_file']}`",
        f"- Source exists: `{schedule['exists']}`",
        f"- Matches: `{schedule['matches']}`",
    ])
    summary = schedule.get("summary") or {}
    if summary:
        lines.extend([
            f"- Date range: `{summary.get('first_match')}` to `{summary.get('last_match')}`",
            f"- Rows with opponent team ID: `{summary.get('rows_with_opponent_team_id')}`",
            f"- Rows with Wyscout team ID: `{summary.get('rows_with_wyscout_team_id')}`",
        ])

    lines.extend(["", "## Warnings", ""])
    lines.extend(format_list(warnings))
    lines.extend(["", "## Blocking Errors", ""])
    lines.extend(format_list(blocking))
    lines.extend([
        "",
        "## Interpretation",
        "",
        "- Use this model lane for scouting workflow, simulation, and explainable ML artifacts.",
        "- Do not treat current probabilities as high-confidence until the training sample expands.",
        "- COUG Table scoring remains coach-defined and should feed this lane only after score provenance is stable.",
        "",
    ])
    return "\n".join(lines)


def format_list(values: list[str]) -> list[str]:
    if not values:
        return ["_None._"]
    return [f"- {value}" for value in values]


if __name__ == "__main__":
    main()
