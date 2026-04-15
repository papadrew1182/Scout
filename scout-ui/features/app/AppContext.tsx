/**
 * Session 3 global state container — Block 2 contract-aligned version.
 *
 * Holds the only canonical copy of:
 *   - me                  (GET /api/me)
 *   - familyContext       (GET /api/family/context/current)
 *   - householdToday      (GET /api/household/today)
 *   - rewardsWeek         (GET /api/rewards/week/current)
 *   - connectors          (GET /api/connectors)
 *   - connectorsHealth    (GET /api/connectors/health)
 *   - calendarExports     (GET /api/calendar/exports/upcoming  — mock only)
 *   - controlPlaneSummary (GET /api/control-plane/summary      — mock only)
 *   - completionMutations (in-flight optimistic state)
 *   - uiState             (focused child, completion-sheet target, toast)
 *
 * Completion mutation contract (POST /api/household/completions) is the
 * four-field bare echo:
 *   { task_occurrence_id, status, daily_win_recomputed, reward_preview_changed }
 *
 * No `updated_block` or `daily_win_preview` echo. The reducer keeps a
 * single safe optimistic mutation — flipping the LOCAL occurrence's
 * status to "complete" inside the householdToday cache. Daily-win and
 * reward-preview state must come from a refetch of the affected slices
 * after the server tells us they changed.
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
  RewardsCurrentWeekResponse,
  TaskOccurrence,
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
  daily_win_recomputed: boolean;
  reward_preview_changed: boolean;
}

export interface UiState {
  /** Currently focused child filter on the Today board, or null = household-wide */
  focused_member_id: string | null;
  /** Open completion sheet target */
  completion_sheet_occurrence_id: string | null;
  /** Transient toast surfaced by the completion + reward flows */
  toast: { kind: "success" | "error"; message: string } | null;
}

export interface AppState {
  me: RemoteSlice<MeResponse>;
  familyContext: RemoteSlice<FamilyContextResponse>;
  householdToday: RemoteSlice<HouseholdTodayResponse>;
  rewardsWeek: RemoteSlice<RewardsCurrentWeekResponse>;
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
  uiState: { focused_member_id: null, completion_sheet_occurrence_id: null, toast: null },
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
  | {
      type: "completion/success";
      occurrence_id: string;
      result: CompletionResponse;
    }
  | { type: "completion/error"; occurrence_id: string; error: string }
  | { type: "ui/focusMember"; member_id: string | null }
  | { type: "ui/openCompletionSheet"; occurrence_id: string | null }
  | { type: "ui/showToast"; kind: "success" | "error"; message: string }
  | { type: "ui/dismissToast" };

function flipOccurrenceComplete(
  state: AppState,
  occurrence_id: string,
): AppState {
  const today = state.householdToday.data;
  if (!today) return state;
  const flipOcc = (o: TaskOccurrence): TaskOccurrence =>
    o.task_occurrence_id === occurrence_id ? { ...o, status: "complete" } : o;
  const blocks = today.blocks.map((b) => {
    const occs = b.occurrences.map(flipOcc);
    const all_done = occs.length > 0 && occs.every((o) => o.status === "complete");
    return {
      ...b,
      occurrences: occs,
      status: all_done ? ("done" as const) : b.status,
    };
  });
  const standalone_chores = today.standalone_chores.map(flipOcc);
  const weekly_items = today.weekly_items.map(flipOcc);
  // Recompute summary counts from the flipped state.
  const all = [
    ...blocks.flatMap((b) => b.occurrences),
    ...standalone_chores,
    ...weekly_items,
  ];
  const summary = {
    due_count: all.filter((o) => o.status === "open" || o.status === "late").length,
    completed_count: all.filter((o) => o.status === "complete").length,
    late_count: all.filter((o) => o.status === "late").length,
  };
  return {
    ...state,
    householdToday: {
      ...state.householdToday,
      data: { ...today, blocks, standalone_chores, weekly_items, summary },
    },
  };
}

function reducer(state: AppState, action: Action): AppState {
  switch (action.type) {
    case "slice/loading": {
      const slice = state[action.slice] as RemoteSlice<any>;
      return { ...state, [action.slice]: { ...slice, status: "loading", error: null } };
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
            daily_win_recomputed: false,
            reward_preview_changed: false,
          },
        },
      };
    case "completion/success": {
      const flipped = flipOccurrenceComplete(state, action.occurrence_id);
      return {
        ...flipped,
        completionMutations: {
          ...flipped.completionMutations,
          [action.occurrence_id]: {
            occurrence_id: action.occurrence_id,
            status: "success",
            error: null,
            daily_win_recomputed: action.result.daily_win_recomputed,
            reward_preview_changed: action.result.reward_preview_changed,
          },
        },
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
            daily_win_recomputed: false,
            reward_preview_changed: false,
          },
        },
      };
    case "ui/focusMember":
      return { ...state, uiState: { ...state.uiState, focused_member_id: action.member_id } };
    case "ui/openCompletionSheet":
      return {
        ...state,
        uiState: {
          ...state.uiState,
          completion_sheet_occurrence_id: action.occurrence_id,
        },
      };
    case "ui/showToast":
      return {
        ...state,
        uiState: {
          ...state.uiState,
          toast: { kind: action.kind, message: action.message },
        },
      };
    case "ui/dismissToast":
      return { ...state, uiState: { ...state.uiState, toast: null } };
    default:
      return state;
  }
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

