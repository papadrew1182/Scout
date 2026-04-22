# Scout Private Launch Runbook

## Quick Start (Local Dev)

```bash
# 1. Start Postgres (or use docker-compose)
docker-compose up postgres -d

# 2. Migrate + seed
cd backend
python migrate.py
python seed_smoke.py
# Seeded: adult@test.com / testpass123, child@test.com / testpass123

# 3. Start backend
python -m uvicorn app.main:app --port 8000 --reload

# 4. Start frontend (new terminal)
cd scout-ui && npx expo start --web

# 5. Sign in at http://localhost:8081
```

## Release Check

```bash
# Tests + TypeScript only (fast)
python scripts/release_check.py

# Full: tests + types + migrate + seed + start stack + Playwright smoke
python scripts/release_check.py --smoke
```

## Docker Compose

```bash
docker-compose up --build
# Postgres: localhost:5432
# Backend: localhost:8000
# Frontend: localhost:3000
```

Healthchecks: Postgres waits for pg_isready, backend waits for Postgres healthy, web waits for backend healthy.

## Production Environment Variables

| Variable | Required | Example |
|---|---|---|
| `SCOUT_DATABASE_URL` | Yes | `postgresql://user:pass@host:5432/scout` |
| `SCOUT_ENVIRONMENT` | Yes | `production` |
| `SCOUT_AUTH_REQUIRED` | Yes | `true` |
| `SCOUT_CORS_ORIGINS` | Yes | `https://scout.yourfamily.com` |
| `SCOUT_ENABLE_BOOTSTRAP` | Disable after setup | `false` |
| `SCOUT_ANTHROPIC_API_KEY` | For AI features | `sk-ant-...` |
| `SCOUT_SMOKE_ADULT_EMAIL` | Persistent smoke operator account | `smoke@scout.app` |
| `SCOUT_SMOKE_ADULT_PASSWORD` | Persistent smoke operator password | (random 43-char token) |
| `EXPO_PUBLIC_API_URL` | Frontend build | `https://api.yourfamily.com` |
| `PUSH_PROVIDER` | Phase 1 expansion | `expo` |
| `EXPO_PUSH_SECURITY_ENABLED` | Phase 1 expansion | `false` (true requires access token) |
| `EXPO_ACCESS_TOKEN` | Only when security enabled | token from Expo dashboard |
| `EXPO_PUBLIC_PUSH_PROVIDER` | Frontend, Phase 1 | `expo` |

## Push notifications (Sprint Expansion Phase 1) — LIVE

iOS push is live in production as of 2026-04-21, validated on physical
device. Scout delivers time-sensitive notifications through the Expo
Push Service, which fans out to APNs. The backend records one delivery
row per device attempt and polls Expo for receipts on the scheduler
tick.

### Setup (completed 2026-04-21)

All four steps below are done in production. Document retained so a
future new-environment bring-up has the procedure.

1. Register an Apple Developer bundle ID for Scout and upload the APNs
   Auth Key to the Expo project. Expo handles the handoff to APNs.
2. Run `eas init` inside `scout-ui/` to create the EAS project ID. Paste
   the generated ID into `scout-ui/app.json` under
   `expo.extra.eas.projectId`. Without it,
   `Notifications.getExpoPushTokenAsync` fails on EAS-built apps.
3. Set `PUSH_PROVIDER=expo` on the backend (Railway). Leave
   `EXPO_PUSH_SECURITY_ENABLED=false` unless you have enabled Expo's
   push-security flow; in that case also set `EXPO_ACCESS_TOKEN`.
4. Set `EXPO_PUBLIC_PUSH_PROVIDER=expo` on the frontend (Vercel).

### Operations

Rotation + incident procedure for APNs key, Expo access token, and EAS
project credentials is still TBD, tracked as item 8 on the gap list
(ops playbook work).

### Provider semantics

- A successful **ticket** from the Expo `/send` endpoint means Expo
  accepted the payload. The backend sets the delivery row to
  `provider_accepted` and stores `provider_ticket_id`.
- A successful **receipt** from `/getReceipts` (polled on the scheduler
  tick) means Expo handed the payload to APNs. The row moves to
  `provider_handoff_ok`.
- Neither guarantees the device displayed the notification. Physical-
  device validation is required for end-to-end confidence.

### DeviceNotRegistered handling

If Expo reports `DeviceNotRegistered` (either on the send ticket or on
the receipt), the backend deactivates `scout.push_devices.is_active`
for that token. Subsequent sends skip the stale device.

### Receipt polling

