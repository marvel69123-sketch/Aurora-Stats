# Phase 8.4-A.1 — Files missing from production

## Confirmations

| Check | Result |
|-------|--------|
| `match_opinion_renderer.py` exists locally | **YES** (`artifacts/aurora/src/conversation/match_opinion_renderer.py`) |
| Present on `origin/main` before this deploy | **NO** |

## 8.3-A files not on remote (pre-commit)

| Path | Status vs origin |
|------|------------------|
| `src/conversation/match_opinion_renderer.py` | **untracked** (missing on remote) |
| `src/conversation/natural_conversation.py` | modified (mop wire) |
| `src/conversation/response_intelligence.py` | modified (mop bypass) |
| `src/conversation/user_expectation.py` | modified (`match_opinion` bias) |
| `src/conversation/response_planner.py` | modified (`match_opinion` plan) |
| `src/conversation/football_expectations.py` | modified |
| `src/conversation/intelligence_fallback.py` | modified |
| `src/conversation/context_recovery.py` | modified (atuação patterns) |
| `src/conversation/human_inference.py` | modified (atuação patterns) |
| `scripts/phase83a_opinion_renderer_smoke.py` | **untracked** |
| `observations/phase83a/` | **untracked** |

## Explicitly excluded from this commit

- `.tools/`, `prediction_experience.db`, `*_smoke_out.txt`, `human_validation_*`
- Continuity 8.3-B (already on `main`)
