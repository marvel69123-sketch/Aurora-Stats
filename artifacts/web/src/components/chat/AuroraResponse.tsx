import { useState } from "react";
import { ChevronDownIcon, ChevronUpIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import type { CopilotResponse, DebugAudit, MarketEntry } from "@/types/chat";
import { InsightBadgeRow, type InsightBadgeKind } from "./InsightBadge";
import { Markdown, MarkdownInline } from "./Markdown";
import { MatchHeader, canRenderMatchHeader } from "./MatchHeader";
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
  if (quality === "INVALID") return true;
  if (status === "NOT_FOUND" || status === "FICTIONAL") return true;
  if (response.entities?.entity_invalid === true) return true;
  // fixture_found=false covers INVALID paths; skip PARTIAL (different UX)
  if (quality === "PARTIAL" || status === "PARTIAL") return false;
  const found =
    typeof response.fixture_found === "boolean"
      ? response.fixture_found
      : typeof response.entities?.fixture_found === "boolean"
        ? (response.entities.fixture_found as boolean)
        : null;
  return found === false;
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
  insufficient: "muito baixa",
  insuficiente: "muito baixa",
  "muito baixa": "muito baixa",
  unavailable: "indisponível",
  indisponível: "indisponível",
  indisponivel: "indisponível",
};

function deriveBadges(response: CopilotResponse): InsightBadgeKind[] {
  // Social / help chrome: never show analysis badges
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
  if (response.intent !== "analyze_match" && response.intent !== "live_opportunities") {
    // Follow-ups: only high-risk / no-bet caution, never REGRA DE OURO spam
    const kinds: InsightBadgeKind[] = [];
    if (response.risk.level === "High") kinds.push("high_risk");
    else if (response.bankroll_recommendation.no_bet) kinds.push("caution");
    return kinds;
  }

  const kinds: InsightBadgeKind[] = [];
  const riskHigh = response.risk.level === "High";
  const noBet = response.bankroll_recommendation.no_bet;
  const strong =
    response.confidence.label === "strong" || response.confidence.score >= 7.5;
  const moderate =
    response.confidence.label === "moderate" ||
    response.confidence.label === "adequate" ||
    (response.confidence.score >= 5 && response.confidence.score < 7.5);

  if (riskHigh) kinds.push("high_risk");
  else if (noBet) kinds.push("caution");
  else if (strong) kinds.push("opportunity");
  else if (moderate) kinds.push("caution");

  return [...new Set(kinds)].slice(0, 1); // max one badge
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
      className="border-t border-white/[0.07] pt-3"
      open={open}
      onToggle={(e) => {
        const next = e.currentTarget.open;
        if (next !== open) setOpen(next);
      }}
    >
      <summary className="flex w-full cursor-pointer list-none items-center justify-between py-2 text-left text-sm text-[#A0A0A0] transition-colors hover:text-[#ECECEC] [&::-webkit-details-marker]:hidden">
        <span className="font-medium tracking-wide">{title}</span>
        {open ? <ChevronUpIcon size={15} /> : <ChevronDownIcon size={15} />}
      </summary>
      {open && <div className="mt-3.5 space-y-5">{children}</div>}
    </details>
  );
}

