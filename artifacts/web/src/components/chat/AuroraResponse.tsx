import { useState } from "react";
import { ChevronDownIcon, ChevronUpIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import type { CopilotResponse, MarketEntry } from "@/types/chat";

function InlineMd({ text }: { text: string }) {
  const parts: React.ReactNode[] = [];
  const regex = /\*\*([^*]+)\*\*|\*([^*]+)\*|`([^`]+)`/g;
  let lastIndex = 0;
  let match;
  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) parts.push(text.slice(lastIndex, match.index));
    if (match[1] !== undefined)
      parts.push(
        <strong key={match.index} className="font-semibold text-white/95">
          {match[1]}
        </strong>,
      );
    else if (match[2] !== undefined) parts.push(<em key={match.index}>{match[2]}</em>);
    else if (match[3] !== undefined)
      parts.push(
        <code
          key={match.index}
          className="rounded bg-white/10 px-1.5 py-0.5 font-mono text-[11px]"
        >
          {match[3]}
        </code>,
      );
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) parts.push(text.slice(lastIndex));
  return <>{parts}</>;
}

function MdText({ text, className }: { text: string; className?: string }) {
  return (
    <div className={cn("space-y-2.5", className)}>
      {text.split("\n").map((line, i) => {
        if (line.trim() === "---") return <hr key={i} className="my-3 border-white/10" />;
        if (!line.trim()) return <div key={i} className="h-1" />;
        return (
          <p key={i} className="text-[15px] leading-7 text-white/80">
            <InlineMd text={line} />
          </p>
        );
      })}
    </div>
  );
}

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
    <div className="border-t border-white/[0.06] pt-3">
      <button
        type="button"
        className="flex w-full items-center justify-between py-1 text-left text-sm text-white/55 hover:text-white/80"
        onClick={() => setOpen(!open)}
      >
        <span>{title}</span>
        {open ? <ChevronUpIcon size={14} /> : <ChevronDownIcon size={14} />}
      </button>
      {open && <div className="mt-2 space-y-3">{children}</div>}
    </div>
  );
}

function MarketsTable({ markets, isLiveList }: { markets: MarketEntry[]; isLiveList: boolean }) {
  if (isLiveList) {
    return (
      <ul className="space-y-2">
        {markets.map((m) => (
          <li key={m.rank} className="text-sm">
            <p className="font-medium text-white/85">{m.market}</p>
            {m.rationale && (
              <p className="mt-0.5 text-xs leading-relaxed text-white/45">{m.rationale}</p>
            )}
          </li>
        ))}
      </ul>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-white/[0.06] text-white/35">
            <th className="px-1 py-2 text-left font-medium">Mercado</th>
            <th className="px-1 py-2 text-right font-medium">Prob.</th>
            <th className="px-1 py-2 text-right font-medium">VE</th>
            <th className="px-1 py-2 text-right font-medium">Risco</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-white/[0.04]">
          {markets.map((m) => (
            <tr key={m.rank}>
              <td className="max-w-[180px] truncate px-1 py-2 text-white/80">{m.market}</td>
              <td className="px-1 py-2 text-right text-white/55">{m.probability.toFixed(0)}%</td>
              <td
                className={cn(
                  "px-1 py-2 text-right font-medium",
                  m.expected_value > 0 ? "text-emerald-400" : "text-red-400",
                )}
              >
                {m.expected_value > 0 ? "+" : ""}
                {m.expected_value.toFixed(1)}%
              </td>
              <td className="px-1 py-2 text-right text-white/45">
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
    <div className="w-full max-w-none space-y-4">
      {metaBits.length > 0 && (
        <p className="text-xs text-white/40">{metaBits.join(" · ")}</p>
      )}

      {showRec && (
        <p
          className={cn(
            "text-[15px] leading-7",
            response.bankroll_recommendation.no_bet
              ? "text-amber-200/85"
              : "font-medium text-white/90",
          )}
        >
          <InlineMd text={response.final_recommendation} />
        </p>
      )}

      <MdText text={response.executive_summary} />

      {(response.confidence.score > 0 ||
        !response.bankroll_recommendation.no_bet ||
        hasMarkets ||
        hasFactors ||
        hasNotes ||
        hasHistory) && (
        <Details title="Detalhes da análise" defaultOpen={hasMarkets && response.intent === "analyze_match"}>
          {response.confidence.score > 0 && (
            <p className="text-sm text-white/55">
              Confiança{" "}
              <span className="text-white/85">{response.confidence.score.toFixed(1)}/10</span>
              {" · "}
              {CONF_PT[response.confidence.label] ?? response.confidence.label}
              {" · Risco "}
              {RISK_PT[response.risk.level] ?? response.risk.level}
            </p>
          )}

          {!response.bankroll_recommendation.no_bet && (
            <p className="text-sm text-white/55">
              Stake sugerida:{" "}
              <span className="text-white/85">
                {response.bankroll_recommendation.recommended_stake_pct.toFixed(1)}%
              </span>{" "}
              da banca ({response.bankroll_recommendation.method})
            </p>
          )}

          {hasMarkets && (
            <MarketsTable
              markets={response.best_markets}
              isLiveList={response.intent === "live_opportunities"}
            />
          )}

          {hasFactors && (
            <div className="grid gap-3 sm:grid-cols-2">
              {response.positive_factors.length > 0 && (
                <ul className="space-y-1.5">
                  <li className="text-[11px] font-medium uppercase tracking-wide text-white/35">
                    A favor
                  </li>
                  {response.positive_factors.map((f, i) => (
                    <li key={i} className="text-xs leading-relaxed text-white/60">
                      <InlineMd text={f} />
                    </li>
                  ))}
                </ul>
              )}
              {response.negative_factors.length > 0 && (
                <ul className="space-y-1.5">
                  <li className="text-[11px] font-medium uppercase tracking-wide text-white/35">
                    Atenção
                  </li>
                  {response.negative_factors.map((f, i) => (
                    <li key={i} className="text-xs leading-relaxed text-white/60">
                      <InlineMd text={f} />
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {hasNotes && (
            <ul className="space-y-1.5">
              {response.knowledge_notes.map((n, i) => (
                <li key={i} className="text-xs leading-relaxed text-white/50">
                  <InlineMd text={n} />
                </li>
              ))}
            </ul>
          )}

          {hasHistory && (
            <ul className="space-y-1.5">
              {response.historical_references.map((r, i) => (
                <li key={i} className="text-xs leading-relaxed text-white/50">
                  <InlineMd text={r} />
                </li>
              ))}
            </ul>
          )}
        </Details>
      )}
    </div>
  );
}
