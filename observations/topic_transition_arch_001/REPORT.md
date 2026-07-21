# TOPIC-TRANSITION-ARCH-001 — Public transition layer investigation

**Type:** Investigation only — **NO PRODUCT CODE CHANGES**  
**Date:** 2026-07-21  
**Scope:** Transition *decision* layer only (new fixture / follow-up keep-episode / new episode).  
**Out of scope:** Full CSL/SRF/conversational memory replacement (deferred TOPIC-STATE-ARCH-001).  
**Adjacent (not reopened):** sticky multi-writer bleed cleanup, ownership_stability, sport_continuity_guard, response_selector, frozen sports engines.

**Evidence sources:**
- Code: `artifacts/aurora/src/conversation/topic_boundary_v2.py`, `aurora/src/conversation/brain_authority.py`, `aurora/src/core/followup_guard.py`, `aurora/src/core/follow_up_engine.py`, `aurora/src/conversation/message_intelligence.py`, `aurora/src/routers/copilot_unified_router.py`, `artifacts/aurora/src/routers/copilot_unified_router.py`
- Prior research: `artifacts/aurora/observations/arch_003/ARCHITECTURE_RESEARCH.md`, `observations/sticky_bleed_001/REPORT.md`, `observations/topic_boundary_002/REPORT.md`
- Public docs (fetched 2026-07-21): LangGraph Graph API (`docs.langchain.com/oss/python/langgraph/graph-api`), Rasa Events / `DialogueStateTracker` docs (`rasa.com/docs/...`)

---

## 1. Current Aurora transition surface (facts from code)

### 1.1 Decision outcomes that matter

| Decision | Meaning | Primary detectors today |
|----------|---------|-------------------------|
| **New fixture** | Message names a different `A x B` than sticky prior → do **not** reuse follow-up context; force analyze / new fixture ctx | `aurora/src/core/followup_guard.py` → `decide_followup_reuse` + `start_new_fixture_context`; also V2 `reason=new_fixture` |
| **Soft FU / keep episode** | No new teams (or soft PT phrases) → stay on same episode | V2 `_SOFT_FOLLOWUP` + short-message heuristic; `brain_authority.compute_boundary_score` soft regex; `follow_up_engine.is_followup` |
| **New episode / low overlap** | Entity Jaccard &lt; 0.34 or new fixture vs prior → boundary clear + episode rotate | `artifacts/aurora/src/conversation/topic_boundary_v2.py` → `detect_episode_boundary` |

There is **no single owner**. The same semantic (“should this turn leave the prior sport subject?”) is computed in at least four places with overlapping regex/heuristics.

### 1.2 Topic Boundary V2 (canonical episode classifier — flag-gated)

**Path:** `artifacts/aurora/src/conversation/topic_boundary_v2.py`  
**Flag:** `ENABLE_TOPIC_BOUNDARY_V2` (default OFF).  
**Note:** Present under `artifacts/aurora/…` and wired in `artifacts/aurora/src/routers/copilot_unified_router.py`. Live tree `aurora/src/` still uses the older `brain_authority` boundary path and does **not** contain `topic_boundary_v2.py` as of this investigation.

`detect_episode_boundary(message, ctx)` (pure, fail-open):

1. Skip if flag off or `has_prior_episode(ctx)` false.
2. Collect **prior** teams/fixture from sticky keys (`last_home`/`last_away`/`last_match`, focus, continuity, sport_anchor) — intentionally **not** live CSL first (CSL may already be overwritten).
3. Collect **current** teams from SLL clubs + `_FIXTURE_PHRASE` / `_COMPARE_PHRASE` / `_SINGLE_TEAM_ASK`.
4. **Soft FU keep-episode:** no current entities and no new fixture → if `_SOFT_FOLLOWUP` matches **or** message ≤ 6 tokens → `reason=soft_followup_same_episode`.
5. **New fixture:** `extract_fixture_phrase` vs `prior_episode_fixture` not equivalent → `is_boundary=True`, `reason=new_fixture`.
6. **Low overlap:** Jaccard on folded names &lt; `_LOW_OVERLAP` (0.34) → `reason=low_entity_overlap` (or `new_fixture_no_prior_label`).
7. Same fixture restated / overlap OK → keep.

