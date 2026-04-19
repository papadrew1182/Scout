-- Phase 3: Chore scope contracts + dispute tracking
--
-- Adds scope-contract fields to public.chore_templates (the legacy
-- Session 1 table). The sprint spec references scout.chore_templates
-- but the live table is in public; this migration adds columns there.
--
-- Also adds dispute tracking to public.task_instances.

-- 1. Scope contract columns on chore_templates
ALTER TABLE public.chore_templates
  ADD COLUMN IF NOT EXISTS included jsonb DEFAULT '[]',
  ADD COLUMN IF NOT EXISTS not_included jsonb DEFAULT '[]',
  ADD COLUMN IF NOT EXISTS done_means_done text,
  ADD COLUMN IF NOT EXISTS supplies jsonb DEFAULT '[]',
  ADD COLUMN IF NOT EXISTS photo_example_url text,
  ADD COLUMN IF NOT EXISTS estimated_duration_minutes integer,
  ADD COLUMN IF NOT EXISTS consequence_on_miss text;

-- 2. Dispute tracking on task_instances
ALTER TABLE public.task_instances
  ADD COLUMN IF NOT EXISTS in_scope_confirmed boolean DEFAULT false,
  ADD COLUMN IF NOT EXISTS scope_dispute_opened_at timestamptz;
