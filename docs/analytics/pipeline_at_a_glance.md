# CofC Soccer Analytics Pipeline At A Glance

Last updated: 2026-07-27

Purpose: give coaches, analysts, and future maintainers a plain-language map of
how the COUG Table, staff portal, reconciliation workflow, and upcoming Catapult
integration fit together.

## Operating Principle

The system should make every player score explainable.

For any PEAK, ASET, set-piece, positional, or load value, staff should be able
to answer:

- Which player received credit?
- Which event counted?
- Which source file produced the event?
- Which coach-defined metric did it map to?
- Which weight was applied?
- Which items still need coach or analyst review?

The staff-facing score is only useful if the evidence trail is visible.

## Current Flow

```text
Raw vendor files
  -> source inventory and file registration
  -> Wyscout / Spiideo / CSV parsers
  -> athlete_event evidence rows
  -> metric_definition + metric_weight
  -> coug_score player totals
  -> FastAPI endpoints
  -> Staff Portal trace view
```

## Main Tables

| Table | Role |
| --- | --- |
| `athlete` | Roster identity, position, position group, source IDs |
| `session` | Match, scrimmage, or training session metadata |
| `match` | Match-specific opponent, venue, result, goals |
| `athlete_session_stint` | Player minutes, starts, participation |
| `metric_category` | Score buckets such as ASET, PEAK, Set Piece, Load |
| `metric_definition` | Coach-facing event names and rule notes |
| `metric_weight` | Versioned scoring weights |
| `athlete_event` | Event-level scoring evidence |
| `athlete_load` | Catapult/GPS physical load evidence |
| `coug_score` | Player score totals for dashboards |

## COUG Table Lanes

The pipeline has three separate product lanes. Keep them distinct.

| Lane | Purpose | Modeling? |
| --- | --- | --- |
| COUG Table | Coach-defined player evaluation: ASET, PEAK, set piece, positional, load | Rules-based |
| Scouting and Modeling | Match prediction, simulation, opponent prep | Predictive |
| Recruiting Similarity | Compare recruits to CofC position profiles | Unsupervised similarity |

## Score Evidence Layer

`athlete_event` is the key evidence layer. Every event should carry:

| Field | Meaning |
| --- | --- |
| `athlete_id` | Player credited or penalized |
| `session_id` | Match/training context |
| `metric_id` | Coach-facing metric definition |
| `source_id` or source file ID | Source provenance |
| `raw_value` | Count or numeric value to score |
| `raw_value_context` | Raw label, outcome, location, subtype, tags |
| `event_time` | Video/event timestamp when available |
| `collection_method` | Auto, manual, semi-auto, derived |
| `manually_tagged` | Whether it came from staff tagging |
| `coach_confirmed` | Whether the metric or row is confirmed |

## PEAK Summary

PEAK means Punish, Establish, Advance, Kill.

Confirmed rules:

- Individual Wyscout events can support PEAK.
- No PEAK sequence bonus.
- No coach/video confirmation gate required for PEAK.
- Goal scorer = `3.0`.
- Assist = `2.0`.
- Punish Action after Regain = `0.2`.
- Advance = `0.5` per `10` successful Advance actions.
- Punish takes priority over Advance.
- Punish and Advance should not double-count the same event.
- The 3-5 pass threshold separates Punish from Advance.

Migration-critical rule: do not blindly sum every attacking Wyscout label. PEAK
requires normalization, priority rules, and the Advance threshold.

## ASET Summary

ASET means All in, Sprint, Engage, Trust.

Coach-facing ASET metric families:

- Possession Regain
- Successful Counter Press within five seconds
- Block in Box
- Clearance from Danger
- Concede Goal on field, negative

Wyscout proxy labels currently used or reviewed for ASET include:

- `Vol_Interception`
- `Tackles`
- `Clearances`
- `Anticipated`
- `Anticipation`
- `Pressing duel`
- `Loose ball duel`
- `Defensive duel`
- `1VS1`

Migration-critical rule: keep mapping status. Some Wyscout labels are strong
proxies; others are only review bridges for coach-defined concepts.

## Set Piece Summary

Set-piece events are event-derived and require careful normalization.

Core families:

- Win 1st Header, offensive
- Win 1st Header, defensive
- Set Piece Goal, first phase
- Set Piece Goal, second phase
- Penalty Save
- Freekick Save/Block
- Concede from Set Piece on field

Open question: confirm whether set-piece goal events also receive normal
Goal/Assist credit or only set-piece bonus credit.

## Catapult / Load Summary

Catapult should start as a supporting evidence lane, not an automatic ASET/PEAK
override.

Recommended first fields:

- `distance`
- `player_load`
- `high_metabolic_load_distance`
- `accel_decel_efforts`
- `player_load_per_minute`
- `accel_decel_per_minute`
- `hi_distance_pct`
- `max_velocity`
- `sprint_distance`
- `sprint_efforts`
- `max_acceleration`
- `max_deceleration`

Initial uses:

- Training and match load monitoring
- Availability/readiness context
- Validating the Sprint component of ASET counter press
- Goalkeeper load scoring after thresholds are coach-approved
- Scouting model fatigue and recent-load features

Conservative rule: show Catapult next to ASET first. Do not let it silently
change ASET totals until thresholds and score rules are signed off.

## Staff Portal Trace View

The staff portal should present two things separately:

1. Official stored totals from `coug_score`.
2. Event-derived evidence from `athlete_event`.

This matters because 2025 includes legacy/PDF-derived values and event-derived
values that do not always match. The UI should make the gap visible rather than
hide it.

The ideal player conversation view:

```text
Player
  -> score tiles
  -> event families included
  -> category totals
  -> event ledger
      -> date
      -> timestamp
      -> raw source/platform
      -> metric
      -> raw value
      -> weight
      -> calculated score
      -> review flag
```

## Reconciliation And Publication Gate

Before coach-facing publication:

```bash
.venv/bin/python pipeline/analytics/validate_scoring_config.py
.venv/bin/python pipeline/analytics/check_peak_scoring_fixture.py
.venv/bin/python pipeline/analytics/reconcile_coug_scores.py --season <season>
.venv/bin/python pipeline/analytics/preflight_check.py --season <season>
```

Expected publish logic:

- `validate_scoring_config.py` checks mapping/config shape.
- `check_peak_scoring_fixture.py` checks critical PEAK behavior.
- `reconcile_coug_scores.py` compares event-derived scores to legacy/PDF values.
- `preflight_check.py` blocks publication if unresolved triage rows remain.

## What Must Not Be Lost

- `athlete_event` as the durable evidence layer
- `metric_definition` and `metric_weight` as scoring source of truth
- Wyscout raw label normalization
- Spiideo/manual tag handling
- PEAK priority and Advance threshold rules
- ASET coach-review flags
- source file provenance
- duplicate/idempotency checks
- reconciliation output
- analyst signoff
- preflight publication gate
- staff portal traceability

