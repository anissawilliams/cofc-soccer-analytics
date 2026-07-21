# Predictive Modeling Roadmap

This roadmap describes how the CofC soccer analytics pipeline can mature from the current match-modeling scaffold into a more robust predictive scouting system.

Current status: prototype / exploratory. The architecture exists, but model outputs should not be treated as validated coaching recommendations until the feature set, training sample, and evaluation reports improve.

## Current Foundation

The project already includes the core pieces needed to support predictive modeling:

- 2025 match-model scaffold in `pipeline/scouting/build_match_model.py`
- Leave-one-out evaluation over available CofC matches
- 2026 schedule QA and opponent report shells
- Staff portal prediction simulator seeded from future match context
- Supabase-backed source/entity structure for reproducible data joins
- COUG Table outputs that can eventually become team-level predictive features

Known current limitations:

- Training sample is small.
- Opponent historical data is incomplete.
- Spiideo is future-facing, not a current structured source.
- Catapult/load features are schema-ready but need stronger routine ingestion.
- Current simulator uses transparent prototype assumptions, not a fully validated model.

## Literature-Informed Direction

Two soccer forecasting papers are especially useful for shaping the next phase:

- Baboota and Kaur, 2019: useful for rolling form, engineered differentials, draw difficulty, ranked probability score, and calibration.
- Wong et al., 2025: useful for predictive analytics framework design, fatigue, momentum, weather/context features, LightGBM, CNNs, stacking, and voting ensembles.

The main lesson: predictive performance depends less on choosing one fancy model and more on building the right feature history, evaluation loop, and uncertainty communication.

Source and reconciliation plan:

- `docs/analytics/scouting/predictive_modeling_source_plan.md`

## Phase 1: Baseline Model Hardening

Goal: make the existing model scaffold honest, repeatable, and easy to evaluate.

Implementation status: started. The match model now reports ranked probability score, draw recall, majority-class baseline metrics, a confusion matrix CSV, and a calibration summary CSV.

Add evaluation metrics:

- Accuracy
- Log loss
- Ranked probability score: implemented
- Confusion matrix: implemented
- Draw recall: implemented
- Calibration summary: implemented

Add baseline comparisons:

- Majority-class baseline
- Home-field baseline
- Recent-form baseline
- Simple Poisson baseline

Deliverables:

- `match_model_summary.md` with all metrics
- `match_model_predictions.csv`
- `match_model_confusion_matrix.csv`
- `match_model_calibration.csv`

Success criteria:

- Every model run produces the same output contract.
- Reports clearly label readiness as `BLOCKED`, `CAUTION`, or `READY`.
- Draw performance is evaluated explicitly.

## Phase 2: Rolling Momentum Features

Goal: give the model temporally meaningful inputs instead of static match rows.

Implementation status: scaffolded. The feature builder now creates pre-match rolling momentum columns and the model command writes `match_feature_matrix.csv` and `match_feature_coverage.csv`. These features are not yet promoted into the active model config because opponent historical coverage is still sparse.

Candidate features:

- Last 3 and last 5 match points per game
- Weighted recent form: scaffolded
- Rolling goals for and against
- Rolling goal differential
- Rolling xG and xG differential
- Rolling shots and shots-on-target differential
- Rolling possession differential
- Rolling COUG team score, when stable
- Rolling ASET, PEAK, and set-piece team trends, when stable

Feature design principles:

- Compute features using only matches before the target match.
- Keep season boundaries explicit.
- Store both raw team features and CofC-minus-opponent differentials.
- Avoid leakage from post-match reports into pre-match predictions.

Deliverables:

- `pipeline/scouting/features.py` rolling feature helpers: implemented
- `match_feature_matrix.csv`: implemented
- `match_feature_coverage.csv`: implemented
- Feature dictionary update: pending

## Phase 3: Fatigue and Availability Features

Goal: incorporate the sports-performance context that is unique to CofC.

Candidate features:

- Days since last match
- Matches in prior 7, 10, and 14 days
- Home/away travel sequence
- Away travel distance
- Short-rest flag
- Catapult rolling load, when available
- Team-level high-speed distance trend
- Projected lineup availability
- Returning starter count
- Minutes concentration among likely starters

Why this matters:

