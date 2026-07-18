# Phase 8.4-A — Call stack (produção = `origin/main`)

Pergunta: `"o que você achou do jogo do fluminense ontem?"`

## Stack real em produção

```
copilot_unified_router
  → MasterIntent          (SPORT_QUERY — sport ok)
  → ContextRecovery / HIE (8.2-E: opinion > calendar)
  → DeepThinking
  → try_natural_conversation
       detect → kind=team_opinion, recent_match≈True
       entities.opinion_time = True          ← routing OK
       compose_intelligent_reply(
           force_type="team_summary"        ← RENDER path
       )
         → infer_expected_information (bias team_summary)
         → plan_response (answer_type=team_summary)
         → synthesize_knowledge / rank
         → render_dynamic(plan)
              title = "**Fluminense** — panorama"   ← sintoma
  → payload.executive_summary = esse texto
```

## Onde `match_opinion_renderer` deveria entrar (só local / smoke)

```
try_natural_conversation (kind=team_opinion)
  → wants_match_opinion_render?  YES
  → render_match_opinion(...)
  → entities.response_type = "match_opinion"
  → entities.match_opinion_renderer = True
  → NÃO chama compose com team_summary
```

Em `origin/main` esse bloco **não existe**. O arquivo
`src/conversation/match_opinion_renderer.py` **não está no remote**.

## Quem define `response_type` / tipo efetivo

| Camada | Produção (`origin/main`) | Local 8.3-A (não deployado) |
|--------|--------------------------|-----------------------------|
| Natural detect | `team_opinion` + `opinion_time=True` | igual |
| Force into RI | `force_type="team_summary"` (sempre, se não moment) | bypass mop primeiro |
| Plan | `answer_type=team_summary` | `match_opinion` |
| Template | `**Team** — panorama` | texto opinativo de partida |
| Entity `response_type` | frequentemente ausente / só `response_intelligence` | `match_opinion` |

Nota: o sintoma “panorama” vem do **título do template** em
`response_templates.render_dynamic` quando `answer_type == team_summary`,
não de um flag mágico `response_type=team_summary` no payload de produção.
