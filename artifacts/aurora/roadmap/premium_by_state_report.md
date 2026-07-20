# P3-B.1 — Premium by Match State (Diagnosis)

**Date:** 2026-07-20  
**Status:** `MATCH_STATE_DENSITY_DIAGNOSIS`  
**Freeze:** engines · DRS · NMB · Gateway · Resolve · Cost Protection **unchanged**  
**Mode:** Diagnosis only — **NOT IMPLEMENTED**

## Baseline

| Metric | Value |
|--------|------:|
| n | 102 |
| resolve_rate | **99.0%** |
| premium_rate | **22.6%** |
| PREMATCH / LIVE / FINISHED | 96 / 6 / 0 |

---

## 1–3. Density + premium by state

### PREMATCH
| Metric | Value |
|--------|------:|
| n | 96 |
| resolve_rate | 1.0 |
| premium_rate | **0.1875** |
| mean_drs | 56.92 |

| Signal | Coverage |
|--------|---------:|
| statistics | 0.0 |
| lineups | 0.0 |
| events | 0.0 |
| injuries | 0.0495 |
| odds | 0.0729 |
| standings | 0.0729 |
| xg | 0.0182 |
| momentum | 0.0 |

### LIVE
| Metric | Value |
|--------|------:|
| n | 6 |
| resolve_rate | 0.8333 |
| premium_rate | **0.8333** |
| mean_drs | 93.4 |

| Signal | Coverage |
|--------|---------:|
| statistics | 1.0 |
| lineups | 0.94 |
| events | 0.8 |
| injuries | 0.38 |
| odds | 1.0 |
| standings | 1.0 |
| xg | 0.2 |
| momentum | 1.0 |

### FINISHED
| Metric | Value |
|--------|------:|
| n | 0 |
| resolve_rate | 0.0 |
| premium_rate | **0.0** |
| mean_drs | None |

| Signal | Coverage |
|--------|---------:|
| statistics | n/a |
| lineups | n/a |
| events | n/a |
| injuries | n/a |
| odds | n/a |
| standings | n/a |
| xg | n/a |
| momentum | n/a |

---

## 4. Operational ceiling (contextual pack fill)

| State | Baseline premium | Contextual ceiling | Unconstrained fantasy |
|-------|-----------------:|-------------------:|----------------------:|
| PREMATCH | 0.1875 | 1.0 | 1.0 |
| LIVE | 0.8333 | 0.8333 | 0.8333 |
| FINISHED | 0.0 | 0.0 | 0.0 |

### Real teto operacional (interpretation)

| State | Real teto hoje | Nota |
|-------|---------------:|------|
| **PREMATCH** | **~19%** (observed) | Lineups/odds/injuries/standings coverage ≈ 0–7%. Simulated “fill statistics/xG” is **invalid** (structural empty). Contextual pack (lineups+odds+injuries+standings+calendar) is the **design** ceiling if those APIs fill — not current reality. |
| **LIVE** | **~83%** (n=6) | Already near-saturated when resolved; mean DRS 93. Small sample. |
| **FINISHED** | **unknown** | **n=0** this run — no estimate. |

**Fleet premium ~23%** is the mix: mostly PREMATCH (~94% of corpus) at ~19%, plus a few LIVE at ~83%.

---

## 5. Signals that move Premium (by state)

**Honest reading (ignore structural fantasy):**

| State | Signals that actually raise premium |
|-------|-------------------------------------|
| **Prematch** | **lineups**, **odds**, **injuries**, **standings**, **calendar** (and referee). Stats/events/momentum/xG are not operable. Simulation lists statistics/xG as top ROI only because DRS still scores them — that is the bug this diagnosis flags. |
| **Live** | **statistics**, **events**, **momentum**, **score**, **odds**, **lineups** — already present when premium; no residual movers in this sample (5/5 resolved live = premium). |
| **Finished** | Expected: **statistics**, **events**, **xG**, **score** — **no data this run**. |

Simulation movers list (raw model, includes structural): `['statistics', 'xg', 'lineups']` for PREMATCH — treat statistics/xG as **false ROI**.

---

## 6. Structurally impossible in prematch

events, live_momentum, score, statistics, xg

These should be **N/A**, not DRS penalties, while status is NS/TBD.

---

## 7. Contextual DRS model (design only)

- If status in {NS,TBD}: exclude statistics/events/score/live_momentum/xg from missing penalties and from DRS denominator.
- Prematch premium path: weight lineups + odds + injuries + standings + calendar (+ referee).
- Live premium path: weight statistics + events + live_momentum + score (+ odds).
- Finished premium path: weight statistics + events + xg + score (+ standings).
- Optional: state-conditional tier thresholds (e.g. prematch T3 at calibrated lower bar) — product decision, not implemented here.

**Not implemented.** Frozen surfaces unchanged.

---

## Artifacts

- `roadmap/premium_by_state_report.md`
- `roadmap/signal_density_by_state.json`
- `roadmap/drs_state_projection.json`
- `roadmap/premium_unlock_by_state.json`
