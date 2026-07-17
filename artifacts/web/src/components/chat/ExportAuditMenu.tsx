import { useEffect, useState } from "react";
import { DownloadIcon, MoreVerticalIcon } from "lucide-react";
import type { Session } from "@/types/chat";
import {
  downloadConversationAudit,
  isDeveloperAuditMode,
  setDeveloperAuditMode,
} from "@/lib/auditExport";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuCheckboxItem,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

type Props = {
  session: Session | null | undefined;
};

export function ExportAuditMenu({ session }: Props) {
  const [devMode, setDevMode] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    setDevMode(isDeveloperAuditMode());
  }, []);

  const disabled = !session || session.messages.length === 0;

  const handleExport = () => {
    if (!session || disabled) return;
    try {
      const { filename, bytes } = downloadConversationAudit(session, {
        developerAuditMode: isDeveloperAuditMode(),
        appVersion: "web",
      });
      setToast(`${filename} (${Math.round(bytes / 1024)} KB)`);
      window.setTimeout(() => setToast(null), 3200);
    } catch {
      setToast("Falha ao exportar auditoria");
      window.setTimeout(() => setToast(null), 3200);
    }
  };

  return (
    <div className="relative ml-auto flex items-center gap-1">
      <button
        type="button"
        onClick={handleExport}
        disabled={disabled}
        className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-[0.75rem] text-[#A0A0A0] transition hover:bg-white/5 hover:text-[#ECECEC] disabled:cursor-not-allowed disabled:opacity-40"
        aria-label="Exportar Auditoria"
        title="Exportar Auditoria"
      >
        <DownloadIcon size={16} aria-hidden />
        <span className="hidden sm:inline">Exportar Auditoria</span>
      </button>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            className="rounded-lg p-1.5 text-[#A0A0A0] hover:bg-white/5 hover:text-[#ECECEC]"
            aria-label="Mais opções de auditoria"
          >
            <MoreVerticalIcon size={16} />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-56">
          <DropdownMenuLabel>Auditoria</DropdownMenuLabel>
          <DropdownMenuItem disabled={disabled} onClick={handleExport}>
            <DownloadIcon className="mr-2 h-4 w-4" />
            Exportar Auditoria
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuCheckboxItem
            checked={devMode}
            onCheckedChange={(v) => {
              const on = Boolean(v);
              setDeveloperAuditMode(on);
              setDevMode(on);
            }}
          >
            Modo desenvolvedor (diagnóstico)
          </DropdownMenuCheckboxItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {toast ? (
        <span
          className="absolute right-0 top-full z-20 mt-1 max-w-[16rem] truncate rounded-md bg-[#1a1a1a] px-2 py-1 text-[0.65rem] text-[#A0A0A0] shadow"
          role="status"
        >
          {toast}
        </span>
      ) : null}
    </div>
  );
}
