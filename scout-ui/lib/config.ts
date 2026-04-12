/**
 * Scout frontend configuration.
 *
 * ALL runtime configuration lives here.
 * Identity and family are derived from the auth session (see lib/auth.tsx).
 */

// ---- Environment ----

export const API_BASE_URL = "http://localhost:8000";

/**
 * Dev mode flag.
 * When true: DevTools panel is visible on Personal dashboard.
 * When false: DevTools panel is hidden.
 */
export const DEV_MODE = true;
