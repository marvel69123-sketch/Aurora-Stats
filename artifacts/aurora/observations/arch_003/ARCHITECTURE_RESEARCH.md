# AURORA-ARCH-003 — Mature Utility Layer Research

**TYPE:** INVESTIGATION (no engine rewrites)  
**PRIORITY:** P0  
**MODE:** Design / Borrow map  
**CONSTRAINT:** Aurora engines FROZEN. Goal = replace defective *utility* layers with mature solutions.  
**PRIOR ART:** ARCH-001 (SLL+CSL façades), PATCH-002A (SLL shipped).

---

## Executive verdict

| Focus | Verdict | Action |
|-------|---------|--------|
| 1. Conversation state | **WRAP → CSL** | Borrow Rasa slots + LangGraph TypedDict; do **not** adopt Rasa/LangGraph runtime |
| 2. Follow-up understanding | **WRAP** | Borrow Athena rule-coref + CANARD rewrite *pattern*; keep domain FU engines |
| 3. Context switching | **WRAP** (narrow **REPLACE**) | Borrow Episodic/Athena topic boundaries; replace only brittle regex switcher |
| 4. Calendar queries | **REPLACE** date NLU; **WRAP** UX | Replace hoje/amanhã regex with `dateparser`; keep Natural calendar replies |

**Do not replace:** FROZEN ownership / sport continuity / ambiguous / fiction guards, or methodology / confidence / market / intelligence / learning engines.  
**Already KEEP:** SLL (`sports_language.py`) + Entity Safety (`entity_safety.py`).

---

## Candidate repositories

### Tier A — borrow concepts / small adapters (recommended)

