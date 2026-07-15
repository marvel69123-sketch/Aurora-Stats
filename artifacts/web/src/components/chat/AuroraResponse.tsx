import { useState } from "react";
import { ChevronDownIcon, ChevronUpIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { marketLabelPt, oneLinePt, scrubProsePt } from "@/lib/marketDisplay";
import type { CopilotResponse, DebugAudit, MarketEntry } from "@/types/chat";
import { InsightBadgeRow, type InsightBadgeKind } from "./InsightBadge";
import { MarkdownInline } from "./Markdown";
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
  /\d+[.,]?\d*\s*\/\s*10|best[-_\s]?mercado|best[-_\s]?market|over_\d+|λ\s*=|ve\s*[+\-]|puxando a pontua|puxando a nota|modo degradado|fixture oficial|precis[aã]o\s+\d|≥\s*60%|api[-_\s]?football|data_completeness|market_generation|category pulling|portfolio exposure/i;

const INTERESTING_MARKET_RE =
  /gol|btts|ambos|escanteio|canto|1x2|vit[oó]r|win|empate|vencedor|over|under|handicap|dnb/i;

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
 * Always try to keep at least one useful line.
 */
function compactSummary(
  text: string,
  usedIdeas: Set<string>,
  fallbackMatch: string | null,
): string {
  const out: string[] = [];
  for (const sentence of splitSentences(text)) {
    if (TECH_FACTOR_RE.test(sentence)) continue;
    if (LOW_CONF_IDEA_RE.test(sentence)) continue; // reserved for alert
    const key = ideaKey(sentence);
    if (usedIdeas.has(key)) continue;
    // Drop near-empty platitudes alone
    if (/^confronto reconhecido\.?$/i.test(sentence) && out.length === 0) {
      continue; // wait for a richer second sentence or fallback
    }
    usedIdeas.add(key);
    out.push(sentence.replace(/\s+/g, " ").trim());
    if (out.length >= 2) break;
  }
  if (out.length === 0 && fallbackMatch) {
    out.push(`Análise de ${fallbackMatch}.`);
    out.push("Dados atuais ainda são limitados.");
    usedIdeas.add("summary_fallback");
  } else if (out.length === 1 && /reconhecido/i.test(out[0])) {
    out.push("Dados atuais ainda são limitados.");
    usedIdeas.add("summary_limited");
  }
  return out.slice(0, 2).join(" ");
}

function humanBullet(raw: string): string | null {
  let t = oneLinePt((raw || "").replace(/^•\s*/, "").replace(/\*\*/g, ""), 72);
  if (!t || TECH_FACTOR_RE.test(t)) return null;
  if (LOW_CONF_IDEA_RE.test(t)) return null;
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

function pickInterestingMarkets(markets: MarketEntry[]): MarketEntry[] {
  const filtered = markets.filter((m) => INTERESTING_MARKET_RE.test(m.market));
  return (filtered.length > 0 ? filtered : markets).slice(0, 3);
}

function humanRationale(text: string, usedIdeas: Set<string>): string | null {
  const clean = oneLinePt(text || "", 90);
  if (!clean || TECH_FACTOR_RE.test(clean) || LOW_CONF_IDEA_RE.test(clean)) {
    return null;
  }
  const key = ideaKey(clean);
  if (usedIdeas.has(key)) return null;
  usedIdeas.add(key);
  return clean;
}

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
    return "Cenário de baixa confiança. Fixture ainda não confirmada.";
  }
  if (highRisk || (noBet && lowConf)) {
    return "Cenário de risco elevado. Mercados podem sofrer alterações.";
  }
  if (lowConf) {
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

function MarketsTable({ markets, isLiveList }: { markets: MarketEntry[]; isLiveList: boolean }) {
  if (isLiveList) {
    return (
      <ul className="space-y-2.5">
        {markets.map((m) => (
          <li key={m.rank}>
            <p className="text-[0.875rem] font-medium leading-snug text-[#ECECEC]">
              {marketLabelPt(m.market)}
            </p>
          </li>
        ))}
      </ul>
    );
  }

  return (
    <div className="overflow-x-auto -mx-0.5">
      <table className="w-full min-w-[280px] text-[0.8125rem]">
        <thead>
          <tr className="border-b border-white/[0.05] text-[#A0A0A0]/80">
            <th className="px-1 py-2 text-left font-medium">Mercado</th>
            <th className="px-1 py-2 text-right font-medium">Prob.</th>
            <th className="px-1 py-2 text-right font-medium">VE</th>
            <th className="px-1 py-2 text-right font-medium">Risco</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/[0.04]">
          {markets.map((m) => (
            <tr key={m.rank}>
              <td className="max-w-[11rem] truncate px-1 py-2 text-[#ECECEC]/85 sm:max-w-[220px]">
                {marketLabelPt(m.market)}
              </td>
              <td className="whitespace-nowrap px-1 py-2 text-right text-[#A0A0A0]">
                {m.probability.toFixed(0)}%
              </td>
              <td
                className={cn(
                  "whitespace-nowrap px-1 py-2 text-right font-medium",
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

/** Aurora v3.4 — product UX: opportunity > risk > details; no repeated ideas. */
export function AuroraResponse({
  response,
  onRefreshMatch,
}: {
  response: CopilotResponse;
  onRefreshMatch?: () => void;
}) {
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
  const integrityBlocked =
    fixtureQuality === "INVALID" ||
    fixtureStatus === "NOT_FOUND" ||
    fixtureStatus === "FICTIONAL" ||
    response.entities?.entity_invalid === true;

  const showMatchHeader = !integrityBlocked && canRenderMatchHeader(card);

  const matchLabel =
    response.match && !/^unknown$/i.test(response.match) ? response.match : null;

  // Alert claims low_conf first so summary never repeats it
  const alertText =
    !isSocial && isAnalysis ? decisionAlert(response) : null;
  if (alertText) usedIdeas.add("low_conf");

  const summaryText = compactSummary(
    response.executive_summary || "",
    usedIdeas,
    isAnalysis ? matchLabel : null,
  );

  const interesting =
    !integrityBlocked && isAnalysis
      ? pickInterestingMarkets(response.best_markets)
      : [];
  const showMarketsBlock = !integrityBlocked && isAnalysis;

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

  const metaBits: string[] = [];
  if (!showMatchHeader) {
    if (matchLabel && !integrityBlocked) metaBits.push(matchLabel);
    if (response.is_live) {
      metaBits.push(
        response.minute != null ? `Ao vivo ${response.minute}'` : "Ao vivo",
      );
    }
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

  return (
    <article className="w-full max-w-none space-y-6 sm:space-y-7">
      <InsightBadgeRow kinds={badges} />

      {showMatchHeader && card ? (
        <MatchHeader card={card} onRefresh={onRefreshMatch} />
      ) : metaBits.length > 0 ? (
        <header aria-label="Partida">
          <p className="text-[0.9375rem] font-medium leading-relaxed text-[#ECECEC]">
            {metaBits.join(" · ")}
          </p>
        </header>
      ) : null}

      {summaryText ? (
        <section aria-label="Resumo">
          <p className="text-[15px] leading-[1.7] text-[#ECECEC]/92">{summaryText}</p>
        </section>
      ) : null}

      {/* Oportunidade */}
      {showMarketsBlock && (
        <section
          className="rounded-xl border border-emerald-400/15 bg-emerald-400/[0.04] px-3.5 py-3"
          aria-label="Destaque"
        >
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.08em] text-emerald-300/75">
            {response.is_live || (showMatchHeader && card?.is_live)
              ? "Neste momento"
              : "Destaque"}
          </p>
          {interesting.length > 0 ? (
            <ul className="space-y-2.5">
              {interesting.map((m) => {
                const why = humanRationale(m.rationale, usedIdeas);
                return (
                  <li key={m.rank}>
                    <p className="text-[0.9rem] font-medium leading-snug text-[#ECECEC]">
                      {marketLabelPt(m.market)}
                    </p>
                    {why ? (
                      <p className="mt-0.5 text-[0.75rem] leading-relaxed text-[#A0A0A0]">
                        {why}
                      </p>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="text-[0.875rem] leading-relaxed text-[#A0A0A0]">
              Nenhum mercado se destacou neste momento.
            </p>
          )}
        </section>
      )}

      {/* Risco — um alerta */}
      {alertText ? (
        <section
          className="rounded-xl border border-amber-400/15 bg-amber-400/[0.04] px-3.5 py-2.5"
          aria-label="Alerta"
        >
          <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-amber-300/75">
            Alerta
          </p>
          <p className="mt-1 text-[0.875rem] leading-relaxed text-[#ECECEC]/90">
            {alertText}
          </p>
        </section>
      ) : null}

      {(favorBullets.length > 0 || attentionBullets.length > 0) && (
        <section
          className="grid gap-4 sm:grid-cols-2 sm:gap-6"
          aria-label="Pontos rápidos"
        >
          {favorBullets.length > 0 && (
            <div>
              <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-[#A0A0A0]">
                A favor
              </p>
              <ul className="space-y-1">
                {favorBullets.map((f, i) => (
                  <li
                    key={i}
                    className="text-[0.8125rem] leading-snug text-[#ECECEC]/88"
                  >
                    {f}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {attentionBullets.length > 0 && (
            <div>
              <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-[#A0A0A0]">
                Atenção
              </p>
              <ul className="space-y-1">
                {attentionBullets.map((f, i) => (
                  <li
                    key={i}
                    className="text-[0.8125rem] leading-snug text-[#ECECEC]/88"
                  >
                    {f}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}

      {showDetails && (
        <Details title="Ver análise completa" defaultOpen={false}>
          {response.confidence.score > 0 && (
            <p className="text-[0.8125rem] leading-relaxed text-[#A0A0A0]">
              Confiança{" "}
              <span className="text-[#ECECEC]">
                {response.confidence.score.toFixed(1)}/10
              </span>
              {" · "}
              {confLabelPt(response.confidence.label)}
              {(() => {
                const riskLabel = RISK_PT[response.risk.level] ?? "";
                return riskLabel ? ` · Risco ${riskLabel}` : "";
              })()}
            </p>
          )}

          {!response.bankroll_recommendation.no_bet && (
            <p className="text-[0.8125rem] leading-relaxed text-[#A0A0A0]">
              Stake sugerida:{" "}
              <span className="text-[#ECECEC]">
                {response.bankroll_recommendation.recommended_stake_pct.toFixed(1)}%
              </span>{" "}
              da banca
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

          {hasNotes && (
            <section aria-label="Notas">
              <ul className="space-y-1.5">
                {response.knowledge_notes.slice(0, 4).map((n, i) => (
                  <li key={i} className="text-[0.75rem] leading-relaxed text-[#A0A0A0]">
                    <MarkdownInline text={scrubProsePt(n)} />
                  </li>
                ))}
              </ul>
            </section>
          )}

          {hasHistory && (
            <section aria-label="Histórico">
              <ul className="space-y-1.5">
                {response.historical_references.slice(0, 3).map((r, i) => (
                  <li key={i} className="text-[0.75rem] leading-relaxed text-[#A0A0A0]">
                    <MarkdownInline text={scrubProsePt(r)} />
                  </li>
                ))}
              </ul>
            </section>
          )}
        </Details>
      )}

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
  if (!response.debug && !clientDebugEnabled()) return null;

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
