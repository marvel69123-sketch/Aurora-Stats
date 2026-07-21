# TOPIC-STATE-CENTRALIZATION-001 — Sport conversational state SSOT design

**Type:** Architectural investigation + design proposal only — **NO PRODUCT CODE CHANGES**  
**Date:** 2026-07-21  
**Scope:** Single Source of Truth for *sport conversational subject state* (who may WRITE teams/fixture/episode/referents).  
**Out of scope:** Implementing code; redesigning Ownership / Sport Continuity Guard internals; replacing engines; adopting Rasa/LangGraph as sport-logic substitutes.

**Prior conclusions verified against repo (not invented):**

| Prior | Evidence in repo | Status |
|-------|------------------|--------|
| Response Selector approved | `artifacts/aurora/src/conversation/response_selector.py` + `tests/test_response_selector_001.py` | Present; reads subject state, writes only `_response_selector_pool` (candidate pool), not fixture SoT |
| Topic Boundary V2 approved; TB-002 sticky bleed fixed; `ENABLE_TOPIC_BOUNDARY_V2` | `topic_boundary_v2.py`, `observations/topic_boundary_002/REPORT.md`, router order SLL→V2→CSL | Present; flag default OFF |
| Public LangGraph/Rasa rejected for domain logic | `observations/topic_transition_arch_001/REPORT.md`, `artifacts/aurora/observations/arch_003/ARCHITECTURE_RESEARCH.md` | Confirmed |
| Transition: KEEP CUSTOM TRANSITION (CENTRALIZE) | `observations/topic_transition_arch_001/REPORT.md` ending | Confirmed — **decision** layer only |
| TOPIC-STATE-ARCH-001 deferred | Transition report explicitly deferred full CSL/SRF replacement | This mission is the deferred state-store design |

**Relationship to topic_transition_arch_001:**

| Concern | Owner after ideal end-state | What it is |
|---------|----------------------------|------------|
| **Transition decision** | Single `EpisodeTransition.decide` (custom Aurora; LangGraph may *host* later) | KEEP / NEW_FIXTURE / NEW_EPISODE + reason |
| **Sport conversational state store** | Single write module (this report) | Subject slots + episode_id + boundary stamps + follow-up context projections |

These are **complementary**, not duplicates. Centralizing transition detection without a single state writer leaves residual multi-writer bleed. Centralizing the store without a single transition decision leaves duplicate classifiers. Neither replaces market/methodology/confidence engines.

**Principles applied:** Reality > optimism; never invent data; perception > elegance; never regress; KEEP SLL / TB-V2 / Response Selector / Ownership / Engines / sports reasoning.

---

## 1. Evidence surfaces (read paths)

Primary tree: `artifacts/aurora/src/` (V2-aware router). Adjacent: `observations/sticky_bleed_001`, `observations/topic_boundary_002`, `observations/topic_transition_arch_001`, `artifacts/aurora/observations/csl_001`, `artifacts/aurora/observations/arch_003`.

Turn pipeline (artifacts router, V2 ON):

```
SLL → TopicBoundaryV2 → CSL resolve → Sport Intent → short mem / fiction / entity v2
    → … Response Selector / continuity / ownership claims …
    → analyze / soft FU paths → _save_analysis_context (last_*)
    → end-of-turn note_* cascade (short_mem, continuity, pronoun, OS, sport_anchor, CSL, …)
    → stamp_bind_on_payload → SRF.note_from_payload + entity_v2_last_bind
```

---

## 2. Complete ownership map (who writes / who reads / when)

### 2.1 Write owners (sport conversational / subject-adjacent)

