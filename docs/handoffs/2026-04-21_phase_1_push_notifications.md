# Expansion Phase 1 Handoff — Push notifications

**Branch:** `sprint/expansion-phase-1-push-notifications`
**Date:** 2026-04-21
**Spec:** `SCOUT_EXPANSION_SPRINT_V2.md` §Phase 1
**Base commit:** `927d571` (main, post-operability-sprint)

---

## Summary

Scout can now deliver time-sensitive push notifications via the Expo
Push Service. The AI tool `send_notification_or_create_action` —
previously a no-op that only logged — now pushes to active devices
and falls back to an Action Inbox row when no device is available.

## Machine-verifiable prerequisites satisfied

Before this phase could proceed, none of the Phase 1 prereqs in §3.2
were met. This branch adds the minimum repo-visible config so they are:

- `PushSettings` in `backend/app/config.py` declares
  `push_provider`, `expo_push_security_enabled`, `expo_access_token`,
  `expo_push_api_base`, `push_receipt_poll_batch` with sensible
  defaults.
- `backend/.env.example` documents `PUSH_PROVIDER`,
  `EXPO_PUSH_SECURITY_ENABLED`, `EXPO_ACCESS_TOKEN`.
- `scout-ui/.env.example` documents `EXPO_PUBLIC_PUSH_PROVIDER`.
- `scout-ui/app.json` adds the `expo-notifications` plugin.
- `scout-ui/package.json` adds `expo-notifications`, `expo-constants`,
  `expo-device` as dependencies.

Andrew still needs to:

- Set the env keys in Railway and Vercel for prod.
- Run `eas init` and paste the EAS project ID into
  `scout-ui/app.json` under `expo.extra.eas.projectId`. Without this,
  `getExpoPushTokenAsync` fails on EAS-built apps.

## Migrations added

- `046_push_notifications.sql` (mirrored to `database/migrations/`)
  - New tables `scout.push_devices`, `scout.push_deliveries`
  - Indexes for member lookup, pending-receipt polling, and active
    devices
  - Permissions: `push.register_device`, `push.revoke_device`,
    `push.send_to_member`, `push.view_delivery_log`
  - Register / revoke granted to every tier except DISPLAY_ONLY
  - Send / view delivery log granted to PARENT / PRIMARY_PARENT

### Migration number note

`database/migrations/045_ai_message_metadata.sql` exists without a
`backend/migrations/` twin — pre-existing drift from PR #25 (Supabase
Storage). I bumped my migration to 046 rather than reclaim 045 to
avoid corrupting any environment that has already applied the 045
add-column. **Out of scope to fix in this sprint.**

## Permission keys added

- `push.register_device` — self-scoped device registration.
- `push.revoke_device` — self-scoped device revoke.
- `push.send_to_member` — send a push to another family member.
- `push.view_delivery_log` — read family-wide delivery log.

## Backend added

- `backend/app/models/push.py` — `PushDevice`, `PushDelivery`
  SQLAlchemy models.
- `backend/app/services/push_service.py` — registration, send,
  receipt polling, tap recording, Expo HTTP client entry points
  (`_expo_send`, `_expo_get_receipts`) that tests monkeypatch.
- `backend/app/routes/push.py` — seven endpoints under `/api/push/*`,
  all permission-gated per the spec.
- `backend/app/scheduler.py` — receipt polling wired into the
  existing APScheduler tick via `run_push_receipt_poll_tick`.
- `backend/app/ai/tools.py` — `_send_notification_or_create_action`
  now delivers or falls back; `ToolDefinition` input schema gains
  optional `title` and `route_hint`.
- `backend/app/main.py` — includes the new `push.router`.

## Frontend added

- `scout-ui/lib/push.ts` — API wrappers + hooks
  (`useRegisteredDevices`, `useMyPushDeliveries`,
  `useFamilyPushDeliveries`, `useSendTestPush`, `usePushRegistration`).
  `usePushRegistration` dynamically imports
  `expo-notifications`/`expo-device`/`expo-constants` so the web
  bundle stays lean.
- `scout-ui/app/settings/notifications.tsx` — permission status,
  device list with revoke, personal delivery log, and admin-only
  Test push / Family delivery log cards gated by `useHasPermission`.
- `scout-ui/app/settings/index.tsx` — adds a Notifications row to
  the settings index.

## Tests added

- `backend/tests/test_push_notifications.py` — 13 tests:
  - `send_push` writes `provider_accepted` rows with ticket id
  - empty-devices send returns empty result
  - request-level Expo failure marks rows `provider_error`
  - DeviceNotRegistered ticket deactivates the device
  - `poll_pending_receipts` advances to `provider_handoff_ok`
  - `poll_pending_receipts` deactivates on DeviceNotRegistered receipt
  - device register / list / revoke round-trip over HTTP
  - child-tier 403 on `/api/push/test-send`
  - child-tier 403 on `/api/push/deliveries`
  - adult test-send creates a delivery row
  - AI tool push-delivered path skips Action Inbox
  - AI tool no-device path creates a ParentActionItem
  - AI tool rejects invalid target member

Smoke test: `smoke-tests/tests/push-notifications.spec.ts` — four
cases covering settings link, notifications page core sections, admin
cards, and the web-unsupported notice.

## Test counts

| Suite | Before | After | Delta |
|---|---|---|---|
| Backend pytest | 714 | 727 | +13 |
| Smoke specs | (unchanged) | +1 file | +1 spec |

## Arch-check

- Baseline (main @ 927d571): 40 WARN, 1 INFO.
- Final (this branch):        40 WARN, 1 INFO.
- No new WARNs introduced. The per-route arch-check initially flagged
  `POST /api/push/deliveries/{id}/tap` for missing permission; fixed
  by gating on `push.register_device` (the floor tier that can own a
  delivery to tap in the first place).

## Scheduler ownership

Not a new scheduler. Receipt polling rides the existing tier-5
`BackgroundScheduler` in `backend/app/scheduler.py`, inside the same
advisory-lock gate as morning brief, weekly retro, moderation digest,
and anomaly scan. §7 amendment respected.

## Not covered (per spec)

- Widgets, Siri Shortcuts, lock screen surfaces — Sprint 1B.
- Android push UX — schema is future-safe, Phase 1 is iOS-only.
- Rich media, action buttons on the push, quiet hours, grouping.
- Receipt polling is in the existing scheduler, but no new recurring
  job invention was done. Daily-brief scheduled delivery stays on the
  existing morning-brief tick; push is additive, not a replacement.

## Physical-device validation

**Not verifiable from repo state.** Per the Phase 1 acceptance:

- [ ] Install the Scout app on a physical iPhone
- [ ] Register from /settings/notifications (requires the EAS project
      ID to be set in app.json, which Andrew must add after `eas init`)
- [ ] Send a test push from an admin session
- [ ] iPhone displays the notification
- [ ] Tapping the notification opens Scout and `tapped_at` populates

## Out-of-scope debt flagged

- Migration drift: `database/migrations/045_ai_message_metadata.sql`
  has no `backend/migrations/` twin. Fixing is a small follow-up
  commit; not in this sprint.
