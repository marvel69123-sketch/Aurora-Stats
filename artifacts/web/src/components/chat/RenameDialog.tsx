import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

interface RenameDialogProps {
  open: boolean;
  initialTitle: string;
  onClose: () => void;
  onConfirm: (title: string) => void;
}

export function RenameDialog({
  open,
  initialTitle,
  onClose,
  onConfirm,
}: RenameDialogProps) {
  const [value, setValue] = useState(initialTitle);

  useEffect(() => {
    if (open) setValue(initialTitle);
  }, [open, initialTitle]);

  const submit = () => {
    onConfirm(value);
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="border-white/10 bg-[#111] text-white sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-base font-medium">Renomear conversa</DialogTitle>
        </DialogHeader>
        <input
          autoFocus
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") submit();
          }}
          className="mt-1 w-full rounded-lg border border-white/10 bg-[#0a0a0a] px-3 py-2 text-sm text-white outline-none focus:border-white/25"
          placeholder="Título da conversa"
        />
        <DialogFooter className="gap-2 sm:gap-2">
          <Button
            variant="ghost"
            className="text-white/60 hover:bg-white/5 hover:text-white"
            onClick={onClose}
          >
            Cancelar
          </Button>
          <Button
            className="bg-[#10a37f] text-white hover:bg-[#0e8f6f]"
            onClick={submit}
          >
            Salvar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
