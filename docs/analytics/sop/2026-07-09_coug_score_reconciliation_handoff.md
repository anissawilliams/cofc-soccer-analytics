# COUGS Score Reconciliation Handoff

Date: 2026-07-09

## Goal

Make the College of Charleston men's soccer COUGS Table pipeline more reliable, auditable, and easier to hand off. The main concern was that coach-facing PEAK/ASET values did not line up with the pipeline, and prior iterations had mixed PDF-derived scores, Wyscout event scores, and incomplete `athlete_event` loading.

## Current Source Truth

The working hierarchy is:

1. Coach-confirmed scoring rules and weights.
2. `athlete_event` rows as the durable evidence layer.
3. Wyscout/Sportscode parsed event evidence.
4. Coach spreadsheet / legacy COUGS files as calibration and sanity-check targets.
5. Wyscout PDFs as fallback/validation summaries, not the main event-level source.

Raw XML is preferred archive evidence, but parsed `_players.csv` files are acceptable working evidence when raw XML is not easily accessible.

## Repo And Paths

The real project is:

```text
/Users/anissawilliams/PycharmProjects/cofc_soccer_analytics_2026
```

The empty/less relevant PyCharm folder is:

```text
/Users/anissawilliams/PycharmProjects/cofc_soccer_fastapi
```

Important source/output roots:

```text
pipeline/data/matches/2025/
pipeline/outputs/2025/
pipeline/ingestion/outputs/2025/
pipeline/data/outputs/2025/
pipeline/outputs/reports/score_reconciliation/2025/
```

## Code Added Or Updated

### Source path reliability

Added:

```text
pipeline/ingestion/source_paths.py
pipeline/ingestion/inventory_sources.py
```

These centralize path handling and provide an inventory command for checking whether each match has Sportscode XML, player events XML, effective-time XML, PDFs, Spiideo, and parsed outputs.

### Wyscout parsing/loading

Updated:

```text
pipeline/ingestion/parse_wyscout.py
pipeline/ingestion/load_match.py
pipeline/ingestion/batch_parse.py
```

Important changes:

- Removed brittle hardcoded roster path behavior.
- Added/kept duplicate protection for `athlete_event`.
- Preserved `athlete_event` as the evidence layer.
- Continued loading parsed Wyscout `_players.csv` event labels into `athlete_event`.

### Reconciliation

Added/updated:

```text
pipeline/analytics/reconcile_coug_scores.py
pipeline/config/wyscout_coug_metric_map.csv
docs/analytics/sop/score_reconciliation_sop.md
```

The reconciliation script now writes:

```text
*_event_score_trace.csv
*_pipeline_score_summary.csv
*_score_explainer.csv
*_score_reconciliation.csv
```

It also now supports:

- `athlete_alias` resolution.
- Raw player name vs resolved player name in reconciliation outputs.
- Candidate/review-only PEAK columns.

## Alias Work

Created/used `athlete_alias` in Supabase. The chosen canonical athlete record for E. Goetzke / E. Emanuele is:

```text
E. Goetzke
```

Aliases can point alternate/former names and nicknames to the single canonical athlete ID. Do not create a duplicate athlete row for Emanuele.

The reconciliation output now includes columns like:

```text
legacy_player_raw
legacy_player_resolved
legacy_player_match_method
pdf_player_raw
pdf_player_resolved
pdf_player_match_method
```

This lets us tell whether a comparison used direct athlete display name, full name, alias, or unmatched fallback.

## W&M Reconciliation Files

Regenerated and reviewed:

```text
pipeline/outputs/reports/score_reconciliation/2025/2025-09-27_william_mary_score_reconciliation.csv
pipeline/outputs/reports/score_reconciliation/2025/2025-09-27_william_mary_score_explainer.csv
pipeline/outputs/reports/score_reconciliation/2025/2025-10-25_william_mary_score_reconciliation.csv
pipeline/outputs/reports/score_reconciliation/2025/2025-10-25_william_mary_score_explainer.csv
```

W&M is a better calibration case than UNCW because the coach spreadsheet has W&M rows filled in.

## Key Finding: PEAK Source

The large legacy PEAK values are mostly not from Wyscout PDF tables. They come from legacy Wyscout/event scoring CSVs:

```text
pipeline/data/outputs/2025/<slug>/<slug>_coug_scores.csv
```

Those files have breakdowns like:

```text
WY:Shots
WY:Goal
WY:Free kick goal
WY:Assists
```

So the PEAK discrepancy is mostly a rule/mapping/filtering issue, not a PDF extraction issue.

## Key Finding: Parsed Player Events Are Enough For Now

For W&M, the parsed player event CSVs exist:

