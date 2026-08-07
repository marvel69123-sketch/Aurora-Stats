# AURORA TASK — ARCHITECTURE_SPECIFICATION / DESIGN (Missão 004)

**Type:** Engineering specification — **NO PRODUCT CODE, NO IMPLEMENTATION, NO MODULE MODIFICATIONS**  
**Date:** 2026-08-06  
**Deliverable path:** `observations/aurora_context_manager_spec_004/SPEC.md`  
**Role:** Senior Software Architect (design only)  
**Implementation authorization:** **NOT AUTHORIZED.** Next process step is Missão 005 (spec review). Do not execute 005 in this mission.

---

## Binding sources (cited, not invented)

| Source | Role in this SPEC |
|--------|-------------------|
| `observations/aurora_context_manager_research_003/REPORT.md` | **Primary architecture decision:** LangGraph-hosted SportTopicState (STS) Sole-Writer Context Manager; 6-phase migration; dual-SoT prohibition |
| `observations/aurora_core_audit_001/REPORT.md` | Context Manager **Substituir**; Audit pillars; Frozen candidates; Documento Mestre **INSUFFICIENT EVIDENCE**; deploy SoT = `artifacts/aurora/` |
| `observations/topic_state_centralization_001/REPORT.md` | STS sole writer; 14 write-owners; projection map; centralization migration phases |
| `observations/topic_transition_arch_001/REPORT.md` | Binding: **KEEP CUSTOM TRANSITION (CENTRALIZE)**; LangGraph host ≠ classifier SoT; Rasa rejected for domain |
| `observations/langgraph_state_poc_001/REPORT.md` + `ARCHITECTURE.md` + `shadow/CONTAMINATION_NOTES.md` | Existing POC contract evolution (flags, graph shape, shadow loci); not greenfield invent |
| `observations/sticky_bleed_001/REPORT.md` | Failure mode: ordering + incomplete cleanup (not UUID alone) |
| `observations/topic_boundary_002/REPORT.md` | TB-002 fix exists; `ENABLE_TOPIC_BOUNDARY_V2` default OFF; order SLL→V2→CSL |

**Documento Mestre Etapa 1:** **INSUFFICIENT EVIDENCE** in-repo (Audit 001). This SPEC must remain compatible with Audit 001 pillars, Frozen engines policy, and “specializations never modify Core.” Compliance with an unseen master document **cannot be certified**.

---

## 1. Executive Summary

This specification defines the **Aurora Core Context Manager** replacement as a **LangGraph-hosted SportTopicState (STS) Sole-Writer Context Manager**:

- **LangGraph** hosts typed graph state, ordered edges, and checkpointer durability.
- **Aurora-owned STS** is the **only** component authorized to write sport conversational subject (`episode_id`, teams, fixture, topic/phase, date_context, followup_context summary, boundary stamps consumed).
- **KEEP CUSTOM TRANSITION** remains Aurora domain logic (TB-V2 / future `EpisodeTransition.decide`), **hosted inside** the graph as classify nodes — **not** replaced by LangGraph or Rasa sport logic.
- Existing LangGraph STS POC assets under `artifacts/aurora/` evolve into this contract; they are not discarded and not rewritten in this mission.
- Migration is **six conceptual phases**, shadow-first, with **dual Source-of-Truth (dual-SoT) prohibited** once production write is enabled.
- Frozen sports engines, SLL, Response Selector, and Ownership/SCG public APIs are preserved; specializations must not modify Core STS internals.

**Perception > elegance.** The architecture attacks the proven sticky-bleed class (multi-writer + ordering/cleanup), which episode UUID rotation alone did not fix.

---

## 2. Objetivos

| ID | Objetivo |
|----|----------|
| O1 | Establish a **sole-writer** Context Manager for sport conversational subject state (STS). |
| O2 | Host STS turn updates in a **LangGraph** state machine that **enforces order**: classify/transition **before** subject rewrite/commit. |
| O3 | Preserve **KEEP CUSTOM TRANSITION** (Aurora PT football / fixture / soft-FU policy) inside the graph. |
| O4 | Eliminate independent subject authorship by the current **≥14 write-owners** after cutover (demote to projections / adapters). |
| O5 | Provide **checkpointed** session durability and **recovery after restart** keyed by stable session/thread identity. |
| O6 | Migrate incrementally via flags (shadow → gated funnel → production write → writer retirement) without dual-SoT. |
| O7 | Protect betting credibility: subject switches must be **fail-closed** on write path when production STS is active; shadow remains fail-open. |
| O8 | Keep frozen engines, SLL, Response Selector, OS/SCG public APIs intact; specializations never modify Core. |
| O9 | Remain governance-compatible with Audit 001 while Documento Mestre remains **INSUFFICIENT EVIDENCE**. |

---

## 3. Escopo

**In scope (Context Manager pillar substitution design):**

1. Sport conversational subject SSOT: schema ownership, sole commit, read snapshot API.
2. LangGraph host contract: graph topology, node responsibilities, checkpointer, thread identity.
3. Custom transition hosting: classify → route → apply_boundary | keep_followup | apply_subject.
4. Projection/façade contracts for legacy keys (`last_*`, CSL, SRF, short_mem, focus, continuity).
5. Feature-flag matrix and relationship to TB-V2 / STS / LangGraph flags.
6. Persistence, checkpoints, recovery, error semantics (fail-open vs fail-closed).
7. Compatibility with current Aurora pipeline and Frozen policy.
8. Conceptual 6-phase migration, test/validation/Frozen criteria, risks, ADRs.
9. Evolution path from existing POC assets (`sport_topic_state.py`, `langgraph_state_graph.py`, `langgraph_state_adapter.py`, shadow harness).

**Code SoT for future implementation (when authorized):** `artifacts/aurora/` (Audit 001). Mirror `aurora/` must not be assumed parity (TB-V2 / LangGraph absent on mirror).

---

## 4. Não Objetivos

