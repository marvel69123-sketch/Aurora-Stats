# PARALLEL-HUMAN-AUDIT-001

**MODE:** Validation only — **no commits / no product code changes**  
**BRANCH:** `feat/aurora-response-selector-001`  
**SoT:** `artifacts/aurora`  
**RUNTIME:** local TestClient · partial data / no API-Football key  
**ARTIFACTS:** `raw_sport_nlg_{off,on}.json`, `raw_topic_boundary_{off,on}.json`, `raw_entity_edge_{off,on}.json`, `raw_before.json`, `raw_after.json`, `run_meta.json`, `run_log.txt`

---

## Flag matrix (realistic stack)

| Flag | Value used | Notes |
|------|------------|-------|
| `ENABLE_RESPONSE_SELECTOR` | **1** | default ON — keep realistic post-RESPONSE-001 stack |
| `ENABLE_SPORT_INTENTS` | **1** | default ON |
| `ENABLE_CSL` | **1** | default ON |
| `ENABLE_SPORTS_LANGUAGE_LAYER` | **1** | default ON |
| `ENABLE_SPORT_NLG` | **0 / 1** | under audit (default OFF in product) |
| `ENABLE_TOPIC_BOUNDARY_V2` | **0 / 1** | under audit (default OFF) |
| `ENABLE_ENTITY_EDGE` | **0 / 1** | under audit (default OFF) |

**Per-track A/B:** only the audited flag flips; the other two stay **0**.  
**Combined before/after:** all three OFF vs all three ON.

---

## PIS rubric (same as INTENT / RESPONSE human audits)

| Band | Meaning |
|------|---------|
| 8–10 | Right specialized / natural frame |
| 5–7 | On-topic; thin on data but not sticky shell |
| 3–4 | Sticky / generic |
| 0–2 | Miss / wrong frame |

---

## 1) SPORT-NLG transcripts (OFF vs ON)

Seed: `Flamengo x Palmeiras` → FU: `Quem esta melhor?` / `Vale aposta?` / `E fora de casa?`

### Scorecard

| Turn | Ask | Owner | OFF prefix frame | ON prefix frame | Invented odds? | PIS OFF | PIS ON | Δ |
|------|-----|-------|------------------|-----------------|----------------|---------|--------|---|
| S1T1 | Flamengo x Palmeiras | `partial_analysis` | `Com **dados parciais**…` honesty | `No mano a mano entre **Flamengo** e **Palmeiras**…` | No | 6.5 | **7.5** | +1.0 |
| S1T2 | Quem esta melhor? | `sport_intent_skill` | `Comparando a **fase recente**…` | `Olhando a **fase recente**…` | No | 7.0 | **8.0** | +1.0 |
| S2T2 | Vale aposta? | `sport_intent_skill` | `Viabilidade de aposta no contexto…` | `Sobre **valer a aposta**…` (+ awkward Title Case fixture label) | No | 7.0 | **7.5** | +0.5 |
| S3T2 | E fora de casa? | `sport_intent_skill` | `Leitura de **mando de campo**…` | `No **mando de campo**…` | No | 7.0 | **8.0** | +1.0 |

`entities.sport_nlg=True` only when ON. Same `sport_intent` / owner as OFF (selector still authors; NLG rewrites surface).

### Verdict

- Prose is **more analyst-like** when ON (mano a mano / olhando / valer a aposta).
- **No invented odds / % / xG** in either mode (`invented_odds_like=false` on all turns).
- Minor polish: ON bet path embeds Title-Case skill label (`Viabilidade De Aposta Em…`).

**Mean PIS (S1T1 + three FUs):** OFF **6.9** → ON **7.8** (**+0.9**)  
**FU-only mean:** OFF **7.0** → ON **7.8** (**+0.8**)

---

## 2) Topic boundary transcripts (OFF vs ON)

### S1 — KEEP continuity

| Mode | T1 episode | T2 `Quem esta melhor?` episode | Boundary? | User text | PIS |
|------|------------|--------------------------------|-----------|-----------|-----|
| OFF | `2945bce3…` | **same** | n/a | form FU on Flamengo x Palmeiras | **7.0** |
| ON | `d6a12dd8…` | **same** | keep | same specialized form frame | **7.0** |

**OK:** soft FU does not rotate episode when V2 ON.

### S2 — NEW fixture (sticky-bleed check)

| Mode | Turn | User | episode_id | CSL fixture | Owner | User-visible | PIS |
|------|------|------|------------|-------------|-------|--------------|-----|
| OFF | T1 | Flamengo x Palmeiras | `34ad1c4e` | Flamengo vs Palmeiras | partial_analysis | correct seed | 6.5 |
| OFF | T2 | Liverpool x Chelsea | **same** `34ad1c4e` | still Flamengo | sport_intent_skill | **Comparativo Flamengo vs Palmeiras** (no Liverpool) | **1.5** |
| OFF | T3 | Quem esta melhor? | same | Flamengo | sport_intent_skill | form on Flamengo | **2.0** |
| ON | T1 | Flamengo x Palmeiras | `6af4d299` | Flamengo | partial_analysis | correct seed | 6.5 |
| ON | T2 | Liverpool x Chelsea | **rotated** `036e2b46` | **still Flamengo** | partial_analysis | **`Mantendo foco Flamengo x Palmeiras`** | **2.0** |
| ON | T3 | Quem esta melhor? | `036e2b46` | Flamengo | sport_intent_skill | still Flamengo form | **2.0** |

### Verdict

| Signal | OFF | ON |
|--------|-----|----|
| Soft FU keeps episode | yes | **yes** |
| New fixture rotates `episode_id` | no | **yes** |
| New fixture answers about Liverpool/Chelsea | **no** | **no** |
| Sticky bleed cleared in user text | no | **no** (`Mantendo foco` still wins) |

