import { PlusIcon, Trash2Icon, MessageSquareIcon, XIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Session } from "@/types/chat";

interface SidebarProps {
  sessions: Session[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNewChat: () => void;
  onDelete: (id: string) => void;
  isOpen: boolean;
  onClose: () => void;
}

function tempoAtras(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "agora mesmo";
  if (m < 60) return `há ${m}min`;
  const h = Math.floor(m / 60);
  if (h < 24) return `há ${h}h`;
  const d = Math.floor(h / 24);
  if (d < 7) return `há ${d}d`;
  return new Date(iso).toLocaleDateString("pt-BR");
}

export function Sidebar({
  sessions,
  activeId,
  onSelect,
  onNewChat,
  onDelete,
  isOpen,
  onClose,
}: SidebarProps) {
  return (
    <>
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-20 md:hidden"
          onClick={onClose}
        />
      )}

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-30 w-64 flex flex-col",
          "bg-[hsl(222,28%,7%)] border-r border-white/[0.06]",
          "transition-transform duration-300 ease-in-out",
          isOpen ? "translate-x-0" : "-translate-x-full",
          "md:relative md:translate-x-0 md:flex-shrink-0"
        )}
      >
        {/* Cabeçalho */}
        <div className="flex items-center justify-between px-4 pt-5 pb-4">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-emerald-500 flex items-center justify-center flex-shrink-0">
              <span className="text-white font-bold text-xs tracking-wide">A</span>
            </div>
            <span className="font-semibold text-white text-sm tracking-wide">Aurora</span>
          </div>
          <button
            onClick={onClose}
            className="md:hidden p-1.5 rounded-md text-white/40 hover:text-white/80 hover:bg-white/5 transition-colors"
          >
            <XIcon size={15} />
          </button>
        </div>

        {/* Nova Conversa */}
        <div className="px-3 pb-3">
          <button
            onClick={onNewChat}
            className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl border border-white/10 text-white/70 hover:text-white hover:bg-white/5 hover:border-white/20 transition-all text-sm font-medium"
          >
            <PlusIcon size={15} />
            Nova conversa
          </button>
        </div>

        <div className="px-3 pb-1">
          <p className="text-[10px] font-semibold text-white/25 uppercase tracking-widest px-1">
            Histórico
          </p>
        </div>

        {/* Lista de conversas */}
        <div className="flex-1 overflow-y-auto px-2 pb-4 space-y-0.5">
          {sessions.length === 0 ? (
            <div className="flex flex-col items-center gap-2 py-12 text-center">
              <MessageSquareIcon size={24} className="text-white/15" />
              <p className="text-xs text-white/30">Nenhuma conversa ainda</p>
              <p className="text-[11px] text-white/20">Comece fazendo uma pergunta</p>
            </div>
          ) : (
            sessions.map((session) => (
              <SessionItem
                key={session.id}
                session={session}
                active={session.id === activeId}
                onSelect={onSelect}
                onDelete={onDelete}
              />
            ))
          )}
        </div>

        {/* Rodapé */}
        <div className="px-4 py-3 border-t border-white/[0.05]">
          <p className="text-[10px] text-white/20 leading-relaxed">
            Aurora — Inteligência Esportiva
            <br />
            <span className="text-emerald-500/50">Copilot v1.0</span>
          </p>
        </div>
      </aside>
    </>
  );
}

interface SessionItemProps {
  session: Session;
  active: boolean;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
}

function SessionItem({ session, active, onSelect, onDelete }: SessionItemProps) {
  return (
    <div
      className={cn(
        "group relative flex items-center gap-2 px-3 py-2.5 rounded-xl cursor-pointer transition-all",
        active
          ? "bg-white/10 text-white"
          : "text-white/50 hover:text-white/80 hover:bg-white/5"
      )}
      onClick={() => onSelect(session.id)}
    >
      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium leading-snug truncate">{session.title}</p>
        <p className="text-[10px] text-white/25 mt-0.5">{tempoAtras(session.lastActive)}</p>
      </div>
      <button
        onClick={(e) => {
          e.stopPropagation();
          onDelete(session.id);
        }}
        className="opacity-0 group-hover:opacity-100 p-1 rounded-md text-white/30 hover:text-red-400 hover:bg-red-400/10 transition-all flex-shrink-0"
      >
        <Trash2Icon size={12} />
      </button>
    </div>
  );
}