| ID | Não objetivo |
|----|--------------|
| N1 | Implement, refactor, migrate, or patch any product module in this mission. |
| N2 | Replace Response Selector, SLL, Ownership Stability, Sport Continuity Guard, or sports engines. |
| N3 | Adopt Rasa DialogueStateTracker (or full Rasa runtime) as Context Manager or transition SoT. |
| N4 | Make LangGraph the **sport-logic** Source of Truth (fixture parse, Jaccard policy, PT soft-FU lexicon). |
| N5 | Rewrite full Orchestration / Tool Use / Execution Manager pillars (adjacent; out of this Context Manager SPEC). |
| N6 | Treat cache, short_mem, or chat history as sport subject SoT. |
| N7 | Invent Documento Mestre Etapa 1 requirements. |
| N8 | Enable `ENABLE_LANGGRAPH_STATE` by default or claim bleed “fixed” while production write / sole-writer remain OFF. |
| N9 | Big-bang delete of `last_*` / CSL / SRF physical keys without projection phase. |
| N10 | Redesign OS/SCG internals (only call-site funnel via public APIs). |

---

## 5. Arquitetura Geral

### 5.1 Primary architecture (binding)

**LangGraph-hosted SportTopicState (STS) Sole-Writer Context Manager**  
(Source: research_003 §7; Audit 001 §3.2; centralization_001 §7; transition_arch_001 KEEP CUSTOM; POC_001.)

```text
User → POST /aurora/copilot
  → conversation_manager session load (session_id)
  → SLL (perception normalize; KEEP)
  → LangGraph STS Host (thread_id = map(session_id))
        ├─ init_load          (hydrate STS from checkpoint / projections)
        ├─ classify           (Aurora CUSTOM transition — TB-V2 / EpisodeTransition.decide)
        ├─ apply_boundary | keep_followup | apply_subject
        └─ STS._commit        ★ SOLE WRITER of sport subject
  → Projection refresh (last_*/CSL façade/SRF/short_mem/focus/continuity write-through)
  → OS / SCG via public APIs only (fed by STS snapshot; no independent subject invent)
  → Engines (FROZEN, untouched) when analyze/live required
  → Response Selector (read-only consumer of STS snapshot / projections)
  → CopilotResponse
```

### 5.2 Sole-writer rule (normative)

| Rule | Statement |
|------|-----------|
| SW-1 | After cutover (`ENABLE_LANGGRAPH_STATE` + sole-writer gate), **only STS commit** may mutate sport subject fields. |
| SW-2 | Transition modules **decide**; they do not independently author subject outside the funnel. |
| SW-3 | Projections may refresh **from STS only**; they must not invent subject from peer caches when STS is authoritative. |
| SW-4 | OS lock and SCG anchor remain KEEP modules; subject fields they need are **sourced from STS**; forbidden: `setdefault(last_match, …)` invent outside funnel. |
| SW-5 | Engines and Response Selector **never** write sport subject SoT. |

### 5.3 What LangGraph hosts vs what Aurora owns

| Concern | Owner |
|---------|-------|
| Graph topology, conditional edges, super-step order | **LangGraph (host)** |
| Checkpointer snapshot / resume by `thread_id` | **LangGraph (host)** + Aurora-chosen backend |
| Typed STS schema fields & semantics | **Aurora STS** |
| Transition classify (new_fixture / soft_FU / new_episode / keep) | **Aurora custom** (hosted as graph node) |
| Sole `_commit` of subject | **Aurora STS** (invoked only from graph commit path) |
| Sports math / markets / confidence | **Frozen engines** (outside graph ownership) |
| Response candidate selection | **Response Selector** (consumer) |
| Nickname / club normalize | **SLL** (input) |

### 5.4 Dual-SoT prohibition (normative)

| Phase | Allowed |
|-------|---------|
| Shadow (`ENABLE_LANGGRAPH_STATE_SHADOW=1`, write OFF) | Live multi-writer OLD + isolated NEW compare — **log only**; not dual production SoT |
| Funnel gated (write OFF or projection write-through under STS) | Single logical writer path; legacy keys updated **only** via STS adapters |
| Production write ON | **Forbidden:** parallel independent subject authorship + STS write |
| Cutover complete | **Forbidden:** any of the 14 legacy writers mutating subject keys outside STS |

Enabling `ENABLE_LANGGRAPH_STATE` **before** sole-writer funnel completion recreates Audit R3 dual-SoT and is **out of compliance** with this SPEC.

### 5.5 Failure modes this SPEC must prevent (sticky bleed / TB-002 evidence)

| Failure mode | Evidence | Spec control |
|--------------|----------|--------------|
| Boundary after CSL/intent rewrite | sticky_bleed_001; TB-002 | Graph edges: classify → apply **before** subject consumers see stale triad |
| Incomplete orphan clear (SRF, bind, short_mem) | sticky_bleed_001; TB-002 | `apply_boundary` must clear orphans via STS commit atomicity |
| End-of-turn note_* re-materializes wrong subject | centralization_001 §6 | note_* become adapters → STS or no-ops |
| Soft FU preserves contaminated OLD | CONTAMINATION_NOTES locus (1) | Production write path must land NEW on switch turn; soft FU only after correct prior |
| Episode UUID rotates but subject does not | sticky_bleed_001 | Subject replace is mandatory on NEW_FIXTURE / NEW_EPISODE |
| Flag OFF fail-open legacy path | TB-002 default OFF; Audit R1 | Credibility: do not claim fixed while defaults OFF; production STS fail-closed when ON |

---

## 6. Componentes

**Component count: 16**

