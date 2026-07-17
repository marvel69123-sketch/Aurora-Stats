import { cn } from "@/lib/utils";

export type InsightBadgeKind = "opportunity" | "caution" | "high_risk";

const BADGE_META: Record<
  InsightBadgeKind,
  { label: string; className: string }
> = {
  opportunity: {
    label: "🟢 Oportunidade",
    className:
      "border-emerald-400/35 bg-emerald-400/[0.10] text-emerald-200/95",
  },
  caution: {
    label: "Leitura cautelosa",
    className: "border-amber-400/35 bg-amber-400/[0.10] text-amber-200/95",
  },
  high_risk: {
    label: "🔴 Risco elevado",
    className: "border-rose-400/35 bg-rose-500/[0.10] text-rose-200/95",
  },
};

interface InsightBadgeProps {
  kind: InsightBadgeKind;
  className?: string;
}

/** Soft insight chip — analysis only, never social chat. */
export function InsightBadge({ kind, className }: InsightBadgeProps) {
  const meta = BADGE_META[kind];
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2.5 py-1",
        "text-[10px] font-semibold tracking-[0.04em]",
        meta.className,
        className,
      )}
    >
      {meta.label}
    </span>
  );
}

interface InsightBadgeRowProps {
  kinds: InsightBadgeKind[];
  className?: string;
}

export function InsightBadgeRow({ kinds, className }: InsightBadgeRowProps) {
  if (kinds.length === 0) return null;
  return (
    <nav
      className={cn("flex flex-wrap items-center gap-2", className)}
      aria-label="Insights"
    >
      {kinds.map((kind) => (
        <InsightBadge key={kind} kind={kind} />
      ))}
    </nav>
  );
}
