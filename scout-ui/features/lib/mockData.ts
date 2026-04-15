/**
 * Roberts-family seed data for the Session 3 mock client.
 *
 * Sourced directly from `family_chore_system.md` (the locked product
 * doc for routines, ownership chores, dog walks, weekly events, and
 * Daily Win logic). Member roster:
 *   - Andrew  (adult, parent)
 *   - Sally   (adult, parent)
 *   - Sadie   (child, 13)
 *   - Townes  (child, 10)
 *   - River   (child, 8)
 *
 * Mutable state lives in `mockState` so that postCompletion() can
 * realistically mark an occurrence done and have subsequent reads of
 * /api/household/today and /api/rewards/week/current reflect that.
 *
 * Nothing here is canonical for the backend. This is a *frontend-only*
 * fixture that mirrors the published contracts so the UI can move
 * before Session 2 ships.
 */

import {
  CalendarExport,
  CalendarExportsResponse,
  ChildDailyWinPreview,
  CompletionRequest,
  CompletionResponse,
  CompletionStatus,
  Connector,
  ConnectorHealth,
  ConnectorsHealthResponse,
  ConnectorsResponse,
  ControlPlaneSummaryResponse,
  FamilyContextResponse,
  HouseholdTodayResponse,
  MeResponse,
  PersonRef,
  RewardWeekChild,
  RewardWeekResponse,
  RoutineBlock,
  StandardOfDone,
  TaskOccurrence,
} from "./contracts";

// ---------------------------------------------------------------------------
// Stable UUID-shaped ids — short, deterministic, easy to read in logs.
// ---------------------------------------------------------------------------

const FAMILY_ID = "fam-roberts";
const ANDREW = "mem-andrew";
const SALLY = "mem-sally";
const SADIE = "mem-sadie";
const TOWNES = "mem-townes";
const RIVER = "mem-river";

const ANDREW_REF: PersonRef = { member_id: ANDREW, first_name: "Andrew", role: "adult" };
const SALLY_REF: PersonRef = { member_id: SALLY, first_name: "Sally", role: "adult" };
const SADIE_REF: PersonRef = { member_id: SADIE, first_name: "Sadie", role: "child" };
const TOWNES_REF: PersonRef = { member_id: TOWNES, first_name: "Townes", role: "child" };
const RIVER_REF: PersonRef = { member_id: RIVER, first_name: "River", role: "child" };

const KIDS: PersonRef[] = [SADIE_REF, TOWNES_REF, RIVER_REF];

const TIMEZONE = "America/Chicago";

// ---------------------------------------------------------------------------
// Date helpers — keep the mock locked to "today" so the UI always renders
// against a fresh schedule regardless of when the developer runs the app.
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
  // Build an ISO string with the local offset so the UI's Date() parses
  // it back into the same wall-clock time the doc specifies.
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

// Calendar-day parity drives the rotating chore + dog-walk assistant rule.
function isOddDayToday(): boolean {
  return new Date().getDate() % 2 === 1;
}

const ROOM_RESET_STANDARDS: StandardOfDone[] = [
  { label: "Floor mostly clear (no loose clothes/toys)" },
  { label: "Clothes in hamper" },
  { label: "Dishes/cups removed" },
  { label: "Trash in trash can" },
  { label: "Bed made (simple is fine)" },
];

const COMMON_AREA_STANDARDS: StandardOfDone[] = [
  { label: "Cups/plates/trash moved to kitchen" },
  { label: "Blankets folded to basket" },
  { label: "Toys/items put in bins" },
  { label: "Remotes returned" },
  { label: "Floor clear enough a robot vacuum could run" },
];

// ---------------------------------------------------------------------------
// Mutable mock state
// ---------------------------------------------------------------------------

interface MockOccurrence extends TaskOccurrence {
  /** day-key for the occurrence so we can age out stale completions */
  day_key: string;
}

interface MockBlock extends RoutineBlock {
  occurrences: MockOccurrence[];
}

interface MockState {
  blocks: MockBlock[];
  standalone: MockOccurrence[];
}

