/**
 * Hardcoded seed data for the redesigned UI. Single source of truth
 * for every page in the new design system. Replace with real data
 * when/if the redesign goes past mockup demo stage.
 *
 * KNOWN CONCERN (mockup-stage tradeoff): several fields couple view
 * concerns into what would normally be domain data — ActivityRow.tint,
 * PersonalTask.tagTone, CalendarEvent.dot, and the paired tag/tagTone
 * fields in PersonalTask. When the backing data becomes real, these
 * should be replaced with semantic kinds (e.g. "chore_complete",
 * "meal_updated") and the UI should derive color/tone from the kind.
 * Not fixing now because every page consuming this file is also
 * mockup-only and gets rewritten in the same pass.
 */

export type MemberRole = "admin" | "full" | "child";
export type AvatarTint = "purple" | "teal" | "amber" | "coral";

export interface Member {
  id: string;
  firstName: string;
  lastName: string;
  initials: string;
  age?: number;
  role: MemberRole;
  tint: AvatarTint;
  email?: string;
  dietary?: string;
}

export const FAMILY: Member[] = [
  { id: "andrew", firstName: "Andrew", lastName: "Roberts", initials: "AR", role: "admin", tint: "purple", email: "robertsandrewt@gmail.com", dietary: "No restrictions" },
  { id: "sally",  firstName: "Sally",  lastName: "Roberts", initials: "S",  role: "admin", tint: "teal",   dietary: "Vegetarian-lean" },
  { id: "tyler",  firstName: "Tyler",  lastName: "Roberts", initials: "T",  age: 18, role: "full",  tint: "amber",  dietary: "No restrictions" },
  { id: "sadie",  firstName: "Sadie",  lastName: "Roberts", initials: "S",  age: 14, role: "full",  tint: "purple", dietary: "No restrictions" },
  { id: "townes", firstName: "Townes", lastName: "Roberts", initials: "T",  age: 10, role: "child", tint: "teal",   dietary: "No restrictions" },
  { id: "river",  firstName: "River",  lastName: "Roberts", initials: "R",  age: 8,  role: "child", tint: "coral",  dietary: "No onions" },
];

export interface ChoreProgress {
  memberId: string;
  done: number;
  total: number;
}

export const CHORES_TODAY: ChoreProgress[] = [
  { memberId: "sadie",  done: 3, total: 4 },
  { memberId: "townes", done: 4, total: 4 },
  { memberId: "tyler",  done: 2, total: 4 },
  { memberId: "river",  done: 0, total: 3 },
];

export interface MealPlanDay {
  day: "MON" | "TUE" | "WED" | "THU" | "FRI" | "SAT" | "SUN";
  name: string;
  note: string;
  isToday?: boolean;
}

export const MEALS_THIS_WEEK: MealPlanDay[] = [
  { day: "MON", name: "Taco Bowl",  note: "Ground turkey" },
  { day: "TUE", name: "Pasta",      note: "Veggie marinara" },
  { day: "WED", name: "Stir Fry",   note: "Tonight", isToday: true },
  { day: "THU", name: "Salmon",     note: "Roasted veg" },
  { day: "FRI", name: "Pizza Night",note: "Family build" },
  { day: "SAT", name: "Brunch",     note: "Batch cook" },
  { day: "SUN", name: "Tacos",      note: "Easy night" },
];

export interface BatchCookItem { name: string; minutes: number; done: boolean; }

export const BATCH_COOK: BatchCookItem[] = [
  { name: "Cilantro lime rice (2x)",     minutes: 30, done: true },
  { name: "Roasted bell peppers",        minutes: 25, done: true },
  { name: "Ground turkey (seasoned)",    minutes: 20, done: false },
  { name: "Overnight oats (5 servings)", minutes: 10, done: false },
  { name: "Veggie stir fry sauce",       minutes: 15, done: false },
];

export interface GroceryItem { name: string; section: string; done: boolean; requestedBy?: string; }
export interface GroceryStore { name: string; items: GroceryItem[]; }