| # | Repo | Stars / maturity | Why it matters for Aurora |
|---|------|------------------|---------------------------|
| A1 | [RasaHQ/rasa](https://github.com/RasaHQ/rasa) | ~21k · production DST | Typed **slots**, `DialogueStateTracker`, Forms/ActiveLoop, TrackerStore persistence |
| A2 | [langchain-ai/langgraph](https://github.com/langchain-ai/langgraph) | Mature · widely used | `TypedDict` state, **reducers**, checkpointers (`thread_id`), conditional edges = phases |
| A3 | [scrapinghub/dateparser](https://github.com/scrapinghub/dateparser) | ~2.8k · 200+ locales | PT/BR relative dates (`amanhã`, `próxima segunda`) without Haskell ops |
| A4 | [facebook/duckling](https://github.com/facebook/duckling) | ~4.3k · industry NLU | Gold-standard time/duration entities; use via HTTP **or** concepts only |
| A5 | Athena 2.0 discourse model ([arXiv:2308.01887](https://arxiv.org/abs/2308.01887)) | Research → proven in live traffic | **Rule-based coref** (1 prior turn) beats spaCy/AllenNLP for short chat pronouns |
| A6 | [mhcoen/episodic](https://github.com/mhcoen/episodic) | Active · topic segmentation | Topic detect, subject-change boundaries, topic reactivation |
| A7 | AWS sample [`followup.py` contextualize](https://github.com/aws-samples/sample-semantic-layer-structured/blob/main/agents/shared/followup.py) | Pattern, not framework | Rewrite ellipsis/pronoun follow-ups into self-contained questions **before** router |

### Tier B — optional / heavier (flagged, not default)

| # | Repo | Note |
|---|------|------|
| B1 | [castorini/t5-base-canard](https://huggingface.co/castorini/t5-base-canard) + CANARD | Neural query rewrite; latency/GPU cost; PT coverage weak |
| B2 | [unpod-ai/superdialog](https://github.com/unpod-ai/superdialog) | Pure dialog FSM; useful for CSL phase graph, not drop-in |
| B3 | [NikolasMarkou/fsm_llm](https://github.com/NikolasMarkou/fsm_llm) | 2-pass extract→transition; small community |
| B4 | [Mazyod/puckling](https://github.com/Mazyod/puckling) | Python Duckling; **EN/AR only** → poor BR fit |
| B5 | [lexisark/ark-chatbot](https://github.com/lexisark/ark-chatbot) / LATRACE | Long-term entity memory; overkill vs sport session TTL |
| B6 | [msg-systems/coreferee](https://github.com/msg-systems/coreferee) | spaCy coref; **no Portuguese**, spaCy ≤3.5 lock → reject as default |

### Explicit non-adoptions (as runtime)

- Full **Rasa** training / stories runtime — would rewrite `copilot_unified_router`
- Full **LangGraph** as orchestrator — same risk
- **LangChain classic memory** as dependency — deprecated path; borrow *window/entity* ideas only

---

## Exact files / components to borrow

### 1) Conversation state → **WRAP as CSL façade**

| Borrow from | Component / idea | Aurora target |
|-------------|------------------|---------------|
| Rasa | `DialogueStateTracker` (`rasa/core/trackers.py`), `slots`, `active_loop` | Typed slots: `{home, away, focus_team, date_hint, ask_kind, phase}` |
| Rasa | Forms / slot mappings / `influence_conversation: false` | Clarify until slots ready; slots must not steal sport engine authority |
| Rasa | TrackerStore (SQL/Redis/InMemory) | Harden `conversation_context` multi-node gap |
| LangGraph | `TypedDict` state + `Annotated[..., reducer]` | Single authoritative state schema; append histories, replace slots |
| LangGraph | Checkpointer + `thread_id` | Map to `session_id`; optional SQLite saver later |
| SuperDialog | `switch_flow` / SessionWorker locks | Phase transitions under concurrency |

**Aurora modules:**

| Module | Decision | Why |
|--------|----------|-----|
| `conversation_context.py` | **KEEP** | Session shell + SQLite fallback is fine as store |
| `sport_referent_frame.py` | **KEEP** | Clean consumer frame; already avoids FROZEN blobs |
| `conversation_state.py` | **WRAP** | Become CSL consumer; stop being a second nickname SoT |
| `state_driven_resolution.py` | **REPLACE** nickname path; **WRAP** clarify | Nick maps → SLL only (done in 002A); keep clarify UX |
| `short_conversation_memory.py` | **WRAP** | Keep early pronoun resolve; feed from CSL slots |
| `conversation_focus.py` | **WRAP** | Focus as slot projection, not parallel memory |
| `human_conversation_state.py` / `perception_conversation_state.py` | **WRAP** | Merge under CSL phase; keep anti-sticky rules |
| `context_reinforcement.py` | **KEEP** | Soft scores; low risk |
| `ownership_stability.py` / `sport_continuity_guard.py` | **KEEP (FROZEN)** | Advise only via `can_dispatch` |

### 2) Follow-up understanding → **WRAP**

| Borrow from | Component / idea | Aurora target |
|-------------|------------------|---------------|
| Athena 2.0 | Rule coref: last-turn entities + pronoun gender/number | Strengthen `pronoun_continuity` without spaCy |
| AWS followup.py | `contextualize_question` (detect FU → rewrite standalone) | Thin pre-router rewriter behind flag |
| CANARD / T5-QR | Dataset + rewrite objective (optional Tier B) | Offline eval corpus for FU quality |
| Rasa | Slot carry-over across turns | CSL holds `focus_team` / fixture across FU |

**Aurora modules:**

| Module | Decision | Why |
|--------|----------|-----|
| `core/follow_up_engine.py` | **WRAP** | Domain market FU works; wrap with contextualize-before-match |
| `conversation_continuity.py` | **WRAP** | Keep 1–3 turn window; expose as CSL phase `FOLLOWUP` |
| `pronoun_continuity.py` | **WRAP** | Adopt Athena 1-turn rule patterns; reject coreferee default |
| `advanced_football_continuity.py` | **KEEP** | Domain metric lexicon unique to Aurora |
| `human_inference.py` | **WRAP** (narrow fix later) | Strong-verb SoT useful; multi-word `_PAIR` is defective → prefer SLL compact tokens (already) |
| `short_answer_resolver.py` | **KEEP** | Conservative yes/no mapping |
| FROZEN OS/SCG | **KEEP** | FU reclaim / GA block stay |

### 3) Context switching → **WRAP** + narrow **REPLACE**

| Borrow from | Component / idea | Aurora target |
|-------------|------------------|---------------|
| Episodic | Topic detect + subject-change boundary + reactivation | Replace brittle `A x B`-only switch regex |
| Athena Topic Manager | Explicit topic class per turn + entity→topic link | CSL `phase` + `topic_id` |
| LangGraph | Conditional edges / interrupt_before | `CLARIFY` gate before engines |
| SuperDialog | `switch_flow` | Hard vs soft switch policy |

**Aurora modules:**

| Module | Decision | Why |
|--------|----------|-----|
| `message_intelligence.is_topic_switch` | **REPLACE** (narrow) | Regex-only `A x B` misses slang compares / soft digressions |
| `dialog_mode.py` | **WRAP** | Modes map cleanly to CSL phases |
| `master_intent_router.py` | **WRAP** | Keep utility-vs-sport; SLL already fixed `short_general` on EU compares |
| `brain_authority.py` topic boundary | **WRAP** | Keep SoT gates; read CSL slots |
| `fiction_context_jump_guard.py` | **KEEP (FROZEN)** | Defensive scrub only |
| `ambiguous_context_guard.py` | **KEEP (FROZEN)** | Clarify underspec opens |

### 4) Calendar queries → **REPLACE** date NLU; **WRAP** UX

| Borrow from | Component / idea | Aurora target |
|-------------|------------------|---------------|
| **dateparser** | `parse` / `search_dates`, locales `pt`/`pt-BR`, relative dates | Single SoT for `hoje`/`amanhã`/`próxima segunda`/`semana que vem` |
| Duckling | Time grain + intervals (concepts) | Optional HTTP sidecar later; not default (ops) |
| Rasa DucklingEntityExtractor | Dimension filter + slot fill pattern | How to attach `date_hint` slot without owning UX |
| puckling | Avoid for BR | EN/AR only |

**Aurora modules:**

| Module | Decision | Why |
|--------|----------|-----|
| `natural_conversation.py` date regex block | **REPLACE** (date extract only) | Brittle `hoje`/`amanha` lists; miss richer PT |
| `natural_conversation.py` reply builders / `_fetch_fixtures_for_date` | **WRAP / KEEP** | UX + fetch already correct; feed ISO dates from dateparser |
| `human_inference.py` calendar branch | **WRAP** | Keep opinion-before-calendar priority; consume `date_hint` slot |
| `brain_authority.is_calendar_authority` | **KEEP** | Sticky-calendar gate still needed |
| `data/calendar.py` | **KEEP** | Downstream enrichment; no invent |
| SLL `ask_kind=calendar` | **KEEP** | Already stamps calendar intent when conf high |

---

## KEEP / REPLACE / WRAP summary matrix

```text
KEEP (frozen or healthy)
  ownership_stability, sport_continuity_guard,
  ambiguous_context_guard, fiction_context_jump_guard,
  methodology/confidence/market/intelligence/learning engines,
  sports_language (SLL), entity_safety,
  advanced_football_continuity, conversation_context,
  sport_referent_frame, data/calendar, brain_authority calendar gate

WRAP (façade / adapter — preferred default)
  conversation_state + perception/HCE state → CSL
  short_conversation_memory, conversation_focus,
  follow_up_engine, conversation_continuity, pronoun_continuity,
  human_inference, dialog_mode, master_intent_router,
  natural_conversation (reply/fetch), message_intelligence (bands)

REPLACE (defective utility only)
  Duplicate nickname maps outside SLL (SDR / short_memory lists) → SLL SoT
  message_intelligence.is_topic_switch regex → Episodic/Athena-style boundary
  natural_conversation bare date regex → dateparser (pt-BR)
```

---

## Replacement risks

| Change | Risk | Severity | Guard |
|--------|------|----------|-------|
| Adopt dateparser | Wrong locale / timezone → wrong fixture day | Med | Pin `settings={'PREFER_DATES_FROM':'future'}`, `timezone='America/Sao_Paulo'`; golden calendar corpus |
| CSL slot façade | Dual-write desync with old ctx keys | High | Feature flag; read-through old keys; write both for 1 release |
| Topic-switch REPLACE | False hard-clears on soft digression | High | Only clear on high-conf boundary; EVAL continuity cases |
| Neural T5 rewrite (Tier B) | Latency, PT quality, cost | High | Off by default; BR rule rewriter first |
| Duckling server | Ops / Haskell / deploy surface | Med | Prefer dateparser; Duckling only if grain/interval gaps proven |
| Compact routing tokens | Alias drift vs TEAM_ALIASES | Low | Single table in SLL + team_aliases; unit tests |
| Touching FROZEN modules | AEP P0 reopen | Critical | **Forbidden** |

---

## Migration plan

### Phase 0 — already done (PATCH-002A)
- SLL live behind `ENABLE_SPORTS_LANGUAGE_LAYER`
- Nickname SoT consolidation started
- EVAL-001: Success 84.5%→91.8%, SPORT_REASONING 10.9%→2.7%, HPS 76.4→83.7

### Phase 1 — Calendar date NLU (next, lowest risk)
1. Add `dateparser` dependency (pt/pt-BR).
2. New thin module `src/conversation/calendar_time.py` (flag `ENABLE_DATEPARSER_CALENDAR`).
3. WRAP: Natural Conversation calls it for `date_offset` / ISO; delete only the brittle regex extractors.
4. Golden tests: hoje / amanhã / segunda / próxima rodada / “dia 20”.
5. Re-run EVAL-001 calendar subset + full suite (no success regression).

### Phase 2 — Conversational State Layer (CSL) façade
1. Define `CSLState` TypedDict (LangGraph-style) + Rasa-like slots.
2. Façade reads/writes existing ctx keys (compatibility).
3. Gate: `can_dispatch_sport_engine` from slots + phase (advise OS/SCG, never replace).
4. Deprecate duplicate nick maps in SDR / short_memory (call SLL).
5. Flag `ENABLE_CONVERSATIONAL_STATE_LAYER`; default off → on after EVAL.

### Phase 3 — Follow-up contextualize
1. Port AWS-style `contextualize_question` as pure rules first (Athena 1-turn coref).
2. Wire **after SLL, before MasterIntent** (same band as short_memory).
3. Optional Tier B: T5-CANARD behind `ENABLE_NEURAL_FU_REWRITE=0`.
4. Measure FOLLOWUP_DETECTION + OWNER_LOCK on EVAL + continuity smokes.

### Phase 4 — Topic switch REPLACE
1. Implement boundary detector borrowing Episodic/Athena ideas (entity delta + dialog act).
2. Replace `message_intelligence.is_topic_switch` implementation only.
3. Keep FROZEN fiction/ambiguous guards as hard vetoes.

Each phase: additive module → flag → dual-run metrics → flip default → delete dead regex.

---

## Rollback plan

| Layer | Flag | Effect |
|-------|------|--------|
| SLL | `ENABLE_SPORTS_LANGUAGE_LAYER=0` | Pass-through raw message |
| Calendar dateparser | `ENABLE_DATEPARSER_CALENDAR=0` | Old Natural regex path |
| CSL | `ENABLE_CONVERSATIONAL_STATE_LAYER=0` | Direct ctx dict as today |
| FU contextualize | `ENABLE_FOLLOWUP_CONTEXTUALIZE=0` | Skip rewrite |
| Topic boundary | `ENABLE_TOPIC_BOUNDARY_V2=0` | Legacy `is_topic_switch` |

**Procedure:** flip flag → restart workers → run EVAL-001 + ownership/continuity smokes → if needed, revert git tag of the phase commit only (engines untouched).

**Hard rule:** never roll back by editing FROZEN modules.

---

## Recommended borrow priority (next 30 days)

1. **dateparser** into calendar path (Phase 1) — highest ROI, lowest orchestration risk  
2. **CSL TypedDict + Rasa slots concepts** (Phase 2) — fixes memory desync without new runtime  
3. **Athena-style rule coref + contextualize** (Phase 3) — cuts residual OWNER_LOCK / FU misses  
4. **Episodic topic boundary** (Phase 4) — only after CSL exists  

Skip for now: full Rasa/LangGraph runtime, Duckling server, coreferee, T5 rewrite.

---

## Deliverable checklist

- [x] Candidate repositories (Tier A/B + rejects)
- [x] Exact files/components to borrow
- [x] KEEP / REPLACE / WRAP per Aurora utility
- [x] Replacement risks
- [x] Migration plan (phased, flagged)
- [x] Rollback plan (per-flag)

**Engines remain FROZEN. Defective utilities get façades or narrow swaps — not rewrites.**