| # | Componente | Layer | Origin / evolution |
|---|------------|-------|---------------------|
| C1 | **LangGraph State Host** | Infrastructure | POC `langgraph_state_graph.py` → production host contract |
| C2 | **Sport Topic State (STS)** | Core Context Manager | POC `sport_topic_state.py` → sole-writer SSOT |
| C3 | **Custom Transition Classifier** | Domain decision | TB-V2 detect / future `EpisodeTransition.decide` hosted in classify node |
| C4 | **Graph Node: init_load** | Host node | POC topology |
| C5 | **Graph Node: classify** | Host node wrapping Aurora rules | POC topology; KEEP CUSTOM |
| C6 | **Graph Nodes: apply_boundary / keep_followup / apply_subject** | Host nodes | POC topology; materialize via STS |
| C7 | **STS Commit Gate (`_commit`)** | Sole writer | POC single writer; normative sole commit |
| C8 | **Projection / Façade Layer** | Compatibility | centralization_001 §5 demotions |
| C9 | **Shadow Adapter** | Observability / migration | POC `langgraph_state_adapter.py` |
| C10 | **Checkpoint Store** | Persistence | LangGraph checkpointer backend (InMemory→SQLite→Postgres as needed) |
| C11 | **Session–Thread Identity Mapper** | Identity | Maps Aurora `session_id` → LangGraph `thread_id` |
| C12 | **Feature Flag Controller** | Governance | LangGraph / TB-V2 / STS flags matrix |
| C13 | **Ownership Stability (OS) Adapter** | KEEP module façade | Public APIs only; fed by STS |
| C14 | **Sport Continuity Guard (SCG) Adapter** | KEEP module façade | Public APIs only; fed by STS |
| C15 | **Router Integration Boundary** | Orchestration edge | `copilot_unified_router` call site contract (design) |
| C16 | **Context Observability Stamps** | Observability | AUDIT stamps for boundary/commit/shadow/divergence |

**Preserved external collaborators (not Context Manager components, must not be replaced by this SPEC):**

- SLL (`sports_language`)
- Response Selector
- Frozen sports engines (methodology, market, confidence, intelligence, learning, decision_center, knowledge, …)
- `conversation_manager` / Memory pillar stores (session envelope; not sport subject SoT)

---

## 7. Responsabilidades

### C1 — LangGraph State Host
- Compile and invoke the STS turn graph once per copilot turn (when write or shadow path active).
- Enforce edge order; do not invent domain outcomes.
- Persist/load graph state via checkpointer.
- Provide sequential fallback when `langgraph` package missing (POC behavior) — **shadow only**; production write path must not silently skip order guarantees (see §15).

### C2 — Sport Topic State (STS)
- Own schema for sport conversational subject.
- Expose `snapshot` (read-only) and event apply APIs (`apply_boundary`, `apply_subject`, `apply_analysis`, `apply_followup_window`, `apply_ci_pending`, `apply_bind`).
- Perform **sole** `_commit` that updates authoritative subject fields and triggers projection refresh.
- Never call frozen engine internals.

### C3 — Custom Transition Classifier
- Pure decision: `KEEP_EPISODE | NEW_FIXTURE | NEW_EPISODE` (+ reason string compatible with TB-V2 reasons: `new_fixture`, `soft_followup_same_episode`, `low_entity_overlap`, …).
- Consume SLL clubs + sticky prior from STS snapshot (not live peer caches when STS authoritative).
- Must not write subject keys directly.

### C4 — init_load
- Load checkpointed STS (or hydrate from projections during migration) into graph state.
- Establish turn baseline before classify.

### C5 — classify
- Invoke C3; attach decision to graph state; select next edge.

### C6 — apply_boundary / keep_followup / apply_subject
- Translate decision into STS events only.
- `apply_boundary`: clear orphans + replace subject + bump episode (TB-002 semantics elevated into STS).
- `keep_followup`: preserve episode/subject; update followup window stamps only.
- `apply_subject`: seed or same-fixture restated / overlap OK → `replace_subject` without false episode rotate.

### C7 — STS Commit Gate
- Single mutation point for authoritative subject blob.
- Emit observability stamps; refresh projections atomically relative to commit success.

### C8 — Projection / Façade Layer
- Maintain compatibility keys for deep call graph: `last_*`, CSL façade, SRF, short_mem sport keys, focus, continuity.
- After cutover: write-through from STS only; ban independent invent.
- Provide read adapters during shadow/read phases.

### C9 — Shadow Adapter
- When `ENABLE_LANGGRAPH_STATE_SHADOW=1`: capture OLD from live ctx; run isolated NEW; log divergence + `contamination_locus`; **never** write back.
- Fail-open (must not break turn).

### C10 — Checkpoint Store
- Persist STS graph state per `thread_id` each successful super-step (or defined commit boundary).
- Keep snapshots lean (subject fields, not engine payloads / large analysis blobs).

### C11 — Session–Thread Identity Mapper
- Deterministic mapping `session_id → thread_id`.
- Guarantee isolation across sessions; stable across process restart for same session.

### C12 — Feature Flag Controller
- Interpret flags consistently (unset/`0`/`false`/`off`/`no` → OFF; `1`/`true`/`on`/`yes` → ON — POC/TB-V2 pattern).
- Enforce precedence rules in §8 / §17.

### C13 — OS Adapter
- Call `claim` / `release` / note APIs with STS-sourced identity; do not store fixture subject inside OS as SoT.

### C14 — SCG Adapter
- Call create/expire/note with STS-sourced fixture; forbid independent `last_match` seed invent.

### C15 — Router Integration Boundary
- Define exact pipeline insertion: after SLL, before subject-consuming layers when production path ON.
- Preserve fail-open shadow hook position from POC until cutover.

### C16 — Context Observability Stamps
- Emit AUDIT lines for: shadow compare, boundary decision, commit, projection refresh, blocked illegal writes, recovery events.

---

## 8. Interfaces

### 8.1 Turn ingress (Router → Context Manager)

| Field | Direction | Notes |
|-------|-----------|-------|
| `session_id` | in | Aurora session identity |
| `message` | in | Raw user text (post any transport decode) |
| `sll` result | in | Normalized clubs / compare signals |
| `ctx` envelope | in/out | Session dict; subject keys owned by STS after cutover |
| flags | in | Env / config snapshot for this process |

### 8.2 Graph invoke (Host ↔ STS)

| Interface | Contract |
|-----------|----------|
| `init_load` | Input: `thread_id`, checkpoint, optional hydrate snapshot; Output: graph state with STS baseline |
| `classify` | Input: message + STS prior + SLL; Output: transition decision enum + reason |
| apply nodes | Input: decision + candidate entities; Output: pending STS events |
| `_commit` | Input: pending events; Output: committed STS + projection plan |

### 8.3 Snapshot (STS → consumers)

Read-only snapshot fields (normative minimum; aligns centralization_001 §7.4 + POC schema):

