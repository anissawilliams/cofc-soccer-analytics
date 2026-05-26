# Weekly Workflow SOP
**Purpose:**  
This document outlines the repeatable process for running the CofC Soccer analytics system after each match. It ensures consistency, data quality, and reproducibility across seasons and analysts.

---

## 1. Overview
This workflow covers the full cycle from data ingestion → processing → validation → scoring → reporting.  
It applies after every match where data is available (conference, non-conference, scrimmage if tagged).

---

## 2. Required Inputs
List all files and sources needed to run the workflow:

- Wyscout event export (JSON or CSV)
- Wyscout match metadata (lineups, subs, formations)
- Spideo manual tags (CSV)
- Any additional manual tagging sheets
- Previous week’s Cougs Table (for continuity checks)

---

## 3. Data Ingestion
**Steps:**
1. Download Wyscout event data and save to:  
   `/analytics/data/raw/wyscout/YYYY_MM_DD_opponent/`
2. Download Spideo tags and save to:  
   `/analytics/data/raw/spideo/YYYY_MM_DD_opponent/`
3. Confirm file naming conventions match the SOP.

**Checks:**
- Ensure all expected files are present.
- Confirm match ID consistency across sources.

---

## 4. Pre‑Processing
**Steps:**
1. Run the preprocessing script to clean and standardize event data.
2. Normalize timestamps across Wyscout and Spideo.
3. Merge manual tags with event stream.

**Checks:**
- No missing periods or halves.
- No duplicated events.
- All manual tags successfully merged.

---

## 5. Metric Computation
**Steps:**
1. Apply Cougs Table metric definitions.
2. Compute:
   - On‑ball metrics  
   - Off‑ball metrics  
   - Pressing metrics  
   - Set‑piece metrics  
   - Transition metrics  
3. Apply weights from the `weights.yaml` file.

**Checks:**
- All players with minutes > 0 have metrics.
- No negative minutes or invalid substitutions.
- Weighting logic applied correctly.

---

## 6. Data Validation
**Steps:**
1. Compare manual tags vs. Wyscout events for alignment.
2. Spot‑check:
   - Counter‑press events  
   - First headers  
   - Set‑piece phases  
   - Punish actions  
3. Review outliers (extremely high/low values).

**Checks:**
- No missing tags for key moments.
- No impossible sequences (e.g., press without regain).
- Confirm lineup and minutes played.

---

## 7. Generate Outputs
**Steps:**
1. Produce updated Cougs Table.
2. Export player‑level summary.
3. Export team‑level summary.
4. Update dashboard inputs (if applicable).

**Checks:**
- All players appear in the table.
- Formatting matches coach‑facing expectations.

---

## 8. Deliverables to Coaches
**Steps:**
1. Export final Cougs Table (PDF, PNG, or spreadsheet).
2. Send via preferred communication channel.
3. Include brief notes on:
   - standout performances  
   - tactical patterns  
   - anomalies or context  

---

## 9. Archive & Version Control
**Steps:**
1. Commit all new data and outputs to GitHub.
2. Push to `main` with a descriptive commit message.
3. Archive raw data in season folder.

---

## 10. Troubleshooting
Common issues and how to resolve them:
- Missing Spideo tags  
- Wyscout export mismatch  
- Timestamp drift  
- Player name inconsistencies  
- Script errors  

(Add details as they emerge.)

---

## 11. Change Log
Document updates to this SOP over time.

- **v0.1** — Initial scaffold created.
