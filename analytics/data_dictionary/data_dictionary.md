# Data Dictionary
**Purpose:**  
Define all metrics, tags, and data fields used in the CofC Soccer analytics system.

---

## 1. Event‑Level Fields
| Field | Description | Source | Notes |
|-------|-------------|--------|-------|
| event_id | Unique event identifier | Wyscout |  |
| timestamp | Event timestamp (ms) | Wyscout | Normalized to match Spideo |
| team | Team performing the action | Wyscout |  |
| player | Player performing the action | Wyscout | Standardized naming |

(Add more once confirmed.)

---

## 2. Manual Tags
| Tag | Definition | Source | SOP Link |
|------|------------|--------|----------|
| counter_press | … | Spideo | tagging_counter_press_sop.md |
| first_header | … | Spideo | tagging_first_header_sop.md |
| set_piece_phase | … | Spideo | tagging_set_piece_phase_sop.md |
| punish_action | … | Spideo | tagging_punish_action_sop.md |

---

## 3. Derived Metrics
| Metric | Definition | Formula | Notes |
|--------|------------|---------|-------|
| CP Win % | … | … |  |
| 1st Header Win % | … | … |  |
| Punish Rate | … | … |  |

---

## 4. Cougs Table Metrics
| Metric | Description | Weight | Category |
|--------|-------------|--------|----------|
| … | … | … | … |

---

## 5. Change Log
- v0.1 — Created after coach confirmation.
