/**
 * Session 3 published contracts — aligned to backend/app/routes/canonical.py
 * (Session 2 commit ad912e7) and the Session 3 charter rules pinned in the
 * Block 2 prompt:
 *
 *   GET  /api/me                        → {user, family}
 *   GET  /api/family/context/current    → {family, date, active_time_block, kids[], household_rules}
 *   GET  /api/household/today           → {date, summary, blocks[], standalone_chores[], weekly_items[]}
 *   POST /api/household/completions     → {task_occurrence_id, status, daily_win_recomputed, reward_preview_changed}
 *   GET  /api/rewards/week/current      → {period|null, members[], approval}
 *   GET  /api/connectors                → {items[]}
 *   GET  /api/connectors/health         → {items[]}
 *   GET  /api/calendar/exports/upcoming → (not yet shipped — mock-only)
 *   GET  /api/control-plane/summary     → (not yet shipped — mock-only)
 *
 * The completion response is intentionally bare. There is no `updated_block`
 * and no `daily_win_preview` echo. The frontend must invalidate / refetch
 * householdToday + rewardsWeek after a successful completion if it wants
 * fresh derived state.
 */

// ---------------------------------------------------------------------------
// Common primitives
// ---------------------------------------------------------------------------

export type ISODateTime = string;
export type ISODate = string;
export type UUID = string;

/**
 * Canonical role tier keys from public.role_tiers (widened in migration 022).
 * `parent`-tier privileges = PRIMARY_PARENT or PARENT.
 */
export type RoleTierKey =
  | "PRIMARY_PARENT"
  | "PARENT"
  | "TEEN"
  | "CHILD"
  | "YOUNG_CHILD"
  | "DISPLAY_ONLY";

export function isParentTier(role: RoleTierKey | string | null | undefined): boolean {
  return role === "PRIMARY_PARENT" || role === "PARENT";
}

export type CompletionMode = "manual" | "auto" | "parent_override" | "ai_recorded";

// ---------------------------------------------------------------------------
// GET /api/me
// ---------------------------------------------------------------------------

export interface MeUser {
  id: UUID | null;
  email: string | null;
  full_name: string;
  role_tier_key: RoleTierKey;
  family_member_id: UUID;
  feature_flags: {
    calendar_publish: boolean;
    greenlight_settlement: boolean;
    meal_planning: boolean;
  };
}

export interface MeFamily {
  id: UUID;
  name: string;
  timezone: string;
}

export interface MeResponse {
  user: MeUser;
  family: MeFamily;
}

// ---------------------------------------------------------------------------
// GET /api/family/context/current
// ---------------------------------------------------------------------------

export interface ActiveTimeBlock {
  id: UUID | null;
  block_key: string;
  label: string;
  starts_at: ISODateTime;
  ends_at: ISODateTime;
  status: "upcoming" | "active" | "closed";
}

export interface FamilyKid {
  family_member_id: UUID;
  name: string;
  age: number | null;
  role_tier_key: RoleTierKey;
}