- `episode_id`
- `teams` / subject teams
- `fixture` / fixture label
- `topic` / phase
- `date_context`
- `followup_context` (summary)
- `boundary_reason` (last decision)
- `ownership_lock_active` (read from OS; not authored by STS as lock SoT)

Consumers: Response Selector, follow-up gates, Entity honesty, analyze force paths, OS/SCG adapters, engines’ **inputs** only.

### 8.4 Transition decision (Classifier → Graph)

```text
EpisodeTransitionDecision = {
  outcome: KEEP_EPISODE | NEW_FIXTURE | NEW_EPISODE,
  reason: string,           # e.g. new_fixture | soft_followup_same_episode | low_entity_overlap
  current_entities: ...,    # from SLL / fixture phrase
  prior_subject: ...        # from STS snapshot
}
```

Downstream must **consume** this decision; re-detecting in parallel (brain_authority / followup_guard / is_topic_switch) is a migration debt to retire (transition_arch_001).

### 8.5 Projections (STS → legacy keys)

| Projection | Interface rule |
|------------|----------------|
| `last_home` / `last_away` / `last_match` / `last_fixture` | Write-through from STS commit only |
| CSL façade | Schema aligned with STS; `set_csl` private/adapter-only |
| SRF | Refresh from STS; `set_*` only via `apply_bind` / `apply_analysis` |
| short_mem / focus / continuity sport fields | Projection of followup_context / subject |
| `entity_v2_last_bind` | Ephemeral bind cache via STS funnel; cleared on boundary |
| `conversation_state.active_fixture` | Deprecate → projection then eliminate (phase late) |

### 8.6 OS / SCG

| Call | Caller | Constraint |
|------|--------|------------|
| `release_owner_lock` | STS boundary path | On NEW_FIXTURE / NEW_EPISODE |
| `create` / `expire` / note sport anchor | STS funnel | Subject from STS; no invent |
| claim/note ownership | Existing turn owners via public APIs | Lock ≠ subject SoT |

### 8.7 Shadow adapter

| API (conceptual) | Behavior |
|------------------|----------|
| `shadow_from_ctx` | Read-only OLD capture |
| isolated graph update | NEW with `force=True` semantics (POC) |
| `compare_shadow` | Diff + `contamination_locus` ∈ {`before_langgraph`, `inside_state_layer`, `after_state_commit`} |
| `maybe_shadow_compare` | Flag-gated; fail-open; no live mutation |

### 8.8 Flag relationships

| Flag | Default | Role |
|------|---------|------|
| `ENABLE_LANGGRAPH_STATE_SHADOW` | OFF | Log-only OLD vs NEW; no sole-writer |
| `ENABLE_LANGGRAPH_STATE` | OFF | Production host write path |
| `ENABLE_TOPIC_BOUNDARY_V2` | OFF | Legacy/TB-002 path; classify rules may be reused even when V2 apply path differs (POC: detection helpers reused without depending on V2 flag for isolated graph) |
| Future STS funnel flags (centralization_001) | OFF | `ENABLE_STS_READ_ADAPTERS`, `ENABLE_STS_WRITE_FUNNEL_BOUNDARY`, `ENABLE_STS_WRITE_FUNNEL_ANALYZE`, `ENABLE_STS_PROJECTIONS_RO`, `ENABLE_STS_SOLE_WRITER` — conceptual gates aligned under LangGraph host plan |

**Precedence (normative):**

1. If `ENABLE_LANGGRAPH_STATE=0`: production subject writes follow legacy/funnel-migration path only; LangGraph must not write live subject.
2. Shadow may run independently of production write.
3. Production write **requires** sole-writer funnel readiness (research_003 P3 before P4).
4. TB-V2 flag remains independently toggleable during early phases; after cutover, transition decision is centralized inside graph classify — dual materializers (V2 apply + brain_authority apply) must be retired.

---

## 9. Fluxo Completo

### 9.1 Production path (target, flags ON after gates)

```text
1. Ingress: POST /aurora/copilot {session_id, message, …}
2. Load session envelope (conversation_manager) — Memory pillar; not subject SoT
3. SLL normalize → clubs / compare signals
4. Map session_id → thread_id
5. LangGraph invoke(thread_id):
   5.1 init_load ← checkpoint (+ hydrate if cold)
   5.2 classify ← Custom Transition (message, SLL, STS prior)
   5.3 route:
        NEW_FIXTURE / NEW_EPISODE → apply_boundary
        soft FU / keep → keep_followup
        seed / same fixture / overlap OK → apply_subject
   5.4 STS._commit → authoritative subject
   5.5 checkpointer save
6. Projection refresh (legacy keys write-through)
7. OS/SCG public API side-effects as required by boundary/keep
8. Downstream Understanding / Intent / planning consume STS snapshot (no invent)
9. Engines (if analyze/live) — FROZEN; inputs from resolved subject
10. Response Selector reads STS / projections; writes only candidate pool
11. Integrity / credibility / response emit
12. End-of-turn: no independent note_* subject authorship; adapters may call STS events only
```

### 9.2 Shadow path (current POC → hardened)

```text
SLL → (TB-V2/CSL/intent as today) → maybe_shadow_compare
  → OLD from ctx; NEW isolated graph; AUDIT log; locus
  → live path continues unchanged
```

### 9.3 Critical scenario (must succeed on production path)

**Flamengo×Palmeiras → Liverpool×Chelsea → “Quem está melhor?”**

| Turn | Required STS outcome |
|------|----------------------|
| T1 | Subject = Flamengo×Palmeiras; episode E1 |
| T2 | Boundary; subject = Liverpool×Chelsea; episode E2; orphans cleared; **no** Flamengo residual in projections |
| T3 | Soft FU keep E2 + Liverpool×Chelsea |

Shadow evidence: NEW correct on T2 while OLD lagged (`before_langgraph`). Production path must make live state match NEW semantics.

---

## 10. Contratos

### 10.1 Ingress contract

| Item | Spec |
|------|------|
| **Inputs** | `session_id`, `message`, SLL result, session envelope, flag snapshot |
| **Preconditions** | `session_id` non-empty; Code SoT deploy path is `artifacts/aurora/` |
| **Outputs** | Updated session envelope with STS-authoritative subject (when write ON); response pipeline continues |
| **Postconditions** | If write ON and commit succeeded: subject fields consistent across STS + projections; checkpoint advanced |

