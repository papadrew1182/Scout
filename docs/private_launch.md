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
