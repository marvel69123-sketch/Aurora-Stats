import type { ConversationPreferences } from "./types";

/** Default = Aurora Técnica (current product behavior). */
export const DEFAULT_CONVERSATION_PREFERENCES: ConversationPreferences = {
  profile: "technical",
  emojis: "none",
  enthusiasm: "low",
  structure: "technical",
  headersLists: "normal",
  detail: "normal",
};
