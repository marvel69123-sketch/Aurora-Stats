import type { LiveStatsSnapshot } from "@/types/chat";

/** Live statistics table — presentation only. */
export function LiveStatsPanel({ stats }: { stats: LiveStatsSnapshot }) {
  return (
    <section
      className="rounded-xl border border-white/[0.07] bg-white/[0.025] px-3.5 py-3.5 sm:px-4"
      aria-label="Estatísticas ao vivo"
    >
      <p className="mb-3 text-[10px] font-semibold uppercase tracking-[0.08em] text-[#A0A0A0]">
        Estatísticas ao vivo
      </p>

      <div className="mb-2 grid grid-cols-[1fr_auto_1fr] items-end gap-2 px-0.5 text-[0.75rem] font-medium text-[#ECECEC]/90">
        <span className="truncate text-left">{stats.homeName}</span>
        <span className="w-28 shrink-0" aria-hidden />
        <span className="truncate text-right">{stats.awayName}</span>
      </div>

      {stats.rows.length === 0 ? (
        <p className="text-[0.8125rem] leading-relaxed text-[#A0A0A0]">
          Dados indisponíveis
        </p>
      ) : (
        <ul className="space-y-1.5">
          {stats.rows.map((row) => (
            <li
              key={row.label}
              className="grid grid-cols-[1fr_auto_1fr] items-center gap-2 border-t border-white/[0.04] pt-1.5 first:border-0 first:pt-0"
            >
              <span className="text-right text-[0.8125rem] tabular-nums text-[#ECECEC]">
                {row.home}
              </span>
              <span className="w-28 shrink-0 text-center text-[0.6875rem] text-[#A0A0A0]">
                {row.label}
              </span>
              <span className="text-left text-[0.8125rem] tabular-nums text-[#ECECEC]">
                {row.away}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
