# Scout Dual-Surface Architecture

## Overview

Scout is organized around two distinct **surfaces** for every feature area:

- **User Surface** — inline, task-flow actions taken by any family member during their day (completing a chore, adding a grocery item, reviewing a meal, submitting a purchase request). Fast, contextual, minimal friction.
- **Admin Surface** — governance actions that configure, override, or approve state on behalf of the family or another member (setting allowance rates, approving a weekly meal plan, managing permission tiers, editing family-wide rules).

**"Admin" means permission-holder, not adult.**
The boundary is not age or family role — it is whether the caller holds the required permission key. A teen can hold `allowance.run_payout` if an admin grants it. A parent can be restricted from `meal_plan.generate` if the family configuration requires it. Never conflate `role === "adult"` with "can do anything."

---

## The Three Layers

Every feature in Scout spans three orthogonal layers:

| Layer | What it is | Where it lives |
|-------|-----------|----------------|
| **1 — User Preferences** | Self-scoped data a member controls about themselves. Example: a child's dietary notes, a teen's reading level preference. | `member_config` table; `useMemberConfig` hook. |
| **2 — Selection / Personalization Logic** | How the app uses Layer 1. Example: Scout AI picks meals respecting each member's dietary notes. No admin action required — the system reads preferences automatically. | Feature services, AI orchestrator, aggregation hooks in `scout-ui/lib/{feature}.ts`. |
| **3 — Admin Governance** | Who can override, configure, or set family-wide rules. Example: minimum allowance payout, chore point values, grocery approval flow, AI toggle states. | `family_config` table; `useFamilyConfig` hook; admin API routes; `scout-ui/app/admin/*`. |

Layer 3 always requires a permission check. Layers 1–2 may require the member to be authenticated and self-scoped, but do not require elevated permissions.

---

## Role Tiers

Role tiers are seeded in the `role_tiers` table. Every family member is assigned a tier via `role_tiers_overrides`; the tier determines the base permission set. Per-member overrides (also stored in `role_tiers_overrides.override_permissions`) layer on top, and can grant or revoke individual keys.

| Tier | Intended for | Key permissions bundled by default |
|------|-------------|-----------------------------------|
| `admin` | Primary family manager(s) | All keys — full governance, config management, permission management, all feature approvals |
| `parent_peer` | Co-parents, caregivers with delegated authority | Most admin keys except `admin.manage_permissions` and `admin.manage_config`; can approve, run payouts, manage content |
| `teen` | Older children (typically 13+) | Self-scoped actions: `account.update_self`, `chore.complete_self`, `grocery.add_item`, `grocery.request_item`, `meal.review_self`, `purchase_request.submit` |
| `child` | Younger children | Same as teen minus `grocery.add_item` (must request instead) |
| `kid` | Youngest children | Minimal surface: `chore.complete_self`, `meal.review_self`, no purchase request submission |

Tier assignment is append-only: new permissions are added via migrations; existing tier rows are never edited in place. Per-member overrides handle exceptions without touching shared seed data.

---

## Permission Key Naming Convention

Keys follow the pattern `{feature}.{action}` — lowercase, underscore-separated tokens.

```
allowance.run_payout
allowance.manage_config
chores.manage_config
grocery.add_item
grocery.approve
meal_plan.generate
meal_plan.approve
admin.manage_permissions
admin.view_config
family.manage_members
purchase_request.submit
purchase_request.approve
scout_ai.manage_toggles
```

Rules:
- Feature token: one word or underscore-joined compound (`meal_plan`, `scout_ai`).
- Action token: verb or verb-noun (`run_payout`, `view_config`, `approve`).
- No uppercase, no dots in either token, no spaces.
- Regex: `^[a-z][a-z_]*\.[a-z][a-z_]*$`

---

## Adding a New Feature — Compliance Checklist

Every new Scout feature MUST satisfy all eight points before merge. This checklist is also enforced in `.github/pull_request_template.md`.

1. **Define permission keys** for every action that mutates state or exposes governance controls. Register them in the appropriate tier(s) via a new migration.

2. **Write a migration** — `backend/migrations/NNN_{feature}_permissions.sql` that INSERTs new permission keys into the affected `role_tiers` rows (JSONB merge). Never edit an existing migration. The database mirror at `database/migrations/` must be kept in sync.

3. **Backend enforcement** — every `POST`, `PUT`, `PATCH`, `DELETE` endpoint in `backend/app/routes/{feature}.py` that mutates family or member state MUST call `actor.require_permission("feature.action")`. Endpoints that are genuinely public (e.g. health check, unauthenticated login) MUST be annotated with `# noqa: public-route` so the architecture check script skips them.

4. **Frontend gating** — every button, form control, or menu item that triggers an admin-level action MUST call `useHasPermission("feature.action")` and conditionally render `null` (or a disabled state) when the result is `false`. Never hide controls using hardcoded role checks.

5. **Family-wide config** — any value that the admin can configure for the whole family belongs in the `family_config` table, accessed via `useFamilyConfig<T>(key, default)` on the frontend and `get_family_config` / `set_family_config` on the backend.

6. **Per-member config** — any value scoped to an individual member belongs in the `member_config` table, accessed via `useMemberConfig<T>(memberId, key, default)` on the frontend and `get_member_config` / `set_member_config` on the backend.

7. **Admin screen** — governance UI lives at `scout-ui/app/admin/{feature}/`. The route file must check `useHasPermission` at the top and return `null` or redirect if the caller lacks access. Standard section layout: config editor → rules/overrides → analytics stub.

8. **User surface purity** — the user-facing screens for a feature (`scout-ui/app/{feature}/`) show ONLY the actions the caller is permitted to take. Admin-only controls (approve, override, bulk edit) must NEVER appear on user-facing pages, even conditionally based on role.

