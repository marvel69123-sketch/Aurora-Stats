import { useMemo, useState } from "react";
import {
  MessageSquareIcon,
  PanelLeftCloseIcon,
  PanelLeftIcon,
  PlusIcon,
  Settings2Icon,
  XIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  DATE_GROUP_LABELS,
  conversationDateGroup,
  type DateGroup,
} from "@/lib/conversationTitle";
import type { Session } from "@/types/chat";
import { AuroraAvatar } from "./AuroraAvatar";
import { AvatarSettingsDialog } from "./AvatarSettingsDialog";
import { ConversationItem } from "./ConversationItem";

interface SidebarProps {
  sessions: Session[];
  activeId: string | null;
  avatarUrl: string | null;
  onSelect: (id: string) => void;
  onNewChat: () => void;
  onDelete: (id: string) => void;
  onRename: (id: string, title: string) => void;
  onTogglePin: (id: string) => void;
  onAvatarUpload: (file: File) => Promise<void>;
  onAvatarClear: () => void;
  isOpen: boolean;
  onClose: () => void;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
}

const GROUP_ORDER: DateGroup[] = ["pinned", "today", "yesterday", "week", "older"];

export function Sidebar({
  sessions,
  activeId,
  avatarUrl,
  onSelect,
  onNewChat,
  onDelete,
  onRename,
  onTogglePin,
  onAvatarUpload,
  onAvatarClear,
  isOpen,
  onClose,
  collapsed = false,
  onToggleCollapse,
}: SidebarProps) {
  const [avatarOpen, setAvatarOpen] = useState(false);

  const groups = useMemo(() => {
    const map = new Map<DateGroup, Session[]>();
    for (const g of GROUP_ORDER) map.set(g, []);
    for (const s of sessions) {
      const g = conversationDateGroup(s.lastActive, s.pinned);
      map.get(g)!.push(s);
    }
    return GROUP_ORDER.map((key) => ({
      key,
      label: DATE_GROUP_LABELS[key],
      items: map.get(key) ?? [],
    })).filter((g) => g.items.length > 0);
  }, [sessions]);

  return (
    <>
      {isOpen && (
        <div
          className="fixed inset-0 z-20 bg-black/55 backdrop-blur-[2px] md:hidden"
          onClick={onClose}
        />
      )}

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-30 flex flex-col bg-[#171717]",
          "border-r border-white/[0.05]",
          "transition-[transform,width] duration-200 ease-out",
          collapsed ? "md:w-[52px]" : "md:w-[272px]",
          "w-[272px]",
          isOpen ? "translate-x-0" : "-translate-x-full",
          "md:relative md:translate-x-0 md:shrink-0",
        )}
      >
        <div className={cn("flex items-center gap-1 p-2.5", collapsed && "md:flex-col")}>
          <button
            type="button"
            onClick={onNewChat}
            className={cn(
              "flex h-10 items-center gap-2.5 rounded-lg px-3 text-[0.875rem] text-white/88",
              "hover:bg-white/[0.06] transition-colors",
              collapsed ? "md:w-10 md:justify-center md:px-0" : "flex-1",
            )}
            title="Nova conversa"
          >
            <PlusIcon size={17} className="shrink-0 opacity-90" strokeWidth={2.25} />
            {!collapsed && <span className="font-medium tracking-[-0.01em]">Nova conversa</span>}
            {collapsed && <span className="md:hidden font-medium">Nova conversa</span>}
          </button>

          {onToggleCollapse && (
            <button
              type="button"
              onClick={onToggleCollapse}
              className="hidden h-10 w-10 shrink-0 items-center justify-center rounded-lg text-white/40 hover:bg-white/[0.06] hover:text-white/75 md:flex"
              title={collapsed ? "Expandir" : "Recolher"}
            >
              {collapsed ? <PanelLeftIcon size={17} /> : <PanelLeftCloseIcon size={17} />}
            </button>
          )}

          <button
            type="button"
            onClick={onClose}
            className="flex h-10 w-10 items-center justify-center rounded-lg text-white/40 hover:bg-white/[0.06] md:hidden"
          >
            <XIcon size={17} />
          </button>
        </div>

        <div
          className={cn(
            "flex-1 overflow-y-auto px-2 pb-3",
            collapsed && "md:hidden",
          )}
        >
          {sessions.length === 0 ? (
            <div className="flex flex-col items-center gap-2.5 px-2 py-12 text-center">
              <MessageSquareIcon size={22} className="text-white/18" />
              <p className="text-[0.8125rem] text-white/35">Nenhuma conversa ainda</p>
            </div>
          ) : (
            groups.map((group) => (
              <div key={group.key} className="mb-3.5">
                <p className="px-2.5 pb-1.5 pt-2 text-[11px] font-medium tracking-[0.04em] text-white/32">
                  {group.label}
                </p>
                <div className="space-y-0.5">
                  {group.items.map((session) => (
                    <ConversationItem
                      key={session.id}
                      session={session}
                      active={session.id === activeId}
                      onSelect={onSelect}
                      onRename={onRename}
                      onDelete={onDelete}
                      onTogglePin={onTogglePin}
                    />
                  ))}
                </div>
              </div>
            ))
          )}
        </div>

        <div
          className={cn(
            "border-t border-white/[0.05] p-2.5",
            collapsed && "md:flex md:justify-center",
          )}
        >
          <button
            type="button"
            onClick={() => setAvatarOpen(true)}
            className={cn(
              "flex w-full items-center gap-2.5 rounded-lg px-2 py-2 text-left",
              "text-white/70 hover:bg-white/[0.06] hover:text-white transition-colors",
              collapsed && "md:w-10 md:justify-center md:px-0",
            )}
            title="Avatar da Aurora"
          >
            <AuroraAvatar url={avatarUrl} size="sm" />
            {!collapsed && (
              <div className="min-w-0 flex-1">
                <p className="truncate text-[0.875rem] font-medium tracking-[-0.01em]">
                  Aurora
                </p>
                <p className="flex items-center gap-1 text-[11px] text-white/32">
                  <Settings2Icon size={11} />
                  Personalizar avatar
                </p>
              </div>
            )}
            {collapsed && (
              <span className="md:hidden min-w-0 flex-1">
                <p className="truncate text-sm font-medium">Aurora</p>
              </span>
            )}
          </button>
        </div>
      </aside>

      <AvatarSettingsDialog
        open={avatarOpen}
        avatarUrl={avatarUrl}
        onClose={() => setAvatarOpen(false)}
        onUpload={onAvatarUpload}
        onClear={onAvatarClear}
      />
    </>
  );
}
