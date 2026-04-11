# Scout: Local Development Setup

## Prerequisites

- Python 3.12+
- PostgreSQL 14+
- pip

## 1. Install Python dependencies

```bash
cd backend
pip install -r requirements.txt
```

## 2. Environment variables

The backend reads settings from environment variables prefixed with `SCOUT_`.

| Variable | Default | Description |
|----------|---------|-------------|
| `SCOUT_DATABASE_URL` | `postgresql://scout:scout@localhost:5432/scout` | Main database connection string |
| `SCOUT_ECHO_SQL` | `false` | Log all SQL statements to stdout |

Set these in your shell or a `.env` file (pydantic-settings loads both).

```bash
export SCOUT_DATABASE_URL="postgresql://scout:scout@localhost:5432/scout"
```

## 3. PostgreSQL setup

Create two databases: `scout` (dev) and `scout_test` (tests).

```bash
psql -U postgres -c "CREATE USER scout WITH PASSWORD 'scout';"
psql -U postgres -c "CREATE DATABASE scout OWNER scout;"
psql -U postgres -c "CREATE DATABASE scout_test OWNER scout;"
```

## 4. Apply migrations

Run in order. Each migration is a single transaction.

```bash
psql -h localhost -U scout -d scout -f database/migrations/001_foundation_connectors.sql
psql -h localhost -U scout -d scout -f database/migrations/002_life_management.sql
```

For the test database:

```bash
psql -h localhost -U scout -d scout_test -f database/migrations/001_foundation_connectors.sql
psql -h localhost -U scout -d scout_test -f database/migrations/002_life_management.sql
```

## 5. Run seeds (dev database only)

Seeds insert hardcoded UUIDs. Run in order after migrations.

```bash
psql -h localhost -U scout -d scout -f database/seeds/001_foundation_seed.sql
psql -h localhost -U scout -d scout -f database/seeds/002_life_management_seed.sql
```

To re-seed from scratch:

```bash
psql -h localhost -U scout -d scout -c "TRUNCATE families CASCADE;"
psql -h localhost -U scout -d scout -f database/seeds/001_foundation_seed.sql
psql -h localhost -U scout -d scout -f database/seeds/002_life_management_seed.sql
```

Do not seed the test database. Tests manage their own data via transactional rollback.

## 6. Run tests

```bash
cd backend
pytest tests/ -v
```

Tests require the `scout_test` database with migrations applied (step 4). Each test runs in a transaction that rolls back automatically.

## 7. Start FastAPI locally

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs available at `http://localhost:8000/docs`.

## 8. Example API calls

These use the seeded family UUID `a1b2c3d4-0000-4000-8000-000000000001`. Replace with your own if not using seeds.

**List family members:**

```bash
curl http://localhost:8000/families/a1b2c3d4-0000-4000-8000-000000000001/members
```

**List routines for the family:**

```bash
curl http://localhost:8000/families/a1b2c3d4-0000-4000-8000-000000000001/routines
```

**Generate task instances for a date:**

```bash
curl -X POST "http://localhost:8000/families/a1b2c3d4-0000-4000-8000-000000000001/task-instances/generate?target_date=2026-04-06"
```

**Compute and materialize daily wins for a date:**

```bash
curl -X POST "http://localhost:8000/families/a1b2c3d4-0000-4000-8000-000000000001/daily-wins/compute?win_date=2026-03-30"
```

**Create weekly payout for Sadie (week of 2026-03-30):**

```bash
curl -X POST "http://localhost:8000/families/a1b2c3d4-0000-4000-8000-000000000001/allowance/weekly-payout?member_id=b1000000-0000-4000-8000-000000000003&baseline_cents=1200&week_start=2026-03-30"
```
