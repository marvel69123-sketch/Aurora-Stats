# Phase 8.4-A — Fix plan (sem implementar nesta fase)

## Ação mínima (deploy do 8.3-A)

1. **Commit + push** do patch 8.3-A já existente no working tree:
   - `src/conversation/match_opinion_renderer.py` (**novo**)
   - `natural_conversation.py` (mop antes de RI)
   - `response_intelligence.py` (bypass)
   - `user_expectation.py` / `response_planner.py` / `football_expectations.py`
   - `intelligence_fallback.py` (force_type `match_opinion` quando cabe)
   - smoke + `observations/phase83a/`
2. Redeploy produção.
3. Revalidar pergunta: `"o que você achou do jogo do fluminense ontem?"`
   - Esperado: `match_opinion_renderer=True` / `response_type=match_opinion`
   - Não esperado: título `— panorama` / seções Fase atual / Agenda

## Ordem sugerida de verificação pós-deploy

1. Log `[AUDIT]` / entities: `match_opinion_renderer`, `response_type`
2. Texto sem `panorama` / `Agenda à frente` / `Fase atual`
3. Confirmar que agenda (`quando é o próximo jogo?`) **não** cai em mop
4. Smoke `phase83a_opinion_renderer_smoke.py` no ambiente deployado (ou CI)

## Não fazer (escopo)

- Não redesenhar routing 8.2-E
- Não alterar repair / short memory / continuity 8.3-B / ownership 7.9
- Não inventar segundo renderer se o deploy do 8.3-A bastar

## Se após deploy ainda falhar

Só então auditar overrides **pós**-Natural no router (presence/formatter/fallback).
Com o gap atual de deploy, essa investigação é prematura.
