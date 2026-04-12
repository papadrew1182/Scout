# Scout Smoke Tests

Browser-based smoke tests using Playwright against the running web app.

## Prerequisites

1. Backend running on `localhost:8000`
2. Frontend web running on `localhost:8081` (`cd scout-ui && npx expo start --web`)
3. Test database seeded with family data
4. Test accounts created:
   - Adult: `adult@test.com` / `testpass123`
   - Child: `child@test.com` / `testpass123`

## Setup

```bash
cd smoke-tests
npm install
npx playwright install chromium
```

## Run

```bash
# Headless
npm test

# With browser visible
npm run test:headed
```

## Coverage

- Login: adult, child, bad password, sign out
- Session: invalid token clears to login
- Surfaces: personal, meals, grocery, settings (adult + child)
- Role: adult sees Accounts & Access, child does not
