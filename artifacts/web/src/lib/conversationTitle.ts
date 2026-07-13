/**
 * Generate a short ChatGPT-style conversation title from the first user message.
 * Prefers match pairs ("A x B") when present.
 */
export function generateConversationTitle(raw: string): string {
  const text = raw.trim().replace(/\s+/g, " ");
  if (!text) return "Nova conversa";

  // Prefer "Team A x Team B" (with optional live/command noise)
  const match = text.match(
    /(?:analis[ae]r?\s+|analise\s+|como\s+est[aá]\s+(?:o\s+)?)?(.+?)\s+(?:x|vs|versus|contra)\s+(.+?)(?:\s+(?:ao\s+vivo|agora|live))?\s*$/i,
  );
  if (match) {
    const home = cleanTeam(match[1]);
    const away = cleanTeam(match[2]);
    if (home && away) {
      const live = /\b(ao\s+vivo|agora|live)\b/i.test(text) ? " ao vivo" : "";
      return truncate(`${titleCase(home)} x ${titleCase(away)}${live}`, 48);
    }
  }

  // Strip common command prefixes
  let cleaned = text
    .replace(
      /^(quero\s+(?:analisar|ver)|analis[ae]r?|analise|analisa|explique|explica|mostre|me\s+fale\s+sobre|o\s+que\s+voce\s+sabe\s+sobre)\s+/i,
      "",
    )
    .trim();

  if (!cleaned) cleaned = text;
  return truncate(titleCase(cleaned), 42);
}

function cleanTeam(s: string): string {
  return s
    .replace(/\b(ao\s+vivo|agora|live|analise|analisar)\b/gi, "")
    .replace(/[''`´’]/g, "'")
    .trim();
}

function titleCase(s: string): string {
  return s
    .split(" ")
    .filter(Boolean)
    .map((w) => {
      if (w.length <= 2 && w.toLowerCase() !== "pb") return w.toUpperCase();
      return w.charAt(0).toUpperCase() + w.slice(1).toLowerCase();
    })
    .join(" ");
}

function truncate(s: string, max: number): string {
  if (s.length <= max) return s;
  return s.slice(0, max - 1).trimEnd() + "…";
}

export type DateGroup = "pinned" | "today" | "yesterday" | "week" | "older";

export function conversationDateGroup(iso: string, pinned?: boolean): DateGroup {
  if (pinned) return "pinned";
  const d = new Date(iso);
  const now = new Date();
  const startToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startYesterday = new Date(startToday);
  startYesterday.setDate(startYesterday.getDate() - 1);
  const startWeek = new Date(startToday);
  startWeek.setDate(startWeek.getDate() - 7);

  if (d >= startToday) return "today";
  if (d >= startYesterday) return "yesterday";
  if (d >= startWeek) return "week";
  return "older";
}

export const DATE_GROUP_LABELS: Record<DateGroup, string> = {
  pinned: "Fixadas",
  today: "Hoje",
  yesterday: "Ontem",
  week: "7 dias anteriores",
  older: "Anteriores",
};
