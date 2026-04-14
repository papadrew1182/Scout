import { API_BASE_URL } from "./config";
import type {
  Bill,
  ChoreTemplate,
  DailyWin,
  Event,
  FamilyAISettings,
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

// ---------------------------------------------------------------------------
// Auth + family state — set by AuthProvider, read by all API calls
// ---------------------------------------------------------------------------

let _authToken: string | null = null;
let _familyId: string | null = null;

export function setApiToken(token: string | null) { _authToken = token; }
export function setApiFamilyId(familyId: string | null) { _familyId = familyId; }

function familyUrl(): string {
  if (!_familyId) throw new Error("No active family. Sign in first.");
  return `${API_BASE_URL}/families/${_familyId}`;
}

function authHeaders(): Record<string, string> {
  return _authToken ? { Authorization: `Bearer ${_authToken}` } : {};
}

// Centralized 401 handler
let _onUnauthorized: (() => void) | null = null;
export function setOnUnauthorized(handler: () => void) { _onUnauthorized = handler; }
function _handleUnauthorized() {
  _authToken = null;
  _familyId = null;
  if (_onUnauthorized) _onUnauthorized();
}

// ---------------------------------------------------------------------------
// Base helpers
// ---------------------------------------------------------------------------

async function get<T>(url: string): Promise<T> {
  const res = await fetch(url, { headers: authHeaders() });
  if (res.status === 401) { _handleUnauthorized(); throw new Error("Session expired"); }
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
  if (res.status === 401) { _handleUnauthorized(); throw new Error("Session expired"); }
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
  if (res.status === 401) { _handleUnauthorized(); throw new Error("Session expired"); }
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
  return get(`${familyUrl()}/members`);
}

// ---------------------------------------------------------------------------
// Task instances
// ---------------------------------------------------------------------------

export function fetchTaskInstances(
  date: string,
  memberId?: string
): Promise<TaskInstance[]> {
  let url = `${familyUrl()}/task-instances?instance_date=${date}`;
  if (memberId) url += `&member_id=${memberId}`;
  return get(url);
}

export function fetchStepCompletions(
  instanceId: string
): Promise<StepCompletion[]> {
  return get(`${familyUrl()}/task-instances/${instanceId}/steps`);
}

export function markTaskComplete(instanceId: string): Promise<TaskInstance> {
  return post(`${familyUrl()}/task-instances/${instanceId}/complete`, {});
}

export async function updateStepCompletion(
  instanceId: string,
  stepCompletionId: string,
  isCompleted: boolean
): Promise<StepCompletion> {
  return patch(
    `${familyUrl()}/task-instances/${instanceId}/steps/${stepCompletionId}`,
    { is_completed: isCompleted },
  );
}

export function generateTasks(date: string): Promise<TaskInstance[]> {
  return post(`${familyUrl()}/task-instances/generate?target_date=${date}`);
}

// ---------------------------------------------------------------------------
// Routines / Chores
// ---------------------------------------------------------------------------

export function fetchRoutines(memberId?: string): Promise<Routine[]> {
  let url = `${familyUrl()}/routines`;
  if (memberId) url += `?member_id=${memberId}`;
  return get(url);
}

export function fetchChoreTemplates(): Promise<ChoreTemplate[]> {
  return get(`${familyUrl()}/chore-templates`);
}

export function fetchRoutineSteps(routineId: string): Promise<any[]> {
  return get(`${familyUrl()}/routines/${routineId}/steps`);
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
    `${familyUrl()}/daily-wins?member_id=${memberId}&start_date=${startDate}&end_date=${endDate}`
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
  const url = `${familyUrl()}/allowance/weekly-payout?member_id=${memberId}&baseline_cents=${baselineCents}&week_start=${weekStart}`;
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
  return get(`${familyUrl()}/meals${qs ? `?${qs}` : ""}`);
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
  return get(`${familyUrl()}/events${qs ? `?${qs}` : ""}`);
}

// ---------------------------------------------------------------------------
// Personal Tasks
// ---------------------------------------------------------------------------

export function fetchTopPersonalTasks(
  assignedTo: string,
  limit: number = 5
): Promise<PersonalTask[]> {
  return get(
    `${familyUrl()}/personal-tasks/top?assigned_to=${assignedTo}&limit=${limit}`
  );
}

// ---------------------------------------------------------------------------
// Finance
// ---------------------------------------------------------------------------

export function fetchUnpaidBills(): Promise<Bill[]> {
  return get(`${familyUrl()}/bills/unpaid`);
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
  return get(`${familyUrl()}/notes/recent?${params.toString()}`);
}

// ---------------------------------------------------------------------------
// Grocery — auth-derived actor, no more member_id params on protected routes
// ---------------------------------------------------------------------------

export function fetchGroceryItems(includePurchased?: boolean): Promise<GroceryItem[]> {
  const params = new URLSearchParams();
  if (includePurchased) params.set("include_purchased", "true");
  const qs = params.toString();
  return get(`${familyUrl()}/groceries/current${qs ? `?${qs}` : ""}`);
}

export function fetchPendingReviewItems(): Promise<GroceryItem[]> {
  return get(`${familyUrl()}/groceries/pending-review`);
}

export function createGroceryItem(
  payload: { title: string; quantity?: number; unit?: string; category?: string; preferred_store?: string; notes?: string }
): Promise<GroceryItem> {
  return post(`${familyUrl()}/groceries/items`, payload);
}

export function updateGroceryItem(
  itemId: string,
  payload: { title?: string; is_purchased?: boolean; approval_status?: string }
): Promise<GroceryItem> {
  return patch(`${familyUrl()}/groceries/items/${itemId}`, payload);
}

export function fetchPurchaseRequests(status?: string): Promise<PurchaseRequest[]> {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  const qs = params.toString();
  return get(`${familyUrl()}/purchase-requests${qs ? `?${qs}` : ""}`);
}

export function createPurchaseRequest(
  payload: { title: string; type?: string; details?: string; quantity?: number; unit?: string; preferred_brand?: string; preferred_store?: string; urgency?: string }
): Promise<PurchaseRequest> {
  return post(`${familyUrl()}/purchase-requests`, payload);
}

export function approvePurchaseRequest(requestId: string): Promise<PurchaseRequest> {
  return post(`${familyUrl()}/purchase-requests/${requestId}/approve`, {});
}

export function rejectPurchaseRequest(requestId: string): Promise<PurchaseRequest> {
  return post(`${familyUrl()}/purchase-requests/${requestId}/reject`, {});
}

export function convertPurchaseRequestToGrocery(requestId: string): Promise<GroceryItem> {
  return post(`${familyUrl()}/purchase-requests/${requestId}/convert-to-grocery`);
}

// ---------------------------------------------------------------------------
// Dashboards — auth-derived actor
// ---------------------------------------------------------------------------

export function fetchPersonalDashboard(): Promise<any> {
  return get(`${familyUrl()}/dashboard/personal`);
}

export function fetchParentDashboard(): Promise<any> {
  return get(`${familyUrl()}/dashboard/parent`);
}

export function fetchParentDashboardInsight(): Promise<{
  status: string;
  narrative: string;
  model: string | null;
  as_of: string;
  source: string;
}> {
  return get(`${familyUrl()}/dashboard/parent/insight`);
}

export interface HomeworkChildRollup {
  member_id: string;
  first_name: string;
  sessions: number;
  subjects: Record<string, number>;
  last_at: string | null;
}
export interface HomeworkSummary {
  days: number;
  total_sessions: number;
  children: HomeworkChildRollup[];
}

export function fetchHomeworkSummary(days: number = 7): Promise<HomeworkSummary> {
  return get(`${familyUrl()}/homework/summary?days=${days}`);
}

export function fetchChildDashboard(): Promise<any> {
  return get(`${familyUrl()}/dashboard/child`);
}

export function fetchActionItems(status: string = "pending"): Promise<any[]> {
  return get(`${familyUrl()}/action-items/current?status=${status}`);
}

export function fetchActionItem(id: string): Promise<any> {
  return get(`${familyUrl()}/action-items/${id}`);
}

export function resolveActionItem(id: string): Promise<any> {
  return post(`${familyUrl()}/action-items/${id}/resolve`);
}

// ---------------------------------------------------------------------------
// AI Chat — auth-derived actor
// ---------------------------------------------------------------------------

export interface AIHandoff {
  entity_type: string;
  entity_id: string;
  route_hint: string;
  summary: string;
}

export interface AIPendingConfirmation {
  tool_name: string;
  arguments: Record<string, unknown>;
  message: string;
}

export interface AIChatResult {
  conversation_id: string;
  response: string;
  tool_calls_made: number;
  model: string;
  tokens: { input?: number; output?: number };
  handoff?: AIHandoff | null;
  pending_confirmation?: AIPendingConfirmation | null;
}

export interface SendChatOptions {
  surface?: string;
  conversationId?: string;
  confirmTool?: { tool_name: string; arguments: Record<string, unknown> };
}

export async function sendChatMessage(
  message: string,
  surfaceOrOptions: string | SendChatOptions = "personal",
  conversationId?: string,
): Promise<AIChatResult> {
  // Backwards-compatible two-call signatures:
  //   sendChatMessage("msg", "personal", convId)
  //   sendChatMessage("", { confirmTool: {...}, conversationId })
  const opts: SendChatOptions =
    typeof surfaceOrOptions === "string"
      ? { surface: surfaceOrOptions, conversationId }
      : { surface: "personal", ...surfaceOrOptions };

  const traceId = `scout-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const body: Record<string, unknown> = {
    surface: opts.surface ?? "personal",
    message,
  };
  if (opts.conversationId) body.conversation_id = opts.conversationId;
  if (opts.confirmTool) body.confirm_tool = opts.confirmTool;

  const res = await fetch(`${API_BASE_URL}/api/ai/chat`, {
    method: "POST",
    headers: {
      ...authHeaders(),
      "Content-Type": "application/json",
      "X-Scout-Trace-Id": traceId,
    },
    body: JSON.stringify(body),
  });
  if (res.status === 401) { _handleUnauthorized(); throw new Error("Session expired"); }
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    console.error(`[Scout AI] trace=${traceId} status=${res.status} error=${text.slice(0, 200)}`);
    throw new Error(`AI request failed (${res.status})`);
  }
  return (await res.json()) as AIChatResult;
}

// ---------------------------------------------------------------------------
// Streaming chat — Server-Sent Events variant of sendChatMessage.
// ---------------------------------------------------------------------------

export type StreamEvent =
  | { type: "text"; text: string }
  | { type: "tool_start"; name: string }
  | { type: "tool_end"; name: string; ok: boolean }
  | { type: "done"; conversation_id: string; response: string; model: string;
      tool_calls_made: number; tokens: { input?: number; output?: number };
      handoff?: AIHandoff | null; pending_confirmation?: AIPendingConfirmation | null }
  | { type: "error"; message: string };

export interface StreamHandlers {
  onEvent: (event: StreamEvent) => void;
  onError?: (err: Error) => void;
}

/**
 * Stream an AI chat turn via /api/ai/chat/stream. The backend emits SSE
 * frames of the form `data: <json>\n\n`. This reader uses fetch +
 * ReadableStream (RN Web has no EventSource, but fetch's body reader
 * works). On network or parse failure the caller's onError fires and
 * no further events are dispatched.
 */
export async function sendChatMessageStream(
  message: string,
  opts: { surface?: string; conversationId?: string },
  handlers: StreamHandlers,
): Promise<void> {
  const traceId = `scout-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const body = {
    surface: opts.surface ?? "personal",
    message,
    conversation_id: opts.conversationId || undefined,
  };

  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}/api/ai/chat/stream`, {
      method: "POST",
      headers: {
        ...authHeaders(),
        "Content-Type": "application/json",
        Accept: "text/event-stream",
        "X-Scout-Trace-Id": traceId,
      },
      body: JSON.stringify(body),
    });
  } catch (e) {
    handlers.onError?.(e as Error);
    return;
  }

  if (res.status === 401) {
    _handleUnauthorized();
    handlers.onError?.(new Error("Session expired"));
    return;
  }
  if (!res.ok || !res.body) {
    const text = await res.text().catch(() => "");
    console.error(`[Scout AI stream] trace=${traceId} status=${res.status} error=${text.slice(0, 200)}`);
    handlers.onError?.(new Error(`AI stream failed (${res.status})`));
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // SSE frames are separated by a blank line (`\n\n`).
      let sepIdx: number;
      while ((sepIdx = buffer.indexOf("\n\n")) !== -1) {
        const frame = buffer.slice(0, sepIdx);
        buffer = buffer.slice(sepIdx + 2);
        if (!frame.trim()) continue;

        // Each frame may have multiple `data:` lines; we join them.
        const dataLines: string[] = [];
        for (const line of frame.split("\n")) {
          if (line.startsWith("data:")) {
            dataLines.push(line.slice(5).trimStart());
          }
        }
        if (dataLines.length === 0) continue;
        const payload = dataLines.join("\n");
        try {
          const event = JSON.parse(payload) as StreamEvent;
          handlers.onEvent(event);
        } catch (e) {
          console.warn(`[Scout AI stream] trace=${traceId} bad frame: ${payload.slice(0, 120)}`);
        }
      }
    }
  } catch (e) {
    handlers.onError?.(e as Error);
  }
}

// ---------------------------------------------------------------------------
// Platform readiness probe — used by ScoutPanel to render a disabled state
// when the backend reports ai_available=false.
// ---------------------------------------------------------------------------

export interface ReadyState {
  status: string;
  ai_available: boolean;
  transcribe_available?: boolean;
  auth_required?: boolean;
  environment?: string;
  reason?: string;
}

export interface ReceiptItem {
  title: string;
  quantity: number | null;
  unit: string | null;
  category: string | null;
  confidence: number;
}
export interface ReceiptExtractResult {
  items: ReceiptItem[];
  model: string;
  tokens: { input: number; output: number };
}

export async function extractReceipt(blob: Blob, filename: string = "receipt.jpg"): Promise<ReceiptExtractResult> {
  const form = new FormData();
  form.append("image", blob, filename);
  const res = await fetch(`${API_BASE_URL}/api/ai/receipt`, {
    method: "POST",
    headers: { ...authHeaders() },
    body: form,
  });
  if (res.status === 401) {
    _handleUnauthorized();
    throw new Error("Session expired");
  }
  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    throw new Error(`Receipt extraction failed (${res.status}): ${txt.slice(0, 200)}`);
  }
  return (await res.json()) as ReceiptExtractResult;
}

export async function transcribeAudio(blob: Blob): Promise<{ text: string; provider: string }> {
  const form = new FormData();
  form.append("audio", blob, "voice.webm");
  const res = await fetch(`${API_BASE_URL}/api/ai/transcribe`, {
    method: "POST",
    headers: { ...authHeaders() },
    body: form,
  });
  if (res.status === 401) {
    _handleUnauthorized();
    throw new Error("Session expired");
  }
  if (!res.ok) {
    throw new Error(`Transcription failed (${res.status})`);
  }
  return (await res.json()) as { text: string; provider: string };
}

export async function fetchReady(): Promise<ReadyState> {
  const res = await fetch(`${API_BASE_URL}/ready`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) {
    return { status: "unknown", ai_available: false, reason: `ready ${res.status}` };
  }
  return (await res.json()) as ReadyState;
}

export function fetchDailyBrief(): Promise<any> {
  return post(`${API_BASE_URL}/api/ai/brief/daily`, {
    family_id: _familyId,
  });
}

// ---------------------------------------------------------------------------
// Weekly Meal Plans — auth-derived actor
// ---------------------------------------------------------------------------

export function generateWeeklyMealPlan(
  weekStartDate: string,
  opts?: { constraints?: Record<string, unknown>; answers?: Record<string, unknown> },
): Promise<WeeklyMealPlanGenerateResponse> {
  return post(`${familyUrl()}/meals/weekly/generate`, {
    week_start_date: weekStartDate,
    constraints: opts?.constraints,
    answers: opts?.answers,
  });
}

export function fetchCurrentWeeklyPlan(): Promise<WeeklyMealPlan> {
  return get(`${familyUrl()}/meals/weekly/current`);
}

export function fetchWeeklyPlan(planId: string): Promise<WeeklyMealPlan> {
  return get(`${familyUrl()}/meals/weekly/${planId}`);
}

export function fetchWeeklyPlans(includeArchived?: boolean): Promise<WeeklyMealPlan[]> {
  const qs = includeArchived ? "?include_archived=true" : "";
  return get(`${familyUrl()}/meals/weekly${qs}`);
}

export function updateWeeklyPlan(
  planId: string,
  payload: { title?: string; week_plan?: unknown; prep_plan?: unknown; grocery_plan?: unknown; plan_summary?: string },
): Promise<WeeklyMealPlan> {
  return patch(`${familyUrl()}/meals/weekly/${planId}`, payload);
}

export function approveWeeklyPlan(planId: string): Promise<WeeklyMealPlan> {
  return post(`${familyUrl()}/meals/weekly/${planId}/approve`);
}

export function archiveWeeklyPlan(planId: string): Promise<WeeklyMealPlan> {
  return post(`${familyUrl()}/meals/weekly/${planId}/archive`);
}

export function regenerateWeeklyPlanDay(
  planId: string,
  day: string,
  mealTypes?: string[],
): Promise<WeeklyMealPlan> {
  return post(`${familyUrl()}/meals/weekly/${planId}/regenerate-day`, {
    day,
    meal_types: mealTypes,
  });
}

export function fetchWeeklyPlanGroceries(planId: string): Promise<GroceryItem[]> {
  return get(`${familyUrl()}/meals/weekly/${planId}/groceries`);
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
  return post(`${familyUrl()}/meals/reviews`, { ...payload, member_id: "00000000-0000-0000-0000-000000000000" });
}

export function fetchMealReviews(limit: number = 50): Promise<MealReview[]> {
  return get(`${familyUrl()}/meals/reviews?limit=${limit}`);
}

export function fetchMealReviewSummary(): Promise<MealReviewSummary> {
  return get(`${familyUrl()}/meals/reviews/summary`);
}

// ---------------------------------------------------------------------------
// Integrations (dev/operator only)
// ---------------------------------------------------------------------------

export async function ingestGoogleCalendar(
  payload: { external_id: string; title: string; starts_at: string; ends_at: string; description?: string; location?: string }
): Promise<unknown> {
  return post(`${API_BASE_URL}/integrations/google-calendar/ingest`, {
    family_id: _familyId,
    payload,
  });
}

export async function ingestYnabBill(
  payload: { external_id: string; title: string; amount_cents: number; due_date: string; description?: string }
): Promise<unknown> {
  return post(`${API_BASE_URL}/integrations/ynab/ingest`, {
    family_id: _familyId,
    payload,
  });
}

// ---------------------------------------------------------------------------
// Family AI settings + per-child learning context
// ---------------------------------------------------------------------------

export function fetchAISettings(): Promise<FamilyAISettings> {
  return get(`${familyUrl()}/ai-settings`);
}

export function updateAISettings(
  payload: Partial<FamilyAISettings>,
): Promise<FamilyAISettings> {
  return patch(`${familyUrl()}/ai-settings`, payload);
}

export function updateMemberLearning(
  memberId: string,
  payload: {
    grade_level?: string | null;
    learning_notes?: string | null;
    personality_notes?: string | null;
    read_aloud_enabled?: boolean;
  },
): Promise<FamilyMember> {
  return patch(`${familyUrl()}/members/${memberId}/learning`, payload);
}

// ---------------------------------------------------------------------------
// Conversation resume + end (Tier 3 Feature 12)
// ---------------------------------------------------------------------------

export interface ResumableConversation {
  conversation_id: string | null;
  updated_at: string | null;
  preview: string | null;
  kind: string | null;
}

export function fetchResumableConversation(
  surface: string = "personal",
): Promise<ResumableConversation> {
  return get(
    `${API_BASE_URL}/api/ai/conversations/resumable?surface=${encodeURIComponent(surface)}`,
  );
}

export function fetchConversationMessages(
  conversationId: string,
  familyId: string,
): Promise<Array<{
  id: string;
  role: string;
  content: string | null;
  tool_calls: unknown;
  tool_results: unknown;
  model: string | null;
  created_at: string;
}>> {
  return get(
    `${API_BASE_URL}/api/ai/conversations/${conversationId}/messages?family_id=${familyId}`,
  );
}

export function endConversation(conversationId: string): Promise<{ conversation_id: string; status: string }> {
  return post(`${API_BASE_URL}/api/ai/conversations/${conversationId}/end`);
}

// ---------------------------------------------------------------------------
// AI usage / cost rollup (Tier 3 Feature 11)
// ---------------------------------------------------------------------------

export interface AIUsageReport {
  days: number;
  as_of: string;
  total_messages: number;
  total_tokens: { input: number; output: number };
  approx_cost_usd: number;
  soft_cap_usd: number;
  cap_warning: boolean;
  by_day: Array<{
    date: string;
    messages: number;
    input: number;
    output: number;
    cost_usd: number;
  }>;
  by_model: Array<{
    model: string;
    messages: number;
    input: number;
    output: number;
    cost_usd: number;
  }>;
  by_member: Array<{
    member_id: string;
    first_name: string;
    messages: number;
    input: number;
    output: number;
    cost_usd: number;
  }>;
}

export function fetchAIUsage(days: number = 7): Promise<AIUsageReport> {
  return get(`${API_BASE_URL}/api/ai/usage?days=${days}`);
}
