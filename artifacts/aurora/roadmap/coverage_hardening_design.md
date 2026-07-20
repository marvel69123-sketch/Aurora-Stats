# P3-A.5 — Coverage Hardening Design

**Date:** 2026-07-20  
**Mode:** Design only — **NOT IMPLEMENTED**  
**Freeze:** Engines / Gateway / Cache / NMB / DRS / Guards unchanged  
**Evidence base:** P3-A.4 diagnosis (`n=113`, unresolved=41) + P3-A.3 full cert

**Priority:** ROI → low risk → low effort

---

## Executive recommendation

| Priority | Intervention | Effort | Risk | Resolve Δ (pp) | Premium Δ (pp) |
|:--------:|--------------|:------:|:----:|---------------:|---------------:|
| **1** | **A** Reuse `fixture_id_hint` + **C** skip name re-resolve | S | Low | **+28 → +31** | **+2 → +5** |
| **2** | **B** UCL/UEL alias packs | M | Medium | +14 → +18 (alone) | +1 → +1.5 |
| — | Stacked A+C+B | S+M | Low–Med | **~+30 → +35** | **+2.5 → +6** |

Ship **A+C first**. Treat **B** as chat/name-only residual and long-tail clubs, not the cert unlock.

Thin Premium remains **HOLD** after resolve hardening alone (premium stays ~13–16%, gate needs ≥50%).

---

## Problem statement (from P3-A.4)

1. Soft partials stamp `league.name = "Unknown"`, inflating the Unknown bucket even when corpus had a real `league_hint`.
2. Cert discovery often has **`fixture_id_hint`**, but `analyze_fixture` resolves **only by team names** → wasteful re-resolve.
3. **80%** of unresolved failures are **`alias_team_resolve`** (UCL/UEL qualifiers + some BR names).
4. **37/41** unresolved rows already carried a `fixture_id_hint`.
5. API gaps under throttle: **0**.

---

## Intervention designs

### A — Reuse `fixture_id_hint`

**Intent:** When a caller (cert harness, copilot, gateway ingest) already knows the API-Football fixture id, bind analyze to that id.

**Proposed shape (design only):**
- Optional `fixture_id: int | None` on analyze / internal `_find_fixture` bypass.
- Path: `GET /fixtures?id={fixture_id}` → validate teams loosely (fold/name_match) → continue existing fan-out.
- Cert script: pass `fixture_id_hint` when present.
- On validation miss or 404: fall back to today’s name resolve (no behavior change for chat).

**Expected recoveries:** 37 eligible × 85–95% capture → **~31–35** fixtures.

**Resolve:** 63.7% → **~91.5–94.8%** (clears ≥85% gate).

**Premium:** recovered set is mostly thin prematch → **~12.8–15.8%** absolute (Δ **+2.2–5.2 pp**). Not ≥50%.

**Cost:** **S** — ~0.5–1.5 eng-days (param + fetch-by-id + cert wire + unit tests with mocked fixture payload). No engine/DRS/NMB changes.

**Regression risks (mitigations):**
| Risk | Mitigation |
|------|------------|
| Stale / wrong id | Soft validate home/away names; else fall back |
| Side/home swap | Accept either orientation in validation |
| Id without soft mode | Keep soft partial on 404 |
| Extra API call | Usually **replaces** N team-search calls → net fewer |

---

### B — UCL/UEL alias packs

**Intent:** Extend `TEAM_ALIASES` / search variants for qualifier clubs that fail `/teams?search=` (Mjällby, Saburtalo, Ararat-Armenia, Fenerbahçe diacritics, etc.).

**Proposed shape (design only):**
- Curated alias map from P3-A.4 failure list (canonical API names).
- Prefer exact alias → API id; **no** aggressive fuzzy that maps fiction→real (see Goku→Gokulam).
- Optional league-scoped search when `league_hint` is UCL/UEL.

**Expected recoveries (alone):** 23 eligible × 70–90% → **~16–21**.

**Resolve alone:** → **~78–82%** (does **not** clear 85% by itself).

**Premium:** Δ **~+1.1–1.5 pp** (thin qualifiers).

**Cost:** **M** — ~2–4 eng-days (curation, tests, ongoing pack maintenance each season).

**Regression risks:**
| Risk | Mitigation |
|------|------------|
| Wrong club identity | Human-curated only; tests per alias |
| Fiction/control contamination | Keep control seeds; never alias Goku/Naruto |
| Diacritic collisions | Fold + explicit canonical id where possible |
| Overlap with A | On cert path A already recovers most — B ROI is mainly **name-only UX** |

---

### C — Prevent unnecessary re-resolve

**Intent:** If `fixture_id` is known, **do not** run team search + last/next + H2H pool.

**Relationship:** Implementation detail of **A**; listed separately because P3-A.4 called it out as a root cause.

**Cost:** bundled with A (S).  
**Risk:** low.  
**Direct resolve/premium delta:** same as A.

**Secondary benefit:** fewer provider calls → more budget for signal fan-out → small indirect chance of better soft-miss rates (not counted in projections).

---

## Answers (required)

### 1. Expected gain per lever

| Lever | Resolve gain | Premium gain | Notes |
|-------|-------------:|-------------:|-------|
| Reuse `fixture_id_hint` | **+28 to +31 pp** | **+2 to +5 pp** | Highest ROI |
| UCL/UEL alias packs | +14 to +18 pp alone | +1 to +1.5 pp | Overlaps A on cert |
| Skip unnecessary re-resolve | (enables A) | (via A) | Call reduction |

### 2. How much would resolve rise?

| Package | Resolve rate |
|---------|-------------:|
| Baseline (P3-A.4) | **63.7%** |
| A+C | **~91.5–94.8%** |
| B alone | **~78–82%** |
| A+B+C | **~93–98%** |

**≥85% resolve gate:** achievable with **A+C alone**.

### 3. How much would premium rise?

| Package | Premium rate (band) |
|---------|--------------------:|
| Baseline | **10.6%** |
| A+C | **~12.8–15.8%** |
| B alone | **~11.8–12.1%** |
| A+B+C | **~13–16.5%** |

**Thin Premium (≥50%):** still **no**.

### 4. Implementation cost

| Item | Effort | Scope |
|------|:------:|-------|
| A+C | **S** | analyze optional id + cert pass-through + tests |
| B | **M** | alias pack + tests + seasonal upkeep |
| Engines / DRS / NMB / Gateway core | **None** | out of scope by design |

### 5. Regression risk?

| Area | Risk | Verdict |
|------|:----:|---------|
| A+C with validate+fallback | Low | Preferred |
| B aggressive fuzzy | Medium–High | Avoid; curated only |
| Engine score drift | None | Not touched |
| Cert vs chat parity | Low | Chat gains later via B |

---

## Out of scope (explicit)

- No engine retune  
- No DRS / NMB / Gateway / Cache changes  
- No Thin Premium surface launch  
- No implementation in this phase  

---

## Suggested next phase (when approved)

1. Implement **A+C** behind optional `fixture_id` (default off for external API until tested).  
2. Re-run throttled full cert → confirm resolve ≥85%.  
3. Only then consider **B** for conversational alias coverage.  
4. Signal-density work (stats/events/lineups/odds) remains the path to premium ≥50%.

---

## Artifacts

- `roadmap/coverage_hardening_design.md` (this file)
- `roadmap/resolve_projection.json`
- `roadmap/premium_projection.json`
