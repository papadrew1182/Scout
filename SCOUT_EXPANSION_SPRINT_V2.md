# Scout Expansion Sprint - Claude Code Handoff

**Ref commit:** latest `main` at time of execution (expected to be post-operability-sprint)
**Prepared:** 2026-04-21 (consolidated from REVISED + V2 drafts)
**Intended audience:** Claude Code running against the Scout monorepo
**Precondition:** `SCOUT_OPERABILITY_SPRINT.md` phases 1-6 are complete and merged on `main`. This sprint builds on them.
**Supersedes:** earlier drafts `SCOUT_EXPANSION_SPRINT.md`, `SCOUT_EXPANSION_SPRINT_REVISED.md`, `SCOUT_EXPANSION_SPRINT_V2.md`.

---

## 1. Why this sprint exists

The operability sprint made Scout usable. This sprint makes Scout irreplaceable.

Three phases, one from each strategic category:

- **Phase 1 - Push notifications (platform):** Scout currently has no way to reach a family member off-screen. Every feature built so far relies on the user opening the app. This phase unblocks the Action Layer promise in the original product vision: Scout can now interrupt life at the right moment, not wait for someone to remember to check.
- **Phase 2 - Google Calendar real integration (platform/depth):** Scout's calendar domain has worked against dev-mode ingestion buttons since launch. Per `docs/roadmaps/scout_external_data_roadmap.md`, Google Calendar is the scheduling spine that bridges Scout, Hearth Display, and the rest of the family's time. This phase replaces the dev-mode buttons with a real OAuth flow, a real sync engine, and bidirectional publication.
- **Phase 3 - Family projects engine (new domain):** `docs/architecture/ARCHITECTURE.md` lists Projects as a core Scout domain, but no schema or UI exists. Per the system prompt vision, Projects are multi-week efforts with tasks, deadlines, grocery impacts, and budget checkpoints. This phase ships the engine. Templates and content come in a follow-up sprint.

**Explicitly deferred to later sprints:**

- Widgets, Siri Shortcuts, and lock screen surfaces. These require native iOS surface work and should not ride along with Phase 1.
- YNAB OAuth integration. Listed as Sprint 2B in §6.
- Apple Health and Nike Run Club integrations. Listed as Sprint 2C in §6.
- Built-in project template content. Engine first, content later.

---

## 2. Operating constraints

All work in this sprint must satisfy the existing Scout architecture contract as defined in `docs/architecture/ARCHITECTURE.md`. The compliance checklist is the acceptance floor for every phase.

Non-negotiable:

- `scout.*` schema. UUID PKs named `id`. FKs named using the repo's canonical table naming pattern. `timestamptz` everywhere it is appropriate. `created_at` on every table. `updated_at` on mutable tables. `is_` / `has_` prefix on booleans.
- Zero external IDs on core tables. All external system IDs, including Google event IDs, watch channel IDs, OAuth tokens, and push device tokens, live in connector tables or dedicated integration tables.
- Never edit an existing migration. New migrations at `backend/migrations/NNN_{feature}.sql`, mirrored to `database/migrations/`.
- Every mutating endpoint calls `actor.require_permission("feature.action")`. Public endpoints annotated with `# noqa: public-route`.
- Frontend admin controls gated with `useHasPermission`. User-surface purity maintained.
- Family-wide config in `family_config`. Per-member config in `member_config`.
- SQL params `$1` / `$2` asyncpg style.
- No em dashes in any produced content.
- `node scripts/architecture-check.js` runs at end of every phase. Any new WARN-level finding is a blocker.

Phase-wide clarifications that override the original draft:

- Push delivery semantics must distinguish between provider acceptance and provider handoff. A successful Expo ticket means Expo accepted the message. A successful Expo receipt means Expo handed the message to APNs or FCM. Neither guarantees the device displayed it.
- Native Google OAuth must use a system browser based flow. Do not use an embedded WebView for authorization.
- Per-member Google calendar subscription and webhook lifecycle state do not belong in `connector_configs` JSON. They must live in dedicated integration tables.
- Claude Code may verify only what is machine-verifiable from repo state, env vars, or config files. It must not claim it verified Apple portal or Google Cloud console state from the codebase alone.

Testing floor per phase:

- Backend pytest suite remains at or above current passing count.
- Smoke Playwright suite remains green at or above current count.
- Every new endpoint gets a happy-path test and a permission-denial test.
- Every new user-visible flow gets a new Playwright spec.
- Any acceptance criterion that depends on physical-device push delivery must be satisfied by manual validation, not by Playwright.

Documentation floor per phase:

- ERDs for new tables in `docs/architecture/erd/{feature}.mmd` using Mermaid.
- Architecture diagrams for cross-cutting changes in `docs/architecture/diagrams/{name}.svg`.
- Session handoff at `docs/handoffs/{YYYY-MM-DD}_phase_{N}_{slug}.md`.
- Verification harness entry appended to `docs/verification/scout_operability_verification_harness.md` under a new Expansion section.
- Release candidate report updated per phase.

