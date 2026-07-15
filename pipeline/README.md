# CofC Soccer Analytics — Pipeline

**College of Charleston Men's Soccer | Head of Sports Performance & Data Intelligence**

This directory contains the full analytics pipeline: data ingestion, COUG Table
scoring, match outcome modeling, scouting, and recruiting similarity.

---

## Three Lanes

The pipeline has three separate, complementary lanes. Keep them distinct.

| Lane | Purpose | ML? |
|------|---------|-----|
| **COUG Table** | Coach-defined player evaluation (ASET / PEAK / Set Piece) | No — rules-based |
| **Scouting & Modeling** | Match outcome prediction, simulation, opponent prep | Yes |
| **Recruiting Similarity** | Compare recruits to CofC ideal profiles by position | Yes (unsupervised) |

---

## Directory Layout

```text
pipeline/
├── analytics/          COUG scoring, reconciliation, validation
├── core/               Shared config/path helpers
├── config/             Wyscout label maps, profile schemas, weight tables
├── data/               Schedules, manifests, recruiting profiles (local/gitignored)
├── ingestion/          Source inventory, parsing, Supabase loading
├── notebooks/          Exploratory notebooks (gitignored outputs)
├── outputs/            Generated reports — selected Markdown tracked in Git
├── recruiting/         Recruiting similarity pipeline
└── scouting/           Schedule QA, match model, opponent report shells
```

---

## Lane 1 — COUG Table

### Preflight check — run before publishing to coaches
```bash
.venv/bin/python pipeline/analytics/preflight_check.py --season 2025
```
Exits non-zero if any reconciliation issue is unresolved or unsigned. Write
a preflight report:
```bash
.venv/bin/python pipeline/analytics/preflight_check.py --season 2025 \
  --output pipeline/outputs/reports/score_reconciliation/2025/preflight_report.md
```
Add signoffs for known issues in `pipeline/config/reconciliation_signoffs.csv`
before rerunning. See the disposition reference at the bottom of any preflight
report for guidance.

### Validate scoring config
```bash
.venv/bin/python pipeline/analytics/validate_scoring_config.py
.venv/bin/python pipeline/analytics/check_peak_scoring_fixture.py
```
Expected: `0 error(s), 0 warning(s)` and `all checks passed`.

### Ingest source files for a match
```bash
.venv/bin/python pipeline/ingestion/inventory_sources.py --season 2025
.venv/bin/python pipeline/ingestion/inventory_sources.py --season 2025 --csv
.venv/bin/python pipeline/ingestion/register_source_files.py --season 2025 --slug <match_slug>
.venv/bin/python pipeline/ingestion/batch_parse.py --season 2025 --slug <match_slug>
```

### Reconcile COUG scores
```bash
.venv/bin/python pipeline/analytics/reconcile_coug_scores.py --season 2025
```
Output: `pipeline/outputs/reports/score_reconciliation/2025/`

### Smoke test (run after any clone or setup change)
```bash
.venv/bin/python pipeline/ingestion/inventory_sources.py --season 2025 --slug 2025-09-27_william_mary
.venv/bin/python pipeline/ingestion/batch_parse.py --season 2025 --slug 2025-09-27_william_mary --dry-run
.venv/bin/python pipeline/ingestion/batch_parse.py --season 2025 --slug 2025-09-27_william_mary
```

### Key docs
- [PEAK normalization rules](../docs/analytics/peak_normalization.md)
- [Scoring & weights SOP](../docs/analytics/sop/scoring_and_weights_sop.md)
- [Score reconciliation SOP](../docs/analytics/sop/score_reconciliation_sop.md)
- [Data validation SOP](../docs/analytics/sop/data_validation_sop.md)
- [2025 reconciliation triage](../docs/analytics/reconciliation_triage_2025.md)

---

## Lane 2 — Scouting & Modeling

### 2026 schedule QA
```bash
.venv/bin/python pipeline/scouting/build_schedule_report.py --org cofc --season 2026
```
Output: `pipeline/outputs/reports/scouting/2026/schedule/`

### 2026 opponent report shells
```bash
.venv/bin/python pipeline/scouting/build_opponent_shells.py --org cofc --season 2026
```
Output: `pipeline/outputs/reports/scouting/2026/opponents/<slug>/`