The APScheduler tick (every five minutes) polls pending receipts in
batches of up to `push_receipt_poll_batch` (default 1000). No separate
scheduler is introduced — receipt polling rides the existing tier-5
advisory-locked tick.

### AI tool integration

`send_notification_or_create_action` now delivers a real push when the
target member has at least one active device. If no active device exists
or every send attempt is rejected at provider submission, the tool
falls back to an Action Inbox row so the message is not lost. A
successful push does NOT create a duplicate Action Inbox row.

### Manual validation

Automated tests cover provider submission and receipt processing only.
Each push release must include a manual validation step: install the
Scout app on a physical iPhone, register the device from
`/settings/notifications`, send a test push, verify delivery on the
device, and confirm `tapped_at` populates when the notification is
tapped.

## Production Fail-Closed Rules

When `SCOUT_ENVIRONMENT=production`:
- `SCOUT_AUTH_REQUIRED` must be `true` (startup fails otherwise)
- `SCOUT_CORS_ORIGINS` must include non-localhost (startup fails otherwise)
- `SCOUT_ENABLE_BOOTSTRAP` warns if still `true`

## Bootstrap

1. `POST /api/auth/bootstrap` only works when zero accounts exist
2. Even with `SCOUT_ENABLE_BOOTSTRAP=true`, returns 409 if accounts exist
3. Production warns if bootstrap still enabled
4. After creating first account, set `SCOUT_ENABLE_BOOTSTRAP=false`

## Active Family Derivation

`GET /api/auth/me` returns `family_id`. Frontend derives all API URLs from this. No hardcoded FAMILY_ID.

## Verify Health

```bash
curl http://domain/health   # {"status":"ok"}
curl http://domain/ready    # {"status":"ready","environment":"production",...}
```

## CI

GitHub Actions runs on: `main`, `release-*`, `release/**`, PRs to main.

Jobs: `backend-tests`, `frontend-types`, `smoke-web` (full Playwright).

## Merge / Release Checklist

- [ ] `python -m pytest backend/tests/ -q` green (349 tests as of
      2026-04-13)
- [ ] `cd scout-ui && npx tsc --noEmit` clean
- [ ] `python scripts/release_check.py --smoke` passes
- [ ] CI green on branch
- [ ] `/ready` returns `status=ready`, `accounts_exist=true`,
      `ai_available=true`
- [ ] Adult sign-in works (meals, grocery, settings, inbox load)
- [ ] Child sign-in works (restricted view)
- [ ] ScoutPanel opens and streams a response on the personal surface
- [ ] Bootstrap disabled (`SCOUT_ENABLE_BOOTSTRAP=false`)
- [ ] `SCOUT_AUTH_REQUIRED=true` for production
- [ ] `SCOUT_CORS_ORIGINS` set to production frontend
- [ ] `SCOUT_ENVIRONMENT=production`
- [ ] `SCOUT_ANTHROPIC_API_KEY` set
- [ ] `SCOUT_SMOKE_ADULT_EMAIL` / `SCOUT_SMOKE_ADULT_PASSWORD` set for
      operator / CI smoke
- [ ] Only one Railway service in the Scout project (`scout-backend`);
      stale duplicate services removed

## Operator AI verification

After each deploy, an operator can re-verify the production AI path
end-to-end by following `docs/AI_OPERATOR_VERIFICATION.md`. The
standing credentials live in Railway env vars; no password needs to
leave the Railway vault.

## Production error reporting

Every JS crash on the frontend — `ErrorBoundary.componentDidCatch`,
unhandled promise rejections, and `window.onerror` events — POSTs to
`/api/client-errors`, which emits one structured `client_error` log
line per report. No external provider is wired up (Sentry etc.), on
purpose: Scout has one operator, and reusing Railway's log pipeline
keeps the on-call surface to one place.

### Watching for crashes

```bash
# Tail for new crashes
railway logs --service scout-backend | grep client_error

# Rollup across the latest deploy (uses jq)
railway logs --deployment | grep client_error | jq -s '
  group_by(.source) |
  map({source: .[0].source, count: length})
'
```

Each line carries `message`, `stack` (capped at 2 KB), `url`,
`user_agent`, `source` (`error_boundary` /
`unhandled_rejection` / `window_error` / `manual`), an optional
`release`, and — when the crashing session is signed in — the
actor's `family_id` + `member_id` for attribution.

### Swapping to an external provider

If crash volume or team size grows beyond one operator, replace the
body of `scout-ui/lib/errorReporter.ts#report()` with a call into
`@sentry/react` (or similar). The `ErrorBoundary` call site, the
`unhandledrejection` + `window.onerror` handlers, and the log-line
shape were all designed to survive that swap without touching
anything else.