Apply path (`apply_episode_boundary`) mutates session: clear fixture context, expire sport anchor, release owner lock (public APIs), clear orphan referents, bump CSL `episode_id` + replace subject. That is **materialization**, not classification — and sticky-bleed failures were mostly **ordering + incomplete cleanup**, not “wrong Jaccard” (see STICKY-BLEED-001).

### 1.3 Parallel / legacy transition detectors

| Module | Path | Role |
|--------|------|------|
| Brain Authority boundary | `aurora/src/conversation/brain_authority.py` — `compute_boundary_score` / `should_clear_topic_boundary` / `apply_topic_boundary` | Soft FU keep; explicit `x\|vs` → clear; entity pivot vs prior/focus |
| Follow-up reuse guard | `aurora/src/core/followup_guard.py` — `decide_followup_reuse` | Named fixture vs `last_*` → `reuse` bool + `new_fixture` |
| Follow-up phrase engine | `aurora/src/core/follow_up_engine.py` — `is_followup` | Portuguese market/soft FU **phrasing** (not episode ID) |
| Legacy topic switch | `aurora/src/conversation/message_intelligence.py` — `is_topic_switch` | Regex-only explicit `A x B` |
| V2 switch helper | `topic_boundary_v2.is_topic_switch_v2` | Narrow replace for `is_topic_switch` when flag ON |

### 1.4 Router order (decision surface placement)

**Artifacts (V2-aware) —** `artifacts/aurora/src/routers/copilot_unified_router.py`:

```
SLL → TopicBoundaryV2 → CSL → Sport Intent → … → (later) brain_authority boundary / focus
     → followup_guard decide_followup_reuse → QuickFollowUpGate (is_followup + reuse)
```

**Live `aurora/src/routers/copilot_unified_router.py`:** no early `apply_topic_boundary_v2`; mid-pipeline `brain_authority.should_clear_topic_boundary`; then `decide_followup_reuse` / `is_followup` gates (~0b block).

### 1.5 Decision surface: public solution vs Aurora-specific

| Concern | Must stay Aurora-specific | Could be generic infra |
|---------|---------------------------|------------------------|
| Club name folding / aliases | Yes (`fold`, SLL clubs, entity resolver) | No drop-in |
| PT soft FU phrases (`e os gols`, `quem está melhor`, …) | Yes | No mature PT sport lexicon in LangGraph/Rasa |
| Sport fixture phrases (`A x B` / vs / versus / ou / contra) | Yes (domain regex + cleaner) | Partially patternable, still custom |
| Jaccard / overlap threshold vs sticky prior | Policy choice (Aurora) | Framework won’t pick 0.34 |
| Session `ctx` keys (`last_*`, CSL, SRF, anchors) | Aurora ownership | Store/checkpointer only |
| Orchestration (run classifier **before** CSL rewrite) | Process rule | LangGraph edges *could* enforce order if Aurora rewired |
| Slots / event log / restart semantics | Optional | Rasa tracker / LangGraph state |

**Bottom line:** the *classifier* is domain rules + entity geometry. Frameworks supply **state containers and routing graphs**, not a ready-made `new_fixture | soft_fu | new_episode` API for Brazilian football chat.

---

## 2. Comparative: LangGraph vs Rasa (+ optional third)

### 2.1 LangGraph (State Architecture)

**What it actually provides (docs):** typed shared `State` (TypedDict/Pydantic), nodes, **conditional edges** (router function → next node name), reducers, checkpointers (`thread_id`), interrupts. It is a **stateful workflow orchestrator**, not a dialogue episode classifier.

