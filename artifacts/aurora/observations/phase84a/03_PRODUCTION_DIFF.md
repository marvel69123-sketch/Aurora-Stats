# Phase 8.4-A — Produção vs smoke / local

## Diff de código (essencial)

| Artefato | `origin/main` (prod) | Local (smoke 8.3-A) |
|----------|----------------------|---------------------|
| `match_opinion_renderer.py` | **ausente** | presente (untracked) |
| `natural_conversation` bloco mop | **ausente** — vai direto ao RI | presente — mop antes do RI |
| `response_intelligence` bypass mop | **ausente** | presente |
| `user_expectation` bias `match_opinion` | ausente / default team_summary | presente (unstaged) |
| `response_planner` type `match_opinion` | ausente | presente (unstaged) |
| Routing opinion > calendar (8.2-E) | **presente** | presente |
| Continuity 8.3-B | **presente** (pushed) | presente |

## Diff de comportamento

```
Prod:
  opinion_time=True
  + force_type=team_summary
  → "**Fluminense** — panorama…"

Local smoke:
  opinion_time=True
  + match_opinion_renderer
  → response_type=match_opinion
  → texto de leitura de partida (sem panorama/agenda)
```

## Diff de pipeline (secundário)

Smoke 8.3-A:

```
MasterIntent → recover → DeepThinking → HIE → try_natural_conversation
```

Produção (router): mais camadas (GA/repair/HCE/presence/fallback/formatter).
Para este sintoma, **não é necessário** um sequestro posterior: o path Natural→RI
já emite panorama sem o arquivo 8.3-A.

## Deploy gap

```
8.2-E  → pushed (opinion_time)
8.3-A  → NÃO pushed (renderer)
8.3-B  → pushed (continuity)
```

Resultado: produção “parece” opinativa no flag, mas renderiza resumo de time.
