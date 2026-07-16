import { cn } from "@/lib/utils";
import {
  CONVERSATION_PROFILE_LIST,
  type ConversationPreferences,
  type ConversationProfileId,
  type DetailLevel,
  type EmojiLevel,
  type EnthusiasmLevel,
  type HeadersListsLevel,
  type StructureLevel,
} from "@/lib/conversationPersonalization";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface ConversationSettingsPanelProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  preferences: ConversationPreferences;
  onChange: (next: ConversationPreferences) => void;
}

function OptionRow<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: Array<{ value: T; label: string }>;
  onChange: (v: T) => void;
}) {
  return (
    <fieldset className="space-y-2">
      <legend className="text-[0.75rem] font-medium uppercase tracking-[0.06em] text-[#A0A0A0]">
        {label}
      </legend>
      <div className="flex flex-wrap gap-2">
        {options.map((opt) => {
          const active = opt.value === value;
          return (
            <button
              key={opt.value}
              type="button"
              onClick={() => onChange(opt.value)}
              className={cn(
                "rounded-lg border px-3 py-1.5 text-[0.8125rem] transition-colors",
                active
                  ? "border-white/25 bg-white/[0.08] text-[#ECECEC]"
                  : "border-white/[0.08] bg-transparent text-[#A0A0A0] hover:border-white/15 hover:text-[#ECECEC]",
              )}
              aria-pressed={active}
            >
              {opt.label}
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}

function SettingsBody({
  preferences,
  onChange,
}: {
  preferences: ConversationPreferences;
  onChange: (next: ConversationPreferences) => void;
}) {
  const patch = <K extends keyof ConversationPreferences>(
    key: K,
    value: ConversationPreferences[K],
  ) => onChange({ ...preferences, [key]: value });

  return (
    <div className="space-y-6 pb-2">
      <section className="space-y-3" aria-label="Perfil conversacional">
        <p className="text-[0.75rem] font-medium uppercase tracking-[0.06em] text-[#A0A0A0]">
          Perfil conversacional
        </p>
        <div className="grid gap-2">
          {CONVERSATION_PROFILE_LIST.map((p) => {
            const active = preferences.profile === p.id;
            return (
              <button
                key={p.id}
                type="button"
                onClick={() =>
                  patch("profile", p.id as ConversationProfileId)
                }
                className={cn(
                  "rounded-xl border px-3.5 py-3 text-left transition-colors",
                  active
                    ? "border-white/25 bg-white/[0.07]"
                    : "border-white/[0.08] hover:border-white/15 hover:bg-white/[0.03]",
                )}
                aria-pressed={active}
              >
                <p className="text-[0.9375rem] font-medium text-[#ECECEC]">
                  {active ? "● " : "○ "}
                  {p.label}
                </p>
                <p className="mt-1 text-[0.8125rem] leading-relaxed text-[#A0A0A0]">
                  {p.description}
                </p>
              </button>
            );
          })}
        </div>
        <p className="text-[0.75rem] leading-relaxed text-[#A0A0A0]/85">
          A personalização muda só a apresentação. Inteligência, mercados e
          estatísticas permanecem iguais. Mensagens antigas não são reescritas.
        </p>
      </section>

      <OptionRow<EmojiLevel>
        label="Emojis"
        value={preferences.emojis}
        onChange={(v) => patch("emojis", v)}
        options={[
          { value: "none", label: "Nenhum" },
          { value: "low", label: "Pouco" },
          { value: "medium", label: "Médio" },
          { value: "high", label: "Alto" },
        ]}
      />

      <OptionRow<EnthusiasmLevel>
        label="Entusiasmo"
        value={preferences.enthusiasm}
        onChange={(v) => patch("enthusiasm", v)}
        options={[
          { value: "low", label: "Baixo" },
          { value: "medium", label: "Médio" },
          { value: "high", label: "Alto" },
        ]}
      />

      <OptionRow<StructureLevel>
        label="Estrutura"
        value={preferences.structure}
        onChange={(v) => patch("structure", v)}
        options={[
          { value: "conversational", label: "Mais conversacional" },
          { value: "balanced", label: "Equilibrado" },
          { value: "technical", label: "Mais técnico" },
        ]}
      />

      <OptionRow<HeadersListsLevel>
        label="Cabeçalhos e listas"
        value={preferences.headersLists}
        onChange={(v) => patch("headersLists", v)}
        options={[
          { value: "few", label: "Poucos" },
          { value: "normal", label: "Normais" },
          { value: "many", label: "Muitos" },
        ]}
      />

      <OptionRow<DetailLevel>
        label="Nível de detalhamento"
        value={preferences.detail}
        onChange={(v) => patch("detail", v)}
        options={[
          { value: "short", label: "Curto" },
          { value: "normal", label: "Normal" },
          { value: "detailed", label: "Detalhado" },
        ]}
      />
    </div>
  );
}

/**
 * ChatGPT-like settings:
 * - Mobile: fullscreen dialog
 * - Desktop: centered modal
 *
 * Presentation prefs only — never touches engines / frozen modules.
 */
export function ConversationSettingsPanel({
  open,
  onOpenChange,
  preferences,
  onChange,
}: ConversationSettingsPanelProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className={cn(
          "border-white/10 bg-[#111] text-[#ECECEC]",
          // Mobile fullscreen
          "left-0 top-0 h-[100dvh] max-h-[100dvh] w-full max-w-none translate-x-0 translate-y-0 rounded-none",
          "overflow-y-auto",
          // Desktop modal
          "sm:left-[50%] sm:top-[50%] sm:h-auto sm:max-h-[min(85vh,640px)] sm:w-full sm:max-w-md",
          "sm:translate-x-[-50%] sm:translate-y-[-50%] sm:rounded-lg",
        )}
      >
        <DialogHeader>
          <DialogTitle className="text-base font-medium tracking-[-0.01em]">
            Personalizar Aurora
          </DialogTitle>
        </DialogHeader>
        <SettingsBody preferences={preferences} onChange={onChange} />
      </DialogContent>
    </Dialog>
  );
}
