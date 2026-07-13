# COUG Score Reconciliation Triage

Generated from reconciliation CSVs with a PEAK delta threshold of `1`.

This report is diagnostic only. It does not decide whether the coach/legacy, PDF, or event-derived value is correct.

## Status Counts

| triage_status | rows |
| --- | --- |
| within_threshold | 39 |
| legacy_only_player | 16 |
| candidate_below_legacy | 9 |
| legacy_peak_without_normalized_peak_events | 4 |

## Highest PEAK Deltas

| slug | triage_status | triage_player | candidate_peak_score | legacy_peak | pdf_peak | delta_candidate_peak_score_vs_legacy_peak | trace_candidate_peak_labels | legacy_peak_breakdown |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2025-09-27_william_mary | legacy_peak_without_normalized_peak_events | J. Watson | 0 | 19 | 0 | -19 |  | {'WY:Free kick goal': 10.0, 'WY:Goal': 9.0} |
| 2025-10-25_william_mary | legacy_only_player | B. Alibaruho |  | 16 |  | -16 |  | {'WY:Free kick goal': 7.0, 'WY:Goal': 9.0} |
| 2025-10-25_william_mary | candidate_below_legacy | S. Bendvold | 3.8 | 10 | 7.3 | -6.2 | Goal (scorer), Punish Action after Regain | {'WY:Shots': 7.0, 'WY:Goal': 3.0} |
| 2025-09-27_william_mary | candidate_below_legacy | S. Bendvold | 3.2 | 9 | 14 | -5.8 | Assist, Punish Action after Regain | {'WY:Shots': 7.0, 'WY:Assists': 2.0} |
| 2025-09-27_william_mary | candidate_below_legacy | P. Dashin | 3.8 | 8 | 9.5 | -4.2 | Goal (scorer), Punish Action after Regain | {'WY:Shots': 5.0, 'WY:Goal': 3.0} |
| 2025-10-25_william_mary | legacy_only_player | A. Duran |  | 4 |  | -4 |  | {'WY:Shots': 4.0} |
| 2025-11-02_uncw | candidate_below_legacy | S. Bendvold | 0.4 | 4 | 4.3 | -3.6 | Punish Action after Regain | {'WY:Shots': 1.0, 'WY:Goal': 3.0} |
| 2025-09-27_william_mary | legacy_peak_without_normalized_peak_events | E. White | 0 | 3 | 5.1 | -3 |  | {'WY:Goal': 3.0} |
| 2025-11-02_uncw | legacy_only_player | E. Goetzke |  | 3 | 3.5 | -3 |  | {'WY:Goal': 3.0} |
| 2025-10-25_william_mary | legacy_peak_without_normalized_peak_events | R. Watson | 0 | 3 | 0 | -3 |  | {'WY:Goal': 3.0} |
| 2025-11-02_uncw | candidate_below_legacy | L. Gill | 1.2 | 4 | 9.2 | -2.8 | Punish Action after Regain | {'WY:Shots': 4.0} |
| 2025-09-27_william_mary | candidate_below_legacy | B. Bagshaw | 7.2 | 10 | 13.6 | -2.8 | Goal (scorer), Punish Action after Regain | {'WY:Shots': 4.0, 'WY:Goal': 6.0} |
| 2025-10-25_william_mary | legacy_only_player | J. Neumann |  | 2 |  | -2 |  | {'WY:Shots': 2.0} |
| 2025-09-27_william_mary | candidate_below_legacy | M. Lenert | 1.2 | 3 | 12 | -1.8 | Punish Action after Regain | {'WY:Shots': 3.0} |
| 2025-10-25_william_mary | candidate_below_legacy | L. Gill | 4.2 | 6 | 10.4 | -1.8 | Goal (scorer), Punish Action after Regain | {'WY:Shots': 3.0, 'WY:Goal': 3.0} |
| 2025-09-27_william_mary | candidate_below_legacy | L. Gill | 0.8 | 2 | 6.5 | -1.2 | Punish Action after Regain | {'WY:Shots': 2.0} |
| 2025-11-02_uncw | legacy_peak_without_normalized_peak_events | P. Dashin | 0 | 1 | 0.2 | -1 |  | {'WY:Shots': 1.0} |
| 2025-09-27_william_mary | legacy_only_player | A. Duran |  | 1 |  | -1 |  | {'WY:Shots': 1.0} |
| 2025-11-02_uncw | within_threshold | M. Lenert | 3.4 | 4 | 4.1 | -0.6 | Goal (scorer), Punish Action after Regain | {'WY:Shots': 1.0, 'WY:Goal': 3.0} |
| 2025-10-25_william_mary | within_threshold | M. Lenert | 0.4 | 1 | 3.6 | -0.6 | Punish Action after Regain | {'WY:Shots': 1.0} |
| 2025-11-02_uncw | within_threshold | E. White | 0 | 0 | 3.7 | 0 |  | {} |
| 2025-09-27_william_mary | within_threshold | H. Walker | 0 | 0 | 3.4 | 0 |  | {} |
| 2025-09-27_william_mary | within_threshold | C. Hughes | 2 | 2 | 5.1 | 0 | Assist | {'WY:Assists': 2.0} |
| 2025-10-25_william_mary | within_threshold | J. Barrett | 0 | 0 | 3 | 0 |  | {} |
| 2025-10-25_william_mary | within_threshold | J. Jordheim | 0 | 0 | 3 | 0 |  | {} |

