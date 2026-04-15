/**
 * Roberts-family seed data for the Session 3 mock client.
 *
 * Aligned to the canonical contracts in `contracts.ts` (which match
 * backend/app/routes/canonical.py). The mock honors the *real* shape:
 * a thin `standalone_chores[]` + `weekly_items[]` list out of
 * /api/household/today, NOT the rich nested-block shape Block 1 used.
 *
 * Sourced from `family_chore_system.md`:
 *   - Sadie (13), Townes (10), River (8)
 *   - morning / after-school / evening routines with deadlines
 *   - ownership chores (Sadie unload, Townes table+sweep, River living-room)
 *   - Common Area Closeout odd/even rotation (Townes ODD, River EVEN)
 *   - Sadie-lead dog walks with Townes/River assistant rule
 *   - Saturday Power 60 + Backyard Poop Patrol (8-week rotation)
 *
 * Mutable state lives in `mockState` so postCompletion() can mark an
 * occurrence done and have subsequent reads reflect it.
 */

import {
  BlockAssignment,
  BlockStep,
  CalendarExport,
  CalendarExportsResponse,
  CompletionRequest,
  CompletionResponse,
  ConnectorListItem,
  ConnectorHealthItem,
  ConnectorsHealthResponse,
  ConnectorsResponse,
  ControlPlaneSummaryResponse,
  FamilyContextResponse,
  HouseholdBlock,
  HouseholdTodayResponse,
  MeResponse,
  OccurrenceStatus,
  RewardsCurrentWeekResponse,
  RewardsMember,
  TaskOccurrence,
} from "./contracts";

// ---------------------------------------------------------------------------
// Stable IDs (UUID-shaped strings — short, deterministic, easy in logs)
// ---------------------------------------------------------------------------

const FAMILY_ID = "fam-roberts";
const ANDREW = "mem-andrew";
const SALLY = "mem-sally";
const SADIE = "mem-sadie";
const TOWNES = "mem-townes";
const RIVER = "mem-river";

const FAMILY_TZ = "America/Chicago";

interface KidSeed {
  id: string;
  name: string;
  age: number;
}

const KIDS: KidSeed[] = [
  { id: SADIE, name: "Sadie", age: 13 },
  { id: TOWNES, name: "Townes", age: 10 },
  { id: RIVER, name: "River", age: 8 },
];

// ---------------------------------------------------------------------------
// Date helpers
// ---------------------------------------------------------------------------

function startOfToday(): Date {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d;
}

function todayAt(hour: number, minute: number): Date {
  const d = startOfToday();
  d.setHours(hour, minute, 0, 0);
  return d;
}

