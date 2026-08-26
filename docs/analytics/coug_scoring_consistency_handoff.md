# COUG Scoring Consistency Handoff

Date: 2026-08-26

## Current Question

The staff portal currently shows a much smaller Match Story score than the COUG Table for the same match.

Example from the staff portal:

- Match Story: `EVENTS 196`, `PLAYERS 16`, `COUG 13.80`
- COUG Table top bar: `ASET 43.5`, `PEAK 15.8`, `SP 0.0`
- COUG Table total implied by those buckets: `59.3`

That gap is why the wording and calculation path need to be clarified and then made consistent.

## What The Match Story Score Is

The Match Story score is currently a timeline/evidence score.

It is calculated from raw `athlete_event` rows for the selected match. For each event row, the backend looks up the event's COUG metric weight and adds:

```text
raw_value * metric_weight
```

Only mapped categories that land in the Match Story buckets are included:

- `ASET_DEF` -> ASET
- `PEAK_OFF` -> PEAK
- `SET_PIECE` -> set piece

The Match Story still lists unweighted evidence rows, but those rows do not add to the displayed score.

Important: this is not currently the same thing as the published COUG Table total.

## What The COUG Table Score Is

The COUG Table reads from `coug_score`, either directly from Supabase or from the dashboard read model snapshot.

The table totals are the sum of player-level score rows:

```text
team ASET = sum(player.aset_score)
team PEAK = sum(player.peak_score)
team SP   = sum(player.set_piece_score)
```

Before the local fix, those rows could come from more than one scoring era/source unless the backend filtered them.

## Why The COUG Table Can Look Inflated

There is still a legacy score loading path that inserts rows into `coug_score` from `*_coug_scores.csv`.

That legacy path uses broad precomputed CSV/PDF-style totals and stores:

```text
data_source_path = "csv"
score_type = "match"
```

Those legacy totals are broader than the event-derived Match Story evidence. They can include formulas such as:

- Defensive actions like interceptions, clearances, sliding tackles, and defensive duels
- Attacking actions like goals, assists, shots on target, key passes, and dribbles
- Player-level totals that were already calculated before the newer event-derived scoring model

The newer event-derived publisher writes official rows with:

```text
data_source_path = "xml"
score_type = "match"
scoring_version_id = current scoring version
```

So the likely cause of the `59.3` vs `13.8` gap is that the COUG Table is still able to show legacy/imported `coug_score` rows while Match Story is showing raw event evidence with current weights.

## Coach-Friendly Explanation

The Match Story is showing the weighted event evidence we can trace directly back to match events. It is useful for explaining what happened and when.

The COUG Table is the official player/team score table. Right now, we need to make sure it is only reading from the same current event-derived scoring pipeline and not older legacy CSV score imports.

Before the local fix, the Match Story and COUG Table could disagree because they were not guaranteed to be using the same source of scoring truth.

## Decision

We should stop calculating or displaying official staff-portal COUG scores from legacy CSV/PDF score imports.

Official COUG Table scores should come only from the event-derived scoring publisher:

```text
pipeline/analytics/publish_event_derived_coug_scores.py
```

Legacy score files can remain available for reconciliation, QA, and historical comparison, but they should not feed the staff-facing COUG Table.

## Local Implementation Started

The current local working tree has started this fix.

Implemented locally:

- `db.py` now filters staff-facing COUG score reads to official event-derived rows only:
  - `score_type = "match"`
  - `data_source_path = "xml"`
  - `scoring_version.version = "trial_1"` by default
- `pipeline/analytics/build_dashboard_read_model.py` now passes the selected weight/scoring version into leaderboard, match-score, and player-history reads.
- `backend/read_models.py` now allows API callers to require snapshot metadata before trusting cached read-model values.
- `backend/main.py` now requires score snapshots to declare the official XML source and active weight version before using them for COUG Table views.
- `pipeline/ingestion/load_season_scores.py` now skips legacy `*_coug_scores.csv` score inserts by default.
- Legacy CSV score loading now requires the explicit `--load-legacy-scores` flag.
- If legacy CSV score loading is explicitly enabled, the loader also writes `scoring_version_id` so it remains schema-compatible.

Remaining operational step:

- Regenerate dashboard read-model JSON after official event-derived scores are published, because existing snapshot files may still contain older legacy totals.
- Old snapshots without the new `official_score_source` metadata will be ignored for score views until regenerated.

## Implementation Pattern

Backend score reads should keep staff-facing COUG Table endpoints limited to official event-derived rows:

```text
score_type = "match"
data_source_path = "xml"
scoring_version = current weight version, probably "trial_1"
```

Primary files touched:

- `db.py`
- `backend/main.py`
- `backend/read_models.py`
- `pipeline/analytics/build_dashboard_read_model.py`
- `pipeline/ingestion/load_season_scores.py`

Suggested ingestion change:

- Keep loading sessions, matches, athletes, and minutes/stints as needed.
- Do not load legacy COUG score rows unless an explicit emergency/backfill flag is passed.
- If legacy CSV scores are skipped, log that they were skipped intentionally.

## Existing Local Work

The repo was updated with the latest remote work on branch:

```text
2026-roster-event-pipeline
```

A backup branch was created before pulling:

```text
backup/pre-pull-2026-08-26
```

The pull completed, and a README conflict from the stash was resolved by keeping both useful sections.

Current local change already made in Match Story wording:

- Header stat label changed from `COUG` to `TIMELINE PTS`
- Subtitle now says this is mapped event rows with COUG weights applied, not the full published COUG Table total
- Event detail label changed from `Contribution` to `Timeline contribution`
- Unweighted rows now say `Unweighted event`

Frontend build passed after the wording and score-source changes.

## Important Branch Naming Note

Do not use `codex` in the feature branch name.

Use something like:

```text
feature/event-derived-coug-scores
```

or:

```text
fix/official-coug-score-source
```

## Next Step On The Other Computer

1. Open `/Users/anissawilliams/PycharmProjects/cofc_soccer_analytics_2026`.
2. Check status with `git status --short --branch`.
3. Confirm whether the COUG Table should hide rows when no event-derived `xml` score exists yet, or show a clear "not published yet" empty state.
4. Patch backend `coug_score` reads to filter out legacy `csv` scores.
5. Patch `load_season_scores.py` so legacy scores are not loaded by default.
6. Rebuild the dashboard read model after scores are republished from the event-derived pipeline.
7. Run frontend build and Python compile/tests before shipping.