export const GROCERY: GroceryStore[] = [
  {
    name: "Costco",
    items: [
      { section: "Produce", name: "Baby spinach (2 bags)",   done: true },
      { section: "Produce", name: "Bell peppers (6-pack)",   done: true },
      { section: "Produce", name: "Broccoli crowns",         done: false },
      { section: "Protein", name: "Ground turkey (3 lbs)",   done: false },
      { section: "Protein", name: "Salmon fillets (2 lbs)",  done: false },
      { section: "Protein", name: "Rotisserie chicken",      done: false },
      { section: "Pantry",  name: "Olive oil (2L)",          done: false },
      { section: "Pantry",  name: "Tortillas (30-pack)",     done: false },
    ],
  },
  {
    name: "Tom Thumb",
    items: [
      { section: "Produce",   name: "Bananas",        done: true },
      { section: "Produce",   name: "Limes (8)",      done: false },
      { section: "Produce",   name: "Avocados (4)",   done: false },
      { section: "Dairy",     name: "Greek yogurt",   done: false },
      { section: "Dairy",     name: "Cotija cheese",  done: false },
      { section: "Requested", name: "Paper towels",   done: false, requestedBy: "River" },
    ],
  },
];

export interface ActivityRow {
  id: string;
  text: string;
  tint: "green" | "purple" | "amber" | "teal" | "red";
  meta: string;
}

export const ACTIVITY: ActivityRow[] = [
  { id: "a1", tint: "green",  text: "Townes completed all 4 chores",       meta: "+40 pts" },
  { id: "a2", tint: "purple", text: "Sally updated meal plan",             meta: "4h ago" },
  { id: "a3", tint: "amber",  text: "River: paper towels request",         meta: "Pending" },
  { id: "a4", tint: "teal",   text: "Sadie redeemed 200 pts",              meta: "Yesterday" },
  { id: "a5", tint: "red",    text: "Tyler missed recycling",              meta: "Missed" },
];

export interface AllowanceRow { memberId: string; earned: number; max: number; }

export const ALLOWANCE: AllowanceRow[] = [
  { memberId: "sadie",  earned: 7.5, max: 10 },
  { memberId: "townes", earned: 8,   max: 8 },
  { memberId: "tyler",  earned: 6,   max: 12 },
  { memberId: "river",  earned: 0,   max: 6 },
];

export interface LeaderRow { memberId: string; points: number; rank: number; }

export const LEADERBOARD: LeaderRow[] = [
  { memberId: "townes", points: 840, rank: 1 },
  { memberId: "sadie",  points: 605, rank: 2 },
  { memberId: "tyler",  points: 400, rank: 3 },
  { memberId: "river",  points: 125, rank: 4 },
];

export interface Bill {
  name: string;
  amount: number;
  status: "due" | "upcoming" | "paid";
  dueLabel: string;
  urgent?: boolean;
}

export const BILLS: Bill[] = [
  { name: "Hilltop mortgage", amount: 4820, status: "due",      dueLabel: "Apr 18", urgent: true },
  { name: "Electric — Oncor", amount: 312,  status: "upcoming", dueLabel: "Apr 22" },
  { name: "Internet — AT&T",  amount: 89,   status: "paid",     dueLabel: "paid" },
  { name: "Spotify Family",   amount: 16,   status: "paid",     dueLabel: "paid" },
];

export interface PersonalTask { title: string; tag: string; tagTone: "green" | "amber" | "purple" | "muted"; done: boolean; }

export const PERSONAL_TASKS: PersonalTask[] = [
  { title: "Review Bishop Modern drawings", tag: "Done",     tagTone: "green",  done: true  },
  { title: "Send Treehaus punch list",      tag: "Today",    tagTone: "amber",  done: false },
  { title: "Call insurance re: Hilltop",    tag: "Today",    tagTone: "amber",  done: false },
  { title: "Approve grocery budget",        tag: "Family",   tagTone: "purple", done: false },
  { title: "Schedule Exxir all-hands",      tag: "This week",tagTone: "muted",  done: false },
];

export interface RecentNote { title: string; preview: string; date: string; }

