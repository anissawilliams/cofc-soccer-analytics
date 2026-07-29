-- ============================================================
-- COUG SOCCER ANALYTICS — NORMALIZED METRIC SCORING RULES
-- ============================================================
-- Purpose:
--   Move machine-readable scoring metadata out of free-text notes while
--   preserving metric_definition.notes as immutable migration evidence.
--
-- Safety:
--   - Does not update metric_definition, metric_weight, athlete_event, or
--     coug_score.
--   - Does not change a metric weight or calculate a score.
--   - Safe to run repeatedly.
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS public.metric_scoring_rule (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  metric_id uuid NOT NULL REFERENCES public.metric_definition(id),

  source_platform varchar(30) NOT NULL,
  source_event_label varchar(120) NOT NULL,
  outcome_rule varchar(30) NOT NULL DEFAULT 'always_count',

  eligible_positions text[] NOT NULL DEFAULT '{}'::text[],
  excluded_positions text[] NOT NULL DEFAULT '{}'::text[],
  minimum_event_count integer NOT NULL DEFAULT 1,
  aggregation_rule varchar(30) NOT NULL DEFAULT 'per_event',
  raw_value_per_event numeric NOT NULL DEFAULT 1.0,

  review_status varchar(30) NOT NULL DEFAULT 'unreviewed',
  relationship_type varchar(30),
  related_metric_id uuid REFERENCES public.metric_definition(id),

  coach_explanation text NOT NULL,
  technical_notes text,
  legacy_note text,
  is_active boolean NOT NULL DEFAULT true,
  effective_from timestamp without time zone NOT NULL DEFAULT now(),
  effective_to timestamp without time zone,
  created_at timestamp without time zone NOT NULL DEFAULT now(),
  updated_at timestamp without time zone NOT NULL DEFAULT now(),

  CONSTRAINT chk_metric_scoring_rule_outcome CHECK (
    outcome_rule IN ('always_count', 'plus_only', 'non_minus')
  ),
  CONSTRAINT chk_metric_scoring_rule_aggregation CHECK (
    aggregation_rule IN ('per_event', 'threshold_qualifier')
  ),
  CONSTRAINT chk_metric_scoring_rule_review CHECK (
    review_status IN (
      'confirmed',
      'unreviewed',
      'needs_confirmation',
      'proxy_review',
      'duplicate',
      'alias'
    )
  ),
  CONSTRAINT chk_metric_scoring_rule_relationship CHECK (
    relationship_type IS NULL OR relationship_type IN (
      'alias_of',
      'duplicate_of',
      'possible_duplicate_of'
    )
  ),
  CONSTRAINT chk_metric_scoring_rule_minimum CHECK (minimum_event_count >= 1),
  CONSTRAINT chk_metric_scoring_rule_raw_value CHECK (raw_value_per_event > 0)
);

CREATE UNIQUE INDEX IF NOT EXISTS uniq_metric_scoring_rule_active_source
ON public.metric_scoring_rule (source_platform, source_event_label)
WHERE is_active AND effective_to IS NULL;

CREATE INDEX IF NOT EXISTS idx_metric_scoring_rule_metric
ON public.metric_scoring_rule (metric_id);

CREATE INDEX IF NOT EXISTS idx_metric_scoring_rule_related_metric
ON public.metric_scoring_rule (related_metric_id);

COMMENT ON TABLE public.metric_scoring_rule IS
'Normalized source-event eligibility and counting metadata. Weights remain authoritative in metric_weight.';

COMMENT ON COLUMN public.metric_scoring_rule.legacy_note IS
'Verbatim metric_definition.notes captured during migration for audit; never parsed at scoring runtime.';