### 10.2 Transition contract

| Item | Spec |
|------|------|
| **Inputs** | message, SLL clubs, STS prior subject/fixture/episode |
| **Preconditions** | Classifier is Aurora custom; no Rasa/LangGraph domain substitute |
| **Outputs** | Single decision per turn at classify node |
| **Postconditions** | No parallel detector may apply a conflicting materialization after cutover |

### 10.3 STS commit contract

| Item | Spec |
|------|------|
| **Inputs** | Pending events from apply_* nodes |
| **Preconditions** | Exactly one commit path; events validated (e.g. boundary requires clear+replace) |
| **Outputs** | New STS snapshot; projection plan; observability stamps |
| **Postconditions** | On NEW_FIXTURE/NEW_EPISODE: episode changed; teams/fixture replaced; orphans cleared; OS release + SCG expire invoked via public APIs |

### 10.4 Shadow contract

| Item | Spec |
|------|------|
| **Inputs** | message, ctx (read-only) |
| **Preconditions** | `ENABLE_LANGGRAPH_STATE_SHADOW=1` |
| **Outputs** | Log/metrics dict; contamination locus |
| **Postconditions** | Live subject stores unchanged |

### 10.5 Read consumer contract

| Item | Spec |
|------|------|
| **Inputs** | `SportTopicState.snapshot` |
| **Preconditions** | Consumer is allow-listed (RS, gates, honesty, adapters) |
| **Outputs** | Derived UX / routing decisions |
| **Postconditions** | No subject key mutation |

### 10.6 Illegal write contract (after cutover)

Any write to subject keys outside STS commit is **contract violation**: must no-op + audit-fail in tests (centralization Phase 5 semantics) and must not silently succeed in production when `ENABLE_STS_SOLE_WRITER` (or equivalent) is ON.

---

## 11. Estados Internos

### 11.1 STS authoritative fields

| Field | Meaning |
|-------|---------|
| `episode_id` | Conversational sport episode identity |
| `teams` | Subject teams |
| `fixture` | Fixture label / match identity string |
| `topic` / `phase` | Topic phase (CSL-aligned) |
| `date_context` | Date grounding for subject |
| `followup_context` | Soft-FU window summary |
| `boundary_reason` | Last transition reason |
| `subject` / meta | POC-aligned subject markers as needed for graph |

### 11.2 Graph routing state (ephemeral per turn)

| State | Meaning |
|-------|---------|
| Loaded STS baseline | From checkpoint |
| Transition decision | From classify |
| Pending events | Pre-commit |
| Contamination locus (shadow only) | Diagnostic |

### 11.3 Projection states (non-authoritative after cutover)

Legacy triad clusters (centralization_001 §4) become **derived**:

1. Canonical fixture triad: `last_*` ↔ CSL ↔ SRF  
2. Soft-FU referent triad: short_mem ↔ continuity ↔ focus  
3. “What game” triad: SCG anchor ↔ `active_fixture` ↔ `entity_v2_last_bind`

### 11.4 KEEP external states (not STS-owned)

| State | Owner |
|-------|-------|
| `ownership_stability` lock blob | OS module |
| SCG TTL/anchor mechanics | SCG module (fields sourced from STS) |
| Response selector candidate pool | Response Selector |
| Engine analysis payloads | Engines / analyze path |
| Long-term Memory DB collections | Memory pillar |

---

## 12. Persistência

| Store | What persists | Authority |
|-------|---------------|-----------|
| LangGraph checkpointer (per `thread_id`) | STS graph state snapshots | Context Manager durability for sport subject host state |
| `conversation_manager` RAM+SQLite | Session envelope | Memory/session; must not become competing subject SoT |
| Projection keys inside session ctx | Compatibility mirrors | Derived from STS when write path ON |
| Engine / knowledge / learning DBs | Sports domain | Frozen / other pillars — out of STS |

**Rules:**

- Checkpoint must remain **lean** (research_003 R6): subject + episode + followup summary + boundary stamp — not full analyze blobs.
- Cache is **never** SoT (Audit authority order).
- Cross-node Autoscale: without sticky sessions, Memory miss is known (Audit); checkpointer backend for multi-process must be shared (SQLite file locality insufficient → Postgres when horizontally scaled).
- Long-term facts belong in Memory/Knowledge stores, not inflated checkpoints.

---

## 13. Checkpoints

### 13.1 Keys

| Key | Definition |
|-----|------------|
| `thread_id` | Deterministic function of Aurora `session_id` (stable, unique per session) |
| `checkpoint_ns` (if used) | Optional namespace for Context Manager graph only — must not collide with future unrelated graphs |
| `checkpoint_id` | Framework-assigned per super-step; used for resume/time-travel diagnostics |

### 13.2 When to checkpoint

- After successful STS `_commit` for the turn (minimum).
- Must not checkpoint partial classify without commit when production write ON (avoid half-applied subject).

### 13.3 What is in a checkpoint

- STS authoritative fields (§11.1).
- Minimal graph channels required to resume.
- **Exclude:** frozen engine internals, raw provider payloads, Response Selector pools, secrets.

### 13.4 Backend progression (conceptual)

| Stage | Backend | Gate |
|-------|---------|------|
| Dev/POC | InMemory or local SQLite | Shadow / single node |
| Staging | SQLite durable file | Restart recovery tests pass |
| Multi-instance prod | Postgres (or equivalent shared checkpointer) | Horizontal scale requirement |

---

## 14. Recuperação

| Scenario | Behavior |
|----------|----------|
| Process restart, same `session_id` | Mapper resolves `thread_id`; load latest checkpoint; hydrate STS; projections refresh from STS |
| Missing checkpoint (cold session) | `init_load` empty/default STS; first subject seed via `apply_subject` / analysis events |
| Corrupt checkpoint | Fail-closed on production write path: do not guess sticky subject from peer caches; open new episode or refuse contaminated hydrate (emit AUDIT); soft product copy may ask clarify — **must not** silently reuse divergent triad |
| Shadow path failure | Fail-open; live path continues (POC) |
| `langgraph` import missing | Shadow: sequential fallback OK; Production write: **fail-closed** (cannot claim order guarantees) — see §15 |
| Partial migration (funnel incomplete) | Production write flag must remain OFF |

