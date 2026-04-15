/**
 * Thin convenience hooks over `AppContext`.
 *
 * Each hook auto-loads its slice the first time it is used and exposes
 * the standard `{data, status, error, refresh}` shape so leaf components
 * never reach into AppContext directly for slice metadata.
 */

import { useEffect } from "react";

import {
  CalendarExportsResponse,
  ConnectorsHealthResponse,
  ConnectorsResponse,
  ControlPlaneSummaryResponse,
  FamilyContextResponse,
  HouseholdTodayResponse,
  MeResponse,
  RewardWeekResponse,
} from "../lib/contracts";
import { LoadStatus, RemoteSlice, useAppContext } from "../app/AppContext";

interface UseSliceResult<T> {
  data: T | null;
  status: LoadStatus;
  error: string | null;
  loaded_at: number | null;
  refresh: () => Promise<void>;
}

function useSlice<T>(
  slice:
    | "me"
    | "familyContext"
    | "householdToday"
    | "rewardsWeek"
    | "connectors"
    | "connectorsHealth"
    | "calendarExports"
    | "controlPlaneSummary",
): UseSliceResult<T> {
  const { state, loadSlice } = useAppContext();
  const value = state[slice] as RemoteSlice<T>;
  useEffect(() => {
    if (value.status === "idle") loadSlice(slice);
  }, [value.status, loadSlice, slice]);
  return {
    data: value.data,
    status: value.status,
    error: value.error,
    loaded_at: value.loaded_at,
    refresh: () => loadSlice(slice, true),
  };
}

export function useMe() {
  return useSlice<MeResponse>("me");
}

export function useFamilyContext() {
  return useSlice<FamilyContextResponse>("familyContext");
}

export function useHouseholdToday() {
  return useSlice<HouseholdTodayResponse>("householdToday");
}

export function useRewardsWeek() {
  return useSlice<RewardWeekResponse>("rewardsWeek");
}

export function useConnectors() {
  return useSlice<ConnectorsResponse>("connectors");
}

export function useConnectorsHealth() {
  return useSlice<ConnectorsHealthResponse>("connectorsHealth");
}

export function useCalendarExports() {
  return useSlice<CalendarExportsResponse>("calendarExports");
}

export function useControlPlaneSummary() {
  return useSlice<ControlPlaneSummaryResponse>("controlPlaneSummary");
}

/**
 * Mutator hook for marking a task complete from anywhere in the tree.
 * Returns `{run, statusOf}` — `run(occurrence_id)` posts the completion;
 * `statusOf(occurrence_id)` reports the current in-flight state for
 * optimistic UI.
 */
export function useCompletionMutation() {
  const { state, completeOccurrence } = useAppContext();
  return {
    run: completeOccurrence,
    statusOf: (occurrence_id: string) =>
      state.completionMutations[occurrence_id]?.status ?? null,
    errorOf: (occurrence_id: string) =>
      state.completionMutations[occurrence_id]?.error ?? null,
  };
}

/**
 * UI hooks (focus filter, sheet open state).
 */
export function useUiFocusMember() {
  const { state, focusMember } = useAppContext();
  return { focused_member_id: state.uiState.focused_member_id, setFocus: focusMember };
}

export function useUiCompletionSheet() {
  const { state, openCompletionSheet } = useAppContext();
  return {
    occurrence_id: state.uiState.completion_sheet_occurrence_id,
    open: (id: string) => openCompletionSheet(id),
    close: () => openCompletionSheet(null),
  };
}
