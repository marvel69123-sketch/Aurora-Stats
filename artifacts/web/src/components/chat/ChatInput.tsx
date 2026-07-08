import { useEffect, useRef, useState } from "react";
import { ArrowUpIcon } from "lucide-react";
import { cn } from "@/lib/utils";

const SUGGESTIONS = [
  "Analisar Arsenal x Chelsea",
  "Analisar Manchester City x Liverpool",
  "Melhores oportunidades ao vivo",
  "Revisar banca",
  "O que a Aurora aprendeu hoje?",
  "O que você sabe sobre BTTS?",
  "O que você sabe sobre escanteios?",
  "Explique o Critério de Kelly",
];

interface ChatInputProps {
  onSend: (text: string) => void;
  disabled: boolean;
  empty: boolean;
}

export function ChatInput({ onSend, disabled, empty }: ChatInputProps) {
  const [text, setText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 120) + "px";
  }, [text]);

  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  const handleSend = () => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSuggestion = (s: string) => {
    setText(s);
    textareaRef.current?.focus();
  };

  return (
    <div className="border-t border-white/[0.06] bg-background px-4 pt-3 pb-4">
      {empty && (
        <div className="flex flex-wrap gap-2 mb-3">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => handleSuggestion(s)}
              className="text-[11px] px-3 py-1.5 rounded-full bg-white/[0.06] text-white/45 border border-white/[0.08] hover:bg-white/10 hover:text-white/70 hover:border-white/20 transition-all"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      <div
        className={cn(
          "flex gap-3 items-end rounded-2xl border px-4 py-3 transition-colors",
          "bg-white/[0.04] border-white/10",
          "focus-within:border-white/25 focus-within:bg-white/[0.06]"
        )}
      >
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Pergunte à Aurora..."
          rows={1}
          disabled={disabled}
          className={cn(
            "flex-1 bg-transparent resize-none outline-none",
            "text-sm text-white/90 placeholder:text-white/25",
            "leading-relaxed min-h-[20px]",
            disabled && "opacity-50 cursor-not-allowed"
          )}
          style={{ maxHeight: "120px" }}
        />
        <button
          onClick={handleSend}
          disabled={!text.trim() || disabled}
          className={cn(
            "w-8 h-8 rounded-full flex items-center justify-center transition-all flex-shrink-0",
            text.trim() && !disabled
              ? "bg-emerald-500 hover:bg-emerald-400 shadow-md shadow-emerald-500/20"
              : "bg-white/8 cursor-not-allowed"
          )}
        >
          <ArrowUpIcon
            size={15}
            className={text.trim() && !disabled ? "text-white" : "text-white/20"}
          />
        </button>
      </div>

      <p className="text-[10px] text-white/20 text-center mt-2">
        Enter para enviar · Shift+Enter para nova linha
      </p>
    </div>
  );
}
