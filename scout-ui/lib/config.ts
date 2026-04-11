/**
 * Scout frontend configuration.
 *
 * ALL runtime configuration lives here.
 * No other file should contain hardcoded UUIDs, URLs, or identity assumptions.
 *
 * Categories:
 * - Environment: API URL, dev mode flag
 * - Identity: current user (temporary until auth exists)
 * - Family: family tenant (temporary until multi-tenant sessions exist)
 * - Product: allowance baselines (temporary until stored per-member in backend)
 */

// ---- Environment ----

export const API_BASE_URL = "http://localhost:8000";

/**
 * Dev mode flag.
 * When true: DevTools panel is visible on Personal dashboard.
 * When false: DevTools panel is hidden.
 */
export const DEV_MODE = true;

// ---- Identity (temporary — replace with auth session) ----

/**
 * The current user. This is the ONLY place a user identity is assumed.
 * All frontend code references these values rather than scattering UUIDs.
 */
export const CURRENT_USER_ID = "b1000000-0000-4000-8000-000000000001";
export const CURRENT_USER_NAME = "Andrew";

// ---- Family tenant (temporary — replace with session-derived family) ----

export const FAMILY_ID = "a1b2c3d4-0000-4000-8000-000000000001";