**Recovery invariant:** After restart, soft FU must not resurrect a fixture that was cleared by a committed boundary in a prior checkpointed turn.

---

## 15. Tratamento de Erros

### 15.1 Credibility policy (betting-critical subject)

| Path | Mode | Rationale |
|------|------|-----------|
| Shadow compare | **Fail-open** | Observability must not break turns (POC + Audit) |
| Production STS write / commit | **Fail-closed** on subject mutation errors | Wrong sticky fixture destroys betting credibility more than a controlled degrade |
| Transition classify exception | Production: **fail-closed** toward safe boundary or no subject invent (no silent keep of contested sticky prior when message states new fixture); exact product UX copy deferred but **must not** analyze prior fixture against new named fixture |
| Projection refresh failure after successful commit | Retry refresh; if still failing, mark projections stale + AUDIT; STS snapshot remains authoritative for consumers that can read snapshot API |
| Illegal legacy write attempt after cutover | Block / no-op + AUDIT (+ test fail) | Sole-writer integrity |
| OS/SCG public API failure | Boundary clear still requires subject replace in STS; lock/anchor best-effort with AUDIT — subject correctness > lock cosmetics |

### 15.2 Explicit anti-patterns

- Fail-open production write that leaves multi-writer cascade authoritative.
- Healing soft FU on contaminated OLD (CONTAMINATION_NOTES).
- Claiming TB-002/STS “fixed in production” while flags default OFF.

---

## 16. Compatibilidade

### 16.1 With current Aurora (as-is)

| Surface | Compatibility approach |
|---------|------------------------|
| `POST /aurora/copilot` | Unchanged external API |
| SLL | KEEP; input to classify |
| TB-V2 | Rules reused; apply path migrates into STS funnel / graph |
| CSL / SRF / short_mem / continuity / focus | Temporary writers → projections |
| Response Selector | KEEP; read STS |
| OS / SCG | KEEP modules; adapter call sites |
| Frozen engines | Untouched |
| Feature flags | Additive; defaults remain OFF until gates |
| `artifacts/aurora/` vs `aurora/` | Deploy SoT = artifacts; mirror drift must be resolved before production write (Audit R5) |

### 16.2 POC → contract evolution (no code in this mission)

| POC asset | Evolves into |
|-----------|--------------|
| `sport_topic_state.py` | Normative STS schema + commit API |
| `langgraph_state_graph.py` | Production host graph with same topology family: `init_load → classify → {apply_boundary\|keep_followup\|apply_subject}` |
| `langgraph_state_adapter.py` | Shadow + eventual hydrate/compare metrics harness |
| Flags `ENABLE_LANGGRAPH_STATE(_SHADOW)` | Remain; production write gated by sole-writer readiness |
| Shadow harness / CONTAMINATION_NOTES | Golden scenario suite for validation |
| Sequential fallback | Shadow-only after cutover policy |

### 16.3 Audit pillars / Frozen / specializations

- Context Manager pillar: **Substituir** via this architecture (Audit §3.2).
- Frozen candidates (engines, OS, SCG, SLL KEEP, Response Selector, …): **must not** be redesigned here.
- Specializations (e.g. Conversation Personalization): **never modify Core** STS internals; consume public snapshot API only.

### 16.4 Documento Mestre

**INSUFFICIENT EVIDENCE.** Spec uses Audit 001 + listed ARCH reports as governance proxies. Formal Substitution sign-off against master doc is **blocked** until master doc appears in-repo (research_003 R2 / Audit R2).

---

## 17. Plano de Migração

Conceptual **6 phases**, aligning research_003 §8 with centralization_001 §8 (merged, no code).

| Phase | Name | Intent | Gate to exit |
|-------|------|--------|--------------|
| **P0** | Governance proxy | Ratify Audit 001 + research_003 + this SPEC as interim authority; explicit Documento Mestre INSUFFICIENT EVIDENCE | Architecture review (Missão 005) accepts SPEC |
| **P1** | Transition hygiene | Centralize `EpisodeTransition.decide` (KEEP CUSTOM); detector ownership map closed; classify node consumes single decision | No conflicting materializers on staging with flags under test |
| **P2** | Shadow hardening | Expand LangGraph STS shadow vs OLD; track loci; divergence metrics | Locus `(2) inside_state_layer` rare; `(1)` understood as legacy lag; harness green |
| **P3** | Sole-writer funnel (gated) | All subject writes call STS.commit; projections write-through; OS/SCG via public APIs; **dual-write forbidden in design** | Funnel flags prove single path; `ENABLE_LANGGRAPH_STATE` still OFF |
| **P4** | Production host write | Enable `ENABLE_LANGGRAPH_STATE` behind flag; choose checkpointer backend; rollback proven | Shadow green + restart recovery + bleed scenarios pass with write ON |
| **P5** | Writer retirement | Demote CSL/SRF/short_mem/continuity/focus/`last_*`/brain_authority apply/legacy conversation_state subject authors to read projections; sole-writer assert | Forbidden writers list enforced in tests; defaults reconsidered only with evidence |

**Principles:** incremental; perception validated before elegance; frozen engines never in diff; specializations consume Core STS API only; never enable P4 before P3.

### 17.1 Exact forbidden writers after cutover (P5)

The following **must not** independently mutate sport subject fields (`episode_id`, teams, fixture/subject triad, SRF subject, sport sticky `last_*`, short_mem sport subject, continuity/focus sport subject, `active_fixture` subject, bind subject) except via STS funnel:

1. Topic Boundary V2 **apply** (decide OK; apply → STS only)  
2. CSL `set_csl` / `note_csl_after_response` (adapter only)  
3. SRF `save_srf` / `set_fixture` / `set_team` / `project_from_ctx` invent (refresh only)  
4. Entity Resolver v2 bind writers (via STS.apply_bind only)  
5. Short conversation memory sport keys  
6. Message intelligence `clear_fixture_context` / shift / sticky pops (orchestrated by STS boundary)  
7. Router `_save_analysis_context` direct `last_*` (via STS.apply_analysis)  
8. Conversation focus sport fields  
9. Conversation continuity sport fields  
10. Sport Continuity Guard `setdefault(last_match, …)` invent  
11. Ownership Stability storing fixture subject (lock only)  
12. Brain Authority boundary **apply** materializer  
13. Legacy `conversation_state.active_fixture` author  
14. Pronoun continuity sport subject authorship  

