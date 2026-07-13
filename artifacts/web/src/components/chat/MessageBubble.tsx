import { AuroraAvatar, UserAvatar } from "./AuroraAvatar";
import { AuroraResponse } from "./AuroraResponse";
import type { Message } from "@/types/chat";

interface MessageBubbleProps {
  message: Message;
  avatarUrl?: string | null;
}

export function TypingIndicator({ avatarUrl }: { avatarUrl?: string | null }) {
  return (
    <div className="flex gap-4 items-start">
      <AuroraAvatar url={avatarUrl} size="sm" className="mt-1" />
      <div className="flex items-center gap-1.5 py-2">
        <div className="aurora-dot h-1.5 w-1.5 rounded-full bg-white/50" />
        <div className="aurora-dot h-1.5 w-1.5 rounded-full bg-white/50" />
        <div className="aurora-dot h-1.5 w-1.5 rounded-full bg-white/50" />
      </div>
    </div>
  );
}

export function MessageBubble({ message, avatarUrl }: MessageBubbleProps) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="flex max-w-[min(100%,42rem)] gap-3 items-start">
          <div className="rounded-3xl bg-[#2f2f2f] px-5 py-3 text-[15px] leading-7 text-white/90">
            {message.userText}
          </div>
          <UserAvatar size="sm" className="mt-1" />
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-4 items-start">
      <AuroraAvatar url={avatarUrl} size="sm" className="mt-1" />
      <div className="min-w-0 flex-1 pt-0.5">
        {message.loading ? (
          <div className="flex items-center gap-1.5 py-2">
            <div className="aurora-dot h-1.5 w-1.5 rounded-full bg-white/50" />
            <div className="aurora-dot h-1.5 w-1.5 rounded-full bg-white/50" />
            <div className="aurora-dot h-1.5 w-1.5 rounded-full bg-white/50" />
          </div>
        ) : message.error ? (
          <div className="space-y-1">
            <p className="text-[15px] leading-7 text-red-300/90">{message.error}</p>
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
