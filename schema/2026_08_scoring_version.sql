-- Stable scoring-version identity for metric weights and published COUG scores.
-- Review and run this migration in Supabase before using the 2026 publisher.
-- This is an additive compatibility migration: it deliberately retains the
-- legacy coug_score.weight_version_id column and its existing foreign key.
-- It intentionally aborts if existing COUG rows collapse to duplicate logical
-- scores after their individual metric-weight IDs are mapped to one version.

BEGIN;

CREATE TABLE IF NOT EXISTS public.scoring_version (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    version         VARCHAR(50) NOT NULL UNIQUE,
    effective_from  TIMESTAMP,
    notes           TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

INSERT INTO public.scoring_version (version, effective_from)
SELECT version, MIN(effective_from)
FROM public.metric_weight
GROUP BY version
ON CONFLICT (version) DO NOTHING;

ALTER TABLE public.metric_weight
ADD COLUMN IF NOT EXISTS scoring_version_id UUID;

UPDATE public.metric_weight mw
SET scoring_version_id = sv.id
FROM public.scoring_version sv
WHERE sv.version = mw.version
  AND mw.scoring_version_id IS DISTINCT FROM sv.id;

ALTER TABLE public.metric_weight
ALTER COLUMN scoring_version_id SET NOT NULL;

ALTER TABLE public.metric_weight
DROP CONSTRAINT IF EXISTS metric_weight_scoring_version_id_fkey;

ALTER TABLE public.metric_weight
ADD CONSTRAINT metric_weight_scoring_version_id_fkey
FOREIGN KEY (scoring_version_id) REFERENCES public.scoring_version(id);

ALTER TABLE public.coug_score
ADD COLUMN IF NOT EXISTS scoring_version_id UUID;

UPDATE public.coug_score cs
SET scoring_version_id = mw.scoring_version_id
FROM public.metric_weight mw
WHERE cs.weight_version_id = mw.id
  AND cs.scoring_version_id IS NULL;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM public.coug_score WHERE scoring_version_id IS NULL) THEN
        RAISE EXCEPTION 'Migration blocked: some coug_score rows have no resolvable scoring version';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM public.coug_score
        GROUP BY athlete_id, session_id, scoring_version_id, score_type
        HAVING COUNT(*) > 1
    ) THEN
        RAISE EXCEPTION 'Migration blocked: duplicate logical COUG scores exist after version mapping';
    END IF;
END $$;

ALTER TABLE public.coug_score
ALTER COLUMN scoring_version_id SET NOT NULL;

ALTER TABLE public.coug_score
ADD CONSTRAINT coug_score_scoring_version_id_fkey
FOREIGN KEY (scoring_version_id) REFERENCES public.scoring_version(id);

CREATE UNIQUE INDEX IF NOT EXISTS uniq_coug_score_athlete_session_scoring_version_type
ON public.coug_score (athlete_id, session_id, scoring_version_id, score_type);

COMMIT;
