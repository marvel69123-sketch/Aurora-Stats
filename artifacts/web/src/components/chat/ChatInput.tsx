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
    <div className="px-3 pb-5 pt-2 md:px-6">
      <div
        className={cn(
          "aurora-chat-column mx-auto flex items-end gap-2 rounded-[26px] border border-white/[0.09]",
          "bg-[#212121] px-3.5 py-2.5",
          "focus-within:border-white/20 focus-within:bg-[#252525]",
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
            "max-h-48 min-h-[28px] flex-1 resize-none bg-transparent py-2",
            "text-[15px] leading-6 tracking-[0.01em] text-white/[0.92] outline-none",
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
              : "bg-white/[0.08] text-white/25 cursor-not-allowed",
          )}
          aria-label="Enviar"
        >
          <ArrowUpIcon size={18} />
        </button>
      </div>
      <p className="aurora-chat-column mx-auto mt-2.5 text-center text-[11px] tracking-wide text-white/25">
        Aurora pode errar. Confira dados ao vivo antes de decidir.
      </p>
    </div>
  );
}
