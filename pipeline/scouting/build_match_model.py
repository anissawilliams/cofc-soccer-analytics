from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline.core.config_loader import load_project_config
from pipeline.scouting.features import (
    build_match_features,
    feature_matrix,
    load_wyscout_match_stats,
)
from pipeline.scouting.modeling import (
    evaluate_logistic_loo,
    fit_feature_importance,
    write_json,
)
from pipeline.scouting.simulation import simulate_from_match_features


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build match outcome scouting model outputs for one organization-season."
    )
    parser.add_argument("--org", default="cofc", help="Organization config key.")
    parser.add_argument("--season", default="2025", help="Season label.")
    parser.add_argument(
        "--n-simulations",
        type=int,
        default=10000,
        help="Monte Carlo simulations per historical match.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_project_config(args.org, args.season, repo_root=REPO_ROOT)
    model_config = config.season["modeling"]
    random_state = int(model_config.get("random_state", 42))
    labels = list(model_config["outcome_labels"])
    feature_columns = list(model_config["feature_columns"])

    match_stats_path = config.resolve_path(config.season["team_match_stats_path"])
    model_dir = config.output_path("model_dir")
    model_dir.mkdir(parents=True, exist_ok=True)

    raw_matches = load_wyscout_match_stats(match_stats_path, config.org["team_name"])
    features = build_match_features(raw_matches)
    X, y = feature_matrix(features, feature_columns)

    metrics, predictions = evaluate_logistic_loo(
        X=X,
        y=y,
        labels=labels,
        random_state=random_state,
    )
    minimum_recommended = int(model_config.get("minimum_recommended_matches", 30))
    metrics["small_sample_warning"] = len(y) < minimum_recommended
    metrics["minimum_recommended_matches"] = minimum_recommended
    metrics["source_file"] = str(match_stats_path.relative_to(config.repo_root))

    predictions = predictions.join(
        features.loc[predictions.index, ["date", "match", "opponent"]]
    )
    predictions = predictions[
        ["date", "match", "opponent", "actual", "predicted", "correct"]
        + [f"prob_{label}" for label in labels]
    ]
    importance = fit_feature_importance(X, y, random_state=random_state)
    simulation = simulate_from_match_features(
        features,
        n_simulations=args.n_simulations,
        random_state=random_state,
    )

    predictions_path = model_dir / "match_model_predictions.csv"
    importance_path = model_dir / "match_model_feature_importance.csv"
    metrics_path = model_dir / "match_model_metrics.json"
    simulation_path = model_dir / "match_simulation_backtest.csv"
    summary_path = model_dir / "match_model_summary.md"

    predictions.to_csv(predictions_path, index=False)
    importance.to_csv(importance_path, index=False)
    simulation.to_csv(simulation_path, index=False)
    write_json(metrics_path, metrics)
    summary_path.write_text(
        _build_summary_markdown(
            config=config,
            n_matches=len(y),
            metrics=metrics,
            predictions_path=predictions_path,
            importance_path=importance_path,
            metrics_path=metrics_path,
            simulation_path=simulation_path,
        ),
        encoding="utf-8",
    )

    print(f"Built scouting model outputs for {config.org['short_name']} {config.season_label}")
    print(f"Matches: {len(y)}")
    print(f"LOO accuracy: {metrics['accuracy']:.3f}")
    print(f"LOO log loss: {metrics['log_loss']:.3f}")
    print(f"Outputs: {model_dir}")


def _build_summary_markdown(
    config,
    n_matches: int,
    metrics: dict,
    predictions_path: Path,
    importance_path: Path,
    metrics_path: Path,
    simulation_path: Path,
) -> str:
    warning = ""
    if metrics["small_sample_warning"]:
        warning = (
            "\n> Small-sample warning: this model is useful for a practicum-grade "
            "ML workflow and coaching discussion, but should not be treated as a "
            "high-confidence betting or personnel decision model yet.\n"
        )

    rel = lambda path: path.relative_to(config.repo_root)
    return f"""# Match Outcome Model Summary

Organization: {config.org["display_name"]}
Season: {config.season_label}
Source file: `{metrics["source_file"]}`
Validation: leave-one-out cross-validation
Model: multinomial logistic regression
Matches: {n_matches}

{warning}
## Metrics

- Accuracy: {metrics["accuracy"]:.3f}
- Log loss: {metrics["log_loss"]:.3f}
- Labels: {", ".join(metrics["labels"])}

## Outputs

- Predictions: `{rel(predictions_path)}`
- Feature importance: `{rel(importance_path)}`
- Metrics JSON: `{rel(metrics_path)}`
- Poisson simulation backtest: `{rel(simulation_path)}`

## Notes

This is the first professionalized scouting/modeling lane. It is separate from
COUG Table scoring: the COUG Table remains a coach-defined evaluation framework,
while this model is used for outcome prediction, tactical scouting, feature
importance, and simulation.
"""


if __name__ == "__main__":
    main()
