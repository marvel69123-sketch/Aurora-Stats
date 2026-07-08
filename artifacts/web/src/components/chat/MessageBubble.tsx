import { AuroraResponse } from "./AuroraResponse";
import type { Message } from "@/types/chat";

// ---------------------------------------------------------------------------
// Typing indicator
// ---------------------------------------------------------------------------

export function TypingIndicator() {
  return (
    <div className="flex gap-3 items-start">
      <AvatarA />
      <div className="flex items-center gap-1.5 bg-white/[0.04] border border-white/8 rounded-2xl rounded-tl-sm px-4 py-3">
        <div className="aurora-dot w-1.5 h-1.5 rounded-full bg-emerald-400" />
        <div className="aurora-dot w-1.5 h-1.5 rounded-full bg-emerald-400" />
        <div className="aurora-dot w-1.5 h-1.5 rounded-full bg-emerald-400" />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Avatars
// ---------------------------------------------------------------------------

function AvatarA() {
  return (
    <div className="w-8 h-8 rounded-xl bg-emerald-500 flex items-center justify-center flex-shrink-0 mt-0.5 shadow-lg shadow-emerald-500/20">
      <span className="text-white font-bold text-xs">A</span>
    </div>
  );
}

function AvatarUser() {
  return (
    <div className="w-8 h-8 rounded-xl bg-blue-600 flex items-center justify-center flex-shrink-0 mt-0.5">
      <span className="text-white font-bold text-xs">U</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main MessageBubble
// ---------------------------------------------------------------------------

export function MessageBubble({ message }: { message: Message }) {
  if (message.role === "user") {
    return (
      <div className="flex gap-3 items-start justify-end">
        <div className="max-w-[75%] px-4 py-3 rounded-2xl rounded-tr-sm bg-blue-600/90 text-white text-sm leading-relaxed shadow-md shadow-blue-900/30">
          {message.userText}
        </div>
        <AvatarUser />
      </div>
    );
  }

  // Aurora message
  return (
    <div className="flex gap-3 items-start">
      <AvatarA />
      <div className="flex-1 min-w-0">
        <p className="text-[11px] font-semibold text-emerald-400/80 mb-2 tracking-wide">AURORA</p>
        {message.loading ? (
          <div className="flex items-center gap-1.5 bg-white/[0.04] border border-white/8 rounded-2xl rounded-tl-sm px-4 py-3 w-fit">
            <div className="aurora-dot w-1.5 h-1.5 rounded-full bg-emerald-400" />
            <div className="aurora-dot w-1.5 h-1.5 rounded-full bg-emerald-400" />
            <div className="aurora-dot w-1.5 h-1.5 rounded-full bg-emerald-400" />
          </div>
        ) : message.error ? (
          <div className="rounded-xl border border-red-500/20 bg-red-500/[0.06] px-4 py-3">
            <p className="text-sm text-red-300/80">{message.error}</p>
            <p className="text-xs text-white/30 mt-1">
              Check the fixture name spelling and try again.
            </p>
          </div>
        ) : message.response ? (
          <AuroraResponse response={message.response} />
        ) : null}
      </div>
    </div>
  );
}
