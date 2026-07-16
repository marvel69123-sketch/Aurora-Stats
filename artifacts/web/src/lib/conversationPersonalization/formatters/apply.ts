import { formatCasual } from "./casual";
import { formatTechnical } from "./technical";
import type { ConversationPreferences } from "../types";

export type PresentationFormatter = (
  text: string,
  prefs: ConversationPreferences,
) => string;

/**
 * Apply presentation formatter with mandatory Technical fallback.
 *
 * Engines → payload neutro → Formatter → UI
 * Personalization NEVER alters intelligence — only display text.
 *
 * Foundation note: not wired into AuroraResponse while
 * `conversationPersonalizationEnabled === false`.
 */
export function applyPresentation(
  text: string,
  prefs: ConversationPreferences,
): string {
  const input = text ?? "";
  try {
    if (prefs.profile === "casual") {
      const out = formatCasual(input, prefs);
      if (typeof out !== "string") return formatTechnical(input, prefs);
      return out;
    }
    return formatTechnical(input, prefs);
  } catch {
    // Usuário nunca deve perceber falha → Aurora Técnica
    return formatTechnical(input, prefs);
  }
}