let _state: MockState | null = null;

function ensureState(): MockState {
  if (_state) return _state;
  _state = buildInitialState();
  return _state;
}

/**
 * Reset the mock so devs / tests can re-run the day. Not exported into the
 * client surface — used by smoke tests via direct import.
 */
export function __resetMock(): void {
  _state = null;
}

// ---------------------------------------------------------------------------
// Block builders
// ---------------------------------------------------------------------------

let _occCounter = 0;
function newOccId(): string {
  _occCounter += 1;
  return `occ-${_occCounter.toString().padStart(4, "0")}`;
}

function makeOccurrence(args: {
  title: string;
  description?: string | null;
  owner: PersonRef;
  assistants?: PersonRef[];
  due: Date;
  block_id: string | null;
  standards?: StandardOfDone[];
}): MockOccurrence {
  return {
    occurrence_id: newOccId(),
    task_template_id: null,
    title: args.title,
    description: args.description ?? null,
    owner: args.owner,
    assistants: args.assistants ?? [],
    due_at: isoLocal(args.due),
    block_id: args.block_id,
    status: "pending",
    late: false,
    standards: args.standards ?? [],
    one_tap_eligible: true,
    day_key: todayDateOnly(),
  };
}

function buildMorning(): MockBlock {
  const blockId = "blk-morning";
  const due = todayAt(7, 25);
  const occurrences: MockOccurrence[] = [
    // Sadie
    makeOccurrence({ title: "Get dressed", owner: SADIE_REF, due, block_id: blockId }),
    makeOccurrence({ title: "Make bed", owner: SADIE_REF, due, block_id: blockId }),
    makeOccurrence({
      title: "Hygiene: brush teeth, deodorant, hair",
      owner: SADIE_REF,
      due,
      block_id: blockId,
    }),
    makeOccurrence({
      title: "Breakfast + dish to sink/dishwasher",
      owner: SADIE_REF,
      due,
      block_id: blockId,
    }),
    makeOccurrence({
      title: "Backpack check (homework / device / water bottle)",
      owner: SADIE_REF,
      due,
      block_id: blockId,
    }),
    makeOccurrence({
      title: "Lunch check (packed or plan confirmed)",
      owner: SADIE_REF,
      due,
      block_id: blockId,
    }),
    // Townes
    makeOccurrence({ title: "Get dressed", owner: TOWNES_REF, due, block_id: blockId }),
    makeOccurrence({ title: "Make bed", owner: TOWNES_REF, due, block_id: blockId }),
    makeOccurrence({ title: "Brush teeth", owner: TOWNES_REF, due, block_id: blockId }),
    makeOccurrence({
      title: "Breakfast + dish away",
      owner: TOWNES_REF,
      due,
      block_id: blockId,
    }),
    makeOccurrence({
      title: "Backpack check (homework / water bottle)",
      owner: TOWNES_REF,
      due,
      block_id: blockId,
    }),
    makeOccurrence({
      title: "Shoes / coat at launch spot",
      owner: TOWNES_REF,
      due,
      block_id: blockId,
    }),
    // River
    makeOccurrence({
      title: "Get dressed (clothes chosen night before)",
      owner: RIVER_REF,
      due,
      block_id: blockId,
    }),
    makeOccurrence({
      title: "Make bed (blanket up, pillow placed)",
      owner: RIVER_REF,
      due,
      block_id: blockId,
    }),
    makeOccurrence({ title: "Brush teeth", owner: RIVER_REF, due, block_id: blockId }),
    makeOccurrence({
      title: "Breakfast + dish away",
      owner: RIVER_REF,
      due,
      block_id: blockId,
    }),
    makeOccurrence({
      title: "Backpack + shoes at launch spot",
      owner: RIVER_REF,
      due,
      block_id: blockId,
    }),
  ];
  return {
    block_id: blockId,
    kind: "morning_routine",
    title: "Morning Routine",
    starts_at: isoLocal(todayAt(6, 45)),
    due_at: isoLocal(due),
    status: deriveBlockStatus(occurrences, due),
    members: KIDS,
    occurrences,
    note: "Due 7:25 on school days.",
  };
}

