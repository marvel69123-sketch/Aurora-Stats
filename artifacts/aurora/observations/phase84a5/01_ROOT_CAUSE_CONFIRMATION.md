# Phase 8.4-A.5 — Root cause confirmation

## Confirmed (8.4-A.4 forensics)

1. `team_opinion` path hits  
2. `match_opinion_renderer` imports and renders successfully  
3. **IntelligenceFallback** replaces the payload because Natural left `turn_owner=None`  
4. Sync fallback emits `**Fluminense** leitura rápida` / Momento  

## This phase

Ownership lock prevents step 3. Natural match-opinion survives to the final response.
