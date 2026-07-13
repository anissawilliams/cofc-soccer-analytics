# CofC Soccer Analytics

College of Charleston men's soccer analytics repo for COUG Table scoring,
Wyscout ingestion, scouting reports, simulation/modeling, and coaching
dashboards.

## What This Repo Does

- Ingests and inventories Wyscout source files
- Reconciles COUG Table scoring against database, legacy CSVs, and PDF reports
- Builds 2026 scouting schedule QA and opponent report shells
- Trains a baseline 2025 match outcome model
- Provides dashboard/application code for coach-facing views

## Fresh Computer Setup

```bash
git clone <repo-url>
cd cofc_soccer_analytics_2026

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp env.example .env
```

Then fill in `.env` if you need Supabase-backed commands:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`
- `STREAMLIT_PASSWORD` if running Streamlit

Most local file paths are resolved from the repo root. Optional path overrides
are documented in `env.example`.

## Key Commands

Source inventory:

```bash
.venv/bin/python pipeline/ingestion/inventory_sources.py --season 2025
.venv/bin/python pipeline/ingestion/inventory_sources.py --season 2025 --csv
```

2025 match model:

```bash
.venv/bin/python pipeline/scouting/build_match_model.py --org cofc --season 2025
```

2026 schedule QA:

```bash
.venv/bin/python pipeline/scouting/build_schedule_report.py --org cofc --season 2026
```

2026 opponent report shells:

```bash
.venv/bin/python pipeline/scouting/build_opponent_shells.py --org cofc --season 2026
```

COUG score reconciliation:

```bash
.venv/bin/python pipeline/analytics/reconcile_coug_scores.py --season 2025
```

## Important Docs

- [Current state inventory](docs/analytics/current_state_inventory.md)
- [2025 source inventory](docs/analytics/source_inventory_2025.md)
- [Coach questions](docs/analytics/coach_questions.md)
- [PEAK normalization](docs/analytics/peak_normalization.md)
- [Repo hygiene](docs/analytics/repo_hygiene.md)
- [Scouting README](docs/analytics/scouting/README.md)
- [Opposition report product spec](docs/analytics/scouting/opposition_report_product_spec.md)
- [Score reconciliation SOP](docs/analytics/sop/score_reconciliation_sop.md)

## Data Notes

This repo should track code, configs, docs, schedules, manifests, and small
mapping tables. Raw vendor exports and generated outputs should normally live
outside Git, either locally or in a shared Google Drive/data store, and be
connected through the `COFC_*` path overrides in `.env`.

For durable raw file storage, prefer Supabase Storage. The ingestion parser
keeps a local-file interface and can download missing Wyscout XML files from
Storage into `COFC_SOURCE_CACHE_DIR` when `COFC_ENABLE_SUPABASE_STORAGE=true`.

Current source truth is summarized in:

```text
docs/analytics/source_inventory_2025.md
```

As of 2026-07-13:

- 16 real 2025 matches are included in the default inventory.
- All 16 have Wyscout `sportscode.xml` and `effective_time.xml`.
- 15 of 16 have Wyscout PDF player reports in the expected folder.
- 16 of 16 have parsed player CSV outputs.
- Only UNCW currently has raw `player_events.xml` and `team_events.xml` locally.
- Spiideo is treated as a future source, not a current blocker.

## Repo Layout

```text
configs/                         Organization and season configs
docs/analytics/                  SOPs, handoff docs, scouting specs
pipeline/analytics/              COUG scoring, reconciliation, legacy analytics
pipeline/core/                   Shared config/path helpers
pipeline/data/                   Schedules/manifests plus local data mount docs
pipeline/ingestion/              Source inventory, parsing, loading
pipeline/scouting/               Schedule QA, match model, opponent shells
pipeline/outputs/reports/        Generated outputs; selected Markdown may be tracked
frontend/                        React app
backend/                         FastAPI/backend experiments
streamlit/                       Streamlit app, if present locally
schema/                          Database guardrails/migrations
```

## Development Hygiene

Before committing:

```bash
git status --short
.venv/bin/python -m py_compile pipeline/ingestion/inventory_sources.py
.venv/bin/python -m py_compile pipeline/core/config_loader.py pipeline/scouting/features.py pipeline/scouting/modeling.py pipeline/scouting/simulation.py pipeline/scouting/build_match_model.py
```

Do not commit:

- `.env`
- downloaded secrets
- accidental scratch files
- huge ad hoc search outputs
- new raw data unless it is intentionally approved as a tiny fixture
- generated CSV/PNG/XLSX/PDF outputs

## Current Strategic Direction

COUG Table scoring remains a coach-defined rules framework, not ML. The ML lane
belongs in match outcome modeling, simulation, scouting, and eventually
recruiting similarity.

The immediate build path is:

1. Keep source inventory and pathing clean.
2. Keep PEAK candidate/review-only until coach mapping rules are final.
3. Generate and progressively populate 2026 scouting report shells.
4. Add 2026 match results/files as they arrive.
5. Expand modeling with additional historical data if it becomes available.