function buildAfterSchool(): MockBlock {
  const blockId = "blk-afterschool";
  const due = todayAt(17, 30);
  const odd = isOddDayToday();
  const occurrences: MockOccurrence[] = [
    // Sadie
    makeOccurrence({ title: "Snack (15 min max)", owner: SADIE_REF, due, block_id: blockId }),
    makeOccurrence({
      title: "Homework / Study (30–45 min timer)",
      owner: SADIE_REF,
      due,
      block_id: blockId,
    }),
    makeOccurrence({
      title: "10-minute zone reset (timer)",
      owner: SADIE_REF,
      due,
      block_id: blockId,
    }),
    makeOccurrence({
      title: "Dog walks led — Memphis + Willie",
      description: "Sadie owns completion. Willie's assistant rule applies.",
      owner: SADIE_REF,
      assistants: odd ? [TOWNES_REF] : [RIVER_REF],
      due,
      block_id: blockId,
    }),
    // Townes
    makeOccurrence({ title: "Snack (15 min max)", owner: TOWNES_REF, due, block_id: blockId }),
    makeOccurrence({
      title: "Homework / Reading (25–35 min timer)",
      owner: TOWNES_REF,
      due,
      block_id: blockId,
    }),
    makeOccurrence({
      title: "10-minute zone reset (timer)",
      owner: TOWNES_REF,
      due,
      block_id: blockId,
    }),
    ...(odd
      ? [
          makeOccurrence({
            title: "Willie walk assistant (ODD day)",
            description: "ODD calendar day → Townes assists Sadie on Willie's walk.",
            owner: TOWNES_REF,
            due,
            block_id: blockId,
          }),
        ]
      : []),
    // River
    makeOccurrence({ title: "Snack (15 min max)", owner: RIVER_REF, due, block_id: blockId }),
    makeOccurrence({
      title: "Homework / Reading (15–25 min timer)",
      owner: RIVER_REF,
      due,
      block_id: blockId,
    }),
    makeOccurrence({
      title: "10-minute zone reset (timer)",
      owner: RIVER_REF,
      due,
      block_id: blockId,
    }),
    ...(!odd
      ? [
          makeOccurrence({
            title: "Willie walk assistant (EVEN day)",
            description: "EVEN calendar day → River assists Sadie on Willie's walk.",
            owner: RIVER_REF,
            due,
            block_id: blockId,
          }),
        ]
      : []),
  ];
  return {
    block_id: blockId,
    kind: "after_school_routine",
    title: "After School Closeout",
    starts_at: isoLocal(todayAt(15, 30)),
    due_at: isoLocal(due),
    status: deriveBlockStatus(occurrences, due),
    members: KIDS,
    occurrences,
    note: odd
      ? "ODD day → Townes assists Sadie on the Willie walk."
      : "EVEN day → River assists Sadie on the Willie walk.",
  };
}

