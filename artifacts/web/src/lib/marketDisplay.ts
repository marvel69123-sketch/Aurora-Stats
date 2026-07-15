/**
 * Aurora v3.4.1 — display-only PT helpers.
 * Does NOT change Decision Center / market engines / MatchHeader.
 *
 * Future architecture (not implemented):
 * MarketFocusKind → cards | btts | handicap | dnb | momentum | possession | corners
 */
export type MarketFocusKind =
  | "corners"
  | "goals"
  | "btts"
  | "handicap"
  | "dnb"
  | "winner"
  | "other";

export const MARKET_FOCUS_ARCH: Record<MarketFocusKind, string> = {
  corners: "escanteios",
  goals: "gols",
  btts: "ambos marcam",
  handicap: "handicap",
  dnb: "empate anula",
  winner: "resultado",
  other: "outros",
};

const MARKET_PT: Array<[RegExp, string]> = [
  [/^over\s*9\.5\s*corners$/i, "Mais de 9.5 escanteios"],
  [/^over\s*8\.5\s*corners$/i, "Mais de 8.5 escanteios"],
  [/^over\s*10\.5\s*corners$/i, "Mais de 10.5 escanteios"],
  [/^under\s*8\.5\s*corners$/i, "Menos de 8.5 escanteios"],
  [/^over\s*2\.5\s*goals$/i, "Mais de 2.5 gols"],
  [/^under\s*2\.5\s*goals$/i, "Menos de 2.5 gols"],
  [/^over\s*1\.5\s*goals$/i, "Mais de 1.5 gols"],
  [/^under\s*1\.5\s*goals$/i, "Menos de 1.5 gols"],
  [/^over\s*3\.5\s*goals$/i, "Mais de 3.5 gols"],
  [/^btts\s*yes$/i, "Ambos marcam — Sim"],
  [/^btts\s*no$/i, "Ambos marcam — Não"],
  [/^home\s*win$/i, "Vitória do mandante"],
  [/^away\s*win$/i, "Vitória do visitante"],
  [/^draw$/i, "Empate"],
  [/^draw\s*no\s*bet\s*home$/i, "Empate anula — mandante"],
  [/^draw\s*no\s*bet\s*away$/i, "Empate anula — visitante"],
  [/\basian\s*handicap\b/i, "Handicap asiático"],
  [/\bover\s*(\d+(?:\.\d+)?)\s*corners\b/i, "Mais de $1 escanteios"],
  [/\bunder\s*(\d+(?:\.\d+)?)\s*corners\b/i, "Menos de $1 escanteios"],
  [/\bover\s*(\d+(?:\.\d+)?)\s*goals\b/i, "Mais de $1 gols"],
  [/\bunder\s*(\d+(?:\.\d+)?)\s*goals\b/i, "Menos de $1 gols"],
];

/** Phrase-level EN→PT for factors / summaries shown in the main UI. */
const PROSE_PT: Array<[RegExp, string]> = [
  [/\bhigh[- ]?risk\b/gi, "risco elevado"],
  [/\bhigh risk\b/gi, "risco elevado"],
  [/\blow[- ]?risk\b/gi, "risco baixo"],
  [/\bmedium[- ]?risk\b/gi, "risco médio"],
  [/\bhistorical\b/gi, "histórico"],
  [/\bperformance\b/gi, "desempenho"],
  [/\bhome advantage\b/gi, "vantagem de mando"],
  [/\baway (form|performance)\b/gi, "desempenho como visitante"],
  [/\bstrong momentum\b/gi, "bom ritmo"],
  [/\bmomentum\b/gi, "ritmo"],
  [/\bmarket confidence\b/gi, "confiança do mercado"],
  [/\bportfolio exposure\b/gi, "exposição da banca"],
  [/\bcategory pulling (the )?score down\b/gi, "categoria puxando a nota para baixo"],
  [/\bpulling the (overall )?score down\b/gi, "puxando a nota para baixo"],
  [/\bbest[- ]?market\b/gi, "melhor mercado"],
  [/\bexpected value\b/gi, "valor esperado"],
  [/\bconfidence\b/gi, "confiança"],
  [/\binsufficient\b/gi, "insuficiente"],
  [/\bmoderate\b/gi, "moderada"],
  [/\badequate\b/gi, "adequada"],
  [/\bstrong\b/gi, "forte"],
  [/\bweak\b/gi, "fraca"],
  [/\bunknown\b/gi, "indefinido"],
  [/\bnot started\b/gi, "não iniciada"],
  [/\bfixture\b/gi, "partida"],
  [/\blineups?\b/gi, "escalações"],
  [/\bxG\b/g, "xG"],
];

export function classifyMarketFocus(market: string): MarketFocusKind {
  const m = market.toLowerCase();
  if (/corner|escanteio|canto/.test(m)) return "corners";
  if (/btts|ambos/.test(m)) return "btts";
  if (/dnb|draw\s*no\s*bet|empate anula/.test(m)) return "dnb";
  if (/handicap|ah\b/.test(m)) return "handicap";
  if (/over|under|gol|goal/.test(m)) return "goals";
  if (/win|vit[oó]r|empate|draw|1x2|vencedor/.test(m)) return "winner";
  return "other";
}

export function marketLabelPt(market: string): string {
  const raw = (market || "").trim();
  if (!raw) return raw;
  for (const [re, out] of MARKET_PT) {
    if (re.test(raw)) return raw.replace(re, out);
  }
  return scrubProsePt(raw)
    .replace(/\bcorners\b/gi, "escanteios")
    .replace(/\bgoals\b/gi, "gols")
    .replace(/\bover\b/gi, "Mais de")
    .replace(/\bunder\b/gi, "Menos de")
    .replace(/\bhome\b/gi, "mandante")
    .replace(/\baway\b/gi, "visitante")
    .replace(/\bdraw\b/gi, "empate")
    .replace(/\bwin\b/gi, "vitória");
}

/** Scrub residual English in user-facing prose (not #debug). */
export function scrubProsePt(text: string): string {
  let t = (text || "").trim();
  if (!t) return t;
  for (const [re, out] of PROSE_PT) {
    t = t.replace(re, out);
  }
  return t.replace(/\s+/g, " ").trim();
}

/** One visual line for bullets (~mobile-safe). */
export function oneLinePt(text: string, max = 72): string {
  let t = scrubProsePt(text).replace(/^•\s*/, "");
  t = (t.split(/(?<=[.!?])\s+/)[0] || t).trim();
  if (t.length > max) return `${t.slice(0, max - 1)}…`;
  return t;
}
