# Fase 8.2-A — Repair Design

## Problema

Sinais humanos de correção/frustração (`não foi isso`, `pensa um pouco`, …) caíam em `GENERAL_CHAT` → `reply_general()` → “Entendi. Posso te ajudar…”, com perda de contexto.

## Solução (mínima)

Novo módulo isolado: `src/conversation/conversation_repair.py`

```
mensagem
  → is_repair_signal?
       SIM → build repair reply (usa repair_memory)
            → payload conversation_repair (skip_llm)
            → NÃO chama reply_general
       NÃO → pipeline anterior (GA / Natural / …)
```

## Memória temporária (`ctx["repair_memory"]`)

| Campo | Uso |
|-------|-----|
| `last_user_question` | última pergunta substantiva (não-repair) |
| `last_team` | último time (payload ou texto) |
| `last_assistant_reply` | última resposta (preview) |
| `repair_active` | flag leve |

Atualizada via `note_repair_memory()` no fim do turno (junto do HCE note).

## Wire (router)

1. **Early stack** — `try_conversation_repair` **antes** de `try_general_assistant`
2. **Forced nonsport** — repair **antes** de HCE force / GA retry
3. **Não altera** ownership / confidence / sports / 7.9 modules

## Companion mínimo

`natural_response_engine._ACK` inclui `que bom` para o turno social do fluxo de aprovação não cair no template Entendi (expressão NRE; não é repair).

## Exemplo obrigatório

User: opinião Fluminense ontem → (misroute calendar possível)  
User: `não foi isso`  
→ `Acho que interpretei errado. Você queria minha opinião sobre a partida de ontem do Fluminense?`