| # | Write owner | Module path | Ctx keys written | When |
|---|-------------|-------------|------------------|------|
| 1 | **Topic Boundary V2** | `artifacts/aurora/src/conversation/topic_boundary_v2.py` | Clears orphans; bumps `csl` episode/subject; `csl_subject_guard`; `episode_boundary`, `boundary_*`, `topic_boundary_v2`, `block_hydrate_legacy`, `episode_id`; pops continuity/ci/owners; calls public clear/expire/release APIs | Turn-start `apply_topic_boundary_v2` (flag ON, boundary true) |
| 2 | **CSL** | `…/conversation_state_layer.py` | `csl` via `set_csl`; may set `note_csl_blocked` | Turn-start `apply_csl_resolve`; end-of-turn `note_csl_after_response` |
| 3 | **SRF** | `…/sport_referent_frame.py` | `sport_referent_frame` via `save_srf` / `set_fixture` / `set_team` / `clear_srf` / `project_from_ctx` / `note_from_payload` | Entity resolve (project + set_*); end stamp via `stamp_bind_on_payload` |
| 4 | **Entity Resolver v2** | `…/core/entity_resolver_v2.py` | `entity_v2_last_bind` (+ mid-router bind); drives SRF writers | Mid-turn resolve; end `stamp_bind_on_payload` |
| 5 | **Short conversation memory** | `…/short_conversation_memory.py` | `short_conversation_memory`, `short_memory_resolve` | Early resolve; end `note_short_memory` |
| 6 | **Message intelligence** | `…/message_intelligence.py` | `clear_fixture_context` pops `last_*`/`prev_*`/`ci_pending`; `set_ci_pending`; `shift_fixture_memory` → `prev_*` | Boundary/cancel; CI clarify; before new analyze save |
| 7 | **Router analyze save** | `…/routers/copilot_unified_router.py` `_save_analysis_context` | `last_home`/`last_away`/`last_match`/`last_fixture`/`last_analysis`/`last_intent`/…; also live path can seed `last_*` | After successful analyze / some live flows |
| 8 | **Conversation focus** | `…/conversation_focus.py` | `conversation_focus`, `short_memory_window` | Mid-pipeline `update_conversation_focus`; boundary `clear_focus_on_boundary` |
| 9 | **Conversation continuity** | `…/conversation_continuity.py` | `conversation_continuity`, continuity resolve marker | End `note_continuity` / `_arm`; turn resolve |
| 10 | **Sport Continuity Guard** (public APIs only) | `…/sport_continuity_guard.py` | `sport_continuity_guard.anchor`; **also** `ctx.setdefault("last_match", fx)` on create | `create`/`expire`/`note_sport_anchor_after_response` / V2 expire |
| 11 | **Ownership Stability** (public APIs only) | `…/ownership_stability.py` | `ownership_stability` lock blob; `last_turn_owner` / `last_response_owner`; `_continuity_stamp` | Claim/release/note; V2 `release_owner_lock` |
| 12 | **Brain Authority** (legacy boundary) | `…/brain_authority.py` | `clear_fixture_context` + `brain_boundary_cleared` / `block_hydrate_legacy` / `topic_boundary_reason` / `boundary_score` | Mid-pipeline when V2 path not the sole clearer (still wired in router) |
| 13 | **Legacy conversation_state** | `…/conversation_state.py` | `conversation_state.active_fixture` / markets / history | `_save_analysis_context` → `apply_after_analysis`; hydrate/clear helpers |
| 14 | **Pronoun continuity** | `…/pronoun_continuity.py` | `pronoun_continuity` (via `note_pronoun_memory` in router cascade) | End-of-turn note |

**Not a subject SoT writer:**

| Module | Writes? | Role |
|--------|---------|------|
| **Response Selector** | `ctx["_response_selector_pool"]` only | Selects among candidates; **reads** `last_match` / sport_anchor / continuity — does not own subject |
| **SLL** | `ctx["sll"]` (normalized clubs) | Perception input to subject writers — KEEP |
| **CIL** | `cil_*`, may consume `ci_pending` | Goal/thought overlays — not fixture SoT |

**Distinct write-owners mapped:** **14** (subject / subject-adjacent session writers above).

### 2.2 Primary readers (consume subject; should not invent)

| Reader | Reads from | Purpose |
|--------|------------|---------|
| Topic Boundary V2 detect | Sticky `last_*`, focus, continuity, sport_anchor (intentionally **not** live CSL first) | Episode classify |
| CSL hydrate / inject | `sll`, `last_*`, own `csl`, `csl_subject_guard` | Slots + bare FU rewrite |
| SRF project | `last_match`, continuity, short_mem, sport_anchor | Fill empty frame |
| Entity v2 / honesty | SRF, `entity_v2_last_bind` | Bind + “Mantendo foco…” |
| Response Selector / continuity / OS / sport_anchor guards | `last_*`, short_mem, CSL teams, anchors | Soft FU / lock / pool |
| Follow-up gate (`followup_guard`) | `last_*` | Reuse vs new fixture |
| Partial inference honesty | `entity_v2_last_bind`, SRF | Prefix honesty |