Commit discipline:

- Branch per phase: `sprint/expansion-phase-{N}-{slug}`.
- Commit groups: `migration:` / `backend:` / `frontend:` / `smoke:` / `docs:`. Omit groups that do not apply.
- Only `docs:` is mandatory.
- `docs:` is always the final commit on the branch.

---

## 3. Pre-flight checklist

This sprint has external dependencies that Claude Code cannot satisfy alone. Split them into two classes.

### 3.1 Human-confirmed prerequisites

Claude Code must not pretend it can verify these from repo state. Andrew confirms these manually.

**Phase 1 prerequisites (push notifications):**

- [ ] Apple Developer Program membership is active.
- [ ] Scout's production iOS bundle ID is registered in Apple Developer.
- [ ] APNs credentials exist for the app, either as an APNs Auth Key already managed in Expo/EAS or as credentials Andrew can upload before testing.
- [ ] Decision made on push provider: Expo Push Service for this sprint unless Andrew explicitly overrides.
- [ ] At least one physical iOS device is available for push validation.

**Phase 2 prerequisites (Google Calendar):**

- [ ] Google Cloud project exists for Scout.
- [ ] Google Calendar API is enabled in the project.
- [ ] OAuth consent screen is configured.
- [ ] OAuth test users are added while the app is in testing mode.
- [ ] The backend callback URL and webhook URL are publicly reachable over HTTPS.
- [ ] Andrew confirms the intended redirect URI and post-connect app return URI before implementation starts.

**Phase 3 prerequisites (Family projects engine):**

- None external.

### 3.2 Machine-verifiable prerequisites

Claude Code must verify these from env vars, app config, or other repo-visible configuration. If any required item below is missing, HALT that phase and report the missing item.

**Phase 1 machine-verifiable prerequisites:**

- [ ] `PUSH_PROVIDER=expo` is present in backend env/config for this phase.
- [ ] `EXPO_PUBLIC_PUSH_PROVIDER=expo` is present in frontend env/config.
- [ ] If `EXPO_PUSH_SECURITY_ENABLED=true`, then `EXPO_ACCESS_TOKEN` is present. If push security is not enabled, `EXPO_ACCESS_TOKEN` is optional.
- [ ] Expo app config includes the notifications plugin and any existing project ID wiring needed by the current Expo token registration path.

**Phase 2 machine-verifiable prerequisites:**

- [ ] `GOOGLE_CLIENT_ID` is present.
- [ ] `GOOGLE_CLIENT_SECRET` is present.
- [ ] `SCOUT_OAUTH_ENCRYPTION_KEY` is present.
- [ ] `SCOUT_GOOGLE_OAUTH_REDIRECT_URI` is present.
- [ ] `SCOUT_GOOGLE_OAUTH_APP_RETURN_URI` is present.
- [ ] Backend base URL / callback configuration resolves to HTTPS.

### 3.3 Execution rule

- Claude Code may halt automatically only for missing machine-verifiable prerequisites, or if Andrew has explicitly marked a human-confirmed prerequisite as incomplete.
- Claude Code must not claim it verified Apple portal state, APNs key presence in Apple, Google Cloud console settings, or OAuth consent screen configuration from repo state alone.
- Do not stub external credentials.
- Do not proceed with placeholders.

---

## 4. Phases

### Phase 1 - Push notification delivery

**Goal:** Scout can deliver time-sensitive notifications to family members off-screen. Every user-visible action with a deadline or an assignment can trigger a push. The existing `send_notification_or_create_action` AI tool actually delivers a notification for the first time.

**Strategic note:** this phase deliberately scopes to push only. Widgets, Siri Shortcuts, lock screen complications, and all other native notification surfaces are deferred to Sprint 1B in §6.

**Stack:** Expo Push Service is the recommended provider. `expo-notifications` handles permissioning, device token registration, foreground display, and notification response handling. The backend stores Expo push tokens per device and posts to Expo's push API. Expo fans out to APNs. Receipt polling is required in this phase so Scout can distinguish between provider acceptance and provider handoff.

**Scope:**

**Schema** (migration `NNN_push_notifications.sql`):

- New table `scout.push_devices`
  - `id`
  - `family_member_id` FK
  - `expo_push_token` text UNIQUE
  - `device_label` text
  - `platform` enum [`ios`, `android`, `web`]
  - `app_version` text
  - `is_active` boolean default true
  - `last_registered_at` timestamptz
  - `last_successful_delivery_at` timestamptz nullable
  - `created_at`
  - `updated_at`
