import { AuroraAvatar, UserAvatar } from "./AuroraAvatar";
import { AuroraResponse } from "./AuroraResponse";
import type { Message } from "@/types/chat";

interface MessageBubbleProps {
  message: Message;
  avatarUrl?: string | null;
}

export function TypingIndicator({ avatarUrl }: { avatarUrl?: string | null }) {
  return (
    <article className="flex items-start gap-3.5" aria-busy="true" aria-label="Aurora digitando">
      <AuroraAvatar url={avatarUrl} size="md" className="mt-0.5" />
      <div className="flex items-center gap-1.5 py-3" aria-hidden>
        <span className="aurora-dot h-1.5 w-1.5 rounded-full bg-[#A0A0A0]" />
        <span className="aurora-dot h-1.5 w-1.5 rounded-full bg-[#A0A0A0]" />
        <span className="aurora-dot h-1.5 w-1.5 rounded-full bg-[#A0A0A0]" />
      </div>
    </article>
  );
}

export function MessageBubble({ message, avatarUrl }: MessageBubbleProps) {
  if (message.role === "user") {
    return (
      <article className="flex justify-end" aria-label="Você">
        <div className="flex max-w-[min(100%,48rem)] items-start gap-3">
          <p className="rounded-[1.35rem] bg-[#2f2f2f] px-5 py-3.5 text-[15px] leading-[1.8] tracking-[0.01em] text-[#ECECEC]">
            {message.userText}
          </p>
          <UserAvatar size="md" className="mt-0.5" />
        </div>
      </article>
    );
  }

  return (
    <article className="flex items-start gap-3.5" aria-label="Aurora">
      <AuroraAvatar url={avatarUrl} size="md" className="mt-0.5" />
      <div className="min-w-0 flex-1 pt-1">
        {message.loading ? (
          <div className="flex items-center gap-1.5 py-3" aria-busy="true" aria-hidden>
            <span className="aurora-dot h-1.5 w-1.5 rounded-full bg-[#A0A0A0]" />
            <span className="aurora-dot h-1.5 w-1.5 rounded-full bg-[#A0A0A0]" />
            <span className="aurora-dot h-1.5 w-1.5 rounded-full bg-[#A0A0A0]" />
          </div>
        ) : message.error ? (
          <section className="space-y-2" aria-label="Erro">
            <p className="text-[15px] leading-[1.8] text-rose-300/90">{message.error}</p>
            <p className="text-sm leading-relaxed text-[#A0A0A0]">
              Verifique o nome da partida e tente novamente.
            </p>
          </section>
        ) : message.response ? (
          <AuroraResponse response={message.response} />
        ) : null}
      </div>
    </article>
  );
}