---

## 3. Current state map (conceptual fields × physical stores)

Target conceptual shape (refined from real code fields):

```text
conversation_state (conceptual SSOT) ≈ {
  episode_id,          # CSL.episode_id + ctx.episode_id (duplicated today)
  subject_teams,       # CSL.teams | last_home/away | SRF.home/away | focus.topic_teams | anchor.teams | short_mem.last_team | continuity.last_team | bind
  fixture,             # CSL.fixture | last_match/last_fixture | SRF.fixture_label | focus.topic_fixture | anchor.fixture | continuity.last_fixture | conversation_state.active_fixture
  topic / phase,      # CSL.topic/phase | focus.topic_kind | continuity.mode
  ownership,           # ownership_stability lock (KEEP module; project read)
  boundary_reason,     # topic_boundary_v2 / topic_boundary_reason / boundary_reason
  followup_context,    # continuity + short_mem + ci_pending + followup_resolved_*
  date_context         # CSL.date_context
}
```

| Conceptual field | Physical stores today (multi-writer) |
|------------------|--------------------------------------|
| episode_id | `csl.episode_id`, `ctx.episode_id`, `csl_subject_guard.episode_id`, `topic_boundary_v2.episode_id` |
| teams / subject | `csl.teams`, `last_home`/`last_away`, `srf.home`/`away`/`focus_team`, `entity_v2_last_bind`, `short_conversation_memory.last_team`, `conversation_continuity.last_team`, `conversation_focus.topic_team(s)`, `sport_continuity_guard.anchor.teams`, `conversation_state` (indirect) |
| fixture | `csl.fixture`, `last_match`/`last_fixture`, `srf.fixture_label`, focus/continuity/short_mem/anchor/`active_fixture` |
| ownership | `ownership_stability` (+ `last_turn_owner`) — **keep OS as lock authority** |
| boundary | V2 decision blob + router/brain flags |
| follow-up / CI | `conversation_continuity`, `ci_pending`, `followup_resolved_*`, short_mem, pronoun blob |
| date | `csl.date_context` (+ message regex elsewhere) |

---

## 4. Redundant state map

### 4.1 Same subject duplicated (Top 3)

| Rank | Redundant cluster | Stores | Failure mode if divergent |
|------|-------------------|--------|---------------------------|
| **1** | **Canonical fixture/subject triad** | `last_home`/`last_away`/`last_match` **↔** `csl.teams`/`fixture` **↔** `sport_referent_frame` | Sticky bleed / honesty “Mantendo foco” / wrong analyze (STICKY-BLEED-001; mitigated but not eliminated as architecture) |
| **2** | **Soft FU referent triad** | `short_conversation_memory` **↔** `conversation_continuity` **↔** `conversation_focus` (+ `short_memory_window`) | Soft FU answers prior team after episode rotate if any store survives clear |
| **3** | **“What game are we on” triad** | `sport_continuity_guard.anchor` **↔** `conversation_state.active_fixture` **↔** `entity_v2_last_bind` | Anchor/`setdefault(last_match)` re-seeds legacy; bind drives honesty; active_fixture is third nickname SoT (ARCH-003 already flagged) |

### 4.2 Additional redundancy (must remain aware)

| Pair / group | Note |
|--------------|------|
| `last_match` vs `last_fixture` | Same value written together in `_save_analysis_context` |
| `prev_*` vs `last_*` | Intentional shift buffer (`shift_fixture_memory`) — **projection**, not third subject |
| V2 stamps vs brain_authority boundary flags | Dual clear paths when both fire |
| `ci_pending` vs CIL pending_question | Clarify pending — related but not full subject SoT |

---

## 5. Eliminate vs keep as projection/cache (after SSOT)