WITH rule_seed (
  metric_name,
  source_event_label,
  outcome_rule,
  eligible_positions,
  excluded_positions,
  minimum_event_count,
  aggregation_rule,
  review_status,
  relationship_type,
  related_metric_name,
  coach_explanation,
  technical_notes
) AS (
  VALUES
    ('Vol_Interception', 'Vol_Interception', 'always_count', '{}'::text[], '{}'::text[], 1, 'per_event', 'proxy_review', NULL, NULL,
      'Count each Wyscout interception event.', 'Review as a proxy for the coach-defined possession-regain concept.'),
    ('Tackles', 'Tackles', 'plus_only', '{}'::text[], '{}'::text[], 1, 'per_event', 'proxy_review', NULL, NULL,
      'Count successful Wyscout tackle events.', 'Success is represented by outcome Plus.'),
    ('Clearances', 'Clearances', 'plus_only', '{}'::text[], '{}'::text[], 1, 'per_event', 'proxy_review', NULL, NULL,
      'Count successful Wyscout clearance events.', 'Review as a proxy for Clearance from Danger.'),
    ('Anticipated', 'Anticipated', 'plus_only', '{}'::text[], '{}'::text[], 1, 'per_event', 'proxy_review', NULL, NULL,
      'Count successful Wyscout anticipated-action events.', 'Success is represented by outcome Plus.'),
    ('Anticipation', 'Anticipation', 'plus_only', '{}'::text[], '{}'::text[], 1, 'per_event', 'alias', 'alias_of', 'Anticipated',
      'Normalize successful Wyscout Anticipation events to the canonical anticipated-action metric.', 'This source label is an alias.'),
    ('Pressing duel', 'Pressing duel', 'non_minus', '{}'::text[], '{}'::text[], 1, 'per_event', 'proxy_review', NULL, NULL,
      'Count Wyscout pressing duels unless the outcome is Minus.', 'Review as a proxy for the coach-defined counter-press concept.'),
    ('Loose ball duel', 'Loose ball duel', 'non_minus', '{}'::text[], '{}'::text[], 1, 'per_event', 'proxy_review', NULL, NULL,
      'Count Wyscout loose-ball duels unless the outcome is Minus.', 'Review as an ASET proxy.'),
    ('Defensive duel', 'Defensive duel', 'non_minus', '{}'::text[], '{}'::text[], 1, 'per_event', 'proxy_review', NULL, NULL,
      'Count Wyscout defensive duels unless the outcome is Minus.', 'Review as an ASET proxy.'),
    ('1VS1', '1VS1', 'non_minus', '{}'::text[], '{}'::text[], 1, 'per_event', 'proxy_review', NULL, NULL,
      'Count Wyscout one-versus-one events unless the outcome is Minus.', 'Review as an ASET proxy.'),
    ('Goal (scorer)', 'Goal', 'always_count', '{}'::text[], ARRAY['GK'], 1, 'per_event', 'confirmed', NULL, NULL,
      'Count each Wyscout goal for the scorer; opponent goals are excluded for goalkeepers.', NULL),
    ('Assist', 'Assists', 'always_count', '{}'::text[], '{}'::text[], 1, 'per_event', 'confirmed', NULL, NULL,
      'Count each Wyscout assist event.', NULL),
    ('Key passes', 'Key passes', 'plus_only', '{}'::text[], '{}'::text[], 1, 'per_event', 'confirmed', NULL, NULL,
      'Count successful Wyscout key-pass events.', 'Success is represented by outcome Plus.'),
    ('Smart pass', 'Smart pass', 'plus_only', '{}'::text[], '{}'::text[], 1, 'per_event', 'confirmed', NULL, NULL,
      'Count successful Wyscout Smart pass events.', 'Canonical singular source label.'),
    ('Smart passes', 'Smart passes', 'plus_only', '{}'::text[], '{}'::text[], 1, 'per_event', 'alias', 'alias_of', 'Smart pass',
      'Normalize successful Wyscout Smart passes events to the canonical Smart pass metric.', 'This source label is an alias.'),
    ('Opportunity', 'Opportunity', 'plus_only', '{}'::text[], '{}'::text[], 1, 'per_event', 'confirmed', NULL, NULL,
      'Count successful Wyscout Opportunity events.', 'Success is represented by outcome Plus.'),
    ('Saves', 'Saves', 'always_count', ARRAY['GK'], '{}'::text[], 1, 'per_event', 'confirmed', NULL, NULL,
      'Count each Wyscout save for goalkeepers.', NULL),
    ('Free kick goal', 'Free kick goal', 'always_count', '{}'::text[], ARRAY['GK'], 1, 'per_event', 'confirmed', NULL, NULL,
      'Count each Wyscout free-kick goal; opponent goals are excluded for goalkeepers.', NULL),
    ('Free kick shot', 'Free kick shot', 'plus_only', '{}'::text[], '{}'::text[], 1, 'per_event', 'confirmed', NULL, NULL,
      'Count successful Wyscout free-kick shot events.', 'Success is represented by outcome Plus.'),
    ('Aerial duels', 'Aerial duels', 'always_count', ARRAY['CB'], '{}'::text[], 1, 'per_event', 'duplicate', 'duplicate_of', 'Aerial Duels Won (CB)',
      'Count each Wyscout aerial duel for center backs.', 'Possible duplicate representation retained for reconciliation.'),
    ('Cross', 'Cross', 'always_count', ARRAY['WB','RB','LB'], '{}'::text[], 8, 'threshold_qualifier', 'duplicate', 'duplicate_of', 'Crosses Attempted (WB)',
      'For wing backs and outside backs, count crosses only when the player records at least eight in the match.', 'The threshold qualifies all matching events; it is not batch scoring.'),
    ('Shots', 'Shots', 'always_count', ARRAY['F','W','F/W','WF'], '{}'::text[], 1, 'per_event', 'needs_confirmation', 'possible_duplicate_of', 'Shots on Target (FWD)',
      'Count each Wyscout shot for forwards and wingers.', 'Confirm whether this duplicates the Shots on Target positional metric.')
)
INSERT INTO public.metric_scoring_rule (
  metric_id,
  source_platform,
  source_event_label,
  outcome_rule,
  eligible_positions,
  excluded_positions,
  minimum_event_count,
  aggregation_rule,
  raw_value_per_event,
  review_status,
  relationship_type,
  related_metric_id,
  coach_explanation,
  technical_notes,
  legacy_note
)
SELECT
  metric.id,
  'wyscout',
  seed.source_event_label,
  seed.outcome_rule,
  seed.eligible_positions,
  seed.excluded_positions,
  seed.minimum_event_count,
  seed.aggregation_rule,
  1.0,
  seed.review_status,
  seed.relationship_type,
  related.id,
  seed.coach_explanation,
  seed.technical_notes,
  metric.notes
