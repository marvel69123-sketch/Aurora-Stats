# P3-B — Premium Gap Report (Match-State Diagnosis)

**Date:** 2026-07-20  
**Status:** `PREMIUM_GAP_DIAGNOSIS`  
**Mode:** Diagnosis only — **NOT IMPLEMENTED**  
**Freeze:** engines / DRS formulas / NMB / Gateway unchanged

## Baseline

| Metric | Value |
|--------|------:|
| n | 106 |
| resolve_rate | **96.2%** |
| premium_rate | **24.5%** |
| resolved non-premium (gap) | **76** |
| mean DRS in gap | 40.79 |
| mean points short of 60 | 19.21 |
| gap by phase | `{'seed': 6, 'prematch': 70}` |

Resolve is largely solved; premium stays ~25% because **DRS&lt;60** on most resolved fixtures — match-state / prematch emptiness, not identity.

---

## 1. Signals missing in the non-premium ~75%

Among **resolved ∧ ¬premium**:

| Signal | Times missing |
|--------|--------------:|
| events | 76 |
| lineups | 76 |
| live_momentum | 76 |
| score | 76 |
| statistics | 76 |
| referee | 75 |
| injuries | 57 |
| xg | 43 |
| standings | 26 |
| odds | 22 |

---

## 2. Highest ROI signal (single fill → 100% on gap)

| Signal | Δ premium pp | Resulting premium | Newly premium |
|--------|-------------:|------------------:|--------------:|
| statistics | 29.25 | 53.8% | 31 |
| lineups | 17.92 | 42.4% | 19 |
| events | 0.0 | 24.5% | 0 |
| live_momentum | 0.0 | 24.5% | 0 |
| odds | 0.0 | 24.5% | 0 |
| xg | 0.0 | 24.5% | 0 |
| score | 0.0 | 24.5% | 0 |

---

## 3. If each signal were 100% (on current gap)

See `signal_roi_projection.json` → `single_fill_if_100pct_coverage_on_gap`.

---

## 4. Minimal combo for premium ≥50%

`statistics` → premium **53.8%**

Broader packs in `premium_unlock_projection.json`.

---

## 5. Signal dependencies

- **Prematch structure:** statistics / events / score / live_momentum often empty together until live or FT.
- **DRS caps:** core ≤50, context ≤20, market ≤10, wave3 bonus ≤12.
- **Synergy:** xG+events(+momentum); odds+lineups+calendar cluster.
- **live_or_finished (+8):** blocked while status is NS — hard ceiling for pure prematch.

---

## Artifacts

- `roadmap/premium_gap_report.md`
- `roadmap/signal_roi_projection.json`
- `roadmap/premium_unlock_projection.json`
