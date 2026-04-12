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