export interface FamilyContextResponse {
  family: MeFamily;
  date: ISODate;
  active_time_block: ActiveTimeBlock | null;
  kids: FamilyKid[];
  /**
   * Free-form household rules. Charter ships at least:
   *   one_owner_per_task: boolean
   *   one_reminder_max:  boolean
   * but the bag is open-ended.
   */
  household_rules: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// GET /api/household/today
// ---------------------------------------------------------------------------

/**
 * Status string from scout.v_household_today: backend uses `open`, `late`,
 * `complete`, `excused`. We accept all four.
 */
export type OccurrenceStatus = "open" | "complete" | "late" | "excused";

/**
 * Single occurrence row as it comes out of v_household_today. The shape is
 * deliberately flat — no nested owner ref, no embedded standards.
 */
export interface TaskOccurrence {
  task_occurrence_id: UUID;
  template_key: string | null;
  label: string;
  owner_family_member_id: UUID | null;
  owner_name: string | null;
  due_at: ISODateTime | null;
  status: OccurrenceStatus;
  /** Optional block label string the backend may attach (e.g. "Morning Routine") */
  block_label?: string | null;
  /** Optional grouping key set by the backend for routine block membership */
  routine_key?: string | null;
}

/**
 * Block-level group (routine block, weekly item). Shape kept thin to match
 * canonical.py — `blocks[]` is empty until the legacy → scout backfill runs,
 * but the contract keeps the key so Session 3 can render against it.
 */
export interface HouseholdBlock {
  block_key: string;
  label: string;
  starts_at: ISODateTime | null;
  ends_at: ISODateTime | null;
  due_at: ISODateTime | null;
  status: "upcoming" | "active" | "due_soon" | "late" | "done" | "blocked";
  member_family_member_ids: UUID[];
  occurrences: TaskOccurrence[];
  note?: string | null;
}

export interface HouseholdTodaySummary {
  due_count: number;
  completed_count: number;
  late_count: number;
}

export interface HouseholdTodayResponse {
  date: ISODate;
  summary: HouseholdTodaySummary;
  blocks: HouseholdBlock[];
  standalone_chores: TaskOccurrence[];
  weekly_items: TaskOccurrence[];
}

// ---------------------------------------------------------------------------
// POST /api/household/completions
// ---------------------------------------------------------------------------

export interface CompletionRequest {
  task_occurrence_id: UUID;
  completed_by_family_member_id: UUID;
  completed_at?: ISODateTime;
  completion_mode?: CompletionMode;
  notes?: string;
}

/**
 * Charter-pinned response. Four fields, no echo data.
 *
 * `daily_win_recomputed` and `reward_preview_changed` are flags. When either
 * is true, the frontend must refetch the affected slice. When both are false
 * the frontend can keep its optimistic local mutation.
 */
export interface CompletionResponse {
  task_occurrence_id: UUID;
  status: "complete";
  daily_win_recomputed: boolean;
  reward_preview_changed: boolean;
}

// ---------------------------------------------------------------------------
// GET /api/rewards/week/current
// ---------------------------------------------------------------------------

export interface RewardsPeriod {
  id: UUID;
  start_date: ISODate;
  end_date: ISODate;
}

export interface RewardsMember {
  family_member_id: UUID;
  name: string;
  /** Dollars (not cents) — matches canonical.py float division. */
  baseline_allowance: number;
  /** Whole number of daily wins earned so far this period. */
  daily_wins: number;
  payout_percent: number;
  projected_payout: number;
  miss_reasons: string[];
}

export interface RewardsApproval {
  state: "draft" | "ready_for_review" | "approved";
}

export interface RewardsCurrentWeekResponse {
  period: RewardsPeriod | null;
  members: RewardsMember[];
  approval: RewardsApproval;
}

// ---------------------------------------------------------------------------
// GET /api/connectors
// ---------------------------------------------------------------------------

export type ConnectorStatus =
  | "connected"
  | "disconnected"
  | "error"
  | "decision_gated"
  | "pending";

export interface ConnectorListItem {
  connector_key: string;
  label: string;
  status: ConnectorStatus | string;
  last_sync_at: ISODateTime | null;
}

export interface ConnectorsResponse {
  items: ConnectorListItem[];
}

// ---------------------------------------------------------------------------
// GET /api/connectors/health
// ---------------------------------------------------------------------------

export type ConnectorFreshness =
  | "fresh"
  | "stale"
  | "very_stale"
  | "never_synced"
  | "unknown";

export interface ConnectorHealthItem {
  connector_key: string;
  healthy: boolean;
  freshness_state: ConnectorFreshness | string;
  last_success_at: ISODateTime | null;
  last_error_at: ISODateTime | null;
  last_error_message: string | null;
}

export interface ConnectorsHealthResponse {
  items: ConnectorHealthItem[];
}

// ---------------------------------------------------------------------------
// GET /api/calendar/exports/upcoming   (NOT YET SHIPPED — mock-only)
// ---------------------------------------------------------------------------

export interface CalendarExport {
  export_id: UUID;
  title: string;
  starts_at: ISODateTime;
  ends_at: ISODateTime;
  google_calendar_event_id: string | null;
  publication_status: "pending" | "published" | "failed";
  failure_reason?: string | null;
}

export interface CalendarExportsResponse {
  generated_at: ISODateTime;
  upcoming: CalendarExport[];
}

// ---------------------------------------------------------------------------
// GET /api/control-plane/summary   (NOT YET SHIPPED — mock-only)
// ---------------------------------------------------------------------------

export interface ControlPlaneSummaryResponse {
  generated_at: ISODateTime;
  household_status: "healthy" | "warning" | "critical";
  connectors: ConnectorHealthItem[];
  sync_jobs: Array<{
    job_id: UUID;
    name: string;
    status: "idle" | "running" | "error";
    last_run_at: ISODateTime | null;
    next_run_at: ISODateTime | null;
    error_message: string | null;
  }>;
  publications: Array<{
    surface: "hearth_calendar_lane";
    last_published_at: ISODateTime | null;
    pending_count: number;
    failed_count: number;
  }>;
  notifications: {
    rules_active: number;
    deliveries_24h: number;
    failures_24h: number;
  };
}

// ---------------------------------------------------------------------------
// Standards-of-done — frontend-side detail layer
//
// The household/today contract ships only `template_key + label`. The
// standards from family_chore_system.md are not in the API. We keep them in
// the frontend so the CompletionSheet can show meaningful done-detail
// without inventing backend fields.
// ---------------------------------------------------------------------------

export interface StandardOfDone {
  label: string;
}

export const STANDARDS_BY_TEMPLATE_KEY: Record<string, StandardOfDone[]> = {
  // Room reset (per family_chore_system.md → "Room Reset = DONE when")
  evening_room_reset: [
    { label: "Floor mostly clear (no loose clothes/toys)" },
    { label: "Clothes in hamper" },
    { label: "Dishes/cups removed" },
    { label: "Trash in trash can" },
    { label: "Bed made (simple is fine)" },
  ],
  // Common Area Closeout (rotating chore — Townes/River)
  rotating_common_area_closeout: [
    { label: "Cups/plates/trash moved to kitchen" },
    { label: "Blankets folded to basket" },
    { label: "Toys/items put in bins" },
    { label: "Remotes returned" },
    { label: "Floor clear enough a robot vacuum could run" },
  ],
  // Living Room Reset (River ownership chore)
  ownership_living_room_reset: [
    { label: "Blankets folded to basket" },
    { label: "Toys to bins" },
    { label: "Cups/dishes to kitchen" },
  ],
  // Trash (used by ownership / sweep)
  ownership_kitchen_trash: [
    { label: "Kitchen can checked; if ~75% full → taken out" },
    { label: "Bag tied, taken to outdoor bin" },
    { label: "New bag installed" },
  ],
  // Dog walks (Sadie lead) — done-detail comes from the chore doc
  afterschool_dog_walks: [
    { label: "Memphis walked (Sadie handling) 15-20 min" },
    { label: "Willie walked 10-15 min (assistant rule applies)" },
    { label: "Leashes/harnesses returned to hook" },
    { label: "Paws wiped if wet" },
    { label: "Poop bags restocked if low" },
  ],
  // Backyard Poop Patrol (weekly — Townes owner / River assistant on
  // current rotation; rotation flips every 8 weeks per the doc).
  weekly_backyard_poop_patrol: [
    { label: "Gloves on / grab bags or scooper" },
    { label: "Pick up all visible poop" },
    { label: "Tie bag + outdoor bin" },
    { label: "Put tools away" },
  ],
};

export function standardsForTemplate(template_key: string | null | undefined): StandardOfDone[] {
  if (!template_key) return [];
  return STANDARDS_BY_TEMPLATE_KEY[template_key] ?? [];
}

// ---------------------------------------------------------------------------
// Client interface
// ---------------------------------------------------------------------------

export interface ScoutClient {
  getMe(): Promise<MeResponse>;
  getFamilyContext(): Promise<FamilyContextResponse>;
  getHouseholdToday(): Promise<HouseholdTodayResponse>;
  postCompletion(body: CompletionRequest): Promise<CompletionResponse>;
  getRewardsWeek(): Promise<RewardsCurrentWeekResponse>;
  getConnectors(): Promise<ConnectorsResponse>;
  getConnectorsHealth(): Promise<ConnectorsHealthResponse>;
  getCalendarExports(): Promise<CalendarExportsResponse>;
  getControlPlaneSummary(): Promise<ControlPlaneSummaryResponse>;
}
