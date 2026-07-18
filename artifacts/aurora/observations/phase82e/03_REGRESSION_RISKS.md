# Fase 8.2-E — Regression Risks

| Risco | Mitigação | Residual |
|-------|-----------|----------|
| Agenda com “jogo do” virar opinion | Só se markers opinativos (achou/como foi/jogou bem/…) | Baixo |
| `tem jogo hoje?` sem time | Continua calendar_generic / calendar_today | OK |
| Sticky calendar de turno anterior | Gate + fallback checam raw recent-match | Baixo |
| Repair / short memory | Não tocados; smokes PASS | Nenhum |
| 7.9-E misroutes | Smoke 11/11 | Nenhum |

## Respostas às perguntas da fase

| # | Pergunta | Resposta |
|---|----------|----------|
| 1 | Quem define `topic_kind=calendar`? | HIE (`_CALENDAR`) + Recovery rewrite — **corrigido** |
| 2 | Quem define `natural_may_emit_opinion=False`? | `brain_authority` quando calendar authority — **exceção recent-match** |
| 3 | Prioridade incorreta? | **Sim** — calendar antes de opinion |
| 4 | Opinion deve preceder agenda? | **Sim** — implementado |