**Allowed non-subject writes remain:** Response Selector pool, SLL `ctx["sll"]`, engine outputs, Memory DBs, OS lock blob, SCG TTL mechanics (fields sourced from STS).

---

## 18. Critérios de Teste

| ID | Criterion |
|----|-----------|
| T1 | Unit: STS commit is only mutator under sole-writer flag (illegal writers no-op/audit-fail). |
| T2 | Unit: classify outcomes cover NEW_FIXTURE, NEW_EPISODE, KEEP/soft FU, same-fixture restate. |
| T3 | Graph order: classify precedes subject commit (no CSL/intent rewrite before boundary on production path). |
| T4 | Golden sticky scenario Flamengo→Liverpool→soft FU (production write ON): T2 subject Liverpool; T3 keep Liverpool; no “Mantendo foco Flamengo”. |
| T5 | Orphan clear: SRF, `entity_v2_last_bind`, short sport mem cleared on boundary commit. |
| T6 | `note_csl` disjoint payload blocked / cannot overwrite new subject (TB-002 semantics preserved). |
| T7 | Shadow: live ctx unchanged; locus codes stable; fail-open on adapter errors. |
| T8 | Restart recovery: checkpoint restore yields same episode/subject before soft FU. |
| T9 | Flag matrix: defaults OFF; shadow≠write; write OFF ⇒ no live STS mutation. |
| T10 | Frozen engines / Response Selector / OS / SCG internals: no behavioral contract change tests required beyond public API call-site expectations. |
| T11 | Dual-SoT detection tests: if write ON and a legacy writer mutates subject, test fails. |
| T12 | Missing langgraph package: shadow fallback OK; production write path refuses silent degrade. |

---

## 19. Critérios de Validação

| ID | Validation |
|----|------------|
| V1 | Architecture matches research_003 primary decision (LangGraph host + STS sole writer + KEEP CUSTOM). |
| V2 | Audit 001 Context Manager Substituir addressed without violating Frozen list. |
| V3 | Documento Mestre gap explicitly labeled INSUFFICIENT EVIDENCE; no invented master requirements. |
| V4 | Shadow metrics: divergence explained; locus (2) not dominant on golden suite. |
| V5 | Production write enabled only after P3 funnel evidence. |
| V6 | Perception parity: soft FU, analyze honesty, boundary scenarios pass with flags under test. |
| V7 | Specializations do not patch Core STS modules. |
| V8 | Deploy path single SoT (`artifacts/aurora/`) before production write. |
| V9 | Missão 005 spec review completed before any implementation mission. |

---

## 20. Critérios para Frozen

A module/asset may be treated as **Frozen relative to Context Manager work** when:

| ID | Criterion |
|----|-----------|
| F1 | Listed in Audit 001 Frozen Candidates / `docs/FROZEN_MODULES.md` / code FROZEN headers (engines, OS, SCG, guards, Decision Center, Knowledge, follow_up_engine formulas, analyze integrity contracts, etc.). |
| F2 | Context Manager substitution **does not** require editing their internal algorithms — only public API call-site ordering/arguments. |
| F3 | Response Selector remains read-only w.r.t. fixture SoT (pool writes only). |
| F4 | SLL remains perception KEEP; not replaced by graph. |
| F5 | STS/LangGraph host reaches sole-writer + recovery + golden bleed suite green under production flag — then Context Manager itself may be proposed for **Congelar** in a later audit (not automatic in Missão 004). |
| F6 | Until F5, Context Manager remains Replacement Candidate; flags default OFF. |

**Explicitly not Frozen as subject SSOT:** CSL, SRF, short_mem, conversation_state, multi-writer cascade (Audit §4).

---

## 21. Riscos

