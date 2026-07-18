# Fase 8.1 — Pipeline Real do Transcript

**Fonte:** `aurora_audit_20260718_002712.json`  
**Sessão:** `vgpnk4k2`  
**Export:** `2026-07-18T03:27:12.394Z`  
**Modo:** INVESTIGAÇÃO — sem implementação

---

## Mapa por turno

Legenda: `intent` = intent exportado no audit · `route` = família efetiva · `owner` = quem produziu a resposta · `fallback` = caminho de escape · `source final` = evidência no audit

| # | User | intent | route | owner | fallbacks | source final |
|---|------|--------|-------|-------|-----------|--------------|
| 0 | quem e voce? | `identity` | SYSTEM / GA system | GeneralAssistant (`assistant_kind=system`) | nenhum | identidade OK; `skip_llm=true`; conf 0.95 |
| 1 | que bom | `general_chat` | GENERAL_CHAT → GA general | **GeneralAssistant** | NRF (se ativo) não alterou texto | **Entendi…**; `sources=["GeneralAssistant"]`; `skip_llm=true`; conf 0.75 (`short_general`) |
| 2 | me fale sobre o flamengo | `team_opinion` | NaturalConversation | Natural (`natural_kind=team_opinion`) | template opinion | resposta “leitura rápida” Flamengo; `opinion_time=true` |
| 3 | oque voce achou do jogo do fluminense ontem? | **`team_calendar`** | NaturalConversation agenda | Natural (`natural_kind=team_calendar`) | nenhum repair | agenda **hoje** (`calendar_date=2026-07-18`); Vitória U20 x Fluminense de Feira U20 |
| 4 | nao voce nao entendeu… | `general_chat` | GENERAL_CHAT → GA general | **GeneralAssistant** | sem repair intent | **Entendi…**; conf **0.55** (`default_general`); `skip_llm=true` |
| 5 | quero saber oque voce achou do ultimo jogo… | **`team_calendar`** | NaturalConversation agenda | Natural | nenhum | mesma agenda U20 de hoje |
| 6 | pensa um pouco… aurora | `general_chat` | GENERAL_CHAT → GA general | **GeneralAssistant** | sem meta/repair | **Entendi…**; conf 0.55 |
| 7 | aurora? | `general_chat` | GENERAL_CHAT → GA general | **GeneralAssistant** | — | **Entendi…**; conf 0.75 |
| 8 | ? | `general_chat` | GENERAL_CHAT → GA general | **GeneralAssistant** | — | **Entendi…**; conf 0.75 |
| 9 | cara voce e muito inutil serio | `general_chat` | GENERAL_CHAT → GA general | **GeneralAssistant** | — | **Entendi…**; conf 0.75 |
| 10 | paraaa de fica em loop | `general_chat` | GENERAL_CHAT → GA general | **GeneralAssistant** | — | **Entendi…** |
| 11 | pare imediamente | `general_chat` | GENERAL_CHAT → GA general | **GeneralAssistant** | — | **Entendi…** |
| 12 | cansei de testar | `general_chat` | GENERAL_CHAT → GA general | **GeneralAssistant** | — | **Entendi…** |

---

## Fluxo estrutural observado

```
mensagem
  → MasterIntent (fail-open GENERAL_CHAT)
  → se nonsport: try_general_assistant → reply_general (Entendi) + skip_llm
  → se sport/natural: NaturalConversation detect kind
       (team_calendar ANTES de team_opinion quando há "jogo do")
  → HCE meta/repair: NÃO disparou em nenhum turno de frustração
  → late NRF / ownership: sem markers `turn_owner` / `rewrite_locked` no export
  → source final = texto idêntico em 9/13 respostas assistente
```

---

## Contagem

| Sinal | Valor |
|-------|-------|
| Turnos user | 13 |
| Respostas “Entendi…” idênticas | **9** (turns 1,4,6–12) |
| Misroutes calendar vs opinion | **2** (turns 3,5) |
| `memory_used` | **sempre false** |
| `fallback_used` (flag audit) | sempre false (GA não é marcado como fallback) |
| `GeneralAssistant` como source | turns 1,4,6–12 |
| Markers 7.9 (`turn_owner`, `NRF_BYPASS`, `forced_*`) no entities | **ausentes** |

---

## Conclusão do pipeline real

O caminho dominante desta sessão **não é** o pipeline esportivo corrigido nas fases 7.9-A…E.  
É o **segundo sistema**: `GENERAL_CHAT` → `GeneralAssistant.reply_general` → `skip_llm=true`, intercalado com um misroute de `NaturalConversation` (`team_calendar`) que ignora “achou / ontem / último jogo”.
