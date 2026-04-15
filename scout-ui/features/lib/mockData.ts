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
// Internal mutable state — owns occurrences for the day so postCompletion
// can flip them and subsequent reads reflect the new status.
// ---------------------------------------------------------------------------

interface MockOccurrence extends TaskOccurrence {
  /** Backed by an owner record — for daily-win bookkeeping. */
  __owner_id: string;
  /** Whether this occurrence counts toward the owning kid's Daily Win today. */
  __counts_for_daily_win: boolean;
}

interface MockState {
  blocks: HouseholdBlock[];
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
// Block builders. The real backend will populate `blocks[]` once the
// scout backfill runs. The mock fills it directly so the UI exercises the
// block path. Block contents share the same MockOccurrence rows for
// completion bookkeeping.
// ---------------------------------------------------------------------------

function buildMorning(): { block: HouseholdBlock; occs: MockOccurrence[] } {
  const due = todayAt(7, 25);
  const items: MockOccurrence[] = [];
  // Sadie
  for (const label of [
    "Get dressed",
    "Make bed",
    "Hygiene: brush teeth, deodorant, hair",
    "Breakfast + dish to sink/dishwasher",
    "Backpack check (homework / device / water bottle)",
    "Lunch check (packed or plan confirmed)",
  ]) {
    items.push(
      makeOcc({
        template_key: "morning_routine",
        label: `Sadie · ${label}`,
        owner_id: SADIE,
        owner_name: "Sadie",
        due,
        counts_for_daily_win: true,
        block_label: "Morning Routine",
        routine_key: "morning_routine",
      }),
    );
  }
  // Townes
  for (const label of [
    "Get dressed",
    "Make bed",
    "Brush teeth",
    "Breakfast + dish away",
    "Backpack check (homework / water bottle)",
    "Shoes / coat at launch spot",
  ]) {
    items.push(
      makeOcc({
        template_key: "morning_routine",
        label: `Townes · ${label}`,
        owner_id: TOWNES,
        owner_name: "Townes",
        due,
        counts_for_daily_win: true,
        block_label: "Morning Routine",
        routine_key: "morning_routine",
      }),
    );
  }
  // River
  for (const label of [
    "Get dressed (clothes chosen night before)",
    "Make bed (blanket up, pillow placed)",
    "Brush teeth",
    "Breakfast + dish away",
    "Backpack + shoes at launch spot",
  ]) {
    items.push(
      makeOcc({
        template_key: "morning_routine",
        label: `River · ${label}`,
        owner_id: RIVER,
        owner_name: "River",
        due,
        counts_for_daily_win: true,
        block_label: "Morning Routine",
        routine_key: "morning_routine",
      }),
    );
  }
  return {
    block: {
      block_key: "morning_routine",
      label: "Morning Routine",
      starts_at: isoLocal(todayAt(6, 45)),
      ends_at: isoLocal(due),
      due_at: isoLocal(due),
      status: deriveBlockStatus(items, due),
      member_family_member_ids: KIDS.map((k) => k.id),
      occurrences: items,
      note: "Due 7:25 on school days.",
    },
    occs: items,
  };
}

function buildAfterSchool(): { block: HouseholdBlock; occs: MockOccurrence[] } {
  const due = todayAt(17, 30);
  const odd = isOddDayToday();
  const items: MockOccurrence[] = [];

  // Sadie
  items.push(
    makeOcc({
      template_key: "afterschool_routine",
      label: "Sadie · Snack (15 min max)",
      owner_id: SADIE,
      owner_name: "Sadie",
      due,
      counts_for_daily_win: true,
      block_label: "After School Closeout",
      routine_key: "afterschool_routine",
    }),
    makeOcc({
      template_key: "afterschool_routine",
      label: "Sadie · Homework / Study (30-45 min)",
      owner_id: SADIE,
      owner_name: "Sadie",
      due,
      counts_for_daily_win: true,
      block_label: "After School Closeout",
    }),
    makeOcc({
      template_key: "afterschool_routine",
      label: "Sadie · 10-minute zone reset",
      owner_id: SADIE,
      owner_name: "Sadie",
      due,
      counts_for_daily_win: true,
      block_label: "After School Closeout",
    }),
    makeOcc({
      template_key: "afterschool_dog_walks",
      label: "Sadie · Dog walks led — Memphis + Willie",
      owner_id: SADIE,
      owner_name: "Sadie",
      due,
      counts_for_daily_win: true,
      block_label: "After School Closeout",
    }),
  );

  // Townes
  items.push(
    makeOcc({
      template_key: "afterschool_routine",
      label: "Townes · Snack (15 min max)",
      owner_id: TOWNES,
      owner_name: "Townes",
      due,
      counts_for_daily_win: true,
      block_label: "After School Closeout",
    }),
    makeOcc({
      template_key: "afterschool_routine",
      label: "Townes · Homework / Reading (25-35 min)",
      owner_id: TOWNES,
      owner_name: "Townes",
      due,
      counts_for_daily_win: true,
      block_label: "After School Closeout",
    }),
    makeOcc({
      template_key: "afterschool_routine",
      label: "Townes · 10-minute zone reset",
      owner_id: TOWNES,
      owner_name: "Townes",
      due,
      counts_for_daily_win: true,
      block_label: "After School Closeout",
    }),
  );
  if (odd) {
    items.push(
      makeOcc({
        template_key: "afterschool_dog_walks",
        label: "Townes · Willie walk assistant (ODD day)",
        owner_id: TOWNES,
        owner_name: "Townes",
        due,
        counts_for_daily_win: true,
        block_label: "After School Closeout",
      }),
    );
  }

  // River
  items.push(
    makeOcc({
      template_key: "afterschool_routine",
      label: "River · Snack (15 min max)",
      owner_id: RIVER,
      owner_name: "River",
      due,
      counts_for_daily_win: true,
      block_label: "After School Closeout",
    }),
    makeOcc({
      template_key: "afterschool_routine",
      label: "River · Homework / Reading (15-25 min)",
      owner_id: RIVER,
      owner_name: "River",
      due,
      counts_for_daily_win: true,
      block_label: "After School Closeout",
    }),
    makeOcc({
      template_key: "afterschool_routine",
      label: "River · 10-minute zone reset",
      owner_id: RIVER,
      owner_name: "River",
      due,
      counts_for_daily_win: true,
      block_label: "After School Closeout",
    }),
  );
  if (!odd) {
    items.push(
      makeOcc({
        template_key: "afterschool_dog_walks",
        label: "River · Willie walk assistant (EVEN day)",
        owner_id: RIVER,
        owner_name: "River",
        due,
        counts_for_daily_win: true,
        block_label: "After School Closeout",
      }),
    );
  }

  return {
    block: {
      block_key: "afterschool_routine",
      label: "After School Closeout",
      starts_at: isoLocal(todayAt(15, 30)),
      ends_at: isoLocal(due),
      due_at: isoLocal(due),
      status: deriveBlockStatus(items, due),
      member_family_member_ids: KIDS.map((k) => k.id),
      occurrences: items,
      note: odd
        ? "ODD day → Townes assists Sadie on Willie's walk."
        : "EVEN day → River assists Sadie on Willie's walk.",
    },
    occs: items,
  };
}

function buildEvening(): { block: HouseholdBlock; occs: MockOccurrence[] } {
  const sadieDue = todayAt(21, 30);
  const townesDue = todayAt(21, 0);
  const riverDue = todayAt(20, 30);
  const items: MockOccurrence[] = [];

  // Sadie
  for (const label of ["Pack backpack for tomorrow", "Outfit set out", "Hygiene", "Devices to charging station"]) {
    items.push(
      makeOcc({
        template_key: "evening_routine",
        label: `Sadie · ${label}`,
        owner_id: SADIE,
        owner_name: "Sadie",
        due: sadieDue,
        counts_for_daily_win: true,
        block_label: "Evening Reset",
      }),
    );
  }
  items.push(
    makeOcc({
      template_key: "evening_room_reset",
      label: "Sadie · Room reset",
      owner_id: SADIE,
      owner_name: "Sadie",
      due: sadieDue,
      counts_for_daily_win: true,
      block_label: "Evening Reset",
    }),
  );

  // Townes
  for (const label of ["Pack backpack", "Outfit set out", "Brush teeth", "Devices to charging station"]) {
    items.push(
      makeOcc({
        template_key: "evening_routine",
        label: `Townes · ${label}`,
        owner_id: TOWNES,
        owner_name: "Townes",
        due: townesDue,
        counts_for_daily_win: true,
        block_label: "Evening Reset",
      }),
    );
  }
  items.push(
    makeOcc({
      template_key: "evening_room_reset",
      label: "Townes · Room reset",
      owner_id: TOWNES,
      owner_name: "Townes",
      due: townesDue,
      counts_for_daily_win: true,
      block_label: "Evening Reset",
    }),
  );

  // River
  for (const label of [
    "Outfit set out (parent check if needed)",
    "Backpack packed",
    "Brush teeth",
    "Devices to charging station",
  ]) {
    items.push(
      makeOcc({
        template_key: "evening_routine",
        label: `River · ${label}`,
        owner_id: RIVER,
        owner_name: "River",
        due: riverDue,
        counts_for_daily_win: true,
        block_label: "Evening Reset",
      }),
    );
  }
  items.push(
    makeOcc({
      template_key: "evening_room_reset",
      label: "River · Room reset (small scope)",
      owner_id: RIVER,
      owner_name: "River",
      due: riverDue,
      counts_for_daily_win: true,
      block_label: "Evening Reset",
    }),
  );

  return {
    block: {
      block_key: "evening_routine",
      label: "Evening Reset",
      starts_at: isoLocal(todayAt(20, 0)),
      ends_at: isoLocal(sadieDue),
      due_at: isoLocal(sadieDue),
      status: deriveBlockStatus(items, sadieDue),
      member_family_member_ids: KIDS.map((k) => k.id),
      occurrences: items,
      note: "River → 8:30, Townes → 9:00, Sadie → 9:30.",
    },
    occs: items,
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

function deriveBlockStatus(occs: TaskOccurrence[], due: Date): HouseholdBlock["status"] {
  if (occs.length === 0) return "upcoming";
  const allDone = occs.every((o) => o.status === "complete");
  if (allDone) return "done";
  const now = new Date();
  if (now > due) return "late";
  if (due.getTime() - now.getTime() <= 30 * 60_000) return "due_soon";
  return now > new Date(due.getTime() - 6 * 60 * 60_000) ? "active" : "upcoming";
}

function buildInitialState(): MockState {
  const morning = buildMorning();
  const afterschool = buildAfterSchool();
  const evening = buildEvening();
  const standalone = buildOwnershipStandalone();
  const weekly = buildWeeklyItems();

  return {
    blocks: [morning.block, afterschool.block, evening.block],
    standalone,
    weekly,
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

export function mockHouseholdToday(): HouseholdTodayResponse {
  const state = ensureState();
  const allOccs: MockOccurrence[] = [
    ...state.blocks.flatMap((b) => b.occurrences as MockOccurrence[]),
    ...state.standalone,
    ...state.weekly,
  ];
  const due_count = allOccs.filter((o) => o.status === "open" || o.status === "late").length;
  const completed_count = allOccs.filter((o) => o.status === "complete").length;
  const late_count = allOccs.filter((o) => o.status === "late").length;

  return {
    date: todayDateOnly(),
    summary: { due_count, completed_count, late_count },
    blocks: state.blocks.map((b) => ({
      ...b,
      occurrences: (b.occurrences as MockOccurrence[]).map(stripInternal),
    })),
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
  let target: MockOccurrence | undefined;

  for (const b of state.blocks) {
    target = (b.occurrences as MockOccurrence[]).find(
      (o) => o.task_occurrence_id === req.task_occurrence_id,
    );
    if (target) break;
  }
  if (!target) {
    target = state.standalone.find((o) => o.task_occurrence_id === req.task_occurrence_id);
  }
  if (!target) {
    target = state.weekly.find((o) => o.task_occurrence_id === req.task_occurrence_id);
  }

  if (!target) {
    return {
      task_occurrence_id: req.task_occurrence_id,
      status: "complete",
      daily_win_recomputed: false,
      reward_preview_changed: false,
    };
  }

  target.status = "complete";

  // Re-derive owning block status so a follow-up GET reflects done.
  for (const b of state.blocks) {
    if ((b.occurrences as MockOccurrence[]).includes(target)) {
      b.status = deriveBlockStatus(
        b.occurrences,
        new Date(b.due_at ?? b.ends_at ?? new Date()),
      );
    }
  }

  // Did this completion change the owning kid's daily-win readiness?
  // The mock stays conservative: any daily-win-relevant occurrence flips
  // both flags so the frontend will refetch and confirm.
  const changes_daily_win = target.__counts_for_daily_win;

  return {
    task_occurrence_id: req.task_occurrence_id,
    status: "complete",
    daily_win_recomputed: changes_daily_win,
    reward_preview_changed: changes_daily_win,
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
    const required = collectRequiredOccurrences(state, k.id);
    const completed = required.filter((o) => o.status === "complete");
    const remaining = required.filter((o) => o.status !== "complete");
    const blocking = remaining.filter((o) => o.status === "late").map((o) => o.label);

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

function collectRequiredOccurrences(state: MockState, memberId: string): MockOccurrence[] {
  const all: MockOccurrence[] = [
    ...state.blocks.flatMap((b) => b.occurrences as MockOccurrence[]),
    ...state.standalone,
  ];
  return all.filter((o) => o.__owner_id === memberId && o.__counts_for_daily_win);
}

// ---------------------------------------------------------------------------
// /api/connectors  +  /api/connectors/health
// ---------------------------------------------------------------------------

export function mockConnectors(): ConnectorsResponse {
  const items: ConnectorListItem[] = [
    { connector_key: "google_calendar", label: "Google Calendar", status: "connected", last_sync_at: isoLocal(new Date()) },
    { connector_key: "hearth", label: "Hearth (display lane)", status: "connected", last_sync_at: isoLocal(new Date(Date.now() - 5 * 60_000)) },
    { connector_key: "greenlight", label: "Greenlight", status: "disconnected", last_sync_at: null },
    { connector_key: "rex", label: "Rex", status: "disconnected", last_sync_at: null },
    { connector_key: "ynab", label: "YNAB", status: "pending", last_sync_at: isoLocal(new Date(Date.now() - 24 * 60 * 60_000)) },
    { connector_key: "google_maps", label: "Google Maps", status: "decision_gated", last_sync_at: null },
    { connector_key: "apple_health", label: "Apple Health", status: "decision_gated", last_sync_at: null },
    { connector_key: "nike_run_club", label: "Nike Run Club", status: "decision_gated", last_sync_at: null },
  ];
  return { items };
}

export function mockConnectorsHealth(): ConnectorsHealthResponse {
  const within = (mins: number) => isoLocal(new Date(Date.now() - mins * 60_000));
  const items: ConnectorHealthItem[] = [
    { connector_key: "google_calendar", healthy: true, freshness_state: "fresh", last_success_at: within(2), last_error_at: null, last_error_message: null },
    { connector_key: "hearth", healthy: true, freshness_state: "fresh", last_success_at: within(5), last_error_at: null, last_error_message: null },
    { connector_key: "greenlight", healthy: false, freshness_state: "never_synced", last_success_at: null, last_error_at: null, last_error_message: "Not linked" },
    { connector_key: "rex", healthy: false, freshness_state: "never_synced", last_success_at: null, last_error_at: null, last_error_message: "Not linked" },
    { connector_key: "ynab", healthy: true, freshness_state: "stale", last_success_at: within(45), last_error_at: null, last_error_message: null },
    { connector_key: "google_maps", healthy: false, freshness_state: "never_synced", last_success_at: null, last_error_at: null, last_error_message: "Decision gated" },
    { connector_key: "apple_health", healthy: false, freshness_state: "never_synced", last_success_at: null, last_error_at: null, last_error_message: "Decision gated" },
    { connector_key: "nike_run_club", healthy: false, freshness_state: "never_synced", last_success_at: null, last_error_at: null, last_error_message: "Decision gated" },
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
      starts_at: b.starts_at ?? b.due_at ?? isoLocal(new Date()),
      ends_at: b.ends_at ?? b.due_at ?? isoLocal(new Date()),
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
      // never_synced / decision_gated / explicit error → error bucket
      // unless freshness flags it as merely stale.
      if (h.freshness_state === "stale" || h.freshness_state === "very_stale") {
        stale += 1;
      } else {
        error += 1;
      }
    } else if (h.freshness_state === "stale" || h.freshness_state === "very_stale") {
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
