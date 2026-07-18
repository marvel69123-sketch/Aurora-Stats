# 8.4-A.7 — Partial Analysis Patch

## New module

`src/core/partial_analysis.py`

| Helper | Role |
|--------|------|
| `allow_partial_analysis` | Gate: `entity_invalid=false` + quality PARTIAL/WEAK/INCOMPLETE + min signals (teams/fixture/standings) + `completeness ≥ 0.20` (or rate-limited) |
| `build_preliminary_executive` | Public-safe preliminary narrative + limitations + qualitative markets hint — **no invented stats** |
| `resolve_preliminary_confidence` | Band weak/adequate (≈2.0–5.5), never hard refuse at 1.5 |
| `detect_rate_limited` / `is_rate_limit_error` | 429 / too many requests / api_fetch limit |

## Inference context

`scan_analyze_data` now restores prior `inferred_signals` and prior `available_signals` into the live context so soft PARTIAL keeps completeness ≥ 0.20 when teams+fixture were inferred.

## Router (`_run_analyze`)

When `_allow_partial`:

- confidence via `resolve_preliminary_confidence` (not 1.5 cap)
- executive via `build_preliminary_executive`
- entities: `preliminary_analysis=true`, `rewrite_locked=true`, `response_owner=partial_analysis`
- skips Personality polish / ThinkingDelay / PIE overwrite of the prelim body

When not allowed and truly degraded → previous low-confidence behavior remains (fiction INVALID unchanged).

## Soft analyze (`analyze.py`)

Rate-limit on secondary fetches → register penalty / notes; never abort the pipeline.

## Outer 404 path

Valid home/away with failed soft analyze → preliminary payload instead of “não consegui… manteve a conversa”.

## Scope respected

No changes to Opinion Renderer, Calendar Authority, Small Talk, Team Summary, Repair Engine, Follow-up Engine logic — only inference / incomplete-data recovery and guards so presentation does not erase it.
