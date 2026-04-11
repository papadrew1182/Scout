# Scout Database

The database schema for the Scout family operations platform. Two migration phases: Foundation + Connectors, and Life Management.

## Schema

15 tables across three domains:

**Foundation** — families, family_members, user_accounts, sessions, role_tiers, role_tier_overrides

**Connectors** — connector_configs, connector_mappings

**Life Management** — routines, routine_steps, chore_templates, task_instances, task_instance_step_completions, daily_wins, allowance_ledger

`families` is the tenant boundary. All data scopes through it. `family_members` are people (adults and children) who may or may not have login credentials. `user_accounts` are authentication identities. `connector_mappings` is the only place external system IDs are stored. Life Management tables track routines, chores, task execution history, daily win scoring, and allowance payouts.

## Files

```
database/
  foundation.sql                          # Canonical Foundation DDL (locked, do not modify)
  migrations/
    001_foundation_connectors.sql         # Foundation + Connectors (transaction-wrapped)
    002_life_management.sql               # Life Management (transaction-wrapped)
  seeds/
    001_foundation_seed.sql               # 1 family, 5 members, 4 connectors
    002_life_management_seed.sql          # Routines, chores, 1 week of task history
  DEVELOPER_NOTES.md                      # Task generation, daily wins, payout logic
```

## Running migrations

Requires PostgreSQL 14+. Run in order:

```bash
psql -h <host> -U <user> -d <database> -f database/migrations/001_foundation_connectors.sql
psql -h <host> -U <user> -d <database> -f database/migrations/002_life_management.sql
```

Each migration is wrapped in `BEGIN`/`COMMIT`. If any statement fails, that migration rolls back entirely.

## Running seeds

Run after both migrations have been applied. Order matters:

```bash
psql -h <host> -U <user> -d <database> -f database/seeds/001_foundation_seed.sql
psql -h <host> -U <user> -d <database> -f database/seeds/002_life_management_seed.sql
```

Seeds use hardcoded UUIDs. To re-seed from scratch:

```bash
psql -h <host> -U <user> -d <database> -c "TRUNCATE families CASCADE;"
psql -h <host> -U <user> -d <database> -f database/seeds/001_foundation_seed.sql
psql -h <host> -U <user> -d <database> -f database/seeds/002_life_management_seed.sql
```

## Assumptions

- PostgreSQL 14+ (uses `gen_random_uuid()` from pgcrypto, partial unique indexes, jsonb, `EXTRACT(isodow ...)`).
- `updated_at` is enforced by database triggers, not application logic.
- `connector_mappings` has no FK to `connector_configs`. The relationship is intentionally logical, not referential.
- External system IDs never appear in domain tables. They go through `connector_mappings` exclusively.
- `family_id` is denormalized onto `task_instances`, `daily_wins`, and `allowance_ledger` for query performance. Write-path code must validate that `family_id` matches `family_members.family_id`.
- `task_instances` uses two nullable FK columns (`routine_id`, `chore_template_id`) with a CHECK constraint enforcing exactly one is set. This is not polymorphic — both are real FKs with referential integrity.
- `task_instance_step_completions` should only be created for routine-sourced task_instances. This is enforced at the application layer, not the database.
- `daily_wins` enforces Mon-Fri only via CHECK constraint. Weekend task_instances exist but do not generate daily_win rows.
- `allowance_ledger.week_start` is always a Monday, enforced via CHECK constraint.
- Both schemas are locked. Do not add tables or modify columns. Future changes go in new numbered migrations.
- Seed data is for local development only. Do not use in production.
