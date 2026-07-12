from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix
from sklearn.model_selection import LeaveOneOut
from sklearn.preprocessing import StandardScaler


def evaluate_logistic_loo(
    X: pd.DataFrame,
    y: pd.Series,
    labels: list[str],
    random_state: int,
) -> tuple[dict[str, Any], pd.DataFrame]:
    """Evaluate a multinomial logistic model with leave-one-out CV."""

    actuals: list[str] = []
    predictions: list[str] = []
    probabilities: list[list[float]] = []

    loo = LeaveOneOut()
    for train_index, test_index in loo.split(X):
        X_train = X.iloc[train_index]
        X_test = X.iloc[test_index]
        y_train = y.iloc[train_index]
        y_test = y.iloc[test_index]

        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)

        model = LogisticRegression(
            max_iter=1000,
            random_state=random_state,
        )
        model.fit(X_train_scaled, y_train)

        fold_proba = _aligned_probability_row(model, X_test_scaled, labels)
        pred = labels[int(np.argmax(fold_proba))]

        actuals.append(str(y_test.iloc[0]))
        predictions.append(pred)
        probabilities.append(fold_proba)

    proba_frame = pd.DataFrame(probabilities, columns=[f"prob_{label}" for label in labels])
    prediction_frame = pd.DataFrame(
        {
            "actual": actuals,
            "predicted": predictions,
            "correct": [actual == predicted for actual, predicted in zip(actuals, predictions)],
        }
    )
    prediction_frame = pd.concat([prediction_frame, proba_frame], axis=1)

    probability_array = np.array(probabilities)
    metrics = {
        "model_type": "multinomial_logistic_regression",
        "validation_method": "leave_one_out_cross_validation",
        "n_matches": int(len(y)),
        "labels": labels,
        "accuracy": float(accuracy_score(actuals, predictions)),
        "log_loss": float(_negative_log_likelihood(actuals, probability_array, labels)),
        "confusion_matrix": _confusion_matrix_dict(actuals, predictions, labels),
    }
    return metrics, prediction_frame


def fit_feature_importance(
    X: pd.DataFrame,
    y: pd.Series,
    random_state: int,
) -> pd.DataFrame:
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    model = LogisticRegression(
        max_iter=1000,
        random_state=random_state,
    )
    model.fit(X_scaled, y)

    importance = np.mean(np.abs(model.coef_), axis=0)
    return (
        pd.DataFrame({"feature": X.columns, "importance": importance})
        .sort_values("importance", ascending=False)
        .reset_index(drop=True)
    )


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, default=str)
        handle.write("\n")


def _aligned_probability_row(
    model: LogisticRegression,
    X_test_scaled: np.ndarray,
    labels: list[str],
) -> list[float]:
    raw = model.predict_proba(X_test_scaled)[0]
    aligned = np.full(len(labels), 1e-9, dtype=float)
    class_to_probability = dict(zip(model.classes_, raw))
    for index, label in enumerate(labels):
        if label in class_to_probability:
            aligned[index] = class_to_probability[label]
    aligned = aligned / aligned.sum()
    return aligned.tolist()


def _confusion_matrix_dict(
    actuals: list[str],
    predictions: list[str],
    labels: list[str],
) -> dict[str, dict[str, int]]:
    matrix = confusion_matrix(actuals, predictions, labels=labels)
    return {
        actual_label: {
            predicted_label: int(matrix[actual_index, predicted_index])
            for predicted_index, predicted_label in enumerate(labels)
        }
        for actual_index, actual_label in enumerate(labels)
    }


def _negative_log_likelihood(
    actuals: list[str],
    probabilities: np.ndarray,
    labels: list[str],
) -> float:
    label_to_index = {label: index for index, label in enumerate(labels)}
    losses = []
    for row_index, actual in enumerate(actuals):
        probability = probabilities[row_index, label_to_index[actual]]
        losses.append(-np.log(max(probability, 1e-15)))
    return float(np.mean(losses))
