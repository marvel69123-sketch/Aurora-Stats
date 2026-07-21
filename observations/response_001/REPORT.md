# RESPONSE-001 — Shell ownership → candidate-response architecture

**Type:** Investigation / architecture proposal (no code changes)  
**Date:** 2026-07-21  
**Depends on:** OWNER-001 (`observations/owner_001/REPORT.md`)  
**Inspirations:** Athena Response Generators, Rasa Actions / Response Selector, Priority Response Selection

---

## Verdict

**Recommend replacing the early-claim / soft-hold race with a candidate-response + priority selector** (Athena-shaped, Rasa/nl_router–simple ranking — **not** a neural ranker in v1).

| Approach | Cost vs status quo | Recommendation |
|----------|--------------------|----------------|
| One-off skill patch (OWNER-001 Option A) | Cheapest **for a single skill** (~2–4 eng-days) | Do only if scope stays one intent |
| Serial patches (skill + honesty + OS bypass × N) | Compounds fast; fights FROZEN surfaces | Reject as strategy |
| Full Athena (BERT response ranker + open RG swarm) | Weeks–months; high eval risk | Overkill now |
| **Candidate pool + deterministic priority select** | **~1.5–3 eng-weeks MVP**; lower long-run cost than patching ownership | **Adopt** |

Per rule (*if replacement is cheaper than patching, recommend replacement*): **replacement of the selection mechanism is cheaper than continued ownership patching** once more than one specialized skill/sink must reach the user. Shell generators stay as **low-priority candidates**, not exclusive claimers.

---

## 1. Complexity estimate

### Current system (problem shape)

- Copilot router uses **first-payload-wins**: ~28 `if payload is None` gates; early claimers set `skipped_nl` and starve later engines.
- Soft holds (`ownership_stability._build_hold_payload`, continuity crumbs) are **responses**, not fallbacks.
- INTENT-001 skills rewrite **messages only** — never emit candidates (OWNER-001).
- Late honesty prefixes Mantendo foco / No-bet onto whatever won.
- Existing related pattern: `nl_router.py` already does **multi-classifier → sort by (confidence, priority)** — intent-level only, not response-level.

### Inspirations → Aurora mapping

| Inspiration | Core idea | Aurora fit |
|-------------|-----------|------------|
| **Athena RGs** | DM dispatches contracts → many Response Generators fill a **pool** → ranker picks one | Map claimers → generators; replace first-wins with pool |
| **Athena ranker** | BERT / annotated preference | **Defer** — no labeled pool yet; use rules first |
| **Rasa Actions** | Action computes; dispatcher utters; slots carry state | Skills/analyze = actions that **return** a candidate payload, not rewrite-only |
| **Rasa Response Selector** | Embed & pick among retrieval responses | Optional later for template variants |
| **Priority selection** | Explicit priority table + confidence | Mirror `nl_router` at **response** layer |

### Effort bands

| Workstream | Size | Notes |
|------------|------|-------|
| `ResponseCandidate` type + collector + priority table | S–M | ~150–300 LOC new module |
| Wrap 6–8 claimers as generators (clarify, continuity, pronoun, advanced, SCG, OS hold, sport_intent, analyze stub) | M | **Wrap, don’t rewrite FROZEN cores** |
| Router: collect → select once → single lock | M | Touch `copilot_unified_router` claim band (~1976–2270) behind flag |
| Honesty / soft sections as **post-select polish** (not authors) | S | Gate prefixes when winner is skill/analyze |
| Tests + eval harness (FU form/compare, lock regression) | M | Highest calendar risk |
| Neural Athena-RR | XL | Out of MVP |

**MVP complexity: Medium (≈ 1.5–3 engineer-weeks)** with feature flag dual-path.  
**Full Athena parity: Extra Large (≫ 6 weeks)** — not recommended now.

**vs patching:** One skill sink ≈ 2–4 days. Three skills + honesty exceptions + OS carve-outs ≈ same calendar as MVP **with worse architecture**. Replacement wins past ~2 specialized sinks.

---

## 2. Regression risk

| Area | Risk | Why | Mitigation |
|------|------|-----|------------|
| Sticky SPORT lock / anti-GA steal | **High** | Soft hold today *is* the anti-steal mechanism | Keep OS/SCG as generators; priority ≥ “hold” when no better candidate; preserve `should_block_ga` as **eligibility**, not author |
| Short FU (placar / mercados / e dele?) | **High** | Continuity early-claim is load-bearing | Continuity generators keep high priority for matched kinds |
| Analyze / GA first turns | **Medium** | Claim order changes | Flag off by default; golden sessions for openers |
| Honesty / No-bet UX | **Medium** | Prefix can still dominate thin winners | Skip assumption prefix when `generator_id` ∈ skill/analyze |
| Eval HPS / success rate | **Medium** | Human-audit FUs may improve; unrelated turns may shift | Diff eval ON vs OFF; freeze OS internals |
| Latency | **Low–Medium** | Parallel generators vs serial early-exit | Run only eligible generators (Athena-style contract); soft hold is cheap |
| FROZEN module edits | **Policy** | Direct OS edits may be forbidden | Wrapper adapters only |

