# P3-A.1 — Live Density Certification

**Date:** 2026-07-20  
**Status:** `CERTIFIED_RUN`  
**Mode:** `full`  
**Verdict:** **HOLD**  
**Samples:** 109 (planned 109)  
**Throttle budget used:** 670/900  
**Freeze:** engines / Gateway core / NMB / DRS **not modified**

---

## GO criteria

| Gate | Threshold | Result | Pass |
|------|-----------|-------:|:----:|
| resolve_rate | ≥ 85% | 0.7407 | ❌ |
| pct_drs_ge_60 | ≥ 50% | 0.2407 | ❌ |
| premium_fixture_rate | ≥ 50% | 0.2407 | ❌ |
| provider_health | healthy/degraded | healthy | ✅ |

**Verdict: HOLD**  
**Thin Premium: HOLD**

---

## P3-A.2 pacing

| Control | Value |
|---------|------:|
| current_delay_sec | 0.12 |
| rate_limit_hits | 2 |
| total_wait_sec | 42.078 |
| budget_used | 670 |
| budget_max | 900 |
| budget_rejected | 0 |

---

## Mandatory metrics

| Metric | Value |
|--------|------:|
| resolve_rate | **0.7407** |
| t3_t4_live_rate | **0.2407** |
| pct_drs_ge_60 | **0.2407** |
| premium_fixture_rate | **0.2407** |
| soft_miss_rate | 0.7982 |
| provider_health | **healthy** |
| mean_drs | 41.7 |
| mean_analyze_latency_ms | 1437.8 |

Bucket mix: `{'top': 59, 'mid': 24, 'low': 25, 'control': 1, 'live_phase': 13, 'prematch_phase': 78, 'seed_phase': 18}`

---
### Degrading leagues

| League | n | resolve | t3_t4 | soft_miss | mean_drs |
|--------|--:|--------:|------:|----------:|---------:|
| Unknown | 29 | 0.0 | 0.0 | 1.0 | 5.0 |
| Community Shield | 1 | 1.0 | 0.0 | 1.0 | 23.0 |
| Super Cup | 1 | 1.0 | 0.0 | 1.0 | 18.0 |
| Ligue 1 | 1 | 1.0 | 0.0 | 1.0 | 33.0 |
| UEFA Champions League | 14 | 1.0 | 0.0 | 1.0 | 38.0 |
| UEFA Europa League | 3 | 1.0 | 0.0 | 1.0 | 38.0 |
| Major League Soccer | 3 | 1.0 | 0.0 | 1.0 | 50.0 |
| Premier League | 17 | 1.0 | 0.1176 | 0.8824 | 40.88 |
| K League 1 | 8 | 1.0 | 0.25 | 0.75 | 59.75 |
| Serie A | 11 | 1.0 | 0.2727 | 0.7273 | 61.73 |
| Friendlies Clubs | 2 | 1.0 | 0.5 | 1.0 | 43.5 |
| First League | 2 | 1.0 | 1.0 | 1.0 | 75.0 |

---

## Artifacts

- `roadmap/live_density_certified.json`
- `roadmap/provider_slo_report.json`
- `roadmap/p3a_live_certification.md`
