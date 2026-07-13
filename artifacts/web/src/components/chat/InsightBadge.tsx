import { cn } from "@/lib/utils";

export type InsightBadgeKind = "golden_rule" | "alert" | "risk";

const BADGE_META: Record<
  InsightBadgeKind,
  { label: string; className: string }
> = {
  golden_rule: {
    label: "REGRA DE OURO",
    className:
      "border-amber-400/35 bg-amber-400/[0.12] text-amber-200/95",
  },
  alert: {
    label: "ALERTA",
    className: "border-rose-400/35 bg-rose-500/[0.12] text-rose-200/95",
  },
  risk: {
    label: "GESTÃO DE RISCO",
    className: "border-sky-400/35 bg-sky-500/[0.12] text-sky-200/95",
  },
};

interface InsightBadgeProps {
  kind: InsightBadgeKind;
  className?: string;
}

/** Visual insight chip for Aurora analysis responses. */
export function InsightBadge({ kind, className }: InsightBadgeProps) {
  const meta = BADGE_META[kind];
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2 py-0.5",
        "text-[10px] font-semibold tracking-[0.08em]",
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
    <nav className={cn("flex flex-wrap gap-1.5", className)} aria-label="Insights">
      {kinds.map((kind) => (
        <InsightBadge key={kind} kind={kind} />
      ))}
    </nav>
  );
}
