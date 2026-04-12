# Scout Private Launch Runbook

## Quick Start (Local)

```bash
# 1. Start Postgres (or use docker-compose)
docker-compose up postgres -d

# 2. Migrate
cd backend && python migrate.py

# 3. Seed smoke data (creates family + test accounts)
python seed_smoke.py

# 4. Start backend
python -m uvicorn app.main:app --port 8000 --reload

# 5. Start frontend
cd ../scout-ui && npx expo start --web

# 6. Sign in at http://localhost:8081
#    Adult: adult@test.com / testpass123
#    Child: child@test.com / testpass123
```

## Release Check

```bash
python scripts/release_check.py
```

Runs: backend tests, TypeScript check. Then follow printed instructions for smoke tests.

## Full Stack via Docker Compose

```bash
docker-compose up --build
# Backend: http://localhost:8000
# Frontend: http://localhost:3000
```

## Production Environment Variables

| Variable | Required | Example |
|---|---|---|
| `SCOUT_DATABASE_URL` | Yes | `postgresql://user:pass@host:5432/scout` |
| `SCOUT_AUTH_REQUIRED` | Yes (prod) | `true` |
| `SCOUT_CORS_ORIGINS` | Yes (prod) | `https://scout.yourfamily.com` |
| `SCOUT_ENABLE_BOOTSTRAP` | Disable after setup | `false` |
| `SCOUT_ANTHROPIC_API_KEY` | For AI features | `sk-ant-...` |
| `EXPO_PUBLIC_API_URL` | Frontend build | `https://api.yourfamily.com` |

## Bootstrap: First Account

1. Ensure `SCOUT_ENABLE_BOOTSTRAP=true`
2. Run migrations + seed (or just migrations if seeding manually)
3. Create first account:
   ```bash
   curl -X POST http://localhost:8000/api/auth/bootstrap \
     -H "Content-Type: application/json" \
     -d '{"email": "you@email.com", "password": "your-password"}'
   ```
   Only works when zero accounts exist.
4. Set `SCOUT_ENABLE_BOOTSTRAP=false` for production

## Bootstrap Safety

- Bootstrap endpoint only works when zero UserAccount rows exist
- Even with `SCOUT_ENABLE_BOOTSTRAP=true`, it returns 409 if accounts already exist
- Production startup warns if bootstrap is enabled

## Auth Behavior

When `SCOUT_AUTH_REQUIRED=true`:
- All family-scoped routes require Bearer token
- No legacy member_id fallback
- Login rate limiting: 10 attempts per 5 minutes per email/IP

## Active Family Derivation

1. User signs in with email + password
2. `GET /api/auth/me` returns `family_id`, `member_id`, `role`
3. Frontend uses session-derived family for all API calls
4. No hardcoded family ID

## Verify Health

```bash
curl http://your-domain/health     # {"status": "ok"}
curl http://your-domain/ready      # {"status": "ready", ...}
```

`/ready` reports: `auth_required`, `bootstrap_enabled`, `accounts_exist`, `ai_available`

## Running Smoke Tests

```bash
# After backend + frontend + seed are running:
cd smoke-tests
npm install && npx playwright install chromium
npm test
```

## CI

GitHub Actions runs automatically on push/PR to main:
- `backend-tests`: Python tests with Postgres
- `frontend-types`: TypeScript check
- `smoke-web`: Full stack smoke tests with Playwright

## Release Checklist

- [ ] Migrations applied
- [ ] Backend tests pass (`python -m pytest tests/ -v`)
- [ ] TypeScript clean (`cd scout-ui && npx tsc --noEmit`)
- [ ] `/health` returns ok
- [ ] `/ready` shows `accounts_exist: true`, `auth_required: true`
- [ ] Bootstrap disabled (`SCOUT_ENABLE_BOOTSTRAP=false`)
- [ ] CORS set to production frontend URL
- [ ] Adult can sign in and see dashboard
- [ ] Child can sign in and sees restricted view
- [ ] Smoke tests pass
