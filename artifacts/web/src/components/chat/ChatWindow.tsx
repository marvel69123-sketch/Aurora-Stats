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

const UI_BUILD =
  typeof __AURORA_UI_BUILD__ !== "undefined" ? __AURORA_UI_BUILD__ : "chatgpt-dev";

function EmptyState({
  onSend,
  avatarUrl,
}: {
  onSend: (text: string) => void;
  avatarUrl: string | null;
}) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center px-6 text-center">
      <AuroraAvatar url={avatarUrl} size="lg" className="mb-6" />
      <h1 className="mb-2 text-2xl font-semibold tracking-tight text-white/90 md:text-3xl">
        Aurora
      </h1>
      <p className="mb-2 max-w-md text-sm leading-relaxed text-white/40">
        Como posso ajudar nas análises de hoje?
      </p>
      <p className="mb-10 text-[11px] text-white/20" data-aurora-ui={UI_BUILD}>
        UI {UI_BUILD}
      </p>
      <div className="grid w-full max-w-xl grid-cols-1 gap-2 sm:grid-cols-2">
        {STARTERS.map((p) => (
          <button
            key={p.text}
            type="button"
            onClick={() => onSend(p.text)}
            className="rounded-2xl border border-white/10 bg-transparent px-4 py-3.5 text-left transition-colors hover:bg-white/[0.04]"
          >
            <p className="text-sm text-white/75">{p.label}</p>
            <p className="mt-0.5 text-xs text-white/35">{p.text}</p>
          </button>
        ))}
      </div>
    </div>
  );
}

export function ChatWindow({
  session,
  loading,
  avatarUrl,
  onSend,
}: ChatWindowProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const messages = session?.messages ?? [];
  const isEmpty = messages.length === 0;

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [messages.length, loading]);

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-[#0a0a0a]">
      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        {isEmpty ? (
          <EmptyState onSend={onSend} avatarUrl={avatarUrl} />
        ) : (
          <div className="mx-auto w-full max-w-3xl space-y-8 px-4 py-8 md:px-6">
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} avatarUrl={avatarUrl} />
            ))}
          </div>
        )}
      </div>

      <div className="bg-gradient-to-t from-[#0a0a0a] via-[#0a0a0a] to-transparent">
        <ChatInput onSend={onSend} disabled={loading} />
      </div>
    </div>
  );
}
