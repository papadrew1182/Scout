/**
 * Session 3 published contracts.
 *
 * These types match the API shapes named in the Session 3 charter:
 *   GET  /api/me
 *   GET  /api/family/context/current
 *   GET  /api/household/today
 *   POST /api/household/completions
 *   GET  /api/rewards/week/current
 *   GET  /api/connectors
 *   GET  /api/connectors/health
 *   GET  /api/calendar/exports/upcoming
 *   GET  /api/control-plane/summary
 *
 * They are *exactly* the contracts the Session 3 frontend lane is
 * expected to consume. They will be served by the real backend once
 * Session 2 lands; until then `mockClient.ts` answers them locally
 * with the seed data in `mockData.ts`.
 *
 * No Session-3-only alternate contract is invented. If something here
 * is ambiguous it should be resolved by amending the charter, not by
 * shipping a different shape under the same name.
 */

// ---------------------------------------------------------------------------
// Common primitives
// ---------------------------------------------------------------------------

export type ISODateTime = string; // e.g. "2026-04-14T07:25:00-05:00"
export type ISODate = string;     // e.g. "2026-04-14"
export type UUID = string;
export type Cents = number;

export type RoleTier = "adult" | "child";

export interface PersonRef {
  member_id: UUID;
  first_name: string;
  role: RoleTier;
}

// ---------------------------------------------------------------------------
// /api/me
// ---------------------------------------------------------------------------

export interface MeResponse {
  member_id: UUID;
  family_id: UUID;
  first_name: string;
  last_name: string | null;
  role: RoleTier;
  family_name: string;
  // permissions surfaced for the operating surface.
  capabilities: {
    can_complete_for: UUID[];      // member_ids whose tasks this user may complete
    can_approve_payouts: boolean;
    can_view_control_plane: boolean;
  };
}

// ---------------------------------------------------------------------------
// /api/family/context/current
// ---------------------------------------------------------------------------

export interface FamilyContextResponse {
  family_id: UUID;
  family_name: string;
  timezone: string;
  members: Array<{
    member_id: UUID;
    first_name: string;
    last_name: string | null;
    role: RoleTier;
    is_active: boolean;
    birthdate: ISODate | null;
  }>;
  // Reward policy snapshot — kept thin on purpose. Full policy lives in
  // /api/rewards/week/current.
  reward_baselines: Record<UUID, Cents>;
}

// ---------------------------------------------------------------------------
// /api/household/today
// ---------------------------------------------------------------------------

/**
 * Status pill for a routine block or a single task occurrence.
 *
 * - `upcoming`   — start time hasn't arrived yet today
 * - `active`     — currently within the block window
 * - `due_soon`   — within the next 30 min of its deadline
 * - `late`       — past deadline, not yet complete
 * - `done`       — every task in the block is complete
 * - `blocked`    — explicitly blocked (e.g. assistant rule unmet)
 */
export type BlockStatus =
  | "upcoming"
  | "active"
  | "due_soon"
  | "late"
  | "done"
  | "blocked";

export type BlockKind =
  | "morning_routine"
  | "after_school_routine"
  | "evening_routine"
  | "ownership_chore"
  | "rotating_chore"
  | "weekly_event"      // Saturday Power 60, Backyard Poop Patrol
  | "dog_walks";

export type CompletionStatus = "pending" | "complete" | "missed" | "excused";

export interface StandardOfDone {
  label: string;          // short description
  detail?: string | null; // optional longer copy
}

export interface TaskOccurrence {
  occurrence_id: UUID;
  task_template_id: UUID | null;
  title: string;
  description: string | null;
  owner: PersonRef;
  assistants: PersonRef[];
  due_at: ISODateTime;
  /**
   * If this task belongs to a routine block, the block id; otherwise null
   * (e.g. ownership chores that stand alone outside a block).
   */
  block_id: UUID | null;
  status: CompletionStatus;
  late: boolean;
  // standards-of-done preview
  standards: StandardOfDone[];
  // any one-tap eligibility hint the UI can act on before the network
  one_tap_eligible: boolean;
}

export interface RoutineBlock {
  block_id: UUID;
  kind: BlockKind;
  title: string;            // "Morning Routine", "Power 60", etc.
  // human-readable scheduling window
  starts_at: ISODateTime | null;  // null for blocks with no fixed start
  due_at: ISODateTime;            // hard deadline used for late logic
  status: BlockStatus;
  // who this block applies to. Multiple if the block spans more than one
  // child (Common Area Closeout = Townes/River; Power 60 = all three).
  members: PersonRef[];
  occurrences: TaskOccurrence[];
  // optional "why is this blocked" explanation when status === "blocked"
  blocked_reason?: string | null;
  // notes for adults — e.g. "ODD day → Townes leads"
  note?: string | null;
}

export interface ChildDailyWinPreview {
  member_id: UUID;
  on_track: boolean;
  required_count: number;      // how many requirements the child has today
  completed_count: number;
  remaining_count: number;
  // explain the gap if not on track
  blocking_titles: string[];
}

export interface HouseholdTodayResponse {
  date: ISODate;
  generated_at: ISODateTime;
  blocks: RoutineBlock[];
  // standalone occurrences not tied to a block
  standalone_occurrences: TaskOccurrence[];
  daily_win_preview: ChildDailyWinPreview[];
}

