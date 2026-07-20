# P3-A.2 — Lite Certification

**Date:** 2026-07-20  
**Status:** `CERTIFIED_RUN`  
**Mode:** `lite`  
**Verdict:** **HOLD**  
**Samples:** 30 (planned 30)  
**Throttle budget used:** 130/180  
**Freeze:** engines / Gateway core / NMB / DRS **not modified**

---

## GO criteria

| Gate | Threshold | Result | Pass |
|------|-----------|-------:|:----:|
| resolve_rate | ≥ 85% | 1.0 | ✅ |
| pct_drs_ge_60 | ≥ 50% | 0.2667 | ❌ |
| premium_fixture_rate | ≥ 50% | 0.2667 | ❌ |
| provider_health | healthy/degraded | healthy | ✅ |

**Verdict: HOLD**  
Lite mode is signal-only; Thin Premium unlock still requires full P3-A.1 (≥100).

---

## P3-A.2 pacing

| Control | Value |
|---------|------:|
| current_delay_sec | 0.25 |
| rate_limit_hits | 0 |
| total_wait_sec | 12.331 |
| budget_used | 130 |
| budget_max | 180 |
| budget_rejected | 0 |

---

## Mandatory metrics

| Metric | Value |
|--------|------:|
| resolve_rate | **1.0** |
| t3_t4_live_rate | **0.2667** |
| pct_drs_ge_60 | **0.2667** |
| premium_fixture_rate | **0.2667** |
| soft_miss_rate | 0.7333 |
| provider_health | **healthy** |
| mean_drs | 46.47 |
| mean_analyze_latency_ms | 2420.04 |

Bucket mix: `{'top': 30, 'mid': 0, 'low': 0, 'control': 0, 'live_phase': 0, 'prematch_phase': 20, 'seed_phase': 10}`

---

## Artifacts

- `roadmap/live_density_lite_certified.json`
- `roadmap/provider_slo_lite_report.json`
- `roadmap/p3a2_lite_certification.md`
