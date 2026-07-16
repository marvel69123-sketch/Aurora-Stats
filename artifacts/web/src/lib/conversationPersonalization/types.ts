/**
 * Presentation-only preference types.
 * Never fed into engines / payloads / Decision Center.
 */

export type ConversationProfileId = "technical" | "casual";

export type EmojiLevel = "none" | "low" | "medium" | "high";
export type EnthusiasmLevel = "low" | "medium" | "high";
export type StructureLevel = "conversational" | "balanced" | "technical";
export type HeadersListsLevel = "few" | "normal" | "many";
export type DetailLevel = "short" | "normal" | "detailed";

export interface ConversationPreferences {
  profile: ConversationProfileId;
  emojis: EmojiLevel;
  enthusiasm: EnthusiasmLevel;
  structure: StructureLevel;
  headersLists: HeadersListsLevel;
  detail: DetailLevel;
}

/** Snapshot frozen onto a message at send-time (history must not reshape). */
export interface PresentationSnapshot {
  profile: ConversationProfileId;
  emojis: EmojiLevel;
  enthusiasm: EnthusiasmLevel;
  structure: StructureLevel;
  headersLists: HeadersListsLevel;
  detail: DetailLevel;
  capturedAt: number;
}

/** Future FollowUp hooks — prepare only; not wired to follow_up_engine. */
export interface FollowUpPresentationHints {
  profile: ConversationProfileId;
  emojis: EmojiLevel;
  enthusiasm: EnthusiasmLevel;
  structure: StructureLevel;
  headersLists: HeadersListsLevel;
  detail: DetailLevel;
}

export interface ConversationProfileMeta {
  id: ConversationProfileId;
  label: string;
  description: string;
}
