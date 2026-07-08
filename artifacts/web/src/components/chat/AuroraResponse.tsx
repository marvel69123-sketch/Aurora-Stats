import { useState } from "react";
import {
  TrendingUpIcon,
  ShieldIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  ZapIcon,
  BookOpenIcon,
  BarChart3Icon,
  WalletIcon,
  AlertTriangleIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { CopilotResponse, MarketEntry } from "@/types/chat";

// ---------------------------------------------------------------------------
// Inline markdown renderer
// ---------------------------------------------------------------------------

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
        </strong>
      );
    else if (match[2] !== undefined)
      parts.push(<em key={match.index}>{match[2]}</em>);
    else if (match[3] !== undefined)
      parts.push(
        <code
          key={match.index}
          className="bg-white/10 px-1.5 py-0.5 rounded text-[11px] font-mono"
        >
          {match[3]}
        </code>
      );
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) parts.push(text.slice(lastIndex));
  return <>{parts}</>;
}

function MdText({ text, className }: { text: string; className?: string }) {
  return (
    <div className={cn("space-y-1.5", className)}>
      {text.split("\n").map((line, i) => {
        if (line.trim() === "---")
          return <hr key={i} className="border-white/10 my-2" />;
        if (!line.trim()) return <div key={i} className="h-1" />;
        return (
          <p key={i} className="text-sm leading-relaxed text-white/75">
            <InlineMd text={line} />
          </p>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Intent badge
// ---------------------------------------------------------------------------

const INTENT_META: Record<string, { label: string; color: string }> = {
  analyze_match:      { label: "Match Analysis",     color: "bg-blue-500/15 text-blue-300 border-blue-500/20" },
  live_opportunities: { label: "Live Opportunities", color: "bg-emerald-500/15 text-emerald-300 border-emerald-500/20" },
  bankroll_review:    { label: "Bankroll Review",    color: "bg-amber-500/15 text-amber-300 border-amber-500/20" },
  learning_recap:     { label: "Learning Recap",     color: "bg-purple-500/15 text-purple-300 border-purple-500/20" },
  knowledge_search:   { label: "Knowledge Search",   color: "bg-teal-500/15 text-teal-300 border-teal-500/20" },
  greeting:           { label: "Hello",              color: "bg-white/5 text-white/50 border-white/10" },
  help:               { label: "Help",               color: "bg-white/5 text-white/50 border-white/10" },
  unknown:            { label: "Aurora",             color: "bg-white/5 text-white/50 border-white/10" },
};

function IntentBadge({ intent }: { intent: string }) {
  const meta = INTENT_META[intent] ?? INTENT_META.unknown;
  return (
    <span
      className={cn(
        "inline-flex items-center text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full border",
        meta.color
      )}
    >
      {meta.label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Final recommendation box
// ---------------------------------------------------------------------------

function FinalRec({ text, noBet }: { text: string; noBet: boolean }) {
  if (!text || text.startsWith("Please provide")) return null;

  if (noBet) {
    return (
      <div className="rounded-xl border border-amber-500/20 bg-amber-500/[0.07] px-4 py-3 flex gap-3 items-start">
        <AlertTriangleIcon size={15} className="text-amber-400 flex-shrink-0 mt-0.5" />
        <p className="text-sm text-amber-200/80 leading-relaxed">
          <InlineMd text={text} />
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-emerald-500/25 bg-emerald-500/[0.08] px-4 py-3 flex gap-3 items-start">
      <TrendingUpIcon size={15} className="text-emerald-400 flex-shrink-0 mt-0.5" />
      <p className="text-sm text-white/90 leading-relaxed font-medium">
        <InlineMd text={text} />
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Best Markets table
// ---------------------------------------------------------------------------

function RiskPill({ risk }: { risk: string }) {
  const map: Record<string, string> = {
    Low:     "bg-emerald-500/15 text-emerald-300",
    Medium:  "bg-amber-500/15 text-amber-300",
    High:    "bg-red-500/15 text-red-300",
    Unknown: "bg-white/5 text-white/30",
  };
  return (
    <span className={cn("text-[10px] font-semibold px-2 py-0.5 rounded-full", map[risk] ?? map.Unknown)}>
      {risk}
    </span>
  );
}

function MarketsSection({ markets, intent }: { markets: MarketEntry[]; intent: string }) {
  const [expanded, setExpanded] = useState(intent === "analyze_match");

  if (markets.length === 0) return null;

  const isFixtureList = intent === "live_opportunities";

  return (
    <div className="rounded-xl border border-white/8 bg-white/[0.02] overflow-hidden">
      <button
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-white/5 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-2">
          <BarChart3Icon size={13} className="text-white/40" />
          <span className="text-xs font-semibold text-white/70 uppercase tracking-wider">
            {isFixtureList ? "Live Matches" : "Best Markets"}
          </span>
          <span className="text-[10px] text-white/30 bg-white/5 px-1.5 py-0.5 rounded-full">
            {markets.length}
          </span>
        </div>
        {expanded ? (
          <ChevronUpIcon size={13} className="text-white/30" />
        ) : (
          <ChevronDownIcon size={13} className="text-white/30" />
        )}
      </button>

      {expanded && (
        <div className="border-t border-white/8">
          {isFixtureList ? (
            <div className="divide-y divide-white/5">
              {markets.map((m) => (
                <div key={m.rank} className="px-4 py-3">
                  <p className="text-sm font-medium text-white/90">{m.market}</p>
                  <p className="text-xs text-white/40 mt-0.5 leading-relaxed">{m.rationale}</p>
                </div>
              ))}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-white/5">
                    <th className="text-left px-4 py-2.5 text-white/30 font-medium">#</th>
                    <th className="text-left px-2 py-2.5 text-white/30 font-medium">Market</th>
                    <th className="text-right px-2 py-2.5 text-white/30 font-medium">Prob.</th>
                    <th className="text-right px-2 py-2.5 text-white/30 font-medium">EV</th>
                    <th className="text-right px-2 py-2.5 text-white/30 font-medium">Conf.</th>
                    <th className="text-right px-4 py-2.5 text-white/30 font-medium">Risk</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/[0.04]">
                  {markets.map((m) => (
                    <MarketRow key={m.rank} market={m} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function MarketRow({ market: m }: { market: MarketEntry }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <>
      <tr
        className={cn(
          "hover:bg-white/[0.03] transition-colors cursor-pointer",
          m.rank === 1 && "bg-emerald-500/[0.04]"
        )}
        onClick={() => setExpanded(!expanded)}
      >
        <td className="px-4 py-2.5 text-white/30">{m.rank}</td>
        <td className="px-2 py-2.5 font-medium text-white/85 max-w-[140px]">
          <div className="truncate">{m.market}</div>
        </td>
        <td className="px-2 py-2.5 text-right text-white/60">{m.probability.toFixed(0)}%</td>
        <td className={cn("px-2 py-2.5 text-right font-semibold", m.expected_value > 0 ? "text-emerald-400" : "text-red-400")}>
          {m.expected_value > 0 ? "+" : ""}{m.expected_value.toFixed(1)}%
        </td>
        <td className="px-2 py-2.5 text-right text-white/60">{m.confidence.toFixed(1)}</td>
        <td className="px-4 py-2.5 text-right">
          <RiskPill risk={m.risk} />
        </td>
      </tr>
      {expanded && m.rationale && (
        <tr className="bg-white/[0.02]">
          <td colSpan={6} className="px-4 py-2.5">
            <p className="text-[11px] text-white/45 leading-relaxed">{m.rationale}</p>
          </td>
        </tr>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Confidence + Risk cards
// ---------------------------------------------------------------------------

function ConfidenceBar({ score }: { score: number }) {
  const pct = Math.min(100, (score / 10) * 100);
  const color =
    score >= 8 ? "bg-emerald-500" : score >= 6 ? "bg-blue-500" : score >= 4 ? "bg-amber-500" : "bg-red-500";
  return (
    <div className="h-1.5 bg-white/10 rounded-full overflow-hidden">
      <div
        className={cn("h-full rounded-full transition-all", color)}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

function ConfidenceCard({ confidence }: { confidence: CopilotResponse["confidence"] }) {
  return (
    <div className="rounded-xl border border-white/8 bg-white/[0.02] px-4 py-3 space-y-2">
      <div className="flex items-center gap-2">
        <ShieldIcon size={12} className="text-white/35" />
        <span className="text-[10px] font-semibold text-white/40 uppercase tracking-wider">Confidence</span>
      </div>
      <div>
        <div className="flex items-baseline gap-1.5">
          <span className="text-2xl font-bold text-white/90">{confidence.score.toFixed(1)}</span>
          <span className="text-xs text-white/30">/10</span>
          <span className={cn(
            "text-xs font-medium ml-1 capitalize",
            confidence.label === "strong" ? "text-emerald-400" :
            confidence.label === "moderate" ? "text-blue-400" :
            confidence.label === "adequate" ? "text-amber-400" : "text-red-400"
          )}>
            {confidence.label}
          </span>
        </div>
        <ConfidenceBar score={confidence.score} />
      </div>
      {confidence.data_sources.length > 0 && (
        <div className="flex flex-wrap gap-1 pt-0.5">
          {confidence.data_sources.map((src, i) => (
            <span key={i} className="text-[10px] text-white/30 bg-white/5 px-1.5 py-0.5 rounded">
              {src}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function RiskCard({ risk }: { risk: CopilotResponse["risk"] }) {
  const riskColor =
    risk.level === "Low" ? "text-emerald-400" :
    risk.level === "Medium" ? "text-amber-400" :
    risk.level === "High" ? "text-red-400" : "text-white/40";

  return (
    <div className="rounded-xl border border-white/8 bg-white/[0.02] px-4 py-3 space-y-2">
      <div className="flex items-center gap-2">
        <AlertTriangleIcon size={12} className="text-white/35" />
        <span className="text-[10px] font-semibold text-white/40 uppercase tracking-wider">Risk</span>
      </div>
      <div>
        <span className={cn("text-xl font-bold", riskColor)}>{risk.level}</span>
      </div>
      {risk.flags.length > 0 ? (
        <div className="space-y-1">
          {risk.flags.slice(0, 2).map((flag, i) => (
            <p key={i} className="text-[11px] text-white/40 leading-snug line-clamp-2">
              <InlineMd text={flag} />
            </p>
          ))}
        </div>
      ) : (
        <p className="text-[11px] text-white/30">No critical risk flags.</p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Bankroll
// ---------------------------------------------------------------------------

function BankrollCard({ br }: { br: CopilotResponse["bankroll_recommendation"] }) {
  const examples = Object.entries(br.examples);

  return (
    <div className="rounded-xl border border-blue-500/15 bg-blue-500/[0.05] px-4 py-3 space-y-2.5">
      <div className="flex items-center gap-2">
        <WalletIcon size={12} className="text-blue-400/70" />
        <span className="text-[10px] font-semibold text-blue-400/60 uppercase tracking-wider">
          Bankroll Recommendation
        </span>
      </div>
      <div className="flex items-baseline gap-1.5">
        <span className="text-2xl font-bold text-white/90">{br.recommended_stake_pct.toFixed(1)}%</span>
        <span className="text-xs text-white/40">of bankroll</span>
        <span className="text-[10px] text-blue-400/50 ml-1">({br.method})</span>
      </div>
      {examples.length > 0 && (
        <div className="flex gap-3 flex-wrap">
          {examples.map(([bankroll, stake]) => (
            <div key={bankroll} className="text-[11px]">
              <span className="text-white/30">£{parseInt(bankroll).toLocaleString()} →</span>{" "}
              <span className="font-semibold text-white/70">£{stake}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Factors
// ---------------------------------------------------------------------------

function FactorsSection({ pos, neg }: { pos: string[]; neg: string[] }) {
  const [open, setOpen] = useState(false);
  if (pos.length === 0 && neg.length === 0) return null;

  return (
    <div className="rounded-xl border border-white/8 bg-white/[0.02] overflow-hidden">
      <button
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-white/5 transition-colors"
        onClick={() => setOpen(!open)}
      >
        <div className="flex items-center gap-2">
          <ZapIcon size={13} className="text-white/40" />
          <span className="text-xs font-semibold text-white/70 uppercase tracking-wider">Factors</span>
          <span className="text-[10px] text-white/30 bg-white/5 px-1.5 py-0.5 rounded-full">
            {pos.length}+ / {neg.length}-
          </span>
        </div>
        {open ? <ChevronUpIcon size={13} className="text-white/30" /> : <ChevronDownIcon size={13} className="text-white/30" />}
      </button>

      {open && (
        <div className="border-t border-white/8 grid grid-cols-1 sm:grid-cols-2 divide-y sm:divide-y-0 sm:divide-x divide-white/5">
          {pos.length > 0 && (
            <div className="px-4 py-3 space-y-1.5">
              <p className="text-[10px] font-semibold text-emerald-400/60 uppercase tracking-wider mb-2">
                Positive
              </p>
              {pos.map((f, i) => (
                <div key={i} className="flex gap-1.5">
                  <CheckCircleIcon size={11} className="text-emerald-500/50 flex-shrink-0 mt-0.5" />
                  <p className="text-[11px] text-white/55 leading-snug">
                    <InlineMd text={f} />
                  </p>
                </div>
              ))}
            </div>
          )}
          {neg.length > 0 && (
            <div className="px-4 py-3 space-y-1.5">
              <p className="text-[10px] font-semibold text-amber-400/60 uppercase tracking-wider mb-2">
                Negative
              </p>
              {neg.map((f, i) => (
                <div key={i} className="flex gap-1.5">
                  <XCircleIcon size={11} className="text-amber-500/40 flex-shrink-0 mt-0.5" />
                  <p className="text-[11px] text-white/55 leading-snug">
                    <InlineMd text={f} />
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Knowledge Notes
// ---------------------------------------------------------------------------

function KnowledgeNotes({ notes }: { notes: string[] }) {
  const [open, setOpen] = useState(false);
  if (notes.length === 0) return null;

  return (
    <div className="rounded-xl border border-white/8 bg-white/[0.02] overflow-hidden">
      <button
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-white/5 transition-colors"
        onClick={() => setOpen(!open)}
      >
        <div className="flex items-center gap-2">
          <BookOpenIcon size={13} className="text-white/40" />
          <span className="text-xs font-semibold text-white/70 uppercase tracking-wider">
            Knowledge Rules
          </span>
          <span className="text-[10px] text-white/30 bg-white/5 px-1.5 py-0.5 rounded-full">
            {notes.length}
          </span>
        </div>
        {open ? <ChevronUpIcon size={13} className="text-white/30" /> : <ChevronDownIcon size={13} className="text-white/30" />}
      </button>

      {open && (
        <div className="border-t border-white/8 px-4 py-3 space-y-2.5 max-h-64 overflow-y-auto">
          {notes.map((note, i) => (
            <p key={i} className="text-[11px] text-white/45 leading-snug">
              <InlineMd text={note} />
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Historical References
// ---------------------------------------------------------------------------

function HistoricalSection({ refs }: { refs: string[] }) {
  const [open, setOpen] = useState(false);
  if (refs.length === 0) return null;

  return (
    <div className="rounded-xl border border-white/8 bg-white/[0.02] overflow-hidden">
      <button
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-white/5 transition-colors"
        onClick={() => setOpen(!open)}
      >
        <div className="flex items-center gap-2">
          <ClockIcon size={13} className="text-white/40" />
          <span className="text-xs font-semibold text-white/70 uppercase tracking-wider">
            Historical References
          </span>
          <span className="text-[10px] text-white/30 bg-white/5 px-1.5 py-0.5 rounded-full">
            {refs.length}
          </span>
        </div>
        {open ? <ChevronUpIcon size={13} className="text-white/30" /> : <ChevronDownIcon size={13} className="text-white/30" />}
      </button>

      {open && (
        <div className="border-t border-white/8 px-4 py-3 space-y-2 max-h-48 overflow-y-auto">
          {refs.map((ref, i) => (
            <p key={i} className="text-[11px] text-white/45 leading-snug">
              <InlineMd text={ref} />
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Bankroll stats mini-grid (for bankroll_review / learning intents)
// ---------------------------------------------------------------------------

function EntityStats({ entities }: { entities: Record<string, unknown> }) {
  const stats: Array<{ key: string; label: string; format: (v: unknown) => string }> = [
    { key: "total_predictions", label: "Predictions", format: (v) => String(v) },
    { key: "wins",              label: "Wins",         format: (v) => String(v) },
    { key: "losses",            label: "Losses",       format: (v) => String(v) },
    { key: "accuracy_pct",      label: "Accuracy",     format: (v) => `${Number(v).toFixed(1)}%` },
    { key: "roi_pct",           label: "ROI",          format: (v) => `${Number(v) >= 0 ? "+" : ""}${Number(v).toFixed(1)}%` },
  ];

  const available = stats.filter((s) => entities[s.key] !== undefined && entities[s.key] !== null);
  if (available.length === 0) return null;

  return (
    <div className="grid grid-cols-3 sm:grid-cols-5 gap-2">
      {available.map(({ key, label, format }) => (
        <div key={key} className="rounded-lg bg-white/[0.04] px-3 py-2.5 text-center">
          <p className="text-[10px] text-white/30 mb-0.5">{label}</p>
          <p className="text-sm font-semibold text-white/80">{format(entities[key])}</p>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main AuroraResponse component
// ---------------------------------------------------------------------------

export function AuroraResponse({ response }: { response: CopilotResponse }) {
  const isAnalyze = response.intent === "analyze_match";
  const hasMarkets = response.best_markets.length > 0;
  const hasConfidence = response.confidence.score > 0;
  const hasBankroll = !response.bankroll_recommendation.no_bet;
  const hasFactors = response.positive_factors.length > 0 || response.negative_factors.length > 0;
  const hasStats = ["bankroll_review", "learning_recap"].includes(response.intent);

  return (
    <div className="space-y-3 w-full">
      {/* Intent badge + match header */}
      <div className="flex items-center gap-2 flex-wrap">
        <IntentBadge intent={response.intent} />
        {response.match && (
          <span className="text-sm font-semibold text-white/80">{response.match}</span>
        )}
        {response.status && (
          <span className="text-xs text-white/30">{response.status}</span>
        )}
        {response.is_live && response.minute && (
          <span className="text-[10px] font-semibold text-emerald-400 bg-emerald-400/10 px-2 py-0.5 rounded-full">
            LIVE {response.minute}'
          </span>
        )}
      </div>

      {/* Final recommendation — most prominent */}
      <FinalRec
        text={response.final_recommendation}
        noBet={response.bankroll_recommendation.no_bet}
      />

      {/* Entity stats for bankroll/learning */}
      {hasStats && <EntityStats entities={response.entities} />}

      {/* Executive summary */}
      <MdText text={response.executive_summary} />

      {/* Best markets */}
      {hasMarkets && <MarketsSection markets={response.best_markets} intent={response.intent} />}

      {/* Confidence + Risk — side by side */}
      {(isAnalyze || hasConfidence) && (
        <div className="grid grid-cols-2 gap-2">
          <ConfidenceCard confidence={response.confidence} />
          <RiskCard risk={response.risk} />
        </div>
      )}

      {/* Bankroll */}
      {hasBankroll && <BankrollCard br={response.bankroll_recommendation} />}

      {/* Factors */}
      {hasFactors && (
        <FactorsSection
          pos={response.positive_factors}
          neg={response.negative_factors}
        />
      )}

      {/* Knowledge notes */}
      {response.knowledge_notes.length > 0 && (
        <KnowledgeNotes notes={response.knowledge_notes} />
      )}

      {/* Historical references */}
      {response.historical_references.length > 0 && (
        <HistoricalSection refs={response.historical_references} />
      )}

      {/* Timestamp */}
      <p className="text-[10px] text-white/15 pt-1">
        {response.aurora_version} · {new Date(response.generated_at).toLocaleTimeString()}
      </p>
    </div>
  );
}
