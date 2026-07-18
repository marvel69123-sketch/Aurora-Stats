# Phase 8.4-A.5 — Ownership patch

## Changes

| File | Change |
|------|--------|
| `turn_ownership.py` | `is_finalized_opinion_payload()`; `can_presence_claim` / `should_skip_competing_social` respect it; `finalize_early_ownership` locks match-opinion as `SPORT` + `rewrite_locked` |
| `natural_conversation.py` | On mop success: `response_owner=match_opinion_renderer`, `final_response=True` |
| `copilot_unified_router.py` | After Natural: if finalized opinion → `mark_owner(SPORT, rewrite_locked=True)` before IntelFallback |

## Rule enforced

If payload is a finalized Natural opinion (`match_opinion_renderer` / `response_type=match_opinion` / `response_owner` / `final_response` / `team_opinion_path` with body / non-entry `renderer_stage`):

→ `can_presence_claim = False`  
→ `should_skip_competing_social = True`  
→ IntelligenceFallback **does not** replace `executive_summary`
