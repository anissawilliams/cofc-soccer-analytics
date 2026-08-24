-- Coach-confirmed individual red-card penalty used by staff event CSV intake.
BEGIN;

INSERT INTO public.metric_definition (
    category_id, name, collection_method, manual_tag_required,
    coach_confirmed, applies_to_session_type, notes
)
SELECT
    category.id, 'Red Card', 'manual', TRUE,
    TRUE, 'match', 'Individual dismissal penalty entered through reviewed staff events.'
FROM public.metric_category AS category
WHERE category.code = 'ASET_DEF'
  AND NOT EXISTS (
      SELECT 1 FROM public.metric_definition WHERE name = 'Red Card'
  );

-- Production may still use the legacy metric_weight shape. Insert through the
-- normalized scoring_version FK only when that compatibility migration is live.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'metric_weight'
          AND column_name = 'scoring_version_id'
    ) THEN
        EXECUTE $sql$
            INSERT INTO public.metric_weight (
                metric_id, weight, weight_type, is_multiplier, version,
                scoring_version_id, coach_notes, effective_from
            )
            SELECT
                definition.id, -2, 'match', FALSE, 'trial_1',
                version.id, 'Red card: -2 to the dismissed player.', NOW()
            FROM public.metric_definition AS definition
            JOIN public.scoring_version AS version ON version.version = 'trial_1'
            WHERE definition.name = 'Red Card'
              AND NOT EXISTS (
                  SELECT 1 FROM public.metric_weight AS existing
                  WHERE existing.metric_id = definition.id
                    AND existing.version = 'trial_1'
                    AND existing.effective_to IS NULL
              )
        $sql$;
    ELSE
        INSERT INTO public.metric_weight (
            metric_id, weight, weight_type, is_multiplier, version,
            coach_notes, effective_from
        )
        SELECT
            definition.id, -2, 'match', FALSE, 'trial_1',
            'Red card: -2 to the dismissed player.', NOW()
        FROM public.metric_definition AS definition
        WHERE definition.name = 'Red Card'
          AND NOT EXISTS (
              SELECT 1 FROM public.metric_weight AS existing
              WHERE existing.metric_id = definition.id
                AND existing.version = 'trial_1'
                AND existing.effective_to IS NULL
          );
    END IF;
END $$;

COMMIT;
