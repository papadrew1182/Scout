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

async function get<T>(url: string): Promise<T> {
  const res = await fetch(url);
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
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    console.error("API ERROR:", res.status, url, text);
    throw new Error(`Failed to fetch`);
  }
  return await res.json();
}

export function fetchMembers(): Promise<FamilyMember[]> {
  return get(`${familyUrl}/members`);
}

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

export function fetchRoutines(memberId?: string): Promise<Routine[]> {
  let url = `${familyUrl}/routines`;
  if (memberId) url += `?member_id=${memberId}`;
  return get(url);
}

export function fetchChoreTemplates(): Promise<ChoreTemplate[]> {
  return get(`${familyUrl}/chore-templates`);
}

export function fetchDailyWins(
  memberId: string,
  startDate: string,
  endDate: string
): Promise<DailyWin[]> {
  return get(
    `${familyUrl}/daily-wins?member_id=${memberId}&start_date=${startDate}&end_date=${endDate}`
  );
}

export function markTaskComplete(instanceId: string): Promise<TaskInstance> {
  return post(`${familyUrl}/task-instances/${instanceId}/complete`, {});
}

export async function updateStepCompletion(
  instanceId: string,
  stepCompletionId: string,
  isCompleted: boolean
): Promise<StepCompletion> {
  const res = await fetch(
    `${familyUrl}/task-instances/${instanceId}/steps/${stepCompletionId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_completed: isCompleted }),
    }
  );
  if (!res.ok) throw new Error(`PATCH step failed: ${res.status}`);
  return res.json();
}

export function generateTasks(date: string): Promise<TaskInstance[]> {
  return post(`${familyUrl}/task-instances/generate?target_date=${date}`);
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
  const res = await fetch(url, { method: "POST" });
  if (!res.ok) {
    throw new PayoutError(res.status, `payout request failed (${res.status})`);
  }
  return res.json();
}

// ---- Meals ----

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

// ---- Calendar ----

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

// ---- Personal Tasks ----

export function fetchTopPersonalTasks(
  assignedTo: string,
  limit: number = 5
): Promise<PersonalTask[]> {
  return get(
    `${familyUrl}/personal-tasks/top?assigned_to=${assignedTo}&limit=${limit}`
  );
}

// ---- Finance ----

export function fetchUnpaidBills(): Promise<Bill[]> {
  return get(`${familyUrl}/bills/unpaid`);
}

// ---- Notes ----

export function fetchRecentNotes(
  familyMemberId?: string,
  limit: number = 10
): Promise<Note[]> {
  const params = new URLSearchParams();
  if (familyMemberId) params.set("family_member_id", familyMemberId);
  params.set("limit", String(limit));
  return get(`${familyUrl}/notes/recent?${params.toString()}`);
}

// ---- Grocery ----

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
  memberId: string,
  payload: { title: string; quantity?: number; unit?: string; category?: string; preferred_store?: string; notes?: string }
): Promise<GroceryItem> {
  return post(`${familyUrl}/groceries/items?member_id=${memberId}`, payload);
}

export function updateGroceryItem(
  memberId: string,
  itemId: string,
  payload: { title?: string; is_purchased?: boolean; approval_status?: string }
): Promise<GroceryItem> {
  const res = fetch(`${familyUrl}/groceries/items/${itemId}?member_id=${memberId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return res.then(async (r) => {
    if (!r.ok) { const t = await r.text().catch(() => ""); console.error("API ERROR:", r.status, t); throw new Error("Failed to fetch"); }
    return r.json();
  });
}

export function fetchPurchaseRequests(status?: string): Promise<PurchaseRequest[]> {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  const qs = params.toString();
  return get(`${familyUrl}/purchase-requests${qs ? `?${qs}` : ""}`);
}

export function createPurchaseRequest(
  memberId: string,
  payload: { title: string; type?: string; details?: string; quantity?: number; unit?: string; preferred_brand?: string; preferred_store?: string; urgency?: string }
): Promise<PurchaseRequest> {
  return post(`${familyUrl}/purchase-requests?member_id=${memberId}`, payload);
}

export function approvePurchaseRequest(reviewerId: string, requestId: string): Promise<PurchaseRequest> {
  return post(`${familyUrl}/purchase-requests/${requestId}/approve?reviewer_id=${reviewerId}`, {});
}

export function rejectPurchaseRequest(reviewerId: string, requestId: string): Promise<PurchaseRequest> {
  return post(`${familyUrl}/purchase-requests/${requestId}/reject?reviewer_id=${reviewerId}`, {});
}

export function convertPurchaseRequestToGrocery(reviewerId: string, requestId: string): Promise<GroceryItem> {
  return post(`${familyUrl}/purchase-requests/${requestId}/convert-to-grocery?reviewer_id=${reviewerId}`);
}

// ---- Dashboards ----

export function fetchPersonalDashboard(memberId: string): Promise<any> {
  return get(`${familyUrl}/dashboard/personal?member_id=${memberId}`);
}

export function fetchParentDashboard(memberId: string): Promise<any> {
  return get(`${familyUrl}/dashboard/parent?member_id=${memberId}`);
}

export function fetchChildDashboard(memberId: string): Promise<any> {
  return get(`${familyUrl}/dashboard/child?member_id=${memberId}`);
}

export function fetchActionItems(memberId: string, status: string = "pending"): Promise<any[]> {
  return get(`${familyUrl}/action-items/current?member_id=${memberId}&status=${status}`);
}

// ---- AI Chat ----

export async function sendChatMessage(
  memberId: string,
  message: string,
  surface: string = "personal",
  conversationId?: string,
): Promise<any> {
  return post(`${API_BASE_URL}/api/ai/chat`, {
    family_id: FAMILY_ID,
    member_id: memberId,
    surface,
    message,
    conversation_id: conversationId || undefined,
  });
}

export function fetchDailyBrief(memberId: string): Promise<any> {
  return post(`${API_BASE_URL}/api/ai/brief/daily`, {
    family_id: FAMILY_ID,
    member_id: memberId,
  });
}

// ---- Weekly Meal Plans ----

export function generateWeeklyMealPlan(
  memberId: string,
  weekStartDate: string,
  opts?: { constraints?: Record<string, unknown>; answers?: Record<string, unknown> },
): Promise<WeeklyMealPlanGenerateResponse> {
  return post(`${familyUrl}/meals/weekly/generate`, {
    member_id: memberId,
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

export async function updateWeeklyPlan(
  planId: string,
  memberId: string,
  payload: { title?: string; week_plan?: unknown; prep_plan?: unknown; grocery_plan?: unknown; plan_summary?: string },
): Promise<WeeklyMealPlan> {
  const res = await fetch(`${familyUrl}/meals/weekly/${planId}?member_id=${memberId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    console.error("API ERROR:", res.status, text);
    throw new Error("Failed to update weekly plan");
  }
  return res.json();
}

export function approveWeeklyPlan(planId: string, memberId: string): Promise<WeeklyMealPlan> {
  return post(`${familyUrl}/meals/weekly/${planId}/approve`, { member_id: memberId });
}

export function archiveWeeklyPlan(planId: string, memberId: string): Promise<WeeklyMealPlan> {
  return post(`${familyUrl}/meals/weekly/${planId}/archive?member_id=${memberId}`);
}

export function regenerateWeeklyPlanDay(
  planId: string,
  memberId: string,
  day: string,
  mealTypes?: string[],
): Promise<WeeklyMealPlan> {
  return post(`${familyUrl}/meals/weekly/${planId}/regenerate-day`, {
    member_id: memberId,
    day,
    meal_types: mealTypes,
  });
}

export function fetchWeeklyPlanGroceries(planId: string): Promise<GroceryItem[]> {
  return get(`${familyUrl}/meals/weekly/${planId}/groceries`);
}

// ---- Meal Reviews ----

export function createMealReview(payload: {
  member_id: string;
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
  return post(`${familyUrl}/meals/reviews`, payload);
}

export function fetchMealReviews(limit: number = 50): Promise<MealReview[]> {
  return get(`${familyUrl}/meals/reviews?limit=${limit}`);
}

export function fetchMealReviewSummary(): Promise<MealReviewSummary> {
  return get(`${familyUrl}/meals/reviews/summary`);
}

// ---- Integrations (dev/operator only) ----

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
