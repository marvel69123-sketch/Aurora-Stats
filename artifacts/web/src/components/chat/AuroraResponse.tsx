import { useState } from "react";
import { ChevronDownIcon, ChevronUpIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import type { CopilotResponse, MarketEntry } from "@/types/chat";
import { InsightBadgeRow, type InsightBadgeKind } from "./InsightBadge";
import { Markdown, MarkdownInline } from "./Markdown";

const RISK_PT: Record<string, string> = {
  Low: "Baixo",
  Medium: "Médio",
  High: "Alto",
  Unknown: "—",
};

const CONF_PT: Record<string, string> = {
  strong: "forte",
  moderate: "moderada",
  adequate: "adequada",
  weak: "fraca",
  insufficient: "insuficiente",
};

function deriveBadges(response: CopilotResponse): InsightBadgeKind[] {
  const kinds: InsightBadgeKind[] = [];
  const riskHigh = response.risk.level === "High";
  const noBet = response.bankroll_recommendation.no_bet;
  const hasNotes = response.knowledge_notes.length > 0;
  const strong =
    response.confidence.label === "strong" || response.confidence.score >= 7.5;

  if (hasNotes || (strong && !noBet && !riskHigh)) kinds.push("golden_rule");
  if (noBet || riskHigh || response.negative_factors.length > 0) kinds.push("alert");
  if (
    !noBet ||
    response.risk.flags.length > 0 ||
    response.risk.level === "Medium" ||
    response.risk.level === "High"
  ) {
    kinds.push("risk");
  }
  return [...new Set(kinds)];
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
      <summary className="flex w-full cursor-pointer list-none items-center justify-between py-1.5 text-left text-sm text-white/50 transition-colors hover:text-white/80 [&::-webkit-details-marker]:hidden">
        <span className="font-medium tracking-wide">{title}</span>
        {open ? <ChevronUpIcon size={15} /> : <ChevronDownIcon size={15} />}
      </summary>
      {open && <div className="mt-3 space-y-4">{children}</div>}
    </details>
  );
}

function MarketsTable({ markets, isLiveList }: { markets: MarketEntry[]; isLiveList: boolean }) {
  if (isLiveList) {
    return (
      <ul className="space-y-2.5">
        {markets.map((m) => (
          <li key={m.rank}>
            <p className="text-[0.9375rem] font-medium text-white/88">{m.market}</p>
            {m.rationale && (
              <p className="mt-0.5 text-[0.8125rem] leading-relaxed text-white/45">
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
              <td className="max-w-[220px] truncate px-3 py-2.5 text-white/82">{m.market}</td>
              <td className="px-3 py-2.5 text-right text-white/55">
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
              <td className="px-3 py-2.5 text-right text-white/45">
                {RISK_PT[m.risk] ?? m.risk}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Clean ChatGPT-style Aurora reply — prose first, details collapsed. */
export function AuroraResponse({ response }: { response: CopilotResponse }) {
  const hasMarkets = response.best_markets.length > 0;
  const hasFactors =
    response.positive_factors.length > 0 || response.negative_factors.length > 0;
  const hasNotes = response.knowledge_notes.length > 0;
  const hasHistory = response.historical_references.length > 0;
  const showRec =
    response.final_recommendation &&
    !response.final_recommendation.startsWith("Por favor") &&
    !response.final_recommendation.startsWith("Please");

  const badges = deriveBadges(response);

  const metaBits: string[] = [];
  if (response.match) metaBits.push(response.match);
  if (response.is_live) {
    metaBits.push(
      response.minute != null ? `Ao vivo ${response.minute}'` : "Ao vivo",
    );
  } else if (response.status) {
    metaBits.push(response.status);
  }

  return (
    <article className="w-full max-w-none space-y-4">
      <InsightBadgeRow kinds={badges} />

      {metaBits.length > 0 && (
        <header>
          <p className="text-[0.8125rem] tracking-wide text-white/40">
            {metaBits.join(" · ")}
          </p>
        </header>
      )}

      {showRec && (
        <section
          className={cn(
            "rounded-2xl px-4 py-3 text-[15px] leading-7",
            response.bankroll_recommendation.no_bet
              ? "border border-amber-400/20 bg-amber-400/[0.06] text-amber-100/90"
              : "border border-white/[0.06] bg-white/[0.03] font-medium text-white/[0.92]",
          )}
          aria-label="Recomendação"
        >
          <MarkdownInline text={response.final_recommendation} />
        </section>
      )}

      <section aria-label="Resumo">
        <Markdown text={response.executive_summary} />
      </section>

      {(response.confidence.score > 0 ||
        !response.bankroll_recommendation.no_bet ||
        hasMarkets ||
        hasFactors ||
        hasNotes ||
        hasHistory) && (
        <Details
          title="Detalhes da análise"
          defaultOpen={hasMarkets && response.intent === "analyze_match"}
        >
          {response.confidence.score > 0 && (
            <p className="text-[0.9375rem] text-white/55">
              Confiança{" "}
              <span className="font-medium text-white/88">
                {response.confidence.score.toFixed(1)}/10
              </span>
              {" · "}
              {CONF_PT[response.confidence.label] ?? response.confidence.label}
              {" · Risco "}
              {RISK_PT[response.risk.level] ?? response.risk.level}
            </p>
          )}

          {!response.bankroll_recommendation.no_bet && (
            <p className="text-[0.9375rem] text-white/55">
              Stake sugerida:{" "}
              <span className="font-medium text-white/88">
                {response.bankroll_recommendation.recommended_stake_pct.toFixed(1)}%
              </span>{" "}
              da banca ({response.bankroll_recommendation.method})
            </p>
          )}

          {hasMarkets && (
            <section aria-label="Mercados">
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
                    <li key={i} className="text-[0.8125rem] leading-relaxed text-white/65">
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
                    <li key={i} className="text-[0.8125rem] leading-relaxed text-white/65">
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
                  <li key={i} className="text-[0.8125rem] leading-relaxed text-white/50">
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
                  <li key={i} className="text-[0.8125rem] leading-relaxed text-white/50">
                    <MarkdownInline text={r} />
                  </li>
                ))}
              </ul>
            </section>
          )}
        </Details>
      )}
    </article>
  );
}
