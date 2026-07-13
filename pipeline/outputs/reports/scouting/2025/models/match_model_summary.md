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
- Labels: W, D, L

## Outputs

- Predictions: `pipeline/outputs/reports/scouting/2025/models/match_model_predictions.csv`
- Feature importance: `pipeline/outputs/reports/scouting/2025/models/match_model_feature_importance.csv`
- Metrics JSON: `pipeline/outputs/reports/scouting/2025/models/match_model_metrics.json`
- Poisson simulation backtest: `pipeline/outputs/reports/scouting/2025/models/match_simulation_backtest.csv`

## Notes

This is the first professionalized scouting/modeling lane. It is separate from
COUG Table scoring: the COUG Table remains a coach-defined evaluation framework,
while this model is used for outcome prediction, tactical scouting, feature
importance, and simulation.