| Store | After SSOT | Rationale |
|-------|------------|-----------|
| **SSOT blob** (new / elevated) | **KEEP as sole WRITE** | Subject + episode + date + followup_context summary |
| `csl` | **Become the SSOT schema or 1:1 projection of it** | Already closest typed contract (`teams`, `fixture`, `topic`, `episode_id`, `date_context`) |
| `last_home`/`last_away`/`last_match`/`last_fixture` | **Projection/cache** (write-through from SSOT only) | Deep call graph; cannot big-bang delete |
| `sport_referent_frame` | **Read projection** for Entity v2 (refresh from SSOT; no independent subject invent) | Consumer frame by design; today also writes |
| `entity_v2_last_bind` | **Ephemeral turn bind cache** (cleared on episode; written only via SSOT funnel after bind resolve) | Needed for honesty stamp |
| `short_conversation_memory` sport keys | **Projection** of followup_context / team | Keep pronoun helper API; stop independent subject authorship |
| `conversation_focus` / `short_memory_window` | **Projection** | Soft FU UX |
| `conversation_continuity` | **Projection** (mode + TTL window over SSOT subject) | Soft FU arm/decay |
| `sport_anchor` | **KEEP module**; anchor fields **sourced from SSOT** (no `setdefault(last_match)` invent) | FROZEN guard — wrap public create/note to read SSOT |
| `ownership_stability` | **KEEP** lock writer; **do not** store fixture subject inside OS | Lock ≠ subject |
| `conversation_state.active_fixture` | **Deprecate → projection** then eliminate | ARCH-003 nickname SoT |
| `ci_pending` | **Keep** as clarify pending (narrow); subject teams still from SSOT | Not a parallel fixture store |
| Response Selector pool | **Keep** ephemeral | Not subject |
| Boundary decision stamp | **Keep** as transition output read by SSOT.apply | Transition ≠ store |

---

## 6. Remaining bleed vectors after TB-002

TB-002 fixed the **ordering + orphan clear + note_csl guard** class for V2 ON. Residual multi-writer risks (architectural, not “TB-002 failed”):

1. **End-of-turn note cascade still multi-writes subject** — `note_short_memory`, `note_continuity`, `note_sport_anchor_after_response` (may `setdefault last_match`), `note_csl_after_response`, `stamp_bind_on_payload`→SRF/`entity_v2_last_bind`, `apply_after_analysis` — each can re-materialize subject independently if payload/message diverge.
2. **Dual boundary materializers** — V2 early + `brain_authority.apply_topic_boundary` mid-pipeline (clear + flags) can still disagree when V2 OFF or when both paths partially apply.
3. **Sport-intent / other rewriters** still consume CSL or sticky reads; if any path skips V2 (flag OFF / fail-open), STICKY-BLEED-001 class returns.
4. **`create_sport_context_anchor` → `ctx.setdefault("last_match", fx)`** — guard can write legacy sticky outside CSL/SSOT.
5. **Projections can be refreshed from stale peers** — e.g. `project_from_ctx` fills SRF from short_mem/continuity/anchor if SSOT empty/wrong order.
6. **Flag default OFF** — production perception still on multi-writer legacy until V2 enabled; SSOT must not assume V2 always on.
7. **Transition detectors still split** (followup_guard / brain_authority / is_topic_switch) — orthogonal but amplifies state inconsistency when decisions disagree.

**Honest verdict:** TB-002 + transition centralization alone **reduce** bleed but **do not** make “only one component writes.” Residual risk is structural multi-writer, not missing Jaccard.

---

## 7. Centralization proposal

### 7.1 Single write owner

| Item | Proposal |
|------|----------|
| **Name** | **Sport Topic State (STS)** |
| **Module (future)** | `artifacts/aurora/src/conversation/sport_topic_state.py` (design name only) |
| **Role** | **Sole authorized writer** of sport conversational subject: `episode_id`, teams, fixture, topic/phase, date_context, followup_context summary, boundary_reason stamp consumption |
| **Schema home** | Prefer **elevate CSL contract** as the persisted SSOT shape (already closest); STS owns `commit`/`apply_event`; raw `set_csl` / `save_srf` / direct `last_*=` become private or adapter-only |

### 7.2 Write funnel (events, not free-form dict edits)

```text
  Transition.decide  ──►  STS.apply_boundary(decision)     # clear + replace subject
  SLL clubs / explicit fixture ──► STS.apply_subject(...)
  Analyze success ──► STS.apply_analysis(home, away, match, …)
  Soft FU arm ──► STS.apply_followup_window(mode, ttl)
  Clarify pending ──► STS.apply_ci_pending(...)
  Bind resolve ──► STS.apply_bind(entities)  # updates bind cache + SRF projection
```

