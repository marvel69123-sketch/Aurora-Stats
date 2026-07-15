/**
 * Aurora v3.5.1 — FE-only live refresh helpers.
 * Consumes existing GET /aurora/live. Does not alter engines, FollowUp, or payloads.
 */

import type { CopilotResponse, LiveStatsSnapshot, MatchCard } from "@/types/chat";

const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

/** Common national-team / club name bridges (display matching only). */
const ALIAS_GROUPS: string[][] = [
  ["england", "inglaterra"],
  ["argentina", "argentina"],
  ["brazil", "brasil"],
  ["spain", "espanha"],
  ["germany", "alemanha"],
  ["france", "franca"],
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
  ["south korea", "corea do sul", "korea republic"],
  ["croatia", "croacia"],
  ["belgium", "belgica"],
  ["morocco", "marrocos"],
  ["senegal", "senegal"],
  ["nigeria", "nigeria"],
  ["cameroon", "camaroes"],
  ["australia", "australia"],
  ["canada", "canada"],
  ["switzerland", "suica"],
  ["poland", "polonia"],
  ["denmark", "dinamarca"],
  ["sweden", "suecia"],
  ["norway", "noruega"],
  ["austria", "austria"],
  ["scotland", "escocia"],
  ["wales", "gales"],
  ["ireland", "irlanda"],
  ["turkey", "turquia"],
  ["greece", "grecia"],
  ["serbia", "servia"],
  ["ukraine", "ucrania"],
  ["universidad catolica", "universidad catolica de chile", "uc catolica"],
  ["ldu quito", "ldu", "liga de quito", "ldu de quito"],
  ["leones del norte", "leones del norte"],
  ["deportivo cuenca", "cd cuenca"],
  ["universitario de deportes", "universitario lima"],
  ["manchester city", "man city", "manchester city fc"],
  ["manchester united", "man united", "man utd"],
  ["tottenham", "tottenham hotspur", "spurs"],
  ["psg", "paris saint germain", "paris sg"],
  ["inter milan", "internazionale", "fc internazionale"],
  ["atletico madrid", "atletico de madrid"],
  ["bayern", "bayern munich", "bayern munchen"],
  ["borussia dortmund", "dortmund", "bvb"],
  ["real madrid", "real madrid cf"],
  ["barcelona", "fc barcelona", "barca"],
];

/** Minimum pair score for name-based live resolution. */
const LIVE_NAME_THRESHOLD = 0.72;

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
  date?: string | null;
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
    // Prefer exact alias hits to avoid short-token overmatch (e.g. "inter").
    if (group.some((a) => f === a)) return group[0];
  }
  for (const group of ALIAS_GROUPS) {
    if (group.some((a) => a.length >= 5 && (f.includes(a) || a.includes(f)))) {
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
  const ka = aliasKey(a);
  const kb = aliasKey(b);
  if (ka === kb && ka.length > 2) return 0.95;
  if (fa.length >= 5 && fb.length >= 5 && (fa.includes(fb) || fb.includes(fa))) {
    return 0.85;
  }
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

export function findLiveFixtureById(
  matches: LiveFixture[],
  fixtureId: number | null | undefined,
): LiveFixture | null {
  if (fixtureId == null || !Number.isFinite(fixtureId) || fixtureId <= 0) {
    return null;
  }
  return matches.find((m) => m.fixture_id === fixtureId) ?? null;
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
  return bestScore >= LIVE_NAME_THRESHOLD ? best : null;
}

/** Prefer locked fixture_id; then cache identity; name only as last resort. */
export function resolveLiveFixture(
  matches: LiveFixture[],
  opts: {
    fixtureId?: number | null;
    homeName: string;
    awayName: string;
    /** When true and id is set, never fall back to name matching. */
    idOnly?: boolean;
    /** Optional FE cache — verifies name fallback against last known sides. */
    cache?: {
      lastFixtureId?: number | null;
      lastHome?: string | null;
      lastAway?: string | null;
      lastCompetition?: string | null;
    } | null;
  },
): LiveFixture | null {
  const id =
    opts.fixtureId && opts.fixtureId > 0
      ? opts.fixtureId
      : opts.cache?.lastFixtureId && opts.cache.lastFixtureId > 0
        ? opts.cache.lastFixtureId
        : null;

  const byId = findLiveFixtureById(matches, id);
  if (byId) return byId;

  // Had an id but fixture left the live feed — do not name-rematch to another game.
  if (opts.idOnly && id) return null;
  if (id) return null;

  const byName = findLiveFixture(matches, opts.homeName, opts.awayName);
  if (!byName) return null;

  // If we already know last home/away, reject weak rematches to a different fixture.
  const ch = opts.cache?.lastHome;
  const ca = opts.cache?.lastAway;
  if (ch && ca) {
    const verify = pairScore(ch, ca, byName.home?.name || "", byName.away?.name || "");
    if (verify < LIVE_NAME_THRESHOLD) return null;
  }
  return byName;
}

export function buildLiveCacheFromFixture(
  fx: LiveFixture,
  card?: MatchCard | null,
): {
  lastFixtureId: number;
  lastHome: string;
  lastAway: string;
  lastCompetition: string | null;
  kickoff: string | null;
} {
  return {
    lastFixtureId: fx.fixture_id,
    lastHome: card?.home?.name || fx.home.name,
    lastAway: card?.away?.name || fx.away.name,
    lastCompetition:
      card?.competition?.name || fx.league?.name || null,
    kickoff: fx.date || null,
  };
}

/** Collect FE-only / debug hints without changing backend payload schema. */
export function extractFixtureIdHint(opts: {
  liveFixtureId?: number | null;
  liveStats?: LiveStatsSnapshot | null;
  liveCache?: { lastFixtureId?: number | null } | null;
  response?: CopilotResponse | null;
}): number | null {
  if (opts.liveFixtureId && opts.liveFixtureId > 0) return opts.liveFixtureId;
  if (opts.liveCache?.lastFixtureId && opts.liveCache.lastFixtureId > 0) {
    return opts.liveCache.lastFixtureId;
  }
  if (opts.liveStats?.fixtureId && opts.liveStats.fixtureId > 0) {
    return opts.liveStats.fixtureId;
  }
  const dbg = opts.response?.debug?.fixture_id;
  if (typeof dbg === "number" && dbg > 0) return dbg;
  if (typeof dbg === "string" && /^\d+$/.test(dbg)) return Number(dbg);
  const ent = opts.response?.entities?.fixture_id;
  if (typeof ent === "number" && ent > 0) return ent;
  if (typeof ent === "string" && /^\d+$/.test(ent)) return Number(ent);
  return null;
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

export function formatUpdatedAgo(
  iso: string | null | undefined,
  nowMs = Date.now(),
): string | null {
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
