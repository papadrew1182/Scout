# Affirmation Feature — Design Spec

## Overview

A dual-surface affirmation system: one calm card on the Today page for users, a full management control plane for admins. Every family member is eligible by default; admins can disable per-member.

Users influence what they see (preferences, reactions). Admins control the system (library, rules, targeting, analytics).

## Architecture Decision

**Approach A: Dedicated tables + config reuse.** Three new tables in `scout` schema for content and transactional data. Governance config reuses `HouseholdRule`. Per-member preferences reuse `MemberConfig`. No new infrastructure.

---

## 1. Data Model

### New tables (scout schema)

#### scout.affirmations

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | default gen_random_uuid() |
| text | TEXT NOT NULL | The affirmation copy |
| category | TEXT | e.g. "growth", "gratitude", "resilience" |
| tags | JSONB DEFAULT '[]' | freeform tags for filtering |
| tone | TEXT | "encouraging", "challenging", "reflective", "practical" |
| philosophy | TEXT | "discipline", "gratitude", "resilience", "faith-based", "family-first" |
| audience_type | TEXT NOT NULL DEFAULT 'general' | "parent", "child", "family", "general" |
| length_class | TEXT DEFAULT 'short' | "short", "medium" |
| active | BOOLEAN DEFAULT true | admin soft-delete / deactivation |
| source_type | TEXT DEFAULT 'curated' | "curated", "dynamic" |
| created_by | UUID FK family_members | |
| updated_by | UUID FK family_members | |
| created_at | TIMESTAMPTZ DEFAULT now() | |
| updated_at | TIMESTAMPTZ DEFAULT now() | |

#### scout.affirmation_feedback

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| family_member_id | UUID FK NOT NULL | who reacted |
| affirmation_id | UUID FK NOT NULL | what they reacted to |
| reaction_type | TEXT NOT NULL | heart, thumbs_down, skip, reshow |
| context | TEXT | "today", "dashboard" |
| created_at | TIMESTAMPTZ DEFAULT now() | |

No unique constraint — multiple reactions per member per affirmation are valid (heart then later thumbs_down). Selection engine checks for thumbs_down without a later reshow.

#### scout.affirmation_delivery_log

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| family_member_id | UUID FK NOT NULL | |
| affirmation_id | UUID FK NOT NULL | |
| surfaced_at | TIMESTAMPTZ NOT NULL | when shown |
| surfaced_in | TEXT NOT NULL | "today", "dashboard" |
| dismissed_at | TIMESTAMPTZ | when user dismissed/reacted |
| created_at | TIMESTAMPTZ DEFAULT now() | |

Index: `(family_member_id, surfaced_at DESC)` for cooldown lookups.

### Reused config (no new tables)

**HouseholdRule** key `affirmations.config`:
```json
{
  "enabled": true,
  "cooldown_days": 3,
  "max_repeat_window_days": 30,
  "dynamic_generation_enabled": false,
  "moderation_required": false,
  "default_audience": "general",
  "weight_heart_boost": 1.5,
  "weight_preference_match": 1.3
}
```

**MemberConfig** key `affirmations.preferences`:
```json
{
  "enabled": true,
  "preferred_tones": ["encouraging", "reflective"],
  "preferred_philosophies": ["gratitude", "family-first"],
  "excluded_themes": ["faith-based"],
  "preferred_length": "short"
}
```

### Permission

One key: `affirmations.manage_config` — granted to PRIMARY_PARENT and ADMIN tiers by default via migration INSERT into `scout.role_tier_permissions`.

---

## 2. API Design

### User-facing endpoints

All require `Depends(get_current_actor)`, scoped to actor's own family_member_id.

| Method | Path | Purpose |
|---|---|---|
| GET | `/affirmations/current` | Select and return today's affirmation for current user |
| POST | `/affirmations/{id}/feedback` | Submit reaction. Body: `{reaction_type, context}` |
| GET | `/affirmations/preferences` | Get current user's preferences |
| PUT | `/affirmations/preferences` | Update preferences |

**GET /affirmations/current** response:
```json
{
  "affirmation": {
    "id": "uuid",
    "text": "You are building something that matters.",
    "category": "growth",
    "tone": "encouraging"
  },
  "delivered_at": "2026-04-17T08:00:00Z",
  "delivery_id": "uuid"
}
```

Returns `{"affirmation": null}` when no eligible affirmation exists. Frontend caches per session — one call per page load, not per render.

