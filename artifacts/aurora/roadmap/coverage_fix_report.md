# P3-A.6 — Coverage Fix Report (A+C)

**Date:** 2026-07-20  
**Implemented:** A) reuse `fixture_id_hint` · C) skip unnecessary name re-resolve  
**Not touched:** engines · DRS · NMB · provider client · Gateway · conversational layers  

---

## What changed

| Area | Change |
|------|--------|
| `src/routers/analyze.py` | `_try_bind_fixture_by_id` + optional `fixture_id` on `/analyze` |
| `run_p3a1_live_certification.py` | Passes discovery `fixture_id_hint` into `analyze_fixture` |
| Conversational callers | Unchanged (still name-only; `fixture_id` defaults to `None`) |

Behavior: when `fixture_id` is present → `GET /fixtures?id=` → bind → **no** team search / H2H re-resolve. On empty/error → fall back to legacy name path.

---

## Validation — full cert BEFORE vs AFTER

| Metric | BEFORE (P3-A.3) | AFTER (P3-A.6) | Δ |
|--------|----------------:|---------------:|--:|
| sample_count | 113 | 109 | −4 |
| **resolve_rate** | **0.500** | **0.741** | **+24.1 pp** |
| premium_fixture_rate | 0.089 | 0.241 | +15.1 pp |
| pct_drs_ge_60 | 0.089 | 0.241 | +15.1 pp |
| t3_t4_live_rate | 0.089 | 0.241 | +15.1 pp |
| soft_miss_rate | 0.912 | 0.798 | −11.3 pp |
| provider_health | healthy | healthy | — |
| provider_failure_rate | 0.0046 | 0.0030 | better |
| provider latency p50/p95 | 243 / 264 | 257 / 302 | slight ↑ |

**Regression count:** **0** (resolve, premium, DRS≥60, T3/T4, failure rate, health — none worse)

---

## Success criteria

| Criterion | Result |
|-----------|--------|
| resolve ≥ 85% | **NOT MET** (74.1%) |
| No regressions | **MET** |

Partial success: large, clean resolve lift; Thin Premium gates still HOLD.

---

## Why not 85% yet?

Residual unresolved is mostly:
- Named **seeds / control** without `fixture_id_hint`
- Name-only rows where bind is unavailable (alias pack **B** still deferred)
- Corpus mix shifted (AFTER had `live_phase=13` vs BEFORE `0`) — helps premium density but does not guarantee ≥85% resolve alone

Projected A+C ceiling (~91–95%) assumed high share of rows with valid hints; this run’s residual name-only + seeds kept resolve in the mid‑70s.

---

## Unit tests

`tests/test_p3a6_fixture_id_bind.py` — **5 passed** (bind success, empty/HTTP fallback, name mismatch trusts id, analyze skips `_find_fixture` when id binds).

---

## Artifacts

- `roadmap/coverage_fix_report.md` (this file)
- `roadmap/resolve_before_after.json`
- `roadmap/premium_before_after.json`
- `roadmap/_before_p3a6_snapshot.json` (frozen BEFORE)
- `roadmap/live_density_certified.json` (AFTER)

---

## Recommended next (not in this change)

1. Optional: exclude fiction/control + stale seeds from resolve denominator for cert, **or**  
2. Implement design **B** (UCL/UEL aliases) for name-only residual  
3. Signal-density work remains required for premium ≥50%
