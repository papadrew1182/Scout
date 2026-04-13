# Scout Release Candidate Report

**Verified commit:** `549723b` (main)
**Date:** 2026-04-12
**Branch:** launch-preflight (from main)

## Verification Results

### Backend Tests
- **Result:** 320 passed, 0 failed
- **Command:** `cd backend && python -m pytest tests/ -v --tb=short`
- **Coverage:** auth (40), grocery (26), weekly meals (39), AI (29), meals (15), dashboard (11), route-level (27), plus calendar, finance, notes, personal tasks, health, integrations, payouts, tenant isolation

### TypeScript Check
- **Result:** Clean, no errors
- **Command:** `cd scout-ui && npx tsc --noEmit`

### Local Smoke Tests (Playwright)
- **Result:** 12/12 passed (17.0s)
- **Command:** `SCOUT_WEB_URL=http://localhost:8081 npx playwright test --reporter=list`
- **Coverage:**
  - Adult login
  - Child login
  - Bad password error
  - Sign out returns to login
  - Invalid token clears to login
  - Personal dashboard loads
  - Meals This Week loads
  - Grocery page loads
  - Settings page loads
  - Adult sees Accounts & Access
  - Child settings loads
  - Child does NOT see Accounts & Access

### Docker Compose Verification
- **Result:** Skipped
- **Reason:** Docker Desktop daemon not running on this machine
- **Compose file status:** Structurally verified (healthchecks, depends_on service_healthy, correct env propagation). No code changes to compose since last structural review.

### Deployed Smoke Verification
- **Result:** Skipped
- **Reason:** No SCOUT_DEPLOYED_WEB_URL provided
- **Command to run later:** `SCOUT_WEB_URL=https://your-deployed-url npx playwright test`

## Codebase Sweep Results

| Finding | Count | Classification |
|---|---|---|
| FAMILY_ID in code | 0 | Removed |
| CURRENT_USER_ID/NAME | 0 | Removed |
| TODO/FIXME | 0 | None |
| console.log | 0 | None |
| console.error | 9 | Intentional (API error reporting) |
| Test credentials in code | 15 | Intentional (smoke/test-only, documented) |
| localhost in config defaults | 2 | Intentional (dev defaults, production fail-closed rejects) |
| auth_required=false default | 1 | Intentional (dev default, production requires true) |
| enable_bootstrap=true default | 1 | Intentional (bootstrap only works with zero accounts) |

## Production Safety Rules (Confirmed)

1. `SCOUT_ENVIRONMENT=production` requires `SCOUT_AUTH_REQUIRED=true` (startup fails otherwise)
2. Production requires non-localhost `SCOUT_CORS_ORIGINS` (startup fails otherwise)
3. Bootstrap endpoint returns 409 when any accounts exist, regardless of `SCOUT_ENABLE_BOOTSTRAP` flag
4. Production warns if bootstrap still enabled
5. All family-scoped routes require bearer token authentication
6. Role enforcement is server-derived (no client-supplied role trust)
7. Active family derived from `/api/auth/me` (no hardcoded FAMILY_ID)
8. Login rate limited: 10 attempts per 5 minutes per email/IP

## /ready Output

```json
{
  "status": "ready",
  "environment": "development",
  "auth_required": false,
  "bootstrap_enabled": true,
  "accounts_exist": true,
  "ai_available": false,
  "meal_generation": true
}
```

## Go/No-Go Recommendation

**GO — Safe for private family launch** with these caveats:

1. Set `SCOUT_ENVIRONMENT=production` before launch
2. Set `SCOUT_AUTH_REQUIRED=true` before launch
3. Set `SCOUT_CORS_ORIGINS` to production frontend URL
4. Set `SCOUT_ENABLE_BOOTSTRAP=false` after first account creation
5. Docker compose should be verified on a machine with Docker Desktop running before production deploy

## Remaining Deferred Risks

| Item | Risk | Mitigation |
|---|---|---|
| Docker compose not E2E verified | Low | Compose is structurally correct; local stack verified directly |
| Rate limiter is in-memory | Low | Resets on restart; acceptable for single-instance private app |
| No email password reset | Low | Admin direct-reset via Settings; private family only |

---

## Deployed Verification (2026-04-12)

**Commit deployed:** `5c7d849` (main)
**Backend:** https://scout-backend-production-9991.up.railway.app
**Frontend:** https://scout-ui-gamma.vercel.app

### Production Environment Variables Set

