import { API_BASE_URL, FAMILY_ID } from "./config";
import type {
  Bill,
  ChoreTemplate,
  DailyWin,
  Event,
  FamilyMember,
  GroceryItem,
  Meal,
  Note,
  PersonalTask,
  MealReview,
  MealReviewSummary,
  PurchaseRequest,
  Routine,
  StepCompletion,
  TaskInstance,
  WeeklyMealPlan,
  WeeklyMealPlanGenerateResponse,
} from "./types";

const familyUrl = `${API_BASE_URL}/families/${FAMILY_ID}`;

// ---------------------------------------------------------------------------
// Token management — set by AuthProvider, read by all API calls
// ---------------------------------------------------------------------------

let _authToken: string | null = null;

export function setApiToken(token: string | null) {
  _authToken = token;
}

function authHeaders(): Record<string, string> {
  if (_authToken) {
    return { Authorization: `Bearer ${_authToken}` };
  }
  return {};
}

// ---------------------------------------------------------------------------
// Base helpers
// ---------------------------------------------------------------------------

async function get<T>(url: string): Promise<T> {
  const res = await fetch(url, { headers: authHeaders() });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    console.error("API ERROR:", res.status, url, text);
    throw new Error(`Failed to fetch`);
  }
  return await res.json();
}

async function post<T>(url: string, body?: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: { ...authHeaders(), ...(body ? { "Content-Type": "application/json" } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    console.error("API ERROR:", res.status, url, text);
    throw new Error(`Failed to fetch`);
  }
  return await res.json();
}

async function patch<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "PATCH",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    console.error("API ERROR:", res.status, url, text);
    throw new Error(`Failed to fetch`);
  }
  return await res.json();
}

// ---------------------------------------------------------------------------
// Family members
// ---------------------------------------------------------------------------

export function fetchMembers(): Promise<FamilyMember[]> {
  return get(`${familyUrl}/members`);
}

// ---------------------------------------------------------------------------
// Task instances
// ---------------------------------------------------------------------------

export function fetchTaskInstances(
  date: string,
  memberId?: string
): Promise<TaskInstance[]> {
  let url = `${familyUrl}/task-instances?instance_date=${date}`;
  if (memberId) url += `&member_id=${memberId}`;
  return get(url);
}

export function fetchStepCompletions(
  instanceId: string
): Promise<StepCompletion[]> {
  return get(`${familyUrl}/task-instances/${instanceId}/steps`);
}

export function markTaskComplete(instanceId: string): Promise<TaskInstance> {
  return post(`${familyUrl}/task-instances/${instanceId}/complete`, {});
}

export async function updateStepCompletion(
  instanceId: string,
  stepCompletionId: string,
  isCompleted: boolean
): Promise<StepCompletion> {
  return patch(
    `${familyUrl}/task-instances/${instanceId}/steps/${stepCompletionId}`,
    { is_completed: isCompleted },
  );
}

export function generateTasks(date: string): Promise<TaskInstance[]> {
  return post(`${familyUrl}/task-instances/generate?target_date=${date}`);
}

// ---------------------------------------------------------------------------
// Routines / Chores
// ---------------------------------------------------------------------------

export function fetchRoutines(memberId?: string): Promise<Routine[]> {
  let url = `${familyUrl}/routines`;
  if (memberId) url += `?member_id=${memberId}`;
  return get(url);
}

export function fetchChoreTemplates(): Promise<ChoreTemplate[]> {
  return get(`${familyUrl}/chore-templates`);
}

// ---------------------------------------------------------------------------
// Daily Wins / Allowance
// ---------------------------------------------------------------------------

export function fetchDailyWins(
  memberId: string,
  startDate: string,
  endDate: string
): Promise<DailyWin[]> {
  return get(
    `${familyUrl}/daily-wins?member_id=${memberId}&start_date=${startDate}&end_date=${endDate}`
  );
}

