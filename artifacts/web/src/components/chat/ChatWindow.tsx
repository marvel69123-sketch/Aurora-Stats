import { useEffect, useRef } from "react";
import { MessageSquareIcon } from "lucide-react";
import { MessageBubble } from "./MessageBubble";
import { ChatInput } from "./ChatInput";
import type { Session } from "@/types/chat";

interface ChatWindowProps {
  session: Session | null;
  loading: boolean;
  onSend: (text: string) => void;
}

function EmptyState({ onSend }: { onSend: (text: string) => void }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center px-6 text-center select-none">
      <div className="w-16 h-16 rounded-2xl bg-emerald-500/15 border border-emerald-500/20 flex items-center justify-center mb-5 shadow-xl shadow-emerald-500/10">
        <span className="text-3xl font-bold text-emerald-400">A</span>
      </div>
      <h2 className="text-xl font-semibold text-white/80 mb-2">Aurora Intelligence</h2>
      <p className="text-sm text-white/35 max-w-sm leading-relaxed mb-8">
        Professional football analysis powered by expected goals, Poisson modelling,
        and 39 betting methodology rules.
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-lg">
        {STARTER_PROMPTS.map((p) => (
          <button
            key={p.text}
            onClick={() => onSend(p.text)}
            className="text-left px-4 py-3 rounded-xl bg-white/[0.04] border border-white/8 hover:bg-white/8 hover:border-white/15 transition-all group"
          >
            <p className="text-xs font-medium text-white/60 group-hover:text-white/80 transition-colors">
              {p.label}
            </p>
            <p className="text-[11px] text-white/30 mt-0.5">{p.text}</p>
          </button>
        ))}
      </div>
    </div>
  );
}

const STARTER_PROMPTS = [
  { label: "Analyze a match",         text: "Analyze Arsenal vs Chelsea" },
  { label: "Live opportunities",       text: "Best live opportunities" },
  { label: "Bankroll performance",     text: "Review bankroll" },
  { label: "Learning recap",           text: "What did Aurora learn today?" },
  { label: "Knowledge — BTTS",         text: "What do you know about BTTS?" },
  { label: "Knowledge — corners",      text: "What do you know about corners?" },
];

export function ChatWindow({ session, loading, onSend }: ChatWindowProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const messages = session?.messages ?? [];
  const isEmpty = messages.length === 0;

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [messages.length, loading]);

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {/* Messages area */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto"
      >
        {isEmpty ? (
          <EmptyState onSend={onSend} />
        ) : (
          <div className="max-w-3xl mx-auto px-4 py-8 space-y-8">
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
          </div>
        )}
      </div>

      {/* Input area */}
      <div className="max-w-3xl mx-auto w-full">
        <ChatInput onSend={onSend} disabled={loading} empty={isEmpty} />
      </div>
    </div>
  );
}
