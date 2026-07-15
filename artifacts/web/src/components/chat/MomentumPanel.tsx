import type { MatchCard } from "@/types/chat";

function foldMomentumLabel(label: string): {
  title: string;
  tone: "home" | "away" | "balance" | "extreme";
} {
  const l = label.toLowerCase();
  if (/extrema|extreme/.test(l)) {
    return {
      title: /visitante|away/.test(l)
        ? "Pressão extrema do visitante"
        : /mandante|home/.test(l)
          ? "Pressão extrema do mandante"
          : "Pressão extrema",
      tone: "extreme",
    };
  }
  if (/ritmo da partida|equil[ií]brio|balanced|neutral/.test(l)) {
    return { title: "Ritmo da partida", tone: "balance" };
  }
  if (/visitante|away/.test(l)) {
    return { title: "Pressão do visitante", tone: "away" };
  }
  if (/mandante|home/.test(l)) {
    return { title: "Pressão do mandante", tone: "home" };
  }
  return { title: label, tone: "balance" };
}

function iconFor(tone: string): string {
  if (tone === "extreme") return "🚨";
  if (tone === "balance") return "📊";
  return "🔥";
}

/** Rich momentum block — presentation only; does not change MatchHeader logic. */
export function MomentumPanel({
  momentum,
}: {
  momentum: NonNullable<MatchCard["momentum"]>;
}) {
  const { title, tone } = foldMomentumLabel(momentum.label);
  const bullets = (momentum.detail || "")
    .split(/[·•|]|\s{2,}/)
    .map((s) => s.trim())
    .filter(Boolean)
    .slice(0, 3);

  const border =
    tone === "extreme"
      ? "border-rose-400/20 bg-rose-400/[0.05]"
      : tone === "balance"
        ? "border-white/[0.07] bg-white/[0.025]"
        : "border-orange-400/15 bg-orange-400/[0.04]";

  return (
    <section
      className={`rounded-xl border px-3.5 py-3 ${border}`}
      aria-label="Momentum"
    >
      <p className="text-[0.9375rem] font-medium leading-snug text-[#ECECEC]">
        <span className="mr-1.5" aria-hidden>
          {iconFor(tone)}
        </span>
        {title}
      </p>
      {momentum.detail && bullets.length <= 1 ? (
        <p className="mt-1.5 text-[0.8125rem] leading-relaxed text-[#A0A0A0]">
          {momentum.detail}
        </p>
      ) : null}
      {bullets.length > 1 ? (
        <ul className="mt-2 space-y-1">
          {bullets.map((b, i) => (
            <li
              key={i}
              className="text-[0.8125rem] leading-snug text-[#ECECEC]/88"
            >
              • {b}
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
