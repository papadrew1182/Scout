/**
 * Scout frontend configuration.
 *
 * ALL runtime configuration lives here.
 * No other file should contain hardcoded UUIDs, URLs, or identity assumptions.
 *
 * Identity is derived from the auth session (see lib/auth.tsx).
 */

// ---- Environment ----

export const API_BASE_URL = "http://localhost:8000";

/**
 * Dev mode flag.
 * When true: DevTools panel is visible on Personal dashboard.
 * When false: DevTools panel is hidden.
 */
export const DEV_MODE = true;

// ---- Family tenant (temporary — replace with session-derived family) ----

export const FAMILY_ID = "a1b2c3d4-0000-4000-8000-000000000001";