function buildEvening(): MockBlock {
  const blockId = "blk-evening";
  // Each kid has a different deadline; the block's `due_at` is the latest.
  const sadieDue = todayAt(21, 30);
  const townesDue = todayAt(21, 0);
  const riverDue = todayAt(20, 30);

  const occurrences: MockOccurrence[] = [
    // Sadie (due 9:30)
    makeOccurrence({
      title: "Pack backpack for tomorrow",
      owner: SADIE_REF,
      due: sadieDue,
      block_id: blockId,
    }),
    makeOccurrence({
      title: "Outfit set out",
      owner: SADIE_REF,
      due: sadieDue,
      block_id: blockId,
    }),
    makeOccurrence({
      title: "Room reset",
      description: "See standards of done.",
      owner: SADIE_REF,
      due: sadieDue,
      block_id: blockId,
      standards: ROOM_RESET_STANDARDS,
    }),
    makeOccurrence({ title: "Hygiene", owner: SADIE_REF, due: sadieDue, block_id: blockId }),
    makeOccurrence({
      title: "Devices to charging station",
      owner: SADIE_REF,
      due: sadieDue,
      block_id: blockId,
    }),
    // Townes (due 9:00)
    makeOccurrence({
      title: "Pack backpack",
      owner: TOWNES_REF,
      due: townesDue,
      block_id: blockId,
    }),
    makeOccurrence({
      title: "Outfit set out",
      owner: TOWNES_REF,
      due: townesDue,
      block_id: blockId,
    }),
    makeOccurrence({
      title: "Room reset",
      owner: TOWNES_REF,
      due: townesDue,
      block_id: blockId,
      standards: ROOM_RESET_STANDARDS,
    }),
    makeOccurrence({
      title: "Brush teeth",
      owner: TOWNES_REF,
      due: townesDue,
      block_id: blockId,
    }),
    makeOccurrence({
      title: "Devices to charging station",
      owner: TOWNES_REF,
      due: townesDue,
      block_id: blockId,
    }),
    // River (due 8:30)
    makeOccurrence({
      title: "Outfit set out (parent check if needed)",
      owner: RIVER_REF,
      due: riverDue,
      block_id: blockId,
    }),
    makeOccurrence({
      title: "Backpack packed",
      owner: RIVER_REF,
      due: riverDue,
      block_id: blockId,
    }),
    makeOccurrence({
      title: "Room reset (small scope)",
      owner: RIVER_REF,
      due: riverDue,
      block_id: blockId,
      standards: ROOM_RESET_STANDARDS,
    }),
    makeOccurrence({
      title: "Brush teeth",
      owner: RIVER_REF,
      due: riverDue,
      block_id: blockId,
    }),
    makeOccurrence({
      title: "Devices to charging station",
      owner: RIVER_REF,
      due: riverDue,
      block_id: blockId,
    }),
  ];

  return {
    block_id: blockId,
    kind: "evening_routine",
    title: "Evening Reset",
    starts_at: isoLocal(todayAt(20, 0)),
    due_at: isoLocal(sadieDue),
    status: deriveBlockStatus(occurrences, sadieDue),
    members: KIDS,
    occurrences,
    note: "River → 8:30, Townes → 9:00, Sadie → 9:30.",
  };
}

function buildOwnershipChores(): MockBlock {
  const blockId = "blk-ownership";
  const occurrences: MockOccurrence[] = [
    // Sadie - dishwasher captain (option B: unload morning 7:10)
    makeOccurrence({
      title: "Dishwasher Captain — unload",
      description: "Sadie owns this for 6–8 weeks. Currently morning unload.",
      owner: SADIE_REF,
      due: todayAt(7, 10),
      block_id: blockId,
    }),
    // Townes - table + sweep
    makeOccurrence({
      title: "Set table for dinner",
      owner: TOWNES_REF,
      due: todayAt(18, 15),
      block_id: blockId,
    }),
    makeOccurrence({
      title: "Clear table after dinner",
      owner: TOWNES_REF,
      due: todayAt(19, 45),
      block_id: blockId,
    }),
    makeOccurrence({
      title: "Quick sweep — kitchen / dining",
      owner: TOWNES_REF,
      due: todayAt(20, 0),
      block_id: blockId,
    }),
    // River - living room reset captain
    makeOccurrence({
      title: "Living Room Reset",
      description:
        "Blankets folded to basket, toys to bins, cups/dishes to kitchen.",
      owner: RIVER_REF,
      due: todayAt(19, 30),
      block_id: blockId,
    }),
  ];
  return {
    block_id: blockId,
    kind: "ownership_chore",
    title: "Ownership Chores",
    starts_at: null,
    due_at: isoLocal(todayAt(20, 0)),
    status: deriveBlockStatus(occurrences, todayAt(20, 0)),
    members: KIDS,
    occurrences,
    note: "Mon–Fri ownership chores. Each kid has one captain role.",
  };
}