Wong et al. explicitly include fatigue and momentum constructs. CofC has an advantage here because Catapult and internal player availability data can make the model more program-specific than a public-data EPL model.

Deliverables:

- Fatigue feature module
- Catapult/load feature extraction contract
- Staff portal explanation text for fatigue/context drivers

## Phase 4: Weather and Match Context

Goal: add context that may affect match style, tempo, and risk.

Candidate features:

- Temperature
- Humidity
- Wind speed
- Precipitation flag
- Surface, if available
- Home/away/neutral
- Conference match flag
- Exhibition flag
- Venue
- Travel distance

Implementation note:

Weather should be added after the core model pipeline is stable. It is useful, but it should not distract from higher-value features like form, shot quality, opponent strength, and fatigue.

## Phase 5: Model Comparison

Goal: compare simple and advanced models using the same feature matrix and metrics.

Models to test:

- Multinomial logistic regression
- Poisson / bivariate Poisson score model
- Random forest
- Gradient boosting
- LightGBM, if dependency and deployment constraints are acceptable
- Voting ensemble
- Stacking ensemble

Recommended order:

1. Logistic regression baseline
2. Poisson scoreline model
3. Random forest
4. Gradient boosting
5. Ensemble only after the individual models are stable

Avoid:

- Overfitting a tiny sample with complex models
- Treating accuracy alone as model quality
- Presenting uncalibrated probabilities as decision-ready

## Phase 6: Probability Calibration

Goal: make probabilities interpretable for coaches.

Add:

- Reliability/calibration curves
- Expected calibration error, if useful
- Calibrated classifier wrappers where appropriate
- Plain-language confidence labels

Coach-facing examples:

- `High confidence`: model inputs are complete and model agreement is strong.
- `Moderate confidence`: model has enough data, but probabilities are close.
- `Low confidence`: sparse opponent history or unstable feature coverage.

This should feed directly into the Staff portal.

## Phase 7: Staff Portal Integration

Goal: connect model outputs to coaching workflows.

Near-term Staff portal views:

- Select upcoming 2026 match
- Show model readiness
- Show win/draw/loss probabilities
- Show most likely scorelines
- Show top model drivers
- Show fatigue/context flags
- Allow scenario adjustment with dials

Important design principle:

The simulator should start from model or schedule-informed baselines, then let coaches adjust assumptions. It should not present generic sliders with no connection to the selected opponent.

## Phase 8: Opponent Scouting Integration

Goal: connect predictive modeling to opponent report shells.

Inputs:

- Opponent Wyscout match reports
- Opponent rolling form
- Opponent shot/xG profile
- Opponent set-piece profile
- Opponent formation tendencies
- Results against similar formations or styles, when available

Outputs:

- Opponent summary
- Matchup risks
- Key tactical drivers
- Model driver explanation
- Recommended film questions

## Phase 9: Professionalization

Goal: make the predictive lane portable and maintainable.

Add:

- Config-driven feature sets
- Versioned model outputs
- Model registry-style metadata
- Data freshness checks
- Reproducible train/evaluate commands
- Clear source-file provenance
- GitHub Actions smoke tests

Recommended metadata per model run:

- Model version
- Training seasons
- Number of matches
- Feature set version
- Evaluation metrics
- Generated timestamp
- Data readiness status

## Suggested Practicum Language

Use this framing in the practicum report or deck:

> The practicum established an exploratory predictive modeling pipeline for match outcome forecasting and tactical scouting. The current implementation includes feature engineering hooks, model training and evaluation scaffolds, 2026 schedule readiness checks, opponent report shells, and a staff-facing prediction simulator. Recent soccer forecasting literature suggests clear next-stage improvements, including rolling momentum features, fatigue/load covariates, weather and match-context features, ensemble learning, probability calibration, and ranked probability scoring.

## Near-Term Build Queue

Highest-impact next tasks:

1. Add ranked probability score to model evaluation.
2. Add rolling form and differential features.
3. Add draw recall and calibration reporting.
4. Add fatigue/context feature placeholders.
5. Connect Staff portal simulator to generated model outputs.
6. Add opponent historical feature ingestion when Wyscout reports become available.

This sequence keeps the model honest while steadily moving it toward a professional scouting product.
