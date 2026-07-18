# Fase 8.2-D — Production vs Smoke

## Smoke 8.2-B (o que passou)

```python
detect_natural_intent("o que voce achou do jogo do fluminense ontem?")
# → team_opinion, recent_match=True
```

Agenda isolada também OK. **Não** passou por:

- MasterIntent
- ContextRecovery rewrite
- DeepThinking
- HumanInference
- `natural_may_emit_opinion`
- IntelligenceFallback
- `try_natural_conversation` async completo

## Produção (o que o usuário vê)

| Campo audit | Valor típico |
|-------------|--------------|
| `fallback_kind` | `calendar_authority` |
| `opinion_time` | `false` |
| Efeito | agenda / empty calendar — não opinião |

Reprodução local **com o mesmo commit da 8.2-B** no path completo:

```
detect(original)     → team_opinion ✅
recovery             → "jogo do Fluminense" / calendar_or_fixture
HIE                  → topic_kind=calendar
natural_may_emit…    → False
fallback_kind        → calendar_authority
opinion_time         → False
```

## Divergência

| | Smoke | Produção |
|---|-------|----------|
| Entrada do detector | mensagem original | mensagem **reescrita** ou gate DT |
| Brain Authority | ausente | `is_calendar_authority=True` |
| Camada final | N/A | IntelFallback |
| Veredito | 8.2-B “passa” | 8.2-B **irrelevante para o resultado** |

## developer_audit_mode

Flag **só de export** no frontend (`buildAuditExport` / localStorage).  
**Não altera** roteamento backend. Produção e audit mode usam o **mesmo** `copilot_unified_router`.

## Build / commit

- Patch 8.2-B está em `e93609b` / `natural_conversation.py` (`_is_recent_match_opinion`).
- `origin/main` contém o commit (ancestral de HEAD local no momento da auditoria).
- Mesmo com build correta, o sintoma persiste — **não é (só) deploy atrasado**.
- Confirmar em UI: `backend_commit` no DEBUG snapshot (se ≠ `e93609b…`, há também atraso de deploy; se igual, confirma esta causa raiz).
