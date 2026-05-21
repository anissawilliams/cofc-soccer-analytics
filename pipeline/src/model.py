import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import LeaveOneOut
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report
import warnings
warnings.filterwarnings('ignore')

# Import our ingest module
import sys
sys.path.append('.')
from config import TEAM_INGEST_DIR
from ingest import load_matches, build_match_features

ingest_dir = TEAM_INGEST_DIR

def prepare_features(features):
    """Select and prepare feature columns for modeling."""
    feature_cols = [
        'xg_cofc', 'xg_opp', 'xg_diff',
        'shots_cofc', 'shots_opp', 'shot_diff',
        'shots_on_target_cofc', 'shots_on_target_opp',
        'pass_accuracy_pct_cofc', 'pass_accuracy_pct_opp', 'pass_acc_diff',
        'possession_pct_cofc', 'possession_pct_opp', 'possession_diff',
        'recoveries_cofc', 'recoveries_opp', 'recovery_diff',
        'duels_won_cofc', 'duels_won_opp',
    ]

    X = features[feature_cols].copy()
    y = features['result'].copy()

    return X, y, feature_cols


def train_and_evaluate(X, y):
    """
    Train logistic regression with Leave-One-Out cross validation.
    LOO is appropriate for small datasets like this.
    """
    scaler = StandardScaler()
    model = LogisticRegression(max_iter=1000, random_state=42)

    loo = LeaveOneOut()
    predictions = []
    actuals = []

    for train_idx, test_idx in loo.split(X):
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)

        model.fit(X_train_scaled, y_train)
        pred = model.predict(X_test_scaled)

        predictions.append(pred[0])
        actuals.append(y_test.iloc[0])

    return actuals, predictions


def get_feature_importance(X, y, feature_cols):
    """Fit on full dataset and return feature coefficients."""
    scaler = StandardScaler()
    model = LogisticRegression(max_iter=1000, random_state=42)

    X_scaled = scaler.fit_transform(X)
    model.fit(X_scaled, y)

    # Average absolute coefficient across classes
    importance = np.mean(np.abs(model.coef_), axis=0)
    importance_df = pd.DataFrame({
        'feature': feature_cols,
        'importance': importance
    }).sort_values('importance', ascending=False)

    return importance_df


if __name__ == '__main__':
    # Load data
    print("Loading match data...")
    df = load_matches(ingest_dir + 'cofc_matches_2025.xlsx')
    features = build_match_features(df)

    print(f"Matches available: {len(features)}")
    print(f"Results: {features['result'].value_counts().to_dict()}")
    print()

    # Prepare features
    X, y, feature_cols = prepare_features(features)

    # Train and evaluate with LOO CV
    print("Running Leave-One-Out Cross Validation...")
    actuals, predictions = train_and_evaluate(X, y)

    # Results
    accuracy = accuracy_score(actuals, predictions)
    print(f"\nLOO Accuracy: {accuracy:.1%}")
    print()
    print("Classification Report:")
    print(classification_report(actuals, predictions, zero_division=0))
    print()
    print("Confusion Matrix (rows=actual, cols=predicted):")
    labels = ['W', 'D', 'L']
    cm = confusion_matrix(actuals, predictions, labels=labels)
    cm_df = pd.DataFrame(cm, index=labels, columns=labels)
    print(cm_df)
    print()

    # Feature importance
    print("Feature Importance (averaged across W/D/L classes):")
    importance_df = get_feature_importance(X, y, feature_cols)
    print(importance_df.to_string(index=False))

    # Match-by-match predictions
    print("\nMatch-by-Match Predictions:")
    results_df = features[['date', 'match', 'result']].copy()
    results_df['predicted'] = predictions
    results_df['correct'] = results_df['result'] == results_df['predicted']
    print(results_df[['date', 'match', 'result', 'predicted', 'correct']].to_string(index=False))