export class PayoutError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function createWeeklyPayout(
  memberId: string,
  baselineCents: number,
  weekStart: string
): Promise<unknown> {
  const url = `${familyUrl}/allowance/weekly-payout?member_id=${memberId}&baseline_cents=${baselineCents}&week_start=${weekStart}`;
  const res = await fetch(url, { method: "POST", headers: authHeaders() });
  if (!res.ok) {
    throw new PayoutError(res.status, `payout request failed (${res.status})`);
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// Meals
// ---------------------------------------------------------------------------

export function fetchMeals(
  mealDate?: string,
  startDate?: string,
  endDate?: string,
): Promise<Meal[]> {
  const params = new URLSearchParams();
  if (mealDate) params.set("meal_date", mealDate);
  if (startDate) params.set("start_date", startDate);
  if (endDate) params.set("end_date", endDate);
  const qs = params.toString();
  return get(`${familyUrl}/meals${qs ? `?${qs}` : ""}`);
}

// ---------------------------------------------------------------------------
// Calendar
// ---------------------------------------------------------------------------

export function fetchEvents(
  start?: string,
  end?: string,
  hearthVisibleOnly?: boolean
): Promise<Event[]> {
  const params = new URLSearchParams();
  if (start) params.set("start", start);
  if (end) params.set("end", end);
  if (hearthVisibleOnly) params.set("hearth_visible_only", "true");
  const qs = params.toString();
  return get(`${familyUrl}/events${qs ? `?${qs}` : ""}`);
}

// ---------------------------------------------------------------------------
// Personal Tasks
// ---------------------------------------------------------------------------

export function fetchTopPersonalTasks(
  assignedTo: string,
  limit: number = 5
): Promise<PersonalTask[]> {
  return get(
    `${familyUrl}/personal-tasks/top?assigned_to=${assignedTo}&limit=${limit}`
  );
}

// ---------------------------------------------------------------------------
// Finance
// ---------------------------------------------------------------------------

export function fetchUnpaidBills(): Promise<Bill[]> {
  return get(`${familyUrl}/bills/unpaid`);
}

// ---------------------------------------------------------------------------
// Notes
// ---------------------------------------------------------------------------

export function fetchRecentNotes(
  familyMemberId?: string,
  limit: number = 10
): Promise<Note[]> {
  const params = new URLSearchParams();
  if (familyMemberId) params.set("family_member_id", familyMemberId);
  params.set("limit", String(limit));
  return get(`${familyUrl}/notes/recent?${params.toString()}`);
}

// ---------------------------------------------------------------------------
// Grocery — auth-derived actor, no more member_id params on protected routes
// ---------------------------------------------------------------------------

export function fetchGroceryItems(includePurchased?: boolean): Promise<GroceryItem[]> {
  const params = new URLSearchParams();
  if (includePurchased) params.set("include_purchased", "true");
  const qs = params.toString();
  return get(`${familyUrl}/groceries/current${qs ? `?${qs}` : ""}`);
}

export function fetchPendingReviewItems(): Promise<GroceryItem[]> {
  return get(`${familyUrl}/groceries/pending-review`);
}

export function createGroceryItem(
  payload: { title: string; quantity?: number; unit?: string; category?: string; preferred_store?: string; notes?: string }
): Promise<GroceryItem> {
  return post(`${familyUrl}/groceries/items`, payload);
}

export function updateGroceryItem(
  itemId: string,
  payload: { title?: string; is_purchased?: boolean; approval_status?: string }
): Promise<GroceryItem> {
  return patch(`${familyUrl}/groceries/items/${itemId}`, payload);
}

export function fetchPurchaseRequests(status?: string): Promise<PurchaseRequest[]> {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  const qs = params.toString();
  return get(`${familyUrl}/purchase-requests${qs ? `?${qs}` : ""}`);
}

export function createPurchaseRequest(
  payload: { title: string; type?: string; details?: string; quantity?: number; unit?: string; preferred_brand?: string; preferred_store?: string; urgency?: string }
): Promise<PurchaseRequest> {
  return post(`${familyUrl}/purchase-requests`, payload);
}

export function approvePurchaseRequest(requestId: string): Promise<PurchaseRequest> {
  return post(`${familyUrl}/purchase-requests/${requestId}/approve`, {});
}

export function rejectPurchaseRequest(requestId: string): Promise<PurchaseRequest> {
  return post(`${familyUrl}/purchase-requests/${requestId}/reject`, {});
}

export function convertPurchaseRequestToGrocery(requestId: string): Promise<GroceryItem> {
  return post(`${familyUrl}/purchase-requests/${requestId}/convert-to-grocery`);
}

// ---------------------------------------------------------------------------
// Dashboards — auth-derived actor
// ---------------------------------------------------------------------------

export function fetchPersonalDashboard(): Promise<any> {
  return get(`${familyUrl}/dashboard/personal`);
}

export function fetchParentDashboard(): Promise<any> {
  return get(`${familyUrl}/dashboard/parent`);
}

export function fetchChildDashboard(): Promise<any> {
  return get(`${familyUrl}/dashboard/child`);
}

export function fetchActionItems(status: string = "pending"): Promise<any[]> {
  return get(`${familyUrl}/action-items/current?status=${status}`);
}

// ---------------------------------------------------------------------------
// AI Chat — auth-derived actor
// ---------------------------------------------------------------------------

export async function sendChatMessage(
  message: string,
  surface: string = "personal",
  conversationId?: string,
): Promise<any> {
  return post(`${API_BASE_URL}/api/ai/chat`, {
    family_id: FAMILY_ID,
    surface,
    message,
    conversation_id: conversationId || undefined,
  });
}

export function fetchDailyBrief(): Promise<any> {
  return post(`${API_BASE_URL}/api/ai/brief/daily`, {
    family_id: FAMILY_ID,
  });
}

// ---------------------------------------------------------------------------
// Weekly Meal Plans — auth-derived actor
// ---------------------------------------------------------------------------

export function generateWeeklyMealPlan(
  weekStartDate: string,
  opts?: { constraints?: Record<string, unknown>; answers?: Record<string, unknown> },
): Promise<WeeklyMealPlanGenerateResponse> {
  return post(`${familyUrl}/meals/weekly/generate`, {
    week_start_date: weekStartDate,
    constraints: opts?.constraints,
    answers: opts?.answers,
  });
}

export function fetchCurrentWeeklyPlan(): Promise<WeeklyMealPlan> {
  return get(`${familyUrl}/meals/weekly/current`);
}

export function fetchWeeklyPlan(planId: string): Promise<WeeklyMealPlan> {
  return get(`${familyUrl}/meals/weekly/${planId}`);
}

export function fetchWeeklyPlans(includeArchived?: boolean): Promise<WeeklyMealPlan[]> {
  const qs = includeArchived ? "?include_archived=true" : "";
  return get(`${familyUrl}/meals/weekly${qs}`);
}

export function updateWeeklyPlan(
  planId: string,
  payload: { title?: string; week_plan?: unknown; prep_plan?: unknown; grocery_plan?: unknown; plan_summary?: string },
): Promise<WeeklyMealPlan> {
  return patch(`${familyUrl}/meals/weekly/${planId}`, payload);
}

export function approveWeeklyPlan(planId: string): Promise<WeeklyMealPlan> {
  return post(`${familyUrl}/meals/weekly/${planId}/approve`);
}

export function archiveWeeklyPlan(planId: string): Promise<WeeklyMealPlan> {
  return post(`${familyUrl}/meals/weekly/${planId}/archive`);
}

export function regenerateWeeklyPlanDay(
  planId: string,
  day: string,
  mealTypes?: string[],
): Promise<WeeklyMealPlan> {
  return post(`${familyUrl}/meals/weekly/${planId}/regenerate-day`, {
    day,
    meal_types: mealTypes,
  });
}

export function fetchWeeklyPlanGroceries(planId: string): Promise<GroceryItem[]> {
  return get(`${familyUrl}/meals/weekly/${planId}/groceries`);
}

// ---------------------------------------------------------------------------
// Meal Reviews
// ---------------------------------------------------------------------------

export function createMealReview(payload: {
  weekly_plan_id?: string | null;
  linked_meal_ref?: string | null;
  meal_title: string;
  rating_overall: number;
  kid_acceptance?: number | null;
  effort?: number | null;
  cleanup?: number | null;
  leftovers?: string | null;
  repeat_decision: "repeat" | "tweak" | "retire";
  notes?: string | null;
}): Promise<MealReview> {
  return post(`${familyUrl}/meals/reviews`, { ...payload, member_id: "00000000-0000-0000-0000-000000000000" });
}

export function fetchMealReviews(limit: number = 50): Promise<MealReview[]> {
  return get(`${familyUrl}/meals/reviews?limit=${limit}`);
}

export function fetchMealReviewSummary(): Promise<MealReviewSummary> {
  return get(`${familyUrl}/meals/reviews/summary`);
}

// ---------------------------------------------------------------------------
// Integrations (dev/operator only)
// ---------------------------------------------------------------------------

export async function ingestGoogleCalendar(
  payload: { external_id: string; title: string; starts_at: string; ends_at: string; description?: string; location?: string }
): Promise<unknown> {
  return post(`${API_BASE_URL}/integrations/google-calendar/ingest`, {
    family_id: FAMILY_ID,
    payload,
  });
}

export async function ingestYnabBill(
  payload: { external_id: string; title: string; amount_cents: number; due_date: string; description?: string }
): Promise<unknown> {
  return post(`${API_BASE_URL}/integrations/ynab/ingest`, {
    family_id: FAMILY_ID,
    payload,
  });
}