**Overall regression risk for MVP: Medium–High** if cut over without flag; **Medium** with `ENABLE_RESPONSE_CANDIDATES` dual-path + eval gate.

Risk of **not** replacing: skills remain metadata-only; every new intent re-hits OWNER-001 failure mode (certain).

---

## 3. Replacement proposal

### Target architecture

```
NLU / SLL / CSL / SportIntent (classify + optional rewrite)
        │
        ▼
┌─────────────────── Response Generator bus ───────────────────┐
│  Each eligible generator returns 0..1 ResponseCandidate       │
│  { generator_id, priority, confidence, payload,               │
│    eligibility_notes }                                        │
│                                                               │
│  Generators (v1):                                             │
│   clarify_entity_v2 / ambiguous_guard                         │
│   sport_intent_skill     (NEW — real executive_summary)       │
│   continuity_short_fu / pronoun / advanced_football           │
│   analyze_match / match_opinion (when scheduled)              │
│   sport_continuity_hold / ownership_soft_hold   ← shells      │
│   natural / HCE / GA                                          │
└───────────────────────────────┬───────────────────────────────┘
                                ▼
                    PriorityResponseSelector
                    (priority desc, then confidence;
                     hard vetoes: fiction, clarify-required)
                                ▼
                    mark_owner + rewrite_lock (once)
                                ▼
                    honesty / soft sections (polish only)
                                ▼
                    CopilotResponse
```

### Priority table (v1 draft)

| Priority band | Generators | Role |
|---------------|------------|------|
| 100 | Clarify / ambiguous / fiction hard | Safety first |
| 90 | `sport_intent_skill` (conf ≥ 0.75 + anchor) | Specialized answers reach user |
| 80 | Continuity kind match / pronoun / advanced | Existing good short FUs |
| 70 | Analyze / opinion (when invoked) | Full sport engines |
| 40 | Soft hold / SCG minimal hold | **Shell = fallback candidate** |
| 20 | Natural / HCE / GA | Social / repair |
| 0 | Empty / “?” | Never win if any alternative |

Shells stay in the system but **cannot win** when a band ≥ 80 candidate exists — this is the OWNER-001 fix without deleting FROZEN hold logic.

### Athena / Rasa mapping (concrete)

| Pattern | Aurora MVP |
|---------|------------|
| Athena contract to RGs | `eligible(ctx, message) -> bool` per generator |
| Athena response pool | `list[ResponseCandidate]` |
| Athena neural ranker | **Deferred**; use priority + confidence |
| Rasa Action | Skill builds payload (events/slots ≈ ctx stamps) |
| Rasa utter | Selector commits one candidate → `payload` |
| Priority selection | Same sort keys as `nl_router` |

### Migration plan (minimal blast radius)

1. **Flag** `ENABLE_RESPONSE_CANDIDATES` (default off).  
2. Add `src/conversation/response_candidates.py` (type, register, select).  
3. Adapter wrappers around existing try_* functions: on miss → no candidate; on hit → candidate with fixed priority.  
4. **New** `sport_intent` generator: emit real summary for `recent_form` / `compare_strength` / … (closes OWNER-001).  
5. Router path: if flag → collect eligible → select → skip first-wins band; else legacy.  
6. Eval: OWNER-001 FU suite + continuity regression + lock/GA-steal cases.  
7. Flip default on after eval gate; deprecate soft hold as exclusive claimer (keep as P40 generator).

### What not to do

- Do not delete `ownership_stability` / SCG in v1.  
- Do not ship BERT ranker before a labeled candidate corpus.  
- Do not keep message-only skills expecting ownership to “notice” them.

---

## Cost comparison (decision rule)

```
Patch one skill sink:     ████░░░░░░  cheap, debt++
Patch N skills + honesty: ██████████  ≥ MVP cost, worse shape
Candidate MVP:            ███████░░░  one-time, unlocks N skills
Full Athena-RR:           ████████████████  not cheaper than patching
```

**Recommendation:** Replace **shell-first ownership selection** with **candidate + priority selection**. Treat soft holds as low-priority candidates. Implement sport-intent as a high-priority generator. Defer neural ranking.

That replacement is **cheaper than continued ownership patching** for the product goal (specialized skills reaching users). A single Option A patch remains cheaper only for a one-skill tactical hotfix — not as the architecture strategy.

---

## Deliverable checklist

| # | Deliverable | Location |
|---|-------------|----------|
| 1 | Complexity estimate | §1 — MVP **M (1.5–3 wks)**; full Athena **XL** |
| 2 | Regression risk | §2 — **Medium–High** cutover / **Medium** with flag |
| 3 | Replacement proposal | §3 — candidate bus + priority table + migration |

---

## References

- OWNER-001: `observations/owner_001/REPORT.md`  
- Athena 2.0 RG + pool + ranker: [arxiv 2308.01887](https://arxiv.org/pdf/2308.01887), [Athena-RR](https://arxiv.org/pdf/2302.04424)  
- Rasa custom actions / responses: [Rasa docs — custom actions](https://rasa.com/docs/pro/build/custom-actions/), [responses](https://rasa.com/docs/reference/primitives/responses/)  
- Local priority precedent: `artifacts/aurora/src/core/nl_router.py` (confidence × priority sort)
