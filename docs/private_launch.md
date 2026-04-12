# Scout Private Launch Runbook

## Required Production Environment Variables

| Variable | Required | Example |
|---|---|---|
| `SCOUT_DATABASE_URL` | Yes | `postgresql://scout:secret@db:5432/scout` |
| `SCOUT_ENVIRONMENT` | Yes | `production` |
| `SCOUT_AUTH_REQUIRED` | Yes | `true` |
| `SCOUT_CORS_ORIGINS` | Yes | `https://scout.yourfamily.com` |
| `SCOUT_ENABLE_BOOTSTRAP` | Set `false` after first account | `false` |
| `SCOUT_ANTHROPIC_API_KEY` | For AI features | `sk-ant-...` |

## Production Fail-Closed Rules

When `SCOUT_ENVIRONMENT=production`:
- `SCOUT_AUTH_REQUIRED` must be `true` or startup fails
- `SCOUT_CORS_ORIGINS` must include a non-localhost origin or startup fails
- `SCOUT_ENABLE_BOOTSTRAP` warns if still `true`

## How Active Family is Derived

1. User signs in with email + password
2. Backend creates session, returns bearer token
3. Frontend calls `GET /api/auth/me` with token
4. Response includes `family_id`, `member_id`, `role`, `family_name`
5. All subsequent API calls use the session-derived `family_id`
6. No hardcoded family ID in the frontend

## Bootstrap: First Account

### Step 1: Set env vars

```
SCOUT_ENABLE_BOOTSTRAP=true
SCOUT_AUTH_REQUIRED=false   # only during bootstrap
```

### Step 2: Seed family data

Ensure family members exist in the database (via seed SQL or migration).

### Step 3: Create first admin account

```bash
curl -X POST http://localhost:8000/api/auth/bootstrap \
  -H "Content-Type: application/json" \
  -d '{"email": "parent@family.com", "password": "your-secure-password"}'
```

Only works when zero accounts exist. Links to the first adult family member.

### Step 4: Switch to production

```
SCOUT_ENVIRONMENT=production
SCOUT_AUTH_REQUIRED=true
SCOUT_ENABLE_BOOTSTRAP=false
```

### Step 5: Create remaining accounts

Sign in, go to Settings > Accounts & Access. Adults create accounts for others.

## Creating Child Accounts

1. Sign in as adult
2. Settings > Accounts & Access
3. Find child with "No account" > Create Account
4. Share credentials

## Password Management

**Self-service:** Settings > Change Password (requires current password)

**Admin reset:** Settings > Accounts & Access > Reset Password (adults only, no current password needed)

## Session Management

**Own sessions:** Settings > Active Sessions > Sign Out Other Sessions

**Admin:** Settings > Accounts & Access > Revoke Sessions

## Auth-Required Behavior

When `SCOUT_AUTH_REQUIRED=true`:
- All family-scoped routes require Bearer token
- No legacy member_id fallback
- Login rate limit: 10 attempts per 5 minutes per email/IP
- Sessions expire after `SESSION_TTL_HOURS` (default 72)

## CORS

Set `SCOUT_CORS_ORIGINS` to your production frontend URL.
Multiple origins: comma-separated.
Production startup fails if only localhost origins are configured.

## Verifying Health

```bash
curl http://your-domain/health
# {"status": "ok"}

curl http://your-domain/ready
# {"status": "ready", "environment": "production", "auth_required": true, ...}
```

## Running Smoke Tests

```bash
# Start backend
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000

# Start frontend (web)
cd scout-ui && npx expo start --web

# Run smoke tests
cd smoke-tests && npx playwright test
```

Smoke tests require seeded test data and accounts. See `smoke-tests/README.md`.
