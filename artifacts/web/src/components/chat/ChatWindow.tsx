import { useEffect, useRef } from "react";
import { MessageBubble } from "./MessageBubble";
import { ChatInput } from "./ChatInput";
import { AuroraAvatar } from "./AuroraAvatar";
import type { Session } from "@/types/chat";

interface ChatWindowProps {
  session: Session | null;
  loading: boolean;
  avatarUrl: string | null;
  onSend: (text: string) => void;
}

const STARTERS = [
  { label: "Analisar partida", text: "Analisar Arsenal x Chelsea" },
  { label: "Ao vivo", text: "Melhores oportunidades ao vivo" },
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
      className="flex flex-1 flex-col items-center justify-center px-6 pb-8 text-center"
      aria-label="Início"
    >
      <AuroraAvatar url={avatarUrl} size="xl" className="mb-7" />
      <h1 className="mb-3 font-display text-[1.75rem] font-semibold tracking-[-0.03em] text-white/[0.94] md:text-[2rem]">
        Aurora
      </h1>
      <p className="mb-10 max-w-md text-[0.9375rem] leading-relaxed text-white/45">
        Como posso ajudar nas análises de hoje?
      </p>
      <nav
        className="grid w-full max-w-[42rem] grid-cols-1 gap-2.5 sm:grid-cols-2"
        aria-label="Sugestões"
      >
        {STARTERS.map((p) => (
          <button
            key={p.text}
            type="button"
            onClick={() => onSend(p.text)}
            className="rounded-2xl border border-white/[0.08] bg-transparent px-4 py-3.5 text-left transition-colors hover:bg-white/[0.04] hover:border-white/[0.14]"
          >
            <p className="text-[0.9375rem] font-medium text-white/78">{p.label}</p>
            <p className="mt-1 text-[0.8125rem] text-white/35">{p.text}</p>
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
      className="flex min-h-0 flex-1 flex-col bg-[#0a0a0a]"
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
          <section className="aurora-chat-column mx-auto w-full space-y-9 px-4 py-8 md:px-6 md:py-10">
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} avatarUrl={avatarUrl} />
            ))}
          </section>
        )}
      </section>

      <footer className="bg-gradient-to-t from-[#0a0a0a] via-[#0a0a0a]/90 to-transparent">
        <ChatInput onSend={onSend} disabled={loading} />
      </footer>
    </section>
  );
}
