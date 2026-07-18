# 8.4-A.7 — Regression Results

Smoke: `scripts/phase84a7_partial_analysis_smoke.py` → **PASS**  
Extra probes: `observations/phase84a7/regression_extra.json` → **ALL_PASS**

## Mandatory cases

| Case | Input | Result |
|------|-------|--------|
| 1 | `analise argentina x espanha` | ✅ `preliminary_analysis=true`, text contains “leitura preliminar”, ❌ refusal string |
| 2 | `argentina x espanha` | ✅ same preliminary path, confidence label **fraca** (weak) |
| 3 | PARTIAL + rate-limit gate | ✅ `allow_partial_analysis(..., rate_limited=True)` with completeness 0.10 |
| 4 | `analise goku x naruto` | ✅ `entity_invalid=true`, `fixture_quality=INVALID`, no prelim flag |

## Non-regression

| Area | Result | Evidence |
|------|--------|----------|
| Opinion renderer | PASS | `response_type=match_opinion`, `overwrite_by=null` |
| Ownership | PASS | `response_owner=match_opinion_renderer`, locked |
| Small talk | PASS | `intent=small_talk` |
| Identity | PASS | `intent=identity` |
| Continuity (follow-up after opinion) | PASS | Non-empty reply on “e o mercado de gols?” |
| Markets on PARTIAL | PASS | `best_markets` length 5, prelim true, no refusal |
| State isolation / repair | PASS | No ownership steal on opinion path |

## Notes

- Local runs without `API_FOOTBALL_KEY` still recover via soft PARTIAL + inferred teams/fixture (completeness ≈ 0.222).
- Calendar probe returned `intent=unknown` in this env (not introduced by this patch; not in scope). Opinion/ownership/small-talk/identity/markets paths remain green.
