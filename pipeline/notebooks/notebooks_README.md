# Notebooks

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
