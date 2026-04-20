/**
 * Active Session 3 ScoutClient.
 *
 * Mode is selected at build time via `EXPO_PUBLIC_SCOUT_API_MODE`:
 *   - "real" (default) — talks to the published contracts at API_BASE_URL.
 *   - "mock"           — fully in-memory, no network, no backend dep.
 *
 * Session 2 has landed all 9 canonical endpoints, so real mode is now
 * the default. Keep "mock" available for offline/design work.
 */

import { ScoutClient } from "./contracts";
import { mockClient } from "./mockClient";
import { realClient } from "./realClient";

// @ts-ignore — Expo inlines process.env at build time.
const mode: string = process.env.EXPO_PUBLIC_SCOUT_API_MODE ?? "real";

export const scoutClient: ScoutClient = mode === "mock" ? mockClient : realClient;

export const SCOUT_CLIENT_MODE: "mock" | "real" = mode === "mock" ? "mock" : "real";