- New table `scout.push_deliveries`
  - `id`
  - `notification_group_id` uuid
  - `family_member_id` FK
  - `push_device_id` FK
  - `provider` enum [`expo`]
  - `category` text
  - `title` text
  - `body` text
  - `data` jsonb
  - `trigger_source` text
  - `status` enum [`queued`, `provider_accepted`, `provider_handoff_ok`, `provider_error`]
  - `provider_ticket_id` text nullable
  - `provider_receipt_status` text nullable
  - `provider_receipt_payload` jsonb nullable
  - `error_message` text nullable
  - `sent_at` timestamptz nullable
  - `receipt_checked_at` timestamptz nullable
  - `provider_handoff_at` timestamptz nullable
  - `tapped_at` timestamptz nullable
  - `created_at`
  - `updated_at`
- Indexes
  - `(family_member_id, created_at DESC)` on `push_deliveries`
  - `(status, created_at)` on `push_deliveries` for pending receipt polling
  - `(is_active) WHERE is_active = true` on `push_devices`
- Permission keys
  - `push.register_device` (all tiers)
  - `push.revoke_device` (all tiers, self-scoped)
  - `push.send_to_member` (admin, parent_peer)
  - `push.view_delivery_log` (admin, parent_peer)

**Backend:**

- `backend/app/services/push_service.py`
  - Functions: `register_device`, `revoke_device`, `send_push`, `send_bulk_push`, `poll_pending_receipts`, `record_tap_event`, `deactivate_unregistered_device`
  - `send_push` resolves active devices for the target member and writes one `push_deliveries` row per device attempt under a shared `notification_group_id`
  - `send_push` sets `status=provider_accepted` only after Expo returns an `ok` ticket and stores `provider_ticket_id`
  - `send_push` sets `status=provider_error` immediately when Expo returns a per-message error ticket or request-level error
  - `poll_pending_receipts` fetches Expo receipts for pending `provider_ticket_id` values, updates rows to `provider_handoff_ok` or `provider_error`, stores raw receipt payload, and deactivates devices on `DeviceNotRegistered`
- `backend/app/routes/push.py`
  - `POST /api/push/devices` register current device
  - `GET /api/push/devices/me` list current member's registered devices
  - `DELETE /api/push/devices/{id}` revoke one of the current member's devices
  - `GET /api/push/deliveries/me` list the current member's recent deliveries
  - `GET /api/push/deliveries` family-wide recent deliveries for `push.view_delivery_log`
  - `POST /api/push/deliveries/{id}/tap` record tap-to-open
  - `POST /api/push/test-send` send a test push to a target member, requires `push.send_to_member`
- Integrate `send_push` into the existing AI tool `send_notification_or_create_action` in `backend/app/ai/tools.py`
  - Deterministic rule for this sprint: if at least one active device exists and the provider accepts at least one device attempt, treat push as the primary path and do not create a duplicate Action Inbox fallback item by default
  - If no active device exists, or all device attempts fail at provider submission time, preserve the existing Action Inbox fallback behavior
- Expose backend job entry points
  - `send_scheduled_daily_brief(family_member_id)`
  - `poll_pending_push_receipts(limit=1000)`
  - If operability sprint already introduced a scheduler pattern, use it. If not, expose the entry points cleanly and document the follow-up. Do not invent a second scheduling architecture in this phase.

**Frontend:**

- `scout-ui/lib/push.ts`
  - Hooks: `usePushPermission()`, `useRegisteredDevices()`, `useMyPushDeliveries()`, `useFamilyPushDeliveries()`, `useSendTestPush()`
- On app launch
  - If `expo-notifications` reports permission is `undetermined`, prompt the user
  - If permission is granted and the app is running on a physical device, register the device by posting the Expo push token to `/api/push/devices`
  - If the app is running on a simulator, show an informative non-error state in settings and skip device registration
  - Read the notification response that opened the app and post to `/api/push/deliveries/{id}/tap`, then deep-link using `data.route_hint`
- `scout-ui/app/settings/notifications.tsx`
  - **Permission status** section with CTA to iOS Settings if denied
  - **Registered devices** section for the current member
  - **Delivery log** section for the current member
  - **Family delivery log** section only for users with `push.view_delivery_log`
  - **Test push** control only for users with `push.send_to_member`
- Existing settings page gets a Notifications row that navigates to `/settings/notifications`

**Secrets / config:**

- Backend env vars
  - `PUSH_PROVIDER=expo`
  - `EXPO_PUSH_SECURITY_ENABLED=false|true`
  - `EXPO_ACCESS_TOKEN` only required if Expo push security is enabled
- Frontend env vars
  - `EXPO_PUBLIC_PUSH_PROVIDER=expo`
- Documented in `docs/private_launch.md` under a new Push notifications section

**Acceptance criteria:**

