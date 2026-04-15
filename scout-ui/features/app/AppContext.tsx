/**
 * Session 3 global state container.
 *
 * Holds the *only* copy of:
 *   - me
 *   - familyContext
 *   - householdToday
 *   - rewardsWeek
 *   - connectors
 *   - connectorsHealth
 *   - calendarExports
 *   - controlPlaneSummary
 *   - completionMutations (in-flight optimistic state)
 *   - uiState (navigation hints, child filter, panel state)
 *
 * Hooks under `features/hooks/` read and refresh slices of this state.
 * No leaf component should hold the only copy of household status.
 *
 * Purposefully simple: a single React context + a useReducer-style
 * mutator. No external state library. Easy to swap to Zustand/Recoil
 * later if any slice grows out of this shape.
 */

import {
  ReactNode,
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useReducer,
} from "react";

import {
  CalendarExportsResponse,
  CompletionResponse,
  ConnectorsHealthResponse,
  ConnectorsResponse,
  ControlPlaneSummaryResponse,
  FamilyContextResponse,
  HouseholdTodayResponse,
  MeResponse,
  RewardWeekResponse,
} from "../lib/contracts";
import { scoutClient } from "../lib/client";

// ---------------------------------------------------------------------------
// State shape
// ---------------------------------------------------------------------------

export type LoadStatus = "idle" | "loading" | "ready" | "error";

export interface RemoteSlice<T> {
  status: LoadStatus;
  data: T | null;
  error: string | null;
  loaded_at: number | null;
}

function emptySlice<T>(): RemoteSlice<T> {
  return { status: "idle", data: null, error: null, loaded_at: null };
}

export interface CompletionMutation {
  occurrence_id: string;
  status: "pending" | "success" | "error";
  error: string | null;
}

export interface UiState {
  /** Currently focused child filter on the Today board, or null = household-wide */
  focused_member_id: string | null;
  /** Open completion sheet target */
  completion_sheet_occurrence_id: string | null;
}

export interface AppState {
  me: RemoteSlice<MeResponse>;
  familyContext: RemoteSlice<FamilyContextResponse>;
  householdToday: RemoteSlice<HouseholdTodayResponse>;
  rewardsWeek: RemoteSlice<RewardWeekResponse>;
  connectors: RemoteSlice<ConnectorsResponse>;
  connectorsHealth: RemoteSlice<ConnectorsHealthResponse>;
  calendarExports: RemoteSlice<CalendarExportsResponse>;
  controlPlaneSummary: RemoteSlice<ControlPlaneSummaryResponse>;
  completionMutations: Record<string, CompletionMutation>;
  uiState: UiState;
}

const initialState: AppState = {
  me: emptySlice(),
  familyContext: emptySlice(),
  householdToday: emptySlice(),
  rewardsWeek: emptySlice(),
  connectors: emptySlice(),
  connectorsHealth: emptySlice(),
  calendarExports: emptySlice(),
  controlPlaneSummary: emptySlice(),
  completionMutations: {},
  uiState: { focused_member_id: null, completion_sheet_occurrence_id: null },
};

// ---------------------------------------------------------------------------
// Reducer
// ---------------------------------------------------------------------------

type SliceKey =
  | "me"
  | "familyContext"
  | "householdToday"
  | "rewardsWeek"
  | "connectors"
  | "connectorsHealth"
  | "calendarExports"
  | "controlPlaneSummary";

type Action =
  | { type: "slice/loading"; slice: SliceKey }
  | { type: "slice/ready"; slice: SliceKey; data: any }
  | { type: "slice/error"; slice: SliceKey; error: string }
  | { type: "completion/start"; occurrence_id: string }
  | { type: "completion/success"; occurrence_id: string; result: CompletionResponse }
  | { type: "completion/error"; occurrence_id: string; error: string }
  | { type: "ui/focusMember"; member_id: string | null }
  | { type: "ui/openCompletionSheet"; occurrence_id: string | null };

