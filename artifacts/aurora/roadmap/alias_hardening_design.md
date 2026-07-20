# P3-A.7 — Alias Hardening Design (Pack B)

**Date:** 2026-07-20  
**Mode:** Design only — **NOT IMPLEMENTED**  
**Question:** Can Alias Pack B push resolve ≥85% without regressions?

---

## Verdict

**No — Pack B is not required for the resolve ≥85% gate after A+C.**

Post-A+C residual diagnosis (with `fixture_id` wired):

| Metric | Value |
|--------|------:|
| n | 107 |
| resolve_rate | **96.3%** |
| unresolved | **4** |
| alias failures | **0** |

Resolve ≥85% is **already cleared** on the A+C path when bind is healthy. Pack B adds **~0 pp** resolve on current residuals.

---

## 1. Which fixtures still fail?

| Home | Away | league_hint | class |
|------|------|-------------|-------|
| Juventus | Napoli | Serie A | `sampling_seed_no_fixture` |
| Benfica | Porto | Primeira Liga | `sampling_seed_no_fixture` |
| Ajax | Plymouth | Cross / weak | `sampling_seed_no_fixture` |
| Goku | Naruto | Fiction | `sampling_control_fiction` |

All four are **named seeds** without `fixture_id_hint`. Teams often resolve; **no current H2H/recent fixture** in the API window. Alias packs cannot invent fixtures.

---

## 2. Counts

| Category | Count | Share of residual |
|----------|------:|------------------:|
| aliases | **0** | 0% |
| seeds (no fixture) | **3** | 75% |
| fiction controls | **1** | 25% |
| no-fixture / bind-miss (discovered) | **0** | 0% |

---

## 3. Highest-ROI aliases?

**On current residual: none** (alias count = 0).

**Historical ROI (pre-A+C, P3-A.4)** — useful only for name-only / bind-fallback:

| Alias candidate | Why it mattered | Post-A+C ROI |
|-----------------|-----------------|--------------|
| Mjällby / Saburtalo / Ararat-Armenia / Sabah / KI Klaksvik / … | UCL qualifier search misses | **~0** (ids bind) |
| Fenerbahçe diacritic | search variant miss | low |
| Atletico Paranaense, Chapecoense-sc | BR naming | low (ids bind) |
| Vitoria, Remo | short BR names | low + **cross-league risk** |

**ROI ranking today:** sampling hygiene ≫ throttle-safe `fixture_id` bind ≫ Pack B (chat UX only).

---

## 4. Projection after B

| Scenario | resolve | premium |
|----------|--------:|--------:|
| Baseline post-A+C (diagnosis) | **96.3%** | **25.2%** |
| + Pack B on current residual | **96.3%** (~+0) | **~25%** (~+0) |
| + Pack B under name-only stress (bind down) | +5–15 pp vs stressed baseline | small |
| Thin Premium ≥50% | **no** | still HOLD |

P3-A.6 full cert showed resolve **74%** with `rate_limit_hits=2` — that dip is explained by **bind→name fallback**, not by missing Pack B as the primary design target. Fixing bind reliability under throttle beats shipping B for the gate.

---

## 5. Risks if B is implemented anyway

| Risk | Level | Evidence / mitigation |
|------|:-----:|------------------------|
| **False positive** | High if fuzzy | `Goku` already resolves toward **Gokulam**; curated exact aliases only; never fuzzy fiction |
| **Cross-league contamination** | Medium | `Vitoria`, `Remo`, short tokens; require league-scoped or id-pinned aliases |
| **Fiction leakage** | High if open | Control seed must remain soft-unresolved; **blocklist** Goku/Naruto and similar |

Regression risk to resolve gate: **low** if B is additive and curated; risk to **identity honesty** is the real concern.

---

## Recommendation

1. **Do not implement Pack B to chase resolve ≥85%** — already achieved under A+C diagnosis.  
2. Optional cert hygiene: exclude `control` fiction from resolve denominator; treat stale derby seeds as sampling, not product bugs.  
3. Optional reliability: route `fixture_id` bind through the same throttled fetcher as cert (reduces 74% vs 96% gap).  
4. Revisit Pack B later for **conversational name-only** entry — not for Thin Premium / resolve gate.

---

## Artifacts

- `roadmap/alias_hardening_design.md` (this file)
- `roadmap/alias_pack_b_projection.json`
- Residual evidence: `roadmap/unknown_fixture_report.json` (2026-07-20T14:29:11)