- [ ] Migration applied: `push_devices` and `push_deliveries` exist with correct schema and indexes.
- [ ] Permission keys registered in `role_tiers` via migration.
- [ ] Backend happy-path test: send a push to a member with an active device, assert at least one `push_deliveries` row with `status=provider_accepted` and a populated `provider_ticket_id`.
- [ ] Backend receipt test: mock Expo receipts, run `poll_pending_push_receipts`, assert rows move to `provider_handoff_ok` or `provider_error` and store the receipt payload.
- [ ] Permission-denial test: kid-tier actor cannot call `push.send_to_member` or family-wide delivery log routes.
- [ ] Frontend `/settings/notifications` renders for all tiers. Device registration round-trips successfully on a physical device build. Simulator state is handled gracefully.
- [ ] Tap-to-open handler records `tapped_at` and routes to `data.route_hint` if present.
- [ ] `smoke-tests/tests/push-notifications.spec.ts` covers registration, test send, and delivery-row creation with Expo mocked. It does not claim device display.
- [ ] Manual physical-device validation: one iPhone running the built app receives a test push, the app opens from the notification, and `tapped_at` is recorded.
- [ ] AI tool integration test: with an active device and provider acceptance, a push delivery is created and no duplicate fallback Action Inbox item is created by default. With no active device or provider submission failure, the fallback Action Inbox path still executes.
- [ ] Arch check clean.
- [ ] `docs/private_launch.md` documents provider setup, env vars, and manual validation limits.

**Out of scope (enforce):**

- Widgets, Siri Shortcuts, and lock screen surfaces. Sprint 1B.
- Android push UX work. Schema may remain future-safe, but Scout is iOS-first for this phase.
- Rich media pushes, action buttons on the push itself, grouping, quiet hours, or do-not-disturb windows.
- Scheduler ownership beyond exposing clean entry points if no scheduler pattern already exists.

**Estimated output:** 1 migration, ~8 backend files, ~5 frontend files, 1 smoke spec, 3 docs updates.

---

### Phase 2 - Google Calendar real integration

**Goal:** replace dev-mode Google Calendar ingestion with a real OAuth flow and a real sync engine. Scout reads family calendars bidirectionally and writes household anchor blocks that Hearth Display can consume via iCal export.

**Strategic note:** per `docs/roadmaps/scout_external_data_roadmap.md`, Google Calendar is the scheduling spine. The existing `connector_mappings` pattern handles external event IDs. This phase is the first real use of that pattern against a live external system. The patterns established here should become the template for YNAB and later integrations.

**Scope:**

**Schema** (migration `NNN_google_calendar_integration.sql`):

- New table `scout.oauth_credentials`
  - `id`
  - `family_member_id` FK
  - `provider` enum [`google`]
  - `access_token_encrypted` text
  - `refresh_token_encrypted` text
  - `scope` text
  - `expires_at` timestamptz
  - `token_type` text
  - `is_active` boolean default true
  - `revoked_at` timestamptz nullable
  - `created_at`
  - `updated_at`
  - Unique active credential per `(family_member_id, provider)`
- New table `scout.google_calendar_subscriptions`
  - `id`
  - `family_member_id` FK
  - `google_calendar_id` text
  - `google_calendar_name` text
  - `is_bidirectional` boolean default false
  - `conflict_policy` enum [`scout_wins`, `google_wins`, `manual`]
  - `sync_enabled` boolean default true
  - `sync_token` text nullable
  - `watch_channel_id` text nullable
  - `watch_resource_id` text nullable
  - `watch_token` text nullable
  - `watch_expires_at` timestamptz nullable
  - `last_full_synced_at` timestamptz nullable
  - `last_delta_synced_at` timestamptz nullable
  - `last_sync_status` enum [`idle`, `success`, `partial`, `failed`, `needs_full_resync`] default `idle`
  - `last_error_message` text nullable
  - `created_at`
  - `updated_at`
  - Unique `(family_member_id, google_calendar_id)`
- New table `scout.connector_sync_runs`
  - `id`
  - `family_id` FK
  - `family_member_id` FK
  - `connector` text
  - `run_type` enum [`full`, `delta`, `push`, `renew_watch`]
  - `started_at`
  - `completed_at` timestamptz nullable
  - `status` enum [`running`, `success`, `partial`, `failed`]
  - `records_read` int default 0
  - `records_written` int default 0
  - `records_skipped` int default 0
  - `error_message` text nullable
  - `created_at`
- Existing `connector_mappings` is used for Google event ID to Scout event ID pairing. No schema change to core event tables.
- No new Google calendar selection JSON column on `connector_configs`.
- Permission keys
  - `integrations.connect_google` (admin, parent_peer, teen)
  - `integrations.disconnect_google` (admin, parent_peer, teen, self-scoped)
  - `integrations.view_sync_log` (admin, parent_peer)
  - `integrations.force_sync` (admin, parent_peer)

**OAuth and scope model:**

- Launch authorization in a system browser based flow using Expo AuthSession / WebBrowser auth session style behavior. Do not use an embedded WebView.
- The backend is the OAuth client for code exchange and secret handling.
- Backend callback exchanges the code, stores encrypted tokens, and redirects to `SCOUT_GOOGLE_OAUTH_APP_RETURN_URI` with a success or failure result.
- Validate `state` against a short-lived server-side store. Use PKCE if the current auth helper stack already supports it cleanly; otherwise state validation is mandatory.
- Request the narrowest scopes needed for this phase. Default to:
  - `https://www.googleapis.com/auth/calendar.calendarlist.readonly`
  - `https://www.googleapis.com/auth/calendar.events`
