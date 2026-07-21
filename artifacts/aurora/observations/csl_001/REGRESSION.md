# AURORA-CSL-001 — Regression Report

**Harness:** EVAL-001 (110 questions, local TestClient, no API-Football key)  
**Flags:** `ENABLE_SPORTS_LANGUAGE_LAYER=1`, `ENABLE_CSL=1`, `EMERGENCY_COST_PROTECTION=0`

## Results

| Metric | Baseline PATCH-001 | After SLL 002A | After CSL 001 |
|--------|--------------------|----------------|---------------|
| Success rate | 84.5% | 91.8% | **91.8%** |
| SPORT_REASONING | 12 (10.9%) | 3 (2.7%) | **2 (1.8%)** |
| ENTITY_CORRUPTION | 4 (3.6%) | 3 (2.7%) | **2 (1.8%)** |
| OWNER_LOCK | 1 (0.9%) | 3 (2.7%) | 5 (4.5%) |
| HPS | 76.4 | 83.7 | **83.7** |

HPS = clamp(Success − 2·Entity% − OwnerLock%)

## Unit tests
38 passed (`test_conversation_state_layer_csl001` + SLL + entity_safety).

## Two-turn smoke
1. `Flamengo ou Palmeiras?` → analyze_match; `entities.csl.teams=[Flamengo,Palmeiras]`
2. `Quem está melhor?` → follow_up; CSL phase=FOLLOWUP; teams preserved

## Conclusion
CSL is success-neutral vs SLL baseline and slightly reduces SPORT_REASONING / entity failures. Owner-lock increase is confined to FROZEN guard territory — not addressed here by design.
