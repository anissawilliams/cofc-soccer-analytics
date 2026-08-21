-- Wyscout's `Free kick goal` player-event label is free-kick context, not
-- proof that a goal was scored. Davidson produced six such labels in a 1-1
-- match where neither goal came from a free kick. Preserve previously loaded
-- athlete_event evidence, but stop creating/scoring these rows by default.
-- Any future set-piece goal bonus must be corroborated with an actual team
-- goal event and reviewed lineup/set-piece context.

UPDATE public.metric_scoring_rule
SET
  is_active = false,
  effective_to = COALESCE(effective_to, now()),
  review_status = 'needs_confirmation',
  coach_explanation = 'Raw Wyscout free-kick context; not a verified scored goal. Exclude unless corroborated by an actual team goal.',
  technical_notes = 'Disabled after Davidson 2026 review showed six labels and zero free-kick goals.',
  updated_at = now()
WHERE source_platform = 'wyscout'
  AND source_event_label = 'Free kick goal'
  AND is_active = true;