All current `note_*` / `_save_analysis_context` / SRF `set_*` / short_mem sport keys become **adapters that call STS** (or become read-only projectors refreshed by STS).

### 7.3 How existing KEEP modules change role (no replacement of logic)

| Module | Future role |
|--------|-------------|
| **Topic Boundary V2** | **Decide + request** (`detect` pure; `apply` becomes `STS.apply_boundary`) — not a second subject author beyond funnel |
| **CSL** | **Schema / façade readers** + inject rewrite reading STS; `note_csl` merges into STS.commit only |
| **SRF** | **Read projection** for Entity v2; write only via STS.apply_bind / apply_analysis |
| **SLL** | Unchanged perception input |
| **Response Selector** | Read-only consumer of STS snapshot |
| **Ownership / Sport Continuity Guard** | KEEP internals; public create/note/release called **from STS** with subject taken from STS (no independent last_match seed) |
| **Engines** | Untouched |
| **LangGraph** | Optional **future orchestration host** for turn graph / order enforcement — **never** sport-logic substitute |
| **Rasa** | Not adopted for state or logic |

### 7.4 Target snapshot API (read-only for everyone else)

```text
sts = SportTopicState.snapshot(ctx)
# episode_id, teams, fixture, topic, ownership_lock_active (read),
# boundary_reason, followup_context, date_context
```

---

## 8. Incremental migration strategy (no big bang)

| Phase | Flag / gate | Action | Success signal | Rollback |
|-------|-------------|--------|----------------|----------|
| **0** | — | Inventory + freeze new direct subject writes in review checklist (this report) | Map agreed | N/A |
| **1** | `ENABLE_STS_READ_ADAPTERS` | Add STS snapshot **readers**; adapters mirror from existing stores (read-only SSOT view; **no behavior change**) | Shadow logs: divergence rate among last_*/csl/srf | Flag off |
| **2** | `ENABLE_STS_WRITE_FUNNEL_BOUNDARY` | Route V2 `apply_episode_boundary` clears/subject replace **only** through STS.commit (still updates same keys) | TB-002 suite green; orphan clears unchanged | Flag off |
| **3** | `ENABLE_STS_WRITE_FUNNEL_ANALYZE` | `_save_analysis_context` + `note_csl` + `note_from_payload` + short_mem sport keys go through STS | Analyze→FU perception parity; note_csl_blocked still works | Flag off |
| **4** | `ENABLE_STS_PROJECTIONS_RO` | SRF/focus/continuity/short_mem sport fields become **write-through projections**; ban direct `set_fixture`/`note_continuity` subject fields outside funnel | Divergence metrics → 0 on subject fields | Flag off |
| **5** | `ENABLE_STS_SOLE_WRITER` | Assert/guard: non-funnel writes to subject keys no-op or audit-fail in tests | Single writer proven in tests | Flag off |
| **6** | Optional later | Deprecate `conversation_state.active_fixture` nickname; align with transition centralization (`EpisodeTransition`) | Dead code removal behind flag | Restore projection |

**Rules:** never enable Phase 5 before Phase 1 shadow divergence is understood; never regress soft FU / analyze honesty; V2 remains independently flaggable; Ownership/SCG internals not redesigned—only call sites funnel through STS.

**Artifacts vs live tree:** implementation (when later approved) must pick one deployable surface; V2 today lives under `artifacts/aurora/` wiring — migration must not assume live `aurora/src` parity.

---

## 9. Risks of centralizing vs keeping multi-writer

| Risk | If CENTRALIZE | If KEEP CURRENT multi-writer |
|------|---------------|------------------------------|
| Perception regression | Medium during funnel migration (mitigate flags + shadow) | Ongoing residual bleed when V2 OFF or note cascade diverges |
| Dual SoT during migration | High if adapters write both old and new without shadow discipline | Status quo dual/triple SoT |
| Scope creep into engines / OS redesign | Medium — must refuse | Low for engines; high for continued sticky patches |
| Latency / complexity | Low–medium (one commit path) | High long-term (N writers × N clears) |
| Transition work duplication | Low if STS consumes transition decision | Continues patching symptoms |

