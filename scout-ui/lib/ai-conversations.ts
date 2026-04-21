/**
 * Sprint 04 Phase 1 — AI conversation list + resume API helpers.
 *
 * Plain fetch helpers (no react-query; the repo uses useState/useEffect
 * patterns elsewhere). Consumed by ScoutSheet, ScoutSidebar, and the new
 * /settings/ai page.
 *
 * Auto-resume of the most recent in-flight thread continues to use the
 * existing `fetchResumableConversation` helper in `lib/api.ts` — that
 * endpoint has 30-min freshness + pending-confirmation / moderation
 * safety gates that this drawer-level API intentionally does not
 * duplicate.
 */

import { API_BASE_URL } from "./config";
import { get, post, patch } from "./api";

export interface Conversation {
  id: string;
  family_id: string;
  family_member_id: string;
  surface: string;
  status: "active" | "archived" | "ended";
  conversation_kind: string;
  title: string | null;
  last_active_at: string | null;
  is_pinned: boolean;
  created_at: string;
  updated_at: string;
}

export interface ConversationStats {
  total_count: number;
  active_count: number;
  archived_count: number;
}

export interface ConversationMessage {
  id: string;
  conversation_id: string;
  role: string;
  content: string | null;
  tool_calls: unknown;
  tool_results: unknown;
  model: string | null;
  token_usage: unknown;
  attachment_meta: { attachment_path?: string; attachment_url?: string } | null;
  created_at: string;
}

export interface MessagePage {
  messages: ConversationMessage[];
  has_more: boolean;
}

export interface ListOptions {
  includeArchived?: boolean;
  pinnedFirst?: boolean;
  limit?: number;
  offset?: number;
}

export function listMyConversations(
  opts: ListOptions = {},
): Promise<Conversation[]> {
  const params = new URLSearchParams();
  params.set("include_archived", String(opts.includeArchived ?? false));
  params.set("pinned_first", String(opts.pinnedFirst ?? true));
  params.set("limit", String(opts.limit ?? 20));
  params.set("offset", String(opts.offset ?? 0));
  return get(`${API_BASE_URL}/api/ai/conversations?${params.toString()}`);
}

export function getConversationStats(): Promise<ConversationStats> {
  return get(`${API_BASE_URL}/api/ai/conversations/stats`);
}

export interface MessagePageOptions {
  limit?: number;
  beforeMessageId?: string;
}

export function fetchConversationMessagesPaginated(
  conversationId: string,
  opts: MessagePageOptions = {},
): Promise<MessagePage> {
  const params = new URLSearchParams();
  params.set("limit", String(opts.limit ?? 50));
  if (opts.beforeMessageId) {
    params.set("before_message_id", opts.beforeMessageId);
  }
  return get(
    `${API_BASE_URL}/api/ai/conversations/${conversationId}/messages?${params.toString()}`,
  );
}

export function createConversation(
  firstMessage?: string,
): Promise<Conversation> {
  return post(`${API_BASE_URL}/api/ai/conversations`, {
    first_message: firstMessage ?? null,
  });
}

export interface PatchConversationBody {
  title?: string | null;
  status?: "active" | "archived";
  is_pinned?: boolean;
}

export function patchConversation(
  conversationId: string,
  body: PatchConversationBody,
): Promise<Conversation> {
  return patch(
    `${API_BASE_URL}/api/ai/conversations/${conversationId}`,
    body,
  );
}

export function archiveOlderConversations(
  days: number,
): Promise<{ archived_count: number }> {
  return post(`${API_BASE_URL}/api/ai/conversations/archive-older-than`, {
    days,
  });
}
