# Phase 8.4-A — Root cause

## Veredito

**`match_opinion_renderer` não aparece na resposta final porque o patch 8.3-A nunca foi commitado/pushed.**

Produção roda `origin/main` com routing 8.2-E (`opinion_time=True`) e render legado
(`force_type=team_summary` → template panorama). Smoke 8.3-A passa só no workspace local.

## Evidência git (2026-07-18)

```text
git ls-tree -r origin/main | grep match_opinion
→ (vazio)

git status (local):
?? match_opinion_renderer.py
 M natural_conversation.py      # bloco 8.3-A
 M response_intelligence.py     # bypass mop
 M user_expectation.py / response_planner.py / …
```

Último commit relevante no remote para natural/RI: routing/repair (8.2), **não** renderer 8.3-A.
8.3-B (continuity) foi pushed; 8.3-A ficou de fora de propósito no commit anterior.

## Por que `opinion_time=True` + panorama coexistentes

| Flag | Origem | Significa |
|------|--------|-----------|
| `opinion_time=True` | `natural_conversation` após detect `team_opinion` (8.2-E) | INTENT / família opinativa |
| Texto “panorama” | `compose_intelligent_reply(force_type=team_summary)` → `render_dynamic` | RENDER de resumo de time |

São camadas diferentes. Routing certo ≠ renderer certo.

## Respostas às perguntas da fase

### 1) Quem define `response_type=team_summary`?

Em produção o caminho dominante é:

1. `natural_conversation.py` → `compose_intelligent_reply(..., force_type="team_summary")`
2. `response_planner.py` → `answer_type="team_summary"` para `kind=opinion` / general team talk
3. `response_templates.py` → título `**{team}** — panorama` (variant)

No código local 8.3-A, `entities["response_type"] = "team_summary"` só é setado
quando o mop **não** preencheu `reply` e o RI legado corre.

### 2) Override após `match_opinion_renderer`?

**Não em produção** — o renderer nunca roda.

No código local: se mop preenche `reply`, o bloco RI é skipado (`if not reply`).
Não há override posterior dedicado que reescreva `match_opinion` → panorama
dentro de `try_natural_conversation`.

### 3) Outro `compose_intelligent_reply()`?

Sim, dois call sites:

| Call site | Quando |
|-----------|--------|
| `natural_conversation.py` | path principal `team_opinion` |
| `intelligence_fallback.py` | fallback Intel (também pode forçar `team_summary` / `match_opinion` local) |

Produção: ambos sem módulo mop no tree → panorama / team_summary.

### 4) Pipeline smoke ≠ produção?

**Sim — diferença dominante = código deployado.**

| | Smoke 8.3-A | Produção |
|--|-------------|----------|
| Tree | workspace local com mop | `origin/main` sem mop |
| Entry | `try_natural_conversation` após HIE (script) | router completo |
| Resultado | `response_type=match_opinion` | panorama via RI |

O smoke não prova deploy; prova o path local.

### 5) Fallback posterior reescrevendo?

Não é o bug primário. O texto panorama já nasce no **primeiro** compose com
`force_type=team_summary`. Fallbacks posteriores (presence, formatter, etc.)
podem polir, mas não são a fonte do “Fluminense panorama…”.
