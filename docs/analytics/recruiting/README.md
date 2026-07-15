# Recruiting Similarity

This folder documents the recruiting/player-similarity modeling lane.

It is intentionally separate from:

- COUG Table scoring: coach-defined player evaluation
- Opposition scouting: opponent/team preparation

## Current Build

Recruiting config:

```text
configs/organizations/cofc_recruiting.json
```

Expected player-profile schema:

```text
pipeline/config/recruiting_player_profile_schema.csv
```

Product spec:

```text
docs/analytics/recruiting/player_similarity_product_spec.md
```

Readiness command:

```bash
.venv/bin/python pipeline/recruiting/build_recruiting_readiness_report.py
```

Internal CofC profile export command:

```bash
.venv/bin/python pipeline/recruiting/export_internal_profiles.py --season 2025
```

This writes an ignored local CSV:

```text
pipeline/data/recruiting/internal_player_profiles.csv
```

Current expected status is `BLOCKED` until the recruit profile file exists:

```text
pipeline/data/recruiting/recruit_player_profiles.csv
```

Similarity scoring command (with recruit profiles):

```bash
.venv/bin/python pipeline/recruiting/build_similarity_scores.py --season 2025
```

Internal-only validation (no recruit profiles needed — tests the full engine
against the CofC roster):

```bash
.venv/bin/python pipeline/recruiting/build_similarity_scores.py --season 2025 --internal-only
```

Single position group:

```bash
.venv/bin/python pipeline/recruiting/build_similarity_scores.py --season 2025 --position-group CB
```

Outputs to `pipeline/outputs/reports/recruiting/2026/`:

- `position_ideal_profiles.csv` — mean feature profile per position group
- `recruit_similarity_scores.csv` — recruits ranked by fit score
- `recruit_feature_gaps.csv` — per-recruit feature delta vs ideal
- `nearest_cofc_comps.csv` — top-5 CofC comps per recruit
- `shortlist_<position_group>.md` — coach-facing shortlist per position group

## Why This Counts as ML

The recruiting lane uses unsupervised similarity methods:

- position-group normalization
- weighted cosine similarity
- nearest-neighbor player comps
- ideal-profile distance
- later: clustering or dimensionality reduction for archetypes

It should produce coach-facing rankings and explanations, not black-box player
grades.

## Next Data Ask

When player exports are available, request one row per player-season or
player-competition sample using:

```text
pipeline/config/recruiting_player_profile_schema.csv
```

Start with one target position group if full export coverage is not available.
