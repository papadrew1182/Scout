-- Migration 045: Add metadata JSONB column to ai_messages
--
-- Stores per-message auxiliary data that does not fit the existing
-- columns. Initial use-case: attachment references so the frontend
-- can render uploaded images when replaying a conversation thread.
--
-- Example value:
--   {"attachment_path": "family_id/member_id/2026-04-20/img.jpg",
--    "attachment_url": "https://...signed_url..."}

ALTER TABLE public.ai_messages
    ADD COLUMN IF NOT EXISTS metadata JSONB;
