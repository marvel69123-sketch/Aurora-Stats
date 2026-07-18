# Phase 8.4-A.4 — Root cause

## Veredito

**A quebra NÃO é import falho nem path `team_opinion` morto.**

1. `team_opinion` **é atingido**
2. `match_opinion_renderer` **importa e renderiza com sucesso**
3. Em seguida **`IntelligenceFallback` substitui o payload inteiro** porque Natural não trava ownership
4. No fallback, com event loop ativo, o compose async é pulado → `render_from_plan` emite template **leitura rápida / Momento** (família team_summary)
5. O usuário vê panorama/leitura rápida **apesar** de `response_type=match_opinion` nas entities

## Respostas às perguntas

| # | Pergunta | Resposta |
|---|----------|----------|
| 1 | Path team_opinion atingido? | **SIM** |
| 2 | Lazy import OK? | **SIM** |
| 3 | Exception silenciosa no import? | **NÃO** |
| 4 | Estágio posterior sobrescreve? | **SIM — IntelligenceFallback** (texto); late NRF só reetiqueta intent |
| 5 | Runtime = origin/main? | Código local forense = `b288acd` (main). Autoscale vivo ainda não auditável por HTTP |

## Não é

- Ausência de `match_opinion_renderer.py` no tree local/SoT
- Fail-open do `except` do mop no Natural (não disparou)
