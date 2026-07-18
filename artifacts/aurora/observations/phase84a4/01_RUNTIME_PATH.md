# Phase 8.4-A.4 — Runtime path

## Test

`"o que você achou do jogo do fluminense ontem?"`  
Environment: local `TestClient` @ `backend_commit=b288acd` (SoT = origin/main code path).  
Live Autoscale still unreachable (SSL/500) — forensics proved on the same code the deploy should run.

## Path hit?

| Stage | Hit? | Evidence |
|-------|------|----------|
| MasterIntent SPORT_QUERY | YES | logs |
| ContextRecovery `recent_match_opinion` | YES | keep_original |
| HIE `general_team_talk` / Fluminense | YES | conf=0.93 |
| Natural `kind=team_opinion` | YES | `team_opinion_path=true` |
| `match_opinion_renderer` | YES | `renderer_stage=match_opinion_renderer` |
| IntelligenceFallback | YES | **overwrites payload** |
| Late NRF | YES | intent→`small_talk`, keeps fallback text |

## Forensics flags (final entities)

```json
{
  "team_opinion_path": true,
  "match_opinion_import_ok": true,
  "match_opinion_import_error": null,
  "match_opinion_renderer": true,
  "renderer_stage": "match_opinion_renderer",
  "response_type_before_finalize": "match_opinion",
  "response_type_after_finalize": "match_opinion",
  "overwrite_by": "intelligence_fallback",
  "response_type_before_overwrite": "match_opinion",
  "fallback_kind": "local_team_thinking",
  "final_summary_prefix": "**Fluminense** leitura rápida … **Momento** …"
}
```

## Critical mismatch

`response_type` stays `match_opinion` (preserved / re-stamped) but **executive_summary** is team-summary template (“leitura rápida” / Momento) after overwrite.
