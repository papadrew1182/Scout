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

export const API_BASE_URL: string = envApiUrl || "http://localhost:8000";

export const DEV_MODE = !envApiUrl;
