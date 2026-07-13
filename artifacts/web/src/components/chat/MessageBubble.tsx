import { AuroraAvatar, UserAvatar } from "./AuroraAvatar";
import { AuroraResponse } from "./AuroraResponse";
import type { Message } from "@/types/chat";

interface MessageBubbleProps {
  message: Message;
  avatarUrl?: string | null;
}

export function TypingIndicator({ avatarUrl }: { avatarUrl?: string | null }) {
  return (
    <div className="flex items-start gap-4">
      <AuroraAvatar url={avatarUrl} size="sm" className="mt-0.5" />
      <div className="flex items-center gap-1.5 py-2.5">
        <div className="aurora-dot h-1.5 w-1.5 rounded-full bg-white/45" />
        <div className="aurora-dot h-1.5 w-1.5 rounded-full bg-white/45" />
        <div className="aurora-dot h-1.5 w-1.5 rounded-full bg-white/45" />
      </div>
    </div>
  );
}

export function MessageBubble({ message, avatarUrl }: MessageBubbleProps) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="flex max-w-[min(100%,36rem)] items-start gap-3">
          <div className="rounded-[1.35rem] bg-[#2f2f2f] px-5 py-3 text-[15px] leading-[1.7] tracking-[0.01em] text-white/[0.92]">
            {message.userText}
          </div>
          <UserAvatar size="sm" className="mt-0.5" />
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-start gap-4">
      <AuroraAvatar url={avatarUrl} size="sm" className="mt-0.5" />
      <div className="min-w-0 flex-1 pt-0.5">
        {message.loading ? (
          <div className="flex items-center gap-1.5 py-2.5">
            <div className="aurora-dot h-1.5 w-1.5 rounded-full bg-white/45" />
            <div className="aurora-dot h-1.5 w-1.5 rounded-full bg-white/45" />
            <div className="aurora-dot h-1.5 w-1.5 rounded-full bg-white/45" />
          </div>
        ) : message.error ? (
          <div className="space-y-1.5">
            <p className="text-[15px] leading-7 text-rose-300/90">{message.error}</p>
            <p className="text-sm text-white/35">
              Verifique o nome da partida e tente novamente.
            </p>
          </div>
        ) : message.response ? (
          <AuroraResponse response={message.response} />
        ) : null}
      </div>
    </div>
  );
}
