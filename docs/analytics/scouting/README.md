# Scouting and Match Outcome Modeling

This folder documents the scouting/modeling lane. It is intentionally separate
from COUG Table scoring:

- COUG Table: coach-defined ASET, PEAK, and Set Piece player evaluation.
- Scouting/modeling: probabilistic match outcome modeling, simulation, feature
  importance, and opponent preparation.

## Current Build

The first reusable command is:

```bash
.venv/bin/python pipeline/scouting/build_match_model.py --org cofc --season 2025
```

The 2026 schedule QA command is:

```bash
.venv/bin/python pipeline/scouting/build_schedule_report.py --org cofc --season 2026
```

The 2026 opponent shell command is:

```bash
.venv/bin/python pipeline/scouting/build_opponent_shells.py --org cofc --season 2026
```

It reads organization and season config from:

- `configs/organizations/cofc.json`
- `configs/seasons/cofc_2025.json`
- `configs/seasons/cofc_2026.json`

It writes model outputs to:

- `pipeline/outputs/reports/scouting/2025/models/match_model_predictions.csv`
- `pipeline/outputs/reports/scouting/2025/models/match_model_feature_importance.csv`
- `pipeline/outputs/reports/scouting/2025/models/match_model_metrics.json`
- `pipeline/outputs/reports/scouting/2025/models/match_simulation_backtest.csv`
- `pipeline/outputs/reports/scouting/2025/models/match_model_summary.md`
- `pipeline/outputs/reports/scouting/2026/schedule/schedule_qa_report.md`
- `pipeline/outputs/reports/scouting/2026/schedule/schedule_clean.csv`
- `pipeline/outputs/reports/scouting/2026/schedule/schedule_summary.json`
- `pipeline/outputs/reports/scouting/2026/opponents/<match_slug>/executive_brief.md`
- `pipeline/outputs/reports/scouting/2026/opponents/<match_slug>/data_profile.md`
- `pipeline/outputs/reports/scouting/2026/opponents/<match_slug>/simulation.md`
- `pipeline/outputs/reports/scouting/2026/opponents/<match_slug>/set_pieces.md`
- `pipeline/outputs/reports/scouting/2026/opponents/<match_slug>/match_day_observation.md`
- `pipeline/outputs/reports/scouting/2026/opponents/<match_slug>/post_match_validation.md`
- `pipeline/outputs/reports/scouting/2026/opponents/<match_slug>/qa_report.md`

## Why This Counts as ML

The match model uses supervised classification with leave-one-out
cross-validation. It reports accuracy, log loss, confusion matrix, and feature
importance. With only one partial season, it should be presented as a workflow
and decision-support model, not a final high-confidence predictive product.

## What To Add Next

1. Add the 2026 schedule as a CSV once available.
2. Add 2024 match stats to increase training sample size.
3. Add a pre-match report command that joins the schedule, opponent history, and
   model outputs.
4. Add COUG Table match-level features once the scoring reconciliation is
   stable.
5. Add a GitHub Actions workflow that runs config checks and a dry-run model
   build on pull requests.