| Question | Answer |
|----------|--------|
| Solves (1) new fixture detection? | **No out of the box.** You would implement Aurora’s fixture parse + equivalence as a **node** (or edge predicate). LangGraph only hosts that function. |
| Solves (2) FU vs new episode? | **No.** Conditional edges route *after* you decide; they do not detect soft FU or Jaccard overlap. |
| Does **not** solve | Sticky multi-writer bleed, honesty prefixes, analyze correctness, frozen engines, Portuguese sport lexicon. |
| Integration with `ctx` + FastAPI/copilot | High. Would wrap or replace `copilot_unified_router` turn pipeline with a compiled graph; map `session_id` → `thread_id`; sync Aurora `ctx` dict ↔ graph state each turn. Dual SoT risk during migration. |
| Regression risk | **High** if used as router replacement; **medium** if a tiny subgraph only wraps one classifier node (still adds dependency + invoke path). |
| Maintenance cost | Medium–high: LangGraph versioning, checkpointer ops, team learning curve — for little classifier gain. |
| Frozen sports modules | Compatible **if** graph only calls them as leaf nodes and never owns methodology/market/confidence. Risk is accidental “orchestrate everything” scope creep. |

**Partial-adoption honesty:** “Adopt LangGraph for transition only” ≈ put `detect_episode_boundary` inside a node. The public product does not own the decision quality.

### 2.2 Rasa Dialogue Tracker

**What it actually provides (docs):** `DialogueStateTracker` applies an **event log** (`UserUttered`, `SlotSet`, `SessionStarted`, `Restarted`, `AllSlotsReset`, flow/agent events, etc.). `FollowupAction` means **enqueue the next bot action**, bypassing action prediction — **not** “user utterance is a conversational follow-up about the same fixture.” Session restart / slot reset are **storage/control** primitives, not sport episode classifiers.

| Question | Answer |
|----------|--------|
| Solves (1) new fixture detection? | **No.** Slots can *store* `home`/`away` after Aurora fills them; Rasa does not detect `Liverpool x Chelsea` vs sticky Flamengo. |
| Solves (2) FU vs new episode? | **No** as a drop-in classifier. You could train intents/stories or use flows, but that is a **second NLU + dialogue stack** beside Aurora’s router — not a thin transition API. |
| Does **not** solve | Sticky bleed, honesty, analyze correctness, frozen engines. Also does not replace PT soft-FU regex without training data. |
| Integration with `ctx` + FastAPI/copilot | **Very high** for full Rasa; **high even for “tracker only”** (domain, events, tracker store vs Aurora SQLite/`conversation_manager`). Dual trackers = dual bugs. |
| Regression risk | **Very high** if Rasa predicts actions; **high** if tracker becomes parallel SoT for slots already in CSL/`last_*`. |
| Maintenance cost | High (Rasa/Pro lifecycle, NLU training, event schema). Overkill for three enum outcomes. |
| Frozen sports modules | Compatible only if Rasa never owns analyze/market path. Temptation to put sport stories in Rasa fights the freeze. |

**Partial-adoption honesty:** Rasa’s strength is **typed slots + event-sourced dialogue state** (already the conceptual model behind CSL — ARCH-003). It is a poor fit for *only* transition classification without pulling in the assistant runtime.

### 2.3 Optional third (transition-classification only)

| Candidate | Maturity | Fit for Aurora transition-only |
|-----------|----------|--------------------------------|
| `mhcoen/episodic` (topic segmentation / memory) | Low (~5★); LLM-memory oriented | Concept borrow only (ARCH-003 already did). Not a mature classifier API. |
| `dialogue-memory-pipeline` / Nemori | Alpha / research; LLM boundary judges | Latency, non-determinism, weak PT sport control — **worse** than deterministic Jaccard for betting UX. |
| Athena Topic Manager / Episodic *patterns* | Research / patterns | Already inspired V2; borrow rules, not a product dependency. |

**No mature public library clearly beats a centralized Aurora `EpisodeTransition` module for this narrow decision.** Generic DST and LLM segmenters do not ship football fixture geometry + PT soft-FU policy.

---

## 3. What “stop patching hidden states” means architecturally

