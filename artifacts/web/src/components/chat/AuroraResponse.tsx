import { useEffect, useRef, useState } from "react";
import { ChevronDownIcon, ChevronUpIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  buildLiveCacheFromFixture,
  buildLiveStatsView,
  extractFixtureIdHint,
  fetchLiveFixtures,
  momentumFromLive,
  resolveLiveFixture,
} from "@/lib/liveMatch";
import {
  classifyMarketFocus,
  marketLabelPt,
  oneLinePt,
  scrubProsePt,
} from "@/lib/marketDisplay";
import {
  chromeHeading,
  chromeInlineMarker,
  chromeTitleClass,
  isTechnicalReportLayout,
  showChromeHeader,
  useConversationPreferencesContext,
} from "@/lib/conversationPersonalization";
import type {
  CopilotResponse,
  DebugAudit,
  LiveFixtureCache,
  LiveStatsSnapshot,
  MarketEntry,
  MatchCard,
} from "@/types/chat";
import { InsightBadgeRow, type InsightBadgeKind } from "./InsightBadge";
import { LiveStatsPanel } from "./LiveStatsPanel";
import { MarkdownInline } from "./Markdown";
import { MatchHeader, canRenderMatchHeader } from "./MatchHeader";
import { MomentumPanel } from "./MomentumPanel";
import { WarningCard } from "./WarningCard";

const INVALID_FIXTURE_TITLE =
  "Não consegui localizar um confronto esportivo válido.";
const INVALID_FIXTURE_HINT =
  "Verifique os nomes das equipes ou tente outro confronto.";

function isInvalidFixture(response: CopilotResponse): boolean {
  const quality =
    response.fixture_quality ||
    (typeof response.entities?.fixture_quality === "string"
      ? response.entities.fixture_quality
      : null);
  const status =
    response.fixture_status ||
    (typeof response.entities?.fixture_status === "string"
      ? response.entities.fixture_status
      : null);
  if (quality === "PARTIAL" || status === "PARTIAL") return false;
  if (quality === "INVALID") return true;
  if (status === "NOT_FOUND" || status === "FICTIONAL") return true;
  if (response.entities?.entity_invalid === true) return true;
  return false;
}

const RISK_PT: Record<string, string> = {
  Low: "Baixo",
  Medium: "Médio",
  High: "Alto",
  Unknown: "",
};

const CONF_PT: Record<string, string> = {
  strong: "alta",
  forte: "alta",
  alta: "alta",
  moderate: "moderada",
  moderada: "moderada",
  adequate: "adequada",
  adequada: "adequada",
  weak: "fraca",
  fraca: "fraca",
  insufficient: "baixa",
  insuficiente: "baixa",
  "muito baixa": "baixa",
  unavailable: "indisponível",
  indisponível: "indisponível",
  indisponivel: "indisponível",
};

/** Ideas reserved for the single decision alert — never in summary/bullets. */
const LOW_CONF_IDEA_RE =
  /confiança\s+(muito\s+)?baixa|manteve a conversa|ainda faltam sinais|previsibilidade\s+(muito\s+)?baixa|aguardar(ia)?\s+mais\s+confirma|prefira\s+acompanhar|sinais\s+(claros\s+)?insuficientes|cenário\s+(de\s+)?(baixa confiança|incerto)|fixture\s+(oficial\s+)?(ainda\s+)?n[aã]o\s+confirm|dados\s+parciais|sem fixture|indispon[ií]vel/i;

const TECH_FACTOR_RE =
  /\d+[.,]?\d*\s*\/\s*10|best[-_\s]?mercado|best[-_\s]?market|over_\d+|λ\s*=|ve\s*[+\-]|puxando a pontua|puxando a nota|modo degradado|fixture oficial|precis[aã]o\s+\d|≥\s*60%|api[-_\s]?football|data_completeness|market_generation|category pulling|portfolio exposure|regras ao vivo|gest[aã]o de risco|nenhum dado hist[oó]rico|mercado de melhor desempenho|completude dos dados|dados faltantes|infer[eê]ncias|penalidade de confian|sem dados de xg|nenhum hist[oó]rico|confronto reconhecido|an[aá]lise completa de/i;