---

## Canonical File Locations

| Concern | Path |
|---------|------|
| Backend permission resolution | `backend/app/services/permissions.py` |
| Backend permission + config API routes | `backend/app/routes/admin/permissions.py`, `backend/app/routes/admin/config.py` |
| Actor permission primitives | `backend/app/auth.py` — `Actor.has_permission()`, `Actor.require_permission()` |
| Frontend permission hook | `scout-ui/lib/permissions.ts` — `useHasPermission()`, `usePermissionsReady()` |
| Frontend config hooks | `scout-ui/lib/config.ts` — `useFamilyConfig()`, `useMemberConfig()` |
| Frontend API layer | `scout-ui/lib/api.ts` |
| Feature aggregation hooks | `scout-ui/lib/{feature}.ts` |
| Admin route group | `scout-ui/app/admin/*` |
| Migrations | `backend/migrations/NNN_*.sql` (mirrored to `database/migrations/`) |

---

## Anti-Patterns to Avoid

- **Do not hardcode family-configurable values in `seedData.ts`** or any constant file. Any value an admin might need to change belongs in `family_config`. Hardcoded values are permanent drift — they can't be updated without a code deploy.
- **Do not gate only in the UI without backend enforcement.** UI gating is a UX nicety; the backend `require_permission` call is the actual security boundary. Both must exist.
- **Do not add `*.manage_config` permission calls from non-admin routes.** Config write endpoints live under `/admin/config/*`; no other route file should call `set_family_config` or `set_member_config` directly.
- **Do not expose admin-only controls on user pages.** Approval buttons, override inputs, and governance toggles belong exclusively in `app/admin/*`, regardless of whether the current user happens to hold the permission.
- **Do not use `role === "adult"` as a permission check.** Use `actor.require_permission(key)` on the backend and `useHasPermission(key)` on the frontend. Role is metadata; permissions are the authorization boundary.
- **Do not edit existing migrations.** Permission sets must be grown via new migrations only. Editing existing migrations breaks environments that have already run them.
- **Do not skip the `# noqa: public-route` annotation** on genuinely public endpoints. Without it, the architecture check script emits a warning on every CI run for that endpoint.

---

## Known Gaps

The following items were identified by `node scripts/architecture-check.js` on the Phase 7 baseline run. They represent genuine pre-Phase-4 technical debt: routes that predate the permission system and use `actor.require_family()` (authentication + family membership check) but not `actor.require_permission()` (fine-grained permission check). They are **not** security vulnerabilities — all endpoints require authentication and reject cross-family access — but they bypass Scout's permission model, meaning per-member tier overrides and the admin UI cannot restrict them.

Resolving these is a follow-up sprint (post-Phase 7). When fixing each file, add the appropriate `require_permission(key)` call and the corresponding key to the role tier that should hold it, via a new migration.

| File | Endpoint count | Notes |
|------|---------------|-------|
| `backend/app/routes/meals.py` | 14 | Mix of user actions (add review) and admin actions (approve plan, archive meal); need to split by permission key |
| `backend/app/routes/grocery.py` | 8 | Mix of `grocery.add_item`, `grocery.approve`, `purchase_request.approve`, `purchase_request.submit` |
| `backend/app/routes/calendar.py` | 7 | All user-scoped (add/update/delete events); add `calendar.manage_self` or similar |
| `backend/app/routes/notes.py` | 5 | Mix of self-scoped and `notes.manage_any` |
| `backend/app/routes/finance.py` | 5 | Mix of self-scoped and `finance.manage` |
| `backend/app/routes/personal_tasks.py` | 4 | All user-scoped; add `tasks.manage_self` |
| `backend/app/routes/task_instances.py` | 4 | Chore completion self-scoped; `chore.complete_self` already defined |
| `backend/app/routes/health_fitness.py` | 6 | All user-scoped; define `health.manage_self` |
| `backend/app/routes/allowance.py` | 1 | `create_manual_entry` — needs `allowance.run_payout` or a new `allowance.manage_ledger` key |
| `backend/app/routes/chores.py` | 1 | Mix of user action; `chore.complete_self` already seeded |
| `backend/app/routes/routines.py` | 2 | User-scoped; define `routines.manage_self` |
| `backend/app/routes/families.py` | 1 | `family.manage_members` already seeded |
| `backend/app/routes/canonical.py` | 1 | Audit endpoint; needs `admin.view_config` or similar |
| `backend/app/routes/integrations.py` | 2 | `integrations.manage` already seeded |
| `backend/app/routes/daily_wins.py` | 1 | User-scoped; define `daily_wins.manage_self` |
| `backend/app/routes/mcp_http.py` | 1 | MCP proxy; gate with `ai.manage` or a new `mcp.execute` key |

**Check 3 (seedData drift):** Multiple constants from `scout-ui/lib/seedData.ts` are still imported by `app/` pages. These are mockup-stage values that should migrate to `family_config` or `member_config` before the affected pages go to production. The arch-check script reports them as INFO (not WARN) — they do not block merge but should be tracked. Current drift set: `FAMILY`, `CHORES_TODAY`, `MEALS_THIS_WEEK`, `GROCERY`, `ALLOWANCE`, `ACTION_INBOX`, `LEADERBOARD`, `ACTIVITY`, `HOMEWORK`, `BATCH_COOK`, and several single-letter re-exports.

**Annotated false positives (suppressed via `# noqa: public-route`):** `auth.login`, `auth.bootstrap`, `auth.logout`, `auth.password.change`, `auth.sessions.revoke`, `auth.sessions.revoke-others`, `ai.chat`, `ai.chat.stream`, `ai.transcribe`, `ai.receipt`, `ai.brief.daily`, `ai.plans.weekly`, `ai.meals.staples`, `ai.conversations.end`.