**Internal V2 fires; user-facing sticky path still bleeds.** Unit tests for detector/apply pass; full-stack ownership / continuity re-claim still dominates the reply after rotation.

**S2 mean PIS (T2+T3):** OFF **1.8** → ON **2.0** (**+0.2** metadata-only)

---

## 3) Entity edge transcripts (OFF vs ON)

Unit probes via `normalize_team_name` / `resolve_edge_entity` / `fuzzy_correct_team` (see `raw_entity_edge_*.json`).

| Probe | OFF | ON |
|-------|-----|-----|
| Barcelona | Barcelona | Barcelona (`edge_default`) |
| Barcelona SC | Barcelona SC | Barcelona SC (`edge_explicit`) |
| barcelona + La Liga msg | Barcelona | Barcelona (`edge_league`) |
| barcelona + Ecuador/Guayaquil/Liga Pro | **Barcelona** (legacy) | **Barcelona SC** (`edge_league`) |
| Real Madrid / Atletico Madrid | correct | correct (`edge_explicit`) |
| atletico + La Liga | Atletico Madrid | Atletico Madrid |
| atletico + Brasileirão/Bahia | **Atletico Madrid** (legacy default) | **Atletico Mineiro** |
| barca / real / atm | Barcelona / Real Madrid / Atletico Madrid | **unchanged aliases** |
| barcelna / real madrd | fuzzy → Barcelona / Real Madrid | fuzzy still works (edge source may `miss`; normalize OK) |
| chance | not Chapecoense (`Chance` title) | `stopword` / no club |

### Verdict

- `ENABLE_ENTITY_EDGE=0` matches legacy (edge `source=disabled`).
- `=1` disambiguates Barcelona SC vs Barcelona and Mineiro vs Madrid with league cues.
- Alias regression (**barca / real / atm**) green; PATCH-001 stopword path honored.

---

## 4) PIS before vs after (combined)

**BEFORE** = all three OFF · **AFTER** = all three ON · same base stack.

| Turn | Ask | PIS BEFORE | PIS AFTER | Δ | Driver |
|------|-----|------------|-----------|---|--------|
| S1T2 | Quem esta melhor? | 7.0 | **8.0** | +1.0 | Sport-NLG |
| S2T2 | Vale aposta? | 7.0 | **7.5** | +0.5 | Sport-NLG |
| S3T2 | E fora de casa? | 7.0 | **8.0** | +1.0 | Sport-NLG |
| S4T2 | Liverpool x Chelsea | 1.5 | **2.0** | +0.5 | episode rotate only; text still sticky |
| S4T3 | Quem esta melhor? | 2.0 | 2.0 | 0 | still Flamengo frame |

### Means

| Slice | BEFORE | AFTER | Δ |
|-------|--------|-------|---|
| Specialized FUs (S1–S3 T2) | **7.0** | **7.8** | **+0.8** |
| All critical rows above (5) | **4.9** | **5.5** | **+0.6** |
| Topic switch rows (S4 T2–T3) | **1.8** | **2.0** | **+0.2** |

Entity edge does not move these fixture transcripts (no Barcelona collision in this set); gains are NLG-led.

---

## 5) Regression estimate

| Check | Result | Risk band |
|-------|--------|-----------|
| Unit: `test_sport_nlg_001` + `test_topic_boundary_v2_001` + `test_entity_edge_001` + `test_entity_safety_patch001` | **36 passed** | **Low** |
| Soft FU continuity (Quem esta melhor?) with V2 ON | episode kept; form frame intact | **Low** |
| Opener still `partial_analysis` / analyze path | yes (NLG + edge + V2) | **Low** |
| No invented odds under Sport-NLG ON | confirmed on all probe turns | **Low** |
| Alias table (barca/real/atm) with edge ON | unchanged | **Low** |
| Stopword `chance` with edge ON | not Chapecoense | **Low** |
| New fixture user text under V2 ON | **still sticky Flamengo / Mantendo foco** | **High** (enable risk) |
| CSL fixture after V2 rotate | still shows prior fixture in note stamp | **Medium–High** |
| Title-Case NLG bet label | cosmetic | **Low** |

**Overall ship risk if flags stay default OFF:** **Low–Medium** (additive façades).  
**Overall enable risk if V2 flipped ON in prod:** **High** until sticky reply path honors new episode.

---

## 6) Commit recommendation

### Recommendation: **YES — commit behind default-OFF flags**, with conditions

| Layer | Commit code? | Flip default ON? | Condition |
|-------|--------------|------------------|-----------|
| Sport-NLG | **Yes** | **Not yet** (optional soon) | Polish Title-Case bet label; keep honesty contract |
| Entity edge | **Yes** | **Not yet** | rapidfuzz already in requirements; alias/safety green |
| Topic boundary V2 | **Yes (flag OFF)** | **No** | **Blocker:** episode_id rotates but user text still sticky-bleeds; fix ownership / CSL seed / Mantendo foco path before enable |

### Do **not** commit yet if…

- Intent is to **enable** `ENABLE_TOPIC_BOUNDARY_V2=1` as default in the same change — **NO** until S2 Liverpool transcript shows Liverpool (not Mantendo foco Flamengo).

### Blockers (enable / full perception)

1. **Topic V2 full-stack sticky bleed** after `Liverpool x Chelsea` (primary).  
2. Optional: Sport-NLG Title-Case fixture crumb on bet path.

### This audit did **not** commit or push.

---

## Paths

- Report: `observations/parallel_human_audit_001/REPORT.md`  
- Probe runner: `observations/parallel_human_audit_001/run_audit.py`
