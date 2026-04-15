/**
 * In-memory implementation of the Session 3 ScoutClient.
 *
 * Hooks consume this through `features/lib/client.ts`; nothing in the
 * UI layer should import from here directly.
 */

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
import {
  mockCalendarExports,
  mockConnectors,
  mockConnectorsHealth,
  mockControlPlaneSummary,
  mockFamilyContext,
  mockHouseholdToday,
  mockMe,
  mockPostCompletion,
  mockRewardsWeek,
} from "./mockData";

function delay<T>(value: T, ms = 80): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), ms));
}

export const mockClient: ScoutClient = {
  getMe: (): Promise<MeResponse> => delay(mockMe()),
  getFamilyContext: (): Promise<FamilyContextResponse> => delay(mockFamilyContext()),
  getHouseholdToday: (): Promise<HouseholdTodayResponse> => delay(mockHouseholdToday()),
  postCompletion: (body: CompletionRequest): Promise<CompletionResponse> =>
    delay(mockPostCompletion(body), 40),
  getRewardsWeek: (): Promise<RewardsCurrentWeekResponse> => delay(mockRewardsWeek()),
  getConnectors: (): Promise<ConnectorsResponse> => delay(mockConnectors()),
  getConnectorsHealth: (): Promise<ConnectorsHealthResponse> => delay(mockConnectorsHealth()),
  getCalendarExports: (): Promise<CalendarExportsResponse> => delay(mockCalendarExports()),
  getControlPlaneSummary: (): Promise<ControlPlaneSummaryResponse> =>
    delay(mockControlPlaneSummary()),
};