function reducer(state: AppState, action: Action): AppState {
  switch (action.type) {
    case "slice/loading": {
      const slice = state[action.slice] as RemoteSlice<any>;
      return {
        ...state,
        [action.slice]: { ...slice, status: "loading", error: null },
      };
    }
    case "slice/ready":
      return {
        ...state,
        [action.slice]: {
          status: "ready",
          data: action.data,
          error: null,
          loaded_at: Date.now(),
        },
      };
    case "slice/error":
      return {
        ...state,
        [action.slice]: {
          ...(state[action.slice] as RemoteSlice<any>),
          status: "error",
          error: action.error,
        },
      };
    case "completion/start":
      return {
        ...state,
        completionMutations: {
          ...state.completionMutations,
          [action.occurrence_id]: {
            occurrence_id: action.occurrence_id,
            status: "pending",
            error: null,
          },
        },
      };
    case "completion/success": {
      // Mark the occurrence complete inside the householdToday cache
      // optimistically so the UI updates without a refetch.
      const today = state.householdToday.data;
      let updatedToday = today;
      if (today) {
        const blocks = today.blocks.map((b) => {
          const occs = b.occurrences.map((o) =>
            o.occurrence_id === action.occurrence_id ? { ...o, status: "complete" as const } : o,
          );
          const allDone = occs.every((o) => o.status === "complete");
          return {
            ...b,
            occurrences: occs,
            status: allDone ? ("done" as const) : b.status,
          };
        });
        const standalone = today.standalone_occurrences.map((o) =>
          o.occurrence_id === action.occurrence_id ? { ...o, status: "complete" as const } : o,
        );
        // Replace the matching daily-win preview if the server echoed one.
        let dailyWin = today.daily_win_preview;
        if (action.result.daily_win_preview) {
          const echo = action.result.daily_win_preview;
          dailyWin = dailyWin.map((d) =>
            d.member_id === echo.member_id ? echo : d,
          );
        }
        updatedToday = {
          ...today,
          blocks,
          standalone_occurrences: standalone,
          daily_win_preview: dailyWin,
        };
      }
      return {
        ...state,
        completionMutations: {
          ...state.completionMutations,
          [action.occurrence_id]: {
            occurrence_id: action.occurrence_id,
            status: "success",
            error: null,
          },
        },
        householdToday: updatedToday
          ? { ...state.householdToday, data: updatedToday }
          : state.householdToday,
      };
    }
    case "completion/error":
      return {
        ...state,
        completionMutations: {
          ...state.completionMutations,
          [action.occurrence_id]: {
            occurrence_id: action.occurrence_id,
            status: "error",
            error: action.error,
          },
        },
      };
    case "ui/focusMember":
      return { ...state, uiState: { ...state.uiState, focused_member_id: action.member_id } };
    case "ui/openCompletionSheet":
      return {
        ...state,
        uiState: { ...state.uiState, completion_sheet_occurrence_id: action.occurrence_id },
      };
    default:
      return state;
  }
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

interface AppContextValue {
  state: AppState;
  // Slice loaders — idempotent; no-op if already loading/ready unless
  // `force` is true.
  loadSlice: (slice: SliceKey, force?: boolean) => Promise<void>;
  refreshAll: () => Promise<void>;
  // Completion mutation entry point.
  completeOccurrence: (occurrence_id: string) => Promise<void>;
  // UI mutators
  focusMember: (member_id: string | null) => void;
  openCompletionSheet: (occurrence_id: string | null) => void;
}

const AppContext = createContext<AppContextValue | null>(null);

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function AppProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);

  const loadSlice = useCallback(
    async (slice: SliceKey, force = false) => {
      const current = state[slice] as RemoteSlice<any>;
      if (!force && (current.status === "loading" || current.status === "ready")) return;
      dispatch({ type: "slice/loading", slice });
      try {
        const data = await runLoader(slice);
        dispatch({ type: "slice/ready", slice, data });
      } catch (e: any) {
        dispatch({ type: "slice/error", slice, error: e?.message ?? String(e) });
      }
    },
    // We deliberately don't depend on `state`; we read it inside the closure.
    // Capturing state would re-create loadSlice on every render, which would
    // cause hooks that depend on it to refire endlessly.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  const refreshAll = useCallback(async () => {
    await Promise.all([
      loadSlice("me", true),
      loadSlice("familyContext", true),
      loadSlice("householdToday", true),
      loadSlice("rewardsWeek", true),
      loadSlice("connectors", true),
      loadSlice("connectorsHealth", true),
      loadSlice("calendarExports", true),
      loadSlice("controlPlaneSummary", true),
    ]);
  }, [loadSlice]);

  const completeOccurrence = useCallback(
    async (occurrence_id: string) => {
      // Need the actor's member_id from `me`. If unknown yet, attempt to
      // hydrate it first.
      let actor = state.me.data?.member_id;
      if (!actor) {
        try {
          const me = await scoutClient.getMe();
          dispatch({ type: "slice/ready", slice: "me", data: me });
          actor = me.member_id;
        } catch (e: any) {
          dispatch({ type: "completion/error", occurrence_id, error: e?.message ?? String(e) });
          return;
        }
      }
      dispatch({ type: "completion/start", occurrence_id });
      try {
        const result = await scoutClient.postCompletion({
          occurrence_id,
          completed_by_member_id: actor!,
        });
        dispatch({ type: "completion/success", occurrence_id, result });
        // Refresh rewards in the background — completing a task may move
        // the daily-win and the weekly payout preview.
        loadSlice("rewardsWeek", true).catch(() => undefined);
      } catch (e: any) {
        dispatch({ type: "completion/error", occurrence_id, error: e?.message ?? String(e) });
      }
    },
    [loadSlice, state.me.data?.member_id],
  );

  const focusMember = useCallback(
    (member_id: string | null) => dispatch({ type: "ui/focusMember", member_id }),
    [],
  );

  const openCompletionSheet = useCallback(
    (occurrence_id: string | null) => dispatch({ type: "ui/openCompletionSheet", occurrence_id }),
    [],
  );

  // Auto-hydrate the foundational slices once on mount.
  useEffect(() => {
    loadSlice("me");
    loadSlice("familyContext");
    loadSlice("householdToday");
  }, [loadSlice]);

  const value = useMemo<AppContextValue>(
    () => ({
      state,
      loadSlice,
      refreshAll,
      completeOccurrence,
      focusMember,
      openCompletionSheet,
    }),
    [state, loadSlice, refreshAll, completeOccurrence, focusMember, openCompletionSheet],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useAppContext(): AppContextValue {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useAppContext must be used inside <AppProvider>");
  return ctx;
}

// ---------------------------------------------------------------------------
// Slice loader dispatch table
// ---------------------------------------------------------------------------

async function runLoader(slice: SliceKey): Promise<any> {
  switch (slice) {
    case "me":
      return scoutClient.getMe();
    case "familyContext":
      return scoutClient.getFamilyContext();
    case "householdToday":
      return scoutClient.getHouseholdToday();
    case "rewardsWeek":
      return scoutClient.getRewardsWeek();
    case "connectors":
      return scoutClient.getConnectors();
    case "connectorsHealth":
      return scoutClient.getConnectorsHealth();
    case "calendarExports":
      return scoutClient.getCalendarExports();
    case "controlPlaneSummary":
      return scoutClient.getControlPlaneSummary();
  }
}
