# Fase 8.2-D — Real Execution Path

**Modo:** AUDITORIA — sem implementação  
**Pergunta:** `o que você achou do jogo do fluminense ontem?`

---

## Arquivo SoT em produção

Único módulo Natural no monorepo:

`artifacts/aurora/src/conversation/natural_conversation.py`

Importado por:

`artifacts/aurora/src/routers/copilot_unified_router.py` → `try_natural_conversation`

Não há segundo `natural_conversation.py`.

---

## Caminho REAL (produção / router completo)

```
POST copilot
  → MasterIntent          → SPORT_QUERY (club signal)  sport_ok=True
  → ContextRecovery       → REESCREVE mensagem
                            "…achou do jogo do fluminense ontem?"
                            → "jogo do Fluminense"
                            goal=calendar_or_fixture
  → DeepThinking          → topic (pode ser opinion momentâneo)
  → HumanInference        → _CALENDAR casa "jogo do" ANTES de _OPINION
                            topic_kind=calendar  → is_calendar_authority=True
  → NaturalConversation
        detect_natural_intent(mensagem JÁ reescrita)
          ou opinion detectada + natural_may_emit_opinion=False → None
        / agenda team_calendar se detector vê "jogo do …"
  → IntelligenceFallback  → se authority calendar:
                            fallback_kind=calendar_authority
                            opinion_time=false
```

---

## Evidência reproduzida (local, commit com 8.2-B)

| Etapa | Resultado |
|-------|-----------|
| `detect_natural_intent(original)` | `team_opinion` + `recent_match=True` (8.2-B OK) |
| Recovery rewrite | `jogo do Fluminense` / `calendar_or_fixture` |
| HIE | `calendar_or_fixture` / `topic_kind=calendar` |
| `is_calendar_authority` | **True** |
| `natural_may_emit_opinion` | **False** |
| Fallback | `fallback_kind=calendar_authority`, `opinion_time=False` |

---

## Conclusão do path

O patch 8.2-B **é alcançável no arquivo certo**, mas **não governa o turno**: Recovery + HIE + Brain Authority calendar gate + IntelFallback atuam **antes/depois** e anulam a opinião.
