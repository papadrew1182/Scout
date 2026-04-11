import { API_BASE_URL, FAMILY_ID } from "./config";
import type {
  Bill,
  ChoreTemplate,
  DailyWin,
  Event,
  FamilyMember,
  Meal,
  Note,
  PersonalTask,
  Routine,
  StepCompletion,
  TaskInstance,
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
