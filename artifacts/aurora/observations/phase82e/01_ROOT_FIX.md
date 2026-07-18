# Fase 8.2-E — Root Fix

## Diagnóstico (8.2-D)

`detect_natural_intent` já classificava opinion, mas o turno morria antes:

1. **ContextRecovery** — branch `jogo do` antes de opinion → rewrite agenda  
2. **HumanInference** — `_CALENDAR` antes de `_OPINION` → `topic_kind=calendar`  
3. **`natural_may_emit_opinion=False`** → Natural aborta  
4. **IntelligenceFallback** → `calendar_authority` / `opinion_time=false`

## Correção (mínima)

| Camada | Mudança |
|--------|---------|
| `context_recovery.py` | Recent-match / opinion **antes** do calendar; mantém mensagem original |
| `human_inference.py` | `is_recent_match_opinion_ask` + bloco opinion **antes** de `_CALENDAR`; `rewrite=None` |
| `brain_authority.py` | `natural_may_emit_opinion` permite se `raw_user_message` é recent-match opinion |
| `intelligence_fallback.py` | Não emite `calendar_authority` se ask é recent-match opinion |

**Não alterado:** `detect_natural_intent`, repair, short memory, ownership, confidence, GA, 7.9 ownership/NRF/misroute patches.

## Precedência

```
opinion / recent-match  >  agenda / "jogo do" / calendar
```

Agenda pura (`tem jogo hoje?`, `próximo jogo`) permanece calendar.