| Variable | Set | Value |
|---|---|---|
| SCOUT_DATABASE_URL | Yes | (Railway Postgres) |
| SCOUT_ENVIRONMENT | Yes | `production` |
| SCOUT_AUTH_REQUIRED | Yes | `true` |
| SCOUT_CORS_ORIGINS | Yes | Vercel + Railway + localhost |
| SCOUT_ENABLE_BOOTSTRAP | Yes | `false` |
| SCOUT_ANTHROPIC_API_KEY | Yes | (set) |

### Deployment Verification Results

| Check | Result |
|---|---|
| Backend /health | `{"status":"ok"}` |
| Backend /ready | `{"status":"ready","ai_available":true,"meal_generation":true}` |
| Unauthenticated /api/auth/me | 401 (auth enforced) |
| Adult login (robertsandrewt@gmail.com) | Success (token + member returned) |
| Frontend loads (Vercel) | 200 OK |
| Frontend API_BASE_URL | Correct (scout-backend-production-9991.up.railway.app) |
| Bootstrap endpoint | Disabled (SCOUT_ENABLE_BOOTSTRAP=false) |

### Deployed Smoke Tests (Playwright)

**Auth tests (4/4 passed):**
- Adult can sign in
- Bad password shows error
- Sign out returns to login
- Invalid token clears to login

**Surface tests (5/5 passed):**
- Personal dashboard loads
- Meals This Week loads
- Grocery page loads
- Settings page loads
- Adult sees Accounts & Access

**Child tests:** Skipped (no child account in production yet; create via Settings > Accounts & Access)

### Issues Found and Fixed

| Issue | Fix |
|---|---|
| SCOUT_ENVIRONMENT not set in Railway | Set to `production` via `railway variable set` |
| SCOUT_AUTH_REQUIRED not set (defaulted false) | Set to `true` |
| SCOUT_ENABLE_BOOTSTRAP not set (defaulted true) | Set to `false` |

No code changes were needed. All issues were environment configuration.

### Final Launch Recommendation

**GO — Scout is live for private family use.**

- Backend: Railway (healthy, auth enforced)
- Frontend: Vercel (loads, correct API URL)
- Auth: Required, working, sessions functioning
- Bootstrap: Disabled, accounts exist
- AI: Available (API key set)
- 9/9 deployed smoke tests pass

---

## Sprint 1 Closeout (2026-04-13)

**Branch:** `feat/sprint1-verification-closeout`
**Target commit:** to be committed at end of this pass

### What landed

**Backend plumbing for structured confirmation + handoff**
- `backend/app/schemas/ai.py` — new `ConfirmToolPayload`, `HandoffPayload`,
  `PendingConfirmation`. Extended `ChatRequest.confirm_tool` and
  `ChatResponse.handoff` / `ChatResponse.pending_confirmation`.
- `backend/app/ai/orchestrator.py` — `chat()` now detects tool results
  carrying `confirmation_required=true` and surfaces them structurally
  (no second LLM round). Also detects `_handoff()`-shaped dicts and
  surfaces them on the response. New `confirm_tool` direct-execution
  path bypasses the LLM entirely and runs the tool with `confirmed=true`.
- `backend/app/routes/ai.py` — pass `confirm_tool` through; log
  `handoff` + `pending` flags on success.
- `backend/tests/test_ai_routes.py` — new `TestPendingConfirmationPlumbing`
  class. Two tests: scripted-provider test proving pending_confirmation
  propagates structurally, and a zero-provider-calls test proving the
  `confirm_tool` direct path never invokes the LLM.

**ScoutPanel UX hardening**
- `scout-ui/lib/api.ts` — new `fetchReady()`, extended `sendChatMessage()`
  to accept `confirmTool` via an options object (backwards compatible).
  New TypeScript types `AIHandoff`, `AIPendingConfirmation`,
  `AIChatResult`, `ReadyState`, `SendChatOptions`.
- `scout-ui/components/ScoutLauncher.tsx` — probes `/ready` on open,
  renders a disabled-state card when `ai_available=false`, renders a
  confirm/cancel card when `pending_confirmation` arrives, wires
  handoff cards cleanly. Confirmation tap re-invokes `/api/ai/chat`
  with `confirm_tool`.

**Global error boundary**
- `scout-ui/components/ErrorBoundary.tsx` — new React class component.
  Renders "Something went wrong — Reload" fallback + logs to
  `console.error("[Scout ErrorBoundary]", ...)`.
- `scout-ui/app/_layout.tsx` — wraps `AuthProvider + AppShell` in the
  boundary.

**Seed extension**
- `backend/seed_smoke.py` — adds a **draft** weekly meal plan for next
  week, a **pending** purchase request ("New soccer ball"), a chore
  template ("Feed the dog"), and today's `TaskInstance` for the seeded
  child. All idempotent.