- Do not request broad `https://www.googleapis.com/auth/calendar` unless Claude verifies a specific required method in current implementation needs it.

**Backend:**

- `backend/app/services/oauth/google.py`
  - Functions: `build_authorize_url(family_member_id, state_nonce)`, `exchange_code(code, state_nonce)`, `refresh_access_token(credential_id)`, `revoke_credential(credential_id)`
  - Tokens stored encrypted using `cryptography.fernet` with `SCOUT_OAUTH_ENCRYPTION_KEY`
- `backend/app/services/connectors/google_calendar.py`
  - Functions: `list_calendars(family_member_id)`, `create_subscription(family_member_id, google_calendar_id, config)`, `delete_subscription(subscription_id)`, `full_sync(subscription_id)`, `delta_sync(subscription_id)`, `renew_watch(subscription_id)`, `renew_expiring_watches()`, `publish_scout_anchor_block(event_id)`, `pull_google_event(google_event_id, family_member_id)`, `handle_conflict(scout_event, google_event, policy)`, `recover_from_invalid_sync_token(subscription_id)`
  - Persist `sync_token`, channel metadata, and watch expiry in `google_calendar_subscriptions`
  - On Google `410 Gone` for a stale sync token, clear local sync state and perform a full sync for that subscription
  - On unsubscribe or revoke, stop the remote Google watch channel if watch metadata exists
  - Every run writes a row to `connector_sync_runs`
  - Every external event mapping writes to `connector_mappings`
- `backend/app/routes/connectors/google.py`
  - `GET /api/connectors/google/oauth/authorize`
  - `GET /api/connectors/google/oauth/callback` public route, validates `state`, exchanges code, redirects back to the app
  - `POST /api/connectors/google/revoke` revoke the current member's Google credential and mark it inactive
  - `GET /api/connectors/google/calendars` list available Google calendars for the current member
  - `GET /api/connectors/google/subscriptions` list current member's subscriptions
  - `POST /api/connectors/google/subscriptions` subscribe to one Google calendar for sync
  - `DELETE /api/connectors/google/subscriptions/{id}` unsubscribe one calendar
  - `POST /api/connectors/google/sync` force sync, admin / parent_peer only
  - `GET /api/connectors/google/sync-runs` family-wide sync log, admin / parent_peer only
  - `POST /api/connectors/google/webhook` public route, validates `X-Goog-Channel-ID`, `X-Goog-Channel-Token`, and `X-Goog-Resource-ID` against stored subscription metadata and triggers delta sync
- Existing dev-mode ingestion buttons in `scout-ui/components/DevToolsPanel.tsx`
  - Annotate as deprecated
  - Do not remove in this phase

**Frontend:**

- `scout-ui/lib/connectors/google.ts`
  - Hooks: `useGoogleConnection()`, `useGoogleCalendars()`, `useGoogleSubscriptions()`, `useGoogleSyncRuns()`
- `scout-ui/app/settings/connections.tsx`
  - Self-service Google connection screen for the current member
  - Connect button launches the browser-based auth flow
  - Post-connect success returns to the app and refreshes connection state
  - Calendar selection, subscribe toggle, conflict policy, bidirectional toggle, disconnect button, and per-calendar last sync status live here
  - This route is the primary surface for `integrations.connect_google` because the credential is per-member
- `scout-ui/app/admin/connectors/google.tsx`
  - Family-wide operational screen
  - Shows connected members, watch health, last 20 sync runs, force sync action, and any sync errors
  - Does not attempt to drive another member's OAuth consent flow on their behalf
- Update `scout-ui/app/calendar/index.tsx`
  - Show badges for Google-originated events and Scout-published-to-Google events
- Update `scout-ui/components/DevToolsPanel.tsx`
  - Add a Superseded by real Google integration note next to dev ingestion buttons

**Publication to Hearth:**

Per the external data roadmap, Hearth consumes household anchor blocks via the existing iCal export at `/api/calendar/exports/upcoming`. This phase keeps the iCal export intact and additionally publishes Scout-created household anchor blocks to explicitly subscribed Google calendars so they show up on family members' personal calendars.

**Conflict resolution:**

- Default `google_wins` for events whose source of truth originated in Google.
- Default `scout_wins` for Scout-created household anchor blocks published outward.
- If `manual`, write a resolution item to the existing Action Inbox primitive.

**Rate limiting and retries:**

- Respect the Google Calendar API quotas configured for the project instead of hard-coding fixed QPS or QPD numbers.
- Implement exponential backoff for `403 usageLimits` and `429` responses.
- Prefer webhook-driven delta sync over polling whenever possible.

**Watch renewal:**

