# FROZEN — Conversation Personalization System (v3.6.x)

**Status:** CONGELADO  
**Desde:** Aurora v3.6.5  
**Escopo:** Frontend only (`artifacts/web`)  
**Feature flag:** `conversationPersonalizationEnabled`  
**Arquivo da flag:** `artifacts/web/src/lib/conversationPersonalization/flags.ts`

> Qualquer alteração neste módulo exige aprovação explícita de produto + checklist anti-regressão abaixo.  
> Falha em qualquer item do protocolo pré-merge → **ABORTAR MERGE**.

---

## O que está congelado

| Superfície | Comportamento oficial |
|---|---|
| Engrenagem (⚙️) | Renderizada no header ao lado do avatar quando a flag é `true` (`App.tsx`) |
| Modal / painel | `ConversationSettingsPanel` — desktop modal, mobile fullscreen |
| localStorage | Chave `aurora_conversation_preferences_v1` |
| Persistência | Sobrevive a F5, nova conversa e restart do navegador |
| Multi-abas | Sync via evento `storage` em `useConversationPreferences` |
| Emojis | Chrome only (`visualChrome.ts`) — densidade none/low/medium/high |
| Entusiasmo | Chrome only — tom/peso tipográfico dos títulos e empty state |
| Cabeçalhos | Chrome only — few / normal / many (visibilidade de labels) |
| Aurora Técnica | `profile === "technical"` → análise completa **sempre expandida** (sem accordion) |
| Aurora Casual | Accordion **apenas** (`Details`); formatter Casual real **não** implementado |
| Fallback seguro | Preferências inválidas → `sanitizePreferences` → defaults técnicos; Casual formatter (se usado no futuro) → fallback Technical via `applyPresentation` |
| Feature flag | Gate único; desligar a flag remove engrenagem/painel da UI |

---

## Arquivos protegidos (não alterar sem aprovação)

```
artifacts/web/src/lib/conversationPersonalization/
artifacts/web/src/hooks/useConversationPreferences.ts
artifacts/web/src/components/chat/ConversationSettingsPanel.tsx
```

Wiring (alterar só com cuidado extremo — impacto em UI):

```
artifacts/web/src/App.tsx                          # gear + Provider + panel
artifacts/web/src/components/chat/AuroraResponse.tsx  # chrome + Técnica expandida
artifacts/web/src/components/chat/ChatWindow.tsx   # empty greeting chrome
artifacts/web/src/types/chat.ts                    # presentationSnapshot (FE-only, Phase 1 off)
```

**Proibido neste freeze:**

- Conectar formatter Casual às respostas
- Alterar engines / payloads / MatchHeader / Premium Live / mercados / FollowUp
- Mudar layout ou apresentação sem sprint dedicada e aprovação

---

## Smoke tests (obrigatórios)

Executar manualmente após qualquer PR que toque FE de chat ou personalização:

| # | Teste | Esperado |
|---|---|---|
| 1 | Engrenagem renderiza | ⚙️ visível no header (flag `true`) |
| 2 | Modal abre | Clique abre “Personalizar Aurora” |
| 3 | Modal fecha | Overlay/X fecha sem erro |
| 4 | Persistência após F5 | Prefs permanecem |
| 5 | Persistência após reiniciar navegador | Prefs permanecem (`localStorage`) |
| 6 | Multi-abas sincroniza | Mudança numa aba reflete na outra |
| 7 | Emojis funcionam | Nenhum → Alto muda densidade de emoji no chrome |
| 8 | Cabeçalhos funcionam | Few / Normal / Many muda labels visíveis |
| 9 | Técnica = análise aberta | Sem “Ver análise completa”; conteúdo expandido |
| 10 | Casual = accordion | Profile Casual mantém accordion (sem Casual real) |

---

## Protocolo antes de merge

Se **qualquer** item falhar → **ABORTAR MERGE**.

- [ ] MatchHeader
- [ ] Premium Live
- [ ] Resolver
- [ ] Estatísticas
- [ ] FollowUp
- [ ] Small Talk
- [ ] Conversation Personalization (smoke table acima)

Complementar (automático quando aplicável):

```bash
cd artifacts/aurora && python -m pytest tests/test_fixture_integrity.py -q
cd artifacts/web && npm run typecheck
```

---

## Arquitetura (referência)

```
Engines (congelados) → Payload neutro → UI
                              ↓
              Conversation Personalization (chrome / layout only)
```

Personalização **nunca** altera inteligência, odds, mercados ou payloads.

---

## Histórico

| Versão | Nota |
|---|---|
| v3.6.0 | Fundação + flag `false` |
| v3.6.1 | Flag `true` — UI visual only |
| v3.6.2 | Emojis / entusiasmo / cabeçalhos no chrome |
| v3.6.4 | Card unificado + Técnica expandida |
| **v3.6.5** | **Freeze documental** — este arquivo |
