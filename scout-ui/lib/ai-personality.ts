/**
 * Sprint 04 Phase 2 - per-member AI personality API helpers.
 *
 * Plain fetch helpers mirroring the lib/ai-conversations.ts pattern.
 * The preamble preview shown in the UI always comes from the backend's
 * `preamble` field — do NOT compose it in the frontend. That guarantees
 * "what you see is what the chat turn actually gets."
 */

import { API_BASE_URL } from "./config";
import { get, patch } from "./api";

export type Tone = "warm" | "direct" | "playful" | "professional";
export type VocabularyLevel = "simple" | "standard" | "advanced";
export type Formality = "casual" | "neutral" | "formal";
export type Humor = "none" | "light" | "dry";
export type Proactivity = "quiet" | "balanced" | "forthcoming";
export type Verbosity = "short" | "standard" | "detailed";

export interface PersonalityConfig {
  tone: Tone;
  vocabulary_level: VocabularyLevel;
  formality: Formality;
  humor: Humor;
  proactivity: Proactivity;
  verbosity: Verbosity;
  notes_to_self: string;
  role_hints: string;
}

export interface PersonalityResponse {
  stored: Partial<PersonalityConfig> | null;
  resolved: PersonalityConfig;
  preamble: string;
}

export type PersonalityPatch = Partial<PersonalityConfig>;

export function getMyPersonality(): Promise<PersonalityResponse> {
  return get(`${API_BASE_URL}/api/ai/personality/me`);
}

export function patchMyPersonality(
  body: PersonalityPatch,
): Promise<PersonalityResponse> {
  return patch(`${API_BASE_URL}/api/ai/personality/me`, body);
}

export function getMemberPersonality(
  memberId: string,
): Promise<PersonalityResponse> {
  return get(`${API_BASE_URL}/api/ai/personality/members/${memberId}`);
}

export function patchMemberPersonality(
  memberId: string,
  body: PersonalityPatch,
): Promise<PersonalityResponse> {
  return patch(`${API_BASE_URL}/api/ai/personality/members/${memberId}`, body);
}
