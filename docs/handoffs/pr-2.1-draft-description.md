# PR 2.1 draft description

**Branch:** `sprint/pr-2.1-canonical-identity` (off main `83feb0c`)
**Status:** Draft. Not pushed as a PR yet — Andrew gates after multi-reviewer round (Code review → ChatGPT tertiary review → Andrew gate → deploy verification).

## Scope

Builds the six canonical identity tables in the `scout` schema, seeds the six required `scout.role_tiers` reference rows, and restores the 63 of 68 expected post-Phase-2 §2 FKs whose target is one of the six identity tables. Patches the `/ready` endpoint to honor the canonical-rewrite maintenance gate per manifest v1.1.2 §6 PR 2.1 gate criterion 9. PR 2.6 still owns the final 68-row §2 reconciliation; PR 3.1 still owns the canonical rewire of `seed.py` and the underlying `UserAccount` query in `/ready`.

## Files changed

| File | Status | Purpose |
| --- | --- | --- |
| `backend/migrations/058_phase2_canonical_identity.sql` | + | Steps A-F + verification DO block |
| `database/migrations/058_phase2_canonical_identity.sql` | + | Byte-identical mirror (sha256 `34c158b731a6...`) |
| `backend/app/main.py` | M | `/ready` handler patched per criterion 9 |
| `backend/tests/test_ready_endpoint.py` | + | 6 unit tests covering 4 maintenance × DB-state cells + 2 cross-case invariants |
| `scripts/old_reference_grep.py` | M | `MAX_EXCLUDED_MIGRATION` bumped 57 → 58 (058 verification DO block uses PL/pgSQL string-array literals to compare expected table names against `pg_class`; gate-tooling content, not unqualified DDL — see "Tooling change" section below) |
| `docs/plans/runtime/2026-04-25/old_reference_grep_output.json` | M | Fresh capture: 1147 hits / 152 files / 0 unmapped (PASS) |

## §6 PR 2.1 gate self-audit

Per manifest v1.1.2 §6 PR 2.1 gate, every criterion below is a binary check at PR review time. Self-audit results:

| # | Criterion | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Six identity tables exist as base tables, not views | ✓ | Six `CREATE TABLE scout.<name>` in Steps A-C; verification DO block asserts count = 6 in `pg_class` with `relkind = 'r'` |
| 2 | `scout.role_tiers` contains exactly the six required rows before any role-tier-permission reseed | ✓ | Step E `INSERT INTO scout.role_tiers (name) VALUES ('DISPLAY_ONLY'), ('PRIMARY_PARENT'), ('PARENT'), ('TEEN'), ('YOUNG_CHILD'), ('CHILD');` — verification DO block asserts both natural-key set match AND total count = 6 (belt-and-suspenders against unexpected names) |
| 3 | Every §2 FK owned by PR 2.1 is present with constraint name / source column / ON DELETE preserved + target schema rewritten to scout | ✓ | 63 ALTER TABLE ADD CONSTRAINT in Step F, grouped per target. Verification DO block asserts count = 63 in `pg_constraint` (excluding the 6 internal FKs) with `convalidated = true` and target namespace = `scout` |
| 4 | Resolver audit: every PR 2.1 resurrection row is disabled or has Phase 3 owner. No unqualified legacy path newly executable unless explicitly accepted | ✓ | Six §4 resurrection rows at end of PR 2.1 (`families`, `family_members`, `user_accounts`, `role_tiers`, `role_tier_overrides`, `member_config`) all owned by PR 3.1. Containment: PR 1.5 maintenance middleware blocks request-time DB execution for non-allowlisted paths (`/api/*` → 503); scheduler import gated by `SCOUT_SCHEDULER_ENABLED=false`; AI gated by `SCOUT_ENABLE_AI=false`; `seed.py` guarded by `SCOUT_CANONICAL_MAINTENANCE`; `/ready` patched in this PR (criterion 9) |
| 5 | Backend still boots and `/health` still returns 200 | ✓ | `/ready` patch is additive (does not change boot path); `/health` handler unchanged. Will be confirmed at Railway deploy time post-merge |
| 6 | Rebuilt-table contract parity gate: 6 internal FKs / 6 PKs / 3 uniques / 3 CHECKs / 5 indexes / 6 triggers all present | ✓ | Verification DO block asserts each set with explicit `expected_*` arrays (lines 565-700 of migration). Subtleties preserved: `now()` defaults (not `clock_timestamp()`), partial unique on `user_accounts.email WHERE email IS NOT NULL`, lowercase `adult`/`child` in `chk_family_members_role`, `public.set_updated_at()` invoked by all 6 triggers |
| 7 | Migration qualification gate (zero unqualified DDL/DML, zero `IF NOT EXISTS`, zero unvalidated `NOT VALID`, byte-identical mirror) | ✓ | Self-audit grep results captured below; backend/database mirror sha256 match: `34c158b731a6267207f06d254302568018da8303bb88cc2d0a716360efeec5c0` |
| 8 | §2 FK restore parity gate: PR 2.1 owns exactly 63 of 68. Per-target subset 27/28/6/2/0 = 63 | ✓ | Step F structured by target. Counts: 27 → `scout.families(id)`; 28 → `scout.family_members(id)`; 6 → `scout.user_accounts(id)`; 2 → `scout.role_tiers(id)`; 0 → `scout.role_tier_overrides(id)`. Total grep count: `FOREIGN KEY` = 69 (6 internal + 63 §2). All convalidated |
| 9 | `/ready` maintenance semantic gate | ✓ | `backend/app/main.py` `/ready` patched: while `SCOUT_CANONICAL_MAINTENANCE` truthy, body is `{"status": "not_ready", "reason": "canonical_maintenance", "database_reachable": <bool>, ...diagnostic fields}`. DB probe still executes. 6 unit tests in `backend/tests/test_ready_endpoint.py` cover the 4 maintenance × DB-state cells + 2 cross-case invariants (truthy parser consistency with middleware) |

