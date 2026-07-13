import { useEffect, useRef, useState } from "react";
import { ArrowUpIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface ChatInputProps {
  onSend: (text: string) => void;
  disabled: boolean;
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [text, setText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
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
    <div className="px-3 pb-4 pt-2 md:px-4">
      <div
        className={cn(
          "mx-auto flex max-w-3xl items-end gap-2 rounded-[28px] border border-white/10",
          "bg-[#1a1a1a] px-3 py-2.5 shadow-[0_0_0_1px_rgba(255,255,255,0.02)]",
          "focus-within:border-white/20",
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
          className={cn(
            "max-h-40 min-h-[24px] flex-1 resize-none bg-transparent py-1.5",
            "text-[15px] leading-6 text-white/90 outline-none",
            "placeholder:text-white/30",
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
              ? "bg-white text-black hover:bg-white/90"
              : "bg-white/10 text-white/25 cursor-not-allowed",
          )}
          aria-label="Enviar"
        >
          <ArrowUpIcon size={18} />
        </button>
      </div>
      <p className="mx-auto mt-2 max-w-3xl text-center text-[11px] text-white/25">
        Aurora pode errar. Confira dados ao vivo antes de decidir.
      </p>
    </div>
  );
}
