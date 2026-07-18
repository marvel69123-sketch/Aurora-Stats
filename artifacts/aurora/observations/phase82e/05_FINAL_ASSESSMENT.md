# Fase 8.2-E — Final Assessment

## Objetivo

Perguntas opinativas sobre partidas recentes devem sobreviver ao pipeline completo → `team_opinion` / `opinion_time=True`, nunca `calendar_authority`.

## Status

**APROVADO** (smoke full-pipeline + regressões).

## Critério de sucesso

| Critério | Status |
|----------|--------|
| Pipeline completo → team_opinion | OK |
| opinion_time=True | OK |
| Nunca calendar_authority em opinion asks | OK |
| Agenda pura intacta | OK |
| detect_natural_intent intocado | OK |

## Conclusão

A 8.2-B no detector era necessária mas insuficiente. A 8.2-E corrige o **sequestro upstream** (Recovery + HIE + gates). Patch pequeno, sem refactor, sem regressão observada nas suites 8.2-A/C e 7.9-E.
