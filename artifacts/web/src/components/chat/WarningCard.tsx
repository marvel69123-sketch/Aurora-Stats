import { AlertTriangleIcon } from "lucide-react";
import { cn } from "@/lib/utils";

type WarningVariant = "warning" | "error" | "info";

const VARIANT_STYLES: Record<
  WarningVariant,
  { wrap: string; icon: string; title: string; body: string }
> = {
  warning: {
    wrap: "border-amber-400/20 bg-amber-400/[0.06]",
    icon: "text-amber-400/90",
    title: "text-[#ECECEC]",
    body: "text-[#A0A0A0]",
  },
  error: {
    wrap: "border-rose-400/20 bg-rose-400/[0.06]",
    icon: "text-rose-300/90",
    title: "text-[#ECECEC]",
    body: "text-[#A0A0A0]",
  },
  info: {
    wrap: "border-white/[0.08] bg-white/[0.03]",
    icon: "text-[#A0A0A0]",
    title: "text-[#ECECEC]",
    body: "text-[#A0A0A0]",
  },
};

interface WarningCardProps {
  variant?: WarningVariant;
  title: string;
  description?: string;
  className?: string;
}

/** Minimal ChatGPT-style status card — no analysis chrome. */
export function WarningCard({
  variant = "warning",
  title,
  description,
  className,
}: WarningCardProps) {
  const styles = VARIANT_STYLES[variant];
  return (
    <aside
      role="status"
      aria-live="polite"
      className={cn(
        "flex gap-3.5 rounded-2xl border px-4 py-4 sm:px-5",
        styles.wrap,
        className,
      )}
    >
      <AlertTriangleIcon
        className={cn("mt-0.5 size-[1.125rem] shrink-0", styles.icon)}
        aria-hidden
      />
      <div className="min-w-0 space-y-1.5">
        <p
          className={cn(
            "text-[0.9375rem] font-medium leading-snug tracking-[0.01em]",
            styles.title,
          )}
        >
          {title}
        </p>
        {description ? (
          <p className={cn("text-[0.875rem] leading-[1.65]", styles.body)}>
            {description}
          </p>
        ) : null}
      </div>
    </aside>
  );
}