function isoLocal(d: Date): string {
  const pad = (n: number) => `${n}`.padStart(2, "0");
  const tz = -d.getTimezoneOffset();
  const sign = tz >= 0 ? "+" : "-";
  const tzH = pad(Math.floor(Math.abs(tz) / 60));
  const tzM = pad(Math.abs(tz) % 60);
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}:00${sign}${tzH}:${tzM}`
  );
}

function todayDateOnly(): string {
  const d = startOfToday();
  const pad = (n: number) => `${n}`.padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function mondayOfThisWeek(): string {
  const d = startOfToday();
  const day = d.getDay(); // 0 Sun .. 6 Sat
  const offset = day === 0 ? -6 : 1 - day;
  d.setDate(d.getDate() + offset);
  const pad = (n: number) => `${n}`.padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function sundayOfThisWeek(): string {
  const d = startOfToday();
  const day = d.getDay();
  const offset = day === 0 ? 0 : 7 - day;
  d.setDate(d.getDate() + offset);
  const pad = (n: number) => `${n}`.padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function isOddDayToday(): boolean {
  return new Date().getDate() % 2 === 1;
}

function isSaturday(): boolean {
  return new Date().getDay() === 6;
}

// ---------------------------------------------------------------------------
// Internal mutable state — owns blocks + standalone + weekly for the day
// so postCompletion can flip statuses and subsequent reads reflect them.
//
// Block representation is the canonical shape (assignments + steps) plus
// internal underscore-prefixed metadata used for daily-win bookkeeping
// and for synthesizing calendar-export start/end times.
// ---------------------------------------------------------------------------

interface MockOccurrence extends TaskOccurrence {
  /** Backed by an owner record — for daily-win bookkeeping. */
  __owner_id: string;
  /** Whether this occurrence counts toward the owning kid's Daily Win today. */
  __counts_for_daily_win: boolean;
}

interface MockBlockStep extends BlockStep {
  __owner_id: string;
}

interface MockBlockAssignment extends BlockAssignment {
  steps: MockBlockStep[];
  __counts_for_daily_win: boolean;
}

interface MockBlock extends HouseholdBlock {
  assignments: MockBlockAssignment[];
  /** Block window — used only to populate calendar export time ranges. */
  __starts_at: string;
  __ends_at: string;
}

interface MockState {
  blocks: MockBlock[];
  standalone: MockOccurrence[];
  weekly: MockOccurrence[];
}

let _state: MockState | null = null;

export function __resetMock(): void {
  _state = null;
}

function ensureState(): MockState {
  if (!_state) _state = buildInitialState();
  return _state;
}

let _occCounter = 0;
function newOccId(): string {
  _occCounter += 1;
  return `occ-${_occCounter.toString().padStart(4, "0")}`;
}

function makeOcc(args: {
  template_key: string;
  label: string;
  owner_id: string;
  owner_name: string;
  due: Date;
  counts_for_daily_win: boolean;
  block_label?: string;
  routine_key?: string;
}): MockOccurrence {
  const now = new Date();
  const status: OccurrenceStatus = now > args.due ? "late" : "open";
  return {
    task_occurrence_id: newOccId(),
    template_key: args.template_key,
    label: args.label,
    owner_family_member_id: args.owner_id,
    owner_name: args.owner_name,
    due_at: isoLocal(args.due),
    status,
    block_label: args.block_label ?? null,
    routine_key: args.routine_key ?? null,
    __owner_id: args.owner_id,
    __counts_for_daily_win: args.counts_for_daily_win,
  };
}

// ---------------------------------------------------------------------------
// Block builders. The canonical /api/household/today shape is
// {block_key, label, due_at, exported_to_calendar, assignments[]} where
// each assignment carries the kid's name and a steps[] checklist. The
// mock populates steps[] richly so the UI exercises a meaningful
// per-step completion path; the real backend currently emits empty
// steps[] and uses the assignment's routine_instance_id as the
// completable target.
// ---------------------------------------------------------------------------

function makeStep(args: { owner_id: string; label: string; due: Date }): MockBlockStep {
  const now = new Date();
  const status: OccurrenceStatus = now > args.due ? "late" : "open";
  return {
    task_occurrence_id: newOccId(),
    label: args.label,
    status,
    __owner_id: args.owner_id,
  };
}

function makeAssignment(args: {
  owner_id: string;
  owner_name: string;
  steps: MockBlockStep[];
  counts_for_daily_win?: boolean;
}): MockBlockAssignment {
  return {
    routine_instance_id: `asg-${args.owner_id}-${newOccId()}`,
    family_member_id: args.owner_id,
    member_name: args.owner_name,
    status: deriveAssignmentStatus(args.steps),
    steps: args.steps,
    __counts_for_daily_win: args.counts_for_daily_win ?? true,
  };
}

function deriveAssignmentStatus(steps: MockBlockStep[]): OccurrenceStatus {
  if (steps.length === 0) return "open";
  if (steps.every((s) => s.status === "complete")) return "complete";
  if (steps.some((s) => s.status === "late")) return "late";
  return "open";
}

function buildMorning(): MockBlock {
  const due = todayAt(7, 25);
  const sadie = makeAssignment({
    owner_id: SADIE,
    owner_name: "Sadie",
    steps: [
      "Get dressed",
      "Make bed",
      "Hygiene: brush teeth, deodorant, hair",
      "Breakfast + dish to sink/dishwasher",
      "Backpack check (homework / device / water bottle)",
      "Lunch check (packed or plan confirmed)",
    ].map((label) => makeStep({ owner_id: SADIE, label, due })),
  });
  const townes = makeAssignment({
    owner_id: TOWNES,
    owner_name: "Townes",
    steps: [
      "Get dressed",
      "Make bed",
      "Brush teeth",
      "Breakfast + dish away",
      "Backpack check (homework / water bottle)",
      "Shoes / coat at launch spot",
    ].map((label) => makeStep({ owner_id: TOWNES, label, due })),
  });
  const river = makeAssignment({
    owner_id: RIVER,
    owner_name: "River",
    steps: [
      "Get dressed (clothes chosen night before)",
      "Make bed (blanket up, pillow placed)",
      "Brush teeth",
      "Breakfast + dish away",
      "Backpack + shoes at launch spot",
    ].map((label) => makeStep({ owner_id: RIVER, label, due })),
  });
  return {
    block_key: "morning_routine",
    label: "Morning Routine",
    due_at: isoLocal(due),
    exported_to_calendar: true,
    assignments: [sadie, townes, river],
    __starts_at: isoLocal(todayAt(6, 45)),
    __ends_at: isoLocal(due),
  };
}

function buildAfterSchool(): MockBlock {
  const due = todayAt(17, 30);
  const odd = isOddDayToday();

  const sadie = makeAssignment({
    owner_id: SADIE,
    owner_name: "Sadie",
    steps: [
      "Snack (15 min max)",
      "Homework / Study (30-45 min)",
      "10-minute zone reset",
      "Dog walks led — Memphis + Willie",
    ].map((label) => makeStep({ owner_id: SADIE, label, due })),
  });

  const townesSteps = [
    "Snack (15 min max)",
    "Homework / Reading (25-35 min)",
    "10-minute zone reset",
  ];
  if (odd) townesSteps.push("Willie walk assistant (ODD day)");
  const townes = makeAssignment({
    owner_id: TOWNES,
    owner_name: "Townes",
    steps: townesSteps.map((label) => makeStep({ owner_id: TOWNES, label, due })),
  });

  const riverSteps = [
    "Snack (15 min max)",
    "Homework / Reading (15-25 min)",
    "10-minute zone reset",
  ];
  if (!odd) riverSteps.push("Willie walk assistant (EVEN day)");
  const river = makeAssignment({
    owner_id: RIVER,
    owner_name: "River",
    steps: riverSteps.map((label) => makeStep({ owner_id: RIVER, label, due })),
  });

  return {
    block_key: "afterschool_routine",
    label: "After School Closeout",
    due_at: isoLocal(due),
    exported_to_calendar: true,
    assignments: [sadie, townes, river],
    __starts_at: isoLocal(todayAt(15, 30)),
    __ends_at: isoLocal(due),
  };
}

function buildEvening(): MockBlock {
  // The block due_at is the latest of the per-kid evening cutoffs
  // (Sadie's 9:30) — the canonical contract carries one due_at per
  // block, so the per-kid drift collapses into the ordering the
  // operating surface presents.
  const sadieDue = todayAt(21, 30);
  const townesDue = todayAt(21, 0);
  const riverDue = todayAt(20, 30);

  const sadie = makeAssignment({
    owner_id: SADIE,
    owner_name: "Sadie",
    steps: [
      "Pack backpack for tomorrow",
      "Outfit set out",
      "Hygiene",
      "Devices to charging station",
      "Room reset",
    ].map((label) => makeStep({ owner_id: SADIE, label, due: sadieDue })),
  });
  const townes = makeAssignment({
    owner_id: TOWNES,
    owner_name: "Townes",
    steps: [
      "Pack backpack",
      "Outfit set out",
      "Brush teeth",
      "Devices to charging station",
      "Room reset",
    ].map((label) => makeStep({ owner_id: TOWNES, label, due: townesDue })),
  });
  const river = makeAssignment({
    owner_id: RIVER,
    owner_name: "River",
    steps: [
      "Outfit set out (parent check if needed)",
      "Backpack packed",
      "Brush teeth",
      "Devices to charging station",
      "Room reset (small scope)",
    ].map((label) => makeStep({ owner_id: RIVER, label, due: riverDue })),
  });

  return {
    block_key: "evening_routine",
    label: "Evening Reset",
    due_at: isoLocal(sadieDue),
    exported_to_calendar: true,
    assignments: [sadie, townes, river],
    __starts_at: isoLocal(todayAt(20, 0)),
    __ends_at: isoLocal(sadieDue),
  };
}

function buildOwnershipStandalone(): MockOccurrence[] {
  // Ownership chores live OUTSIDE a routine block. They show up under
  // standalone_chores in /api/household/today.
  return [
    makeOcc({
      template_key: "ownership_dishwasher_unload",
      label: "Sadie · Dishwasher Captain — unload",
      owner_id: SADIE,
      owner_name: "Sadie",
      due: todayAt(7, 10),
      counts_for_daily_win: true,
    }),
    makeOcc({
      template_key: "ownership_table_set",
      label: "Townes · Set table for dinner",
      owner_id: TOWNES,
      owner_name: "Townes",
      due: todayAt(18, 15),
      counts_for_daily_win: true,
    }),
    makeOcc({
      template_key: "ownership_table_clear",
      label: "Townes · Clear table after dinner",
      owner_id: TOWNES,
      owner_name: "Townes",
      due: todayAt(19, 45),
      counts_for_daily_win: true,
    }),
    makeOcc({
      template_key: "ownership_kitchen_sweep",
      label: "Townes · Quick sweep — kitchen / dining",
      owner_id: TOWNES,
      owner_name: "Townes",
      due: todayAt(20, 0),
      counts_for_daily_win: true,
    }),
    makeOcc({
      template_key: "ownership_living_room_reset",
      label: "River · Living Room Reset",
      owner_id: RIVER,
      owner_name: "River",
      due: todayAt(19, 30),
      counts_for_daily_win: true,
    }),
    // Rotating Common Area Closeout — only one of (Townes, River) today.
    isOddDayToday()
      ? makeOcc({
          template_key: "rotating_common_area_closeout",
          label: "Townes · Common Area Closeout (ODD day)",
          owner_id: TOWNES,
          owner_name: "Townes",
          due: todayAt(19, 30),
          counts_for_daily_win: true,
        })
      : makeOcc({
          template_key: "rotating_common_area_closeout",
          label: "River · Common Area Closeout (EVEN day)",
          owner_id: RIVER,
          owner_name: "River",
          due: todayAt(19, 30),
          counts_for_daily_win: true,
        }),
  ];
}

function buildWeeklyItems(): MockOccurrence[] {
  if (!isSaturday()) return [];
  const due = todayAt(11, 0);
  return [
    makeOcc({
      template_key: "weekly_power60_bathroom",
      label: "Sadie · Power 60 — Bathroom",
      owner_id: SADIE,
      owner_name: "Sadie",
      due,
      counts_for_daily_win: false,
    }),
    makeOcc({
      template_key: "weekly_power60_vacuum",
      label: "Townes · Power 60 — Vacuum bedroom + hallway",
      owner_id: TOWNES,
      owner_name: "Townes",
      due,
      counts_for_daily_win: false,
    }),
    makeOcc({
      template_key: "weekly_power60_dust",
      label: "River · Power 60 — Dust low surfaces",
      owner_id: RIVER,
      owner_name: "River",
      due,
      counts_for_daily_win: false,
    }),
    makeOcc({
      template_key: "weekly_backyard_poop_patrol",
      label: "Townes · Backyard Poop Patrol (River assistant)",
      owner_id: TOWNES,
      owner_name: "Townes",
      due,
      counts_for_daily_win: false,
    }),
  ];
}

function buildInitialState(): MockState {
  return {
    blocks: [buildMorning(), buildAfterSchool(), buildEvening()],
    standalone: buildOwnershipStandalone(),
    weekly: buildWeeklyItems(),
  };
}

// ---------------------------------------------------------------------------
// /api/me
// ---------------------------------------------------------------------------

export function mockMe(): MeResponse {
  return {
    user: {
      id: "acc-andrew",
      email: "andrew@roberts.local",
      full_name: "Andrew Roberts",
      role_tier_key: "PRIMARY_PARENT",
      family_member_id: ANDREW,
      feature_flags: {
        calendar_publish: false,
        greenlight_settlement: false,
        meal_planning: true,
      },
    },
    family: {
      id: FAMILY_ID,
      name: "Roberts",
      timezone: FAMILY_TZ,
    },
  };
}

// ---------------------------------------------------------------------------
// /api/family/context/current
// ---------------------------------------------------------------------------

export function mockFamilyContext(): FamilyContextResponse {
  return {
    family: { id: FAMILY_ID, name: "Roberts", timezone: FAMILY_TZ },
    date: todayDateOnly(),
    active_time_block: null,
    kids: KIDS.map((k) => ({
      family_member_id: k.id,
      name: k.name,
      age: k.age,
      role_tier_key: k.age >= 13 ? "TEEN" : "CHILD",
    })),
    household_rules: {
      one_owner_per_task: true,
      one_reminder_max: true,
    },
  };
}

// ---------------------------------------------------------------------------
// /api/household/today
// ---------------------------------------------------------------------------

function stripInternal(o: MockOccurrence): TaskOccurrence {
  const { __owner_id, __counts_for_daily_win, ...rest } = o;
  void __owner_id;
  void __counts_for_daily_win;
  return rest;
}

function stripBlockStep(s: MockBlockStep): BlockStep {
  const { __owner_id, ...rest } = s;
  void __owner_id;
  return rest;
}

function stripBlockAssignment(a: MockBlockAssignment): BlockAssignment {
  const { __counts_for_daily_win, ...rest } = a;
  void __counts_for_daily_win;
  return { ...rest, steps: a.steps.map(stripBlockStep) };
}

function stripBlock(b: MockBlock): HouseholdBlock {
  const { __starts_at, __ends_at, ...rest } = b;
  void __starts_at;
  void __ends_at;
  return { ...rest, assignments: b.assignments.map(stripBlockAssignment) };
}

export function mockHouseholdToday(): HouseholdTodayResponse {
  const state = ensureState();

  // Each routine assignment counts as one item toward the summary
  // (matching summarizeForKid in TodayHome and the canonical block
  // contract — assignments are the per-kid daily-win unit, not steps).
  const assignmentStatuses: OccurrenceStatus[] = state.blocks.flatMap((b) =>
    b.assignments.map((a) => a.status),
  );
  const flatStatuses: OccurrenceStatus[] = [
    ...state.standalone.map((o) => o.status),
    ...state.weekly.map((o) => o.status),
  ];
  const all = [...assignmentStatuses, ...flatStatuses];
  const due_count = all.filter((s) => s === "open" || s === "late").length;
  const completed_count = all.filter((s) => s === "complete").length;
  const late_count = all.filter((s) => s === "late").length;

  return {
    date: todayDateOnly(),
    summary: { due_count, completed_count, late_count },
    blocks: state.blocks.map(stripBlock),
    standalone_chores: state.standalone.map(stripInternal),
    weekly_items: state.weekly.map(stripInternal),
  };
}

// ---------------------------------------------------------------------------
// POST /api/household/completions
//
// Charter response is intentionally bare: four fields, no echo.
// ---------------------------------------------------------------------------

export function mockPostCompletion(req: CompletionRequest): CompletionResponse {
  const state = ensureState();
  const id = req.task_occurrence_id;

  // Standalone + weekly first (full TaskOccurrence rows).
  let flatTarget: MockOccurrence | undefined =
    state.standalone.find((o) => o.task_occurrence_id === id) ??
    state.weekly.find((o) => o.task_occurrence_id === id);
  if (flatTarget) {
    flatTarget.status = "complete";
    return {
      task_occurrence_id: id,
      status: "complete",
      daily_win_recomputed: flatTarget.__counts_for_daily_win,
      reward_preview_changed: flatTarget.__counts_for_daily_win,
    };
  }

  // Walk blocks → assignments → steps. The completable id can match
  // either a step's task_occurrence_id or — when steps[] is empty — the
  // assignment's routine_instance_id. Re-derive the assignment's status
  // from its steps after a flip so subsequent reads reflect "all done".
  for (const b of state.blocks) {
    for (const a of b.assignments) {
      if (a.steps.length === 0 && a.routine_instance_id === id) {
        a.status = "complete";
        return {
          task_occurrence_id: id,
          status: "complete",
          daily_win_recomputed: a.__counts_for_daily_win,
          reward_preview_changed: a.__counts_for_daily_win,
        };
      }
      const step = a.steps.find((s) => s.task_occurrence_id === id);
      if (step) {
        step.status = "complete";
        a.status = deriveAssignmentStatus(a.steps);
        return {
          task_occurrence_id: id,
          status: "complete",
          daily_win_recomputed: a.__counts_for_daily_win,
          reward_preview_changed: a.__counts_for_daily_win,
        };
      }
    }
  }

  // Unknown id — still echo the contract bare-response so optimistic
  // local mutation can settle without crashing.
  return {
    task_occurrence_id: id,
    status: "complete",
    daily_win_recomputed: false,
    reward_preview_changed: false,
  };
}

// ---------------------------------------------------------------------------
// /api/rewards/week/current
// ---------------------------------------------------------------------------

export function mockRewardsWeek(): RewardsCurrentWeekResponse {
  const state = ensureState();
  const baselines: Record<string, number> = {
    [SADIE]: 12.0,
    [TOWNES]: 9.0,
    [RIVER]: 7.0,
  };

  const dayIndex = Math.min(4, Math.max(0, new Date().getDay() - 1)); // Mon=0..Fri=4

  const members: RewardsMember[] = KIDS.map((k) => {
    const required = collectRequiredItems(state, k.id);
    const completed = required.filter((o) => o.status === "complete");
    const remaining = required.filter((o) => o.status !== "complete");
    // The new contract no longer carries per-item labels at the
    // daily-win-summary level — late items are surfaced via the
    // operating surface, not inside the rewards card. Keep the
    // miss_reasons list so the card's degraded mode stays useful but
    // populate it with the routine names that contain a late
    // assignment for this kid.
    const blocking = state.blocks
      .filter((b) =>
        b.assignments.some(
          (a) => a.family_member_id === k.id && a.status === "late",
        ),
      )
      .map((b) => b.label);

    // Pretend Mon..yesterday were wins; today reflects current state.
    let wins = dayIndex; // wins for prior weekdays
    const todayDone = required.length > 0 && remaining.length === 0;
    if (todayDone) wins += 1;

    const payout_percent =
      wins >= 5 ? 100 : wins === 4 ? 80 : wins === 3 ? 60 : 0;
    const baseline = baselines[k.id] ?? 0;
    return {
      family_member_id: k.id,
      name: k.name,
      baseline_allowance: baseline,
      daily_wins: wins,
      payout_percent,
      projected_payout: Math.round(((baseline * payout_percent) / 100) * 100) / 100,
      miss_reasons: blocking,
    };
  });

  return {
    period: {
      id: "period-current",
      start_date: mondayOfThisWeek(),
      end_date: sundayOfThisWeek(),
    },
    members,
    approval: { state: "draft" },
  };
}

/**
 * Collected daily-win-relevant items for a kid: each routine
 * assignment they own (counted as one) plus each daily-win-flagged
 * standalone chore. Returned as a uniform `{status}` shape so the
 * rewards builder can count completed/late/remaining without caring
 * whether the source was an assignment or a standalone occurrence.
 */
function collectRequiredItems(
  state: MockState,
  memberId: string,
): { status: OccurrenceStatus }[] {
  const fromBlocks = state.blocks
    .flatMap((b) => b.assignments)
    .filter((a) => a.family_member_id === memberId && a.__counts_for_daily_win)
    .map((a) => ({ status: a.status }));
  const fromStandalone = state.standalone
    .filter((o) => o.__owner_id === memberId && o.__counts_for_daily_win)
    .map((o) => ({ status: o.status }));
  return [...fromBlocks, ...fromStandalone];
}

// ---------------------------------------------------------------------------
// /api/connectors  +  /api/connectors/health
// ---------------------------------------------------------------------------

export function mockConnectors(): ConnectorsResponse {
  // Status vocabulary is the locked Session 2 set — see
  // backend/services/connectors/sync_persistence.py.
  const items: ConnectorListItem[] = [
    { connector_key: "google_calendar", label: "Google Calendar", status: "connected", last_sync_at: isoLocal(new Date()) },
    { connector_key: "hearth", label: "Hearth (display lane)", status: "connected", last_sync_at: isoLocal(new Date(Date.now() - 5 * 60_000)) },
    { connector_key: "greenlight", label: "Greenlight", status: "disconnected", last_sync_at: null },
    { connector_key: "rex", label: "Rex", status: "disconnected", last_sync_at: null },
    { connector_key: "ynab", label: "YNAB", status: "stale", last_sync_at: isoLocal(new Date(Date.now() - 24 * 60 * 60_000)) },
    { connector_key: "google_maps", label: "Google Maps", status: "decision_gated", last_sync_at: null },
    { connector_key: "apple_health", label: "Apple Health", status: "decision_gated", last_sync_at: null },
    { connector_key: "nike_run_club", label: "Nike Run Club", status: "decision_gated", last_sync_at: null },
  ];
  return { items };
}

export function mockConnectorsHealth(): ConnectorsHealthResponse {
  const within = (mins: number) => isoLocal(new Date(Date.now() - mins * 60_000));
  // Freshness vocabulary is locked: live | lagging | stale | unknown
  // (see backend/services/connectors/sync_persistence.py).
  const items: ConnectorHealthItem[] = [
    { connector_key: "google_calendar", healthy: true, freshness_state: "live", last_success_at: within(2), last_error_at: null, last_error_message: null },
    { connector_key: "hearth", healthy: true, freshness_state: "live", last_success_at: within(5), last_error_at: null, last_error_message: null },
    { connector_key: "greenlight", healthy: false, freshness_state: "unknown", last_success_at: null, last_error_at: null, last_error_message: "Not linked" },
    { connector_key: "rex", healthy: false, freshness_state: "unknown", last_success_at: null, last_error_at: null, last_error_message: "Not linked" },
    { connector_key: "ynab", healthy: true, freshness_state: "stale", last_success_at: within(45), last_error_at: null, last_error_message: null },
    { connector_key: "google_maps", healthy: false, freshness_state: "unknown", last_success_at: null, last_error_at: null, last_error_message: "Decision gated" },
    { connector_key: "apple_health", healthy: false, freshness_state: "unknown", last_success_at: null, last_error_at: null, last_error_message: "Decision gated" },
    { connector_key: "nike_run_club", healthy: false, freshness_state: "unknown", last_success_at: null, last_error_at: null, last_error_message: "Decision gated" },
  ];
  return { items };
}

// ---------------------------------------------------------------------------
// Calendar exports + control plane (still vapor — mock-only)
// ---------------------------------------------------------------------------

export function mockCalendarExports(): CalendarExportsResponse {
  // Convert the seeded routine blocks into anchor-block exports that
  // would publish to the family Google Calendar (and therefore the
  // Hearth display lane). We export ROUTINE BLOCKS only, never the
  // micro-tasks underneath — this is the documented strategy from the
  // external-data roadmap (Phase 2: "do not publish every micro-task as
  // a standalone calendar event"). Weekly items get a single export
  // when present (Saturday Power 60).
  const state = ensureState();

  const items: CalendarExport[] = [];

  for (const b of state.blocks) {
    items.push({
      calendar_export_id: `cal-${b.block_key}`,
      label: b.label,
      starts_at: b.__starts_at,
      ends_at: b.__ends_at,
      source_type: "routine_block",
      source_id: b.block_key,
      target: "google_calendar",
      hearth_visible: true,
    });
  }

  // Weekly items are emitted as a single Power-60 anchor export when
  // any are seeded for today (Saturdays only in the mock).
  if (state.weekly.length > 0) {
    const first = state.weekly[0];
    items.push({
      calendar_export_id: "cal-power-60",
      label: "Power 60",
      starts_at: first.due_at ?? isoLocal(new Date()),
      ends_at: first.due_at ?? isoLocal(new Date()),
      source_type: "weekly_event",
      source_id: "weekly-power-60",
      target: "google_calendar",
      hearth_visible: true,
    });
  }

  return { items };
}

export function mockControlPlaneSummary(): ControlPlaneSummaryResponse {
  // Aggregate the existing mocked connector + reward state into the
  // four buckets the charter pins. This stays consistent with what
  // mockConnectorsHealth() and mockRewardsWeek() return.
  const health = mockConnectorsHealth();
  let healthy = 0;
  let stale = 0;
  let error = 0;
  for (const h of health.items) {
    if (!h.healthy) {
      // unknown / explicit error → error bucket unless freshness flags
      // it as merely stale or lagging.
      if (h.freshness_state === "stale" || h.freshness_state === "lagging") {
        stale += 1;
      } else {
        error += 1;
      }
    } else if (h.freshness_state === "stale" || h.freshness_state === "lagging") {
      stale += 1;
    } else {
      healthy += 1;
    }
  }

  // Calendar export pending/failed counts mirror the calendar exports
  // mock — all routine_block exports are "published" once their
  // connector is healthy. We expose pending + failed both as zero
  // because the mock posts to Google Calendar successfully.
  const calendar_exports = { pending_count: 0, failed_count: 0 };

  // Sync job state: assume the calendar publisher is running once per
  // hour and is currently idle, while greenlight is errored because
  // the connector is not linked.
  const sync_jobs = { running_count: 0, failed_count: 1 };

  // Reward approval: one period in draft → one pending approval.
  const rewards = { pending_approval_count: 1 };

  return {
    connectors: { healthy_count: healthy, stale_count: stale, error_count: error },
    sync_jobs,
    calendar_exports,
    rewards,
  };
}
