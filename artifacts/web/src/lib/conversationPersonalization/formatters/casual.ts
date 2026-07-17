import type { ConversationPreferences } from "../types";

/**
 * Casual formatter stub (presentation-only).
 *
 * Prepared for future activation. Does NOT touch engines/payloads.
 * Light prose softening only — never invents markets, odds, or live stats.
 *
 * If this throws or returns invalid output, applyPresentation falls back
 * to Technical automatically.
 */
export function formatCasual(
  text: string,
  prefs?: ConversationPreferences,
): string {
  const raw = (text ?? "").trim();
  if (!raw) return raw;

  // Soften a few report-like openers without changing factual content.
  let out = raw
    .replace(/^Análise baseada nos dados disponíveis no momento\./i, (m) =>
      prefs?.enthusiasm === "high"
        ? "Olha, com o que temos agora, dá para montar um bom cenário."
        : "Com os dados de agora, dá para ler o cenário assim.",
    )
    .replace(/^Pelo que vejo agora, ainda falta contexto para cravar\./i, (m) =>
      prefs?.enthusiasm === "high"
        ? "Olha, ainda falta um pouco de contexto pra cravar."
        : m,
    )
    .replace(/^Leitura com base /i, "Pelo que dá para ver, ")
    .replace(/\bCenário de baixa confiança\./gi, "Ainda está meio incerto.")
    .replace(/\bConfiança baixa neste momento\./gi, "Confiança ainda baixa por aqui.")
    .replace(/\bConfiança moderada\b/gi, "Leitura cautelosa");

  if (prefs?.emojis === "none" || !prefs) {
    return out;
  }

  // Emoji injection is intentionally minimal in the stub — visual prefs
  // are stored now; richer casual prose comes in a later sprint.
  if (prefs.emojis === "high" && !/[⚽🔥✨]/u.test(out)) {
    out = `${out} ⚽`;
  }

  return out;
}
