-- Migration 017: fix ai_messages.created_at ordering bug
--
-- PostgreSQL's now() (which maps to func.now() in SQLAlchemy and
-- DEFAULT now() at the table level) returns TRANSACTION_TIMESTAMP —
-- the time the enclosing transaction started. Every row inserted in
-- the same transaction gets the same created_at.
--
-- The orchestrator persists user/assistant/tool/assistant messages
-- for a single turn in one flush, so all four rows ended up with
-- identical timestamps. _load_conversation_messages then sorted by
-- created_at, got nondeterministic ordering, and handed Anthropic a
-- history where the tool_result preceded the tool_use — producing
-- the "messages.N.content.0: unexpected tool_use_id found in
-- tool_result blocks" 400 error on every follow-up turn after a
-- tool call. Reload fixed it in the UI because it started a fresh
-- conversation without bad history.
--
-- Fix: switch to clock_timestamp(), which returns the actual wall
-- clock at each INSERT. Multi-row flushes now get monotonically
-- increasing timestamps at microsecond resolution.
--
-- Only ai_messages is fixed here — other tables order by created_at
-- but don't depend on intra-transaction monotonicity the way
-- conversation replay does.

BEGIN;

ALTER TABLE ai_messages
    ALTER COLUMN created_at SET DEFAULT clock_timestamp();

COMMIT;
