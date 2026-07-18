# Fase 8.2-C — Short Memory Design

## Problema

Follow-ups pronominais (`o que você achou dele?`) não carregam time/jogo → MasterIntent `GENERAL_CHAT` → GA.

## Solução

Módulo isolado: `short_conversation_memory.py`

| Campo | Uso |
|-------|-----|
| `last_team` | clube ativo na conversa |
| `last_fixture` | rótulo soft (`último jogo do X`) ou `Home x Away` se payload tiver |
| `last_question_type` | `last_match` / `opinion` / `entity_switch` / … |
| `last_user_question` | texto original do user |
| `last_assistant_reply` | preview da última resposta |

Persistência: `ctx["short_conversation_memory"]` + `conversation_manager.save` (sessão atual).

## Fluxo

```
user message
  → apply_short_memory_resolve  (ANTES do MasterIntent)
       "achou dele?" + last_team=Flamengo
       → "o que você achou do último jogo do Flamengo?"
  → MasterIntent / pipeline normal
  → note_short_memory (fim do turno)
```

## Exemplos

1. `último jogo do flamengo` → memoriza Flamengo + last_match  
   `o que você achou dele?` → resolve para último jogo do Flamengo (SPORT)

2. `e o palmeiras?` → troca `last_team` / fixture  
   `e o dele?` → Palmeiras (não Flamengo)

3. `não foi isso` → resolve **não** mexe; repair 8.2-A intacto
