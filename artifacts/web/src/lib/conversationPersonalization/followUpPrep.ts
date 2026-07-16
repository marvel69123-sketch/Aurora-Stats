import type {
  ConversationPreferences,
  FollowUpPresentationHints,
} from "./types";

/**
 * Prepare FollowUp presentation hints for a future sprint.
 * Does NOT call follow_up_engine / LLM conversation.
 */
export function getFollowUpPresentationHints(
  prefs: ConversationPreferences,
): FollowUpPresentationHints {
  return {
    profile: prefs.profile,
    emojis: prefs.emojis,
    enthusiasm: prefs.enthusiasm,
    structure: prefs.structure,
    headersLists: prefs.headersLists,
    detail: prefs.detail,
  };
}