/** Strip noisy technical methodology notes from the main/details surface. */
function publicNotes(notes: string[]): string[] {
  return notes.filter((n) => !TECH_FACTOR_RE.test(n) && !/^\[/.test(n.trim()));
}

const INTERESTING_MARKET_RE =
  /gol|btts|ambos|escanteio|canto|1x2|vit[oó]r|win|empate|vencedor|over|under|handicap|dnb|cart[aã]o|card|dupla|double\s*chance|pr[oó]ximo\s*gol|next\s*goal/i;

/** Non-market CTAs / player props — never featured. */
const NON_MARKET_FEATURED_RE =
  /an[aá]lise\s+completa|confronto\s+reconhecido|player|jogador|anytime|scorer|assist\b/i;

function isRealFeaturedMarket(market: string): boolean {
  const m = (market || "").trim();
  if (!m || NON_MARKET_FEATURED_RE.test(m)) return false;
  if (/^analisar\b/i.test(m)) return false;

  const focus = classifyMarketFocus(m);
  // Cards allowed in featured allowlist (Over/Under cartões)
  if (/cart[aã]o|\bcards?\b|booking/i.test(m) && /over|under|mais|menos|\d/i.test(m)) {
    return true;
  }
  if (focus === "other") {
    return (
      INTERESTING_MARKET_RE.test(m) &&
      /goal|gol|corner|escanteio|canto|cart[aã]o|card|handicap|dupla|btts|ambos|win|empate|over|under/i.test(
        m,
      )
    );
  }
  return (
    focus === "goals" ||
    focus === "btts" ||
    focus === "corners" ||
    focus === "winner" ||
    focus === "handicap" ||
    focus === "dnb"
  );
}

function deriveBadges(response: CopilotResponse): InsightBadgeKind[] {
  if (
    response.intent === "greeting" ||
    response.intent === "identity" ||
    response.intent === "help" ||
    response.intent === "capabilities" ||
    response.intent === "small_talk" ||
    response.intent === "unknown" ||
    response.intent === "emotional"
  ) {
    return [];
  }
  if (response.intent === "analyze_match" || response.intent === "live_opportunities") {
    const riskHigh = response.risk.level === "High";
    const noBet = response.bankroll_recommendation.no_bet;
    const strong =
      response.confidence.label === "strong" || response.confidence.score >= 7.5;
    if (!riskHigh && !noBet && strong) return ["opportunity"];
    return [];
  }
  const kinds: InsightBadgeKind[] = [];
  if (response.risk.level === "High") kinds.push("high_risk");
  else if (response.bankroll_recommendation.no_bet) kinds.push("caution");
  return kinds;
}

function splitSentences(text: string): string[] {
  return scrubProsePt(text || "")
    .replace(/\*\*/g, "")
    .split(/(?<=[.!?…])\s+|\n+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

function ideaKey(sentence: string): string {
  const s = sentence.toLowerCase();
  if (LOW_CONF_IDEA_RE.test(s)) return "low_conf";
  if (/mercado|escanteio|gol|btts|handicap/i.test(s)) return `mkt:${s.slice(0, 40)}`;
  return s.replace(/\s+/g, " ").slice(0, 80);
}

/**
 * Max 2 sentences; skip low-confidence noise (alert owns that idea).
 * Live with data: never say “dados limitados”.
 */
function compactSummary(
  text: string,
  usedIdeas: Set<string>,
  fallbackMatch: string | null,
  opts?: { isLive?: boolean; hasLiveData?: boolean },
): string {
  const out: string[] = [];
  for (const sentence of splitSentences(text)) {
    if (TECH_FACTOR_RE.test(sentence)) continue;
    if (LOW_CONF_IDEA_RE.test(sentence)) continue; // reserved for alert
    if (/an[aá]lise\s+completa|dados\s+atuais\s+ainda\s+s[aã]o\s+limitados|sem\s+dados\s+de\s+xg|nenhum\s+hist[oó]rico|fixture\s+ainda/i.test(sentence)) {
      continue;
    }
    const key = ideaKey(sentence);
    if (usedIdeas.has(key)) continue;
    if (/^confronto reconhecido\.?$/i.test(sentence) && out.length === 0) {
      continue;
    }
    usedIdeas.add(key);
    out.push(sentence.replace(/\s+/g, " ").trim());
    if (out.length >= 2) break;
  }
  if (out.length === 0 && fallbackMatch) {
    if (opts?.isLive || opts?.hasLiveData) {
      out.push("Análise baseada nos dados disponíveis no momento.");
      usedIdeas.add("summary_live_data");
    } else {
      out.push("Análise baseada nos dados disponíveis no momento.");
      usedIdeas.add("summary_fallback");
    }
  } else if (out.length === 1 && /reconhecido/i.test(out[0])) {
    out[0] = "Análise baseada nos dados disponíveis no momento.";
    usedIdeas.add("summary_limited");
  }
  return out.slice(0, 2).join(" ");
}

function humanBullet(raw: string): string | null {
  let t = oneLinePt((raw || "").replace(/^•\s*/, "").replace(/\*\*/g, ""), 72);
  if (!t || TECH_FACTOR_RE.test(t)) return null;
  if (LOW_CONF_IDEA_RE.test(t)) return null;
  if (/an[aá]lise\s+completa/i.test(t)) return null;
  return t || null;
}

function uniqueBullets(items: string[], usedIdeas: Set<string>, limit = 3): string[] {
  const out: string[] = [];
  for (const raw of items) {
    const bullet = humanBullet(raw);
    if (!bullet) continue;
    const key = ideaKey(bullet);
    if (usedIdeas.has(key)) continue;
    usedIdeas.add(key);
    out.push(bullet);
    if (out.length >= limit) break;
  }
  return out;
}

function publicStrengths(response: CopilotResponse): string[] {
  const meta = response.response_metadata;
  if (meta?.public_strengths?.length) return meta.public_strengths;
  return response.positive_factors || [];
}

function pickInterestingMarkets(
  markets: MarketEntry[],
  isLive = false,
): MarketEntry[] {
  const filtered = markets.filter((m) => isRealFeaturedMarket(m.market));
  return filtered.slice(0, isLive ? 1 : 2);
}

/** Rows allowed in the technical analysis table (no CTAs / internal labels). */
function displayableMarketRows(markets: MarketEntry[]): MarketEntry[] {
  return markets.filter((m) => {
    const name = (m.market || "").trim();
    if (!name) return false;
    if (NON_MARKET_FEATURED_RE.test(name)) return false;
    if (/^analisar\b/i.test(name)) return false;
    return true;
  });
}

/**
 * Natural featured-market copy — never reuse truncated engine rationales
 * like "Empate ao min 67…".
 */
function featuredNarrative(
  market: MarketEntry,
  opts: {
    isLive: boolean;
    momentumSide?: string | null;
  },
): { context: string; opportunity: string } {
  const label = marketLabelPt(market.market);
  const side = (opts.momentumSide || "").toLowerCase();

  let context: string;
  if (side === "neutral") {
    context = "Confronto equilibrado. Ambas as equipes seguem criando oportunidades.";
  } else if (side === "home") {
    context = "O mandante pressiona neste momento.";
  } else if (side === "away") {
    context = "O visitante pressiona neste momento.";
  } else {
    context = opts.isLive
      ? "Leitura com base no cenário atual da partida."
      : "Leitura com base nos dados disponíveis do confronto.";
  }

  return {
    context,
    opportunity: `Mercado de ${label} apresenta valor neste momento.`,
  };
}

/**
 * Único alerta consolidado do viewport (v3.4) — substitui previsibilidade + banners soltos.
 *
 * Quando PARTIAL deve aparecer:
 * - `fixture_quality === "PARTIAL"` ou `fixture_status === "PARTIAL"` no payload.
 * - Significa: confronto reconhecível, mas fixture oficial ainda não confirmada
 *   (dados incompletos / precheck parcial). NÃO é INVALID/FICTIONAL.
 * - Nesses casos a UI mostra uma linha compacta; frases de baixa confiança
 *   equivalentes são filtradas do resumo/bullets (`LOW_CONF_IDEA_RE`).
 * - Prioridade: PARTIAL > risco elevado/no_bet+baixa conf > só baixa confiança.
 * - Não altera Integrity Guard nem payloads — só apresentação.
 */
function decisionAlert(response: CopilotResponse): string | null {
  const quality =
    response.fixture_quality ||
    (typeof response.entities?.fixture_quality === "string"
      ? response.entities.fixture_quality
      : null);
  const partial = quality === "PARTIAL" || response.fixture_status === "PARTIAL";
  const lowConf =
    response.confidence.score > 0 &&
    (response.confidence.score < 5 ||
      ["insufficient", "weak", "insuficiente", "fraca", "muito baixa"].includes(
        response.confidence.label,
      ));
  const highRisk = response.risk.level === "High";
  const noBet = response.bankroll_recommendation.no_bet;

  if (partial) {
    return "Cenário de baixa confiança. Partida ainda não confirmada.";
  }
  if (highRisk || (noBet && lowConf)) {
    return "Cenário de risco elevado. Mercados podem sofrer alterações.";
  }
  if (lowConf || (noBet && response.confidence.score > 0)) {
    return "Confiança baixa neste momento.";
  }
  return null;
}

function confLabelPt(label: string): string {
  return CONF_PT[label] || scrubProsePt(label) || "—";
}

function Details({
  title,
  children,
  defaultOpen = false,
}: {
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <details
      className="pt-1"
      open={open}
      onToggle={(e) => {
        const next = e.currentTarget.open;
        if (next !== open) setOpen(next);
      }}
    >
      <summary className="flex w-full cursor-pointer list-none items-center justify-between py-1.5 text-left text-[0.8125rem] text-[#A0A0A0] transition-colors hover:text-[#ECECEC] [&::-webkit-details-marker]:hidden">
        <span className="font-medium tracking-wide">{title}</span>
        {open ? <ChevronUpIcon size={14} /> : <ChevronDownIcon size={14} />}
      </summary>
      {open && <div className="mt-3 space-y-5">{children}</div>}
    </details>
  );
}

function MarketsTable({ markets }: { markets: MarketEntry[] }) {
  const rows = displayableMarketRows(markets);
  if (rows.length === 0) {
    return (
      <p className="text-[0.8125rem] leading-relaxed text-[#A0A0A0]">
        Nenhum mercado técnico disponível neste momento.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto -mx-0.5">
      <table className="w-full min-w-[300px] text-[0.8125rem]">
        <thead>
          <tr className="border-b border-white/[0.05] text-[#A0A0A0]/80">
            <th className="px-1 py-2 text-left font-medium">Mercado</th>
            <th className="px-1 py-2 text-right font-medium">Prob.</th>
            <th className="px-1 py-2 text-right font-medium">VME</th>
            <th className="px-1 py-2 text-right font-medium">Risco</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/[0.04]">
          {rows.map((m) => (
            <tr key={m.rank}>
              <td className="px-1 py-2 text-[#ECECEC]/90">
                {marketLabelPt(m.market)}
              </td>
              <td className="whitespace-nowrap px-1 py-2 text-right tabular-nums text-[#A0A0A0]">
                {m.probability.toFixed(0)}%
              </td>
              <td
                className={cn(
                  "whitespace-nowrap px-1 py-2 text-right font-medium tabular-nums",
                  m.expected_value > 0 ? "text-emerald-400/90" : "text-rose-400/90",
                )}
              >
                {m.expected_value > 0 ? "+" : ""}
                {m.expected_value.toFixed(1)}%
              </td>
              <td className="whitespace-nowrap px-1 py-2 text-right text-[#A0A0A0]">
                {RISK_PT[m.risk] || (/^unknown$/i.test(m.risk) ? "—" : scrubProsePt(m.risk))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TechnicalAnalysisCard({
  response,
  recommended,
}: {
  response: CopilotResponse;
  recommended: MarketEntry | null;
}) {
  const riskLabel = RISK_PT[response.risk.level] || "";
  const conf =
    response.confidence.score > 0
      ? `${response.confidence.score.toFixed(1)}/10 · ${confLabelPt(response.confidence.label)}`
      : "—";

  const matchLabel = (response.match || "").toLowerCase();
  const scopedMarkets =
    response.intent === "live_opportunities"
      ? displayableMarketRows(response.best_markets).filter((m) => {
          // Defense: drop rows that clearly name a different fixture's clubs.
          const label = (m.market || "").toLowerCase();
          if (/orlando pride|fort wayne|new england/i.test(label) && matchLabel) {
            if (
              !matchLabel.includes("orlando") &&
              !matchLabel.includes("fort wayne") &&
              !matchLabel.includes("new england")
            ) {
              return false;
            }
          }
          return true;
        })
      : displayableMarketRows(response.best_markets);

  const metrics: Array<{ label: string; value: string }> = [
    {
      label: "Mercado recomendado",
      value: recommended ? marketLabelPt(recommended.market) : "—",
    },
    {
      label: "Probabilidade",
      value: recommended ? `${recommended.probability.toFixed(0)}%` : "—",
    },
    {
      label: "VME",
      value: recommended
        ? `${recommended.expected_value > 0 ? "+" : ""}${recommended.expected_value.toFixed(1)}%`
        : "—",
    },
    {
      label: "Risco",
      value: riskLabel || "—",
    },
    {
      label: "Confiança",
      value: conf,
    },
  ];

  return (
    <section
      className="space-y-4 rounded-xl border border-white/[0.07] bg-[#1b1b1d]/55 px-3.5 py-3.5"
      aria-label="Análise completa"
    >
      <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-[#A0A0A0]">
        Análise completa
      </p>
      <dl className="grid gap-2.5 sm:grid-cols-2">
        {metrics.map((m) => (
          <div
            key={m.label}
            className="rounded-lg border border-white/[0.04] bg-white/[0.02] px-3 py-2.5"
          >
            <dt className="text-[0.6875rem] text-[#A0A0A0]">{m.label}</dt>
            <dd className="mt-0.5 text-[0.875rem] font-medium leading-snug text-[#ECECEC]">
              {m.value}
            </dd>
          </div>
        ))}
      </dl>
      {!response.bankroll_recommendation.no_bet ? (
        <p className="text-[0.8125rem] leading-relaxed text-[#A0A0A0]">
          Stake sugerida:{" "}
          <span className="text-[#ECECEC]">
            {response.bankroll_recommendation.recommended_stake_pct.toFixed(1)}%
          </span>{" "}
          da banca
        </p>
      ) : null}
      {scopedMarkets.length > 0 ? (
        <div>
          <p className="mb-2 text-[0.75rem] font-medium text-[#A0A0A0]">
            Probabilidades por mercado
          </p>
          <MarketsTable markets={scopedMarkets} />
        </div>
      ) : null}
    </section>
  );
}

/** Aurora v3.5 — live experience + premium presentation hierarchy. */
export function AuroraResponse({
  response,
  onRefreshMatch,
  refreshing = false,
  refreshedAt = null,
  liveStats = null,
  liveStatusNote = null,
  onLiveContextLock,
}: {
  response: CopilotResponse;
  onRefreshMatch?: () => void;
  refreshing?: boolean;
  refreshedAt?: string | null;
  liveStats?: LiveStatsSnapshot | null;
  liveStatusNote?: string | null;
  onLiveContextLock?: (cache: LiveFixtureCache, stats: LiveStatsSnapshot) => void;
}) {
  // Chrome prefs only (emojis / enthusiasm / headers) — never alters reply body.
  const chromePrefs = useConversationPreferencesContext();

  if (isInvalidFixture(response)) {
    return (
      <article className="w-full max-w-none space-y-4" aria-label="Confronto inválido">
        <WarningCard
          variant="warning"
          title={INVALID_FIXTURE_TITLE}
          description={INVALID_FIXTURE_HINT}
        />
        <DeployDebugSnapshot response={response} />
      </article>
    );
  }

  const usedIdeas = new Set<string>();
  const hasMarkets = response.best_markets.length > 0;
  const notes = publicNotes(response.knowledge_notes || []);
  const hasNotes = notes.length > 0;
  const hasHistory = response.historical_references.length > 0;

  const badges = deriveBadges(response);
  const isSocial =
    response.intent === "greeting" ||
    response.intent === "identity" ||
    response.intent === "help" ||
    response.intent === "capabilities" ||
    response.intent === "small_talk" ||
    response.intent === "emotional";

  const isAnalysis =
    response.intent === "analyze_match" ||
    response.intent === "follow_up" ||
    response.intent === "live_opportunities" ||
    response.intent === "live_team_analysis";

  const baseCard = response.match_card ?? null;
  const fixtureStatus =
    response.fixture_status ||
    (typeof response.entities?.fixture_status === "string"
      ? response.entities.fixture_status
      : null);
  const fixtureQuality =
    response.fixture_quality ||
    (typeof response.entities?.fixture_quality === "string"
      ? response.entities.fixture_quality
      : null);
  const integrityBlocked =
    fixtureQuality === "INVALID" ||
    fixtureStatus === "NOT_FOUND" ||
    fixtureStatus === "FICTIONAL" ||
    response.entities?.entity_invalid === true;

  const showMatchHeader = !integrityBlocked && canRenderMatchHeader(baseCard);
  const isLiveCard = Boolean(baseCard?.is_live || response.is_live);

  const [bootStats, setBootStats] = useState<LiveStatsSnapshot | null>(null);
  const [bootMomentum, setBootMomentum] = useState<MatchCard["momentum"] | null>(
    null,
  );

  // Never keep boot enrichment after the card leaves live — avoid stale stats.
  useEffect(() => {
    if (!isLiveCard) {
      setBootStats(null);
      setBootMomentum(null);
    }
  }, [isLiveCard]);

  // Network / refresh failure: wipe boot enrichment so nothing stale remains on screen.
  useEffect(() => {
    if (liveStatusNote && /temporariamente indispon/i.test(liveStatusNote)) {
      setBootStats(null);
      setBootMomentum(null);
    }
  }, [liveStatusNote]);

  const lockedFixtureHint = extractFixtureIdHint({ liveStats, response });
  const lockRef = useRef(onLiveContextLock);
  lockRef.current = onLiveContextLock;

  useEffect(() => {
    if (!isLiveCard || !baseCard?.home?.name || !baseCard?.away?.name) return;
    // Already have fixture id from message — no need to re-fetch / re-lock in a loop
    if (liveStats?.fixtureId) return;

    let cancelled = false;
    (async () => {
      try {
        const fixtures = await fetchLiveFixtures();
        const live = resolveLiveFixture(fixtures, {
          fixtureId: lockedFixtureHint,
          homeName: baseCard.home.name,
          awayName: baseCard.away.name,
          idOnly: Boolean(lockedFixtureHint),
        });
        if (cancelled || !live) return;
        const stats = buildLiveStatsView(live);
        const cache = buildLiveCacheFromFixture(live, baseCard);
        setBootStats(stats);
        setBootMomentum(momentumFromLive(live) ?? null);
        lockRef.current?.(cache, stats);
      } catch {
        // optional enrichment — ignore
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [
    isLiveCard,
    liveStats?.fixtureId,
    lockedFixtureHint,
    baseCard?.home?.name,
    baseCard?.away?.name,
    baseCard?.competition?.name,
  ]);

  const statsBlockedByRefreshError = Boolean(
    liveStatusNote && /temporariamente indispon/i.test(liveStatusNote),
  );
  const statsView = statsBlockedByRefreshError ? null : liveStats || bootStats;
  const card: MatchCard | null =
    baseCard && bootMomentum && !baseCard.momentum?.detail
      ? { ...baseCard, momentum: bootMomentum }
      : baseCard;

  const matchLabel =
    response.match && !/^unknown$/i.test(response.match) ? response.match : null;

  const alertText =
    !isSocial && isAnalysis ? decisionAlert(response) : null;
  if (alertText) usedIdeas.add("low_conf");

  const hasLiveData = Boolean(
    statsView ||
      (isLiveCard &&
        (card?.score != null || (card?.minute != null && card.minute > 0))),
  );

  const summaryText = compactSummary(
    response.executive_summary || "",
    usedIdeas,
    isAnalysis ? matchLabel : null,
    { isLive: isLiveCard, hasLiveData },
  );

  const interesting =
    !integrityBlocked && isAnalysis
      ? pickInterestingMarkets(response.best_markets, isLiveCard)
      : [];
  const showMarketsBlock = !integrityBlocked && isAnalysis;
  const recommendedMarket =
    interesting[0] ||
    displayableMarketRows(response.best_markets)[0] ||
    null;

  const favorBullets =
    !integrityBlocked &&
    (response.intent === "analyze_match" || response.intent === "follow_up")
      ? uniqueBullets(publicStrengths(response), usedIdeas, 3)
      : [];

  const attentionBullets =
    !integrityBlocked &&
    (response.intent === "analyze_match" || response.intent === "follow_up")
      ? uniqueBullets(response.negative_factors || [], usedIdeas, 3)
      : [];

  // Prefer MatchHeader over duplicate "England x Argentina ao vivo" meta line
  const metaBits: string[] = [];
  if (!showMatchHeader && !integrityBlocked && response.is_live) {
    metaBits.push(
      response.minute != null ? `Ao vivo ${response.minute}'` : "Ao vivo",
    );
  }

  const showDetails =
    !isSocial &&
    (response.confidence.score > 0 ||
      !response.bankroll_recommendation.no_bet ||
      hasMarkets ||
      (response.positive_factors?.length ?? 0) > 0 ||
      (response.negative_factors?.length ?? 0) > 0 ||
      hasNotes ||
      hasHistory);

  const momentum =
    card?.momentum && card.momentum.label ? card.momentum : bootMomentum;
  const showMomentum = Boolean(isLiveCard && momentum?.label);

  const highRiskUrgent =
    response.risk.level === "High" &&
    (response.is_live || card?.is_live) &&
    !alertText;

  return (
    <article
      /* Mobile: space-y-5 (~20px) evita stack denso; sm+ abre para space-y-7. */
      className="w-full max-w-none space-y-5 sm:space-y-7"
      aria-label="Resposta Aurora"
    >
      {/*
        Hierarquia v3.4 (+ Premium Live):
        header → resumo → destaque → alerta → [live] → favor/atenção → detalhes

        Por que Momentum/LiveStats ficam entre alerta e bullets:
        - Alerta é decisão de confiança/risco (contexto antes de dados ao vivo).
        - Painéis live são evidência factual do momento (posse, cartões, ritmo)
          e devem ficar perto do destaque/alerta, não enterrados em “análise completa”.
        - Favor/Atenção são síntese narrativa (forças/riscos do payload) e leem
          melhor depois dos números live — no mobile o stack vertical mantém essa ordem.
        - Fora do plano v3.4 original; inserção intencional do Premium Live sem
          alterar MatchHeader / Integrity / engines.
      */}
      <InsightBadgeRow kinds={badges} />

      {showMatchHeader && card ? (
        <MatchHeader
          card={card}
          onRefresh={onRefreshMatch}
          refreshing={refreshing}
          refreshedAt={refreshedAt}
          hideMomentum={showMomentum}
        />
      ) : metaBits.length > 0 ? (
        <header aria-label="Partida">
          <p className="text-[0.9375rem] font-medium leading-relaxed text-[#ECECEC]">
            {metaBits.join(" · ")}
          </p>
        </header>
      ) : null}

      {liveStatusNote ? (
        <p
          className={
            /temporariamente indispon/i.test(liveStatusNote)
              ? "rounded-xl border border-amber-400/15 bg-amber-400/[0.04] px-3.5 py-2.5 text-[0.875rem] leading-relaxed text-[#ECECEC]/90"
              : "text-[0.875rem] leading-relaxed text-[#A0A0A0]"
          }
          role="status"
        >
          {liveStatusNote}
        </p>
      ) : null}

      {summaryText ? (
        <section aria-label="Resumo">
          {showChromeHeader(chromePrefs, "resumo") ? (
            <p
              className={`mb-1.5 uppercase text-[#A0A0A0] ${chromeTitleClass(chromePrefs)}`}
            >
              {chromeHeading("resumo", chromePrefs)}
            </p>
          ) : null}
          <p
            className={
              chromePrefs.enthusiasm === "high"
                ? "text-[15px] leading-[1.7] text-[#ECECEC]"
                : chromePrefs.enthusiasm === "low"
                  ? "text-[15px] leading-[1.8] text-[#ECECEC]/85"
                  : "text-[15px] leading-[1.75] text-[#ECECEC]/92"
            }
          >
            {summaryText}
          </p>
        </section>
      ) : null}

      {/* v3.6.4 — card unificado: Mercado destaque + A favor + Atenção (só layout) */}
      {(showMarketsBlock ||
        favorBullets.length > 0 ||
        attentionBullets.length > 0) && (
        <section
          className="rounded-xl border border-emerald-400/15 bg-emerald-400/[0.04] px-3.5 py-3.5"
          aria-label="Destaque da análise"
        >
          {showMarketsBlock ? (
            <div>
              {showChromeHeader(chromePrefs, "featured") ? (
                <p
                  className={`mb-3 uppercase text-emerald-300/75 ${chromeTitleClass(chromePrefs)}`}
                >
                  {chromeHeading("featured", chromePrefs)}
                </p>
              ) : (
                <p className="sr-only">Mercado em destaque</p>
              )}
              {interesting.length > 0 ? (
                <div className="space-y-3.5">
                  {interesting.map((m) => {
                    const narrative = featuredNarrative(m, {
                      isLive: isLiveCard,
                      momentumSide:
                        card?.momentum?.side ?? bootMomentum?.side ?? null,
                    });
                    return (
                      <div key={m.rank} className="space-y-2.5">
                        <p className="text-[1rem] font-medium leading-snug tracking-[-0.01em] text-[#ECECEC]">
                          {marketLabelPt(m.market)}
                        </p>
                        <div className="space-y-1.5 text-[0.8125rem] leading-relaxed text-[#A0A0A0]">
                          <p>
                            <span className="mr-1 text-[#ECECEC]/80">
                              {chromeInlineMarker("context", chromePrefs)}
                              Contexto:
                            </span>
                            {narrative.context}
                          </p>
                          <p>
                            <span className="mr-1 text-[#ECECEC]/80">
                              {chromeInlineMarker("opportunity", chromePrefs)}
                              Oportunidade:
                            </span>
                            {narrative.opportunity}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="space-y-1 py-0.5">
                  <p className="text-[0.875rem] font-medium leading-snug text-[#ECECEC]/95">
                    {chromePrefs.emojis !== "none" &&
                    chromePrefs.emojis !== "low"
                      ? "🔥 "
                      : ""}
                    Mercado em observação
                  </p>
                  <p className="text-[0.8125rem] leading-relaxed text-[#A0A0A0]">
                    Nenhuma oportunidade clara identificada neste momento.
                  </p>
                </div>
              )}
            </div>
          ) : null}

          {favorBullets.length > 0 ? (
            <div
              className={
                showMarketsBlock
                  ? "mt-4 border-t border-white/[0.06] pt-3.5"
                  : ""
              }
            >
              {showChromeHeader(chromePrefs, "favor") ? (
                <p
                  className={`mb-1.5 uppercase text-emerald-200/80 ${chromeTitleClass(chromePrefs)}`}
                >
                  {chromeHeading("favor", chromePrefs)}
                </p>
              ) : (
                <p className="sr-only">A favor</p>
              )}
              <ul className="space-y-1">
                {favorBullets.map((f, i) => (
                  <li
                    key={i}
                    className="text-[0.8125rem] leading-snug text-[#ECECEC]/88"
                  >
                    {chromeInlineMarker("bullet", chromePrefs)}
                    {f}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {attentionBullets.length > 0 ? (
            <div
              className={
                showMarketsBlock || favorBullets.length > 0
                  ? "mt-3.5 rounded-lg border border-amber-400/20 bg-amber-400/[0.06] px-3 py-2.5"
                  : "rounded-lg border border-amber-400/20 bg-amber-400/[0.06] px-3 py-2.5"
              }
            >
              {showChromeHeader(chromePrefs, "attention") ? (
                <p
                  className={`mb-1.5 uppercase text-amber-300/80 ${chromeTitleClass(chromePrefs)}`}
                >
                  {chromeHeading("attention", chromePrefs)}
                </p>
              ) : (
                <p className="sr-only">Atenção</p>
              )}
              <ul className="space-y-1">
                {attentionBullets.map((f, i) => (
                  <li
                    key={i}
                    className="text-[0.8125rem] leading-snug text-[#ECECEC]/88"
                  >
                    {chromeInlineMarker("bullet", chromePrefs)}
                    {f}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </section>
      )}

      {/* Alerta de confiança — fora do card unificado */}
      {alertText ? (
        <section
          className="rounded-xl border border-amber-400/15 bg-amber-400/[0.04] px-3.5 py-2.5"
          aria-label="Atenção"
        >
          {showChromeHeader(chromePrefs, "alert") ? (
            <p
              className={`uppercase text-amber-300/75 ${chromeTitleClass(chromePrefs)}`}
            >
              {chromeHeading("alert", chromePrefs)}
            </p>
          ) : (
            <p className="sr-only">Atenção</p>
          )}
          <p className="mt-1 text-[0.875rem] leading-relaxed text-[#ECECEC]/90">
            {alertText}
          </p>
        </section>
      ) : null}

      {highRiskUrgent ? (
        <section
          className="rounded-xl border border-rose-400/20 bg-rose-400/[0.05] px-3.5 py-2.5"
          aria-label="Evento importante"
        >
          {showChromeHeader(chromePrefs, "urgency") ? (
            <p
              className={`uppercase text-rose-300/80 ${chromeTitleClass(chromePrefs)}`}
            >
              {chromeHeading("urgency", chromePrefs)}
            </p>
          ) : (
            <p className="sr-only">Evento importante</p>
          )}
          <p className="mt-1 text-[0.875rem] leading-relaxed text-[#ECECEC]/90">
            Cenário de risco elevado — revise stake e invalidadores antes de entrar.
          </p>
        </section>
      ) : null}

      {/* Live — intacto */}
      {isLiveCard && showMomentum && momentum ? (
        <MomentumPanel momentum={momentum} />
      ) : null}

      {isLiveCard && statsView ? <LiveStatsPanel stats={statsView} /> : null}

      {showDetails
        ? (() => {
            const detailsBody = (
              <>
                {showChromeHeader(chromePrefs, "markets_label") ? (
                  <p
                    className={`mb-2 uppercase text-[#A0A0A0] ${chromeTitleClass(chromePrefs)}`}
                  >
                    {chromeHeading("markets_label", chromePrefs)}
                  </p>
                ) : null}
                <TechnicalAnalysisCard
                  response={response}
                  recommended={recommendedMarket}
                />

                {hasNotes && (
                  <section aria-label="Notas" className="mt-4">
                    {showChromeHeader(chromePrefs, "notes_label") ? (
                      <p
                        className={`mb-1.5 uppercase text-[#A0A0A0] ${chromeTitleClass(chromePrefs)}`}
                      >
                        {chromeHeading("notes_label", chromePrefs)}
                      </p>
                    ) : null}
                    <ul className="space-y-1.5">
                      {notes.slice(0, 4).map((n, i) => (
                        <li
                          key={i}
                          className="text-[0.75rem] leading-relaxed text-[#A0A0A0]"
                        >
                          <MarkdownInline text={scrubProsePt(n)} />
                        </li>
                      ))}
                    </ul>
                  </section>
                )}

                {hasHistory && (
                  <section aria-label="Histórico" className="mt-4">
                    {showChromeHeader(chromePrefs, "history_label") ? (
                      <p
                        className={`mb-1.5 uppercase text-[#A0A0A0] ${chromeTitleClass(chromePrefs)}`}
                      >
                        {chromeHeading("history_label", chromePrefs)}
                      </p>
                    ) : null}
                    <ul className="space-y-1.5">
                      {response.historical_references.slice(0, 3).map((r, i) => (
                        <li
                          key={i}
                          className="text-[0.75rem] leading-relaxed text-[#A0A0A0]"
                        >
                          <MarkdownInline text={scrubProsePt(r)} />
                        </li>
                      ))}
                    </ul>
                  </section>
                )}
              </>
            );

            // Técnica = relatório sempre expandido; Casual = accordion (sem Casual real ainda)
            if (isTechnicalReportLayout(chromePrefs)) {
              return (
                <section
                  className="space-y-4 border-t border-white/[0.06] pt-4"
                  aria-label="Análise completa"
                >
                  {detailsBody}
                </section>
              );
            }

            return (
              <Details
                title={chromeHeading("details", chromePrefs)}
                defaultOpen={false}
              >
                {detailsBody}
              </Details>
            );
          })()
        : null}

      <DeployDebugSnapshot response={response} />
    </article>
  );
}

function clientDebugEnabled(): boolean {
  try {
    if (typeof window === "undefined") return false;
    const q = new URLSearchParams(window.location.search);
    if (q.get("debug") === "1" || q.get("debug") === "true") return true;
    if (localStorage.getItem("aurora_debug") === "1") return true;
  } catch {
    // ignore
  }
  return false;
}

function DeployDebugSnapshot({ response }: { response: CopilotResponse }) {
  // Hard gate: only when user explicitly opts into debug UI (?debug=1 / localStorage).
  if (!clientDebugEnabled()) return null;

  const card = response.match_card ?? null;
  const fixtureQuality =
    response.fixture_quality ||
    (typeof response.entities?.fixture_quality === "string"
      ? response.entities.fixture_quality
      : null) ||
    (typeof response.debug?.fixture_quality === "string"
      ? response.debug.fixture_quality
      : null) ||
    "DATA_MISSING";

  const competition =
    card?.competition?.name ||
    (typeof response.entities?.league === "string"
      ? response.entities.league
      : null) ||
    "DATA_MISSING";

  const logosPresent = Boolean(card?.home?.logo && card?.away?.logo);

  const rows: { label: string; value: string }[] = [
    { label: "backend_commit", value: formatDebugValue(response.backend_commit) },
    { label: "frontend_commit", value: formatDebugValue(response.frontend_commit) },
    { label: "fixture_quality", value: formatDebugValue(fixtureQuality) },
    {
      label: "best_markets.length",
      value: String(response.best_markets?.length ?? 0),
    },
    { label: "match_card_present", value: card ? "true" : "false" },
    { label: "competition", value: formatDebugValue(competition) },
    { label: "logos_present", value: logosPresent ? "true" : "false" },
  ];

  return (
    <section
      className="mt-2 rounded-xl border border-amber-500/25 bg-amber-500/[0.06] px-3 py-3"
      aria-label="DEBUG deploy snapshot"
    >
      <p className="mb-2 text-[0.7rem] font-semibold uppercase tracking-[0.08em] text-amber-400/90">
        DEBUG · deploy snapshot
      </p>
      <dl className="grid gap-1.5 font-mono text-[0.75rem] leading-relaxed">
        {rows.map(({ label, value }) => {
          const missing = value === "DATA_MISSING";
          return (
            <div key={label} className="grid grid-cols-[12.5rem_1fr] gap-2">
              <dt className="text-[#8A8A8A]">{label}:</dt>
              <dd
                className={
                  missing ? "text-amber-400/90" : "break-all text-[#ECECEC]"
                }
              >
                {value}
              </dd>
            </div>
          );
        })}
      </dl>
      {response.debug ? <DebugAuditPanel debug={response.debug} /> : null}
    </section>
  );
}

const DEBUG_ROWS: { key: keyof DebugAudit; label: string }[] = [
  { key: "fixture_found", label: "fixture_found" },
  { key: "fixture_id", label: "fixture_id" },
  { key: "fixture_quality", label: "fixture_quality" },
  { key: "fixture_resolver", label: "fixture_resolver" },
  { key: "entity_match_score", label: "entity_match_score" },
  { key: "market_generation_enabled", label: "market_generation_enabled" },
  { key: "data_source", label: "data_source" },
  { key: "markets_source", label: "markets_source" },
  { key: "market_reasoning", label: "market_reasoning" },
  { key: "fallback_used", label: "fallback_used" },
  { key: "confidence_source", label: "confidence_source" },
  { key: "corner_average", label: "corner_average" },
  { key: "goal_average", label: "goal_average" },
  { key: "xg_home", label: "xg_home" },
  { key: "xg_away", label: "xg_away" },
  { key: "form_score", label: "form_score" },
];

function formatDebugValue(value: unknown): string {
  if (value === undefined || value === null || value === "") return "DATA_MISSING";
  if (typeof value === "boolean") return value ? "true" : "false";
  return String(value);
}

function DebugAuditPanel({ debug }: { debug: DebugAudit }) {
  return (
    <Details title="DEBUG · auditoria completa" defaultOpen={false}>
      <dl className="mt-2 grid gap-1.5 font-mono text-[0.75rem] leading-relaxed text-[#A0A0A0]">
        {DEBUG_ROWS.map(({ key, label }) => {
          const text = formatDebugValue(debug[key]);
          const missing = text === "DATA_MISSING";
          return (
            <div key={key} className="grid grid-cols-[11rem_1fr] gap-2">
              <dt className="text-[#6B6B6B]">{label}:</dt>
              <dd
                className={
                  missing ? "text-amber-400/90" : "break-all text-[#ECECEC]/85"
                }
              >
                {text}
              </dd>
            </div>
          );
        })}
      </dl>
    </Details>
  );
}
