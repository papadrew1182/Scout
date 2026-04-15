/**
 * Real Session 3 ScoutClient — wraps `fetch` against the published API.
 *
 * Endpoints are the canonical Session 2 routes shipped in
 * backend/app/routes/canonical.py. As of Session 2 block 3 (commit
 * 3a3bf31), every endpoint Session 3 consumes is real and DB-backed —
 * including /api/calendar/exports/upcoming and /api/control-plane/summary,
 * which were the two stub holdouts in Session 3 block 3.
 */

import { API_BASE_URL } from "../../lib/config";
import {
  CalendarExportsResponse,
  CompletionRequest,
  CompletionResponse,
  ConnectorsHealthResponse,
  ConnectorsResponse,
  ControlPlaneSummaryResponse,
  FamilyContextResponse,
  HouseholdTodayResponse,
  MeResponse,
  RewardsCurrentWeekResponse,
  ScoutClient,
} from "./contracts";

let _bearerToken: string | null = null;

export function setSessionBearer(token: string | null): void {
  _bearerToken = token;
}

async function request<T>(
  method: "GET" | "POST",
  path: string,
  body?: unknown,
): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (_bearerToken) headers.Authorization = `Bearer ${_bearerToken}`;
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${method} ${path} → ${res.status}: ${text.slice(0, 200)}`);
  }
  return (await res.json()) as T;
}

export const realClient: ScoutClient = {
  getMe: () => request<MeResponse>("GET", "/api/me"),
  getFamilyContext: () =>
    request<FamilyContextResponse>("GET", "/api/family/context/current"),
  getHouseholdToday: () =>
    request<HouseholdTodayResponse>("GET", "/api/household/today"),
  postCompletion: (body: CompletionRequest) =>
    request<CompletionResponse>("POST", "/api/household/completions", body),
  getRewardsWeek: () =>
    request<RewardsCurrentWeekResponse>("GET", "/api/rewards/week/current"),
  getConnectors: () => request<ConnectorsResponse>("GET", "/api/connectors"),
  getConnectorsHealth: () =>
    request<ConnectorsHealthResponse>("GET", "/api/connectors/health"),
  getCalendarExports: () =>
    request<CalendarExportsResponse>("GET", "/api/calendar/exports/upcoming"),
  getControlPlaneSummary: () =>
    request<ControlPlaneSummaryResponse>("GET", "/api/control-plane/summary"),
};
