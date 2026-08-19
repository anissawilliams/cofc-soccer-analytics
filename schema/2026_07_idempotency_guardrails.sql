-- ============================================================
-- COUG SOCCER ANALYTICS — IDEMPOTENCY GUARDRAILS
-- ============================================================
-- Review before running in Supabase. This file is intentionally separate
-- from coug_schema_v2.sql because the live DB already exists.
--
-- Run the duplicate check queries first. If any return rows, resolve those
-- duplicates before creating the matching unique index.
-- ============================================================

-- ------------------------------------------------------------
-- 1. Duplicate checks
-- ------------------------------------------------------------

-- Repeated data_source rows make event provenance ambiguous.
SELECT platform, name, COUNT(*) AS duplicate_count
FROM public.data_source
GROUP BY platform, name
HAVING COUNT(*) > 1;

-- A player should have one stint row per session.
SELECT athlete_id, session_id, COUNT(*) AS duplicate_count
FROM public.athlete_session_stint
GROUP BY athlete_id, session_id
HAVING COUNT(*) > 1;

-- COUG scores should be unique for a player/session/scoring-version/score-type.
SELECT athlete_id, session_id, scoring_version_id, score_type, COUNT(*) AS duplicate_count
FROM public.coug_score
GROUP BY athlete_id, session_id, scoring_version_id, score_type
HAVING COUNT(*) > 1;

-- Retain the legacy uniqueness check during the compatibility window.
SELECT athlete_id, session_id, weight_version_id, score_type, COUNT(*) AS duplicate_count
FROM public.coug_score
GROUP BY athlete_id, session_id, weight_version_id, score_type
HAVING COUNT(*) > 1;

-- Athlete events should not duplicate the same evidence from the same source.
SELECT
  athlete_id,
  session_id,
  metric_id,
  source_id,
  collection_method,
  event_time,
  raw_value_context,
  COUNT(*) AS duplicate_count
FROM public.athlete_event
GROUP BY
  athlete_id,
  session_id,
  metric_id,
  source_id,
  collection_method,
  event_time,
  raw_value_context
HAVING COUNT(*) > 1;

-- Athlete load should be unique for a player/session/period.
SELECT athlete_id, session_id, period_name, COUNT(*) AS duplicate_count
FROM public.athlete_load
GROUP BY athlete_id, session_id, period_name
HAVING COUNT(*) > 1;

-- ------------------------------------------------------------
-- 2. Unique indexes
-- ------------------------------------------------------------
-- Run these only after the duplicate checks are clean.

CREATE UNIQUE INDEX IF NOT EXISTS uniq_data_source_platform_name
ON public.data_source (platform, name);

CREATE UNIQUE INDEX IF NOT EXISTS uniq_athlete_session_stint_athlete_session
ON public.athlete_session_stint (athlete_id, session_id);

CREATE UNIQUE INDEX IF NOT EXISTS uniq_coug_score_athlete_session_scoring_version_type
ON public.coug_score (athlete_id, session_id, scoring_version_id, score_type);

CREATE UNIQUE INDEX IF NOT EXISTS uniq_coug_score_athlete_session_weight_type
ON public.coug_score (athlete_id, session_id, weight_version_id, score_type);

CREATE UNIQUE INDEX IF NOT EXISTS uniq_athlete_load_athlete_session_period
ON public.athlete_load (athlete_id, session_id, period_name);

CREATE UNIQUE INDEX IF NOT EXISTS uniq_athlete_event_source_evidence
ON public.athlete_event (
  athlete_id,
  session_id,
  metric_id,
  COALESCE(source_id, '00000000-0000-0000-0000-000000000000'::uuid),
  COALESCE(collection_method, ''),
  COALESCE(event_time, -1),
  COALESCE(raw_value_context::text, '')
);

-- ------------------------------------------------------------
-- 3. Notes
-- ------------------------------------------------------------
-- scoring_version_id references one stable scoring contract. Individual
-- metric_weight rows reference the same scoring_version record.
