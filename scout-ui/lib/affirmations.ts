import { API_BASE_URL } from "./config";
import { authHeaders } from "./api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface AffirmationData {
  id: string;
  text: string;
  category: string | null;
  tone: string | null;
}

export interface AffirmationDelivery {
  affirmation: AffirmationData | null;
  delivered_at: string | null;
  delivery_id: string | null;
}

export interface AffirmationPreferences {
  enabled: boolean;
  preferred_tones: string[];
  preferred_philosophies: string[];
  excluded_themes: string[];
  preferred_length: string;
}

export interface AffirmationItem {
  id: string;
  text: string;
  category: string | null;
  tags: string[];
  tone: string | null;
  philosophy: string | null;
  audience_type: string;
  length_class: string;
  active: boolean;
  source_type: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface AffirmationAnalytics {
  total_affirmations: number;
  active_count: number;
  total_deliveries: number;
  reactions: { heart: number; thumbs_down: number; skip: number; reshow: number };
  most_liked: { id: string; text: string; hearts: number }[];
  most_rejected: { id: string; text: string; thumbs_down: number }[];
  stale: { id: string; text: string; last_delivered: string | null }[];
  per_audience: Record<string, number>;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function _get<T>(url: string): Promise<T> {
  const res = await fetch(url, { headers: authHeaders() });
  if (res.status === 401) throw new Error("Session expired");
  if (!res.ok) throw new Error(`GET ${url} failed (${res.status})`);
  return res.json();
}

async function _post<T>(url: string, body?: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: { ...authHeaders(), ...(body ? { "Content-Type": "application/json" } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401) throw new Error("Session expired");
  if (!res.ok) throw new Error(`POST ${url} failed (${res.status})`);
  return res.json();
}

async function _put<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "PUT",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (res.status === 401) throw new Error("Session expired");
  if (!res.ok) throw new Error(`PUT ${url} failed (${res.status})`);
  return res.json();
}

async function _patch<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "PATCH",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (res.status === 401) throw new Error("Session expired");
  if (!res.ok) throw new Error(`PATCH ${url} failed (${res.status})`);
  return res.json();
}

// ---------------------------------------------------------------------------
// User-facing API
// ---------------------------------------------------------------------------

export function getCurrentAffirmation(): Promise<AffirmationDelivery> {
  return _get(`${API_BASE_URL}/affirmations/current`);
}

export function submitReaction(
  affirmationId: string,
  reactionType: "heart" | "thumbs_down" | "skip" | "reshow",
  context?: string,
): Promise<{ status: string }> {
  return _post(`${API_BASE_URL}/affirmations/${affirmationId}/feedback`, {
    reaction_type: reactionType,
    context,
  });
}

export function getAffirmationPreferences(): Promise<AffirmationPreferences> {
  return _get(`${API_BASE_URL}/affirmations/preferences`);
}

export function updateAffirmationPreferences(
  prefs: Omit<AffirmationPreferences, "enabled">,
): Promise<AffirmationPreferences> {
  return _put(`${API_BASE_URL}/affirmations/preferences`, prefs);
}

// ---------------------------------------------------------------------------
// Admin API
// ---------------------------------------------------------------------------

export function fetchAffirmationLibrary(params?: {
  category?: string;
  tone?: string;
  audience_type?: string;
  active?: boolean;
  q?: string;
}): Promise<AffirmationItem[]> {
  const sp = new URLSearchParams();
  if (params?.category) sp.set("category", params.category);
  if (params?.tone) sp.set("tone", params.tone);
  if (params?.audience_type) sp.set("audience_type", params.audience_type);
  if (params?.active !== undefined) sp.set("active", String(params.active));
  if (params?.q) sp.set("q", params.q);
  const qs = sp.toString();
  return _get(`${API_BASE_URL}/admin/affirmations${qs ? `?${qs}` : ""}`);
}

export function createAffirmation(data: {
  text: string;
  category?: string;
  tags?: string[];
  tone?: string;
  philosophy?: string;
  audience_type?: string;
  length_class?: string;
}): Promise<AffirmationItem> {
  return _post(`${API_BASE_URL}/admin/affirmations`, data);
}

export function updateAffirmation(
  id: string,
  data: Partial<Pick<AffirmationItem, "text" | "category" | "tags" | "tone" | "philosophy" | "audience_type" | "length_class">>,
): Promise<AffirmationItem> {
  return _put(`${API_BASE_URL}/admin/affirmations/${id}`, data);
}

export function toggleAffirmationActive(id: string, active: boolean): Promise<AffirmationItem> {
  return _patch(`${API_BASE_URL}/admin/affirmations/${id}/active`, { active });
}

export function fetchAffirmationAnalytics(): Promise<AffirmationAnalytics> {
  return _get(`${API_BASE_URL}/admin/affirmations/analytics`);
}

export function fetchAffirmationConfig(): Promise<{ key: string; value: Record<string, unknown> }> {
  return _get(`${API_BASE_URL}/admin/affirmations/config`);
}

export function updateAffirmationConfig(value: Record<string, unknown>): Promise<{ key: string; value: Record<string, unknown> }> {
  return _put(`${API_BASE_URL}/admin/affirmations/config`, { value });
}