- Persist all watch metadata now.
- Implement `renew_expiring_watches()` now.
- If the repo already has a scheduler / worker pattern from operability sprint, wire watch renewal into it.
- If not, expose the renewal entry point and admin observability, and document the manual follow-up instead of inventing a second scheduling architecture.

**Acceptance criteria:**

- [ ] Migration applied; `oauth_credentials`, `google_calendar_subscriptions`, and `connector_sync_runs` exist with correct schema.
- [ ] Permission keys registered via migration.
- [ ] Backend: OAuth service, sync engine, and routes are written with happy-path and permission-denial tests.
- [ ] Unit tests cover token refresh, conflict handling, mapping writes, watch renewal, and `410 Gone` recovery to full sync.
- [ ] Integration test: mock Google Calendar API, run a full sync, assert `scout.events` rows match mocked Google events and `connector_mappings` has one row per pair.
- [ ] Frontend self-service connection flow works from `/settings/connections`. The connect button uses a browser-based auth session, not a WebView. Callback returns to Scout and shows success state.
- [ ] Subscribing to a calendar triggers an initial full sync and persists watch metadata.
- [ ] `smoke-tests/tests/google-calendar.spec.ts` covers unconnected state, mocked callback completion, and connected-state rendering. Network stubbing is acceptable.
- [ ] Webhook test: Google-style notification headers resolve a stored subscription and trigger delta sync logic.
- [ ] Revoke path exists and is tested: `POST /api/connectors/google/revoke` deactivates the OAuth credential and stops active watch channels where present.
- [ ] Dev-mode ingestion buttons remain available and are clearly deprecated.
- [ ] Arch check clean.
- [ ] `docs/private_launch.md` documents OAuth setup, env vars, scopes, callback URLs, webhook requirements, and watch renewal behavior.

**Out of scope (enforce):**

- YNAB, Apple Health, Nike Run Club.
- Google Contacts, Google Tasks, Gmail.
- Outlook / Apple Calendar.
- Google Workspace admin delegation.
- Publishing every Scout event to Google. This phase publishes only household anchor blocks and explicitly subscribed calendar content paths.
- A brand new scheduler architecture if one does not already exist.

**Estimated output:** 1 migration, ~15 backend files, ~8 frontend files, 1 smoke spec, 4 docs updates.

---

### Phase 3 - Family projects engine

**Goal:** give Scout first-class support for multi-week family efforts such as birthdays, trips, holidays, home projects, school events, and resets.

**Strategic note:** this phase ships the engine only. Built-in templates and content are explicitly deferred to Sprint 3B.

**Scope:**

**Schema** (migration `NNN_family_projects.sql`):

- New table `scout.project_templates`
  - `id`
  - `family_id` nullable, null means built-in global template in future
  - `name`
  - `description`
  - `category` enum [`birthday`, `holiday`, `trip`, `school_event`, `home_project`, `weekend_reset`, `custom`]
  - `estimated_duration_days` int nullable
  - `default_lead_time_days` int
  - `default_budget_cents` int nullable
  - `created_by_family_member_id` FK nullable
  - `is_active` boolean
  - `is_builtin` boolean default false
  - `created_at`
  - `updated_at`
- New table `scout.project_template_tasks`
  - `id`
  - `project_template_id` FK
  - `title`
  - `description`
  - `order_index` int
  - `relative_day_offset` int
  - `default_owner_role` text nullable
  - `estimated_duration_minutes` int nullable
  - `has_budget_impact` boolean
  - `has_grocery_impact` boolean
  - `created_at`
  - `updated_at`
- New table `scout.projects`
  - `id`
  - `family_id` FK
  - `project_template_id` FK nullable
  - `name`
  - `description`
  - `category`
  - `status` enum [`draft`, `active`, `paused`, `complete`, `cancelled`]
  - `start_date` date
  - `target_end_date` date nullable
  - `actual_end_date` date nullable
  - `budget_cents` int nullable
  - `actual_spent_cents` int nullable
  - `primary_owner_family_member_id` FK nullable
  - `created_by_family_member_id` FK
  - `created_at`
  - `updated_at`
- New table `scout.project_tasks`
  - `id`
  - `project_id` FK
  - `title`
  - `description`
  - `status` enum [`todo`, `in_progress`, `blocked`, `done`, `skipped`]
  - `owner_family_member_id` FK nullable
  - `due_date` date nullable
  - `estimated_duration_minutes` int nullable
  - `actual_duration_minutes` int nullable
  - `budget_cents` int nullable
  - `spent_cents` int nullable
  - `depends_on_project_task_id` FK nullable
  - `notes` text
  - `created_at`
  - `updated_at`
- New table `scout.project_milestones`
  - `id`
  - `project_id` FK
  - `name`
  - `target_date` date
  - `is_complete` boolean default false
  - `completed_at` timestamptz nullable
  - `order_index` int
  - `notes` text
  - `created_at`
  - `updated_at`
