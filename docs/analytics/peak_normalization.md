# PEAK Normalization

Last updated: 2026-07-13

Source file:

```text
pipeline/config/wyscout_peak_normalization.csv
```

## Coach-Confirmed Rules

- Event-derived scoring is official.
- Wyscout PDFs are validation/comparison.
- Individual Wyscout events are sufficient for PEAK scoring.
- No PEAK sequence bonus.
- No coach/video confirmation gate for PEAK.
- Advance = `0.5` points per `10` successful Advance actions.
- Punish and Advance do not double-count the same action.
- Punish takes priority.
- The 3-5 pass threshold divides Punish from Advance.

## How To Read The Table

Important columns:

- `raw_label`: raw or normalized Wyscout label.
- `normalized_metric`: COUG metric name to score.
- `peak_phase`: PEAK phase, such as Punish, Advance, or Kill.
- `score_policy`: how the row scores.
- `event_weight`: per-event weight when applicable.
- `threshold_count` / `threshold_score`: grouped threshold scoring, used for Advance.
- `requires_success`: whether unsuccessful/unknown actions should be filtered.
- `double_count_priority`: lower number wins if one action could map to multiple metrics.
- `pass_threshold_rule`: how the 3-5 pass rule applies.
- `official_status`: whether the coach rule is official, provisional, or excluded.
- `implementation_status`: what the code still needs.

## Current PEAK Mapping

### Kill

| Raw Label | Metric | Rule |
| --- | --- | --- |
| `Goal` | Goal (scorer) | 3.0 per event |
| `Goal (scorer)` | Goal (scorer) | 3.0 per event |
| `Goal (on field)` | Goal (on field) | 1.0 per reviewed on-field athlete except the scorer |
| `Assists` | Assist | 2.0 per event |
| `Assist` | Assist | 2.0 per event |

### Punish

| Raw Label | Metric | Rule |
| --- | --- | --- |
| `Opportunity` | Punish Action after Regain | 0.2 per successful/context-valid event |
| `Shots` with Opportunity context | Punish Action after Regain | 0.2 per successful/context-valid event |

Punish should apply before possession is established. If the same action could
be both Punish and Advance, score it as Punish only.

### Advance

| Raw Label | Metric | Rule |
| --- | --- | --- |
| `Key passes` | Advance | 0.5 per 10 successful Advance actions |
| `Smart pass` | Advance | 0.5 per 10 successful Advance actions |
| `Smart passes` | Advance | 0.5 per 10 successful Advance actions |

Advance should not score per event. Count successful Advance actions and apply:

```text
floor(successful_advance_action_count / 10) * 0.5
```

### Set Piece / Provisional

`Free kick goal` is excluded because the Wyscout label is free-kick context,
not proof of a scored goal. Any future set-piece credit requires corroboration
with an actual team goal event. Only then should the set-piece bonus and
standard scorer credit be evaluated under the coach-approved policy.

`Free kick shot` is excluded for now because no confirmed PEAK metric/weight
exists for it.

## Implementation Checklist

1. Load `pipeline/config/wyscout_peak_normalization.csv` in scoring/reconciliation.
2. Replace hardcoded PEAK candidate constants with table-driven rules.
3. Apply double-count priority so Punish wins over Advance.
4. Apply the 3-5 pass threshold when enough sequence/context exists.
5. Apply Advance threshold scoring at player-match level, not event level.
6. Flag rows where `requires_success=true` but outcome is `Unknown`.
7. Keep PDFs as validation/comparison only.

## Known Constraints

The current repo has parsed player-event CSVs for the 2025 season, but most raw
`player_events.xml` / `team_events.xml` files are still missing locally. That
means implementation should continue to report source completeness and mapping
confidence clearly.
