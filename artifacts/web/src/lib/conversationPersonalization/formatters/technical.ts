import type { ConversationPreferences } from "../types";

/**
 * Technical formatter = identity (current Aurora presentation).
 * Never mutates payload / engines — presentation text in, same text out.
 */
export function formatTechnical(
  text: string,
  _prefs?: ConversationPreferences,
): string {
  return text ?? "";
}