function buildRotatingChore(): MockBlock {
  const blockId = "blk-rotating";
  const odd = isOddDayToday();
  const owner = odd ? TOWNES_REF : RIVER_REF;
  const due = todayAt(19, 30);

  const occ = makeOccurrence({
    title: "Common Area Closeout",
    description: odd
      ? "ODD calendar day → Townes owns this today."
      : "EVEN calendar day → River owns this today.",
    owner,
    due,
    block_id: blockId,
    standards: COMMON_AREA_STANDARDS,
  });

  return {
    block_id: blockId,
    kind: "rotating_chore",
    title: "Common Area Closeout (rotating)",
    starts_at: null,
    due_at: isoLocal(due),
    status: deriveBlockStatus([occ], due),
    members: [owner],
    occurrences: [occ],
    note: odd ? "ODD day → Townes" : "EVEN day → River",
  };
}

function buildDogWalks(): MockBlock {
  const blockId = "blk-dogwalks";
  const odd = isOddDayToday();
  const due = todayAt(19, 30);
  const occurrences: MockOccurrence[] = [
    makeOccurrence({
      title: "Memphis walked (Sadie handling) — 15-20 min",
      owner: SADIE_REF,
      due,
      block_id: blockId,
    }),
    makeOccurrence({
      title: "Willie walked — 10-15 min",
      description: odd
        ? "ODD day → Townes assists."
        : "EVEN day → River assists.",
      owner: SADIE_REF,
      assistants: odd ? [TOWNES_REF] : [RIVER_REF],
      due,
      block_id: blockId,
    }),
    makeOccurrence({
      title: "Leashes/harnesses returned to hook",
      owner: SADIE_REF,
      due,
      block_id: blockId,
    }),
    makeOccurrence({
      title: "Paws wiped if wet",
      owner: SADIE_REF,
      due,
      block_id: blockId,
    }),
    makeOccurrence({
      title: "Poop bags restocked if low",
      owner: SADIE_REF,
      due,
      block_id: blockId,
    }),
  ];
  return {
    block_id: blockId,
    kind: "dog_walks",
    title: "Dog Walks (Sadie lead)",
    starts_at: isoLocal(todayAt(17, 0)),
    due_at: isoLocal(due),
    status: deriveBlockStatus(occurrences, due),
    members: [SADIE_REF, odd ? TOWNES_REF : RIVER_REF],
    occurrences,
    note: "Sadie owns completion. If assistant doesn't show, screens pause until Willie's walk lands.",
  };
}

function buildSaturdayPower60(): MockBlock | null {
  // Only render on Saturday
  if (new Date().getDay() !== 6) return null;
  const blockId = "blk-power60";
  const due = todayAt(11, 0);
  const occurrences: MockOccurrence[] = [
    makeOccurrence({
      title: "Sadie — Bathroom (sink, mirror, toilet, towels)",
      owner: SADIE_REF,
      due,
      block_id: blockId,
    }),
    makeOccurrence({
      title: "Townes — Vacuum bedroom + hallway/landing",
      owner: TOWNES_REF,
      due,
      block_id: blockId,
    }),
    makeOccurrence({
      title: "River — Dust/wipe coffee table + one shelf + one baseboard zone",
      owner: RIVER_REF,
      due,
      block_id: blockId,
    }),
    makeOccurrence({
      title: "Backyard Poop Patrol (Townes owner, River assistant — week-of-rotation)",
      description: "Rotates every 8 weeks. River owner / Townes assistant on swap weeks.",
      owner: TOWNES_REF,
      assistants: [RIVER_REF],
      due,
      block_id: blockId,
    }),
  ];
  return {
    block_id: blockId,
    kind: "weekly_event",
    title: "Power 60 (House Reset)",
    starts_at: isoLocal(todayAt(10, 0)),
    due_at: isoLocal(due),
    status: deriveBlockStatus(occurrences, due),
    members: KIDS,
    occurrences,
    note: "Saturday morning reset. Music on, then done.",
  };
}

