/**
 * Aurora v3.5 — FE-only live refresh helpers.
 * Consumes existing GET /aurora/live. Does not alter engines, FollowUp, or payloads.
 */

import type { MatchCard } from "@/types/chat";

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

/** Common national-team name bridges (display matching only). */
const ALIAS_GROUPS: string[][] = [
  ["england", "inglaterra"],
  ["argentina", "argentina"],
  ["brazil", "brasil"],
  ["spain", "espanha"],
  ["germany", "alemanha"],
  ["france", "franca", "france"],
  ["italy", "italia"],
  ["portugal", "portugal"],
  ["netherlands", "holanda", "paises baixos"],
  ["usa", "estados unidos", "united states"],
  ["mexico", "mexico"],
  ["uruguay", "uruguai"],
  ["colombia", "colombia"],
  ["chile", "chile"],
  ["peru", "peru"],
  ["ecuador", "equador"],
  ["paraguay", "paraguai"],
  ["japan", "japao"],
  ["south korea", "corea do sul", "korea"],
  ["manchester city", "man city", "manchester city fc"],
  ["manchester united", "man united", "man utd"],
  ["tottenham", "tottenham hotspur", "spurs"],
  ["psg", "paris saint germain", "paris sg"],
  ["inter", "inter milan", "internazionale"],
  ["atletico madrid", "atletico de madrid", "atlético madrid"],
];

export interface LiveTeamSide {
  id?: number;
  name: string;
  logo?: string | null;
  score?: number | null;
  yellow_cards?: number | null;
  red_cards?: number | null;
  statistics?: {
    possession?: string | number | null;
    shots_on_target?: string | number | null;
    shots_total?: string | number | null;
    corners?: string | number | null;
    fouls?: string | number | null;
    offsides?: string | number | null;
    saves?: string | number | null;
    xg?: string | number | null;
  } | null;
}

export interface LiveFixture {
  fixture_id: number;
  status?: {
    long?: string | null;
    short?: string | null;
    minute?: number | null;
    extra_time?: number | null;
  };
  league?: {
    name?: string;
    logo?: string | null;
    country?: string | null;
    round?: string | null;
  };
  home: LiveTeamSide;
  away: LiveTeamSide;
}

export interface LiveStatsView {
  homeName: string;
  awayName: string;
  rows: Array<{ label: string; home: string; away: string }>;
  fixtureId: number;
  minute: number | null;
}

function fold(text: string): string {
  return text
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function aliasKey(name: string): string {
  const f = fold(name);
  for (const group of ALIAS_GROUPS) {
    if (group.some((a) => f === a || f.includes(a) || a.includes(f))) {
      return group[0];
    }
  }
  return f;
}

function teamScore(a: string, b: string): number {
  const fa = fold(a);
  const fb = fold(b);
  if (!fa || !fb) return 0;
  if (fa === fb) return 1;
  if (aliasKey(a) === aliasKey(b) && aliasKey(a).length > 2) return 0.95;
  if (fa.includes(fb) || fb.includes(fa)) return 0.85;
  const ta = new Set(fa.split(" ").filter((t) => t.length > 2));
  const tb = new Set(fb.split(" ").filter((t) => t.length > 2));
  if (ta.size === 0 || tb.size === 0) return 0;
  let inter = 0;
  for (const t of ta) if (tb.has(t)) inter += 1;
  return inter / Math.max(ta.size, tb.size);
}

function pairScore(
  wantHome: string,
  wantAway: string,
  liveHome: string,
  liveAway: string,
): number {
  const direct =
    teamScore(wantHome, liveHome) * 0.5 + teamScore(wantAway, liveAway) * 0.5;
  const swapped =
    teamScore(wantHome, liveAway) * 0.5 + teamScore(wantAway, liveHome) * 0.5;
  return Math.max(direct, swapped);
}

export async function fetchLiveFixtures(): Promise<LiveFixture[]> {
  const res = await fetch(`${BASE}/aurora/live`);
  if (!res.ok) {
    throw new Error(`Live feed indisponível (${res.status})`);
  }
  const data = (await res.json()) as { matches?: LiveFixture[] };
  return Array.isArray(data.matches) ? data.matches : [];
}

export function findLiveFixture(
  matches: LiveFixture[],
  homeName: string,
  awayName: string,
): LiveFixture | null {
  let best: LiveFixture | null = null;
  let bestScore = 0;
  for (const m of matches) {
    const s = pairScore(homeName, awayName, m.home?.name || "", m.away?.name || "");
    if (s > bestScore) {
      bestScore = s;
      best = m;
    }
  }
  return bestScore >= 0.55 ? best : null;
}

function parsePossession(value: string | number | null | undefined): number | null {
  if (value == null) return null;
  if (typeof value === "number" && Number.isFinite(value)) return value;
  const m = String(value).match(/(\d+(?:[.,]\d+)?)/);
  if (!m) return null;
  return Number(m[1].replace(",", "."));
}

function fmtStat(value: string | number | null | undefined): string {
  if (value == null || value === "") return "—";
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : value.toFixed(2);
  }
  const s = String(value).trim();
  return s || "—";
}

