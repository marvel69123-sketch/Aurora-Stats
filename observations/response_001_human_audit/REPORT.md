# RESPONSE-001-HUMAN-AUDIT

**MODE:** Validation only — **no code modifications**  
**QUESTION:** Do specialized answers now reach users?  
**FLAGS (ON):** `ENABLE_RESPONSE_SELECTOR=1`, `ENABLE_SPORT_INTENTS=1`, `ENABLE_CSL=1`, `ENABLE_SPORTS_LANGUAGE_LAYER=1`  
**CONTROL (OFF):** same stack with `ENABLE_RESPONSE_SELECTOR=0`  
**RUNTIME:** local TestClient · partial data / no full live odds expected  
**ARTIFACTS:** `raw_on.json`, `raw_off.json`, `raw.json`  
**BASELINE:** INTENT-001-HUMAN-AUDIT (intents stamped, shells owned replies)

---

## Verdict

**Yes — for classified follow-ups with session context.**  
Selector ON: `sport_intent_skill` authors the user-visible `executive_summary` (form / bet / home-away).  
Selector OFF: same intents stamp, but ownership shells (`Mantendo foco` / `No-bet` / `?`) still dominate.

Unclassified asks (`Como chegam?`, `Inter joga hoje?`) are **unchanged** — still soft-hold shells (intent gap, not selector gap).

---

## Perceived Intelligence Score (PIS)

Human rubric **0–10** (same bands as INTENT-001 audit):

| Band | Meaning |
|------|---------|
| 8–10 | Ask felt answered with the right specialized frame |
| 5–7 | On-topic specialized prose; thin on data but not a sticky shell |
| 3–4 | Intent may be right internally; text feels generic / sticky |
| 0–2 | Missed ask, crumb, or pure hold shell |

---

## Transcript summary (critical follow-ups)

### S1 — Compare → form

| | OFF | ON |
|--|-----|-----|
| T1 `Flamengo ou Palmeiras?` | `partial_analysis` · PIS **7.0** | same · PIS **7.0** |
| T2 `Quem esta melhor?` | intent=`recent_form` · owner=`ownership_stability` · **Mantendo foco + No-bet + ?** · PIS **4.0** | intent=`recent_form` · owner=`sport_intent_skill` · **fase recente** prose · PIS **7.5** |

**ON T2 text (prefix):**  
`Comparando a **fase recente** de **Flamengo** e **Palmeiras**…`

### S2 — Bet viability

| | OFF | ON |
|--|-----|-----|
| T2 `Vale aposta?` | intent stamped · owner=`ownership_stability` · No-bet shell / `?` · PIS **3.5** | owner=`sport_intent_skill` · **Viabilidade de aposta…** · PIS **7.0** |

### S3 — Home/away

| | OFF | ON |
|--|-----|-----|
| T2 `E fora de casa?` | intent stamped · Mantendo foco shell · PIS **4.0** | owner=`sport_intent_skill` · **mando de campo** · PIS **7.0** |

### S4 — Form phrasing gap

| | OFF | ON |
|--|-----|-----|
| T2 `Como chegam?` | no intent · ownership shell · PIS **2.5** | no intent · ownership shell · PIS **2.5** |

### S5 — Calendar gap

| | OFF | ON |
|--|-----|-----|
| T1 `Inter joga hoje?` | no intent · ownership hold · PIS **2.5** | same · PIS **2.5** |

---

## Scorecard

| Turn | Ask | Intent | Skill | Owner (ON) | Reaches user? | PIS OFF | PIS ON | Δ |
|------|-----|--------|-------|------------|---------------|---------|--------|---|
| S1T1 | Flamengo ou Palmeiras? | compare_strength | skill_compare_strength | partial_analysis | analyze path (ok) | 7.0 | 7.0 | 0 |
| S1T2 | Quem esta melhor? | recent_form | skill_recent_form | **sport_intent_skill** | **YES** | 4.0 | **7.5** | **+3.5** |
| S2T1 | Flamengo x Palmeiras | compare_strength | … | partial_analysis | analyze path | 7.0 | 7.0 | 0 |
| S2T2 | Vale aposta? | bet_viability | skill_bet_viability | **sport_intent_skill** | **YES** | 3.5 | **7.0** | **+3.5** |
| S3T1 | Flamengo x Palmeiras | compare_strength | … | partial_analysis | analyze path | 7.0 | 7.0 | 0 |
| S3T2 | E fora de casa? | home_away_analysis | skill_home_away | **sport_intent_skill** | **YES** | 4.0 | **7.0** | **+3.0** |
| S4T2 | Como chegam? | — | — | ownership_stability | NO | 2.5 | 2.5 | 0 |
| S5T1 | Inter joga hoje? | — | — | ownership_stability | NO | 2.5 | 2.5 | 0 |

**Follow-up mean PIS (S1T2, S2T2, S3T2, S4T2):**  
OFF **3.5** → ON **6.1** (**+2.6**)

**Specialized FU mean (only turns with intent stamp):**  
OFF **3.8** → ON **7.2** (**+3.4**)

---

## Does specialized answer reach the user?

| Criterion | OFF | ON |
|-----------|-----|-----|
| `response_owner == sport_intent_skill` on form/bet/home FUs | 0/3 | **3/3** |
| User text names the skill frame (fase / viabilidade / mando) | 0/3 | **3/3** |
| Free of Mantendo foco sticky shell on those FUs | 0/3 | **3/3** |
| Free of honesty No-bet *prefix shell* on those FUs | 0/3 | **3/3** |
| Opener still analyze (no skill steal) | yes | **yes** |

**Answer:** Specialized answers **reach users when sport intent classifies and session context exists.** Selector fixed the OWNER-001 failure mode for S1–S3 follow-ups.

---

## Failures (unchanged / out of selector scope)

1. **`Como chegam?`** — no `sport_intent` → no skill candidate → soft hold still wins.  
2. **`Inter joga hoje?`** — calendar not authored by this layer (by design); pattern/intent still weak → hold.  
3. Skill prose is **template-honest** (no invented xG/odds) — smarter frame, not richer engine data.

---

## Regressions

| Check | Result |
|-------|--------|
| Fresh fixture / compare opener stolen by skill | **No** — S1–S4 T1 remain `analyze_match` / `partial_analysis` |
| Continuity short-FU path broken | Not exercised here; OFF path still available via flag |
| OFF mode still shells (control) | **Yes** — confirms delta is selector, not CSL/intent alone |

---

## Comparison to INTENT-001-HUMAN-AUDIT

| Era | What improved | What user felt |
|-----|---------------|----------------|
| INTENT-001 only | Metadata / routing | Barely — shells owned replies |
| RESPONSE-001 + selector | Skill **authors** `executive_summary` | Clear specialized frames on S1–S3 FUs |

---

## Conclusion

| Question | Result |
|----------|--------|
| Do specialized answers reach users? | **Yes, when intent fires + session ready** |
| Human perception on those FUs | **Materially up** (~+3 PIS) |
| Remaining gap | Unclassified intents + calendar; deeper data still engine-bound |

**Recommendation:** Keep `ENABLE_RESPONSE_SELECTOR=1`. Next perception gains are **intent coverage** (`Como chegam?`, calendar phrasing), not another ownership race.
