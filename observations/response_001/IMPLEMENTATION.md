# AURORA-RESPONSE-SELECTOR-001 — Implementation

**Status:** Implemented  
**Flag:** `ENABLE_RESPONSE_SELECTOR` (default **ON**; `0`/`false`/`off` = legacy first-wins race)

## What changed

| Piece | Change |
|-------|--------|
| `src/conversation/response_selector.py` | **NEW** — `ResponseCandidate`, pool collect, deterministic select |
| `copilot_unified_router.py` | Early claim band → selector when flag ON; legacy path retained |
| `partial_inference_honesty.py` | Skip Mantendo foco / No-bet wrap for skill-authored winners |
| Personality / Credibility skips | Also skip for `sport_intent_authored` |
| Tests | `tests/test_response_selector_001.py` (8 passed) |

## What did **not** change

- methodology / market / confidence / intelligence / learning engines  
- SLL, CSL, entity_safety  
- Internal logic of `ownership_stability` / `sport_continuity_guard` (wrapped as **fallback** generators, priority 40)

## Priorities

| Band | Owner |
|------|--------|
| 90 | `sport_intent_skill` (session FU only; no calendar; no fresh A×B opener) |
| 80 | continuity / pronoun / advanced / SCG resolver hits |
| 40 | ownership soft hold / SCG minimal hold (`fallback=True`) |

## Verify

```text
Turn1: Flamengo x Palmeiras → analyze_match (skill does not steal)
Turn2: Quem está melhor? → response_owner=sport_intent_skill, form prose, no Mantendo foco / No-bet shell
```

Rollback: `ENABLE_RESPONSE_SELECTOR=0`