export const RECENT_NOTES: RecentNote[] = [
  { title: "Bishop Canopy — subcontractor notes",  preview: "Framing crew behind 4 days. Need to flag to Mitch before Friday's call...", date: "Yesterday" },
  { title: "Hilltop Casa — landscaping ideas",     preview: "Sally wants native plants on the south slope. Get quote from Hill Country nursery...", date: "Apr 13" },
  { title: "Weekly review — Apr 14",               preview: "3 projects on track. Bishop Flats 2 showing schedule risk at foundation phase...", date: "Apr 14" },
];

export interface CalendarEvent { dot: "purple" | "teal" | "amber"; title: string; time: string; }

export const CALENDAR_EVENTS: CalendarEvent[] = [
  { dot: "purple", title: "Exxir — Bishop North site walk",    time: "2:00 PM" },
  { dot: "teal",   title: "Sadie: soccer practice pickup",     time: "4:30 PM" },
  { dot: "amber",  title: "Hilltop Casa — HVAC inspection",    time: "Fri 10 AM" },
];

export interface InboxItem { kind: "purchase" | "brief" | "chore" | "win"; title: string; sub: string; }

export const ACTION_INBOX: InboxItem[] = [
  { kind: "purchase", title: "River requested paper towels", sub: "Approve or reject to respond" },
  { kind: "brief",    title: "Morning brief — Wed Apr 15",   sub: "Daily briefing ready to review" },
  { kind: "chore",    title: "Tyler missed recycling (Tue)", sub: "Deduct points or mark excused?" },
  { kind: "win",      title: "Townes: 7-day chore streak!",  sub: "Award bonus points?" },
];

export interface HomeworkRow { memberId: string; sessions: number; topics: string; status: "on_track" | "low"; }

export const HOMEWORK: HomeworkRow[] = [
  { memberId: "sadie",  sessions: 2, topics: "math, history",  status: "on_track" },
  { memberId: "townes", sessions: 3, topics: "reading, math",  status: "on_track" },
  { memberId: "tyler",  sessions: 1, topics: "AP history",     status: "low" },
  { memberId: "river",  sessions: 1, topics: "math",           status: "low" },
];

export interface Integration { name: string; status: "connected" | "needs_reauth" | "not_connected"; }

export const INTEGRATIONS: Integration[] = [
  { name: "Google Calendar",      status: "connected" },
  { name: "Greenlight (allowance)", status: "connected" },
  { name: "Hearth Display",       status: "connected" },
  { name: "YNAB",                 status: "needs_reauth" },
  { name: "Apple Health",         status: "not_connected" },
  { name: "Nike Run Club",        status: "not_connected" },
];

export interface ScoutAIToggle { label: string; sub: string; on: boolean; }

export const SCOUT_AI_TOGGLES: ScoutAIToggle[] = [
  { label: "Allow general chat",     sub: "Q&A, creative writing, coding help",                 on: true },
  { label: "Homework help (kids)",   sub: "Socratic tutoring — guides, doesn't give answers",   on: true },
  { label: "Proactive suggestions",  sub: "Scout surfaces ideas without being asked",           on: true },
  { label: "Push notifications",     sub: "Chore reminders, meal alerts, family updates",       on: true },
];

export interface ChildChore { name: string; done: boolean; pts: number; }

// Chore list specifically for the Townes demo screenshot in the child
// view. Not a general child-chores source — when the kid view supports
// other children, this should become a lookup keyed by memberId.
export const TOWNES_CHORES: ChildChore[] = [
  { name: "Make bed",          done: true, pts: 10 },
  { name: "Unload dishwasher", done: true, pts: 10 },
  { name: "Feed Biscuit (dog)",done: true, pts: 10 },
  { name: "Clean up backpack", done: true, pts: 10 },
];

// Helpers
export const getMember = (id: string): Member | undefined =>
  FAMILY.find((m) => m.id === id);

// Children only (role === "child"). Does NOT include Tyler (age 18,
// role "full"), who is a dependent but not a child for UI purposes.
// If you want "everyone except admins," define a separate DEPENDENTS.
export const KIDS = FAMILY.filter((m) => m.role === "child");