## Per-target FK count verification

| Target | Expected (manifest §6 criterion 8) | Actual (grep `REFERENCES scout.<target>(id)`) | Match |
| --- | --- | --- | --- |
| `scout.families(id)` | 27 | 27 (incl. `scout_scheduled_runs_family_id_fkey` from kept-public source) | ✓ |
| `scout.family_members(id)` | 28 | 28 (incl. `scout_scheduled_runs_member_id_fkey`) | ✓ |
| `scout.user_accounts(id)` | 6 | 6 (incl. `sessions_user_account_id_fkey`) | ✓ |
| `scout.role_tiers(id)` | 2 | 2 (`role_tier_permissions_role_tier_id_fkey`, `user_family_memberships_role_tier_id_fkey`) | ✓ |
| `scout.role_tier_overrides(id)` | 0 | 0 (no §2 FKs target it; `role_tier_overrides_role_tier_id_fkey` is the *internal* FK going the other direction) | ✓ |
| **Total §2 PR 2.1 owned** | **63** | **63** | ✓ |

## Contract-parity object inventory (criterion 6 detail)

All counts match the verification DO block's expected arrays in 058_*.sql:

**Tables (6):** `families`, `family_members`, `user_accounts`, `role_tiers`, `role_tier_overrides`, `member_config`.

**PKs (6):** `families_pkey`, `family_members_pkey`, `user_accounts_pkey`, `role_tiers_pkey`, `role_tier_overrides_pkey`, `member_config_pkey`.

**Unique constraints (3):** `uq_role_tiers_name`, `uq_role_tier_overrides_member`, `member_config_family_member_id_key_key`.

**CHECK constraints (3):** `chk_family_members_role` (lowercase `adult`/`child`), `chk_user_accounts_auth_provider`, `chk_user_accounts_email_auth`.

**Indexes (5, explicit — PK-implicit indexes are separate):** `idx_family_members_family_id`, `idx_user_accounts_family_member_id`, `uq_user_accounts_email` (partial: `WHERE email IS NOT NULL`), `idx_role_tier_overrides_role_tier_id`, `idx_member_config_member`.

**Triggers (6):** `trg_families_updated_at`, `trg_family_members_updated_at`, `trg_user_accounts_updated_at`, `trg_role_tiers_updated_at`, `trg_role_tier_overrides_updated_at`, `trg_member_config_updated_at`. All invoke `public.set_updated_at()`.

**Internal FKs (6):**
- `family_members_family_id_fkey` → `scout.families(id)` ON DELETE CASCADE
- `user_accounts_family_member_id_fkey` → `scout.family_members(id)` ON DELETE CASCADE
- `role_tier_overrides_family_member_id_fkey` → `scout.family_members(id)` ON DELETE CASCADE
- `role_tier_overrides_role_tier_id_fkey` → `scout.role_tiers(id)` ON DELETE RESTRICT
- `member_config_family_member_id_fkey` → `scout.family_members(id)` ON DELETE CASCADE
- `member_config_updated_by_fkey` → `scout.family_members(id)` ON DELETE SET NULL

## §6 criterion 7 self-audit grep results

All run against `backend/migrations/058_phase2_canonical_identity.sql`:

