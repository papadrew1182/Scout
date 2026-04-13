/**
 * Scout frontend configuration.
 *
 * Identity and family are derived from the auth session (see lib/auth.tsx).
 * API_BASE_URL is set via EXPO_PUBLIC_API_URL env var at build time,
 * falling back to localhost for local dev.
 *
 * Note: `process.env.EXPO_PUBLIC_API_URL` must be accessed as a literal
 * member expression so Metro can inline it at build time. Avoid optional
 * chaining or destructuring here.
 */

// @ts-ignore - Expo injects process.env at build time
const envApiUrl: string | undefined = process.env.EXPO_PUBLIC_API_URL;
// @ts-ignore - Expo injects process.env at build time
const envE2E: string | undefined = process.env.EXPO_PUBLIC_SCOUT_E2E;

export const API_BASE_URL: string = envApiUrl || "http://localhost:8000";

export const DEV_MODE = !envApiUrl;

/**
 * E2E-only test hooks gate. Enables routes like `/__boom` that force a
 * render crash so the global ErrorBoundary can be verified. Set
 * `EXPO_PUBLIC_SCOUT_E2E=true` in the expo export env for smoke runs.
 * Never set in production builds — the route is a no-op otherwise.
 */
export const E2E_TEST_HOOKS = envE2E === "true";
