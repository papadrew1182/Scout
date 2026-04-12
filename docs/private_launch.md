# Scout Private Launch Runbook

## Required Environment Variables

### Critical (must be set)

| Variable | Description | Example |
|---|---|---|
| `SCOUT_DATABASE_URL` | PostgreSQL connection string | `postgresql://scout:secret@db:5432/scout` |
| `SCOUT_AUTH_REQUIRED` | Enable mandatory auth | `true` |
| `SCOUT_CORS_ORIGINS` | Allowed frontend origins (comma-separated) | `https://scout.yourfamily.com` |
| `SCOUT_ENABLE_BOOTSTRAP` | Allow first-account creation (disable after setup) | `false` |

### Optional

| Variable | Default | Description |
|---|---|---|
| `SCOUT_ANTHROPIC_API_KEY` | (empty) | Enables AI features |
| `SCOUT_ENABLE_AI` | `true` | Master AI toggle |
| `SCOUT_ENABLE_MEAL_GENERATION` | `true` | Meal plan generation toggle |
| `SCOUT_SESSION_TTL_HOURS` | `72` | Session expiry in hours |

## Bootstrap: First Account

### Step 1: Enable bootstrap

Set `SCOUT_ENABLE_BOOTSTRAP=true` before first startup.

### Step 2: Seed family data

Ensure family members exist in the database (via seed SQL or migration).

### Step 3: Create first admin account

```bash
curl -X POST http://localhost:8000/api/auth/bootstrap \
  -H "Content-Type: application/json" \
  -d '{"email": "parent@family.com", "password": "your-secure-password"}'
```

This creates an account linked to the first adult family member.
Only works when zero accounts exist.

### Step 4: Disable bootstrap

Set `SCOUT_ENABLE_BOOTSTRAP=false` and restart.

### Step 5: Create remaining accounts

Sign in at the app, go to Settings > Accounts & Access.
Adults can create accounts for other family members from there.

## Creating Child Accounts

1. Sign in as an adult
2. Go to Settings > Accounts & Access
3. Find the child member with "No account"
4. Click "Create Account"
5. Enter email and password
6. Share credentials with the child

## Resetting a Password

### Self-service

Settings > My Account > Change Password. Requires current password.

### Admin reset

Settings > Accounts & Access > find the member > Reset Password.
Sets a new password directly. Revokes all their sessions.

## Revoking Sessions

### Own sessions

Settings > My Account > Sign Out Other Sessions.

### Admin

Settings > Accounts & Access > find the member > Revoke Sessions.

## Verifying Health

```bash
# App is running
curl http://your-domain/health
# {"status": "ok"}

# App is ready (DB connected, config loaded)
curl http://your-domain/ready
# {"status": "ready", "ai_available": true, "meal_generation": true}
```

## Production Auth Behavior

When `SCOUT_AUTH_REQUIRED=true`:
- All family-scoped routes require a valid Bearer token
- No legacy `member_id` query-param fallback
- Login rate limiting: 10 attempts per 5 minutes per email/IP
- Sessions expire after `SESSION_TTL_HOURS` (default 72)

## CORS

Set `SCOUT_CORS_ORIGINS` to your production frontend URL.
Multiple origins can be comma-separated.
localhost origins are only safe in dev mode.