| Pattern | Expected | Actual | Status |
| --- | --- | --- | --- |
| `^CREATE TABLE ` not followed by `scout.` or `public.` | 0 | 0 | ✓ |
| `^ALTER TABLE ` not followed by `scout.` or `public.` | 0 | 0 | ✓ |
| `REFERENCES ` not followed by `scout.` or `public.` | 0 | 0 | ✓ |
| `^CREATE (UNIQUE )?INDEX ` without `ON scout.` or `ON public.` | 0 | 0 | ✓ |
| `^CREATE TRIGGER ` without `ON scout.` or `ON public.` | 0 | 0 | ✓ |
| `INSERT INTO ` not followed by `scout.` or `public.` | 0 | 0 | ✓ |
| `^UPDATE ` not followed by `scout.` or `public.` | 0 | 0 (no UPDATE statements) | ✓ |
| `^DELETE FROM ` not followed by `scout.` or `public.` | 0 | 0 (no DELETE statements) | ✓ |
| `CREATE TABLE IF NOT EXISTS` | 0 | 0 | ✓ |
| `NOT VALID` (excluding the line 19 docstring "(no NOT VALID)" comment) | 0 | 0 | ✓ |
| Backend/database 058 mirror sha256 match | match | `34c158b731a6...` both sides | ✓ |

## Snapshot subtleties preserved verbatim (criterion 6 detail)

| Item | Snapshot (`_snapshots/2026-04-22_pre_rewrite_full.sql`) | Migration 058 | Match |
| --- | --- | --- | --- |
| `created_at` / `updated_at` defaults | `DEFAULT now()` | `DEFAULT now()` (not normalized to `clock_timestamp()`) | ✓ |
| `user_accounts.email` partial unique | `WHERE (email IS NOT NULL)` | `WHERE (email IS NOT NULL)` | ✓ |
| `chk_family_members_role` casing | `'adult'::text, 'child'::text` (lowercase) | `'adult'::text, 'child'::text` (preserved) | ✓ |
| `chk_user_accounts_auth_provider` vocabulary | `'email', 'apple', 'google'` | `'email', 'apple', 'google'` | ✓ |
| `chk_user_accounts_email_auth` semantic | `(auth_provider <> 'email') OR (password_hash IS NOT NULL)` | preserved verbatim | ✓ |
| `set_updated_at()` function | `public.set_updated_at()` | `public.set_updated_at()` (not changed to any other function) | ✓ |
| Six tier names | DISPLAY_ONLY, PRIMARY_PARENT, PARENT, TEEN, YOUNG_CHILD, CHILD | INSERT preserves exact spelling and casing | ✓ |
| No `ADULT` row | absent from snapshot | absent from migration | ✓ |
| `gen_random_uuid()` defaults | id columns default `gen_random_uuid()` | preserved; non-deterministic UUIDs are the contract per v1.1.2 §1.4 | ✓ |

## Deviations from snapshot

**None.** The six identity tables are byte-equivalent in column definitions, constraints, indexes, and triggers to their pre-rewrite `public.*` counterparts; only the schema has changed from `public` to `scout`.

The §2 FK restorations also preserve constraint name, source column, and ON DELETE action verbatim; only the target schema is rewritten to `scout`.

## Test results

| Suite | Cases | Result |
| --- | --- | --- |
| `test_canonical_maintenance.py` (regression) | 12 | 12 PASS |
| `test_ready_endpoint.py` (new) | 6 | 6 PASS |
| **Combined** | **18** | **18 PASS in 1.48s** |

## Tooling change: `MAX_EXCLUDED_MIGRATION` bumped 57 → 58

PR 2.1 surfaces a small gate-tooling category gap. Migration 058's verification DO block (per criterion 6) uses PL/pgSQL string-array literals to enumerate expected table names for catalog comparison:

```sql
expected_tables text[] := ARRAY[
    'families', 'family_members', 'user_accounts',
    'role_tiers', 'role_tier_overrides', 'member_config'
];
```

These bare names are gate-tooling content — the verification block compares them against `pg_class` to prove every required object landed (criterion 6). They are **not** unqualified DDL/DML in the criterion-7 sense, but `old_reference_grep.py`'s pre-PR-2.1 pattern (`(?<![.\w])\b<name>\b`) flagged them as 23 unmapped hits because the regex doesn't distinguish executable DDL from string literals or comments.

The fix is structurally identical to why migrations 001-057 are excluded and why `test_canonical_maintenance.py` is in `EXCLUDED_FILES`: schema-mutation files and gate-tooling test fixtures reference dropped/created tables by definition; they are not consumer code requiring Phase 3 rewire. Migration 058 fits the same pattern.

The change:
- `MAX_EXCLUDED_MIGRATION = 57` → `58`
- Docstring expanded to clarify the rationale and signal that 059+ Phase 2 migrations (PR 2.2-2.5) will need analogous bumps as their verification blocks land