```text
pipeline/ingestion/outputs/2025/2025-09-27_william_mary/2025-09-27_william_mary_players.csv
pipeline/ingestion/outputs/2025/2025-10-25_william_mary/2025-10-25_william_mary_players.csv
```

They match the canonical parsed copies in:

```text
pipeline/outputs/2025/<slug>/<slug>_players.csv
```

Those CSVs include PEAK-relevant labels:

```text
Smart passes
Key passes
Opportunity
Shots
Goal
Assists
Cross
Free kick goal
```

So raw XML access is not blocking the next work.

## Important Current Limitation

`Smart passes`, `Key passes`, and `Opportunity` exist in parsed `_players.csv`, but not all of them are making it into `athlete_event`.

Likely reason:

```text
load_match.py
```

treats several PEAK labels as `PLUS_ONLY`, and many parsed rows have:

```text
outcome = Unknown
```

Therefore those rows are filtered out before insertion.

This is now the main technical issue to investigate.

## Candidate PEAK

Added review-only candidate PEAK fields to the reconciliation layer. This does not change `coug_score`, Supabase official values, or the frontend.

New reconciliation columns include:

```text
candidate_peak_score
candidate_total_score
candidate_peak_model
delta_candidate_peak_score_vs_legacy_peak
delta_candidate_total_score_vs_legacy_total
```

Current candidate model:

```text
candidate_peak_model = candidate_wyscout_peak_v1
```

Current candidate rules after reviewing `CougsTable_Coach_Questions.pdf`:

```text
Goal / Goal (scorer) = 3.0
Assist / Assists = 2.0
Opportunity on shot rows = 0.2 Punish proxy
Advance = 0.5 for every 10 successful Advance actions
```

This is intentionally conservative and review-only.

## Coach Questions PDF Clarifications

Source:

```text
/Users/anissawilliams/Desktop/CofCSoccer/CougsTable_Coach_Questions.pdf
```

Important decisions from the PDF:

- Q1: Advance should score `0.5` for every `10` successful Advance actions, not `0.5` per action.
- Q2: No full P-E-A-K sequence bonus. Individual metric scores are enough.
- Q3: Punish and Advance should not double-count. If an action immediately follows a regain and progresses the ball, it should count as Punish, not both Punish and Advance.
- Q4: Conceding from a set piece should be `-3` total.
- Q5: No GPS for keepers currently, so GK Catapult load scoring is not ready.
- Q6: Catapult may matter later, but do not stretch the current COUGS score implementation too thin.
- Q7: Wyscout and Spiideo can generally be expected to complement each other except preseason.

Implementation implication:

```text
Do not score Smart pass / Smart passes / Key passes as per-event PEAK.
Track them as candidate Advance actions and apply threshold scoring: floor(action_count / 10) * 0.5.
```

## Frontend Note

Coaches see values in:

```text
frontend/src/CougTable.jsx
```

That component displays fields like:

```text
player.aset_score
player.peak_score
player.set_piece_score
player.total_score
```

We did not change the frontend. The candidate PEAK should stay in reports/API review mode until scoring rules are confirmed.

## Commands To Rerun Reconciliation

From:

```bash
cd /Users/anissawilliams/PycharmProjects/cofc_soccer_analytics_2026
```

Run W&M:

```bash
.venv/bin/python pipeline/analytics/reconcile_coug_scores.py --season 2025 --slug 2025-09-27_william_mary
.venv/bin/python pipeline/analytics/reconcile_coug_scores.py --season 2025 --slug 2025-10-25_william_mary
```

Run full season:

```bash
.venv/bin/python pipeline/analytics/reconcile_coug_scores.py --season 2025 --all
```

Inventory sources:

```bash
python pipeline/ingestion/inventory_sources.py --season 2025
python pipeline/ingestion/inventory_sources.py --season 2025 --slug 2025-10-25_william_mary
```

## Next Best Steps

1. Confirm whether candidate PEAK should include `Smart passes`, `Key passes`, and `Opportunity` when `outcome = Unknown`.
2. Decide whether those labels should be:
   - loaded into `athlete_event` as official evidence, or
   - kept as candidate/review-only evidence first.
3. If candidate-only, update `reconcile_coug_scores.py` to read parsed `_players.csv` directly for candidate PEAK so it captures skipped labels without changing official DB evidence.
4. If official, update `load_match.py` filtering rules for PEAK labels and reload affected matches.
5. Keep PDFs as validation summaries, especially for `Shots / on target`, but avoid making them the primary PEAK source.

## Main Takeaway

The pipeline is no longer a vague reliability problem. The current concrete issue is:

```text
PEAK-relevant labels exist in parsed player-event files, but filtering/mapping prevents some from becoming score evidence.
```

The safest path is to continue using reconciliation reports and `candidate_peak_score` until coaches confirm the exact PEAK rules.