export interface CompletionInput {
  task_occurrence_id: string;
  notes?: string;
  completion_mode?: "manual" | "auto" | "parent_override" | "ai_recorded";
}

interface AppContextValue {
  state: AppState;
  loadSlice: (slice: SliceKey, force?: boolean) => Promise<void>;
  refreshAll: () => Promise<void>;
  /**
   * Post a completion. The returned promise resolves once the network
   * round-trip + any required follow-up refetches finish.
   */
  completeOccurrence: (input: string | CompletionInput) => Promise<void>;
  focusMember: (member_id: string | null) => void;
  openCompletionSheet: (occurrence_id: string | null) => void;
  showToast: (kind: "success" | "error", message: string) => void;
  dismissToast: () => void;
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
    // intentional: read state inside closure so we don't re-create on every render
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
    async (input: string | CompletionInput) => {
      const args: CompletionInput = typeof input === "string" ? { task_occurrence_id: input } : input;
      const occurrence_id = args.task_occurrence_id;

      // We need the actor's family_member_id from /api/me. If unknown
      // yet, hydrate it first so the completion has a real `completed_by`.
      let actor = state.me.data?.user.family_member_id;
      if (!actor) {
        try {
          const me = await scoutClient.getMe();
          dispatch({ type: "slice/ready", slice: "me", data: me });
          actor = me.user.family_member_id;
        } catch (e: any) {
          dispatch({
            type: "completion/error",
            occurrence_id,
            error: e?.message ?? String(e),
          });
          dispatch({
            type: "ui/showToast",
            kind: "error",
            message: "Couldn't identify the current user.",
          });
          return;
        }
      }

      dispatch({ type: "completion/start", occurrence_id });
      try {
        const result = await scoutClient.postCompletion({
          task_occurrence_id: occurrence_id,
          completed_by_family_member_id: actor!,
          completion_mode: args.completion_mode ?? "manual",
          notes: args.notes,
        });
        dispatch({ type: "completion/success", occurrence_id, result });

        // Refetches: the contract says daily_win_recomputed /
        // reward_preview_changed flag a derived state change. When
        // either is set, refresh the affected slice. Default to
        // refreshing both when daily_win_recomputed is true (since
        // daily-win counts feed the rewards preview).
        const refetches: Promise<void>[] = [];
        if (result.daily_win_recomputed) {
          refetches.push(loadSlice("householdToday", true));
        }
        if (result.daily_win_recomputed || result.reward_preview_changed) {
          refetches.push(loadSlice("rewardsWeek", true));
        }
        if (refetches.length > 0) {
          await Promise.allSettled(refetches);
        }

        dispatch({ type: "ui/showToast", kind: "success", message: "Marked complete." });
      } catch (e: any) {
        dispatch({
          type: "completion/error",
          occurrence_id,
          error: e?.message ?? String(e),
        });
        dispatch({
          type: "ui/showToast",
          kind: "error",
          message: "Couldn't mark complete. Please try again.",
        });
      }
    },
    [loadSlice, state.me.data?.user.family_member_id],
  );

  const focusMember = useCallback(
    (member_id: string | null) => dispatch({ type: "ui/focusMember", member_id }),
    [],
  );

  const openCompletionSheet = useCallback(
    (occurrence_id: string | null) =>
      dispatch({ type: "ui/openCompletionSheet", occurrence_id }),
    [],
  );

  const showToast = useCallback(
    (kind: "success" | "error", message: string) =>
      dispatch({ type: "ui/showToast", kind, message }),
    [],
  );

  const dismissToast = useCallback(() => dispatch({ type: "ui/dismissToast" }), []);

  // Auto-hydrate the foundational slices once on mount.
  useEffect(() => {
    loadSlice("me");
    loadSlice("familyContext");
    loadSlice("householdToday");
    loadSlice("rewardsWeek");
  }, [loadSlice]);

  // Auto-dismiss toasts after 4 seconds.
  useEffect(() => {
    if (!state.uiState.toast) return;
    const t = setTimeout(() => dismissToast(), 4000);
    return () => clearTimeout(t);
  }, [state.uiState.toast, dismissToast]);

  const value = useMemo<AppContextValue>(
    () => ({
      state,
      loadSlice,
      refreshAll,
      completeOccurrence,
      focusMember,
      openCompletionSheet,
      showToast,
      dismissToast,
    }),
    [
      state,
      loadSlice,
      refreshAll,
      completeOccurrence,
      focusMember,
      openCompletionSheet,
      showToast,
      dismissToast,
    ],
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
