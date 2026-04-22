# Batch 1 PR 2 handoff — AI chat polish

**Branch:** `batch-1/pr-2-ai-chat-polish`
**Base:** main at `03d8de2` (PR 1 squash merge)
**Pulled from:** the 72-item backlog dump, ai-chat domain, four items

## Summary

Four self-contained AI-chat cleanups. One is dead-code removal that
also doubles as the answer to a long-standing unknown, one is a
surfaced observability measurement, and two are small hygiene fixes.
No schema change, no new routes, no new config keys.

## Items shipped

### Item 1: Remove SAMPLE_THREAD + surrounding dead code

`scout-ui/lib/mockScout.ts` still exported `SAMPLE_THREAD` plus
`ScoutTurn`, `mockScoutResponse`, `KEYWORD_REPLIES`, and `FALLBACK`.
PR #39 (Phase 1 AI resume follow-up) removed the consumers but left
the exports orphaned. Grep for `SAMPLE_THREAD` / `mockScoutResponse`
across `scout-ui/` confirmed zero importers outside the file
itself. The previous gap-analysis agent flagged the same state.

Deleted the dead block. Kept the two exports that ARE used by
`ScoutSidebar.tsx` and `ScoutSheet.tsx` (`ScoutSurface` type and
`QUICK_ACTIONS_BY_SURFACE` lookup). Updated the top-of-file comment
to reflect what the module actually does now.

### Item 2: Skip-with-reason on ai.manage_own_conversations denial test

The `test_post_conversations_denies_without_permission` test in
`backend/tests/test_ai_conversation_resume.py` already had an
in-body `pytest.skip(reason=...)`. Tightened to the decorator form
`@pytest.mark.skip(reason=...)` with a more specific reason
pointing at migration 046 and the unskip condition (a future tier
like `READ_ONLY` that legitimately lacks the permission). Skip
runs cleanly (confirmed by `pytest backend/tests/test_ai_conversation_resume.py -k permission -xvs`).

### Item 3: sendChatMessage 60s timeout investigation

Backlog item 5.3 asked "Does `sendChatMessage` gracefully handle
a 60s timeout?" After mapping the call graph I found:

- `backend/app/config.py:33` pins `ai_request_timeout = 60` seconds
  on the Anthropic SDK client (`provider.py:115`).
- `scout-ui/lib/api.ts` exported both `sendChatMessage` (non-streaming)
  and `sendChatMessageStream` (SSE).
- The UI exclusively calls `sendChatMessageStream`. Grep for
  `sendChatMessage(` outside `api.ts` returns zero hits.

The non-streaming function has been dead since the streaming migration.
Its 60s timeout behavior cannot affect users today.

Honest fix: delete the dead function plus its dead-only types
(`AIChatResult`, `SendChatOptions`). Replace with a banner comment
explaining the removal and the forward path if a non-streaming call
site is ever needed again (buffer the `done` event from the stream
variant rather than re-introducing the old shape).

Per the scope guard (task #43): this is not a timeout refactor,
just dead-code removal. Kept strictly XS; frontend typecheck clean.

### Item 4: Prompt-cache hit-rate measurement

The observability layer (`backend/app/ai/observability.py`) already
stamps `cache_creation_input_tokens` and `cache_read_input_tokens`
on every `ai_call` log line (shipped in PR #31 Phase 10). The
aggregation script `scripts/ai_cost_report.py` parses those lines
but its `Rollup` class dropped the cache fields on the floor.

Extended `Rollup` to accumulate both cache-token fields and
compute `cache_hit_rate = cache_read / total_input` where
`total_input = input_tokens + cache_read + cache_creation`. The
terminal render shows a new line under the Total block:

```
-- Total --
messages=    2  input=     150  output=      80  cost_usd=$0.0015
  cache: read=    1800  created=     200  hit_rate= 83.7%
```

The JSON footer also carries the three new fields per
family-day and per-tool rollup so downstream consumers can pipe.

Sanity-checked locally with a two-line fabricated log input
(1800 cache-read + 200 cache-creation + 150 uncached):

```
hit_rate = 1800 / (150 + 200 + 1800) = 0.8372  (83.7%)
```

Matches the rendered output. A doc note in this handoff covers
what the fields mean; no separate architecture-doc entry needed.

## Verification

- `backend/tests/test_ai_conversation_resume.py`: 24 passed, 1 skipped
- Frontend `npx tsc --noEmit`: clean
- `node scripts/architecture-check.js`: 0 WARN, 1 INFO (same
  pre-existing seedData drift as PR 1; not caused by this PR)

## Not in scope

- Timeout-handling refactor on `sendChatMessageStream`. That's a
  separate concern with different semantics (SSE keeps the
  connection open throughout generation; no 60s budget applies
  the same way).
- Per-conversation hit-rate dashboard. The aggregation script
  produces the signal; a visual dashboard is EXECUTION_BACKLOG
  item 1.2 and stays deferred.
- Deleting `mockScout.ts` entirely. The file still carries
  `QUICK_ACTIONS_BY_SURFACE` which is live data for ScoutSidebar +
  ScoutSheet.

## On Andrew's plate

- Review PR 2 when opened
- Squash-merge
- Confirm Railway + Vercel deploys green post-merge
- Once merged, PR 3 (seed data refresh) starts

## Meta-notes for the batch

- Task #42 (seedData INFO drift watch): unchanged from PR 1 baseline.
  Still pre-existing, same constants, no new additions from this PR.
- Task #43 (timeout investigation scope guard): respected. Finding
  reshaped the work from "investigate runtime behavior" to "delete
  dead code that cannot exhibit runtime behavior." No refactor.
