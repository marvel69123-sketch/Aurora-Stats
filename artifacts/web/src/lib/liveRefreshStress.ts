/**
 * Pure helpers for live refresh identity resolution (v3.5.1-b).
 * Runnable without Vite import.meta — used for stress/unit validation.
 */

export type MiniLive = {
  fixture_id: number;
  home: { name: string };
  away: { name: string };
};

export function resolveByPriority(opts: {
  matches: MiniLive[];
  fixtureId?: number | null;
  cacheId?: number | null;
  homeName: string;
  awayName: string;
  cacheHome?: string | null;
  cacheAway?: string | null;
  nameThreshold?: number;
}): { hit: MiniLive | null; via: "id" | "cache" | "name" | "none" } {
  const threshold = opts.nameThreshold ?? 0.72;
  const fold = (s: string) =>
    s
      .normalize("NFD")
      .replace(/\p{M}/gu, "")
      .toLowerCase()
      .trim();

  const byId = (id: number | null | undefined) =>
    id && id > 0
      ? opts.matches.find((m) => m.fixture_id === id) ?? null
      : null;

  const idHit = byId(opts.fixtureId);
  if (idHit) return { hit: idHit, via: "id" };

  const cacheHit = byId(opts.cacheId);
  if (cacheHit) return { hit: cacheHit, via: "cache" };

  // If we already had an id that left the feed — stop (no name rematch).
  if ((opts.fixtureId && opts.fixtureId > 0) || (opts.cacheId && opts.cacheId > 0)) {
    return { hit: null, via: "none" };
  }

  const score = (a: string, b: string) => {
    const fa = fold(a);
    const fb = fold(b);
    if (!fa || !fb) return 0;
    if (fa === fb) return 1;
    if (fa.includes(fb) || fb.includes(fa)) return 0.85;
    return 0;
  };
  const pair = (wh: string, wa: string, lh: string, la: string) =>
    Math.max(
      score(wh, lh) * 0.5 + score(wa, la) * 0.5,
      score(wh, la) * 0.5 + score(wa, lh) * 0.5,
    );

  let best: MiniLive | null = null;
  let bestScore = 0;
  for (const m of opts.matches) {
    const s = pair(opts.homeName, opts.awayName, m.home.name, m.away.name);
    if (s > bestScore) {
      bestScore = s;
      best = m;
    }
  }
  if (!best || bestScore < threshold) return { hit: null, via: "none" };

  if (opts.cacheHome && opts.cacheAway) {
    const verify = pair(
      opts.cacheHome,
      opts.cacheAway,
      best.home.name,
      best.away.name,
    );
    if (verify < threshold) return { hit: null, via: "none" };
  }

  return { hit: best, via: "name" };
}

/** Simulate 10 consecutive refreshes with locked id — must never rematch. */
export function stressRefreshLockedId(): boolean {
  const matches = [
    { fixture_id: 101, home: { name: "Arsenal" }, away: { name: "Chelsea" } },
    { fixture_id: 202, home: { name: "Argentina" }, away: { name: "England" } },
  ];
  let id: number | null = 101;
  for (let i = 0; i < 10; i += 1) {
    const r = resolveByPriority({
      matches,
      fixtureId: id,
      cacheId: 101,
      homeName: "Arsenal",
      awayName: "Chelsea",
      cacheHome: "Arsenal",
      cacheAway: "Chelsea",
    });
    if (!r.hit || r.hit.fixture_id !== 101 || r.via === "name") return false;
    id = r.hit.fixture_id;
  }
  // After leaving live feed:
  const ended = resolveByPriority({
    matches: [matches[1]],
    fixtureId: 101,
    cacheId: 101,
    homeName: "Arsenal",
    awayName: "Chelsea",
  });
  return ended.hit === null && ended.via === "none";
}
