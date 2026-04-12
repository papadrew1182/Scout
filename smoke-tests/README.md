# Scout Smoke Tests

Browser-based smoke tests using Playwright.

## Prerequisites

- Backend running on `localhost:8000` with migrated DB
- Frontend web on `localhost:8081` (`cd scout-ui && npx expo start --web`)
- Smoke data seeded: `cd backend && python seed_smoke.py`

## Setup

```bash
cd smoke-tests
npm install
npx playwright install chromium
```

## Run

```bash
npm test              # headless
npm run test:headed   # with browser visible
```

## Seeded accounts

| Role  | Email           | Password    |
|-------|-----------------|-------------|
| Adult | adult@test.com  | testpass123 |
| Child | child@test.com  | testpass123 |

## Environment variables

| Variable          | Default                | Description          |
|-------------------|------------------------|----------------------|
| SCOUT_WEB_URL     | http://localhost:8081   | Frontend URL         |
| SMOKE_ADULT_EMAIL | adult@test.com         | Adult test account   |
| SMOKE_CHILD_EMAIL | child@test.com         | Child test account   |
| SMOKE_PASSWORD    | testpass123            | Test account password|
