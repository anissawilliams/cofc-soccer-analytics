# Notebooks

## 2026_match_intake.ipynb — current post-match intake

This is the supported undergraduate-facing Google Colab workflow. It mounts the
shared Drive, accepts original Wyscout filenames, runs the tested intake parser,
shows analytics and scoring readiness separately, and creates a review bundle.
It cannot publish to Supabase.

1. Open the notebook in Colab.
2. Fill in the setup cell and leave `CREATE_REVIEW_BUNDLE = False`.
3. Run through the inspection and review all warnings.
4. Set `CREATE_REVIEW_BUNDLE = True` and create the bundle.
5. Send the validation report to the staff reviewer.

See `docs/analytics/sop/workflow_sop.md` for the complete handoff.
The student download and file-extension checklist is in
[`../data/MATCH_INTAKE_README.md`](../data/MATCH_INTAKE_README.md).

## Legacy and exploratory notebooks

The notebooks below document earlier or exploratory workflows. Do not use them
for 2026 production intake unless a staff maintainer explicitly asks you to.

Run these in order. Each notebook is self-contained and saves its outputs automatically.

---

## 01_match_prediction.ipynb

**What it does:**
- Loads the Wyscout team Excel export
- Builds match-level features (xG, possession, pass accuracy, etc.)
- Trains a logistic regression model with Leave-One-Out cross-validation
- Runs Monte Carlo simulation for match outcome probabilities
- Generates an automated pre-match scouting report

**What you need:**
- `data/raw/cofc_matches_YYYY.xlsx` (Wyscout team export)

**How to run:**
1. Open Jupyter: `jupyter notebook`
2. Open `01_match_prediction.ipynb`
3. Run all cells top to bottom (`Cell → Run All`)
4. Outputs save to `outputs/reports/`

**Update frequency:** After every match (re-run with updated Excel file)

---

## 02_coug_table_batching.ipynb

**What it does:**
- Parses all Players in Match PDFs in `data/raw/player_reports/`
- Scores each player on ASET (defensive) and PEAK (offensive) metrics
- Produces a per-match CSV and a cumulative season leaderboard

**What you need:**
- All Players in Match PDFs in `data/raw/player_reports/`
- `pdftotext` installed (`pdftotext --version` to verify)

**How to run:**
1. Make sure all PDFs are downloaded and named correctly (see `data/raw/README.md`)
2. Open Jupyter: `jupyter notebook`
3. Open `02_coug_table_batching.ipynb`
4. Run all cells top to bottom
5. Outputs save to `outputs/coug_table/`

**Update frequency:** After every match (add the new PDF, re-run)

---

## Troubleshooting

**"No module named config"**
The notebook must be run from inside `pipeline/notebooks/`. 
Open Jupyter from that directory or the project root — not from your Desktop.

**"No player data extracted"**
- Check the PDF is named correctly
- Check `pdftotext --version` works in your terminal
- Make sure you downloaded "Players in Match Report" not "Team Report"

**"pdftotext not found"**
```bash
brew install poppler   # Mac
```
