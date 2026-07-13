import { useRef, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { AuroraAvatar } from "./AuroraAvatar";

interface AvatarSettingsDialogProps {
  open: boolean;
  avatarUrl: string | null;
  onClose: () => void;
  onUpload: (file: File) => Promise<void>;
  onClear: () => void;
}

export function AvatarSettingsDialog({
  open,
  avatarUrl,
  onClose,
  onUpload,
  onClear,
}: AvatarSettingsDialogProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFile = async (file: File | undefined) => {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      await onUpload(file);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Falha ao carregar imagem");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="border-white/10 bg-[#111] text-white sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-base font-medium">Avatar da Aurora</DialogTitle>
        </DialogHeader>

        <div className="flex flex-col items-center gap-4 py-2">
          <AuroraAvatar url={avatarUrl} size="lg" />
          <p className="text-center text-xs text-white/45">
            Escolha uma imagem para a Aurora. Fica só neste navegador.
          </p>
          {error && <p className="text-xs text-red-400">{error}</p>}
        </div>

        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => void handleFile(e.target.files?.[0])}
        />

        <DialogFooter className="flex-col gap-2 sm:flex-col">
          <Button
            disabled={busy}
            className="w-full bg-[#10a37f] text-white hover:bg-[#0e8f6f]"
            onClick={() => inputRef.current?.click()}
          >
            {busy ? "Carregando…" : "Enviar imagem"}
          </Button>
          {avatarUrl && (
            <Button
              variant="ghost"
              className="w-full text-white/55 hover:bg-white/5 hover:text-white"
              onClick={onClear}
            >
              Restaurar padrão
            </Button>
          )}
          <Button
            variant="ghost"
            className="w-full text-white/40 hover:bg-white/5"
            onClick={onClose}
          >
            Fechar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