// ---------------------------------------------------------------------------
// POST /api/household/completions
// ---------------------------------------------------------------------------

export interface CompletionRequest {
  occurrence_id: UUID;
  // The user marking it complete; backend validates against capabilities.
  completed_by_member_id: UUID;
  // Optional client-side timestamp; backend may override.
  completed_at?: ISODateTime;
  /**
   * Optional standards-of-done acknowledgements. Empty array means the
   * caller did not surface them; backend should still record the
   * completion.
   */
  acknowledged_standards?: number[]; // indices into TaskOccurrence.standards
  note?: string;
}

export interface CompletionResponse {
  occurrence_id: UUID;
  status: CompletionStatus;
  // Rewards may move; the response surfaces enough state for the
  // optimistic cache to refresh both Today and Rewards.
  daily_win_preview: ChildDailyWinPreview | null;
  // If completion changed a block-level status, the new block is echoed.
  updated_block: RoutineBlock | null;
}

// ---------------------------------------------------------------------------
// /api/rewards/week/current
// ---------------------------------------------------------------------------

export interface RewardWeekChild {
  member_id: UUID;
  first_name: string;
  baseline_cents: Cents;
  // Per-day Daily Win flags Mon..Fri (length 5). null = not yet decided.
  day_wins: Array<boolean | null>;
  win_count: number;        // count of true entries
  // 5/4/3/2-or-fewer → 100/80/60/0 percent
  payout_percent: number;
  payout_cents: Cents;
  // Strings the UI can use to explain a missed day
  missed_reasons: string[];
  // Approval state, used by the rewards approval sheet
  approval_status: "draft" | "ready_for_review" | "approved";
}

export interface RewardWeekResponse {
  week_start: ISODate; // Monday
  week_end: ISODate;   // Sunday
  children: RewardWeekChild[];
  // Family-level total for the week (sum of payout_cents).
  total_payout_cents: Cents;
}

// ---------------------------------------------------------------------------
// /api/connectors  +  /api/connectors/health
// ---------------------------------------------------------------------------

export type ConnectorId =
  | "google_calendar"
  | "ical_hearth"
  | "greenlight"
  | "rex"
  | "ynab"
  | "google_maps"
  | "apple_health"
  | "nike_run_club";

export interface Connector {
  id: ConnectorId;
  display_name: string;
  tier: 1 | 2 | 3 | 4;
  status: "not_linked" | "linked" | "syncing" | "error" | "disabled";
  scope_summary: string;
  // most recent meaningful event from this connector
  last_event_at: ISODateTime | null;
}

export interface ConnectorsResponse {
  connectors: Connector[];
}

export interface ConnectorHealth {
  id: ConnectorId;
  // overall health + freshness
  ok: boolean;
  last_sync_at: ISODateTime | null;
  last_sync_status: "success" | "partial" | "error" | "never";
  freshness_seconds: number | null; // age of last sync; null = never synced
  message: string | null;           // operator-facing detail
}

export interface ConnectorsHealthResponse {
  connectors: ConnectorHealth[];
  generated_at: ISODateTime;
}

// ---------------------------------------------------------------------------
// /api/calendar/exports/upcoming
// ---------------------------------------------------------------------------

export interface CalendarExport {
  export_id: UUID;
  title: string;          // e.g. "Morning Routine"
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
// /api/control-plane/summary
// ---------------------------------------------------------------------------

export interface ControlPlaneSummaryResponse {
  generated_at: ISODateTime;
  // Rolled-up health
  household_status: "healthy" | "warning" | "critical";
  // Connector health snapshot keyed by id (subset of full health response)
  connectors: ConnectorHealth[];
  // Sync orchestration view
  sync_jobs: Array<{
    job_id: UUID;
    name: string;
    status: "idle" | "running" | "error";
    last_run_at: ISODateTime | null;
    next_run_at: ISODateTime | null;
    error_message: string | null;
  }>;
  // Publication view (Hearth lane via calendar exports)
  publications: Array<{
    surface: "hearth_calendar_lane";
    last_published_at: ISODateTime | null;
    pending_count: number;
    failed_count: number;
  }>;
  // Notification rules summary
  notifications: {
    rules_active: number;
    deliveries_24h: number;
    failures_24h: number;
  };
}

// ---------------------------------------------------------------------------
// Client interface
// ---------------------------------------------------------------------------

/**
 * Single client surface every Session 3 hook depends on. mockClient.ts
 * implements it against in-memory data; realClient.ts wraps fetch().
 */
export interface ScoutClient {
  getMe(): Promise<MeResponse>;
  getFamilyContext(): Promise<FamilyContextResponse>;
  getHouseholdToday(): Promise<HouseholdTodayResponse>;
  postCompletion(body: CompletionRequest): Promise<CompletionResponse>;
  getRewardsWeek(): Promise<RewardWeekResponse>;
  getConnectors(): Promise<ConnectorsResponse>;
  getConnectorsHealth(): Promise<ConnectorsHealthResponse>;
  getCalendarExports(): Promise<CalendarExportsResponse>;
  getControlPlaneSummary(): Promise<ControlPlaneSummaryResponse>;
}
