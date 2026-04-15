/**
 * Centralized "what state is this slice in, and what banner copy goes
 * with it" helper.
 *
 * Every endpoint Session 3 consumes is real and DB-backed since Session
 * 2 block 3 (commit 3a3bf31), so the previous "endpoint not yet shipped"
 * narrative — and the regex sniff that distinguished it from a real
 * fetch failure — is gone. Surfaces now classify into four states:
 *
 *   "loading" → slice is idle or loading (render skeleton)
 *   "ok"      → slice is ready and has data
 *   "empty"   → slice is ready but data is null/empty-ish
 *   "error"   → slice errored; banner offers retry
 *
 * Surface keys still carry per-feed empty-state copy so the operating
 * surface speaks in its own vocabulary instead of generic "nothing to
 * show" text.
 */

import { LoadStatus } from "../app/AppContext";
import { SCOUT_CLIENT_MODE } from "./client";

export type AvailabilityKind = "loading" | "ok" | "empty" | "error";

export interface SliceShape {
  status: LoadStatus;
  error: string | null;
  data: unknown;
}

export interface AvailabilityView {
  kind: AvailabilityKind;
  title: string;
  body: string;
  retryable: boolean;
}

/**
 * Friendly per-surface labels for the empty state. Callers pass the
 * surface key so the banner speaks the surface's vocabulary
 * (calendar exports vs control-plane summary vs generic).
 */
export type SliceSurfaceKey =
  | "calendar_exports"
  | "control_plane_summary"
  | "generic";

const EMPTY_COPY: Record<SliceSurfaceKey, { title: string; body: string }> = {
  calendar_exports: {
    title: "No exports scheduled",
    body: "When Scout has anchor blocks ready to publish, they'll appear here.",
  },
  control_plane_summary: {
    title: "No operating activity",
    body: "Connectors, sync jobs, and publication are all quiet.",
  },
  generic: {
    title: "Nothing to show yet",
    body: "The feed is empty.",
  },
};

/**
 * Classify a slice into one of the four states and return banner copy
 * suitable for the given surface.
 */
export function classifySlice(
  slice: SliceShape,
  surface: SliceSurfaceKey = "generic",
  options: { isEmpty?: (data: unknown) => boolean } = {},
): AvailabilityView {
  if (slice.status === "idle" || slice.status === "loading") {
    return {
      kind: "loading",
      title: "Loading",
      body: "",
      retryable: false,
    };
  }
  if (slice.status === "error") {
    return {
      kind: "error",
      title: "Couldn't load this feed",
      body: slice.error ?? "Unknown error",
      retryable: true,
    };
  }
  // ready
  const empty = options.isEmpty
    ? options.isEmpty(slice.data)
    : slice.data == null;
  if (empty) {
    const copy = EMPTY_COPY[surface];
    return { kind: "empty", ...copy, retryable: false };
  }
  return { kind: "ok", title: "", body: "", retryable: false };
}

/**
 * Session 3 block 4: expose a single source of truth for "is this
 * running against the mock client or a real backend." Surfaces that
 * carry real-vs-mock implications (control plane, assist) render a
 * tiny "MOCK DATA" tag when this is true so demo viewers never
 * mistake seeded data for live production state.
 */
export function isRunningMock(): boolean {
  return SCOUT_CLIENT_MODE === "mock";
}
