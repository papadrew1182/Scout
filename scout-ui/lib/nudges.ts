/**
 * Sprint 05 Phase 2 - nudges API helpers.
 * Plain fetch helpers to match the lib/ai-conversations.ts /
 * lib/ai-personality.ts pattern (no react-query).
 */

import { API_BASE_URL } from "./config";
import { get, put } from "./api";

export type NudgeStatus = "pending" | "delivered" | "suppressed";
export type NudgeSeverity = "low" | "normal" | "high";

export interface NudgeDispatchItem {
  id: string;
  trigger_kind: string;
  trigger_entity_kind: string;
  trigger_entity_id: string | null;
  occurrence_at_utc: string;
  occurrence_local_date: string;
  source_metadata: Record<string, unknown>;
  created_at: string;
}

export interface NudgeDispatch {
  id: string;
  family_member_id: string;
  status: NudgeStatus;
  severity: NudgeSeverity;
  suppressed_reason: string | null;
  deliver_after_utc: string;
  delivered_at_utc: string | null;
  delivered_channels: string[];
  source_count: number;
  body: string | null;
  items: NudgeDispatchItem[];
  created_at: string;
  updated_at: string;
}

export interface QuietHoursConfig {
  start_local_minute: number;
  end_local_minute: number;
  is_default: boolean;
}

export function listMyNudges(limit: number = 20): Promise<NudgeDispatch[]> {
  const params = new URLSearchParams();
  params.set("limit", String(limit));
  return get(`${API_BASE_URL}/api/nudges/me?${params.toString()}`);
}

export function getFamilyQuietHours(): Promise<QuietHoursConfig> {
  return get(`${API_BASE_URL}/api/admin/family-config/quiet-hours`);
}

export function putFamilyQuietHours(
  start_local_minute: number,
  end_local_minute: number,
): Promise<QuietHoursConfig> {
  return put(`${API_BASE_URL}/api/admin/family-config/quiet-hours`, {
    start_local_minute,
    end_local_minute,
  });
}