FROM rule_seed seed
JOIN public.metric_definition metric ON metric.name = seed.metric_name
LEFT JOIN public.metric_definition related ON related.name = seed.related_metric_name
WHERE NOT EXISTS (
  SELECT 1
  FROM public.metric_scoring_rule existing
  WHERE existing.source_platform = 'wyscout'
    AND existing.source_event_label = seed.source_event_label
    AND existing.is_active
    AND existing.effective_to IS NULL
);

-- Migration verification. Expected after the current seed:
--   normalized_rule_count = 21
--   missing_metric_count = 0
SELECT COUNT(*) AS normalized_rule_count
FROM public.metric_scoring_rule
WHERE source_platform = 'wyscout'
  AND is_active
  AND effective_to IS NULL;

WITH expected(label) AS (
  VALUES
    ('Vol_Interception'), ('Tackles'), ('Clearances'), ('Anticipated'),
    ('Anticipation'), ('Pressing duel'), ('Loose ball duel'),
    ('Defensive duel'), ('1VS1'), ('Goal'), ('Assists'), ('Key passes'),
    ('Smart pass'), ('Smart passes'), ('Opportunity'), ('Saves'),
    ('Free kick goal'), ('Free kick shot'), ('Aerial duels'), ('Cross'),
    ('Shots')
)
SELECT COUNT(*) AS missing_metric_count
FROM expected
LEFT JOIN public.metric_scoring_rule rule
  ON rule.source_platform = 'wyscout'
 AND rule.source_event_label = expected.label
 AND rule.is_active
 AND rule.effective_to IS NULL
WHERE rule.id IS NULL;