function deriveBlockStatus(occs: TaskOccurrence[], due: Date): RoutineBlock["status"] {
  if (occs.length === 0) return "upcoming";
  const allDone = occs.every((o) => o.status === "complete");
  if (allDone) return "done";
  const now = new Date();
  if (now > due) return "late";
  // due_soon if within 30 min of deadline
  if (due.getTime() - now.getTime() <= 30 * 60_000) return "due_soon";
  // Treat after start as active when starts_at is known. Conservative
  // default: upcoming.
  return now > new Date(due.getTime() - 6 * 60 * 60_000) ? "active" : "upcoming";
}

function buildInitialState(): MockState {
  const blocks: MockBlock[] = [
    buildMorning(),
    buildAfterSchool(),
    buildEvening(),
    buildOwnershipChores(),
    buildRotatingChore(),
    buildDogWalks(),
  ];
  const power60 = buildSaturdayPower60();
  if (power60) blocks.push(power60);
  return { blocks, standalone: [] };
}

// ---------------------------------------------------------------------------
// Daily Win preview computation
// ---------------------------------------------------------------------------

function computeDailyWin(memberId: string, state: MockState): ChildDailyWinPreview {
  // Per the family doc: a Daily Win = morning + after-school + evening + that
  // child's ownership chore, plus the rotating common-area chore IF assigned
  // today.
  const required: TaskOccurrence[] = [];
  for (const block of state.blocks) {
    if (
      block.kind === "morning_routine" ||
      block.kind === "after_school_routine" ||
      block.kind === "evening_routine"
    ) {
      required.push(...block.occurrences.filter((o) => o.owner.member_id === memberId));
    }
    if (block.kind === "ownership_chore") {
      required.push(...block.occurrences.filter((o) => o.owner.member_id === memberId));
    }
    if (block.kind === "rotating_chore") {
      required.push(...block.occurrences.filter((o) => o.owner.member_id === memberId));
    }
  }
  const completed = required.filter((o) => o.status === "complete");
  const remaining = required.filter((o) => o.status !== "complete");
  return {
    member_id: memberId,
    on_track: remaining.every((o) => !o.late),
    required_count: required.length,
    completed_count: completed.length,
    remaining_count: remaining.length,
    blocking_titles: remaining.filter((o) => o.late).map((o) => o.title),
  };
}

// ---------------------------------------------------------------------------
// Public API surface (consumed by mockClient.ts)
// ---------------------------------------------------------------------------

export function mockMe(): MeResponse {
  // Default to an adult (Andrew) for the operating-surface developer view.
  return {
    member_id: ANDREW,
    family_id: FAMILY_ID,
    first_name: "Andrew",
    last_name: "Roberts",
    role: "adult",
    family_name: "Roberts",
    capabilities: {
      can_complete_for: [SADIE, TOWNES, RIVER, ANDREW, SALLY],
      can_approve_payouts: true,
      can_view_control_plane: true,
    },
  };
}

export function mockFamilyContext(): FamilyContextResponse {
  const today = todayDateOnly();
  return {
    family_id: FAMILY_ID,
    family_name: "Roberts",
    timezone: TIMEZONE,
    members: [
      { member_id: ANDREW, first_name: "Andrew", last_name: "Roberts", role: "adult", is_active: true, birthdate: null },
      { member_id: SALLY, first_name: "Sally", last_name: "Roberts", role: "adult", is_active: true, birthdate: null },
      { member_id: SADIE, first_name: "Sadie", last_name: "Roberts", role: "child", is_active: true, birthdate: null },
      { member_id: TOWNES, first_name: "Townes", last_name: "Roberts", role: "child", is_active: true, birthdate: null },
      { member_id: RIVER, first_name: "River", last_name: "Roberts", role: "child", is_active: true, birthdate: null },
    ],
    reward_baselines: {
      [SADIE]: 1200, // $12.00
      [TOWNES]: 900, // $9.00
      [RIVER]: 700,  // $7.00
    },
  };
}

