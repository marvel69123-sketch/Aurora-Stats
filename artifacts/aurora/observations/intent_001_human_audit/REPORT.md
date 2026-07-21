# INTENT-001-HUMAN-AUDIT

**MODE:** Validation only — **no code modifications**  
**FLAGS (ON run):** `ENABLE_SPORT_INTENTS=1`, `ENABLE_CSL=1`, `ENABLE_SPORTS_LANGUAGE_LAYER=1`  
**CONTROL:** same scenarios with `ENABLE_SPORT_INTENTS=0`  
**RUNTIME:** local TestClient · no API-Football key (partial / no-bet expected)  
**ARTIFACTS:** `raw_on.json`, `raw_off.json`

---

## Perceived Intelligence Score (PIS)

Human rubric **0–10** (this audit only):

| Band | Meaning |
|------|---------|
| 8–10 | Intent felt + answer addresses the ask with continuity |
| 5–7 | Intent/continuity OK; answer thin or partial but on-topic |
| 3–4 | Intent may be right internally; user text feels generic / sticky |
| 0–2 | Missed ask, wrong frame, or GA waffle |

PIS scores **user-facing perception**, not log correctness.

---

## Scenario 1 — Compare → form follow-up

### Transcript (ON)

| Turn | User | sport_intent | skill | response_owner | NL intent | PIS |
|------|------|--------------|-------|----------------|-----------|-----|
| 1 | Flamengo ou Palmeiras? | `compare_strength` | `skill_compare_strength` | `partial_analysis` | `analyze_match` | **7.0** |
| 2 | Quem está melhor? | `recent_form` | `skill_recent_form` | `ownership_stability` | `follow_up` | **4.0** |

**Assistant T1 (prefix):** partial-data honesty + **Flamengo x Palmeiras** preliminar.  
**Assistant T2 (prefix):** `Mantendo foco Flamengo x Palmeiras (comparativo De Forca)` + no-bet + `?`

### Control (OFF)

| Turn | sport_intent | Notes | PIS |
|------|--------------|-------|-----|
| 1 | null | Labels fixture as **Flamengo Ou Palmeiras** (fused) | **5.0** |
| 2 | null | Sticky hold; no form framing | **3.5** |

### Perception verdict
Intent **does** flip T2 to `recent_form` and skill rewrite leaves a “comparativo” breadcrumb. User still does **not** get a form/strength answer — only owner-lock hold. **Internal routing ↑ · felt intelligence slightly ↑ vs OFF, still weak.**

---

## Scenario 2 — Vale aposta?

### transcript (ON)

| Turn | User | sport_intent | skill | response_owner | NL intent | PIS |
|------|------|--------------|-------|----------------|-----------|-----|
| 1 | Flamengo x Palmeiras | `compare_strength` | `skill_compare_strength` | `partial_analysis` | `analyze_match` | **6.5** |
| 2 | Vale aposta? | `bet_viability` | `skill_bet_viability` | `ownership_stability` | `follow_up` | **3.5** |

**Assistant T2:** `No-bet: sinais insuficientes para stake.` + `?`  
CSL topic correctly → `bet`.

### Control (OFF) T2
No intent stamp; reply assumes bare **Flamengo** (drops pair). PIS **3.0**.

### Perception verdict
Classification **works** (`bet_viability`). User hears the same no-bet stub — **skill does not change felt answer quality** without market/methodology output (engines frozen / no API key).

---

## Scenario 3 — E fora de casa?

### transcript (ON)

| Turn | User | sport_intent | skill | response_owner | NL intent | PIS |
|------|------|--------------|-------|----------------|-----------|-----|
| 1 | Flamengo x Palmeiras | `compare_strength` | `skill_compare_strength` | `partial_analysis` | `analyze_match` | **6.5** |
| 2 | E fora de casa? | `home_away_analysis` | `skill_home_away` | `ownership_stability` | `follow_up` | **4.0** |

**Assistant T2:** same sticky template as S1T2 (`Mantendo foco… comparativo De Forca`).  
Does **not** mention away/home performance.

### Control (OFF) T2
No intent; similar sticky hold. PIS **3.5**.

### Perception verdict
Intent selected correctly; **user-visible home/away skill content missing.** Perception gain ≈ metadata only.

---

## Scenario 4 — Como chegam?

### transcript (ON)

| Turn | User | sport_intent | skill | response_owner | NL intent | PIS |
|------|------|--------------|-------|----------------|-----------|-----|
| 1 | Flamengo x Palmeiras | `compare_strength` | `skill_compare_strength` | `partial_analysis` | `analyze_match` | **6.5** |
| 2 | Como chegam? | **null** | **null** | `ownership_stability` | `follow_up` | **2.5** |

