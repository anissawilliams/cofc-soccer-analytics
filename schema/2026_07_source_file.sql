-- ============================================================
-- COUG SOCCER ANALYTICS — SOURCE FILE REGISTRY
-- ============================================================
-- Purpose:
--   Store one row per concrete raw/source file in Supabase Storage.
--
-- Naming:
--   Storage bucket: source-files
--   Metadata table: public.source_file
--
-- Relationship:
--   data_source describes the system/source family, e.g. Wyscout Sportscode.
--   source_file describes the exact object used for a match/session parse.
--
-- Safe to run repeatedly in Supabase SQL editor.
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS public.source_file (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),

  -- Optional links into the existing model.
  source_id uuid REFERENCES public.data_source(id),
  session_id uuid REFERENCES public.session(id),

  -- Match/source identity. Keep season + match_slug denormalized so files can
  -- be registered before the session row exists.
  organization_code varchar(50) DEFAULT 'cofc',
  season varchar(10),
  match_slug varchar(120),
  source_system varchar(50) NOT NULL,      -- wyscout | spiideo | catapult | coach_workbook | manual
  source_type varchar(50) NOT NULL,        -- sportscode | player_events | team_events | effective_time | pdf_report | csv | xlsx
  file_role varchar(80),                   -- primary_events | validation_report | load | scouting | other

  -- Supabase Storage object identity.
  storage_bucket varchar(120) NOT NULL DEFAULT 'source-files',
  storage_path text NOT NULL,
  original_filename text,
  content_type varchar(120),
  file_format varchar(20),                 -- xml | pdf | csv | xlsx | json
  byte_size bigint,
  sha256 char(64),
  storage_etag text,

  -- Ingestion / parse lifecycle.
  upload_status varchar(30) NOT NULL DEFAULT 'registered',
  parse_status varchar(30) NOT NULL DEFAULT 'pending',
  parser_version varchar(80),
  uploaded_at timestamp without time zone DEFAULT now(),
  uploaded_by varchar(120),
  parsed_at timestamp without time zone,
  last_checked_at timestamp without time zone,
  error_message text,

  -- Flexible vendor/file metadata. Examples: Wyscout match id, export
  -- timestamp, row counts, XML encoding, PDF page count.
  metadata jsonb DEFAULT '{}'::jsonb,
  notes text,
  is_active boolean DEFAULT true,
  created_at timestamp without time zone DEFAULT now(),
  updated_at timestamp without time zone DEFAULT now(),

  CONSTRAINT chk_source_file_upload_status CHECK (
    upload_status IN ('registered', 'uploaded', 'missing', 'failed', 'archived')
  ),
  CONSTRAINT chk_source_file_parse_status CHECK (
    parse_status IN ('pending', 'parsed', 'skipped', 'failed', 'not_applicable')
  ),
  CONSTRAINT chk_source_file_sha256 CHECK (
    sha256 IS NULL OR sha256 ~ '^[a-f0-9]{64}$'
  )
);

CREATE UNIQUE INDEX IF NOT EXISTS uniq_source_file_storage_object
ON public.source_file (storage_bucket, storage_path);

CREATE INDEX IF NOT EXISTS idx_source_file_session
ON public.source_file (session_id);

CREATE INDEX IF NOT EXISTS idx_source_file_match
ON public.source_file (season, match_slug);

CREATE INDEX IF NOT EXISTS idx_source_file_system_type
ON public.source_file (source_system, source_type);

CREATE INDEX IF NOT EXISTS idx_source_file_parse_status
ON public.source_file (parse_status);

CREATE INDEX IF NOT EXISTS idx_source_file_sha256
ON public.source_file (sha256);

-- Optional exact-file provenance on parsed fact tables.
ALTER TABLE public.athlete_event
ADD COLUMN IF NOT EXISTS source_file_id uuid REFERENCES public.source_file(id);

ALTER TABLE public.athlete_load
ADD COLUMN IF NOT EXISTS source_file_id uuid REFERENCES public.source_file(id);

CREATE INDEX IF NOT EXISTS idx_athlete_event_source_file
ON public.athlete_event (source_file_id);

CREATE INDEX IF NOT EXISTS idx_athlete_load_source_file
ON public.athlete_load (source_file_id);

COMMENT ON TABLE public.source_file IS
'One row per concrete raw/source file stored in Supabase Storage. data_source describes the platform; source_file identifies the exact object.';

COMMENT ON COLUMN public.source_file.storage_path IS
'Object path inside the bucket, e.g. cofc/2025/2025-09-27_william_mary/wyscout/2025-09-27_william_mary_cfc_sportscode.xml.';

COMMENT ON COLUMN public.athlete_event.source_file_id IS
'Exact raw/source file used to create this event row, when known.';

COMMENT ON COLUMN public.athlete_load.source_file_id IS
'Exact raw/source file used to create this load row, when known.';