### Admin endpoints

All require `actor.require_permission("affirmations.manage_config")`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/admin/affirmations` | List library with filters (?category, ?tone, ?audience_type, ?active, ?q) |
| POST | `/admin/affirmations` | Create affirmation |
| PUT | `/admin/affirmations/{id}` | Update affirmation |
| PATCH | `/admin/affirmations/{id}/active` | Toggle active. Body: `{active: bool}` |
| GET | `/admin/affirmations/analytics` | Aggregate stats |
| GET | `/admin/affirmations/analytics/{id}` | Per-affirmation stats |
| GET | `/admin/affirmations/config` | Read governance config |
| PUT | `/admin/affirmations/config` | Update governance config |

**Analytics response:**
```json
{
  "total_affirmations": 45,
  "active_count": 38,
  "total_deliveries": 312,
  "reactions": {"heart": 89, "thumbs_down": 23, "skip": 145, "reshow": 12},
  "most_liked": [{"id": "...", "text": "...", "hearts": 12}],
  "most_rejected": [{"id": "...", "text": "...", "thumbs_down": 8}],
  "stale": [{"id": "...", "text": "...", "last_delivered": "2026-03-01"}],
  "per_audience": {"parent": 15, "child": 10, "general": 20}
}
```

---

## 3. Selection Engine

Located in `backend/app/services/affirmation_engine.py`. Deterministic, no ML, all tunables from admin config.

### Algorithm

**Step 1: Filter** — build eligible pool
- active = true
- audience_type matches member's role (parent→adult, child→child, general/family→all)
- NOT thumbs_downed by this member (unless a later reshow exists)
- NOT delivered within cooldown_days
- NOT delivered more than once within max_repeat_window_days

**Step 2: Score** — weight each candidate
- Base: 1.0
- x weight_heart_boost (default 1.5) if member hearted this category before
- x weight_preference_match (default 1.3) if tone/philosophy matches preferences
- x 0.5 if previously delivered (novelty bonus for unseen)

**Step 3: Select** — weighted random from top 5 scored candidates

**Step 4: Log** — write to affirmation_delivery_log

**Step 5: Return** — affirmation + delivery metadata

### Edge cases

| Case | Behavior |
|---|---|
| Empty pool | Return null, frontend hides card |
| All exhausted within window | Relax cooldown by 50%, re-filter once. Still empty → null |
| Member disabled | Short-circuit null |
| Family disabled | Short-circuit null |
| New member, no history | All score equally, pure random |

### Implementation

Two SQL queries per call:
1. Eligible affirmations (JOINs against feedback + delivery_log for exclusions)
2. Member's heart history by category (for scoring)

Scoring and weighted random selection in Python.

---

## 4. User Surface (Frontend)

### Affirmation card

Inserted into TodayHome.tsx after the summary strip, before daily-win trackers.

Single card, muted background, affirmation text, subtle category/tone label, four reaction buttons in a row (Heart, Nope, Skip, Later).

After reacting, card animates out. One affirmation per session. If API returns null, card doesn't render (no empty state).

### Preferences

New section on existing `/settings` page. Multi-select chips for tones, philosophies, excluded themes. Toggle for length preference. Uses `useMemberConfig("affirmations.preferences", defaults)`.

### Files

| File | Purpose |
|---|---|
| `scout-ui/features/affirmations/AffirmationCard.tsx` | Card component, fetches + renders + handles reactions |
| `scout-ui/features/affirmations/useAffirmation.ts` | Hook: fetch, cache, reaction POST, loading/null states |
| `scout-ui/features/affirmations/AffirmationPreferences.tsx` | Preferences panel for settings page |
| `scout-ui/lib/affirmations.ts` | API functions |

### Reaction behavior

| Reaction | UI | Backend |
|---|---|---|
| Heart | Icon fills, card fades with pulse | Logs heart, boosts category weight |
| Nope | Card slides away | Logs thumbs_down, excluded from rotation |
| Skip | Card fades quietly | Logs skip, neutral |
| Later | Card fades, "saved" toast | Logs reshow, re-enters rotation sooner |

---

## 5. Admin Surface (Frontend)

Located at `scout-ui/app/admin/affirmations/`. Gated by `useHasPermission("affirmations.manage_config")`.

Single page with four tabs.

### Tab 1: Library

Filterable table of all affirmations. Filters: category, tone, audience, status. Search: substring on text. Row tap → inline edit. Create button. Active toggle per row.

### Tab 2: Governance

Config form backed by `useFamilyConfig("affirmations.config", defaults)`. Fields: cooldown_days, max_repeat_window_days, weight_heart_boost, weight_preference_match, dynamic_generation_enabled, moderation_required.

### Tab 3: Targeting

Table of family members showing: name, role, enabled status, whether preferences are set. Admin can toggle enabled per member.

### Tab 4: Analytics

Counts + tables (no charts v1). Summary stats (deliveries, hearts, nopes, skips, reshows). Most liked, most rejected, stale affirmations.

### Files

| File | Purpose |
|---|---|
| `scout-ui/app/admin/affirmations/index.tsx` | Page shell: permission gate, tab nav |
| `scout-ui/features/affirmations/admin/AffirmationLibrary.tsx` | Library CRUD table |
| `scout-ui/features/affirmations/admin/AffirmationGovernance.tsx` | Config form |
| `scout-ui/features/affirmations/admin/AffirmationTargeting.tsx` | Per-member toggles |
| `scout-ui/features/affirmations/admin/AffirmationAnalytics.tsx` | Stats + tables |

---

## 6. Full File Manifest

### Backend

| File | Purpose |
|---|---|
| `backend/migrations/039_affirmations.sql` | Tables, indexes, permission key, default config |
| `backend/app/models/affirmations.py` | SQLAlchemy models (3 tables) |
| `backend/app/routes/affirmations.py` | User router |
| `backend/app/routes/admin/affirmations.py` | Admin router |
| `backend/app/services/affirmation_engine.py` | Selection engine + analytics queries |
| `backend/app/main.py` | Register both routers (modify) |

### Frontend

| File | Purpose |
|---|---|
| `scout-ui/lib/affirmations.ts` | API functions |
| `scout-ui/features/affirmations/AffirmationCard.tsx` | User card |
| `scout-ui/features/affirmations/useAffirmation.ts` | Hook |
| `scout-ui/features/affirmations/AffirmationPreferences.tsx` | Settings panel |
| `scout-ui/features/affirmations/admin/AffirmationLibrary.tsx` | Admin library tab |
| `scout-ui/features/affirmations/admin/AffirmationGovernance.tsx` | Admin governance tab |
| `scout-ui/features/affirmations/admin/AffirmationTargeting.tsx` | Admin targeting tab |
| `scout-ui/features/affirmations/admin/AffirmationAnalytics.tsx` | Admin analytics tab |
| `scout-ui/app/admin/affirmations/index.tsx` | Admin page shell |
| `scout-ui/features/today/TodayHome.tsx` | Add AffirmationCard import (modify) |
| `scout-ui/app/settings/index.tsx` | Add AffirmationPreferences section (modify) |
| `scout-ui/app/admin/index.tsx` | Add affirmations to ADMIN_SECTIONS (modify) |

---

## 7. Validation Requirements

- [ ] Admin routes return 403 without `affirmations.manage_config` permission
- [ ] User surface shows max 1 affirmation, max 3 actions visible (4 reactions but single-tap dismissal)
- [ ] User surface exposes zero admin controls
- [ ] Thumbs-down removes affirmation from that user's rotation
- [ ] Heart increases category weight without spammy repetition (top-5 weighted random)
- [ ] Cooldown logic prevents re-showing within configured window
- [ ] Admin CRUD creates/edits/deactivates affirmations
- [ ] Analytics endpoint returns delivery and reaction aggregates
- [ ] Family-level disable prevents all members from seeing affirmations
- [ ] Member-level disable prevents that member only

---

## 8. Risks / Follow-ups

- **Seed data**: The migration should include 20-30 starter affirmations across categories so the feature works on first deploy. Without seed data the card renders nothing.
- **Scaling**: Analytics are live SQL aggregates. Fine for <1000 deliveries/month. If volume grows, add a nightly summary materialized view.
- **Dynamic generation**: The `dynamic_generation_enabled` config flag and `source_type: "dynamic"` column are placeholders for future AI-generated affirmations. Not implemented in v1.
- **Charts**: Analytics v1 is counts + tables. Charts (trend over time, per-member breakdown) are a follow-up.
- **Notification surface**: The spec mentions "optionally on the concise user dashboard." v1 puts the card on Today only. Dashboard integration is a follow-up if the card proves valuable.