Pain is not “we lack LangGraph/Rasa.” Pain is **multiple writers + multiple classifiers** deciding episode continuity independently:

- V2 / brain_authority / followup_guard / `is_topic_switch` / sport-intent rewrite / CSL note / SRF honesty  
- Order bugs masquerade as “boundary didn’t fire” (STICKY-BLEED-001)

**Architectural meaning of the user’s ask (narrow):**

1. **Single transition owner** — one pure function, one enum, one reason string, called **once** at a fixed pipeline point (before subject rewrite).  
2. **Downstream consumers** — follow-up gate, CSL bump, SRF clear, analyze force — **read** that decision; they do not re-detect.  
3. **Do not** equate “single owner” with “replace all conversational memory” (that is TOPIC-STATE-ARCH-001 / full CSL).

```
  message + ctx
        │
        ▼
  EpisodeTransition.decide
        │
        ▼
  {KEEP_EPISODE | NEW_FIXTURE | NEW_EPISODE, reason}
        │
        ├──► FU reuse gate (consume)
        ├──► materialize clear (single apply)
        └──► analyze force (consume)
```

Public frameworks can host this box; they do not *be* the box for Aurora sport rules.

---

## 4. Conclusion

```
FACT:
Aurora already implements the transition classifier as domain rules (fixture phrase + folded Jaccard + PT soft-FU) in topic_boundary_v2 / brain_authority / followup_guard, but ownership is split across the copilot router. LangGraph provides orchestration/checkpointers; Rasa DialogueStateTracker provides evented slots/session restart — neither ships a mature drop-in API that classifies new_fixture vs soft_FU keep-episode vs new_episode for PT football without re-implementing Aurora’s rules inside the framework. Sticky bleed evidence points to multi-writer ordering/cleanup, not absence of a public DST product.

HYPOTHESIS:
Centralizing into one Aurora EpisodeTransition decide+apply API (consuming SLL entities, writing one ctx stamp) removes the incentive to patch hidden states, at lower regression risk than adopting LangGraph or Rasa runtimes. Adopting either publicly for “transition only” would still leave ≥90% of decision quality in custom code while adding dual SoT and dependency tax.

RISKS:
(1) Partial LangGraph/Rasa adoption becomes scope creep into full router/memory rewrite (TOPIC-STATE-ARCH-001 by stealth).
(2) Leaving dual detectors (V2 + brain_authority + followup_guard) after “centralize” advice → same class of bugs.
(3) LLM episode segmenters as third option increase non-determinism on betting-critical subject switches.
(4) artifacts vs live tree drift (V2 only under artifacts/) — centralization must pick one deployable surface carefully when implementation is later approved.

RECOMMENDATION:
KEEP CUSTOM TRANSITION (CENTRALIZE)
```

### Framing vs partial / full adoption

| Option | Verdict |
|--------|---------|
| **KEEP CUSTOM TRANSITION (CENTRALIZE)** | **Chosen.** Public solutions do not meaningfully beat a single Aurora transition module; sport rules remain custom either way. |
| ADOPT PUBLIC TRANSITION LAYER (PARTIAL) | Rejected for now. No credible “classifier-only” product; wrapping custom rules in LangGraph/Rasa is ceremony without decision leverage. |
| ADOPT PUBLIC STATE MACHINE (BROADER) | Out of scope; ARCH-003 already advised WRAP concepts, not runtime replacement. Revisit only if rewriting the whole copilot turn graph. |

### If forced to pick a public fit later

**LangGraph is the better fit** for *hosting* a single transition node + enforcing call order (conditional edges, typed state), **not** Rasa. Rasa’s tracker is stronger for full DST/slots/stories — wrong weight class for transition-classification-only and higher integration cost with FastAPI/copilot.

### Adjacent (not reopened)

Full CSL/SRF replacement remains deferred (TOPIC-STATE-ARCH-001). Transition centralization is a **prerequisite hygiene** step; it does not require adopting Rasa/LangGraph memory.