export function mockHouseholdToday(): HouseholdTodayResponse {
  const state = ensureState();
  return {
    date: todayDateOnly(),
    generated_at: isoLocal(new Date()),
    blocks: state.blocks.map(stripDayKey),
    standalone_occurrences: state.standalone.map(stripDayKey),
    daily_win_preview: KIDS.map((k) => computeDailyWin(k.member_id, state)),
  };
}

function stripDayKey<T extends MockOccurrence | MockBlock>(input: T): any {
  if ("occurrences" in input) {
    const { occurrences, ...rest } = input as MockBlock;
    return { ...rest, occurrences: occurrences.map(stripDayKey) };
  }
  const { day_key, ...rest } = input as MockOccurrence;
  return rest;
}

export function mockPostCompletion(req: CompletionRequest): CompletionResponse {
  const state = ensureState();
  let updatedBlock: RoutineBlock | null = null;

  for (const block of state.blocks) {
    const occ = block.occurrences.find((o) => o.occurrence_id === req.occurrence_id);
    if (occ) {
      occ.status = "complete" satisfies CompletionStatus;
      block.status = deriveBlockStatus(block.occurrences, new Date(block.due_at));
      updatedBlock = stripDayKey(block);
      break;
    }
  }
  for (const occ of state.standalone) {
    if (occ.occurrence_id === req.occurrence_id) {
      occ.status = "complete";
      break;
    }
  }

  // Find the owning child for the daily-win echo.
  let dailyWin: ChildDailyWinPreview | null = null;
  const all = state.blocks.flatMap((b) => b.occurrences).concat(state.standalone);
  const target = all.find((o) => o.occurrence_id === req.occurrence_id);
  if (target && target.owner.role === "child") {
    dailyWin = computeDailyWin(target.owner.member_id, state);
  }

  return {
    occurrence_id: req.occurrence_id,
    status: target?.status ?? "complete",
    daily_win_preview: dailyWin,
    updated_block: updatedBlock,
  };
}

export function mockRewardsWeek(): RewardWeekResponse {
  const state = ensureState();
  const baselines: Record<string, number> = { [SADIE]: 1200, [TOWNES]: 900, [RIVER]: 700 };
  const dayIndex = Math.min(4, Math.max(0, new Date().getDay() - 1)); // Mon=0..Fri=4
  const children: RewardWeekChild[] = KIDS.map((k) => {
    const winToday = computeDailyWin(k.member_id, state);
    const day_wins: Array<boolean | null> = [false, false, false, false, false];
    // Pretend the previous days were wins; today reflects current state.
    for (let i = 0; i < dayIndex; i++) day_wins[i] = true;
    day_wins[dayIndex] = winToday.remaining_count === 0 ? true : winToday.on_track ? null : false;
    for (let i = dayIndex + 1; i < 5; i++) day_wins[i] = null;
    const win_count = day_wins.filter((v) => v === true).length;
    const payout_percent =
      win_count >= 5 ? 100 : win_count === 4 ? 80 : win_count === 3 ? 60 : 0;
    const baseline = baselines[k.member_id] ?? 0;
    return {
      member_id: k.member_id,
      first_name: k.first_name,
      baseline_cents: baseline,
      day_wins,
      win_count,
      payout_percent,
      payout_cents: Math.round((baseline * payout_percent) / 100),
      missed_reasons: winToday.blocking_titles,
      approval_status: "draft",
    };
  });
  return {
    week_start: mondayOfThisWeek(),
    week_end: sundayOfThisWeek(),
    children,
    total_payout_cents: children.reduce((s, c) => s + c.payout_cents, 0),
  };
}

