import { useState } from "react";
import { cn } from "@/lib/utils";
import { AuroraAvatar } from "@/components/chat/AuroraAvatar";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
import type { AboutYouProfile } from "@/lib/auroraIdentity";

type TabId = "avatar" | "personality" | "preferences" | "about";

const TABS: Array<{ id: TabId; label: string; icon: string }> = [
  { id: "avatar", label: "Avatar", icon: "👤" },
  { id: "personality", label: "Personalidade", icon: "🧠" },
  { id: "preferences", label: "Preferências", icon: "⚙️" },
  { id: "about", label: "Sobre você", icon: "📋" },
];

interface AuroraIdentityCenterProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  avatarUrl: string | null;
  onAvatarUpload: (file: File) => Promise<void> | void;
  onAvatarClear: () => void;
  preferences: ConversationPreferences;
  onPreferencesChange: (next: ConversationPreferences) => void;
  aboutYou: AboutYouProfile;
  onAboutYouChange: (next: AboutYouProfile) => void;
  onAboutYouClear: () => void;
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

function Field({
  label,
  value,
  placeholder,
  onChange,
}: {
  label: string;
  value: string;
  placeholder: string;
  onChange: (v: string) => void;
}) {
  return (
    <label className="block space-y-1.5">
      <span className="text-[0.75rem] font-medium uppercase tracking-[0.06em] text-[#A0A0A0]">
        {label}
      </span>
      <input
        type="text"
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border border-white/[0.1] bg-white/[0.04] px-3 py-2 text-[0.875rem] text-[#ECECEC] placeholder:text-[#A0A0A0]/70 outline-none focus:border-white/25"
      />
    </label>
  );
}

/**
 * Aurora Identity Center (v4.7) — ChatGPT-inspired hub.
 * Additive surface: does NOT edit frozen ConversationSettingsPanel.
 */
export function AuroraIdentityCenter({
  open,
  onOpenChange,
  avatarUrl,
  onAvatarUpload,
  onAvatarClear,
  preferences,
  onPreferencesChange,
  aboutYou,
  onAboutYouChange,
  onAboutYouClear,
}: AuroraIdentityCenterProps) {
  const [tab, setTab] = useState<TabId>("personality");

  const patchPrefs = <K extends keyof ConversationPreferences>(
    key: K,
    value: ConversationPreferences[K],
  ) => onPreferencesChange({ ...preferences, [key]: value });

  const patchAbout = <K extends keyof AboutYouProfile>(
    key: K,
    value: AboutYouProfile[K],
  ) => onAboutYouChange({ ...aboutYou, [key]: value });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className={cn(
          "border-white/10 bg-[#111] text-[#ECECEC]",
          "left-0 top-0 h-[100dvh] max-h-[100dvh] w-full max-w-none translate-x-0 translate-y-0 rounded-none",
          "overflow-y-auto",
          "sm:left-[50%] sm:top-[50%] sm:h-auto sm:max-h-[min(88vh,720px)] sm:w-full sm:max-w-lg",
          "sm:translate-x-[-50%] sm:translate-y-[-50%] sm:rounded-xl",
        )}
      >
        <DialogHeader>
          <DialogTitle className="text-base font-medium tracking-[-0.01em]">
            Aurora Identity Center
          </DialogTitle>
          <p className="text-[0.8125rem] leading-relaxed text-[#A0A0A0]">
            Avatar, personalidade e um pouco sobre você — para a Aurora
            conversar de forma mais natural.
          </p>
        </DialogHeader>

        <div
          className="mt-2 flex gap-1 overflow-x-auto border-b border-white/[0.08] pb-2"
          role="tablist"
          aria-label="Seções do Identity Center"
        >
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={tab === t.id}
              onClick={() => setTab(t.id)}
              className={cn(
                "shrink-0 rounded-lg px-2.5 py-1.5 text-[0.8125rem] transition-colors",
                tab === t.id
                  ? "bg-white/[0.1] text-[#ECECEC]"
                  : "text-[#A0A0A0] hover:bg-white/[0.05] hover:text-[#ECECEC]",
              )}
            >
              <span className="mr-1" aria-hidden>
                {t.icon}
              </span>
              {t.label}
            </button>
          ))}
        </div>

        <div className="mt-4 space-y-5 pb-2" role="tabpanel">
          {tab === "avatar" ? (
            <section className="space-y-4" aria-label="Avatar">
              <div className="flex items-center gap-4">
                <AuroraAvatar url={avatarUrl} size="lg" />
                <div className="min-w-0 space-y-2">
                  <p className="text-[0.875rem] text-[#ECECEC]">
                    Escolha como a Aurora aparece no chat.
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <label className="cursor-pointer rounded-lg border border-white/15 bg-white/[0.06] px-3 py-1.5 text-[0.8125rem] text-[#ECECEC] hover:bg-white/[0.1]">
                      Enviar imagem
                      <input
                        type="file"
                        accept="image/*"
                        className="hidden"
                        onChange={async (e) => {
                          const file = e.target.files?.[0];
                          if (file) await onAvatarUpload(file);
                          e.target.value = "";
                        }}
                      />
                    </label>
                    {avatarUrl ? (
                      <button
                        type="button"
                        onClick={onAvatarClear}
                        className="rounded-lg border border-white/[0.1] px-3 py-1.5 text-[0.8125rem] text-[#A0A0A0] hover:text-[#ECECEC]"
                      >
                        Remover
                      </button>
                    ) : null}
                  </div>
                </div>
              </div>
            </section>
          ) : null}

          {tab === "personality" ? (
            <section className="space-y-4" aria-label="Personalidade">
              <div className="grid gap-2">
                {CONVERSATION_PROFILE_LIST.map((p) => {
                  const active = preferences.profile === p.id;
                  return (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() =>
                        patchPrefs("profile", p.id as ConversationProfileId)
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
              <OptionRow<EmojiLevel>
                label="Emojis"
                value={preferences.emojis}
                onChange={(v) => patchPrefs("emojis", v)}
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
                onChange={(v) => patchPrefs("enthusiasm", v)}
                options={[
                  { value: "low", label: "Baixo" },
                  { value: "medium", label: "Médio" },
                  { value: "high", label: "Alto" },
                ]}
              />
            </section>
          ) : null}

          {tab === "preferences" ? (
            <section className="space-y-4" aria-label="Preferências">
              <OptionRow<StructureLevel>
                label="Estrutura"
                value={preferences.structure}
                onChange={(v) => patchPrefs("structure", v)}
                options={[
                  { value: "conversational", label: "Mais conversacional" },
                  { value: "balanced", label: "Equilibrado" },
                  { value: "technical", label: "Mais técnico" },
                ]}
              />
              <OptionRow<HeadersListsLevel>
                label="Cabeçalhos e listas"
                value={preferences.headersLists}
                onChange={(v) => patchPrefs("headersLists", v)}
                options={[
                  { value: "few", label: "Poucos" },
                  { value: "normal", label: "Normais" },
                  { value: "many", label: "Muitos" },
                ]}
              />
              <OptionRow<DetailLevel>
                label="Nível de detalhamento"
                value={preferences.detail}
                onChange={(v) => patchPrefs("detail", v)}
                options={[
                  { value: "short", label: "Curto" },
                  { value: "normal", label: "Normal" },
                  { value: "detailed", label: "Detalhado" },
                ]}
              />
              <p className="text-[0.75rem] leading-relaxed text-[#A0A0A0]/85">
                Isso muda só o jeito de falar. Análises e mercados continuam
                iguais.
              </p>
            </section>
          ) : null}

          {tab === "about" ? (
            <section className="space-y-4" aria-label="Sobre você">
              <Field
                label="Nome"
                value={aboutYou.name}
                placeholder="Como a Aurora pode te chamar"
                onChange={(v) => patchAbout("name", v)}
              />
              <Field
                label="Papel"
                value={aboutYou.role}
                placeholder="Ex.: criador, analista, torcedor"
                onChange={(v) => patchAbout("role", v)}
              />
              <Field
                label="Time do coração"
                value={aboutYou.favorite_team}
                placeholder="Ex.: Botafogo"
                onChange={(v) => patchAbout("favorite_team", v)}
              />
              <Field
                label="Projeto"
                value={aboutYou.project}
                placeholder="Ex.: Aurora"
                onChange={(v) => patchAbout("project", v)}
              />
              <button
                type="button"
                onClick={onAboutYouClear}
                className="rounded-lg border border-white/[0.1] px-3 py-1.5 text-[0.8125rem] text-[#A0A0A0] hover:border-white/20 hover:text-[#ECECEC]"
              >
                Apagar minhas informações
              </button>
              <p className="text-[0.75rem] leading-relaxed text-[#A0A0A0]/85">
                Guardado só neste aparelho (localStorage). Sem login. Você
                também pode digitar “apague minhas informações” no chat.
              </p>
            </section>
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}
