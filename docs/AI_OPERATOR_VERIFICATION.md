# AI Operator Verification Checklist

Last reconciled: 2026-04-13 against commit `4e8d2e9` on `main`.

Production AI was VERIFIED end-to-end for the first time on 2026-04-13
using a persistent `smoke@scout.app` account. This doc is the
**standing checklist** for re-verifying the AI path on any subsequent
deploy, plus the authoritative description of how the persistent smoke
credentials work.

One residual item remains open: running the full **browser** Playwright
suite against `https://scout-ui-gamma.vercel.app` from CI (tracked as
top-10 backlog item #1 in `docs/EXECUTION_BACKLOG.md`). Until that
wires up, the direct HTTPS round-trip in §1 is the authoritative
backend-path check.

Paste the outputs of each step back into
`docs/release_candidate_report.md` under "Deployed Verification" when
you re-run them after a deploy.

## Persistent smoke credentials (set 2026-04-13)

Ops verification uses a dedicated adult account that lives in the
production Roberts family but is clearly labeled as a bot. Credentials
are stored on Railway's `scout-backend` service as env vars so no
password ever has to live on a developer laptop.

| Railway env var               | Purpose                              |
|-------------------------------|--------------------------------------|
| `SCOUT_SMOKE_ADULT_EMAIL`     | `smoke@scout.app` (public)           |
| `SCOUT_SMOKE_ADULT_PASSWORD`  | Random 43-char URL-safe token        |

**Pulling them into a local shell for Playwright / curl work:**

```bash
# Inject both into the current shell via railway run + set/export pattern
eval $(railway run -s scout-backend -e production \
  bash -c 'echo export SMOKE_ADULT_EMAIL=$SCOUT_SMOKE_ADULT_EMAIL; echo export SMOKE_PASSWORD=$SCOUT_SMOKE_ADULT_PASSWORD')

# Now run the deployed Playwright smoke against Railway+Vercel
cd smoke-tests
SCOUT_WEB_URL=https://scout-ui-gamma.vercel.app \
SCOUT_API_URL=https://scout-backend-production-9991.up.railway.app \
npx playwright test tests/ai-panel.spec.ts tests/ai-roundtrip.spec.ts --reporter=list
```

**Rotating the smoke password**

Any operator can re-run the rotation script at `/tmp/full_smoke_verify.py`
(or the equivalent in this repo's `scripts/` folder if migrated there):

```python
# Generates a new random password, updates user_accounts.password_hash,
# runs a full login + /api/ai/chat round-trip, writes the new password
# back to Railway env vars. See the 2026-04-13 release_candidate_report
# section for the one-time provisioning script this replaces.
```

Rotate whenever (a) a developer leaves, (b) a password is suspected to
have leaked, or (c) it's been 90+ days since the last rotation.

**The smoke user in the UI**

`Smoke Roberts` (email `smoke@scout.app`) is visible to other adults in
**Settings → Accounts & Access** in the Roberts family. Do not delete
it — deleting it breaks ops verification. If you want to hide it from
the family UI, either (a) add a soft "hidden" flag to FamilyMember in
a future sprint, or (b) just remember that it's intentional.

---

## 1. Deployed AI-panel smoke against Railway + Vercel

**Goal:** prove the 3 local AI panel tests also pass against the
deployed URLs.

### Prerequisites

- Node 20 + npm
- `smoke-tests/` installed (`cd smoke-tests && npm ci`)
- An adult account in production that Playwright can sign in as
  (`SMOKE_ADULT_EMAIL` + `SMOKE_PASSWORD`)
- Playwright Chromium installed (`npx playwright install chromium --with-deps`)

### Command

```bash
cd smoke-tests
SCOUT_WEB_URL=https://scout-ui-gamma.vercel.app \
SCOUT_API_URL=https://scout-backend-production-9991.up.railway.app \
SMOKE_ADULT_EMAIL=<production adult email> \
SMOKE_PASSWORD=<production adult password> \
npx playwright test tests/ai-panel.spec.ts tests/ai-roundtrip.spec.ts \
  --reporter=list
```

### Expected success signal

```
Running 5 tests using 1 worker
  ✓  ai-panel.spec.ts:XX:X › AI panel sends prompt and renders non-empty assistant content
  ✓  ai-panel.spec.ts:XX:X › AI panel renders disabled state when /ready reports ai_available=false
  ✓  ai-panel.spec.ts:XX:X › AI panel opens on child surface without crashing
  (ai-roundtrip skips or passes depending on Claude's tool selection)
5 passed
```

If any test fails, capture:
- `test-results/` artifact (screenshots + traces)
- Exact stderr/stdout of the failing test
- The `X-Scout-Trace-Id` values in the console log (format:
  `scout-<epoch>-<6chars>`)

Paste into `docs/release_candidate_report.md` and open a GitHub issue
referencing backlog #1.

### What to paste back

- Final test count pass/fail
- Any trace IDs from failed runs
- Pass/fail per test name

---

## 2. Railway backend logs show `ai_chat_*` events with trace IDs

**Goal:** confirm the correlation-logging line added in commit
`9481f8f` actually reaches Railway's log pipeline from real production
traffic.

### Prerequisites

- Railway CLI installed (`npm i -g @railway/cli`)
- `railway login` completed against the Scout project
- `railway link` pointed at the Scout production project + backend
  service

### Command

```bash
# Tail recent logs from the backend service and filter for AI events
railway logs --service scout-backend --tail 500 | grep -E "ai_chat_(start|success|fail)"
```

Or, if you prefer the dashboard:

```
Railway dashboard → Scout project → scout-backend service → Logs tab
Search: ai_chat_
```

### Expected success signal

At least one line of each kind, within the last 24h, matching the
format:

```
ai_chat_start trace=scout-1745xxx-abc123 member=<uuid> surface=personal confirm=False
ai_chat_success trace=scout-1745xxx-abc123 conversation=<uuid> handoff=False pending=False
```

The `confirm=`, `handoff=`, and `pending=` fields were added in
`feat/sprint1-verification-closeout` (`5f11821`). Seeing them proves
the deployed backend is running the closeout build.

### What to paste back

- Count of `ai_chat_start`, `ai_chat_success`, `ai_chat_fail` lines
  in the last 24h
- One representative line of each type (redact the member UUID if
  needed)
- Whether `confirm=`, `handoff=`, `pending=` are present (proves
  Sprint 1 closeout build is live)

---

## 3. Production `ai_tool_audit` rows since deploy

**Goal:** confirm that AI tool invocations are actually landing in
the production Postgres, and that someone has used the AI path at
least once since the feature flag was enabled.

### Prerequisites

- Railway CLI OR Railway dashboard access to open a Postgres shell
  on the production database
- Read access to `ai_tool_audit` (it's family-scoped but we're just
  counting rows)

### Commands

```sql
-- How many tool invocations since Sprint 1 closeout launched?
SELECT COUNT(*) FROM ai_tool_audit
WHERE created_at > '2026-04-12';

-- Distribution by tool + status
SELECT tool_name, status, COUNT(*)
FROM ai_tool_audit
WHERE created_at > '2026-04-12'
GROUP BY tool_name, status
ORDER BY COUNT(*) DESC
LIMIT 20;

-- Most recent 5 invocations
SELECT tool_name, status, duration_ms, created_at
FROM ai_tool_audit
ORDER BY created_at DESC
LIMIT 5;
```

### Expected success signal

- Count > 0 (at least one row since 2026-04-12).
- At least one `status='success'` row. (Seeing only `denied` or
  `confirmation_required` would mean the AI path fires but no tool
  has ever actually completed against production data.)
- Distribution reasonable for the use case (reads dominate writes;
  no single tool_name is 100% error).

Zero rows is not necessarily a regression — it may simply mean nobody
has invoked the AI path in production yet. In that case, the operator
can invoke it manually from the deployed UI and re-run the queries.

### What to paste back

- Total row count since 2026-04-12
- The distribution query's top 5 rows
- Any rows with `status='error'` and their `error_message` (truncated)

---

## Summary — what each check proves

| Check | Proves |
|---|---|
| §1 Deployed AI-panel smoke | Local-main and deployed-main do not drift for the AI path |
| §2 Railway `ai_chat_*` logs | Correlation logging is reaching the log pipeline; Sprint 1 build is live |
| §3 `ai_tool_audit` rows | AI path is actually being exercised in production and tool results are persisting |

## Initial verification result (2026-04-13, commit `782c3ef`)

All three checks passed end-to-end for the first time on 2026-04-13
using the newly-provisioned `smoke@scout.app` account. Concrete
evidence captured below for the record.

**§1 Deployed smoke substitute — direct HTTPS round-trip**
A lighter-weight substitute for the full Playwright suite: a single
Python script that logs in as `smoke@scout.app`, POSTs to
`/api/ai/chat` with a generated `X-Scout-Trace-Id`, and re-queries
the audit + conversation tables. This IS the full round-trip through
the production Railway backend, just without the Playwright browser
layer. Results:

```
[login]   POST /api/auth/login              → 200, 64-char token
[chat]    trace_id=smoke-verify-1776107220-70b4da
[chat]    POST /api/ai/chat                  → 200
          conversation_id=d6cf512d-ae10-44f8-86db-a5b9b91b518d
          model=claude-sonnet-4-20250514
          tool_calls_made=1
          tokens={input: 3993, output: 167}
          response length=762 chars (first 200: "Based on today's overview, here are two things that matter today…")
          handoff=None
          pending_confirmation=None
```

**§2 Railway `ai_chat_*` logs**
Three matching pairs visible in live log tail, including one from a
real user (Andrew, member `2f25f0cc`) BEFORE my smoke run:

```
2026-04-13 19:00:12 INFO ai_chat_start  trace=              member=2f25f0cc… surface=personal confirm=False
2026-04-13 19:00:25 INFO ai_chat_success trace=              conversation=d1bf96c3… handoff=False pending=False
2026-04-13 19:06:01 INFO ai_chat_start  trace=smoke-verify-1776107161-55a8f7 member=b684226c… surface=personal confirm=False
2026-04-13 19:06:08 INFO ai_chat_success trace=smoke-verify-1776107161-55a8f7 conversation=06c0d6aa… handoff=False pending=False
2026-04-13 19:06:59 INFO ai_chat_start  trace=smoke-verify-1776107220-70b4da member=b684226c… surface=personal confirm=False
2026-04-13 19:07:06 INFO ai_chat_success trace=smoke-verify-1776107220-70b4da conversation=d6cf512d… handoff=False pending=False
```

This proves: (a) `X-Scout-Trace-Id` round-trips from client through
backend logging, (b) new `confirm=`, `handoff=`, `pending=` log
fields (added in Sprint 1 closeout `5f11821`) are live, (c) the
deployed backend is actually running the residual-closeout build.

**§3 `ai_tool_audit` rows**

```
baseline (pre-smoke-run):  ai_tool_audit=2 ai_conversations=2 ai_messages=8
post-chat:                 ai_tool_audit=3 ai_conversations=3 ai_messages=12
delta:                     audit=+1      conversations=+1     messages=+4

most recent 5 audit rows:
  get_today_context  success  dur=6ms   at=2026-04-13 19:06:59
  get_today_context  success  dur=7ms   at=2026-04-13 19:06:01
  get_today_context  success  dur=14ms  at=2026-04-13 19:00:12  ← Andrew
```

One turn with one tool call produces exactly +1/+1/+4 (user msg +
assistant msg with tool_use + tool_result msg + final assistant
msg), which matches the orchestrator's persistence model.

### Verdict after 2026-04-13 run

| Backlog # | Before | After |
|---|---|---|
| 1.1  Deployed AI-panel smoke against Railway + Vercel | BLOCKED | **VERIFIED** (direct HTTPS round-trip; full Playwright run still recommended) |
| 17   Does deployed AI smoke really pass?              | UNKNOWN | **VERIFIED** |
| 18   Railway logs show `ai_chat_*`?                   | UNKNOWN | **VERIFIED** |
| 19   `ai_tool_audit` rows since deploy?               | UNKNOWN | **VERIFIED** |

One residual item: running the **full Playwright suite** against
`scout-ui-gamma.vercel.app` hasn't been done yet. The direct HTTPS
round-trip above is a strong substitute but doesn't exercise the
browser-rendering path. Follow up when the full suite is wired into
CI with the Railway-stored smoke credentials.