export function mockConnectors(): ConnectorsResponse {
  const now = isoLocal(new Date());
  const yesterday = isoLocal(new Date(Date.now() - 24 * 60 * 60_000));
  const list: Connector[] = [
    { id: "google_calendar", display_name: "Google Calendar", tier: 1, status: "linked", scope_summary: "Read + write Scout calendar", last_event_at: now },
    { id: "ical_hearth", display_name: "Hearth (iCal lane)", tier: 1, status: "linked", scope_summary: "Publish anchor blocks", last_event_at: now },
    { id: "greenlight", display_name: "Greenlight", tier: 1, status: "not_linked", scope_summary: "Payout export", last_event_at: null },
    { id: "rex", display_name: "Rex", tier: 2, status: "not_linked", scope_summary: "Inbound work load", last_event_at: null },
    { id: "ynab", display_name: "YNAB", tier: 2, status: "not_linked", scope_summary: "Budget context", last_event_at: yesterday },
    { id: "google_maps", display_name: "Google Maps", tier: 3, status: "not_linked", scope_summary: "Travel time", last_event_at: null },
    { id: "apple_health", display_name: "Apple Health", tier: 3, status: "not_linked", scope_summary: "Activity context", last_event_at: null },
    { id: "nike_run_club", display_name: "Nike Run Club", tier: 3, status: "not_linked", scope_summary: "Workouts", last_event_at: null },
  ];
  return { connectors: list };
}

export function mockConnectorsHealth(): ConnectorsHealthResponse {
  const now = new Date();
  const within = (mins: number) => isoLocal(new Date(now.getTime() - mins * 60_000));
  const list: ConnectorHealth[] = [
    { id: "google_calendar", ok: true, last_sync_at: within(2), last_sync_status: "success", freshness_seconds: 120, message: null },
    { id: "ical_hearth", ok: true, last_sync_at: within(5), last_sync_status: "success", freshness_seconds: 300, message: null },
    { id: "greenlight", ok: false, last_sync_at: null, last_sync_status: "never", freshness_seconds: null, message: "Not linked" },
    { id: "rex", ok: false, last_sync_at: null, last_sync_status: "never", freshness_seconds: null, message: "Not linked" },
    { id: "ynab", ok: true, last_sync_at: within(45), last_sync_status: "partial", freshness_seconds: 2700, message: "Backfill in progress" },
    { id: "google_maps", ok: false, last_sync_at: null, last_sync_status: "never", freshness_seconds: null, message: "Tier 3 — not linked" },
    { id: "apple_health", ok: false, last_sync_at: null, last_sync_status: "never", freshness_seconds: null, message: "Tier 3 — not linked" },
    { id: "nike_run_club", ok: false, last_sync_at: null, last_sync_status: "never", freshness_seconds: null, message: "Tier 3 — not linked" },
  ];
  return { connectors: list, generated_at: isoLocal(now) };
}

export function mockCalendarExports(): CalendarExportsResponse {
  const state = ensureState();
  const upcoming: CalendarExport[] = state.blocks.slice(0, 5).map((b, i) => ({
    export_id: `cal-${b.block_id}`,
    title: b.title,
    starts_at: b.starts_at ?? b.due_at,
    ends_at: b.due_at,
    google_calendar_event_id: i === 0 ? "gcal-mock-12345" : null,
    publication_status: i === 0 ? "published" : "pending",
  }));
  return { generated_at: isoLocal(new Date()), upcoming };
}

export function mockControlPlaneSummary(): ControlPlaneSummaryResponse {
  const health = mockConnectorsHealth();
  const now = new Date();
  return {
    generated_at: isoLocal(now),
    household_status: "warning", // greenlight not linked
    connectors: health.connectors,
    sync_jobs: [
      {
        job_id: "job-cal-publish",
        name: "Calendar publish",
        status: "idle",
        last_run_at: isoLocal(new Date(now.getTime() - 5 * 60_000)),
        next_run_at: isoLocal(new Date(now.getTime() + 25 * 60_000)),
        error_message: null,
      },
      {
        job_id: "job-greenlight-sync",
        name: "Greenlight sync",
        status: "error",
        last_run_at: null,
        next_run_at: null,
        error_message: "Connector not linked",
      },
    ],
    publications: [
      {
        surface: "hearth_calendar_lane",
        last_published_at: isoLocal(new Date(now.getTime() - 5 * 60_000)),
        pending_count: 4,
        failed_count: 0,
      },
    ],
    notifications: { rules_active: 6, deliveries_24h: 12, failures_24h: 0 },
  };
}
