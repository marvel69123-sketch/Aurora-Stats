import type {
  ConversationPreferences,
  EmojiLevel,
  EnthusiasmLevel,
  HeadersListsLevel,
} from "./types";
import { DEFAULT_CONVERSATION_PREFERENCES } from "./defaults";

/**
 * v3.6.2 — Chrome-only visual prefs (emojis / enthusiasm / headers).
 *
 * NEVER mutates payloads, markets, MatchHeader, Premium Live, or reply body text.
 * Profile / structure / detail are ignored here on purpose.
 */

export type ChromeKind =
  | "alert"
  | "urgency"
  | "favor"
  | "attention"
  | "details"
  | "resumo"
  | "empty_greeting";

const EMOJI_BY_KIND: Record<ChromeKind, string> = {
  alert: "⚠️",
  urgency: "🚨",
  favor: "✓",
  attention: "⚠️",
  details: "",
  resumo: "",
  empty_greeting: "✨",
};

function allowEmoji(level: EmojiLevel, kind: ChromeKind): boolean {
  if (level === "none") return false;
  if (level === "low") {
    // Only critical attention markers
    return kind === "alert" || kind === "urgency" || kind === "attention";
  }
  if (level === "medium") {
    return kind !== "favor" && kind !== "details" && kind !== "resumo";
  }
  // high
  return true;
}

function baseTitle(
  kind: ChromeKind,
  enthusiasm: EnthusiasmLevel,
): string {
  switch (kind) {
    case "alert":
      return enthusiasm === "high" ? "Atenção agora" : "Atenção";
    case "urgency":
      return enthusiasm === "high" ? "Evento importante" : "Evento importante";
    case "favor":
      return enthusiasm === "high" ? "Pontos a favor" : "A favor";
    case "attention":
      return enthusiasm === "high" ? "Fique de olho" : "Atenção";
    case "details":
      return "Ver análise completa";
    case "resumo":
      return "Resumo";
    case "empty_greeting":
      if (enthusiasm === "high") return "Pronto para as análises de hoje?";
      if (enthusiasm === "low") return "Como posso ajudar nas análises de hoje?";
      return "Como posso ajudar nas análises de hoje?";
    default:
      return "";
  }
}

/** Whether a chrome section title should be visible (headersLists). */
export function showChromeHeader(
  prefs: ConversationPreferences | null | undefined,
  kind: ChromeKind,
): boolean {
  const level: HeadersListsLevel =
    prefs?.headersLists ?? DEFAULT_CONVERSATION_PREFERENCES.headersLists;
  if (level === "many") return true;
  if (level === "few") {
    // Keep essential attention markers; hide secondary labels
    return kind === "alert" || kind === "urgency" || kind === "details";
  }
  // normal: hide optional resumo eyebrow
  return kind !== "resumo";
}

/**
 * Build a chrome label. Never use for market names, summaries, or live stats.
 */
export function chromeHeading(
  kind: ChromeKind,
  prefs: ConversationPreferences | null | undefined,
): string {
  const p = prefs ?? DEFAULT_CONVERSATION_PREFERENCES;
  const title = baseTitle(kind, p.enthusiasm);
  const emoji = EMOJI_BY_KIND[kind];
  if (emoji && allowEmoji(p.emojis, kind)) {
    return `${emoji} ${title}`.trim();
  }
  return title;
}
