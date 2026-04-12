/**
 * Scout frontend configuration.
 *
 * Identity and family are derived from the auth session (see lib/auth.tsx).
 * API_BASE_URL is set via EXPO_PUBLIC_API_URL env var at build time,
 * falling back to localhost for local dev.
 */

// @ts-ignore - Expo injects process.env at build time
const envApiUrl = typeof process !== "undefined" && process.env?.EXPO_PUBLIC_API_URL;

export const API_BASE_URL: string = envApiUrl || "http://localhost:8000";

export const DEV_MODE = !envApiUrl;
