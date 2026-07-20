# P3-A.4 — Coverage & Resolve Hardening (Diagnosis)

**Date:** 2026-07-20  
**Status:** `DIAGNOSIS_RUN`  
**Samples diagnosed:** 107  
**Unresolved / Unknown-label:** 4 / 4  
**Resolve rate (this run):** 96.26%  
**Premium rate (this run):** 25.23%  
**Freeze:** diagnosis only — **no** engine / Gateway / Cache / NMB / DRS / guard / throttle changes

---

## 1. Which fixtures became Unknown?

Unresolved soft partials stamp `league.name = "Unknown"` via `build_partial_analyze_data`.  
In P3-A.3 this produced the **Unknown** league bucket (n≈57) even when the corpus had a real `league_hint`.

### Failure classes (unresolved)

| Class | Count |
|-------|------:|
| `sampling_seed_no_fixture` | 3 |
| `sampling_control_fiction` | 1 |

### Discovery ID discarded

Corpus often carries `fixture_id_hint` from league/date discovery, but `analyze_fixture` resolves **only by team names**.  
Hints present yet unresolved: **0**

### Sample of Unknown / unresolved pairs

| Home | Away | league_hint | phase | class |
|------|------|-------------|-------|-------|
| Juventus | Napoli | Serie A | seed | `sampling_seed_no_fixture` |
| Benfica | Porto | Primeira Liga | seed | `sampling_seed_no_fixture` |
| Ajax | Plymouth | Cross / weak | seed | `sampling_seed_no_fixture` |
| Goku | Naruto | Fiction | seed | `sampling_control_fiction` |

---

## 2. Leagues with most resolve failures

Ranked by **corpus `league_hint`** (not the Unknown label):

| league_hint | n | failures | failure_rate |
|-------------|--:|---------:|-------------:|
| Cross / weak | 1 | 1 | 1.0 |
| Fiction | 1 | 1 | 1.0 |
| Primeira Liga | 1 | 1 | 1.0 |
| Serie A | 9 | 1 | 0.1111 |
| 1. Liga | 1 | 0 | 0.0 |
| A Lyga | 1 | 0 | 0.0 |
| Allsvenskan | 5 | 0 | 0.0 |
| BR Serie A | 4 | 0 | 0.0 |

---

## 3. Failure taxonomy

| Axis | Count | Share of unresolved |
|------|------:|--------------------:|
| aliases (team name) | 0 | 0% |
| fixture discovery / name re-resolve | 0 | 0% |
| API gaps / rate limit | 0 | 0% |
| sampling (seeds/control) | 4 | 100% |

**Interpretation**
- **Aliases:** `No team found matching …`
- **Fixture discovery:** teams OK but no H2H/recent/next match; often after discarding `fixture_id_hint`
- **API gaps:** 429 / 5xx / key issues (should be rare under throttle)
- **Sampling:** fiction control + named seeds without a current fixture window

---

## 4–5. Resolve ROI & premium uplift (model)

Baseline: resolve **96.26%**, premium **25.23%**,  
P(premium|resolved) **26.21%**

| If resolve → | Fixtures to recover | Expected premium | Δ premium pp | Hits premium≥50%? |
|--------------|--------------------:|-----------------:|-------------:|:-----------------:|
| 70% | 0.0 | 25.23% | 0.0 | no |
| 80% | 0.0 | 25.23% | 0.0 | no |
| 85% | 0.0 | 25.23% | 0.0 | no |

Resolve hardening alone **does not** unlock Thin Premium (still need signal density).

---

## Artifacts

- `roadmap/coverage_gap_report.md` (this file)
- `roadmap/unknown_fixture_report.json`
- `roadmap/resolve_roi_report.json`
- `roadmap/league_failure_report.json`
