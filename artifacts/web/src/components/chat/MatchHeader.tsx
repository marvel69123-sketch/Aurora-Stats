import { useState } from "react";
import { cn } from "@/lib/utils";
import type { MatchCard } from "@/types/chat";

const TEAM_STOP_WORDS = new Set([
  "aurora",
  "quero",
  "saber",
  "sobre",
  "agora",
  "amanha",
  "amanhã",
  "hoje",
  "analise",
  "análise",
  "analisar",
  "analisa",
  "favor",
  "diga",
  "como",
  "esta",
  "está",
  "vivo",
  "versus",
  "contra",
  "unknown",
]);

function foldAscii(text: string): string {
  return text
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .toLowerCase()
    .trim();
}

/** True when a team name is garbage / placeholder and MatchHeader must not render. */
export function isInvalidMatchTeamName(name?: string | null): boolean {
  if (!name || !name.trim()) return true;
  const raw = name.trim();
  if (/^unknown$/i.test(raw)) return true;
  if (raw.length > 35) return true;

  const words = foldAscii(raw).split(/\s+/).filter(Boolean);
  if (words.length === 0) return true;
  if (words.length > 4) return true;
  if (words.some((w) => TEAM_STOP_WORDS.has(w))) return true;

  const compact = words.join("");
  for (const stop of TEAM_STOP_WORDS) {
    if (stop.length >= 4 && compact.includes(stop) && compact !== stop) {
      return true;
    }
  }
  return false;
}

export function canRenderMatchHeader(card: MatchCard | null | undefined): boolean {
  if (!card?.home?.name || !card?.away?.name) return false;
  if (isInvalidMatchTeamName(card.home.name)) return false;
  if (isInvalidMatchTeamName(card.away.name)) return false;
  return true;
}

function isBlankOrUnknown(value?: string | null): boolean {
  if (!value || !value.trim()) return true;
  return /^(unknown|n\/?a|null|none|undefined)$/i.test(value.trim());
}

/** Competition label: never "Unknown"; null when missing/placeholder. */
export function competitionDisplayName(name?: string | null): string | null {
  if (isBlankOrUnknown(name)) return null;
  return name!.trim();
}

function TeamCrest({
  name,
  logo,
  size = 40,
}: {
  name: string;
  logo?: string | null;
  size?: number;
}) {
  const [broken, setBroken] = useState(false);
  const initial = (name.trim().charAt(0) || "?").toUpperCase();

  if (!logo || broken) {
    return (
      <span
        className="inline-flex shrink-0 items-center justify-center rounded-full bg-white/[0.08] text-sm font-semibold text-[#ECECEC]"
        style={{ width: size, height: size }}
        aria-hidden
      >
        {initial}
      </span>
    );
  }

  return (
    <img
      src={logo}
      alt={`Escudo ${name}`}
      width={size}
      height={size}
      className="shrink-0 rounded-full bg-white/[0.04] object-contain"
      loading="lazy"
      onError={() => setBroken(true)}
    />
  );
}

function statusLine(card: MatchCard): string {
  const bits: string[] = [];
  if (card.is_live) {
    bits.push(card.minute != null ? `Ao vivo ${card.minute}'` : "Ao vivo");
  } else if (
    card.status_label &&
    !isBlankOrUnknown(card.status_label) &&
    !/^not\s*started$/i.test(card.status_label)
  ) {
    bits.push(card.status_label);
  }
  return bits.join(" · ");
}

interface MatchHeaderProps {
  card: MatchCard;
  onRefresh?: () => void;
  className?: string;
}

/** Rich match header — logos, score, competition, venue, momentum. */
export function MatchHeader({ card, onRefresh, className }: MatchHeaderProps) {
  const status = statusLine(card);
  const venueLine = [card.venue?.name, card.venue?.city]
    .filter((v) => v && !isBlankOrUnknown(v))
    .join(" · ");
  const competitionName = competitionDisplayName(card.competition?.name);
  const competitionRound =
    card.competition?.round && !isBlankOrUnknown(card.competition.round)
      ? card.competition.round
      : null;

  return (
    <header
      className={cn(
        "rounded-2xl border border-white/[0.07] bg-white/[0.03] px-4 py-4 sm:px-5",
        className,
      )}
      aria-label="Cabeçalho da partida"
    >
      {competitionName ? (
        <div className="mb-3 flex items-center gap-2 text-[0.75rem] text-[#A0A0A0]">
          {card.competition?.logo ? (
            <img
              src={card.competition.logo}
              alt=""
              width={16}
              height={16}
              className="h-4 w-4 object-contain opacity-90"
              loading="lazy"
            />
          ) : null}
          <span className="truncate tracking-wide">
            {competitionName}
            {competitionRound ? ` · ${competitionRound}` : ""}
          </span>
        </div>
      ) : (
        <p className="mb-3 text-[0.75rem] text-[#A0A0A0]">
          Competição não identificada.
        </p>
      )}

      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 flex-1 flex-col items-center gap-2 text-center">
          <TeamCrest name={card.home.name} logo={card.home.logo} />
          <p className="line-clamp-2 text-[0.8125rem] font-medium leading-snug text-[#ECECEC]">
            {card.home.name}
          </p>
        </div>

        <div className="flex shrink-0 flex-col items-center gap-1 px-1">
          {card.score ? (
            <p
              className="font-semibold tabular-nums tracking-tight text-[#ECECEC]"
              style={{ fontSize: "1.75rem", lineHeight: 1.1 }}
              aria-label={`Placar ${card.score.home} a ${card.score.away}`}
            >
              {card.score.home}
              <span className="mx-1.5 text-white/35">–</span>
              {card.score.away}
            </p>
          ) : (
            <p className="text-sm font-medium tracking-[0.2em] text-white/40">VS</p>
          )}
          {status ? (
            <p className="text-[0.6875rem] font-medium uppercase tracking-[0.06em] text-emerald-400/80">
              {status}
            </p>
          ) : null}
        </div>

        <div className="flex min-w-0 flex-1 flex-col items-center gap-2 text-center">
          <TeamCrest name={card.away.name} logo={card.away.logo} />
          <p className="line-clamp-2 text-[0.8125rem] font-medium leading-snug text-[#ECECEC]">
            {card.away.name}
          </p>
        </div>
      </div>

      {venueLine ? (
        <p className="mt-3 text-center text-[0.75rem] leading-relaxed text-[#A0A0A0]">
          {venueLine}
        </p>
      ) : null}

      {card.momentum?.label && !isBlankOrUnknown(card.momentum.label) ? (
        <div className="mt-3 flex flex-col items-center gap-1">
          <span className="rounded-md border border-white/[0.08] bg-white/[0.04] px-2.5 py-1 text-[0.6875rem] font-medium tracking-wide text-[#ECECEC]/90">
            {card.momentum.label}
          </span>
          {card.momentum.detail ? (
            <p className="max-w-md text-center text-[0.75rem] leading-relaxed text-[#A0A0A0]">
              {card.momentum.detail}
            </p>
          ) : null}
        </div>
      ) : null}

      {onRefresh && card.is_live ? (
        <div className="mt-3.5 flex justify-center">
          <button
            type="button"
            onClick={onRefresh}
            className="rounded-full border border-white/[0.10] bg-white/[0.04] px-3.5 py-1.5 text-[0.75rem] font-medium text-[#ECECEC]/90 transition-colors hover:bg-white/[0.08] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white/30"
          >
            Atualizar partida
          </button>
        </div>
      ) : null}
    </header>
  );
}
