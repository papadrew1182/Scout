# AI Operator Verification Checklist

Last built: 2026-04-13. Maintained by `docs/EXECUTION_BACKLOG.md` items
1.1, 17, 18, 19.

Three Sprint 1 closeout items could not be completed from a developer
workstation because they need credentialed access to Railway, Vercel,
and the production Postgres. This doc is the exact checklist to hand
to whoever has that access. The goal is for each section to produce
either a green "VERIFIED" or a specific failure that becomes a
follow-up ticket.

Paste the outputs of each step back into
`docs/release_candidate_report.md` under "Deployed Verification" when
you run them.

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

All three together upgrade backlog item 1.1 from **BLOCKED** to
**VERIFIED**. Any of them failing means there is a real regression
and a new GitHub issue should be opened.
