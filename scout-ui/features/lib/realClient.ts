/**
 * Real Session 3 ScoutClient — wraps `fetch` against the published API.
 *
 * Until Session 2 ships any of these endpoints they will return 404,
 * which is fine: the AppContext defaults to `mockClient` unless
 * `EXPO_PUBLIC_SCOUT_API_MODE === "real"` is set at build time.
 *
 * No legacy `lib/api.ts` paths are reused. Session 3 explicitly speaks
 * the published contracts and nothing else.
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
  RewardWeekResponse,
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
    request<RewardWeekResponse>("GET", "/api/rewards/week/current"),
  getConnectors: () => request<ConnectorsResponse>("GET", "/api/connectors"),
  getConnectorsHealth: () =>
    request<ConnectorsHealthResponse>("GET", "/api/connectors/health"),
  getCalendarExports: () =>
    request<CalendarExportsResponse>("GET", "/api/calendar/exports/upcoming"),
  getControlPlaneSummary: () =>
    request<ControlPlaneSummaryResponse>("GET", "/api/control-plane/summary"),
};
