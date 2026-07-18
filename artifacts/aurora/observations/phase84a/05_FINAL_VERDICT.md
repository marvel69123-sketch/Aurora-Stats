# Phase 8.4-A — Final verdict

## Status

**AUDIT COMPLETE — root cause confirmed. No code changes in this phase.**

## Verdict

`match_opinion_renderer` não aparece na resposta final porque **8.3-A não está em produção**.

Smoke passou no tree local; `origin/main` ainda faz:

```text
team_opinion + opinion_time=True
  → compose_intelligent_reply(force_type=team_summary)
  → "**Fluminense** — panorama…"
```

Não há override misterioso após o renderer em produção: o renderer **nunca entra no path**.

## Criterion mapping

| Pergunta | Resposta curta |
|----------|----------------|
| Quem define team_summary? | `force_type` em Natural → RI → planner/templates |
| Override após mop? | N/A em prod (mop ausente) |
| Outro compose? | Sim — Natural + IntelligenceFallback |
| Smoke ≠ prod? | **Sim — gap de deploy 8.3-A** |
| Fallback reescreve? | Não é a causa primária |

## Next

Commit/push/redeploy do 8.3-A (ver `04_FIX_PLAN.md`). Sem novas features.