**Smoke suite expansion (13 → ~25 Playwright tests)**
- `smoke-tests/tests/ai-panel.spec.ts` — extended to 3 tests: content
  assertion (response non-empty), disabled-state (via `page.route()`
  stub of `/ready`), child-surface (panel opens without crash).
- `smoke-tests/tests/write-paths.spec.ts` — **new file, 6 tests:**
  approve pending grocery, approve draft meal plan, run weekly payout,
  convert purchase request, child task completion, child meal-review
  submit.
- `smoke-tests/tests/meals-subpages.spec.ts` — **new file, 3 tests:**
  `this-week` renders seeded plan, `prep` loads, `reviews` loads.
- `smoke-tests/tests/dev-mode.spec.ts` — **new file, 1 test:** asserts
  DevToolsPanel ingestion buttons are absent (DEV_MODE gate verified).

**Dev-mode ingestion audit (backlog item 1.3)**
- Audited `scout-ui/lib/config.ts`: `DEV_MODE = !process.env.EXPO_PUBLIC_API_URL`,
  evaluated at compile time via Metro inlining. Any CI or Vercel build
  sets `EXPO_PUBLIC_API_URL`, so `DEV_MODE=false`, so
  `{DEV_MODE && <DevToolsPanel />}` short-circuits. Verified in source
  and backed by new Playwright assertion.

### Backlog status after Sprint 1 closeout

| Backlog # | Item | Status |
|---|---|---|
| 1.1 | Deployed AI-panel smoke against Railway + Vercel | **STILL OPEN** (blocked on operator access to deployed URLs + a deploy-aware smoke runner) |
| 1.2 | ScoutPanel disabled-state handling | **VERIFIED** (code + smoke) |
| 1.3 | Dev-mode ingestion button prod audit | **VERIFIED** (audit + smoke assertion) |
| 2.1 | Write-path E2E smoke suite | **PARTIAL** (6 tests landed; a few may skip with annotations when the UI does not surface the seeded draft plan; remains in Sprint 1 tail) |
| 2.2 | AI panel verification depth | **PARTIAL** (content + disabled + child surface landed; full tool round-trip and confirmation UI round-trip still open) |
| 2.3 | Confirmation-flow UI inside ScoutPanel | **IMPLEMENTED** (backend plumbing + frontend card + pytest coverage; browser round-trip test is backlog item) |
| 2.4 | Global frontend error boundary | **IMPLEMENTED** (no Playwright test yet — force-crash path is hard in Expo Router; manual verification documented) |
| 2.5 | Meals subpages smoke | **IMPLEMENTED** (3 new tests) |
| 17 | Investigate deployed AI smoke pass | **BLOCKED** (same as 1.1) |
| 18 | Investigate Railway logs for `ai_chat_*` | **BLOCKED** (no Railway log access from this environment) |
| 19 | Investigate audit rows since deploy | **BLOCKED** (no production Postgres access) |

### Items explicitly blocked on operator access

The following three investigations cannot be completed from the
environment that ran this Sprint 1 pass. They need to be performed by
an operator with the relevant credentials:

**1.1 + Investigation 17 — Run `ai-panel.spec.ts` against production**
```bash
# Operator checklist:
cd smoke-tests
SCOUT_WEB_URL=https://scout-ui-gamma.vercel.app \
SCOUT_API_URL=https://scout-backend-production-9991.up.railway.app \
npx playwright test tests/ai-panel.spec.ts --reporter=list

# Record the result (pass/fail + any error body) in this file under
# "Deployed Smoke Tests (Playwright)" → "AI tests".
```
Expected: the 3 AI panel tests pass. If any fail, capture the trace
archive and attach to a new GitHub issue referencing backlog #1.

**Investigation 18 — Confirm `ai_chat_*` logs in Railway**
```bash
# Operator checklist (from Railway CLI or dashboard):
railway logs --service scout-backend --tail 500 | grep ai_chat_

# Expected: at least one line each of ai_chat_start, ai_chat_success,
# with an X-Scout-Trace-Id matching the format "scout-<epoch>-<6chars>".
```

**Investigation 19 — Confirm `ai_tool_audit` rows since deploy**
```sql
-- Operator checklist (from Railway Postgres psql):
SELECT COUNT(*) FROM ai_tool_audit
WHERE created_at > '2026-04-12';

SELECT tool_name, status, COUNT(*)
FROM ai_tool_audit
WHERE created_at > '2026-04-12'
GROUP BY tool_name, status
ORDER BY COUNT(*) DESC;
```
Expected: at least one row. Zero rows means nobody has actually
invoked the AI path in production since the feature flag was enabled.

### Test runs in this pass

See "Test Output" section below for actual command output.

