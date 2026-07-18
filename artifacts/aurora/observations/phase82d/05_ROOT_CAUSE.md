# Fase 8.2-D — Root Cause

## Pergunta

Por que `"o que você achou do jogo do fluminense ontem?"` continua em `calendar_authority` após 8.2-B?

## Causa raiz (única, em cadeia)

**O patch 8.2-B corrige só `detect_natural_intent`, mas o turno de produção é sequestrado mais cedo por ContextRecovery + HumanInference, que classificam/reescrevem a frase como agenda (`jogo do`), ativam Brain Authority calendar e fazem IntelligenceFallback emitir `fallback_kind=calendar_authority` com `opinion_time=false`.**

```
frase opinativa com "jogo do"
        ↓
ContextRecovery: calendar branch ANTES de opinion → rewrite "jogo do Fluminense"
        ↓
HumanInference: _CALENDAR antes de _OPINION → topic_kind=calendar
        ↓
natural_may_emit_opinion = False  (e/ou detector vê texto reescrito)
        ↓
IntelligenceFallback → calendar_authority / opinion_time=false
```

## Por que o smoke enganou

Smoke testou o **detector isolado**.  
Produção executa **Recovery → DT → HIE → Natural → Fallback**.

## O que NÃO é a causa principal

| Hipótese | Veredito |
|----------|----------|
| Arquivo errado / segundo natural_conversation | Refutada (1 arquivo) |
| 8.2-B não commitada | Refutada no repo (`e93609b` em main) |
| developer_audit_mode muda rota | Refutada (só export) |
| Ownership/repair/7.9 geram calendar_authority | Refutada (string só em IntelFallback) |
| Deploy atrasado como única causa | Insuficiente (reproduz no código atual) |

## Camadas culpadas (ranking)

1. **P0** `context_recovery.py` — precedência calendar > opinion + rewrite  
2. **P0** `human_inference.py` — `_CALENDAR` > `_OPINION`  
3. **P0** `brain_authority.natural_may_emit_opinion` + `intelligence_fallback` calendar_authority  
4. **P1** lacuna de teste (smoke sem pipeline)  
5. **P2** possível lag de deploy (verificar `backend_commit` na UI)