### 2025 match outcome model
```bash
.venv/bin/python pipeline/scouting/build_match_model.py --org cofc --season 2025
```
Output: `pipeline/outputs/reports/scouting/2025/models/`

Current metrics: 16 matches · LOO accuracy 62.5% · log loss 1.295

### Model readiness check
```bash
.venv/bin/python pipeline/scouting/build_model_readiness_report.py --org cofc --season 2026
```

### Key docs
- [Scouting README](../docs/analytics/scouting/README.md)
- [Opposition report product spec](../docs/analytics/scouting/opposition_report_product_spec.md)
- [Model readiness report](outputs/reports/scouting/2026/model_readiness_report.md)

---

## Lane 3 — Recruiting Similarity

Player similarity is an unsupervised (cosine similarity) model. It is not a
quality predictor — it identifies statistical profile matches. Keep it separate
from COUG Table scoring until 2026 event provenance is fully stable.

### Step 1 — Export internal CofC profiles from Supabase
```bash
.venv/bin/python pipeline/recruiting/export_internal_profiles.py --season 2025
```
Output: `pipeline/data/recruiting/internal_player_profiles.csv` (gitignored)

### Step 2 — Check readiness
```bash
.venv/bin/python pipeline/recruiting/build_recruiting_readiness_report.py
```
Output: `pipeline/outputs/reports/recruiting/2026/recruiting_readiness_report.md`

Status will be `BLOCKED` until `recruit_player_profiles.csv` exists.
Status will be `READY` once both profile files are present and valid.

### Step 3 — Run similarity scoring

**With recruit profiles (normal mode):**
```bash
.venv/bin/python pipeline/recruiting/build_similarity_scores.py --season 2025
```

**Internal-only validation (no recruits needed — tests the engine):**
```bash
.venv/bin/python pipeline/recruiting/build_similarity_scores.py --season 2025 --internal-only
```

**Single position group:**
```bash
.venv/bin/python pipeline/recruiting/build_similarity_scores.py --season 2025 --position-group CB
```

Outputs to `pipeline/outputs/reports/recruiting/2026/`:

| File | Description |
|------|-------------|
| `position_ideal_profiles.csv` | Mean feature profile per position group |
| `recruit_similarity_scores.csv` | Recruits ranked by fit score |
| `recruit_feature_gaps.csv` | Per-recruit feature delta vs ideal |
| `nearest_cofc_comps.csv` | Top-5 CofC comps per recruit |
| `shortlist_<pg>.md` | Coach-facing shortlist per position group |

In internal-only mode outputs are prefixed `internal_` and the shortlists show
roster comps instead of recruit rankings.

### Recruit profile intake

When recruit data is available, populate:
```text
pipeline/data/recruiting/recruit_player_profiles.csv
```
using the schema at `pipeline/config/recruiting_player_profile_schema.csv`.

Required fields: `player_id`, `player_name`, `source_system`, `season`,
`team`, `primary_position`, `position_group`, `minutes`.

All other fields (per-90 stats, COUG metrics) are optional but improve
similarity quality. COUG features should be left blank until 2026 scoring
provenance is reliable.

Position group labels are normalized automatically. Wyscout position strings,
shorthand (CB, LW, CDM), and plain English (Center Back, Winger) are all
accepted.

### Key docs
- [Player similarity product spec](../docs/analytics/recruiting/player_similarity_product_spec.md)
- [Recruiting README](../docs/analytics/recruiting/README.md)
- [Readiness report](outputs/reports/recruiting/2026/recruiting_readiness_report.md)

---

## Config Files

| Path | Purpose |
|------|---------|
| `configs/organizations/cofc_recruiting.json` | Position groups, feature weights, similarity method |
| `pipeline/config/recruiting_player_profile_schema.csv` | Player profile column definitions |
| `pipeline/config/wyscout_peak_normalization.csv` | Wyscout label → COUG metric mapping |
| `configs/seasons/cofc_2026.json` | 2026 season config |
| `configs/organizations/cofc.json` | Org-level config |

---

## Development Notes

Raw vendor files, parsed CSVs, and generated outputs are gitignored. Only
code, configs, docs, schedules, manifests, and curated Markdown reports
belong in Git.

Before committing:
```bash
git status --short
```

See [repo hygiene doc](../docs/analytics/repo_hygiene.md) for the full policy.