| ID | Risk | Sev | Mitigation |
|----|------|-----|------------|
| R1 | Dual-SoT if LangGraph write ON while 14 writers remain | 🔴 | P3 before P4; dual-write forbidden; T11 |
| R2 | Documento Mestre absent — governance gap | 🔴 | INSUFFICIENT EVIDENCE label; block formal Substitution sign-off |
| R3 | Sticky bleed returns (flags OFF / fail-open prod) | 🔴 | Sole-writer + order edges; fail-closed prod write; no false “fixed” claims |
| R4 | LangGraph becomes sport-logic SoT (scope creep) | 🟠 | KEEP CUSTOM in contract; nodes only call Aurora detect |
| R5 | `aurora/` vs `artifacts/aurora/` drift | 🟠 | Single deploy SoT before P4 |
| R6 | Checkpoint bloat / latency | 🟡 | Lean STS snapshots |
| R7 | LangGraph dependency/ops burden | 🟡 | Pin versions; custom STS-only contingency (research_003 shortlist #2) |
| R8 | Split transition detectors persist | 🟠 | P1 centralize decide; retire parallel apply |
| R9 | Soft FU on contaminated prior | 🔴 | Ensure switch turn commits NEW; shadow locus (1) monitoring |
| R10 | OS/SCG internal redesign temptation | 🟠 | Adapters + public APIs only |

---

## 22. Decisões Arquiteturais (ADR)

**ADR count: 12**

### ADR-001 — LangGraph as state host
**Decision:** Use LangGraph as host for typed state, ordered edges, and checkpointers.  
**Why:** Audit public solution; existing POC shadow proves NEW_STATE correct under lag; native order enforcement for boundary-before-rewrite.  
**Rejected:** Hostless custom STS only as primary (kept contingency).

### ADR-002 — STS as sole writer
**Decision:** Aurora Sport Topic State is the only writer of sport conversational subject.  
**Why:** ≥14 writers cause sticky bleed class; TB-002 insufficient as end-state architecture (centralization_001).  
**Rejected:** Continued multi-writer patches.

### ADR-003 — KEEP CUSTOM TRANSITION inside graph
**Decision:** Transition classification remains Aurora custom (TB-V2 / EpisodeTransition), hosted in classify node.  
**Why:** Binding `topic_transition_arch_001`; frameworks lack PT football fixture/soft-FU policy.  
**Rejected:** Framework-provided dialogue policies as classifier.

### ADR-004 — Do not adopt Rasa as Context Manager / transition runtime
**Decision:** Rasa tracker/runtime not adopted.  
**Why:** Wrong embed weight; dual tracker risk; does not classify fixtures; prior ARCH rejection; commercial Pro surface.  
**Borrowable concept only:** event/slot discipline (mental model).

### ADR-005 — Do not adopt full LangGraph sport logic
**Decision:** LangGraph must not own sport domain rules, engines, or Response Selector.  
**Why:** Frozen philosophy; KEEP CUSTOM; perception risks from elegance-driven rewrite.  
**Scope limit:** host/orchestration/checkpointer only for this pillar.

### ADR-006 — Shadow before production write
**Decision:** `ENABLE_LANGGRAPH_STATE_SHADOW` metrics precede `ENABLE_LANGGRAPH_STATE`.  
**Why:** POC + Audit R3 dual-SoT risk.  
**Rule:** Shadow ≠ activation.

### ADR-007 — Dual-SoT prohibition
**Decision:** No parallel authoritative subject authors once production write enabled.  
**Why:** Research_003 R1; contamination locus shows legacy lag class.  
**Implication:** P3 funnel mandatory before P4.

### ADR-008 — Fail-open shadow / fail-closed production subject writes
**Decision:** Shadow errors must not break turns; production subject commit errors must not silently fall back to multi-writer sticky.  
**Why:** Betting credibility > availability of wrong fixture context.

### ADR-009 — Preserve SLL, Response Selector, OS/SCG public APIs, frozen engines
**Decision:** Non-negotiable KEEP set for this substitution.  
**Why:** Audit Frozen Candidates; centralization_001 KEEP table; never regress AEP guards/engines.

### ADR-010 — Projections instead of big-bang key deletion
**Decision:** Demote `last_*`/CSL/SRF/… to write-through projections before removal.  
**Why:** Deep call graph; incremental migration (centralization_001).

### ADR-011 — Session identity via stable thread_id mapping
**Decision:** Checkpoint key = mapped `thread_id(session_id)`.  
**Why:** Restart recovery and multi-turn soft FU require durable identity isolation.

### ADR-012 — Documento Mestre gap acknowledged
**Decision:** Proceed with Audit/ARCH proxies; do not invent master-doc content; block formal master-compliance certification.  
**Why:** INSUFFICIENT EVIDENCE (Audit 001 / research_003).

---

## Validation Contract

| # | Question | Answer |
|---|----------|--------|
| 1 | **Ambiguities remaining?** | **YES (listed below).** Documento Mestre content unknown; exact product UX copy on fail-closed classify errors; Postgres vs SQLite cutover threshold in ops; precise merge calendar of centralization STS flags vs LangGraph flags naming (semantic alignment specified; final env names may be consolidated in implementation mission); full Orchestration pillar replacement timing (out of scope). |
| 2 | **Undefined responsibilities?** | **No for Context Manager sole-writer path.** Adjacent pillars (Tool Use, Execution Manager, full Orchestration rewrite) remain undefined by design (Audit Substituir elsewhere) and must not be smuggled into STS. Transition detector retirement schedule detail belongs to P1 implementation design under this SPEC’s ADR-003. |
| 3 | **Excessive coupling?** | **Controlled coupling:** Router↔Host invoke and STS↔projections are intentional. **Forbidden coupling:** LangGraph↔engine internals; specializations↔STS private commit; Rasa↔session. If projections remain writable, coupling/risk returns — mitigated by P5. |
| 4 | **Conflict with Documento Mestre?** | **INSUFFICIENT EVIDENCE** — master doc not in repo; cannot certify compliance or conflict. Proxies: Audit 001 pillars + Frozen policy + “specializations never modify Core.” |
| 5 | **Supports future evolution?** | **YES.** Host/checkpointer can deepen; STS schema can version; custom transition can centralize further; contingency to drop LangGraph host while keeping STS sole-writer (research_003 shortlist #2); Memory/Orchestration pillars can adopt same thread identity later without rewriting engines. |

### Remaining ambiguities (explicit list)

1. Documento Mestre Etapa 1 requirements (absent).  
2. Final unified flag taxonomy naming (LangGraph vs `ENABLE_STS_*`) — semantics binding; names consolidatable later.  
3. Exact user-visible degrade copy when production classify/commit fail-closes.  
4. Ops threshold for mandating Postgres checkpointer.  
5. Timeline to retire `aurora/` mirror drift (process), though requirement to resolve before P4 is binding.

---

## Evidence index

| Topic | Path |
|-------|------|
| Primary architecture decision | `observations/aurora_context_manager_research_003/REPORT.md` |
| Audit Context Manager Substituir / Frozen | `observations/aurora_core_audit_001/REPORT.md` |
| 14 writers / STS / phases | `observations/topic_state_centralization_001/REPORT.md` |
| KEEP CUSTOM TRANSITION | `observations/topic_transition_arch_001/REPORT.md` |
| LangGraph STS POC | `observations/langgraph_state_poc_001/REPORT.md` |
| POC architecture | `observations/langgraph_state_poc_001/ARCHITECTURE.md` |
| Contamination loci | `observations/langgraph_state_poc_001/shadow/CONTAMINATION_NOTES.md` |
| Sticky bleed RCA | `observations/sticky_bleed_001/REPORT.md` |
| TB-002 / flag default | `observations/topic_boundary_002/REPORT.md` |

---

```
FACT:
Engineering SPEC for LangGraph-hosted SportTopicState (STS) Sole-Writer Context
Manager delivered. KEEP CUSTOM TRANSITION hosted in graph. Documento Mestre =
INSUFFICIENT EVIDENCE. No Aurora product code modified. Implementation NOT
authorized.

NEXT:
Missão 005 — SPEC review (do not execute in Missão 004).
```
