/**
 * Centralized "why is this slice not showing real data" helper.
 *
 * The Session 3 realClient throws a clearly-named "not yet implemented"
 * error for endpoints the backend hasn't shipped. Several surfaces need
 * to distinguish that case from a genuine fetch failure so we can show
 * an honest "not yet shipped" notice instead of a scary red error.
 *
 * Block 3 inlined this classification in two files with a hand-rolled
 * regex. Block 4 lifts it here so every surface uses the same rules.
 *
 * Inputs:
 *   - a slice's `{status, data, error}` triple (the shape `hooks` returns)
 *
 * Outputs:
 *   - `kind` — which narrative to render:
 *       "loading"     → slice is idle or loading (render skeleton)
 *       "ok"          → slice is ready and has data
 *       "empty"       → slice is ready but data is null/empty-ish
 *       "unavailable" → slice errored because the endpoint is not yet
 *                       implemented by the backend (expected in real mode)
 *       "error"       → slice errored for any other reason
 *   - `title`  / `body` — short, human-readable strings suitable for banners
 *   - `retryable` — whether a retry button makes sense (false for
 *                   "unavailable", true for "error")
 */

import { LoadStatus } from "../app/AppContext";
import { SCOUT_CLIENT_MODE } from "./client";

export type AvailabilityKind =
  | "loading"
  | "ok"
  | "empty"
  | "unavailable"
  | "error";

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
 * Known regex for the realClient's "not yet implemented" signal. The
 * realClient deliberately throws a stable string so classifiers can
 * detect it; see features/lib/realClient.ts.
 */
const NOT_IMPLEMENTED_RE = /not\s*(yet\s*)?implemented/i;

export function isUnavailableMessage(message: string | null | undefined): boolean {
  if (!message) return false;
  return NOT_IMPLEMENTED_RE.test(message);
}

/**
 * Friendly per-surface labels for the "endpoint not yet shipped" story.
 * Callers pass the surface key so the banner speaks the surface's
 * vocabulary (calendar exports vs control-plane summary vs generic).
 */
export type UnavailableSurfaceKey =
  | "calendar_exports"
  | "control_plane_summary"
  | "generic";

const UNAVAILABLE_COPY: Record<
  UnavailableSurfaceKey,
  { title: string; body: string }
> = {
  calendar_exports: {
    title: "Calendar export feed not yet shipped",
    body: "The /api/calendar/exports/upcoming endpoint hasn't shipped from Session 2 yet. Once it does, this surface lights up automatically.",
  },
  control_plane_summary: {
    title: "Summary feed not yet shipped",
    body: "/api/control-plane/summary is not yet implemented by the backend. Connector health below is still live.",
  },
  generic: {
    title: "Feed not yet shipped",
    body: "This endpoint hasn't shipped from Session 2 yet. The rest of the page stays live.",
  },
};

const EMPTY_COPY: Record<UnavailableSurfaceKey, { title: string; body: string }> = {
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
 * Classify a slice into one of the five states and return banner copy
 * suitable for the given surface.
 *
 * In mock mode the realClient is never invoked, so the "unavailable"
 * narrative shouldn't appear unless the mock client itself throws — in
 * that case we still defer to the shared copy to avoid surprising the
 * caller.
 */
export function classifySlice(
  slice: SliceShape,
  surface: UnavailableSurfaceKey = "generic",
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
    if (isUnavailableMessage(slice.error)) {
      const copy = UNAVAILABLE_COPY[surface];
      return { kind: "unavailable", ...copy, retryable: false };
    }
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
