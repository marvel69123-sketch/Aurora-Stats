import { useState } from "react";
import {
  MoreHorizontalIcon,
  PencilIcon,
  PinIcon,
  PinOffIcon,
  Trash2Icon,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import type { Session } from "@/types/chat";
import { RenameDialog } from "./RenameDialog";

interface ConversationItemProps {
  session: Session;
  active: boolean;
  onSelect: (id: string) => void;
  onRename: (id: string, title: string) => void;
  onDelete: (id: string) => void;
  onTogglePin: (id: string) => void;
}

export function ConversationItem({
  session,
  active,
  onSelect,
  onRename,
  onDelete,
  onTogglePin,
}: ConversationItemProps) {
  const [renameOpen, setRenameOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <li>
      <div
        className={cn(
          "group relative flex h-10 items-center rounded-lg px-2.5 text-[0.875rem] transition-colors",
          active
            ? "bg-white/[0.09] text-[#ECECEC]"
            : "text-[#A0A0A0] hover:bg-white/[0.05] hover:text-[#ECECEC]",
        )}
      >
        <button
          type="button"
          className="min-w-0 flex-1 truncate text-left tracking-[-0.01em]"
          onClick={() => onSelect(session.id)}
          title={session.title}
        >
          {session.pinned && (
            <PinIcon size={11} className="mr-1.5 inline -mt-0.5 text-[#A0A0A0]" />
          )}
          {session.title}
        </button>

        <DropdownMenu open={menuOpen} onOpenChange={setMenuOpen}>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              className={cn(
                "ml-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-[#A0A0A0] hover:bg-white/10 hover:text-[#ECECEC]",
                "opacity-0 group-hover:opacity-100 focus:opacity-100 data-[state=open]:opacity-100",
                (active || menuOpen) && "opacity-100",
              )}
              onClick={(e) => e.stopPropagation()}
              aria-label="Opções da conversa"
            >
              <MoreHorizontalIcon size={15} />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            align="end"
            className="w-44 border-white/10 bg-[#1f1f1f] text-white"
            onClick={(e) => e.stopPropagation()}
          >
            <DropdownMenuItem
              className="cursor-pointer gap-2 focus:bg-white/10 focus:text-white"
              onClick={() => setRenameOpen(true)}
            >
              <PencilIcon size={14} />
              Renomear
            </DropdownMenuItem>
            <DropdownMenuItem
              className="cursor-pointer gap-2 focus:bg-white/10 focus:text-white"
              onClick={() => onTogglePin(session.id)}
            >
              {session.pinned ? <PinOffIcon size={14} /> : <PinIcon size={14} />}
              {session.pinned ? "Desafixar" : "Fixar"}
            </DropdownMenuItem>
            <DropdownMenuSeparator className="bg-white/10" />
            <DropdownMenuItem
              className="cursor-pointer gap-2 text-rose-400 focus:bg-rose-500/10 focus:text-rose-300"
              onClick={() => onDelete(session.id)}
            >
              <Trash2Icon size={14} />
              Excluir
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <RenameDialog
        open={renameOpen}
        initialTitle={session.title}
        onClose={() => setRenameOpen(false)}
        onConfirm={(title) => onRename(session.id, title)}
      />
    </li>
  );
}
