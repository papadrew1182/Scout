/**
 * Active Session 3 ScoutClient.
 *
 * Mode is selected at build time via `EXPO_PUBLIC_SCOUT_API_MODE`:
 *   - "mock" (default) — fully in-memory, no network, no backend dep.
 *   - "real"           — talks to the published contracts at API_BASE_URL.
 *
 * The Session 3 lane defaults to mock until Session 2 lands all 9
 * endpoints. Swapping is a single env change; no UI code needs to move.
 */

import { ScoutClient } from "./contracts";
import { mockClient } from "./mockClient";
import { realClient } from "./realClient";

// @ts-ignore — Expo inlines process.env at build time.
const mode: string = process.env.EXPO_PUBLIC_SCOUT_API_MODE ?? "mock";

export const scoutClient: ScoutClient = mode === "real" ? realClient : mockClient;

export const SCOUT_CLIENT_MODE: "mock" | "real" = mode === "real" ? "real" : "mock";
