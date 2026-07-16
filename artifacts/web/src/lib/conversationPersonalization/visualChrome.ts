import type {
  ConversationPreferences,
  EmojiLevel,
  EnthusiasmLevel,
  HeadersListsLevel,
} from "./types";
import { DEFAULT_CONVERSATION_PREFERENCES } from "./defaults";

/**
 * v3.6.4 — Chrome-only visual prefs (emojis / enthusiasm / headers).
 *
 * NEVER mutates payloads, markets, MatchHeader, Premium Live, or reply body text.
 * Profile Casual is NOT implemented here — only technical report layout uses profile.
 */

export type ChromeKind =
  | "alert"
  | "urgency"
  | "favor"
  | "attention"
  | "details"
  | "resumo"
  | "featured"
  | "markets_label"
  | "history_label"
  | "notes_label"
  | "empty_greeting";

/** Approx. emoji density targets: none 0%, low 15%, medium 45%, high 80%. */
function emojiRoll(level: EmojiLevel, weight: number): boolean {
  // weight 0..1 — higher weight = more likely to show at a given level
  if (level === "none") return false;
  if (level === "low") return weight >= 0.85; // ~10–20% of chrome slots
  if (level === "medium") return weight >= 0.5; // ~40–50%
  return weight >= 0.15; // high ~70–90%
}

const EMOJI_BY_KIND: Record<ChromeKind, { emoji: string; weight: number }> = {
  alert: { emoji: "⚠️", weight: 0.9 },
  urgency: { emoji: "🚨", weight: 0.95 },
  favor: { emoji: "✅", weight: 0.55 },
  attention: { emoji: "⚠️", weight: 0.85 },
  details: { emoji: "📋", weight: 0.4 },
  resumo: { emoji: "📝", weight: 0.45 },
  featured: { emoji: "💡", weight: 0.7 },
  markets_label: { emoji: "📊", weight: 0.5 },
  history_label: { emoji: "📚", weight: 0.35 },
  notes_label: { emoji: "📎", weight: 0.3 },
  empty_greeting: { emoji: "✨", weight: 0.6 },
};

function baseTitle(kind: ChromeKind, enthusiasm: EnthusiasmLevel): string {
  switch (kind) {
    case "alert":
      if (enthusiasm === "high") return "Atenção — olho nisso";
      if (enthusiasm === "medium") return "Atenção";
      return "Atenção";
    case "urgency":
      if (enthusiasm === "high") return "Evento crítico agora";
      if (enthusiasm === "medium") return "Evento importante";
      return "Evento importante";
    case "favor":
      if (enthusiasm === "high") return "A favor — bons sinais";
      if (enthusiasm === "medium") return "A favor";
      return "A favor";
    case "attention":
      if (enthusiasm === "high") return "Atenção — cuidado";
      if (enthusiasm === "medium") return "Atenção";
      return "Atenção";
    case "details":
      return "Ver análise completa";
    case "resumo":
      if (enthusiasm === "high") return "Resumo rápido";
      return "Resumo";
    case "featured":
      if (enthusiasm === "high") return "Mercado em destaque";
      if (enthusiasm === "medium") return "Mercado em destaque";
      return "Mercado em destaque";
    case "markets_label":
      return "Mercados";
    case "history_label":
      return "Histórico";
    case "notes_label":
      return "Notas";
    case "empty_greeting":
      if (enthusiasm === "high")
        return "Bora nas análises de hoje — estou pronto.";
      if (enthusiasm === "medium")
        return "Pronto para as análises de hoje?";
      return "Como posso ajudar nas análises de hoje?";
    default:
      return "";
  }
}

/** Extra trailing flair for high enthusiasm (chrome only). */
function enthusiasmFlair(
  kind: ChromeKind,
  enthusiasm: EnthusiasmLevel,
  emojis: EmojiLevel,
): string {
  if (enthusiasm !== "high") return "";
  if (emojis === "none") return "";
  if (kind === "favor" && emojiRoll(emojis, 0.2)) return " 🔥";
  if (kind === "featured" && emojiRoll(emojis, 0.25)) return " ⚡";
  if (kind === "empty_greeting" && emojiRoll(emojis, 0.2)) return " ⚽";
  return "";
}

/** Tailwind classes for title energy (enthusiasm). */
export function chromeTitleClass(
  prefs: ConversationPreferences | null | undefined,
): string {
  const e = prefs?.enthusiasm ?? DEFAULT_CONVERSATION_PREFERENCES.enthusiasm;
  if (e === "high") {
    return "font-semibold tracking-[0.06em] text-[11px]";
  }
  if (e === "medium") {
    return "font-semibold tracking-[0.08em] text-[10px]";
  }
  return "font-medium tracking-[0.1em] text-[10px] opacity-90";
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
    // Minimal labels — keep decision-critical only
    return (
      kind === "alert" ||
      kind === "urgency" ||
      kind === "featured" ||
      kind === "details"
    );
  }

  // normal: hide optional report subdivision labels
  return (
    kind !== "resumo" &&
    kind !== "markets_label" &&
    kind !== "history_label" &&
    kind !== "notes_label"
  );
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
  const slot = EMOJI_BY_KIND[kind];
  const withEmoji =
    slot.emoji && emojiRoll(p.emojis, slot.weight)
      ? `${slot.emoji} ${title}`
      : title;
  return `${withEmoji}${enthusiasmFlair(kind, p.enthusiasm, p.emojis)}`.trim();
}

/** Inline marker emojis (📌/🎯) — density by emoji pref; never changes copy body. */
export function chromeInlineMarker(
  marker: "context" | "opportunity" | "bullet",
  prefs: ConversationPreferences | null | undefined,
): string {
  const level = prefs?.emojis ?? DEFAULT_CONVERSATION_PREFERENCES.emojis;
  if (marker === "context") {
    return emojiRoll(level, 0.55) ? "📌 " : "";
  }
  if (marker === "opportunity") {
    return emojiRoll(level, 0.5) ? "🎯 " : "";
  }
  // bullet leading mark — only at high
  return emojiRoll(level, 0.2) ? "• " : "• ";
}

export function isTechnicalReportLayout(
  prefs: ConversationPreferences | null | undefined,
): boolean {
  return (prefs?.profile ?? "technical") === "technical";
}
