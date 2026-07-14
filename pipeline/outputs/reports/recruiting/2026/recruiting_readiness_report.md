# Recruiting Similarity Readiness Report

Program: College of Charleston Men's Soccer
Active season: `2026`

## Status

- Status: `BLOCKED`
- Blocking errors: `1`
- Warnings: `0`

## Config

- Config: `configs/organizations/cofc_recruiting.json`
- Schema: `pipeline/config/recruiting_player_profile_schema.csv`
- Similarity method: `weighted_cosine_similarity`
- Normalization: `position_group_z_score`
- Position groups: `['GK', 'CB', 'FB_WB', 'DM_CM', 'AM_W', 'ST']`

## Profile Inputs

| profile_type | path | exists | rows | eligible_rows | position_group_counts |
| --- | --- | --- | --- | --- | --- |
| internal CofC profiles | `pipeline/data/recruiting/internal_player_profiles.csv` | True | 28 | 27 | `{'AM_W': 1, 'CB': 7, 'DM_CM': 9, 'FB_WB': 2, 'GK': 2, 'ST': 6}` |
| recruit profiles | `pipeline/data/recruiting/recruit_player_profiles.csv` | False | 0 | 0 | `{}` |

## Blocking Errors

- Missing recruit profiles file: pipeline/data/recruiting/recruit_player_profiles.csv

## Warnings

_None._

## Interpretation

- `BLOCKED` is expected until internal and recruit profile CSVs exist.
- This lane is designed for unsupervised similarity, comps, and shortlist generation.
- COUG-derived features should be added only after 2026 scoring provenance is stable.