function MarketsTable({ markets, isLiveList }: { markets: MarketEntry[]; isLiveList: boolean }) {
  if (isLiveList) {
    return (
      <ul className="space-y-2.5">
        {markets.map((m) => (
          <li key={m.rank}>
            <p className="text-[0.9375rem] font-medium leading-snug text-[#ECECEC]">{m.market}</p>
            {m.rationale && (
              <p className="mt-1 text-[0.8125rem] leading-[1.65] text-[#A0A0A0]">
                {m.rationale}
              </p>
            )}
          </li>
        ))}
      </ul>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-white/[0.06]">
      <table className="w-full text-[0.8125rem]">
        <thead>
          <tr className="border-b border-white/[0.06] bg-white/[0.02] text-white/40">
            <th className="px-3 py-2.5 text-left font-medium">Mercado</th>
            <th className="px-3 py-2.5 text-right font-medium">Prob.</th>
            <th className="px-3 py-2.5 text-right font-medium">VE</th>
            <th className="px-3 py-2.5 text-right font-medium">Risco</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/[0.04]">
          {markets.map((m) => (
            <tr key={m.rank} className="hover:bg-white/[0.02]">
              <td className="max-w-[220px] truncate px-3 py-2.5 text-[#ECECEC]/85">{m.market}</td>
              <td className="px-3 py-2.5 text-right text-[#A0A0A0]">
                {m.probability.toFixed(0)}%
              </td>
              <td
                className={cn(
                  "px-3 py-2.5 text-right font-medium",
                  m.expected_value > 0 ? "text-emerald-400" : "text-rose-400",
                )}
              >
                {m.expected_value > 0 ? "+" : ""}
                {m.expected_value.toFixed(1)}%
              </td>
              <td className="px-3 py-2.5 text-right text-[#A0A0A0]">
                {RISK_PT[m.risk] ||
                  (/^unknown$/i.test(m.risk) ? "—" : m.risk)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const INTERESTING_MARKET_RE =
  /gol|btts|ambos|escanteio|canto|1x2|vit[oó]r|win|empate|vencedor|over|under/i;

const TECH_FACTOR_RE =
  /\d+[.,]?\d*\s*\/\s*10|best[-_\s]?mercado|best[-_\s]?market|over_\d+|λ\s*=|ve\s*[+\-]|puxando a pontua|modo degradado|fixture oficial|precis[aã]o\s+\d|≥\s*60%/i;

function pickInterestingMarkets(markets: MarketEntry[]): MarketEntry[] {
  const filtered = markets.filter((m) => INTERESTING_MARKET_RE.test(m.market));
  return (filtered.length > 0 ? filtered : markets).slice(0, 4);
}

function publicStrengths(response: CopilotResponse): string[] {
  const meta = response.response_metadata;
  if (meta?.public_strengths?.length) {
    return meta.public_strengths.slice(0, 3);
  }
  const out: string[] = [];
  for (const f of response.positive_factors.slice(0, 6)) {
    if (TECH_FACTOR_RE.test(f)) {
      if (/escanteio|corner/i.test(f)) {
        const tip = "O histórico recente favorece atenção aos escanteios.";
        if (!out.includes(tip)) out.push(tip);
      }
      continue;
    }
    const clean = f.replace(/^•\s*/, "").trim();
    if (clean) out.push(clean);
    if (out.length >= 3) break;
  }
  return out;
}

function looksTechnicalProse(text: string): boolean {
  return /(?:\bVE\b|λ\s*=|\/\s*10|Best[-_\s]?mercado|não foi confirmada na API|over_\d+)/i.test(
    text,
  );
}

function humanRationale(text: string): string | null {
  const t = (text || "").trim();
  if (!t) return null;
  if (/(?:\bVE\b|λ\s*=|\/\s*10|Best[-_\s]?mercado|over_\d+|metodol)/i.test(t)) {
    return null;
  }
  const first = t.split(/(?<=[.!?])\s+/)[0] || t;
  return first.length > 140 ? `${first.slice(0, 137)}…` : first;
}

/** Clean ChatGPT-style Aurora reply — prose first, details collapsed. */
export function AuroraResponse({
  response,
  onRefreshMatch,
}: {
  response: CopilotResponse;
  onRefreshMatch?: () => void;
}) {
  // v3.3.3 — INVALID fixtures: minimal warning only (ChatGPT-like error state)
  if (isInvalidFixture(response)) {
    return (
      <article className="w-full max-w-none" aria-label="Confronto inválido">
        <WarningCard
          variant="warning"
          title={INVALID_FIXTURE_TITLE}
          description={INVALID_FIXTURE_HINT}
        />
      </article>
    );
  }

  const hasMarkets = response.best_markets.length > 0;
  const hasFactors =
    response.positive_factors.length > 0 || response.negative_factors.length > 0;
  const hasNotes = response.knowledge_notes.length > 0;
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

  const conclusionRaw = response.final_recommendation || "";
  const showRec =
    !isSocial &&
    isAnalysis &&
    Boolean(conclusionRaw) &&
    !conclusionRaw.startsWith("Por favor") &&
    !conclusionRaw.startsWith("Please") &&
    !looksTechnicalProse(conclusionRaw);

  const showCautionBanner =
    showRec &&
    (response.bankroll_recommendation.no_bet || response.risk.level === "High");

  const card = response.match_card ?? null;
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
  const fixtureFound =
    typeof response.fixture_found === "boolean"
      ? response.fixture_found
      : typeof response.entities?.fixture_found === "boolean"
        ? (response.entities.fixture_found as boolean)
        : null;
  const integrityBlocked =
    fixtureFound === false ||
    fixtureQuality === "INVALID" ||
    fixtureStatus === "NOT_FOUND" ||
    fixtureStatus === "FICTIONAL" ||
    response.entities?.markets_blocked === true ||
    response.entities?.entity_invalid === true;
  const showMatchHeader =
    !integrityBlocked &&
    fixtureQuality !== "PARTIAL" &&
    canRenderMatchHeader(card) &&
    fixtureStatus !== "PARTIAL";
  const predictability = showMatchHeader ? card?.predictability : undefined;
  const interesting =
    !integrityBlocked &&
    fixtureQuality !== "PARTIAL" &&
    fixtureStatus !== "PARTIAL" &&
    isAnalysis
      ? pickInterestingMarkets(response.best_markets).slice(0, 4)
      : [];
  const softPositives =
    !integrityBlocked &&
    (response.intent === "analyze_match" || response.intent === "follow_up")
      ? publicStrengths(response)
      : [];
  const metaBits: string[] = [];
  if (!showMatchHeader) {
    if (
      response.match &&
      !/^unknown$/i.test(response.match) &&
      !integrityBlocked
    ) {
      metaBits.push(`⚽ ${response.match}`);
    }
    if (response.is_live) {
      metaBits.push(
        response.minute != null ? `Ao vivo ${response.minute}'` : "Ao vivo",
      );
    } else if (response.status && response.intent === "analyze_match") {
      if (
        !/^not\s*started$/i.test(response.status) &&
        !/^(unknown|n\/?a|NOT_FOUND|FICTIONAL|PARTIAL|INVALID)$/i.test(
          response.status,
        )
      ) {
        metaBits.push(response.status);
      }
    }
  }

  return (
    <article className="w-full max-w-none space-y-5">
      <InsightBadgeRow kinds={badges} className="mb-0.5" />

      {showMatchHeader && card ? (
        <MatchHeader card={card} onRefresh={onRefreshMatch} />
      ) : metaBits.length > 0 ? (
        <header className="-mt-1" aria-label="Partida">
          <p className="text-[0.9375rem] font-medium leading-relaxed tracking-wide text-[#ECECEC]">
            {metaBits[0]}
          </p>
          {metaBits.length > 1 && (
            <p className="mt-0.5 text-[0.8125rem] leading-relaxed text-[#A0A0A0]">
              {metaBits.slice(1).join(" · ")}
            </p>
          )}
        </header>
      ) : null}

      <section className="pt-0.5" aria-label="Resumo">
        <Markdown text={response.executive_summary} />
      </section>

      {predictability ? (
        <section
          className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-4 py-3"
          aria-label="Previsibilidade"
        >
          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#A0A0A0]">
            {predictability.label}
          </p>
          <p className="mt-1.5 text-[0.875rem] leading-[1.65] text-[#ECECEC]/90">
            {predictability.summary}
          </p>
        </section>
      ) : null}

      {softPositives.length > 0 && (
        <section aria-label="Pontos fortes">
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-[#A0A0A0]">
            Pontos que se destacam
          </p>
          <ul className="space-y-1.5">
            {softPositives.map((f, i) => (
              <li key={i} className="text-[0.875rem] leading-[1.65] text-[#ECECEC]/85">
                • <MarkdownInline text={f} />
              </li>
            ))}
          </ul>
        </section>
      )}

      {interesting.length > 0 && (
        <section aria-label="Mercados interessantes">
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-[#A0A0A0]">
            {response.is_live || (showMatchHeader && card?.is_live)
              ? "Mercados neste momento"
              : "Mercados interessantes"}
          </p>
          <ul className="space-y-2.5">
            {interesting.map((m) => {
              const why = humanRationale(m.rationale);
              return (
                <li key={m.rank} className="text-[0.9375rem] leading-snug text-[#ECECEC]">
                  • {m.market}
                  {why ? (
                    <span className="mt-0.5 block text-[0.8125rem] leading-[1.65] text-[#A0A0A0]">
                      {why}
                    </span>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </section>
      )}

      {showRec && (
        <section
          className={cn(
            "text-[15px] leading-[1.8]",
            showCautionBanner
              ? "rounded-2xl border border-amber-400/20 bg-amber-400/[0.06] px-5 py-4 text-amber-100/90"
              : "text-[#ECECEC]/90",
          )}
          aria-label="Conclusão"
        >
          <MarkdownInline text={conclusionRaw} />
        </section>
      )}

      {!isSocial &&
        (response.confidence.score > 0 ||
          !response.bankroll_recommendation.no_bet ||
          hasMarkets ||
          hasFactors ||
          hasNotes ||
          hasHistory) && (
        <Details title="Detalhes da análise" defaultOpen={false}>
          {response.confidence.score > 0 && (
            <p className="text-[0.9375rem] leading-[1.7] text-[#A0A0A0]">
              Confiança{" "}
              <span className="font-medium text-[#ECECEC]">
                {response.confidence.score.toFixed(1)}/10
              </span>
              {" · "}
              {CONF_PT[response.confidence.label] ?? response.confidence.label}
              {(() => {
                const riskLabel =
                  RISK_PT[response.risk.level] ??
                  (/^unknown$/i.test(response.risk.level)
                    ? ""
                    : response.risk.level);
                return riskLabel ? ` · Risco ${riskLabel}` : "";
              })()}
            </p>
          )}

          {!response.bankroll_recommendation.no_bet && (
            <p className="text-[0.9375rem] leading-[1.7] text-[#A0A0A0]">
              Stake sugerida:{" "}
              <span className="font-medium text-[#ECECEC]">
                {response.bankroll_recommendation.recommended_stake_pct.toFixed(1)}%
              </span>{" "}
              da banca ({response.bankroll_recommendation.method})
            </p>
          )}

          {hasMarkets && (
            <section aria-label="Mercados detalhados">
              <MarketsTable
                markets={response.best_markets}
                isLiveList={response.intent === "live_opportunities"}
              />
            </section>
          )}

          {hasFactors && (
            <section className="grid gap-4 sm:grid-cols-2" aria-label="Fatores">
              {response.positive_factors.length > 0 && (
                <ul className="space-y-2">
                  <li className="text-[11px] font-semibold uppercase tracking-[0.08em] text-emerald-400/70">
                    A favor
                  </li>
                  {response.positive_factors.map((f, i) => (
                    <li key={i} className="text-[0.8125rem] leading-[1.65] text-[#ECECEC]/80">
                      <MarkdownInline text={f} />
                    </li>
                  ))}
                </ul>
              )}
              {response.negative_factors.length > 0 && (
                <ul className="space-y-2">
                  <li className="text-[11px] font-semibold uppercase tracking-[0.08em] text-amber-400/70">
                    Atenção
                  </li>
                  {response.negative_factors.map((f, i) => (
                    <li key={i} className="text-[0.8125rem] leading-[1.65] text-[#ECECEC]/80">
                      <MarkdownInline text={f} />
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}

          {hasNotes && (
            <section aria-label="Notas">
              <ul className="space-y-2">
                {response.knowledge_notes.map((n, i) => (
                  <li key={i} className="text-[0.8125rem] leading-[1.65] text-[#A0A0A0]">
                    <MarkdownInline text={n} />
                  </li>
                ))}
              </ul>
            </section>
          )}

          {hasHistory && (
            <section aria-label="Histórico">
              <ul className="space-y-2">
                {response.historical_references.map((r, i) => (
                  <li key={i} className="text-[0.8125rem] leading-[1.65] text-[#A0A0A0]">
                    <MarkdownInline text={r} />
                  </li>
                ))}
              </ul>
            </section>
          )}
        </Details>
      )}

      {response.debug ? <DebugAuditPanel debug={response.debug} /> : null}
    </article>
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
    <Details title="DEBUG · auditoria" defaultOpen>
      <dl className="grid gap-1.5 font-mono text-[0.75rem] leading-relaxed text-[#A0A0A0]">
        {DEBUG_ROWS.map(({ key, label }) => {
          const raw = debug[key];
          const text = formatDebugValue(raw);
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
