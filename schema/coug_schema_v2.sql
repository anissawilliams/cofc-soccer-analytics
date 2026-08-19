-- ============================================================
-- COUG TABLE — DATABASE SCHEMA v2
-- ============================================================
-- Compatible with PostgreSQL 14+ / Supabase
-- Changes from v1:
--   - session table as parent (replaces match as anchor)
--   - match extends session for competitive games
--   - athlete_load table for Catapult GPS data
--   - possession_sequence table for PEAK phase tracking
--   - sequence_id on athlete_event (nullable, v2 feature hook)
--   - Advance added to metric_definition seed
--   - session_type covers match | scrimmage | training
--   - source_priority on data_source for duality handling
--   - raw_value_context JSONB on athlete_event for location etc.
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- TEAM
-- ============================================================
CREATE TABLE team (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name                VARCHAR(100) NOT NULL,
    short_name          VARCHAR(20),
    conference          VARCHAR(50),
    division            VARCHAR(50),
    is_caa_opponent     BOOLEAN DEFAULT FALSE,
    is_cofc             BOOLEAN DEFAULT FALSE,
    wyscout_team_id     VARCHAR(50),
    spideo_team_id      VARCHAR(50),
    logo_url            TEXT,
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- ATHLETE
-- ============================================================
CREATE TABLE athlete (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    wyscout_id          VARCHAR(50),
    spideo_id           VARCHAR(50),
    catapult_id         VARCHAR(50),       -- Catapult uses full names; store for matching
    first_name          VARCHAR(50) NOT NULL,
    last_name           VARCHAR(50) NOT NULL,
    display_name        VARCHAR(100),      -- e.g. "J. Jordheim" — normalized short form
    position            VARCHAR(20),
    position_group      VARCHAR(30),       -- GK | DEF | MID | FWD
    nationality         VARCHAR(50),
    dob                 DATE,
    status              VARCHAR(20) DEFAULT 'active',
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- SESSION  (parent of all activity — match, scrimmage, training)
-- ============================================================
CREATE TABLE session (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_date        DATE NOT NULL,
    session_type        VARCHAR(20) NOT NULL,  -- match | scrimmage | training
    season              VARCHAR(10),
    competition         VARCHAR(50),           -- CAA | non-conference | preseason | training
    venue               VARCHAR(100),
    notes               TEXT,
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW(),

    CONSTRAINT chk_session_type CHECK (
        session_type IN ('match', 'scrimmage', 'training')
    )
);

-- ============================================================
-- MATCH  (extends session for competitive/scrimmage games)
-- ============================================================
CREATE TABLE match (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id          UUID NOT NULL UNIQUE REFERENCES session(id) ON DELETE CASCADE,
    home_team_id        UUID NOT NULL REFERENCES team(id),
    away_team_id        UUID NOT NULL REFERENCES team(id),
    result              VARCHAR(10),           -- W | L | D
    goals_for           INT,
    goals_against       INT,
    created_at          TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- ATHLETE_SESSION_STINT  (replaces athlete_match_stint)
-- covers playing time for matches AND training participation
-- ============================================================
CREATE TABLE athlete_session_stint (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    athlete_id          UUID NOT NULL REFERENCES athlete(id),
    session_id          UUID NOT NULL REFERENCES session(id),
    minutes_on          INT DEFAULT 0,
    minutes_off         INT DEFAULT 90,
    started             BOOLEAN DEFAULT FALSE,
    participated        BOOLEAN DEFAULT TRUE,  -- for training: did they attend?
    created_at          TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- METRIC_CATEGORY  (static lookup)
-- ============================================================
CREATE TABLE metric_category (
    id                          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code                        VARCHAR(20) NOT NULL UNIQUE,
    label                       VARCHAR(50) NOT NULL,
    phase                       VARCHAR(20),
    default_sign                FLOAT DEFAULT 1.0,
    affects_team_score          BOOLEAN DEFAULT FALSE,
    affects_individual_score    BOOLEAN DEFAULT TRUE,
    scoring_logic_notes         TEXT,
    created_at                  TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- METRIC_DEFINITION
-- ============================================================
CREATE TABLE metric_definition (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    category_id             UUID NOT NULL REFERENCES metric_category(id),
    name                    VARCHAR(100) NOT NULL,
    peak_phase              VARCHAR(10),        -- P | E | A | K (PEAK metrics only)
    aset_letter             VARCHAR(10),        -- A | S | E | T (ASET metrics only)
    collection_method       VARCHAR(20),        -- auto | derived | semi-auto | manual
    manual_tag_required     BOOLEAN DEFAULT FALSE,
    coach_confirmed         BOOLEAN DEFAULT FALSE,
    applies_to_session_type VARCHAR(20) DEFAULT 'match', -- match | training | both
    notes                   TEXT,
    created_at              TIMESTAMP DEFAULT NOW(),
    updated_at              TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- METRIC_WEIGHT  (versioned)
-- ============================================================
CREATE TABLE scoring_version (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    version             VARCHAR(50) NOT NULL UNIQUE,
    effective_from      TIMESTAMP,
    notes               TEXT,
    created_at          TIMESTAMP DEFAULT NOW()
);

CREATE TABLE metric_weight (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    metric_id           UUID NOT NULL REFERENCES metric_definition(id),
    weight              FLOAT NOT NULL,
    weight_type         VARCHAR(20) DEFAULT 'match',   -- match | season | cumulative
    is_multiplier       BOOLEAN DEFAULT FALSE,         -- true = multiplier, false = additive
    version             VARCHAR(20) NOT NULL,
    scoring_version_id  UUID NOT NULL REFERENCES scoring_version(id),
    coach_notes         TEXT,
    effective_from      TIMESTAMP DEFAULT NOW(),
    effective_to        TIMESTAMP,
    created_at          TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- DATA_SOURCE
-- ============================================================
CREATE TABLE data_source (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name                VARCHAR(100) NOT NULL,
    platform            VARCHAR(30),       -- wyscout | spideo | catapult | hudl | csv | manual
    source_type         VARCHAR(20),       -- api | file | manual
    source_priority     INT DEFAULT 1,     -- higher = more trusted; xml=3, csv=2, manual=1
    api_endpoint        TEXT,
    file_path           TEXT,
    file_format         VARCHAR(20),       -- xml | json | csv
    ingested_at         TIMESTAMP,
    ingested_by         VARCHAR(100),
    notes               TEXT,
    created_at          TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- POSSESSION_SEQUENCE
-- Tracks full PEAK phase sequences (P→E→A→K) within a session.
-- Individual athlete_event rows link back here via sequence_id.
-- Enables sequence completion bonuses and tactical analysis.
-- ============================================================
CREATE TABLE possession_sequence (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id          UUID NOT NULL REFERENCES session(id),
    started_at          FLOAT,             -- video timestamp (seconds) of P phase
    ended_at            FLOAT,             -- video timestamp of K phase (if completed)
    phases_completed    VARCHAR(10),       -- e.g. 'P', 'PE', 'PEA', 'PEAK'
    sequence_bonus      FLOAT DEFAULT 0,   -- bonus awarded for full PEAK completion
    notes               TEXT,
    created_at          TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- ATHLETE_EVENT
-- One row per scorable event per athlete per session.
-- raw_value_context carries location, phase, or sub-type data
-- that affects weighting (e.g. regain in attacking half = higher value).
-- ============================================================
CREATE TABLE athlete_event (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    athlete_id          UUID NOT NULL REFERENCES athlete(id),
    session_id          UUID NOT NULL REFERENCES session(id),
    metric_id           UUID NOT NULL REFERENCES metric_definition(id),
    source_id           UUID REFERENCES data_source(id),
    sequence_id         UUID REFERENCES possession_sequence(id), -- nullable; v2 hook
    raw_value           FLOAT DEFAULT 1.0,
    raw_value_context   JSONB,             -- e.g. {"half": 1, "x": 87.3, "y": 45.1, "zone": "attacking_third"}
    collection_method   VARCHAR(20),       -- auto | derived | semi-auto | manual
    manually_tagged     BOOLEAN DEFAULT FALSE,
    coach_confirmed     BOOLEAN DEFAULT FALSE,
    tag_notes           TEXT,
    event_time          FLOAT,             -- video timestamp in seconds
    created_at          TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- ATHLETE_LOAD  (Catapult GPS / physical data)
-- One row per athlete per session per period.
-- period_name: 'Session' (full) | '1st Half' | '2nd Half' | 'Training Block'
-- Rolling z-scores calculated at query time or via scheduled job.
-- ============================================================
CREATE TABLE athlete_load (
    id                          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    athlete_id                  UUID NOT NULL REFERENCES athlete(id),
    session_id                  UUID NOT NULL REFERENCES session(id),
    source_id                   UUID REFERENCES data_source(id),
    period_name                 VARCHAR(30) DEFAULT 'Session',

    -- Core volume metrics
    player_load                 FLOAT,
    distance                    FLOAT,
    high_metabolic_load_distance FLOAT,
    accel_decel_efforts         INT,

    -- Core intensity metrics
    player_load_per_minute      FLOAT,
    accel_decel_per_minute      FLOAT,
    hi_distance_pct             FLOAT,
    max_velocity                FLOAT,

    -- Extended metrics (store what Catapult exports; nullable)
    max_acceleration            FLOAT,
    max_deceleration            FLOAT,
    sprint_distance             FLOAT,
    sprint_efforts              INT,
    max_heart_rate              INT,
    avg_heart_rate              INT,
    hr_exertion                 INT,
    energy                      FLOAT,
    duration_seconds            INT,

    -- Derived scores (calculated by pipeline, stored for fast reads)
    volume_score                FLOAT,     -- within-session z-score
    intensity_score             FLOAT,     -- within-session z-score
    volume_score_rolling        FLOAT,     -- rolling z-score vs athlete's own history
    intensity_score_rolling     FLOAT,     -- rolling z-score vs athlete's own history

    created_at                  TIMESTAMP DEFAULT NOW(),

    UNIQUE (athlete_id, session_id, period_name)
);

-- ============================================================
-- COUG_SCORE
-- ============================================================
CREATE TABLE coug_score (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    athlete_id          UUID NOT NULL REFERENCES athlete(id),
    session_id          UUID NOT NULL REFERENCES session(id),
    weight_version_id   UUID REFERENCES metric_weight(id), -- legacy compatibility FK
    scoring_version_id  UUID NOT NULL REFERENCES scoring_version(id),
    aset_score          FLOAT DEFAULT 0,
    peak_score          FLOAT DEFAULT 0,
    set_piece_score     FLOAT DEFAULT 0,
    positional_score    FLOAT DEFAULT 0,
    load_score          FLOAT DEFAULT 0,   -- Catapult-derived component (GK + all athletes)
    total_score         FLOAT DEFAULT 0,
    score_type          VARCHAR(20) DEFAULT 'match',   -- match | rolling | season
    data_source_path    VARCHAR(20) DEFAULT 'xml',     -- xml | csv | manual (trust indicator)
    calculated_at       TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- SPIIDEO_TAG_MAP  (normalize raw Spiideo codes → metric_definition)
-- Handles casing inconsistencies and non-COUG tags.
-- is_scorable = FALSE means tag is logged but not scored
-- (e.g. 'HT clips', 'Double Switch', 'Build from goal kick')
-- ============================================================
CREATE TABLE spiideo_tag_map (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    raw_code            VARCHAR(100) NOT NULL UNIQUE,  -- exactly as it appears in XML
    normalized_code     VARCHAR(100),                  -- cleaned version
    metric_id           UUID REFERENCES metric_definition(id),
    is_scorable         BOOLEAN DEFAULT TRUE,
    notes               TEXT,
    created_at          TIMESTAMP DEFAULT NOW()
);

-- ============================================================
-- INDEXES
-- ============================================================
CREATE INDEX idx_athlete_event_athlete       ON athlete_event(athlete_id);
CREATE INDEX idx_athlete_event_session       ON athlete_event(session_id);
CREATE INDEX idx_athlete_event_metric        ON athlete_event(metric_id);
CREATE INDEX idx_athlete_event_sequence      ON athlete_event(sequence_id);
CREATE INDEX idx_coug_score_athlete          ON coug_score(athlete_id);
CREATE INDEX idx_coug_score_session          ON coug_score(session_id);
CREATE INDEX idx_metric_weight_metric        ON metric_weight(metric_id);
CREATE INDEX idx_session_date_type           ON session(session_date, session_type);
CREATE INDEX idx_session_season              ON session(season);
CREATE INDEX idx_stint_athlete_session       ON athlete_session_stint(athlete_id, session_id);
CREATE INDEX idx_athlete_load_athlete        ON athlete_load(athlete_id);
CREATE INDEX idx_athlete_load_session        ON athlete_load(session_id);
CREATE INDEX idx_possession_sequence_session ON possession_sequence(session_id);
CREATE INDEX idx_athlete_display_name        ON athlete(display_name);

-- ============================================================
-- SEED — METRIC CATEGORIES
-- ============================================================
INSERT INTO metric_category (code, label, phase, default_sign, affects_team_score, affects_individual_score, scoring_logic_notes) VALUES
('ASET_DEF',   'ASET — Defense',   'defense',   1.0,  FALSE, TRUE,  'All in, Sprint, Engage, Trust — defensive effort metrics'),
('PEAK_OFF',   'PEAK — Offense',   'offense',   1.0,  FALSE, TRUE,  'Punish, Establish, Advance, Kill — attacking phase metrics'),
('SET_PIECE',  'Set Piece',        'both',      1.0,  FALSE, TRUE,  'Set piece specific events, offensive and defensive'),
('POSITIONAL', 'Positional',       'both',      1.0,  FALSE, TRUE,  'Position-group specific metrics by role'),
('TEAM',       'Team',             'both',      1.0,  TRUE,  TRUE,  'Clean sheet and team-level events credited to all on-field athletes'),
('LOAD',       'Physical Load',    'both',      1.0,  FALSE, TRUE,  'Catapult-derived physical metrics. GK scoring + counter press validation');

-- ============================================================
-- SEED — METRIC DEFINITIONS
-- ============================================================
INSERT INTO metric_definition (category_id, name, peak_phase, aset_letter, collection_method, manual_tag_required, coach_confirmed, applies_to_session_type, notes)
SELECT c.id, m.name, m.peak_phase, m.aset_letter, m.collection_method, m.manual_tag_required, m.coach_confirmed, m.applies_to_session_type, m.notes
FROM metric_category c
JOIN (VALUES
    -- ASET — Defense (All in, Sprint, Engage, Trust)
    ('ASET_DEF', 'Possession Regain',               NULL, 'E', 'auto',      FALSE, FALSE, 'match', 'Wyscout recovery/interception. Sub-weighted by location: attacking half > counter press > run of play.'),
    ('ASET_DEF', 'Successful Counter Press (<5s)',  NULL, 'S', 'manual',    TRUE,  FALSE, 'match', 'Spideo tag within 5s of turnover. Validate with Catapult sprint/accel data.'),
    ('ASET_DEF', 'Block in Box',                    NULL, 'A', 'auto',      FALSE, TRUE,  'match', 'Wyscout shot_block filtered to penalty area (x>83, y 19-81). Emergency defending = 0.2.'),
    ('ASET_DEF', 'Clearance from Danger',           NULL, 'T', 'manual',    TRUE,  TRUE,  'match', 'Eye test required. No credit if ball ends in opponent possession or no 2nd phase cleared.'),
    ('TEAM',     'Clean Sheet (Full Team)',          NULL, NULL,'derived',   FALSE, TRUE,  'match', 'goals_conceded=0 AND athlete on pitch full match. Everyone gets +1 at final whistle.'),
    ('ASET_DEF', 'Concede Goal (on field)',         NULL, NULL,'derived',   FALSE, TRUE,  'match', 'Negative. All athletes on pitch at moment of concession.'),

    -- PEAK — Offense (Punish, Establish, Advance, Kill)
    ('PEAK_OFF', 'Punish Action after Regain',      'P',  NULL,'manual',    TRUE,  TRUE,  'match', 'Spideo tag. Forward pass or ball progression immediately after regain. Connecting pass, shot.'),
    ('PEAK_OFF', 'Establishing Possession',         'E',  NULL,'derived',   TRUE,  TRUE,  'match', '3+ consecutive passes after regain. Credit to initiating athlete.'),
    ('PEAK_OFF', 'Advance',                         'A',  NULL,'auto',      FALSE, FALSE, 'match', 'Progressive pass/carry into final third. Wyscout progressive action events. Weight TBD — confirm with coach.'),
    ('PEAK_OFF', 'Goal (scorer)',                   'K',  NULL,'auto',      FALSE, TRUE,  'match', 'Wyscout goal event — playerId. 3 points.'),
    ('PEAK_OFF', 'Goal (on field)',                 'K',  NULL,'derived',   FALSE, TRUE,  'match', 'All athletes on pitch when team scores (excluding scorer). 1 point.'),
    ('PEAK_OFF', 'Assist',                          'K',  NULL,'auto',      FALSE, TRUE,  'match', 'Wyscout assist event. Regular assist = 2, hockey assist = 0.5.'),

    -- Set Piece
    ('SET_PIECE','Win 1st Header (offensive)',      NULL, NULL,'manual',    TRUE,  TRUE,  'match', 'Spideo tag. First header won on offensive set piece delivery. Weight 0.25.'),
    ('SET_PIECE','Win 1st Header (defensive)',      NULL, NULL,'manual',    TRUE,  TRUE,  'match', 'Spideo tag. First header won on defensive set piece delivery. Weight 0.25.'),
    ('SET_PIECE','Set Piece Goal (1st phase)',      NULL, NULL,'semi-auto', TRUE,  TRUE,  'match', 'Wyscout set piece goal + Spideo phase tag. Bonus point on top of regular goal credit.'),
    ('SET_PIECE','Set Piece Goal (2nd phase)',      NULL, NULL,'semi-auto', TRUE,  TRUE,  'match', 'Rebound/secondary delivery. Same bonus structure, lower weight than 1st phase.'),
    ('SET_PIECE','Penalty Save',                    NULL, NULL,'auto',      FALSE, TRUE,  'match', 'Wyscout save where situation=penalty. 3 points.'),
    ('SET_PIECE','Freekick Save/Block',             NULL, NULL,'auto',      FALSE, TRUE,  'match', 'Wyscout save/block where situation=free kick. 1 point.'),
    ('SET_PIECE','Concede from Set Piece (on field)',NULL,NULL,'auto',      FALSE, TRUE,  'match', 'Negative multiplier: -2 on top of regular concede -2 = -3 total. Confirm with coach.'),

    -- Positional
    ('POSITIONAL','Shots on Target (FWD)',          NULL, NULL,'auto',      FALSE, FALSE, 'match', 'Forward only. Wyscout shot on target events. Weight 0.5.'),
    ('POSITIONAL','Pass Success Rate (MID)',        NULL, NULL,'auto',      FALSE, FALSE, 'match', 'Center mid only. Wyscout pass accuracy. Threshold TBD. Weight +0.5.'),
    ('POSITIONAL','Crosses Attempted (WB)',         NULL, NULL,'auto',      FALSE, FALSE, 'match', 'Wing back only. 8 crosses = 0.5 per data dictionary.'),
    ('POSITIONAL','Aerial Duels Won (CB)',          NULL, NULL,'auto',      FALSE, FALSE, 'match', 'Center back only. Wyscout aerial duel events. Weight 0.5.'),

    -- Load (Catapult)
    ('LOAD',     'High Volume Session (GK)',        NULL, NULL,'derived',   FALSE, FALSE, 'both',  'Goalkeeper scoring via Catapult. High volume_score_rolling triggers credit. Threshold TBD.'),
    ('LOAD',     'High Intensity Session (GK)',     NULL, NULL,'derived',   FALSE, FALSE, 'both',  'Goalkeeper scoring via Catapult. High intensity_score_rolling triggers credit. Threshold TBD.')

) AS m(category_code, name, peak_phase, aset_letter, collection_method, manual_tag_required, coach_confirmed, applies_to_session_type, notes)
ON c.code = m.category_code;

-- ============================================================
-- SEED — METRIC WEIGHTS (version: trial_1)
-- ============================================================
INSERT INTO scoring_version (version, effective_from, notes)
VALUES ('trial_1', NOW(), 'Initial coach-confirmed scoring weights');

INSERT INTO metric_weight (metric_id, weight, weight_type, is_multiplier, version, scoring_version_id, coach_notes, effective_from)
SELECT d.id, w.weight, 'match', w.is_multiplier, 'trial_1', sv.id, w.coach_notes, NOW()
FROM metric_definition d
JOIN scoring_version sv ON sv.version = 'trial_1'
JOIN (VALUES
    ('Possession Regain',                0.25,  FALSE, 'Attacking half=0.5, counter press=0.25, run of play=0.25 — sub-weighting via raw_value_context'),
    ('Successful Counter Press (<5s)',   0.2,   FALSE, 'Per action'),
    ('Block in Box',                     0.2,   FALSE, 'Emergency defending'),
    ('Clearance from Danger',            0.5,   FALSE, 'No 2nd phase / OOB or regained possession only'),
    ('Clean Sheet (Full Team)',          1.0,   FALSE, 'Full team credit at final whistle'),
    ('Concede Goal (on field)',         -2.0,   FALSE, NULL),
    ('Punish Action after Regain',       0.2,   FALSE, 'Per action — connecting pass, shot'),
    ('Goal (scorer)',                    3.0,   FALSE, NULL),
    ('Goal (on field)',                  1.0,   FALSE, NULL),
    ('Assist',                           2.0,   FALSE, 'Hockey assist = 0.5'),
    ('Win 1st Header (offensive)',       0.25,  FALSE, 'Updated from 0.2 per data dictionary'),
    ('Win 1st Header (defensive)',       0.25,  FALSE, 'Updated from 0.2 per data dictionary'),
    ('Set Piece Goal (1st phase)',       1.0,   FALSE, 'Bonus on top of regular goal credit'),
    ('Set Piece Goal (2nd phase)',       0.5,   FALSE, 'Bonus on top of regular goal credit'),
    ('Penalty Save',                     3.0,   FALSE, NULL),
    ('Freekick Save/Block',              1.0,   FALSE, NULL),
    ('Concede from Set Piece (on field)',-2.0,  TRUE,  'Multiplier: total = -2 (regular) + -2 (set piece) = -3 vs -2. Confirm with coach.'),
    ('Shots on Target (FWD)',            0.5,   FALSE, 'Forward position group only'),
    ('Pass Success Rate (MID)',          0.5,   FALSE, 'Center mid only. Threshold TBD'),
    ('Crosses Attempted (WB)',           0.5,   FALSE, '8 crosses = 0.5'),
    ('Aerial Duels Won (CB)',            0.5,   FALSE, 'Center back only')
) AS w(metric_name, weight, is_multiplier, coach_notes)
ON d.name = w.metric_name;

-- ============================================================
-- SEED — SPIIDEO TAG MAP
-- Maps raw XML codes → metric_definition or marks as non-scorable
-- ============================================================
INSERT INTO spiideo_tag_map (raw_code, normalized_code, metric_id, is_scorable, notes)
SELECT
    t.raw_code,
    t.normalized_code,
    d.id,
    t.is_scorable,
    t.notes
FROM (VALUES
    ('ASET - Counter press',    'ASET - Counter Press',         TRUE,  'Maps to Successful Counter Press (<5s)'),
    ('ASET - Low Block',        'ASET - Low Block',             FALSE, 'Tactical review tag — not a scored metric yet. Log but do not score.'),
    ('ASET - Press',            'ASET - Press',                 FALSE, 'Tactical review tag — not a scored metric yet. Log but do not score.'),
    ('PEAK - Punish',           'PEAK - Punish',                TRUE,  'Maps to Punish Action after Regain'),
    ('Peak - Establish',        'PEAK - Establish',             TRUE,  'Maps to Establishing Possession'),
    ('DEF Set piece',           'DEF Set Piece',                FALSE, 'Context tag — used with header/concede metrics, not standalone scored'),
    ('ATT set piece',           'ATT Set Piece',                FALSE, 'Context tag — used with header/goal metrics, not standalone scored'),
    ('HT clips',                'HT Clips',                     FALSE, 'Highlight clips — not scored'),
    ('Double Switch',           'Double Switch',                FALSE, 'Substitution tag — not scored'),
    ('Build from goal kick',    'Build from Goal Kick',         FALSE, 'Tactical tag — not scored'),
    ('Build',                   'Build',                        FALSE, 'Tactical tag — not scored'),
    ('Press',                   'Press',                        FALSE, 'Generic press tag — not scored. Use ASET - Counter press for scoring.'),
    ('Counter Press',           'Counter Press',                FALSE, 'Unformatted — check if should map to ASET - Counter press'),
    ('Set Def',                 'Set Defense',                  FALSE, 'Tactical tag — not scored'),
    ('UBT',                     'UBT',                          FALSE, 'Unknown tag — needs coach clarification'),
    ('Risk taking areas',       'Risk Taking Areas',            FALSE, 'Tactical tag — not scored'),
    ('Def Trans',               'Defensive Transition',         FALSE, 'Tactical tag — not scored'),
    ('ASET',                    'ASET',                         FALSE, 'Generic ASET tag — too broad to score. Needs subtype.')
) AS t(raw_code, normalized_code, is_scorable, notes)
LEFT JOIN metric_definition d ON (
    (t.raw_code = 'ASET - Counter press'  AND d.name = 'Successful Counter Press (<5s)') OR
    (t.raw_code = 'PEAK - Punish'         AND d.name = 'Punish Action after Regain') OR
    (t.raw_code = 'Peak - Establish'      AND d.name = 'Establishing Possession')
);

-- ============================================================
-- SEED — CAA TEAMS
-- ============================================================
INSERT INTO team (name, short_name, conference, division, is_caa_opponent, is_cofc) VALUES
('College of Charleston',   'CofC',       'CAA', 'DI', FALSE, TRUE),
('Campbell University',     'Campbell',   'CAA', 'DI', TRUE,  FALSE),
('Delaware',                'Delaware',   'CAA', 'DI', TRUE,  FALSE),
('Drexel',                  'Drexel',     'CAA', 'DI', TRUE,  FALSE),
('Elon University',         'Elon',       'CAA', 'DI', TRUE,  FALSE),
('Hampton University',      'Hampton',    'CAA', 'DI', TRUE,  FALSE),
('Hofstra',                 'Hofstra',    'CAA', 'DI', TRUE,  FALSE),
('Monmouth',                'Monmouth',   'CAA', 'DI', TRUE,  FALSE),
('NC Wilmington',           'UNCW',       'CAA', 'DI', TRUE,  FALSE),
('Northeastern',            'NEU',        'CAA', 'DI', TRUE,  FALSE),
('Rhode Island',            'URI',        'CAA', 'DI', TRUE,  FALSE),
('Stony Brook',             'Stony Brook','CAA', 'DI', TRUE,  FALSE),
('Towson',                  'Towson',     'CAA', 'DI', TRUE,  FALSE),
('William & Mary',          'W&M',        'CAA', 'DI', TRUE,  FALSE);

-- ============================================================
-- NOTES FOR SUPABASE SETUP
-- ============================================================
-- 1. Run this entire file in the Supabase SQL editor
-- 2. Enable Row Level Security (RLS) on athlete, coug_score,
--    athlete_event after initial load
-- 3. The spiideo_tag_map table should be the first thing
--    undergrads update when new tag codes appear in XML
-- 4. Advance metric weight is intentionally omitted from
--    trial_1 — add when coach confirms value
-- 5. PEAK sequence bonus logic is a v2 feature — possession_sequence
--    table is ready but sequence_id on athlete_event is nullable
-- 6. Rolling z-scores for athlete_load are calculated by the
--    pipeline, not in the DB — store results in
--    volume_score_rolling / intensity_score_rolling columns
