# CofC Soccer Analytics Pipeline
**College of Charleston Men's Soccer | Director of Data**

A reproducible machine learning pipeline for match prediction, tactical scouting, and player evaluation built on real match data from the 2025 season.

---

## Overview

This project ingests multi-source data from Wyscout, engineers football-specific features, and produces:
- **Match outcome predictions** using logistic regression (62.5% LOO accuracy)
- **Monte Carlo match simulations** using Poisson-distributed goal modeling
- **Automated pre-match scouting reports** for coaching staff

This is the data infrastructure layer for the COUG Table — a coach-defined player evaluation framework tracking ASET (defensive), PEAK (offensive), and Set Piece metrics.

---

## Project Structure

```
cofc_analytics/
│
├── data/
│   ├── raw/                        # Wyscout exports (not tracked in git)
│   └── processed/                  # Cleaned feature matrices
│
├── notebooks/
│   └── 01_match_prediction.ipynb   # End-to-end walkthrough
│
├── src/
│   ├── ingest.py                   # Data loading, cleaning, parsing
│   ├── features.py                 # Feature engineering
│   ├── model.py                    # Logistic regression + LOO evaluation
│   ├── simulate.py                 # Monte Carlo Poisson simulation
│   └── report.py                   # Automated scouting report generator
│
├── outputs/
│   └── reports/                    # Generated pre-match reports
│
├── requirements.txt
└── README.md
```

---

## Pipeline

```
Wyscout Export (.xlsx)
        ↓
    ingest.py          Load, clean, parse results from match strings
        ↓
  Feature Matrix       xG diff, pass accuracy diff, possession diff,
                       shots on target, recoveries, duels won
        ↓
    model.py           Logistic regression
                       Leave-One-Out cross validation
                       62.5% accuracy (vs 33% random baseline)
        ↓
   simulate.py         Poisson Monte Carlo (10,000 iterations)
                       Win / Draw / Loss probabilities
                       Scoreline distribution
        ↓
    report.py          Automated pre-match scouting report
                       Tactical insights + key matchup flags
```

---

## Key Results

| Metric | Value |
|--------|-------|
| Season record | 6W - 3D - 7L |
| Logistic regression accuracy (LOO) | 62.5% |
| Monte Carlo accuracy | 50.0% |
| Most predictive feature | CofC pass accuracy |
| Simulation iterations | 10,000 per match |

**Notable finding:** CofC's pass accuracy is the single most predictive feature for match outcomes — more predictive than xG differential. This suggests build-up quality matters more than chance creation volume for this team.

---

## Data Sources

| Source | Data Type | Usage |
|--------|-----------|-------|
| Wyscout | Match event stats | Primary — team & player metrics |
| Spiideo | Video tagging | Manual COUG Table events |
| Catapult | GPS / physical load | Player workload (in progress) |

---

## COUG Table Framework

The COUG Table is a coach-defined player evaluation system with three metric categories:

**ASET (Defensive)**
- Possession Regain
- Counter Press under 5 seconds
- Block in Box
- Clearance from Danger
- Clean Sheet / Concede Goal

**PEAK (Offensive)**
- Punish Action after Regain
- Establishing Possession
- Goals / Assists

**Set Piece**
- Win 1st Header (offensive & defensive)
- Goal scoring (phased weighting)
- Penalty / Free kick save or concede

---

## Usage

```bash
# Install dependencies
pip install -r requirements.txt

# Run ingestion and feature engineering
python src/ingest.py

# Train and evaluate prediction model
python src/model.py

# Run Monte Carlo simulation
python src/simulate.py

# Generate pre-match scouting report
python src/report.py
```

---

## Requirements

```
pandas
numpy
scikit-learn
openpyxl
jupyter
matplotlib
seaborn
```

---

## Roadmap

- [ ] Player similarity model for recruiting (Objective 3)
- [ ] COUG Table automated scoring from Wyscout events
- [ ] Catapult physical load integration
- [ ] Dashboard for coaching staff (Streamlit)
- [ ] Opponent scouting from Wyscout team profiles
- [ ] Bayesian model comparison vs Poisson baseline

---

## Author

**Anissa Williams**
Director of Data — College of Charleston Men's Soccer
M.S. Data Science Candidate, College of Charleston
Graduate Practicum — DATA 698

---

*Built on real match data. All Wyscout exports excluded from version control.*