---

## 10. Recommendation rationale

- User framing is correct: **split ownership of subject state** is the architectural problem; public libs were correctly rejected as logic replacements.
- TB-002 proves bleed is fixable with order+cleanup+guards, but **does not** collapse writers to one.
- Transition report’s “KEEP CUSTOM TRANSITION (CENTRALIZE)” addresses **decision**; this report addresses **store**. Both lean custom Aurora; LangGraph only as optional future host.
- Evidence favors **CENTRALIZE STATE** with incremental funnel — not KEEP CURRENT as end-state, and not Rasa/LangGraph memory adoption.

---

```
FACT:
Sport conversational subject is written by at least 14 distinct session owners under artifacts/aurora (TopicBoundaryV2, CSL, SRF, Entity v2 bind, short_conversation_memory, message_intelligence clear/ci/shift, router _save_analysis_context, conversation_focus, conversation_continuity, sport_continuity_guard public APIs, ownership_stability public APIs, brain_authority boundary apply, legacy conversation_state, pronoun_continuity). The same fixture/teams appear in last_*/csl/srf and again in short_mem/continuity/focus and again in sport_anchor/active_fixture/entity_v2_last_bind. TB-002 (ENABLE_TOPIC_BOUNDARY_V2) fixed ordering + orphan clear + note_csl guard for the sticky-bleed class when flag ON; Response Selector does not own subject writes. Public Rasa/LangGraph remain unsuitable as sport-logic or subject-SoT replacements (prior ARCH-003 + topic_transition_arch_001).

CURRENT RISKS:
(1) End-of-turn note_* cascade can re-materialize divergent subjects even after a clean V2 boundary.
(2) Dual boundary materializers (V2 + brain_authority) and V2 default OFF leave legacy multi-writer perception path live.
(3) sport_anchor create can setdefault last_match outside CSL.
(4) SRF.project_from_ctx can resurrect subject from uncleared peer caches.
(5) Transition detectors still split — amplifies state inconsistency when paired with multi-writer store.

REDUNDANT STATES:
(1) last_home/last_away/last_match ↔ csl.teams/fixture ↔ sport_referent_frame (canonical fixture triad).
(2) short_conversation_memory ↔ conversation_continuity ↔ conversation_focus (soft-FU referent triad).
(3) sport_continuity_guard.anchor ↔ conversation_state.active_fixture ↔ entity_v2_last_bind (“what game” triad).
Eliminable after SSOT: independent authors of those clusters (keep as projections/caches). Must remain as modules/APIs: Ownership lock, Sport Continuity Guard TTL behavior, Response Selector, SLL, engines — reading STS.

PROPOSED SINGLE SOURCE OF TRUTH:
Sport Topic State (STS) — module role sport_topic_state.py; sole WRITE owner of episode_id/subject teams/fixture/topic/date_context/followup_context summary; elevates CSL contract as persisted schema; Topic Boundary V2 becomes decide→STS.apply_boundary; CSL/SRF/short_mem/focus/continuity/last_* become readers or write-through projections; Ownership/SCG stay KEEP via public APIs invoked from the funnel; LangGraph optional future host only; Rasa not used.

MIGRATION STRATEGY:
Six incremental phases behind flags: (0) inventory freeze, (1) read adapters + shadow divergence, (2) boundary write funnel, (3) analyze/note/bind write funnel, (4) projections read-only for peer stores, (5) sole-writer assert, (6) optional deprecate conversation_state.active_fixture + align EpisodeTransition. No big bang; never regress perception; V2 and STS flags independent.

RISKS:
Partial funnel leaves dual SoT; tempting OS/SCG internal rewrites (forbidden); artifacts vs live tree drift; enabling sole-writer before shadow metrics; conflating transition centralization with state centralization and shipping only one.

RECOMMENDATION:
CENTRALIZE STATE.
```

**Clarification vs topic_transition_arch_001:** that report’s `KEEP CUSTOM TRANSITION (CENTRALIZE)` = centralize **episode transition decision**. This report’s `CENTRALIZE STATE` = centralize **sport conversational state writes**. Do both over time; neither adopts Rasa/LangGraph as sport logic.