**Assistant T2:** `Assumindo o time **Flamengo** (sem confronto completo)` — pair collapsed.

### Failure
`Como chegam?` is a natural **recent_form / arrival-form** ask in BR football slang. **Not covered** by current intent patterns → no skill route.

### Perception verdict
**Fail.** Intent layer does not change perception here; continuity also degrades to single team.

---

## Scenario 5 — Inter joga hoje?

### transcript (ON)

| Turn | User | sport_intent | skill | response_owner | NL intent | PIS |
|------|------|--------------|-------|----------------|-----------|-----|
| 1 | Inter joga hoje? | **null** | **null** | `ownership_stability` | `follow_up` | **2.5** |

**Assistant:** assumes Internacional, no calendar “hoje” answer; sticky sport prose.  
CSL alone stamped `topic=calendar`, `date_context=hoje` — **intent layer did not fire**.

### Failure
Classifier gap: patterns match `jogo hoje` / `jogos hoje`, not **`joga hoje`**. Expected `calendar_query` → `skill_calendar_query`.

### Perception verdict
**Fail.** Calendar ask feels unanswered; wrong NL shape (`follow_up` on cold session).

---

## Summary table (critical turns)

| # | Ask | Intent (ON) | Skill (ON) | Owner | PIS ON | PIS OFF | Δ perception |
|---|-----|-------------|------------|-------|--------|---------|--------------|
| S1.2 | Quem está melhor? | recent_form | skill_recent_form | ownership_stability | 4.0 | 3.5 | +0.5 weak |
| S2.2 | Vale aposta? | bet_viability | skill_bet_viability | ownership_stability | 3.5 | 3.0 | +0.5 weak |
| S3.2 | E fora de casa? | home_away_analysis | skill_home_away | ownership_stability | 4.0 | 3.5 | +0.5 weak |
| S4.2 | Como chegam? | — | — | ownership_stability | 2.5 | ~2.5 | **0** |
| S5 | Inter joga hoje? | — | — | ownership_stability | 2.5 | ~2.5 | **0** |
| S1.1 | Flamengo ou Palmeiras? | compare_strength | skill_compare_strength | partial_analysis | 7.0 | 5.0 | **+2.0** |

**Mean PIS (all ON turns):** ≈ **4.9**  
**Mean PIS (paired OFF critical FUs):** ≈ **3.3** on FUs; opener OFF worse on S1.

---

## Failures

1. **S4** — `Como chegam?` not classified (lexicon gap for form/arrival slang).  
2. **S5** — `Inter joga hoje?` not classified as `calendar_query` (`joga` ≠ `jogo` pattern).  
3. **Skill→UX gap** — When intent *is* correct (S1–S3 FU), owner-lock replies stay generic; user does not perceive specialized skill answers.  
4. **S5 cold follow_up** — first-turn calendar routed as `follow_up` + ownership_stability (feels stuck).

---

## Regressions (ON vs OFF)

| Check | Result |
|-------|--------|
| Success path for explicit `A x B` analyze | **No regression** — still `analyze_match` / partial |
| Sport intent stamps when flag ON | **Present** (S1–S3) |
| Flag OFF clears stamps | **OK** — all null |
| User-facing FU quality | **No material regression**; also **no material upgrade** except S1 opener framing (ON avoids fused “Flamengo Ou Palmeiras”) |
| S1 opener clarity | **Improved ON** (proper `Flamengo x Palmeiras` vs fused label OFF) |

No evidence that enabling intents breaks existing analyze paths in this sample.

---

## Verdict

**Do semantic intents change user perception?**

| Layer | Changes perception? |
|-------|---------------------|
| Logs / entities (`sport_intent`, `sport_skill`) | **Yes** — clear, correct on S1–S3 |
| Opener compare framing (with SLL/CSL+intent rewrite) | **Yes, modest** (S1 T1 +2.0 PIS) |
| Follow-up answers (melhor / aposta / fora) | **Barely** (+0.5) — sticky no-bet templates dominate |
| Gaps (chegam / joga hoje) | **No** — intents never fire |

**Bottom line:** INTENT-001 improves **machine-readable routing** and slightly improves **compare openers**. It does **not yet** reliably raise felt intelligence on follow-ups, because skills reshape text upstream while **response ownership** still emits thin continuity shells—not Athena-style specialized answers.

**Recommendation (audit only, no code):** next perception win = skill sinks that *own* the reply for `recent_form` / `home_away` / `bet_viability` / `calendar_query`, or richer continuity templates keyed off `entities.sport_intent` — without touching frozen engines’ methodology math.