## Legacy-Only Players

| slug | triage_player | legacy_peak | legacy_player_match_method | legacy_peak_breakdown |
| --- | --- | --- | --- | --- |
| 2025-10-25_william_mary | B. Alibaruho | 16 | athlete.display_name | {'WY:Free kick goal': 7.0, 'WY:Goal': 9.0} |
| 2025-10-25_william_mary | A. Duran | 4 | athlete.display_name | {'WY:Shots': 4.0} |
| 2025-11-02_uncw | E. Goetzke | 3 | athlete_alias:coach_workbook:former_name | {'WY:Goal': 3.0} |
| 2025-10-25_william_mary | J. Neumann | 2 | athlete.display_name | {'WY:Shots': 2.0} |
| 2025-09-27_william_mary | A. Duran | 1 | athlete.display_name | {'WY:Shots': 1.0} |
| 2025-10-25_william_mary | E. Goetzke | 0 | athlete_alias:coach_workbook:former_name | {} |
| 2025-09-27_william_mary | E. Goetzke | 0 | athlete_alias:coach_workbook:former_name | {} |
| 2025-09-27_william_mary | J. Neumann | 0 | athlete.display_name | {} |
| 2025-09-27_william_mary | T. Nero | 0 | athlete.display_name | {} |
| 2025-10-25_william_mary | R. Ray | 0 | athlete.display_name | {} |
| 2025-10-25_william_mary | T. Nero | 0 | athlete.display_name | {} |
| 2025-11-02_uncw | A. Duran | 0 | athlete.display_name | {} |
| 2025-11-02_uncw | B. Alibaruho | 0 | athlete.display_name | {} |
| 2025-11-02_uncw | J. Neumann | 0 | athlete.display_name | {} |
| 2025-11-02_uncw | J. Watson | 0 | athlete.display_name | {} |
| 2025-11-02_uncw | R. Cates | 0 | athlete.display_name | {} |

## Normalized PEAK Event Evidence

| slug | triage_player | candidate_peak_score | trace_candidate_peak_score | trace_advance_actions | trace_candidate_peak_labels | trace_peak_statuses |
| --- | --- | --- | --- | --- | --- | --- |
| 2025-10-25_william_mary | S. Bendvold | 3.8 | 3.8 | 0 | Goal (scorer), Punish Action after Regain | ready, needs_context_rule |
| 2025-09-27_william_mary | S. Bendvold | 3.2 | 3.2 | 0 | Assist, Punish Action after Regain | ready, needs_context_rule |
| 2025-09-27_william_mary | P. Dashin | 3.8 | 3.8 | 0 | Goal (scorer), Punish Action after Regain | ready, needs_context_rule |
| 2025-11-02_uncw | S. Bendvold | 0.4 | 0.4 | 0 | Punish Action after Regain | needs_context_rule |
| 2025-11-02_uncw | L. Gill | 1.2 | 1.2 | 0 | Punish Action after Regain | needs_context_rule |
| 2025-09-27_william_mary | B. Bagshaw | 7.2 | 7.2 | 0 | Goal (scorer), Punish Action after Regain | ready, needs_context_rule |
| 2025-09-27_william_mary | M. Lenert | 1.2 | 1.2 | 0 | Punish Action after Regain | needs_context_rule |
| 2025-10-25_william_mary | L. Gill | 4.2 | 4.2 | 0 | Goal (scorer), Punish Action after Regain | ready, needs_context_rule |
| 2025-09-27_william_mary | L. Gill | 0.8 | 0.8 | 0 | Punish Action after Regain | needs_context_rule |
| 2025-11-02_uncw | M. Lenert | 3.4 | 3.4 | 0 | Goal (scorer), Punish Action after Regain | ready, needs_context_rule |
| 2025-10-25_william_mary | M. Lenert | 0.4 | 0.4 | 0 | Punish Action after Regain | needs_context_rule |
| 2025-09-27_william_mary | C. Hughes | 2 | 2 | 0 | Assist | ready |
| 2025-10-25_william_mary | E. White | 2 | 2 | 0 | Assist | ready |
| 2025-10-25_william_mary | N. Gold | 2 | 2 | 0 | Assist | ready |
| 2025-10-25_william_mary | P. Dashin | 2 | 2 | 0 | Assist | ready |
| 2025-09-27_william_mary | B. Baldwin | 1 | 1 | 0 | Set Piece Goal (1st phase) | needs_set_piece_policy |
| 2025-10-25_william_mary | H. Walker | 3 | 3 | 0 | Goal (scorer) | ready |

## How To Use This

- Start with `legacy_peak_without_normalized_peak_events` and `candidate_below_legacy` rows.
- For each top row, inspect the matching `*_event_score_trace.csv` by `player_key` and `raw_metric_name`.
- Treat legacy/PDF values as comparison baselines. The official path is event-derived scoring once source coverage and mapping are verified.
