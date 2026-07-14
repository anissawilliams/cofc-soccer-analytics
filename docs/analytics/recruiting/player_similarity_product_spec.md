# Player Similarity / Recruiting Fit Product Spec

Last updated: 2026-07-14

## Purpose

Build a portable recruiting tool that compares prospective players to CofC's
current and ideal player profiles by position group. This is the practicum's
third modeling lane and should stay separate from:

- COUG Table scoring, which is coach-defined player evaluation
- Match scouting, which is opponent/team preparation

The recruiting lane can use COUG outputs once they are stable, but it should
also work from Wyscout-style player profile exports.

## Coaching Questions

The first version should help answer:

- Which recruits look most similar to current CofC players in the same position group?
- Which recruits fit a target role or archetype?
- What are each recruit's biggest strengths and gaps relative to CofC's ideal profile?
- Which current CofC players are the closest comps?
- Is the fit based on enough minutes to trust?

## Minimum Viable Product

1. Load current CofC player profiles and prospective recruit profiles.
2. Normalize positions into these groups:
   - `GK`
   - `CB`
   - `FB_WB`
   - `DM_CM`
   - `AM_W`
   - `ST`
3. Build an ideal profile per position group.
4. Score each recruit against the matching ideal profile.
5. Return:
   - ranked shortlist by position group
   - nearest CofC comps
   - feature gaps versus ideal profile
   - caveats for minutes, missing data, and source reliability

## Modeling Approach

Recommended baseline:

- Filter to players above a minutes threshold.
- Convert raw stats to per-90 or percentage features before modeling.
- Standardize features within position group.
- Compute weighted cosine similarity to the ideal position profile.
- Compute nearest-neighbor comps against current CofC players.
- Use feature-gap tables to explain why a player ranks high or low.

This is an unsupervised/similarity model, not a prediction model.

## Config

Organization-specific recruiting config lives at:

```text
configs/organizations/cofc_recruiting.json
```

Expected player-profile schema lives at:

```text
pipeline/config/recruiting_player_profile_schema.csv
```

The config defines:

- minutes thresholds
- position groups and aliases
- feature groups
- position-specific feature weights
- similarity method

## Input Data

Required profile fields:

- `player_id`
- `player_name`
- `source_system`
- `season`
- `team`
- `primary_position`
- `position_group`
- `minutes`

Important optional fields:

- attacking per-90s
- passing/progression per-90s
- defensive per-90s
- aerial/set-piece metrics
- COUG per-90 metrics once stable
- age, height, dominant foot, competition, country

## Output Artifacts

Planned output directory:

```text
pipeline/outputs/reports/recruiting/<season>/
```

Planned outputs:

- `recruiting_readiness_report.md`
- `position_ideal_profiles.csv`
- `recruit_similarity_scores.csv`
- `recruit_feature_gaps.csv`
- `nearest_cofc_comps.csv`
- `shortlist_<position_group>.md`

Only Markdown summaries should be considered candidates for Git tracking. Raw
recruit exports should stay out of Git.

## Known Limitations

- Wyscout access is currently unavailable.
- Recruit data may come from different leagues and competitive levels.
- Similarity is not quality by itself. A player can be similar to CofC's current
  profile without being better than current options.
- COUG features should not be used until 2026 scoring provenance is reliable.
- Coach role definitions should eventually tune the feature weights.

## Build Order

1. Add config and schema.
2. Add readiness command that checks whether internal/recruit profiles exist.
3. Add internal CofC profile export from Supabase.
4. Add ideal-profile builder.
5. Add similarity scoring.
6. Add coach-facing shortlist report.
7. Add optional PCA/cluster visualization after the tabular workflow is stable.

The internal profile export is:

```bash
.venv/bin/python pipeline/recruiting/export_internal_profiles.py --season 2025
```

It currently populates identity, position group, minutes/matches, and COUG
per-90 fields from Supabase. Wyscout-style technical profile fields remain
blank until a player export is available.

## First Data Ask

When Wyscout or another data source becomes available, request a player export
with one row per player-season or player-competition sample using the schema in:

```text
pipeline/config/recruiting_player_profile_schema.csv
```

If full exports are not available, start with one target position group and a
small sample of known recruits to validate the workflow.
