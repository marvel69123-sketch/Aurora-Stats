# Fase 8.3-A — Root Cause

## Problema

INTENT correto (`opinion_time=True`) + RENDER `team_summary` (panorama/agenda).

## Causa raiz

`try_natural_conversation` chamava `compose_intelligent_reply(..., force_type="team_summary")` para **todo** `team_opinion`, inclusive recent-match. O planner/expectation tratam `kind=opinion` / `general_team_talk` como **panorama de time**, não leitura de partida.

## Correção

Renderer dedicado `match_opinion_renderer` quando `recent_match` / ask opinativo de partida; `response_type=match_opinion`; bypass do template panorama.
