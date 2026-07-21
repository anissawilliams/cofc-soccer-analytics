# Match Outcome Model Summary

Organization: College of Charleston Men's Soccer
Season: 2025
Source file: `pipeline/data/raw/cofc_matches_2025.xlsx`
Validation: leave-one-out cross-validation
Model: multinomial logistic regression
Matches: 16


> Small-sample warning: this model is useful for a practicum-grade ML workflow and coaching discussion, but should not be treated as a high-confidence betting or personnel decision model yet.

## Metrics

- Accuracy: 0.625
- Log loss: 1.295
- Ranked probability score: 0.227
- Draw recall: 0.333
- Majority baseline accuracy: 0.438
- Majority baseline RPS: 0.240
- Labels: W, D, L

## Outputs

- Predictions: `pipeline/outputs/reports/scouting/2025/models/match_model_predictions.csv`
- Feature matrix: `pipeline/outputs/reports/scouting/2025/models/match_feature_matrix.csv`
- Feature coverage: `pipeline/outputs/reports/scouting/2025/models/match_feature_coverage.csv`
- Feature importance: `pipeline/outputs/reports/scouting/2025/models/match_model_feature_importance.csv`
- Metrics JSON: `pipeline/outputs/reports/scouting/2025/models/match_model_metrics.json`
- Baseline metrics: `pipeline/outputs/reports/scouting/2025/models/match_model_baselines.json`
- Confusion matrix: `pipeline/outputs/reports/scouting/2025/models/match_model_confusion_matrix.csv`
- Calibration summary: `pipeline/outputs/reports/scouting/2025/models/match_model_calibration.csv`
- Poisson simulation backtest: `pipeline/outputs/reports/scouting/2025/models/match_simulation_backtest.csv`

## Feature Matrix Notes

The feature matrix includes rolling momentum scaffold columns. CofC rolling
features are useful for inspection now, but opponent rolling features remain
sparse until opponent historical match data is added. These rolling columns are
therefore generated and coverage-reported, but not yet included in the active
model feature config.

## Notes

This is the first professionalized scouting/modeling lane. It is separate from
COUG Table scoring: the COUG Table remains a coach-defined evaluation framework,
while this model is used for outcome prediction, tactical scouting, feature
importance, and simulation.