- New table `scout.project_budget_entries`
  - `id`
  - `project_id` FK
  - `project_task_id` FK nullable
  - `amount_cents` int
  - `kind` enum [`estimate`, `expense`, `refund`]
  - `vendor` text nullable
  - `notes` text
  - `recorded_at` timestamptz
  - `recorded_by_family_member_id` FK
  - `created_at`
  - `updated_at`
- Extend existing `scout.personal_tasks`
  - Add nullable `source_project_task_id` FK to `scout.project_tasks`
  - Add unique index on `source_project_task_id` where not null
  - This is the only link required. Do not add a reverse FK on `project_tasks`.
- Indexes
  - `(family_id, status) WHERE status IN ('active', 'draft')` on `projects`
  - `(project_id, status)` on `project_tasks`
  - `(project_id, target_date)` on `project_milestones`
- Permission keys
  - `projects.create` (admin, parent_peer, teen)
  - `projects.manage_own` (all tiers, owner-scoped)
  - `projects.manage_any` (admin, parent_peer)
  - `projects.view` (all tiers)
  - `project_tasks.update_assigned` (all tiers, only for tasks assigned to the actor)
  - `project_templates.manage` (admin, parent_peer)
  - `project_templates.view` (all tiers)

**Backend:**

- `backend/app/services/project_service.py`
  - Functions: `create_from_template`, `create_blank`, `add_task`, `complete_task`, `add_milestone`, `complete_milestone`, `add_budget_entry`, `instantiate_template_tasks`, `promote_project_task_to_personal_task`
  - `promote_project_task_to_personal_task` copies a project task into `personal_tasks` and sets `source_project_task_id`
  - Promotion is optional convenience. It is not the only way project tasks surface in Today.
- `backend/app/services/project_aggregation.py`
  - Functions: `list_active_projects(family_id)`, `list_active_projects_for_family_member(family_member_id)`, `project_health_summary(project_id)`, `list_due_project_tasks_for_today(family_member_id, family_id)`
- `backend/app/routes/projects.py`
  - `GET /api/projects?status=active`
  - `POST /api/projects`
  - `GET /api/projects/{id}`
  - `PATCH /api/projects/{id}`
  - `POST /api/projects/{id}/tasks`
  - `PATCH /api/projects/{id}/tasks/{task_id}`
  - `POST /api/projects/{id}/tasks/{task_id}/promote`
  - `POST /api/projects/{id}/milestones`
  - `POST /api/projects/{id}/budget`
  - `GET /api/projects/{id}/health`
- `backend/app/routes/project_templates.py`
  - Family-local template CRUD only
  - Built-in templates are readable if seeded later, but none are seeded in this phase
- Today aggregation
  - Update the Today backend path so due project tasks are queried directly from `project_tasks`
  - Promotion linkage may enrich the Today experience, but it must not be the sole data path
- AI tools
  - Add `create_project_from_template(family_id, project_template_id, start_date, name_override)`
  - Add `add_project_task(project_id, title, due_date, owner_family_member_id)`
  - Both are shared-write and confirmation required
  - Acceptance should verify tool count increases by 2 over current repo count, not assume a hard-coded absolute number

**Frontend:**

- `scout-ui/lib/projects.ts`
  - Hooks and API wrappers: `useProjects({status})`, `useProject(id)`, `useProjectHealth(id)`, `useCreateProject`, `useAddProjectTask`, etc.
- `scout-ui/app/projects/index.tsx`
  - Lists active projects for the family
  - Kid-tier users see only projects they own or projects with tasks assigned to them
- `scout-ui/app/projects/[id].tsx`
  - Tabs: Tasks, Milestones, Budget, Info
- `scout-ui/app/projects/new.tsx`
  - Create from template or blank project
- `scout-ui/app/admin/projects/index.tsx`
  - Tabs: All projects, Family templates, Health
- `scout-ui/app/today/index.tsx`
  - Add a Projects today card showing project tasks due today or overdue
  - Tap target routes to the project detail
  - This card is populated directly from project tasks, not only from promoted personal tasks

**Task-level permissions clarification:**

- Kids and other non-admin users may update the status and notes of project tasks assigned to them through `project_tasks.update_assigned`.
- That permission does not allow changing project ownership, reassigning tasks, editing budgets, or editing the overall project unless they also satisfy `projects.manage_own`.

**Acceptance criteria:**

- [ ] Migration applied: all six new project tables exist and `personal_tasks.source_project_task_id` is added.
- [ ] All seven permission keys are registered in `role_tiers` via migration.
- [ ] Backend services and routes are written with happy-path and permission-denial tests.
- [ ] Template instantiation test: create a template with five tasks, create a project from it, assert five `project_tasks` with correct due dates relative to `start_date`.
- [ ] AI tools added to registry and tool count increases by 2 over the current repo count.
- [ ] Frontend `/projects`, `/projects/{id}`, `/projects/new`, and `/admin/projects` render correctly.
- [ ] Permission gating verified: kid-tier sees only owned or assigned projects; assigned-task updates are limited to allowed fields.
- [ ] `smoke-tests/tests/projects.spec.ts` creates a blank project, adds tasks and a milestone and budget entry, marks a task complete, and asserts completion percentage updates on the list card.
- [ ] Today integration: a project task due today appears in the Projects today section even if it was never promoted into `personal_tasks`.
- [ ] Arch check clean.
- [ ] ERD: `docs/architecture/erd/family_projects.mmd`.
- [ ] Architecture diagram: `docs/architecture/diagrams/project_engine_flow.svg`.

