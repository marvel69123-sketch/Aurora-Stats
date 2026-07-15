import { useEffect, useRef } from "react";
import { MessageBubble } from "./MessageBubble";
import { ChatInput } from "./ChatInput";
import { AuroraAvatar } from "./AuroraAvatar";
import type { LiveFixtureCache, LiveStatsSnapshot, Session } from "@/types/chat";

interface ChatWindowProps {
  session: Session | null;
  loading: boolean;
  avatarUrl: string | null;
  onSend: (text: string) => void;
  onRefreshLiveMatch?: (messageId: string) => void;
  onLockLiveContext?: (
    messageId: string,
    cache: LiveFixtureCache,
    stats?: LiveStatsSnapshot,
  ) => void;
}

const STARTERS = [
  { label: "Analisar partida", text: "Analisar Arsenal x Chelsea" },
  {
    label: "Ao vivo",
    text: "Melhores oportunidades ao vivo",
    hint: "Sinais em partidas correndo agora, com foco em valor.",
  },
  { label: "Banca", text: "Revisar banca" },
  { label: "Aprendizado", text: "O que a Aurora aprendeu hoje?" },
];

function EmptyState({
  onSend,
  avatarUrl,
}: {
  onSend: (text: string) => void;
  avatarUrl: string | null;
}) {
  return (
    <section
      className="flex flex-1 flex-col items-center justify-center px-6 pb-10 text-center"
      aria-label="Início"
    >
      <AuroraAvatar url={avatarUrl} size="xl" className="mb-8" />
      <h1 className="mb-3.5 font-display text-[1.75rem] font-semibold tracking-[-0.03em] text-[#ECECEC] md:text-[2rem]">
        Aurora
      </h1>
      <p className="mb-11 max-w-xl text-[0.9375rem] leading-[1.7] text-[#A0A0A0]">
        Como posso ajudar nas análises de hoje?
      </p>
      <nav
        className="aurora-chat-column grid w-full grid-cols-1 gap-3 px-0 sm:grid-cols-2"
        aria-label="Sugestões"
      >
        {STARTERS.map((p) => (
          <button
            key={p.text}
            type="button"
            onClick={() => onSend(p.text)}
            className="rounded-2xl border border-white/[0.08] bg-[#1b1b1d]/80 px-3.5 py-3.5 text-left transition-colors hover:bg-white/[0.03] hover:border-white/[0.10]"
          >
            <p className="text-[0.9375rem] font-medium leading-snug text-[#ECECEC]/92">
              {p.label}
            </p>
            <p className="mt-1.5 text-[0.8125rem] leading-relaxed text-[#A0A0A0]">
              {p.text}
            </p>
            {"hint" in p && p.hint ? (
              <p className="mt-1.5 text-[0.75rem] leading-relaxed text-[#A0A0A0]/80">
                {p.hint}
              </p>
            ) : null}
          </button>
        ))}
      </nav>
    </section>
  );
}

export function ChatWindow({
  session,
  loading,
  avatarUrl,
  onSend,
  onRefreshLiveMatch,
  onLockLiveContext,
}: ChatWindowProps) {
  const scrollRef = useRef<HTMLElement>(null);
  const messages = session?.messages ?? [];
  const isEmpty = messages.length === 0;

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [messages.length, loading]);

  return (
    <section
      className="flex min-h-0 flex-1 flex-col bg-[#0f0f0f]"
      aria-label="Conversa"
    >
      <section
        ref={scrollRef}
        className="flex-1 overflow-y-auto"
        aria-label={isEmpty ? undefined : "Mensagens"}
      >
        {isEmpty ? (
          <EmptyState onSend={onSend} avatarUrl={avatarUrl} />
        ) : (
          <section className="aurora-chat-column mx-auto w-full max-w-3xl space-y-12 px-3 py-8 sm:space-y-14 sm:px-5 md:px-6 md:py-12">
            {messages.map((msg) => (
              <MessageBubble
                key={msg.id}
                message={msg}
                avatarUrl={avatarUrl}
                onRefreshMatch={
                  msg.response?.match_card?.is_live && onRefreshLiveMatch
                    ? () => onRefreshLiveMatch(msg.id)
                    : undefined
                }
                onLiveContextLock={
                  onLockLiveContext
                    ? (cache, stats) => onLockLiveContext(msg.id, cache, stats)
                    : undefined
                }
              />
            ))}
          </section>
        )}
      </section>

      <footer className="bg-gradient-to-t from-[#0f0f0f] via-[#0f0f0f]/95 to-transparent">
        <ChatInput
          onSend={onSend}
          disabled={loading}
          sessionId={session?.id ?? null}
        />
      </footer>
    </section>
  );
}
