import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowUpIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface ChatInputProps {
  onSend: (text: string) => void;
  disabled: boolean;
  sessionId?: string | null;
}

const ROTATING_PHRASES = [
  "O melhor apostador não prevê tudo — ele gerencia riscos.",
  "Uma boa leitura vale mais que uma entrada apressada.",
  "Nem toda oportunidade precisa ser aproveitada.",
  "O contexto do jogo muda tudo.",
  "Lucro consistente nasce de decisões disciplinadas.",
  "A paciência também é uma estratégia.",
];

function phraseForSession(sessionId: string | null | undefined): string {
  if (!sessionId) return ROTATING_PHRASES[0];
  let h = 0;
  for (let i = 0; i < sessionId.length; i += 1) {
    h = (h * 31 + sessionId.charCodeAt(i)) >>> 0;
  }
  return ROTATING_PHRASES[h % ROTATING_PHRASES.length];
}

export function ChatInput({ onSend, disabled, sessionId = null }: ChatInputProps) {
  const [text, setText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const phrase = useMemo(() => phraseForSession(sessionId), [sessionId]);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
  }, [text]);

  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  const handleSend = () => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <section className="px-3 pb-5 pt-2 md:px-4" aria-label="Composer">
      <div
        className={cn(
          "aurora-chat-column flex items-end gap-2 rounded-[26px] border border-white/[0.1]",
          "bg-[#2f2f2f] px-3.5 py-2.5",
          "focus-within:border-white/20 focus-within:bg-[#333333]",
        )}
      >
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Pergunte à Aurora…"
          rows={1}
          disabled={disabled}
          aria-label="Mensagem"
          className={cn(
            "max-h-48 min-h-[28px] flex-1 resize-none bg-transparent py-2",
            "text-[15px] leading-7 tracking-[0.01em] text-[#ECECEC] outline-none",
            "placeholder:text-[#A0A0A0]/70",
            disabled && "cursor-not-allowed opacity-50",
          )}
        />
        <button
          type="button"
          onClick={handleSend}
          disabled={!text.trim() || disabled}
          className={cn(
            "mb-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full transition-colors",
            text.trim() && !disabled
              ? "bg-[#ECECEC] text-[#212121] hover:bg-white"
              : "bg-white/[0.08] text-[#A0A0A0]/50 cursor-not-allowed",
          )}
          aria-label="Enviar"
        >
          <ArrowUpIcon size={18} />
        </button>
      </div>
      <p className="aurora-chat-column mt-3 text-center text-[11px] leading-relaxed tracking-wide text-[#A0A0A0]/70">
        {phrase}
      </p>
    </section>
  );
}