**Out of scope (enforce):**

- Built-in project template content. Sprint 3B.
- Grocery impact automation.
- YNAB integration.
- Gantt view or dependency graphs.
- Recurring projects.
- Cross-family projects.

**Estimated output:** 1 migration, ~12 backend files, ~10 frontend files, 1 smoke spec, 4 docs updates.

---

## 5. Risks and trade-offs

- **Expo delivery semantics:** provider acceptance and provider handoff are not the same thing as device display. Manual validation on a physical device is required for end-to-end confidence.
- **Expo receipt timing:** receipt data can lag. This phase must persist ticket IDs and support receipt polling rather than assuming immediate final status.
- **Google OAuth verification:** calendar scopes can require OAuth verification for public launch. Private launch testing is fine, but production readiness needs to account for this.
- **Google webhook lifecycle:** watch channels expire and sync tokens can become invalid. This phase must persist enough state to renew watches and recover from `410 Gone` without corrupting local sync state.
- **Token encryption:** `SCOUT_OAUTH_ENCRYPTION_KEY` must remain stable. Any future key rotation needs a versioned migration path.
- **Project task promotion:** promoted personal tasks are convenience copies. They can drift from project tasks. The project task remains the source of truth.
- **Simple dependency model:** `depends_on_project_task_id` is intentionally minimal for v1.

---

## 6. Explicitly deferred (follow-up sprints)

Do not absorb any of these into this sprint.

- **Sprint 1B - Native iOS surfaces.** Widgets, Siri Shortcuts, lock screen surfaces.
- **Sprint 2B - YNAB OAuth integration.** Reuse Phase 2 patterns once proven.
- **Sprint 2C - Apple Health + Nike Run Club.** Separate effort.
- **Sprint 3B - Project templates content.** Birthday, holiday, trip, home project, school event, weekend reset, and related seed content.
- **Scheduler sprint.** If operability sprint did not already establish a shared scheduler / worker pattern, recurring automation for `poll_pending_push_receipts`, `renew_expiring_watches`, daily brief delivery, and other timed jobs belongs here. This sprint still ships the clean callable entry points and state models.
- **Push v2.** Rich notifications, actions, grouping, quiet hours, and snooze.

---

## 7. Amendments for Claude Code (consolidated)

These apply to all phases. If they conflict with earlier body text, these win.

- Treat §3 human-confirmed and machine-verifiable prerequisites differently.
- Do not claim to verify Apple portal or Google Cloud console state from repo state alone.
- No embedded WebView for Google OAuth. Use system browser / auth session flow.
- Do not store per-member Google calendar subscription and webhook lifecycle state in `connector_configs` JSON.
- `EXPO_ACCESS_TOKEN` is optional unless Expo push security is enabled.
- Automated tests may verify provider submission and receipt processing, but not physical-device display.
- Any referenced endpoint must actually be specified in this doc. If a referenced route is missing, add it before implementation starts.
- Any hard-coded tool count or test count in acceptance criteria should be translated into relative change against the current repo count at execution time.
- The dev-mode ingestion buttons are not removed in Phase 2.
- Built-in project templates are not seeded in Phase 3.
- If the repo already has a scheduler / worker pattern, use it. If not, expose clean entry points and observability, and leave recurring scheduling ownership to the scheduler sprint.
- Any request during this sprint to also do widgets, YNAB, HealthKit, template content, or a brand new scheduler architecture gets flagged back to Andrew instead of being absorbed silently.

---

## 8. Prompt for Claude Code to start Phase 1

Paste the following into Claude Code to begin:

> Read `SCOUT_EXPANSION_SPRINT_V2.md` in full, including §7 Amendments. Read `docs/architecture/ARCHITECTURE.md` from The Three Layers through Anti-Patterns. Verify only the machine-verifiable Phase 1 prerequisites in §3. If any machine-verifiable prerequisite is missing, halt and report the specific missing item. If any human-confirmed prerequisite is marked incomplete by Andrew, halt and report it. Otherwise create branch `sprint/expansion-phase-1-push-notifications` from `main`. Implement only Phase 1. Preserve the architecture contract. Do not use embedded stubs for missing external credentials. If the repo already has a scheduler or worker pattern, use it for push receipt polling entry points; otherwise expose the entry points cleanly and document the follow-up. Run `node scripts/architecture-check.js` before the `docs:` commit and record before / after WARN counts in the handoff. If any acceptance criterion cannot be met, stop and ask before proceeding. Do not start Phase 2 in the same session.
