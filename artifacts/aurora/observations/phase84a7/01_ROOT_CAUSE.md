# 8.4-A.7 — Root Cause

## Symptom

Valid confrontations with `fixture_quality=PARTIAL` (e.g. `analise argentina x espanha`) returned:

> A Aurora manteve a conversa com confiança muito baixa (fixture não confirmada)

instead of a preliminary analysis — even when entities were valid and signals existed
(`fixture` / `teams` / `standings`, `data_completeness≈0.333`), including under API rate-limit.

## Blocking gate

**File:** `src/routers/copilot_unified_router.py` (`_run_analyze` assembly)

1. `degraded = is_partial or not fixture_located or completeness < 0.35`
2. `_resolve_fixture_confidence(..., degraded=True)` capped score to **≤1.5** / label `insufficient`
3. Executive preamble forced the refusal string when `is_partial or degraded` and partial recovery was not allowed

## Why `allow_partial` was false (soft / incomplete path)

**File:** `src/core/inference_context.py` → `scan_analyze_data`

Soft analyze (`build_partial_analyze_data`) marks `teams`/`fixture` as **inferred** and puts them in `available_signals`.

`scan_analyze_data` then builds a **fresh** context:

- `fixture.id == 0` → `mark_missing("fixture")`
- prior `inferred_signals` were copied into `inferred_signals` only — **not** restored to `available_signals`

Resulting completeness often became `1/9 ≈ 0.111` (&lt; 0.20), so the new business gate refused preliminary recovery even for named valid teams.

## Secondary overwrite (local smoke)

Even after a useful executive was built, presentation layers could erase it:

1. **Personality polish** — `sanitize_public_prose` treats tokens like `xG` / `API` as internal → empty prose → `human_analyze_fallback` (“Leitura ainda cautelosa…”)
2. **PIE / ThinkingDelay** — with label `insufficient`, rewrote to “Fato: Aprendizado Histórico…”

## Rate limit

`Too many requests` / 429 / `api_fetch` failures were treated as hard data absence rather than a confidence penalty. Soft-fetch already continued, but confidence + refusal path still aborted the useful narrative.

## Not the cause

- Opinion renderer / ownership locks (8.4-A.5) — unrelated; still PASS
- Calendar / Small Talk / Identity — unrelated
- Entity invalid fiction (goku x naruto) — correctly stays INVALID