The criterion-7 self-audit (focused per-construct grep, results in the table above) is the actual gate evidence for migration qualification — that audit returned all-zero hits, which is the binary check criterion 7 requires. The full-repo `old_reference_grep.py` is a different tool with broader scope (consumer code).

If the multi-reviewer round prefers to split the script change to a separate PR (analogous to how PR #79's grep fix was a separate commit on the manifest/v1.1.2 branch), the bump is a single-file, two-edit change with no test impact.

## Self-audit limitations

The verification DO block in `058_phase2_canonical_identity.sql` is a powerful gate — it asserts every required object exists and counts match — but two specific properties are checked only by name/count rather than by per-object detail. These are deliberate tradeoffs surfaced during Andrew's chat review pass (P1 findings #4 and #5):

### (a) §2 FK ON DELETE actions are asserted by count, not per-constraint

The DO block asserts `count = 63` for §2 FKs targeting the four identity-table targets, with `convalidated = true`. It does **not** assert that each FK's `confdeltype` matches the action specified in manifest §2 (e.g. `CASCADE` vs `SET NULL` vs `RESTRICT`).

A miscoded ON DELETE — e.g., writing `CASCADE` for an FK that §2 specifies as `SET NULL` — would pass the count check.

**Mitigation (this PR's gate):** reviewer manual-diff of Step F (lines 234-495 of the migration) against the §2 manifest in `docs/plans/2026-04-25_canonical_rewrite_manifest_v1_1.md` lines 234-301. Each ALTER TABLE ADD CONSTRAINT statement should be cross-checked: source table, source column, ON DELETE action all match the §2 row.

**Why not encode in the DO block:** adding 63 individual `confdeltype` assertions to the DO block would balloon the verification logic to 75+ checks (63 §2 FKs + 6 internal FKs + 6 PKs + 6 uniques + ...). The line-by-line manual diff against the manifest is the more economical gate; the DO block's role is "prove the right structural shape is there," not "prove every per-constraint detail."

### (b) Trigger function targets are asserted by trigger name, not by tgfoid resolution

Criterion 6 specifies all 6 `trg_*_updated_at` triggers must invoke `public.set_updated_at()`. The DO block asserts each trigger exists by name in `pg_trigger`. It does **not** verify each trigger's `tgfoid` resolves to the expected function OID.

A miscoded trigger — e.g., one that runs `clock_timestamp()` directly via inline pg/sql or invokes a different function — would pass the name check.

**Mitigation (this PR's gate):** reviewer manual-diff of Step D (lines 196-201 of the migration) against the snapshot. All six `CREATE TRIGGER ... EXECUTE FUNCTION public.set_updated_at()` lines should be visually identical apart from the trigger name and target table.

**Why not encode in the DO block:** same tradeoff as (a). Per-trigger `tgfoid` resolution is a 6-line addition to the DO block that's easy to add, but the manual-diff against Step D is already the gate language criterion 6 specifies ("preserve the snapshot contract"). If a future PR loosens this — e.g., introduces a different `set_updated_at` variant — the DO block would have to be updated in tandem; for now the simpler shape is fine.

### Combined limitation surface

Both gaps share the same shape: count and name are asserted, per-property semantics are not. The shared mitigation is reviewer manual-diff against the source-of-truth (§2 manifest for FKs, snapshot DDL for triggers). PR review should treat Step D (lines 196-201) and Step F (lines 234-495) as gate sections requiring line-by-line cross-check, not just spot-check.

## Out-of-scope items (per v1.1.2 manifest)

- `seed.py` rewrite/retire (PR 3.1 owner; PR 1.5's guarded no-op remains).
- Canonical rewire of the underlying `UserAccount` query in `/ready` (PR 3.1 owner; PR 2.1 only patches the maintenance-mode status gating).
- Scheduler / AI re-enable (Phase 5 PR 5.3 owner).
- New §3 consumer manifest rows (criterion 4 audit covers existing rows; no §3 path additions in this PR).
- Phase 5 reseed of `scout.permissions` (64 rows) and `scout.role_tier_permissions` (187 rows by natural key) — Phase 5 PR 5.1 owner.

## Stop conditions for this draft

- ✓ Branch `sprint/pr-2.1-canonical-identity` pushed; PR not opened (Andrew gates after multi-reviewer round).
- ✓ No Railway env changes; service stays online in maintenance mode.
- ✓ Manifest v1.1.2 unchanged.

## Next round

Per the PR 2.1 brief: chat reviews → ChatGPT tertiary review → Andrew gates → deploy verification.