export function buildLiveStatsView(fx: LiveFixture): LiveStatsView {
  const hs = fx.home.statistics || {};
  const as = fx.away.statistics || {};
  return {
    homeName: fx.home.name,
    awayName: fx.away.name,
    fixtureId: fx.fixture_id,
    minute: fx.status?.minute ?? null,
    rows: [
      {
        label: "Posse",
        home: fmtStat(hs.possession),
        away: fmtStat(as.possession),
      },
      { label: "xG", home: fmtStat(hs.xg), away: fmtStat(as.xg) },
      {
        label: "Finalizações",
        home: fmtStat(hs.shots_total),
        away: fmtStat(as.shots_total),
      },
      {
        label: "Chutes no gol",
        home: fmtStat(hs.shots_on_target),
        away: fmtStat(as.shots_on_target),
      },
      {
        label: "Escanteios",
        home: fmtStat(hs.corners),
        away: fmtStat(as.corners),
      },
      {
        label: "Impedimentos",
        home: fmtStat(hs.offsides),
        away: fmtStat(as.offsides),
      },
      { label: "Faltas", home: fmtStat(hs.fouls), away: fmtStat(as.fouls) },
      {
        label: "Cartões amarelos",
        home: fmtStat(fx.home.yellow_cards ?? 0),
        away: fmtStat(fx.away.yellow_cards ?? 0),
      },
    ],
  };
}

/** FE presentation momentum from live stats (does not change MatchHeader logic). */
export function momentumFromLive(fx: LiveFixture): NonNullable<MatchCard["momentum"]> {
  const hp = parsePossession(fx.home.statistics?.possession) ?? 50;
  const ap = parsePossession(fx.away.statistics?.possession) ?? 50;
  const hs = Number(fx.home.statistics?.shots_total ?? 0) || 0;
  const as_ = Number(fx.away.statistics?.shots_total ?? 0) || 0;
  const hc = Number(fx.home.statistics?.corners ?? 0) || 0;
  const ac = Number(fx.away.statistics?.corners ?? 0) || 0;

  const homePressure = hp + hs * 4 + hc * 3;
  const awayPressure = ap + as_ * 4 + ac * 3;
  const gap = Math.abs(homePressure - awayPressure);

  if (gap < 12) {
    return {
      label: "Equilíbrio",
      side: "neutral",
      detail: "Partida sem dominância clara.",
    };
  }

  const homeLeads = homePressure > awayPressure;
  const extreme = gap >= 35;
  const side = homeLeads ? "home" : "away";
  const posse = homeLeads ? hp : ap;
  const shots = homeLeads ? hs : as_;
  const corners = homeLeads ? hc : ac;

  return {
    label: extreme
      ? homeLeads
        ? "Pressão extrema do mandante"
        : "Pressão extrema do visitante"
      : homeLeads
        ? "Pressão do mandante"
        : "Pressão do visitante",
    side,
    detail: [
      posse != null ? `${Math.round(posse)}% posse` : null,
      shots > 0 ? `${shots} finalizações` : null,
      corners > 0 ? `${corners} escanteios` : null,
    ]
      .filter(Boolean)
      .join(" · "),
  };
}

export function applyLiveToMatchCard(
  card: MatchCard,
  fx: LiveFixture,
): MatchCard {
  const sh = fx.home.score;
  const sa = fx.away.score;
  const minute = fx.status?.minute ?? card.minute ?? null;
  const momentum = momentumFromLive(fx);

  return {
    ...card,
    home: {
      name: card.home.name,
      logo: card.home.logo || fx.home.logo || null,
    },
    away: {
      name: card.away.name,
      logo: card.away.logo || fx.away.logo || null,
    },
    score:
      sh != null && sa != null
        ? { home: Number(sh), away: Number(sa) }
        : card.score ?? null,
    minute,
    is_live: true,
    status_label:
      fx.status?.long || fx.status?.short || card.status_label || "Ao vivo",
    momentum: {
      label: momentum.label,
      side: momentum.side,
      detail: momentum.detail,
    },
    competition: card.competition?.name
      ? card.competition
      : fx.league?.name
        ? {
            name: fx.league.name,
            logo: fx.league.logo ?? null,
            country: fx.league.country ?? null,
            round: fx.league.round ?? null,
          }
        : card.competition ?? null,
  };
}

export function formatUpdatedAgo(iso: string | null | undefined, nowMs = Date.now()): string | null {
  if (!iso) return null;
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return null;
  const sec = Math.max(0, Math.floor((nowMs - t) / 1000));
  if (sec < 5) return "Atualizado agora";
  if (sec < 60) return `Atualizado há ${sec} segundos`;
  const min = Math.floor(sec / 60);
  if (min === 1) return "Atualizado há 1 minuto";
  return `Atualizado há ${min} minutos`;
}
