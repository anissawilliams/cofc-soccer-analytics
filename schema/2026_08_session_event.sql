-- Staff-entered match and training events.
-- Weighted events point to one exact metric_weight row and remain pending
-- until the existing reviewed COUG score publication process applies them.

BEGIN;

CREATE TABLE IF NOT EXISTS public.session_event (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id          UUID NOT NULL REFERENCES public.session(id) ON DELETE CASCADE,
    athlete_id          UUID REFERENCES public.athlete(id),
    event_type          VARCHAR(100) NOT NULL,
    metric_weight_id    UUID REFERENCES public.metric_weight(id),
    raw_value           NUMERIC NOT NULL DEFAULT 1.0,
    event_time          FLOAT,
    notes               TEXT,
    recorded_by         VARCHAR(100) NOT NULL DEFAULT 'Staff portal',
    score_status        VARCHAR(30) NOT NULL DEFAULT 'informational',
    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_session_event_raw_value CHECK (raw_value > 0),
    CONSTRAINT chk_session_event_time CHECK (event_time IS NULL OR event_time >= 0),
    CONSTRAINT chk_session_event_score_status CHECK (
        score_status IN ('informational', 'pending_review', 'applied', 'excluded')
    ),
    CONSTRAINT chk_session_event_weighted_athlete CHECK (
        metric_weight_id IS NULL OR athlete_id IS NOT NULL
    ),
    CONSTRAINT chk_session_event_status_matches_weight CHECK (
        (metric_weight_id IS NULL AND score_status = 'informational')
        OR (metric_weight_id IS NOT NULL AND score_status IN ('pending_review', 'applied', 'excluded'))
    )
);

CREATE INDEX IF NOT EXISTS idx_session_event_session ON public.session_event(session_id);
CREATE INDEX IF NOT EXISTS idx_session_event_athlete ON public.session_event(athlete_id);
CREATE INDEX IF NOT EXISTS idx_session_event_weight ON public.session_event(metric_weight_id);
CREATE INDEX IF NOT EXISTS idx_session_event_status ON public.session_event(score_status);

ALTER TABLE public.session_event ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE public.session_event IS
'Staff-entered match and training observations. Weighted rows require review before COUG publication.';
COMMENT ON COLUMN public.session_event.metric_weight_id IS
'Exact versioned scoring weight proposed for this event; nullable for informational events.';
COMMENT ON COLUMN public.session_event.score_status IS
'informational, pending_review, applied, or excluded. The form never silently changes published COUG totals.';

COMMIT;
