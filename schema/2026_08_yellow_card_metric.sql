-- Coach-confirmed individual yellow-card deduction used by staff event CSV intake.
-- Five yellow cards total -2 points, equivalent to the existing red-card deduction.
BEGIN;

INSERT INTO public.metric_definition (
    category_id, name, collection_method, manual_tag_required,
    coach_confirmed, applies_to_session_type, notes
)
SELECT
    category.id, 'Yellow Card', 'manual', TRUE,
    TRUE, 'match', 'Individual caution entered through reviewed staff events; five cautions equal -2 points.'
FROM public.metric_category AS category
WHERE category.code = 'ASET_DEF'
  AND NOT EXISTS (
      SELECT 1 FROM public.metric_definition WHERE name = 'Yellow Card'
  );

-- Support both the normalized metric_weight schema and the legacy production shape.
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
                definition.id, -0.4, 'match', FALSE, 'trial_1',
                version.id, 'Yellow card: -0.4; five cautions equal -2.', NOW()
            FROM public.metric_definition AS definition
            JOIN public.scoring_version AS version ON version.version = 'trial_1'
            WHERE definition.name = 'Yellow Card'
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
            definition.id, -0.4, 'match', FALSE, 'trial_1',
            'Yellow card: -0.4; five cautions equal -2.', NOW()
        FROM public.metric_definition AS definition
        WHERE definition.name = 'Yellow Card'
          AND NOT EXISTS (
              SELECT 1 FROM public.metric_weight AS existing
              WHERE existing.metric_id = definition.id
                AND existing.version = 'trial_1'
                AND existing.effective_to IS NULL
          );
    END IF;
END $$;

COMMIT;
