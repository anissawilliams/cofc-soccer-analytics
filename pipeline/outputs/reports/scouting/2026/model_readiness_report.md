# Scouting / ML Readiness Report

Organization: College of Charleston Men's Soccer
Training season: `2025`
Target scouting season: `2026`

## Executive Status

- Status: `CAUTION`
- Blocking errors: `0`
- Warnings: `2`

## Training Data

- Source file: `pipeline/data/raw/cofc_matches_2025.xlsx`
- Source exists: `True`
- Feature rows: `16`
- Usable model rows: `16`
- Minimum recommended matches: `30`
- Outcome labels: `{'D': 3, 'L': 7, 'W': 6}`

## Model Outputs

- Model directory: `pipeline/outputs/reports/scouting/2025/models`
- Missing outputs: `[]`
- Accuracy: `0.625`
- Log loss: `1.295`
- Small-sample warning: `True`

## Target Schedule

- Source file: `pipeline/data/schedules/2026_schedule.csv`
- Source exists: `True`
- Matches: `19`
- Date range: `2026-08-07` to `2026-10-30`
- Rows with opponent team ID: `19`
- Rows with Wyscout team ID: `0`

## Warnings

- Only 16 usable matches; configured minimum recommendation is 30.
- Model metrics carry a small-sample warning.

## Blocking Errors

_None._

## Interpretation

- Use this model lane for scouting workflow, simulation, and explainable ML artifacts.
- Do not treat current probabilities as high-confidence until the training sample expands.
- COUG Table scoring remains coach-defined and should feed this lane only after score provenance is stable.
