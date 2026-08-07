# AURORA TASK — ARCHITECTURE_SPECIFICATION / DESIGN (Missão 004) — Spec 004 v1.2

**Type:** Engineering specification — **NO PRODUCT CODE, NO IMPLEMENTATION, NO MODULE MODIFICATIONS**  
**Version:** **1.2** (residual closure of Spec 004 v1.1 per Plan 010)  
**Date:** 2026-08-07  
**Deliverable path:** `observations/aurora_context_manager_spec_004/SPEC_v1.2.md`  
**Historical v1.0 (unchanged):** `observations/aurora_context_manager_spec_004/SPEC.md`  
**Prior normative v1.1 (unchanged):** `observations/aurora_context_manager_spec_004/SPEC_v1.1.md`  
**Role:** Specification Engineer (Missão 012 — CONTROLLED_EXECUTION residual closure only)  
**Revision authority:** Spec 004 v1.1 + RESIDUAL_BLOCKER_PLAN 010 authorized items only (CDR2-F1 via SSOT Path A; FINDING-014; FINDING-016; CDR2-F2…F6) — **nothing else**  
**Implementation authorization:** **NOT AUTHORIZED.** **IMPLEMENTAÇÃO BLOQUEADA.** Next process step is Missão 013 (CDR3). Do not start CDR3 in this mission.

**Formula:** Spec 004 v1.1 + Plan 010 residual closures = Spec 004 v1.2.

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
| `observations/aurora_context_manager_governance_006/RESOLUTION_MATRIX.md` | ACCEPT/REJECT/DEFER; normative Ação Recomendada for v1.1 |
| `observations/aurora_context_manager_governance_006/AAR-001.md` | Board NOT APPROVED; binding path Spec v1.1 → CDR → AAR |
| `observations/aurora_context_manager_revision_plan_007/REVISION_PLAN.md` | Official application order 1..24 for v1.1 |
| `observations/aurora_context_manager_cdr2_009/CDR2.md` | Hostile review; residual F1–F6 + PARTIAL 014/016 |
| `observations/aurora_context_manager_aar_002/AAR-002.md` | Board NOT APPROVED; liberação criteria for residual closure |
| `observations/aurora_context_manager_residual_plan_010/RESIDUAL_BLOCKER_PLAN.md` | Documentation-only residual closure paths for v1.2 |
| `docs/architecture/master-architecture.md` | Official Documento Mestre / Master Architecture (SSOT Path A; CDR2-F1) |
| `docs/architecture/README.md` | SSOT navigation; SSOT root = `docs/architecture/` |
| `docs/architecture/governance/SSOT_POLICY.md` | Versioning, approval, freeze-while-NOT-APPROVED, F1 closure criteria |

**Documento Mestre / Architecture SSOT (CDR2-F1 — Path A):** Official Master Architecture is **in-repo** at `docs/architecture/master-architecture.md` (VERSION 2026.08.06; Git-versioned at commit `9f53678`), with SSOT root declared in `docs/architecture/README.md` and policy in `docs/architecture/governance/SSOT_POLICY.md`. Prior Audit 001 label **INSUFFICIENT EVIDENCE** *for master-document absence* is **superseded** for pillars/policies recorded in the Master (Master §0; SSOT_POLICY §7–§8). This SPEC remains a **Context Manager specialization** under Core; it must stay compatible with Master pillars, Frozen policy, and “specializations never modify Core.” **Technical Spec acceptance ≠ Substitution authorization** (FINDING-006) — Substitution still requires Master (present) **plus** residual disposition **plus** APPROVED AAR.

**Deploy SoT (normative):** Production deploy path **must** be `artifacts/aurora/`. Open mirror drift `aurora/` vs `artifacts/aurora/` is an explicit **P4 NO-GO** (FINDING-024). Hard release assertion: fail-closed if required LangGraph/STS modules are absent from the deploy tree (see §16.1, §17 P4, V8).

**Matrix-authorized selections instantiated in v1.1 and retained in v1.2 (exactly one per Matrix fork; no third architecture):**

| Fork | Finding | Normative selection in this Spec |
|------|---------|----------------------------------|
| P3 commit host | FINDING-001 | **Option A** — Minimal non-LangGraph Commit Orchestrator with **same** edges/commit/projection semantics as P4 LangGraph host; second ad hoc commit path **prohibited** |
| Durability boundary | FINDING-003 | **Option A** — Checkpoint includes projection plan + `subject_generation`/epoch; consumers **must** discard/refuse on generation mismatch; absolute STS+projection consistency claim removed |
| Multi-node subject authority | FINDING-008 | **Shared session envelope SoT** for projection-bearing subject reads; sticky sessions = complement only, never substitute |
| Concurrent same-`thread_id` conflict | FINDING-007 | **Queue** (serial lease FIFO); bounded wait then **HTTP 429**; refuse merge |
| Classify degrade machine | FINDING-010 | **Single machine:** `safe_boundary_clear` (see §15.1) |
| OS/SCG completeness | FINDING-016 | Required OS/SCG side-effects in boundary commit **stage**; incomplete = **fail-closed** production write; **Disposition D2** (v1.2) — consumer-blocking Stage-5-incomplete flag (CDR2-F3) |
| Corrupt checkpoint | FINDING-023 | **Single branch:** refuse contaminated hydrate → AUDIT → cold empty STS → UX clarify |

**Plan 010 residual closures instantiated in v1.2 (documentation only; no new ADR ids):**

| Residual | Normative selection in this Spec |
|----------|----------------------------------|
| CDR2-F1 | **Path A** — cite official SSOT `docs/architecture/` (Master + README + SSOT_POLICY); no blanket Substitution waiver |
| FINDING-014 / CDR2-F2 | Named falsifiable **P2 Ingress-Order Success Criteria** for `ingress_order_shadow_compare` (§9.2 / Appendix B / T21) |
| FINDING-016 / CDR2-F3 | **Disposition D2** — binding consumer-blocking Stage-5-incomplete semantics (§10.3); no checkpoint undo / 2PC |
| CDR2-F4 | Binding **shared-envelope durability interface contract** (§12); unmet ⇒ P4 multi-instance NO-GO |
| CDR2-F5 | Queue wait bound **5000 ms**; multi-instance write requires **shared lease store** (§8.1); DEFER-017 remains deferred |
| CDR2-F6 | Enforceable mechanism class = **ctx proxy** (§10.6); logging-only stub forbidden |

---

## 1. Executive Summary

This specification defines the **Aurora Core Context Manager** replacement as a **SportTopicState (STS) Sole-Writer Context Manager** hosted by a **phase-specific Commit Host**:

- **P3 Commit Host (normative — Matrix Option A):** a **Minimal Commit Orchestrator** (non-LangGraph) that executes the **same** ordered edges, commit stages, projection, and OS/SCG side-effect semantics as the P4 host.
- **P4 Commit Host (target):** **LangGraph** hosts typed graph state, ordered edges, and checkpointer durability — **ADR-001 is provisional** pending P2/P3 kill criteria (FINDING-020); flip triggers to contingency (custom STS without LangGraph) are normative (see ADR-001).
- **Aurora-owned STS** is the **only** component authorized to write sport conversational subject (`episode_id`, teams, fixture, topic/phase, date_context, followup_context summary, boundary stamps consumed).
- **KEEP CUSTOM TRANSITION** remains Aurora domain logic (TB-V2 / future `EpisodeTransition.decide`), **hosted inside** the Commit Host as classify nodes — **not** replaced by LangGraph or Rasa sport logic.
- Existing LangGraph STS POC assets under `artifacts/aurora/` evolve into this contract; they are not discarded and not rewritten in this mission.
- Migration is **six conceptual phases**, shadow-first, with **dual Source-of-Truth (dual-SoT) prohibited** once production write is enabled.
- Frozen sports engines, SLL, Response Selector, and Ownership/SCG public APIs are preserved; specializations must not modify Core STS internals.
- **Technical Spec acceptance ≠ Substitution Phase authorization** (FINDING-006). Documento Mestre / Architecture SSOT is **present** at `docs/architecture/` (Path A; CDR2-F1). Substitution authorization still requires Master **plus** residual disposition **plus** APPROVED AAR — Spec/CDR/AAR prose alone is never a waiver.

**Perception > elegance.** The architecture attacks the proven sticky-bleed class (multi-writer + ordering/cleanup + message rewrite channel), which episode UUID rotation alone did not fix.

**POC honesty:** LangGraph POC shadow proves classify-under-isolation / NEW_STATE under lag — **not** production sole-writer, multi-node, projection-atomicity, or message-path proof (FINDING-020).

---

## 2. Objetivos

| ID | Objetivo |
|----|----------|
| O1 | Establish a **sole-writer** Context Manager for sport conversational subject state (STS). |
| O2 | Host STS turn updates in a **Commit Host** state machine that **enforces order**: classify/transition **before** subject rewrite/commit (P3 = Minimal Commit Orchestrator; P4 = LangGraph host unless ADR-001 flips). |
| O3 | Preserve **KEEP CUSTOM TRANSITION** (Aurora PT football / fixture / soft-FU policy) inside the Commit Host. |
| O4 | Eliminate independent subject authorship by the current **≥14 write-owners** after cutover (demote to projections / adapters). |
| O5 | Provide **checkpointed** session durability and **recovery after restart** keyed by stable session/thread identity. |
| O6 | Migrate incrementally via flags (shadow → gated funnel → production write → writer retirement) without dual-SoT. |
| O7 | Protect betting credibility: subject switches must be **fail-closed** on write path when production STS is active; shadow remains fail-open. |
| O8 | Keep frozen engines, SLL, Response Selector, OS/SCG public APIs intact; specializations never modify Core. |
| O9 | Remain governance-compatible with Audit 001 and official Architecture SSOT (`docs/architecture/`); separate technical CDR/AAR acceptance from Substitution authorization (FINDING-006 / CDR2-F1 Path A). |

---

## 3. Escopo

**In scope (Context Manager pillar substitution design):**

1. Sport conversational subject SSOT: schema ownership, sole commit, read snapshot API.
2. Commit Host contract: graph/orchestrator topology, node responsibilities, checkpointer, thread identity (phase-specific host — §5.1).
3. Custom transition hosting: classify → route → apply_boundary | keep_followup | apply_subject.
4. Projection/façade contracts for legacy keys (`last_*`, CSL, SRF, short_mem, focus, continuity) with `subject_generation` epoch.
5. Feature-flag / migration-stage matrix and relationship to TB-V2 / STS / LangGraph flags (illegal combinations fail-closed).
6. Persistence, commit stages, checkpoints, recovery, error semantics (fail-open vs fail-closed).
7. Compatibility with current Aurora pipeline and Frozen policy.
8. Conceptual 6-phase migration, test/validation/Frozen criteria, risks, ADRs, rollback matrix.
9. Evolution path from existing POC assets (`sport_topic_state.py`, `langgraph_state_graph.py`, `langgraph_state_adapter.py`, shadow harness).

**Code SoT for future implementation (when authorized):** `artifacts/aurora/` (Audit 001). Mirror `aurora/` must not be assumed parity (TB-V2 / LangGraph absent on mirror). Open mirror drift = **P4 NO-GO**.

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
| N7 | Invent Documento Mestre content outside official SSOT (`docs/architecture/`) or treat Spec/CDR/AAR prose as Substitution waiver. |
| N8 | Enable `ENABLE_LANGGRAPH_STATE` by default or claim bleed “fixed” while production write / sole-writer remain OFF. |
| N9 | Big-bang delete of `last_*` / CSL / SRF physical keys without projection phase. |
| N10 | Redesign OS/SCG internals (only call-site funnel via public APIs). |
| N11 | Apply REJECT-011 or DEFER-017/018 in this Spec revision. |
| N12 | Authorize Substitution Phase via technical CDR/AAR alone. |

---

## 5. Arquitetura Geral

### 5.1 Primary architecture (binding)

**STS Sole-Writer Context Manager with phase-specific Commit Host**  
(Source: research_003 §7; Audit 001 §3.2; centralization_001 §7; transition_arch_001 KEEP CUSTOM; POC_001; RESOLUTION_MATRIX FINDING-001 Option A.)

**Commit Host (normative term — singular per phase):**

| Phase | Legal Commit Host | Notes |
|-------|-------------------|-------|
| Shadow / P2 | LangGraph host **or** sequential shadow fallback | Shadow-only; no production subject write |
| **P3** (sole-writer funnel, `ENABLE_LANGGRAPH_STATE` OFF) | **Minimal Commit Orchestrator (non-LangGraph)** | **Matrix Option A.** Same edges, commit stages, projection plan, OS/SCG stage semantics as P4 host. **Prohibited:** second ad hoc commit path / invent-second-orchestrator |
| **P4+** (production write ON) | **LangGraph State Host** (unless ADR-001 flip) | Same semantic contract as P3 orchestrator; checkpointer durability |

```text
User → POST /aurora/copilot
  → conversation_manager session load (session_id)
  → acquire serial lease on thread_id (production write path)
  → SLL (perception normalize; KEEP)
  → Commit Host (thread_id = map(session_id))
        ├─ init_load          (hydrate STS from checkpoint / projections)
        ├─ classify           (Aurora CUSTOM transition — TB-V2 / EpisodeTransition.decide)
        ├─ apply_boundary | keep_followup | apply_subject
        └─ STS._commit via Commit Gate ★ SOLE WRITER of sport subject
           (numbered commit stages — §10.3)
  → Projection refresh under durability boundary (§10.1 / §13.2)
  → OS / SCG via public APIs only (boundary commit stage; fail-closed if incomplete on prod write)
  → Engines (FROZEN, untouched) when analyze/live required
  → Response Selector (read-only consumer of STS snapshot / projections with epoch check)
  → CopilotResponse
  → release serial lease
```

**Dual orchestration ban:** There is exactly one legal Commit Host per phase. Graph-only `_commit` claims that contradict P3 OFF-LangGraph are **void** under Option A — P3 uses the Minimal Commit Orchestrator, not a silent second invent path.

### 5.2 Sole-writer rule (normative)

| Rule | Statement |
|------|-----------|
| SW-1 | After cutover (`ENABLE_LANGGRAPH_STATE` + sole-writer gate), **only STS commit** (via Commit Gate on the legal Commit Host) may mutate sport subject fields. |
| SW-2 | Transition modules **decide**; they do not independently author subject outside the funnel. |
| SW-3 | Projections may refresh **from STS only**; they must not invent subject from peer caches when STS is authoritative; readers **must** discard on `subject_generation` mismatch. |
| SW-4 | OS lock and SCG anchor remain KEEP modules; subject fields they need are **sourced from STS**; forbidden: `setdefault(last_match, …)` invent outside funnel. |
| SW-5 | Engines and Response Selector **never** write sport subject SoT. |
| SW-6 | After cutover, intent/compare **message rewrite** consumes STS snapshot (or message-side teams pós-SLL) — never CSL sticky pré-STS (FINDING-002). |

### 5.3 What Commit Host / LangGraph hosts vs what Aurora owns

| Concern | Owner |
|---------|-------|
| Ordered edges, super-step / stage order | **Commit Host** (P3 Minimal Orchestrator / P4 LangGraph) |
| Checkpointer snapshot / resume by `thread_id` | **Commit Host** + Aurora-chosen backend (P4 LangGraph checkpointer; P3 orchestrator uses same checkpoint key domain) |
| Typed STS schema fields & semantics | **Aurora STS** |
| Transition classify (new_fixture / soft_FU / new_episode / keep) | **Aurora custom** (hosted as classify step) |
| Sole `_commit` of subject | **Aurora STS** (invoked only from Commit Gate on legal host) |
| Sports math / markets / confidence | **Frozen engines** (outside host ownership) |
| Response candidate selection | **Response Selector** (consumer) |
| Nickname / club normalize | **SLL** (input) |

### 5.4 Dual-SoT prohibition (normative)

| Phase | Allowed |
|-------|---------|
| Shadow (`ENABLE_LANGGRAPH_STATE_SHADOW=1`, write OFF) | Live multi-writer OLD + isolated NEW compare — **log only**; not dual production SoT |
| Funnel gated (write OFF or projection write-through under STS) | Single logical writer path; legacy keys updated **only** via STS adapters; `subject_generation` on STS + projections |
| Production write ON | **Forbidden:** parallel independent subject authorship + STS write; runtime sole-writer guard **must** be active (FINDING-015) |
| Cutover complete | **Forbidden:** any of the 14 legacy writers mutating subject keys outside STS |

**Logical sole-writer vs physical multi-key:** Write-through projections are allowed **only** with mandatory `subject_generation` (epoch) freshness bits on STS and every subject projection; consumers discard mismatch (FINDING-021). Claims of “sole-SoT” without epoch are **non-compliant**.

Enabling `ENABLE_LANGGRAPH_STATE` **before** sole-writer funnel completion recreates Audit R3 dual-SoT and is **out of compliance** with this SPEC. Dual-SoT-by-schedule (write ON before runtime guard / note_* funnel) is **banned** (FINDING-015 / FINDING-026).

### 5.5 Failure modes this SPEC must prevent (sticky bleed / TB-002 evidence)

| Failure mode | Evidence | Spec control |
|--------------|----------|--------------|
| Boundary after CSL/intent rewrite | sticky_bleed_001; TB-002 | Commit Host edges: classify → apply **before** subject consumers see stale triad; message rewrite under STS authority (SW-6) |
| Incomplete orphan clear (SRF, bind, short_mem) | sticky_bleed_001; TB-002 | `apply_boundary` must clear orphans via STS commit **stages** (Unit of Work defined in §10.3) — not fake cross-store “atomic” slogans |
| End-of-turn note_* re-materializes wrong subject | centralization_001 §6 | note_* become adapters → STS or no-ops; **funnel + runtime guard before P4 exit** (FINDING-026) |
| Soft FU preserves contaminated OLD | CONTAMINATION_NOTES locus (1) | Production write path must land NEW on switch turn; soft FU only after correct prior; P2 ingress-order experiment (FINDING-014) |
| Episode UUID rotates but subject does not | sticky_bleed_001 | Subject replace is mandatory on NEW_FIXTURE / NEW_EPISODE |
| Flag OFF fail-open legacy path | TB-002 default OFF; Audit R1 | Credibility: do not claim fixed while defaults OFF; production STS fail-closed when ON |
| Message-derived teams ≠ STS.teams | sticky_bleed_001 | Fail criterion T13 (FINDING-002) |
| Concurrent same-session interleave | Audit R6 | Serial lease per `thread_id` before production write ON (FINDING-007) |

---

## 6. Componentes

**Component count: 17** (C17 added: Minimal Commit Orchestrator — FINDING-001 Option A; no unauthorized split of C2/C7/C8 beyond Matrix)

| # | Componente | Layer | Origin / evolution |
|---|------------|-------|---------------------|
| C1 | **LangGraph State Host** | Infrastructure | POC `langgraph_state_graph.py` → **P4** production host contract (provisional ADR-001) |
| C2 | **Sport Topic State (STS)** | Core Context Manager | POC `sport_topic_state.py` → sole-writer SSOT + `subject_generation` |
| C3 | **Custom Transition Classifier** | Domain decision | TB-V2 detect / future `EpisodeTransition.decide` hosted in classify node |
| C4 | **Graph Node: init_load** | Host node | POC topology (semantic step on both hosts) |
| C5 | **Graph Node: classify** | Host node wrapping Aurora rules | POC topology; KEEP CUSTOM |
| C6 | **Graph Nodes: apply_boundary / keep_followup / apply_subject** | Host nodes | POC topology; materialize via STS; route table Appendix A |
| C7 | **STS Commit Gate (`_commit`)** | Sole writer | Invoked **only** from legal Commit Host; numbered stages §10.3 |
| C8 | **Projection / Façade Layer** | Compatibility | centralization_001 §5 demotions + epoch bits |
| C9 | **Shadow Adapter** | Observability / migration | POC `langgraph_state_adapter.py` |
| C10 | **Checkpoint Store** | Persistence | Checkpointer backend (InMemory→SQLite→Postgres as needed); keys per §13.1 |
| C11 | **Session–Thread Identity Mapper** | Identity | Maps Aurora `session_id` → LangGraph/`thread_id` per §13.1 algorithm |
| C12 | **Feature Flag / Migration Stage Controller** | Governance | Illegal flag matrix + stage enum; fail-closed boot/assert |
| C13 | **Ownership Stability (OS) Adapter** | KEEP module façade | Public APIs only; fed by STS; completeness in commit stage |
| C14 | **Sport Continuity Guard (SCG) Adapter** | KEEP module façade | Public APIs only; fed by STS; completeness in commit stage |
| C15 | **Router Integration Boundary** | Orchestration edge | `copilot_unified_router` call site contract (design) |
| C16 | **Context Observability Stamps** | Observability | AUDIT stamps for boundary/commit/shadow/divergence/recovery |
| C17 | **Minimal Commit Orchestrator** | Infrastructure | **P3 legal Commit Host** (Matrix Option A); same edges/stages/semantics as C1; **not** a second invent path |

**Preserved external collaborators (not Context Manager components, must not be replaced by this SPEC):**

- SLL (`sports_language`)
- Response Selector
- Frozen sports engines (methodology, market, confidence, intelligence, learning, decision_center, knowledge, …)
- `conversation_manager` / Memory pillar stores (session envelope; **shared SoT for multi-node projection-bearing reads** — FINDING-008; not sport subject SoT independent of STS)

---

## 7. Responsabilidades

### C1 — LangGraph State Host
- **P4 Commit Host** when production write ON and ADR-001 not flipped.
- Compile and invoke the STS turn graph once per copilot turn (when write or shadow path active).
- Enforce edge order; do not invent domain outcomes.
- Persist/load graph state via checkpointer.
- Provide sequential fallback when `langgraph` package missing — **shadow only**; production write path must not silently skip order guarantees (see §14 / §15 / T12).

### C2 — Sport Topic State (STS)
- Own schema for sport conversational subject including mandatory `subject_generation` (epoch).
- Expose `snapshot` (read-only) and event apply APIs (`apply_boundary`, `apply_subject`, `apply_analysis`, `apply_followup_window`, `apply_ci_pending`, `apply_bind`).
- Perform **sole** `_commit` that updates authoritative subject fields and emits projection plan + generation.
- Never call frozen engine internals.

### C3 — Custom Transition Classifier
- Pure decision: `KEEP_EPISODE | NEW_FIXTURE | NEW_EPISODE` (+ reason string compatible with TB-V2 reasons: `new_fixture`, `soft_followup_same_episode`, `low_entity_overlap`, …).
- Consume SLL clubs + sticky prior from STS snapshot (not live peer caches when STS authoritative).
- Must not write subject keys directly.
- Emit fully typed `EpisodeTransitionDecision` (§8.4).

### C4 — init_load
- Load checkpointed STS (or hydrate from projections during migration) into host state.
- Validate checkpoint checksum/schema version; on corruption follow §14 single branch.
- Establish turn baseline before classify.
- Enforce serial lease already held for `thread_id` on production write path.

### C5 — classify
- Invoke C3; attach decision to host state; select next edge via Appendix A route table.

### C6 — apply_boundary / keep_followup / apply_subject
- Translate decision into STS events only.
- `apply_boundary`: clear orphans + replace subject + bump episode (TB-002 semantics elevated into STS).
- `keep_followup`: preserve episode/subject; update followup window stamps only.
- `apply_subject`: seed or same-fixture restated / overlap OK → `replace_subject` without false episode rotate.
- Routing is **only** via Appendix A — no bijective ambiguity between KEEP_EPISODE soft-FU and seed/apply_subject.

### C7 — STS Commit Gate
- Single mutation point for authoritative subject blob on the **legal Commit Host for the phase**.
- Execute **numbered commit stages** (§10.3); emit stage identity / completeness signals; observability stamps.
- Refresh projections only under durability boundary (§10.1); **no** fake XA “atomic” claim across stores without defined UoW.
- On NEW_FIXTURE/NEW_EPISODE: OS release + SCG expire are **required stage side-effects** (FINDING-016) — incomplete ⇒ fail-closed production write **and** Disposition **D2** consumer block (§10.3).

### C8 — Projection / Façade Layer
- Maintain compatibility keys for deep call graph: `last_*`, CSL façade, SRF, short_mem sport keys, focus, continuity — each carrying `subject_generation`.
- After cutover: write-through from STS only; ban independent invent.
- Provide read adapters during shadow/read phases; readers discard on generation mismatch.

### C9 — Shadow Adapter
- When `ENABLE_LANGGRAPH_STATE_SHADOW=1`: capture OLD from live ctx; run isolated NEW; log divergence + `contamination_locus`; **never** write back.
- Fail-open (must not break turn).
- P2 must also support ingress-order experiment (post-SLL pre-CSL) with **separate** success criteria published in §9.2 / Appendix B (FINDING-014 / CDR2-F2).

### C10 — Checkpoint Store
- Persist STS host state per `thread_id` at defined commit-stage boundary (§13.2).
- Checkpoint payload includes STS fields, `subject_generation`, projection plan, checksum, schema version.
- Keep snapshots lean (subject fields, not engine payloads / large analysis blobs).

### C11 — Session–Thread Identity Mapper
- Deterministic mapping `session_id → thread_id` per §13.1 (algorithm, length, namespace, empty/anon handling).
- Guarantee isolation across sessions; stable across process restart for same session.

### C12 — Feature Flag / Migration Stage Controller
- Interpret flags consistently (unset/`0`/`false`/`off`/`no` → OFF; `1`/`true`/`on`/`yes` → ON — POC/TB-V2 pattern).
- Enforce **illegal flag matrix** / migration-stage enum at boot/assert — **fail-closed** (FINDING-009); see §8.8.
- Prose precedence alone is insufficient; machine-checkable matrix is normative.

### C13 — OS Adapter
- Call `claim` / `release` / note APIs with STS-sourced identity; do not store fixture subject inside OS as SoT.
- Boundary required side-effects participate in commit stage completeness (FINDING-016).

### C14 — SCG Adapter
- Call create/expire/note with STS-sourced fixture; forbid independent `last_match` seed invent.
- Boundary required side-effects participate in commit stage completeness (FINDING-016).

### C15 — Router Integration Boundary
- Define exact pipeline insertion: after SLL, before subject-consuming layers when production path ON.
- Acquire/release serial lease around Commit Host invoke on production write path.
- Preserve fail-open shadow hook position from POC until cutover.
- Enforce message-authority rule (SW-6) for intent/compare rewrite after cutover.

### C16 — Context Observability Stamps
- Emit AUDIT lines for: shadow compare, boundary decision, commit stages, projection refresh, blocked illegal writes, recovery events, incomplete OS/SCG, lease conflicts, degrade machine transitions.

### C17 — Minimal Commit Orchestrator (P3 Commit Host)
- Legal Commit Host for P3 while `ENABLE_LANGGRAPH_STATE` is OFF (Matrix Option A).
- Must implement the **same** semantic edges: `init_load → classify → {apply_boundary|keep_followup|apply_subject} → Commit Gate stages`.
- Must not invent divergent commit/projection/OS/SCG semantics vs P4 LangGraph host.
- **Prohibited:** a second ad hoc production commit path outside C17 (P3) / C1 (P4).

---

## 8. Interfaces

### 8.1 Turn ingress (Router → Context Manager)

| Field | Direction | Notes |
|-------|-----------|-------|
| `session_id` | in | Aurora session identity; mapped to `thread_id` per §13.1 |
| `message` | in | Raw user text (post any transport decode) |
| `sll` result | in | Normalized clubs / compare signals |
| `ctx` envelope | in/out | Session dict; subject keys owned by STS after cutover; multi-node: shared envelope SoT (FINDING-008) |
| flags | in | Env / config snapshot for this process |
| lease | internal | Serial lease on `thread_id` before production write path proceeds (FINDING-007) |

**Concurrency (normative — FINDING-007 / CDR2-F5):** Before production write ON, same-`session_id` / `thread_id` turns **must** execute serially via lock/lease. Conflict policy (singular): **queue** (FIFO wait under lease). **Queue wait bound = 5000 ms (5 seconds)** — wait for serial lease exceeded → **HTTP 429**; **refuse merge** of concurrent turn payloads. Last-writer-wins silence is **removed**.

**Multi-node lease authority (CDR2-F5):** When multi-instance production write is claimed, lease authority **must** be a **shared lease store** (process-global / in-process mutex alone is **banned** under horizontal scale). Single-node deployment may use process-local lease **only** while multi-instance write remains **unclaimed**; claiming multi-instance write without shared lease store = **P4 NO-GO**. **DEFER-017** (lock acquisition order envelope vs checkpointer) remains **deferred** and visible — this lease-authority rule does **not** close DEFER-017. See §11.5 Race matrix and T14.

### 8.2 Host invoke (Commit Host ↔ STS)

| Interface | Contract |
|-----------|----------|
| `init_load` | Input: `thread_id`, checkpoint, optional hydrate snapshot; Output: host state with STS baseline + generation |
| `classify` | Input: message + STS prior + SLL; Output: typed `EpisodeTransitionDecision` |
| apply nodes | Input: decision + candidate entities; Output: pending STS events (node selected via Appendix A) |
| `_commit` (Commit Gate) | Input: pending events; Output: committed STS + projection plan + stage completeness signals + `subject_generation` |

Legal host: C17 in P3; C1 in P4 (unless ADR-001 flip — then contingency host preserves same invoke contract).

### 8.3 Snapshot (STS → consumers)

Read-only snapshot fields (normative minimum; aligns centralization_001 §7.4 + POC schema):

- `episode_id`
- `teams` / subject teams
- `fixture` / fixture label
- `topic` / phase
- `date_context`
- `followup_context` (summary)
- `boundary_reason` (last decision)
- `subject_generation` (**mandatory epoch** — FINDING-021)
- `ownership_lock_active` (read from OS; not authored by STS as lock SoT)

Consumers: Response Selector, follow-up gates, Entity honesty, analyze force paths, OS/SCG adapters, engines’ **inputs** only. Consumers **must** discard snapshot/projection use on generation mismatch (§10.5).

### 8.4 Transition decision (Classifier → Host)

Normative DTO (FINDING-012) — ellipsis **prohibited**. Aligned to TB-V2 detect inputs/outputs:

```text
EpisodeTransitionDecision = {
  outcome: KEEP_EPISODE | NEW_FIXTURE | NEW_EPISODE,

  reason: enum string ∈ {
    new_fixture,
    soft_followup_same_episode,
    low_entity_overlap,
    seed_subject,
    same_fixture_restated,
    overlap_ok_keep,
    explicit_new_episode
  },  # closed set for v1.1; any future TB-V2 token requires Appendix A row before use

  current_entities: {
    clubs: list[CanonicalClub],      # from SLL; canonicalized club ids/names
    fixture_label: FixtureLabel | null,
    compare_signal: bool
  },

  prior_subject: {
    source: STS_SNAPSHOT,            # normative prior source after cutover — not live CSL sticky
    episode_id: string | null,
    teams: list[CanonicalClub],
    fixture_label: FixtureLabel | null,
    subject_generation: int
  },

  entity_equality: {
    algorithm: CANONICAL_CLUB_SET_EQUALITY,  # order-insensitive set equality on canonical club ids
    overlap_score: float | null              # if Jaccard/overlap used by TB-V2 detect
  },

  fixture_label_canonicalization: {
    rules: NORMALIZE_WHITESPACE | CASEFOLD | STRIP_VS_SEPARATORS,  # normative family; exact token table in P1 fixtures
    canonical_label: FixtureLabel | null
  }
}
```

**P1 exit** requires this typed DTO consumable by classify (FINDING-012). Downstream must **consume** this decision; re-detecting in parallel (brain_authority / followup_guard / is_topic_switch) is a migration debt to retire (transition_arch_001).

**Routing:** pure total function `(outcome × reason) → apply node` — Appendix A (FINDING-013).

### 8.5 Projections (STS → legacy keys)

| Projection | Interface rule |
|------------|----------------|
| `last_home` / `last_away` / `last_match` / `last_fixture` | Write-through from STS commit only; carry `subject_generation` |
| CSL façade | Schema aligned with STS; `set_csl` private/adapter-only; carry generation |
| SRF | Refresh from STS; `set_*` only via `apply_bind` / `apply_analysis`; carry generation |
| short_mem / focus / continuity sport fields | Projection of followup_context / subject; carry generation |
| `entity_v2_last_bind` | Ephemeral bind cache via STS funnel; cleared on boundary |
| `conversation_state.active_fixture` | Deprecate → projection then eliminate (phase late) |

Readers **must** discard projection values when `projection.subject_generation != STS.subject_generation` (FINDING-021).

### 8.6 OS / SCG

| Call | Caller | Constraint |
|------|--------|------------|
| `release_owner_lock` | STS boundary commit **stage** | On NEW_FIXTURE / NEW_EPISODE; required completeness signal |
| `create` / `expire` / note sport anchor | STS funnel / boundary stage | Subject from STS; no invent; required completeness on boundary |
| claim/note ownership | Existing turn owners via public APIs | Lock ≠ subject SoT |

**Silent best-effort without visible incomplete state is removed** (FINDING-016). Incomplete required OS/SCG side-effects ⇒ production write **fail-closed** + **D2** consumer-blocking `stage5_os_scg_incomplete` (§10.3).

### 8.7 Shadow adapter

| API (conceptual) | Behavior |
|------------------|----------|
| `shadow_from_ctx` | Read-only OLD capture |
| isolated graph/orchestrator update | NEW with `force=True` semantics (POC) |
| `compare_shadow` | Diff + `contamination_locus` ∈ {`before_langgraph`, `inside_state_layer`, `after_state_commit`} |
| `maybe_shadow_compare` | Flag-gated; fail-open; no live mutation |
| `ingress_order_shadow_compare` | P2 experiment: compare post-SLL **pre-CSL** (FINDING-014); success criteria = **Appendix B** (separate from locus-1 legacy-lag monitoring) |

### 8.8 Flag relationships / illegal matrix / migration stage

| Flag | Default | Role |
|------|---------|------|
| `ENABLE_LANGGRAPH_STATE_SHADOW` | OFF | Log-only OLD vs NEW; no sole-writer |
| `ENABLE_LANGGRAPH_STATE` | OFF | Production host write path (P4) |
| `ENABLE_TOPIC_BOUNDARY_V2` | OFF | Legacy/TB-002 path; classify rules may be reused even when V2 apply path differs |
| Future STS funnel flags (centralization_001) | OFF | `ENABLE_STS_READ_ADAPTERS`, `ENABLE_STS_WRITE_FUNNEL_BOUNDARY`, `ENABLE_STS_WRITE_FUNNEL_ANALYZE`, `ENABLE_STS_PROJECTIONS_RO`, `ENABLE_STS_SOLE_WRITER` — conceptual gates aligned under Commit Host plan |

**Preferred consolidation (FINDING-009):** single `MIGRATION_STAGE` enum consolidating LangGraph/STS/V2 gates:

| Stage enum | Meaning |
|------------|---------|
| `S0_OFF` | All write/shadow production-affecting paths OFF |
| `S1_SHADOW` | Shadow only |
| `S2_FUNNEL` | P3 funnel via C17; LangGraph production write OFF |
| `S3_PROD_WRITE` | P4 production write ON + sole-writer guard ON |
| `S4_RETIRE` | P5 dead-code retirement |

**Illegal flag matrix (normative — fail-closed boot/assert via C12):**

| # | Illegal combination | Why |
|---|---------------------|-----|
| I1 | `ENABLE_LANGGRAPH_STATE=ON` ∧ `ENABLE_STS_SOLE_WRITER=OFF` (or sole-writer guard inactive) | Dual-SoT-by-schedule |
| I2 | `ENABLE_LANGGRAPH_STATE=ON` ∧ funnel incomplete (boundary/analyze funnel flags not proving single path) | P4 before P3 |
| I3 | `ENABLE_LANGGRAPH_STATE=ON` ∧ note_* subject writers unguarded | FINDING-026 residual |
| I4 | Production write ON ∧ `langgraph` missing ∧ no ADR-001 flip to contingency host | Order guarantees false (FINDING-025) |
| I5 | TB-V2 apply materializer ON ∧ graph/orchestrator apply ON (dual materializers) after cutover stage | Dual apply |
| I6 | `ENABLE_LANGGRAPH_STATE=ON` ∧ deploy tree missing STS/LangGraph modules | Deploy SoT violation (FINDING-024) |
| I7 | Shadow claimed as sole-writer / production write | Shadow ≠ activation |

**Precedence (normative; reinforced by matrix — not prose-only):**

1. If `ENABLE_LANGGRAPH_STATE=0`: production subject writes follow P3 Minimal Commit Orchestrator / funnel-migration path only; LangGraph must not write live subject.
2. Shadow may run independently of production write.
3. Production write **requires** sole-writer funnel readiness + runtime guard + note_* guard (P3 before P4; FINDING-015/026).
4. TB-V2 flag remains independently toggleable during early phases; after cutover, transition decision is centralized inside classify — dual materializers must be retired.
5. Any illegal combination ⇒ **fail-closed** process assert/boot (C12); T9 covers illegal combinations.

---

## 9. Fluxo Completo

### 9.1 Production path (target, flags ON after gates)

```text
1. Ingress: POST /aurora/copilot {session_id, message, …}
2. Map session_id → thread_id (§13.1); reject empty/anon per mapper rules
3. Acquire serial lease on thread_id (queue; bound 5000 ms → 429)
4. Load session envelope (conversation_manager) — Memory pillar; shared envelope SoT multi-node; not independent subject SoT
5. SLL normalize → clubs / compare signals
6. Commit Host invoke(thread_id):   # C17 in P3; C1 in P4
   6.1 init_load ← checkpoint (+ hydrate if cold); validate checksum/schema
   6.2 classify ← Custom Transition → EpisodeTransitionDecision
   6.3 route via Appendix A:
        (outcome × reason) → apply_boundary | keep_followup | apply_subject
   6.4 STS Commit Gate stages (§10.3):
        Stage 1 validate events
        Stage 2 mutate STS + bump subject_generation
        Stage 3 persist checkpoint (includes projection plan + generation + checksum)
        Stage 4 projection write-through (durability window — §10.1)
        Stage 5 OS/SCG required side-effects (boundary); completeness signals; D2 incomplete flag if needed
   6.5 Stage completeness → success or fail-closed
7. Downstream Understanding / Intent / planning consume STS snapshot
   — message/intent rewrite authority: STS snapshot or pós-SLL teams; never CSL sticky pré-STS (FINDING-002)
8. Engines (if analyze/live) — FROZEN; inputs from resolved subject
9. Response Selector reads STS / projections (epoch-checked); writes only candidate pool
10. Integrity / credibility / response emit
11. End-of-turn: no independent note_* subject authorship; adapters may call STS events only
    — note_* subject fields funnel+runtime-guarded before P4 exit (FINDING-026)
12. Release serial lease
```

### 9.2 Shadow path (current POC → hardened)

```text
Path A — legacy-position shadow (POC):
  SLL → (TB-V2/CSL/intent as today) → maybe_shadow_compare
    → OLD from ctx; NEW isolated; AUDIT log; locus
    → live path continues unchanged

Path B — P2 ingress-order experiment (FINDING-014 / CDR2-F2) — required; **falsifiable success criteria published (Appendix B)**:
  SLL → ingress_order_shadow_compare (post-SLL pre-CSL)
    → OLD vs NEW at ingress-order locus
    → live path continues unchanged; fail-open
```

**P2 exit:** locus `(2) inside_state_layer` rare **and** ingress-order experiment meets **Appendix B — P2 Ingress-Order Success Criteria** (pass/fail observables). “Locus-1 understood as legacy lag” is **monitoring only** — **not** a permanent P2 exit substitute and **not** part of Appendix B pass criteria (FINDING-014 / CDR2-F2).

### 9.3 Critical scenario (must succeed on production path)

**Flamengo×Palmeiras → Liverpool×Chelsea → “Quem está melhor?”**

| Turn | Required STS outcome |
|------|----------------------|
| T1 | Subject = Flamengo×Palmeiras; episode E1 |
| T2 | Boundary; subject = Liverpool×Chelsea; episode E2; orphans cleared; **no** Flamengo residual in projections; message rewrite/compare uses STS/Liverpool teams not CSL sticky Flamengo |
| T3 | Soft FU keep E2 + Liverpool×Chelsea |

Shadow evidence: NEW correct on T2 while OLD lagged (`before_langgraph`). Production path must make live state match NEW semantics. Golden §9.3 **cannot** claim success without message-authority rule (FINDING-002).

---

## 10. Contratos

### 10.1 Ingress contract

| Item | Spec |
|------|------|
| **Inputs** | `session_id`, `message`, SLL result, session envelope, flag snapshot |
| **Preconditions** | `session_id` maps successfully per §13.1 (empty/anon handled — not silent collide); Code SoT deploy path is `artifacts/aurora/`; serial lease acquired on production write path |
| **Outputs** | Updated session envelope with STS-authoritative subject (when write ON); response pipeline continues **or** 429 on lease timeout |
| **Postconditions** | If write ON and commit stages completed: STS advanced; checkpoint contains projection plan + `subject_generation`; projections either match generation **or** consumers refuse mismatch within the defined durability window. **No absolute claim** of STS+projection consistency without that window (FINDING-003). |

**Durability boundary (FINDING-003 — Matrix Option A):** Checkpoint **includes** projection plan + `subject_generation`/epoch. Consumers **must** refuse/discard generation mismatch. Crash between Stage 3 (checkpoint) and Stage 4 (projection refresh) ⇒ STS/checkpoint NEW + projections possibly OLD ⇒ readers use STS snapshot API or discard stale projections — **not** silent dual-SoT trust of OLD projections.

### 10.2 Transition contract

| Item | Spec |
|------|------|
| **Inputs** | message, SLL clubs, STS prior subject/fixture/episode |
| **Preconditions** | Classifier is Aurora custom; no Rasa/LangGraph domain substitute; prior from STS snapshot when authoritative |
| **Outputs** | Single typed `EpisodeTransitionDecision` per turn at classify |
| **Postconditions** | Apply node selected solely by Appendix A; no parallel detector may apply a conflicting materialization after cutover |

### 10.3 STS commit contract (stages — FINDING-004)

Word **“atomic”** appears only where a Unit of Work is defined below (order/fsync expectations included). Fake cross-store XA claims are **banned**.

| Stage | Name | Durability / crash semantics | Winner-on-divergence |
|------:|------|------------------------------|----------------------|
| 1 | Validate pending events | No durable mutation; crash = retry turn safe | N/A |
| 2 | Mutate STS in-memory + bump `subject_generation` | Not yet durable | N/A |
| 3 | Checkpoint persist (STS + projection plan + generation + checksum/schema) | **UoW boundary A:** process fsync/commit of checkpointer backend as configured; crash before ack = retry from prior checkpoint | **Checkpoint/STS generation wins** over projections |
| 4 | Projection write-through to session envelope keys | Crash ⇒ projections may lag; consumers discard mismatch | **STS/checkpoint wins**; projections stale until refresh |
| 5 | OS/SCG required side-effects (boundary path) | Incomplete ⇒ stage incomplete signal; production write **fail-closed** (FINDING-016); **Disposition D2 (CDR2-F3):** emit binding `stage5_os_scg_incomplete` flag; **no** production-visible soft-FU / analyze path may treat the session as coherent NEW subject while the flag is set; retry release/expire on subsequent turns until Stage 5 completes. **No** Stage-3 checkpoint undo / 2PC (Durability Option A preserved) | Subject/STS remains authority; OS/SCG incomplete must be **consumer-blocking** — no silent best-effort success; durable NEW + side-effect OLD without defined handling is **eliminated** |

| Item | Spec |
|------|------|
| **Inputs** | Pending events from apply_* nodes |
| **Preconditions** | Exactly one commit path on legal Commit Host; events validated (e.g. boundary requires clear+replace); lease held |
| **Outputs** | New STS snapshot; projection plan; stage identity; completeness signals; observability stamps; on Stage-5 incomplete: `stage5_os_scg_incomplete` flag |
| **Postconditions** | On NEW_FIXTURE/NEW_EPISODE: episode changed; teams/fixture replaced; orphans cleared; OS release + SCG expire **completed** **or** fail-closed **with D2 consumer block** (not invisible best-effort; not coherent-NEW soft-FU/analyze while incomplete) |

#### Stage-5 durable-coherence disposition (FINDING-016 / CDR2-F3) — exactly one: **D2**

Plan 010 authorized dispositions: D1 (durable repair/undo) **or** D2 (consumer-blocking incomplete-flag). This Spec selects **D2** only:

| Rule | Statement |
|------|-----------|
| D2-1 | After durable Stage 3, Stage 5 incompleteness does **not** undo the checkpoint (FINDING-003 Option A / no 2PC invented). |
| D2-2 | Production path **must** set `stage5_os_scg_incomplete` (visible + AUDIT) when required OS/SCG side-effects fail or are incomplete. |
| D2-3 | While `stage5_os_scg_incomplete` is set: soft-FU keep paths and subject-dependent analyze that would treat the session as **coherent NEW subject** are **blocked** (fail-closed / clarify) — consumers must not amplify OLD OS/SCG anchors against NEW STS as if coherent. |
| D2-4 | Subsequent turns **must** retry required release/expire until Stage 5 completes; on success clear the flag and AUDIT recovery. |
| D2-5 | D1 (checkpoint undo / compensation transaction reversing Stage 3) is **not** selected. |

### 10.4 Shadow contract

| Item | Spec |
|------|------|
| **Inputs** | message, ctx (read-only) |
| **Preconditions** | `ENABLE_LANGGRAPH_STATE_SHADOW=1` |
| **Outputs** | Log/metrics dict; contamination locus; optional ingress-order metrics |
| **Postconditions** | Live subject stores unchanged |

### 10.5 Read consumer contract

| Item | Spec |
|------|------|
| **Inputs** | `SportTopicState.snapshot` and/or projections |
| **Preconditions** | Consumer is allow-listed (RS, gates, honesty, adapters) |
| **Outputs** | Derived UX / routing decisions |
| **Postconditions** | No subject key mutation; **must discard** on `subject_generation` mismatch (FINDING-021) |
| **Multi-node** | Must not treat local-only envelope as subject authority cross-node; shared envelope SoT **or** read STS/checkpoint only (this Spec selects **shared envelope SoT** — FINDING-008) |

### 10.6 Illegal write contract (runtime — FINDING-015 / CDR2-F6)

Any write to subject keys outside STS commit is **contract violation**.

**Production mechanism class (normative — named, enforceable, fail-closed — not test-only theater):** When sole-writer / production write stage is ON, the runtime sole-writer guard **must** be implemented as a **ctx proxy** (enforceable surface class selected from CDR2-F6 known set: ctx proxy / write interceptor / frozen setters / import-time wrap — **this Spec selects `ctx proxy`**). The proxy **intercepts** subject-key mutations on the session envelope / ctx and **blocks** illegal writes (no-op of the mutating call + AUDIT + fail-closed for the mutating call). Dual-SoT-by-schedule is banned.

**Non-compliance:** A logging-only stub, metrics-only observer, or test-only monkeypatch **cannot** satisfy §10.6 / T1. Enforcement **must** be on the production write path.

**Schedule:** Runtime sole-writer guard = **hard P4 precondition**. P5 = retire dead code **after** guard proves zero hits — not the first time enforcement appears.

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
| `subject_generation` | **Mandatory epoch** (monotonic per successful Stage 2); carried on STS and all subject projections |
| `subject` / meta | POC-aligned subject markers as needed for host |

### 11.2 Host routing state (ephemeral per turn)

| State | Meaning |
|-------|---------|
| Loaded STS baseline | From checkpoint |
| Transition decision | From classify (`EpisodeTransitionDecision`) |
| Pending events | Pre-commit |
| Stage cursor / completeness | Commit Gate stages 1–5 |
| Contamination locus (shadow only) | Diagnostic |
| Lease held | Serial execution token for `thread_id` |

### 11.3 Projection states (non-authoritative after cutover)

Legacy triad clusters (centralization_001 §4) become **derived** and epoch-tagged:

1. Canonical fixture triad: `last_*` ↔ CSL ↔ SRF  
2. Soft-FU referent triad: short_mem ↔ continuity ↔ focus  
3. “What game” triad: SCG anchor ↔ `active_fixture` ↔ `entity_v2_last_bind`

Mismatch with STS `subject_generation` ⇒ discard (fail criteria in §18).

### 11.4 KEEP external states (not STS-owned)

| State | Owner |
|-------|-------|
| `ownership_stability` lock blob | OS module |
| SCG TTL/anchor mechanics | SCG module (fields sourced from STS) |
| Response selector candidate pool | Response Selector |
| Engine analysis payloads | Engines / analyze path |
| Long-term Memory DB collections | Memory pillar |
| Shared session envelope (multi-node) | Memory / conversation_manager — projection carrier SoT (FINDING-008) |

### 11.5 Race matrix (normative — FINDING-007)

| Race | Hazard | Normative control |
|------|--------|-------------------|
| Concurrent turns same `thread_id` | Interleaved init_load→commit→checkpoint→projection | Serial lease; queue; **bound 5000 ms** → 429; refuse merge |
| Double-submit / client retry | Double boundary / wrong soft-FU prior | Same lease serializes; duplicate turn not merged |
| Multi-node without shared envelope | Stale local projections | Shared envelope SoT + §12 interface; sticky sessions complement only |
| Multi-node without shared lease | Split lease / double-submit across instances | Shared lease store required when multi-instance write claimed (CDR2-F5); else P4 NO-GO |
| Write ON without sole-writer guard | Dual-SoT | Illegal flag I1; P4 precondition; **ctx proxy** mechanism (CDR2-F6) |

---

## 12. Persistência

| Store | What persists | Authority |
|-------|---------------|-----------|
| Checkpoint store (per `thread_id`) | STS host state snapshots + projection plan + generation + checksum/schema | Context Manager durability for sport subject host state |
| `conversation_manager` session envelope (**shared** when multi-instance — interface below) | Session envelope + projection keys | Memory/session; **shared envelope SoT** for multi-node projection-bearing reads (FINDING-008 / CDR2-F4); must not become competing subject SoT independent of STS |
| Projection keys inside session ctx | Compatibility mirrors + `subject_generation` | Derived from STS when write path ON; non-authoritative if generation mismatches |
| Engine / knowledge / learning DBs | Sports domain | Frozen / other pillars — out of STS |
| OS / SCG stores | Lock / anchor mechanics | KEEP modules; completeness visible via commit stage signals + D2 flag |
| Shared lease store (multi-instance write) | Serial lease tokens per `thread_id` | Required when multi-instance production write claimed (CDR2-F5); process-local mutex insufficient under horizontal scale |

**Rules:**

- Checkpoint must remain **lean** (research_003 R6): subject + episode + followup summary + boundary stamp + generation + projection plan + checksum — not full analyze blobs.
- Cache is **never** SoT (Audit authority order).
- Cross-node Autoscale: checkpointer backend for multi-process must be shared (SQLite file locality insufficient → Postgres when horizontally scaled). **Additionally:** session envelope must be shared SoT for projection readers **or** consumers must read STS/checkpoint only — this Spec selects **shared envelope** (FINDING-008). Sticky sessions are **complement, never substitute**.
- Commit across checkpointer, envelope, OS, SCG uses **numbered stages** (§10.3) — not pretended XA.
- Long-term facts belong in Memory/Knowledge stores, not inflated checkpoints.
- P4 multi-instance gate: horizontal scale claims require shared checkpointer **and** shared envelope interface below **and** shared lease store (FINDING-008 / CDR2-F4 / CDR2-F5).

### 12.1 Shared-envelope durability interface contract (CDR2-F4)

Normative selection remains **shared envelope SoT** (FINDING-008). The following interface makes the claim **falsifiable** (no vendor product invented; storage class already implied by Spec Postgres-when-horizontally-scaled language):

| Element | Binding requirement |
|---------|---------------------|
| **SoT location class** | Shared durable session-envelope store reachable by **all** instances that serve the same sessions (e.g. shared Postgres / equivalent shared DB class when horizontally scaled). Instance-local RAM+SQLite alone is **not** the multi-instance SoT. |
| **Read authority** | Projection-bearing subject reads under multi-instance **must** load from the shared envelope SoT (or STS/checkpoint only). Treating a peer’s local-only envelope as cross-node authority is **forbidden**. |
| **Write authority** | Projection write-through (Stage 4) under multi-instance **must** persist to the shared envelope SoT. Local-only write that other instances cannot read is **contract violation**. |
| **Failure mode if local-only** | Split-brain / stale projections across instances (Audit Memory Autoscale miss class). Detectable as: instance A writes projection generation G; instance B serves same `session_id` from local envelope lacking G. |
| **P4 NO-GO** | Any multi-instance production-write claim **without** this interface met = **explicit P4 NO-GO**. Single-node may use local envelope **only** while multi-instance write remains unclaimed. |

---

## 13. Checkpoints

### 13.1 Keys / `thread_id` mapping (FINDING-022)

| Key | Definition |
|-----|------------|
| `thread_id` | Deterministic function of Aurora `session_id` (stable, unique per session) — **algorithm below** |
| `checkpoint_ns` | Fixed namespace `aurora.context_manager.sts` — must not collide with future unrelated graphs |
| `checkpoint_id` | Framework/host-assigned per super-step; used for resume/time-travel diagnostics |

**Mapping algorithm (normative):**

| Rule | Specification |
|------|----------------|
| Algorithm | `thread_id = "sts:" || hex(SHA-256(UTF-8(session_id)))[0:32]` |
| Length | Prefix `sts:` (4) + 32 lowercase hex chars = **36** chars total |
| Namespace | Prefix `sts:` + `checkpoint_ns = aurora.context_manager.sts` |
| Collision domain | SHA-256 truncated hex; practical uniqueness for Aurora session ids; isolation tested via T15 |
| Empty `session_id` | **Reject** ingress — HTTP 400 / fail-closed; do not map |
| Anonymous / whitespace-only | Treat as empty → reject; do not coalesce anon sessions into a shared thread |
| Stability | Same `session_id` ⇒ same `thread_id` across process restart |

### 13.2 When to checkpoint

- After Commit Gate **Stage 3** succeeds for the turn (minimum durable boundary).
- Must not checkpoint partial classify without commit when production write ON (avoid half-applied subject).
- Checkpoint payload **must include** projection plan + `subject_generation` (FINDING-003 Option A).

### 13.3 What is in a checkpoint

- STS authoritative fields (§11.1), including `subject_generation`.
- Projection plan for Stage 4.
- **Checksum** + **schema version** (FINDING-023) — required for corruption vs unexpected-shape detection.
- Minimal host channels required to resume.
- **Exclude:** frozen engine internals, raw provider payloads, Response Selector pools, secrets.

### 13.4 Backend progression (conceptual)

| Stage | Backend | Gate |
|-------|---------|------|
| Dev/POC | InMemory or local SQLite | Shadow / single node |
| Staging | SQLite durable file | Restart recovery tests pass |
| Multi-instance prod | Postgres (or equivalent shared checkpointer) **+ shared session envelope** | Horizontal scale + FINDING-008 rule |

---

## 14. Recuperação

| Scenario | Behavior |
|----------|----------|
| Process restart, same `session_id` | Mapper resolves `thread_id`; load latest checkpoint; hydrate STS; projections refresh from STS under generation rules |
| Missing checkpoint (cold session) | `init_load` empty/default STS; first subject seed via `apply_subject` / analysis events |
| Corrupt checkpoint | **Single normative branch (FINDING-023):** Detector distinguishes **corruption** (checksum fail) vs **unexpected shape** (schema version mismatch / unknown fields). On either: **refuse contaminated hydrate** → emit AUDIT → initialize **cold empty STS** (no peer-cache sticky invent) → response class **UX clarify** (`SUBJECT_RECOVERY_CLARIFY`). Dual “open new episode **or** refuse” without procedure is **removed**. |
| Shadow path failure | Fail-open; live path continues (POC) |
| Commit Host unavailable (`langgraph` missing on P4, or orchestrator fault) with write ON | **Process-global degrade (FINDING-025):** refuse subject mutation **and** block legacy subject writers in-process; HTTP **503**; session subject mutate denied; UX class `SUBJECT_HOST_UNAVAILABLE`; sequential fallback remains **shadow-only** |
| Partial migration (funnel incomplete) | Production write flag must remain OFF |
| Crash between Stage 3 and Stage 4 | Consumers refuse generation mismatch / read STS snapshot; projections refreshed on next successful Stage 4 |

**Recovery invariant:** After restart, soft FU must not resurrect a fixture that was cleared by a committed boundary in a prior checkpointed turn.

---

## 15. Tratamento de Erros

### 15.1 Credibility policy (betting-critical subject)

| Path | Mode | Rationale |
|------|------|-----------|
| Shadow compare | **Fail-open** | Observability must not break turns (POC + Audit) |
| Production STS write / commit | **Fail-closed** on subject mutation errors | Wrong sticky fixture destroys betting credibility more than a controlled degrade |
| Transition classify exception | **Single degrade state machine** below (FINDING-010) | Ambiguity #3 closed as **control-flow**, not UX copy |
| Projection refresh failure after Stage 3 | Retry Stage 4; if still failing, mark projections stale + AUDIT; STS snapshot remains authoritative; consumers discard mismatch | Durability Option A |
| Illegal legacy write attempt after cutover / with guard ON | Block / no-op + AUDIT (+ test fail) | Sole-writer integrity; production fail-closed |
| OS/SCG required side-effect incomplete | Stage 5 incomplete → production write **fail-closed**; **D2** `stage5_os_scg_incomplete` consumer-blocking (no coherent-NEW soft-FU/analyze) | FINDING-016 / CDR2-F3 — best-effort silent success removed |
| Host unavailable + write ON | Process-global degrade §14 | FINDING-025 |

#### Classify degrade state machine (exactly one — FINDING-010)

**Name:** `safe_boundary_clear`

| Input condition | STS mutation | Response class | Analyze |
|-----------------|--------------|----------------|---------|
| Production write ON ∧ classify throws / undecidable ∧ contested prior (message names fixture/teams distinct from prior **or** classifier aborts mid-decision) | Forced **clear-to-empty-seed**: bump episode, clear teams/fixture/orphans via boundary clear events through Commit Gate stages; **do not** invent a new fixture from partial parse; bump `subject_generation` | `SUBJECT_DEGRADE_CLARIFY` | **Blocked** until re-seed |
| Production write ON ∧ classify throws ∧ prior uncontested (no new named fixture signal) | **No subject invent**; no keep of analyze-against-wrong-fixture path — refuse subject-dependent analyze; STS unchanged | `SUBJECT_DEGRADE_CLARIFY` | **Blocked** |
| Shadow path | No live STS mutation | N/A (fail-open) | Live path unchanged |

Product i18n copy for `SUBJECT_DEGRADE_CLARIFY` is **deferred** and must not introduce a second control-flow machine (Validation Contract ambiguity #3 closed as control-flow).

### 15.2 Explicit anti-patterns

- Fail-open production write that leaves multi-writer cascade authoritative.
- Healing soft FU on contaminated OLD (CONTAMINATION_NOTES).
- Claiming TB-002/STS “fixed in production” while flags default OFF.
- Silent best-effort OS/SCG success with incomplete side-effects.
- Last-writer-wins concurrent turns on same `thread_id`.
- Treating POC shadow as production sole-writer / multi-node / projection-atomicity proof.

---

## 16. Compatibilidade

### 16.1 With current Aurora (as-is)

| Surface | Compatibility approach |
|---------|------------------------|
| `POST /aurora/copilot` | Unchanged external API (plus 429 lease / 503 host-unavailable classes) |
| SLL | KEEP; input to classify |
| TB-V2 | Rules reused; apply path migrates into STS funnel / Commit Host |
| CSL / SRF / short_mem / continuity / focus | Temporary writers → projections + epoch |
| Response Selector | KEEP; read STS (epoch-checked) |
| OS / SCG | KEEP modules; adapter call sites; stage completeness |
| Frozen engines | Untouched |
| Feature flags | Additive; defaults remain OFF until gates; illegal matrix fail-closed |
| `artifacts/aurora/` vs `aurora/` | Deploy SoT = artifacts; **hard release assert** fail-closed if required LangGraph/STS modules absent; **open mirror drift = explicit P4 NO-GO** (FINDING-024) — not soft timeline |

### 16.2 POC → contract evolution (no code in this mission)

| POC asset | Evolves into |
|-----------|--------------|
| `sport_topic_state.py` | Normative STS schema + commit API + `subject_generation` |
| `langgraph_state_graph.py` | **P4** host graph with same topology family: `init_load → classify → {apply_boundary\|keep_followup\|apply_subject}` |
| Minimal Commit Orchestrator | **P3** host with identical semantics (C17) |
| `langgraph_state_adapter.py` | Shadow + ingress-order experiment + hydrate/compare metrics harness |
| Flags `ENABLE_LANGGRAPH_STATE(_SHADOW)` | Remain; production write gated by sole-writer readiness + guard + note_* |
| Shadow harness / CONTAMINATION_NOTES | Golden scenario suite for validation |
| Sequential fallback | Shadow-only after cutover policy |

### 16.3 Audit pillars / Frozen / specializations

- Context Manager pillar: **Substituir** via this architecture (Audit §3.2) — **technical design only**; Substitution Phase authorization separate (§16.4 / §17 P0).
- Frozen candidates (engines, OS, SCG, SLL KEEP, Response Selector, …): **must not** be redesigned here.
- Specializations (e.g. Conversation Personalization): **never modify Core** STS internals; consume public snapshot API only.

### 16.4 Documento Mestre / Architecture SSOT (FINDING-006 / CDR2-F1)

**Evidence path (Path A — preferred):** Official Documento Mestre / Master Architecture is **in-repo** and Git-versioned:

| Artifact | Path | Role |
|----------|------|------|
| Master Architecture (Documento Mestre) | `docs/architecture/master-architecture.md` (VERSION **2026.08.06**) | Core pillars + Substitution-facing Core policy |
| SSOT navigation | `docs/architecture/README.md` | Declares SSOT root = `docs/architecture/` |
| SSOT Policy | `docs/architecture/governance/SSOT_POLICY.md` | Versioning, approval, freeze, F1 closure criteria |
| Git evidence | commit `9f53678` (`docs(architecture): establish Aurora Core SSOT`) | Board-resolvable version control evidence |

Prior Audit 001 **INSUFFICIENT EVIDENCE** *for master-document absence* is **superseded** for pillars/policies recorded in the Master (Master §0; SSOT_POLICY §7–§8). Spec/CDR/AAR prose is **not** a Substitution waiver. Path B waiver template exists but is **not activated** — prefer Master coverage (SSOT_POLICY §9).

| Gate | Meaning |
|------|---------|
| Technical acceptance (CDR/AAR) | May accept Spec text quality / implementability judgment |
| Substitution Phase authorization | **≠** technical acceptance. Requires Master (this Path A evidence) **plus** residual disposition **plus** APPROVED AAR (AAR-001/002 liberação chain) |
| Spec role | Context Manager **specialization** under Core Master §5 — not Master substitute |

Formal Substitution sign-off remains **blocked** until APPROVED AAR after residual closure (research_003 R2 / Audit R2 / ADR-012 / AAR-002). Closing CDR2-F1 **does not** authorize implementation (SSOT_POLICY §8).

---

## 17. Plano de Migração

Conceptual **6 phases**, aligning research_003 §8 with centralization_001 §8 (merged, no code), revised per ACCEPT schedule.

| Phase | Name | Intent | Gate to exit |
|-------|------|--------|--------------|
| **P0** | Governance split | Ratify Audit 001 + research_003 + this SPEC as **technical** interim contract under official Architecture SSOT | **Technical** CDR/AAR may accept Spec **≠** Substitution authorization. **CDR2-F1 Path A satisfied** by citing `docs/architecture/` (Master + README + SSOT_POLICY; commit `9f53678`). Exit to Substitution still requires residual disposition + APPROVED AAR. **Not** “Missão accepts SPEC” alone (FINDING-006). |
| **P1** | Transition hygiene | Centralize `EpisodeTransition.decide` (KEEP CUSTOM); typed `EpisodeTransitionDecision`; Appendix A route table; detector ownership map closed; classify consumes single decision | No conflicting materializers on staging with flags under test; typed DTO consumable by classify |
| **P2** | Shadow hardening | Expand LangGraph STS shadow vs OLD; track loci; **plus** ingress-order experiment (post-SLL pre-CSL) meeting **Appendix B** falsifiable criteria | Locus `(2)` rare; harness green; **Appendix B** ingress-order criteria met (T21). Locus-1 legacy-lag monitoring **≠** permanent exit substitute (FINDING-014 / CDR2-F2). ADR-001 flip triggers evaluated against P2/P3 kill criteria. |
| **P3** | Sole-writer funnel (gated) | All subject writes call STS.commit via **C17 Minimal Commit Orchestrator** (Option A); projections write-through with epoch; OS/SCG via public APIs in commit stages (**D2** incomplete semantics); **dual-write forbidden**; `ENABLE_LANGGRAPH_STATE` still OFF | Funnel flags prove single path on C17; commit stages + durability boundary falsifiable; no invent-second-orchestrator |
| **P4** | Production host write | Enable `ENABLE_LANGGRAPH_STATE` behind flag **only if** hard preconditions met; choose checkpointer backend; multi-instance rule; rollback drill proven | **Hard preconditions before exit:** (1) runtime sole-writer guard ON as **ctx proxy** proving blocks (FINDING-015 / CDR2-F6); (2) note_* subject fields funnel+guarded (FINDING-026); (3) illegal flag matrix green; (4) serial lease concurrency tests green (**5000 ms** bound; shared lease if multi-instance — CDR2-F5); (5) deploy path assert + **no open mirror drift** (FINDING-024); (6) shared envelope **interface** / multi-instance gate if horizontal scale claimed (FINDING-008 / CDR2-F4); (7) rollback drill + checklist (§17.2) observable; (8) T10 Frozen call-site goldens; (9) shadow + restart + bleed + message-authority scenarios pass with write ON |
| **P5** | Writer retirement | Delete/retire dead legacy subject writers after guard proves **zero hits**; demote physical keys to read projections | Forbidden writers list enforced; **P5 does not introduce enforcement** — only dead-code retirement (FINDING-015/026) |

**Principles:** incremental; perception validated before elegance; frozen engines never in diff; specializations consume Core STS API only; never enable P4 before P3; never enable P4 before runtime guard + note_* guard.

### 17.1 Exact forbidden writers after cutover (P5 retirement list; guarded from P4)

The following **must not** independently mutate sport subject fields (`episode_id`, teams, fixture/subject triad, SRF subject, sport sticky `last_*`, short_mem sport subject, continuity/focus sport subject, `active_fixture` subject, bind subject) except via STS funnel. **Runtime guard + note_* funnel required before P4 exit**; P5 deletes dead code only:

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

### 17.2 Rollback matrix (FINDING-005) — normative for P1–P5

“**Rollback proven**” (P4 exit) = **drill executed** + **checklist observables** below — not a slogan.

| Phase | Trigger | Steps | Accepted data loss | Verification | In-flight turn policy |
|-------|---------|-------|--------------------|--------------|------------------------|
| P1 | Conflicting materializers / decide fork | Disable new decide flag; revert to last known single-detector staging config; keep TB-V2 detect read-only if needed | Staging-only decision logs | Detector ownership map re-closed; no dual apply in staging | Finish in-flight staging turns fail-open to legacy detect |
| P2 | Shadow/ingress-order harness red or ADR-001 flip trigger hit | Disable shadow flags; keep production write OFF; file flip evaluation if kill criteria met | Shadow metrics only | Flags OFF; no live subject mutation from shadow | In-flight shadow tasks abort fail-open |
| P3 | Funnel divergence / stage incompleteness / dual path detected | Disable funnel write-through flags; return subject writes to pre-funnel staging posture; keep `ENABLE_LANGGRAPH_STATE=0` | Projection mirrors may lag; STS staging data may reset per checkpoint | Single-path tests fail closed; generation mismatch consumers refuse | Reject new funnel turns (429/503); no production write enable |
| P4 | Bleed / dual-SoT / guard hits / deploy assert fail / rollback drill fail | Set `ENABLE_LANGGRAPH_STATE=0` (and stage enum ≤ S2); keep sole-writer guard ON during drain; do **not** re-enable unguarded legacy writers | In-flight production turns may fail-closed clarify; last durable checkpoint retained | Guard hit counter; T1/T11/T4/T13 green on rollback posture; mirror drift check; checklist signed | In-flight: fail-closed subject mutate; queue drain; no merge |
| P5 | Residual writer resurrect / guard non-zero | Stop deletions; restore previous artifact revision; re-enter P4 guard monitoring | None beyond rejecting resurrected writer path | Guard zero-hit window reinstated before further retirement | Block retirement deploys |

**P4 rollback drill checklist (observable):** flag OFF path exercised; guard remains blocking; checkpoint resume verified; projection generation refuse verified; OS/SCG incomplete path visible; lease 429 path exercised; AUDIT lines present for drill.

---

## 18. Critérios de Teste

| ID | Criterion |
|----|-----------|
| T1 | Unit: STS commit is only mutator under sole-writer flag; runtime guard is **ctx proxy** on production path blocking illegal writers (not test-only / not logging stub) (CDR2-F6). |
| T2 | Unit: classify outcomes cover NEW_FIXTURE, NEW_EPISODE, KEEP/soft FU, same-fixture restate; typed DTO fields present. |
| T3 | Host order: classify precedes subject commit (no CSL/intent rewrite before boundary on production path). |
| T4 | Golden sticky scenario Flamengo→Liverpool→soft FU (production write ON): T2 subject Liverpool; T3 keep Liverpool; no “Mantendo foco Flamengo”. |
| T5 | Orphan clear: SRF, `entity_v2_last_bind`, short sport mem cleared on boundary commit. |
| T6 | `note_csl` disjoint payload blocked / cannot overwrite new subject (TB-002 semantics preserved); note_* guard before P4. |
| T7 | Shadow: live ctx unchanged; locus codes stable; fail-open on adapter errors. |
| T8 | Restart recovery: checkpoint restore yields same episode/subject before soft FU; crash-between-stage (3→4) consumers refuse mismatch. |
| T9 | Flag matrix: defaults OFF; shadow≠write; write OFF ⇒ no live STS mutation; **illegal combinations fail-closed** (I1–I7). |
| T10 | Frozen OS/SCG/RS: **golden perception suites** binding observáveis under boundary/soft-FU/analyze as **P4 gates** (FINDING-019). Untouched internals alone insufficient. |
| T11 | Dual-SoT detection tests: if write ON and a legacy writer mutates subject, test fails; runtime guard teeth. |
| T12 | Missing langgraph / host unavailable: shadow fallback OK; production write path **process-global** refuse subject mutation **and** block legacy subject writers; HTTP/status/UX class asserted (FINDING-025). |
| T13 | Message authority: `message-derived teams ≠ STS.teams` after cutover ⇒ fail (FINDING-002). |
| T14 | Concurrency: same-`thread_id` parallel turns serialize; wait **> 5000 ms** → 429; no last-writer-wins; multi-instance write claim requires shared lease store (FINDING-007 / CDR2-F5). |
| T15 | Identity: empty/anon `session_id` rejected; distinct sessions ⇒ distinct `thread_id`; collision/isolation negative case (FINDING-022). |
| T16 | Appendix A route table coverage for seed / same-fixture / soft_FU / new_* (FINDING-013). |
| T17 | Epoch: readers discard projection/STS generation mismatch (FINDING-021). |
| T18 | Corrupt checkpoint: single recovery branch + AUDIT + UX clarify; checksum/schema detector (FINDING-023). |
| T19 | OS/SCG incomplete side-effects ⇒ production write fail-closed + **D2** `stage5_os_scg_incomplete` blocks coherent-NEW soft-FU/analyze (FINDING-016 / CDR2-F3). |
| T20 | Deploy path assert fail-closed when STS/LangGraph modules absent; mirror drift ⇒ P4 NO-GO (FINDING-024). |
| T21 | P2 ingress-order: Appendix B pass/fail set for `ingress_order_shadow_compare` graded without inventing thresholds (FINDING-014 / CDR2-F2). |
| T22 | Shared-envelope interface: multi-instance production-write claim without §12.1 interface ⇒ P4 NO-GO (CDR2-F4). |

---

## 19. Critérios de Validação

| ID | Validation |
|----|------------|
| V1 | Architecture matches research_003 primary decision direction (STS sole writer + KEEP CUSTOM + Commit Host) with ADR-001 provisional honesty. |
| V2 | Audit 001 Context Manager Substituir addressed without violating Frozen list. |
| V3 | Documento Mestre / Architecture SSOT cited at `docs/architecture/`; technical acceptance ≠ Substitution authorization (FINDING-006 / CDR2-F1 Path A). |
| V4 | Shadow metrics: divergence explained; locus (2) not dominant on golden suite; **ingress-order experiment** graded against **Appendix B** criteria separately (FINDING-014 / CDR2-F2). |
| V5 | Production write enabled only after P3 funnel evidence + runtime guard + note_* guard. |
| V6 | Perception parity: soft FU, analyze honesty, boundary, message-authority scenarios pass with flags under test. |
| V7 | Specializations do not patch Core STS modules. |
| V8 | Deploy path single SoT (`artifacts/aurora/`) with hard assert; open mirror drift = P4 NO-GO (FINDING-024). |
| V9 | External CDR/AAR checklist authority; Spec self-grade is not an implementation gate (FINDING-027). |

---

## 20. Critérios para Frozen

A module/asset may be treated as **Frozen relative to Context Manager work** when:

| ID | Criterion |
|----|-----------|
| F1 | Listed in Audit 001 Frozen Candidates / `docs/FROZEN_MODULES.md` / code FROZEN headers (engines, OS, SCG, guards, Decision Center, Knowledge, follow_up_engine formulas, analyze integrity contracts, etc.). |
| F2 | Context Manager substitution **does not** require editing their internal algorithms — only public API call-site ordering/arguments. **Call-site ordering/arguments are a behavioral collaboration surface** and must be covered by T10 golden perception suites (FINDING-019). |
| F3 | Response Selector remains read-only w.r.t. fixture SoT (pool writes only). |
| F4 | SLL remains perception KEEP; not replaced by host. |
| F5 | STS/Commit Host reaches sole-writer + recovery + golden bleed suite green under production flag — then Context Manager itself may be proposed for **Congelar** in a later audit (not automatic in Missão 004/008). |
| F6 | Until F5, Context Manager remains Replacement Candidate; flags default OFF. |

**Explicitly not Frozen as subject SSOT:** CSL, SRF, short_mem, conversation_state, multi-writer cascade (Audit §4).

---

## 21. Riscos

| ID | Risk | Sev | Mitigation |
|----|------|-----|------------|
| R1 | Dual-SoT if production write ON while 14 writers remain | 🔴 | P3 before P4; runtime guard before P4; note_* before P4; T11 |
| R2 | Documento Mestre / Substitution governance gap | 🔴 | Path A SSOT at `docs/architecture/`; P0 cite Master; block Substitution until APPROVED AAR |
| R3 | Sticky bleed returns (flags OFF / fail-open prod / message path) | 🔴 | Sole-writer + order edges + message authority; fail-closed prod write |
| R4 | LangGraph becomes sport-logic SoT (scope creep) | 🟠 | KEEP CUSTOM in contract; nodes only call Aurora detect |
| R5 | `aurora/` vs `artifacts/aurora/` drift | 🟠 | Hard deploy assert; P4 NO-GO on open drift |
| R6 | Checkpoint bloat / latency | 🟡 | Lean STS snapshots |
| R7 | LangGraph dependency/ops burden | 🟡 | ADR-001 provisional; pin versions; explicit flip triggers to custom STS-without-LangGraph contingency (FINDING-020) |
| R8 | Split transition detectors persist | 🟠 | P1 centralize decide; Appendix A; retire parallel apply |
| R9 | Soft FU on contaminated prior | 🔴 | Ensure switch turn commits NEW; P2 ingress-order + Appendix B |
| R10 | OS/SCG internal redesign temptation | 🟠 | Adapters + public APIs only; Stage-5 D2 completeness |
| R11 | Concurrent same-session corruption | 🔴 | Serial lease (5000 ms) + shared lease multi-node + T14 |
| R12 | Multi-node stale envelope | 🟠 | Shared envelope interface §12.1 + epoch refuse |

---

## 22. Decisões Arquiteturais (ADR)

**ADR count: 12** (v1.2 revises ADR-012 and residual cross-links; **no new ADR ids** invented)

### ADR-001 — LangGraph as state host (**PROVISIONAL** — FINDING-020)
**Decision (provisional):** Use LangGraph as **P4** host for typed state, ordered edges, and checkpointers, **pending** P2/P3 kill criteria.  
**Why:** Audit public solution; existing POC shadow proves NEW_STATE correct under lag **in isolation** — **not** production sole-writer / multi-node / projection-atomicity / message-path proof.  
**P3:** Legal Commit Host is **C17 Minimal Commit Orchestrator** (FINDING-001 Option A) with same semantics.  
**Rejected as primary without kill criteria:** Treating POC shadow as production proof.  
**Contingency (first-class flip target):** Custom STS Commit Host **without** LangGraph (research_003 shortlist #2), preserving checkpoint/`thread_id` identity claims.  
**Flip triggers (normative):** (1) P2 ingress-order or shadow harness cannot go green under LangGraph host constraints; (2) P3 kill — C17 semantics cannot be faithfully reproduced by LangGraph path without dual orchestration; (3) ops/dependency burden exceeds pin+contingency budget (R7); (4) Board records flip in subsequent AAR.  
**On flip:** Preserve STS sole-writer, commit stages, durability boundary, `thread_id` mapping, projection epoch — only host implementation swaps.

### ADR-002 — STS as sole writer
**Decision:** Aurora Sport Topic State is the only writer of sport conversational subject.  
**Why:** ≥14 writers cause sticky bleed class; TB-002 insufficient as end-state architecture (centralization_001).  
**Implication:** Runtime guard (**ctx proxy**, CDR2-F6) before P4; note_* funnel before P4; Commit Gate stages; message-authority channel included.  
**Rejected:** Continued multi-writer patches; dual-SoT-by-schedule; logging-only guard stub.

### ADR-003 — KEEP CUSTOM TRANSITION inside Commit Host
**Decision:** Transition classification remains Aurora custom (TB-V2 / EpisodeTransition), hosted in classify step; typed DTO + Appendix A route table.  
**Why:** Binding `topic_transition_arch_001`; frameworks lack PT football fixture/soft-FU policy.  
**Rejected:** Framework-provided dialogue policies as classifier; ellipsis DTO.

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
**Rule:** Shadow ≠ activation. P2 includes ingress-order experiment with **Appendix B** falsifiable criteria. Illegal flag matrix fail-closed (with ADR-007).

### ADR-007 — Dual-SoT prohibition (+ epoch freshness)
**Decision:** No parallel authoritative subject authors once production write enabled; write-through projections allowed only with mandatory `subject_generation` freshness; consumers discard mismatch.  
**Why:** Research_003 R1; contamination locus; FINDING-021.  
**Implication:** P3 funnel mandatory before P4; runtime guard + note_* before P4; no “sole-SoT” claim without epoch bits.

### ADR-008 — Fail-open shadow / fail-closed production subject writes
**Decision:** Shadow errors must not break turns; production subject commit errors must not silently fall back to multi-writer sticky; classify uses single `safe_boundary_clear` machine; host-unavailable is process-global degrade.  
**Why:** Betting credibility > availability of wrong fixture context.

### ADR-009 — Preserve SLL, Response Selector, OS/SCG public APIs, frozen engines
**Decision:** Non-negotiable KEEP set for this substitution.  
**Why:** Audit Frozen Candidates; centralization_001 KEEP table; never regress AEP guards/engines.  
**Implication:** OS/SCG required side-effects in commit stage with **D2** incomplete consumer block (FINDING-016 / CDR2-F3); T10/F2 call-site behavioral surface (FINDING-019).

### ADR-010 — Projections instead of big-bang key deletion (+ epoch)
**Decision:** Demote `last_*`/CSL/SRF/… to write-through projections before removal; every subject projection carries `subject_generation`.  
**Why:** Deep call graph; incremental migration (centralization_001); FINDING-021.  
**Multi-node:** Shared envelope SoT + §12.1 interface (FINDING-008 / CDR2-F4).

### ADR-011 — Session identity via stable thread_id mapping
**Decision:** Checkpoint key = mapped `thread_id(session_id)` per §13.1 algorithm (SHA-256 hex trunc + `sts:` namespace); empty/anon reject; serial lease per `thread_id`.  
**Why:** Restart recovery and multi-turn soft FU require durable identity isolation (FINDING-022 / FINDING-007 / CDR2-F5). Queue wait bound **5000 ms**; multi-instance write requires shared lease store.  
**Corrupt checkpoint:** single refuse→cold→AUDIT→clarify branch; checksum/schema version required (FINDING-023).  
**Deferred:** DEFER-017 lock hierarchy remains deferred — lease authority rule does not close it.

### ADR-012 — Documento Mestre SSOT + deploy SoT honesty
**Decision:** Cite official Architecture SSOT at `docs/architecture/` (Master VERSION 2026.08.06 + README + SSOT_POLICY; Git commit `9f53678`) as Documento Mestre Path A for CDR2-F1. Do not invent parallel master paths; do not treat Spec/CDR/AAR prose as Substitution waiver. Technical CDR/AAR ≠ Substitution authorization. Substitution requires Master **plus** residual disposition **plus** APPROVED AAR. Deploy SoT = `artifacts/aurora/` with hard release assert; open mirror drift = P4 NO-GO.  
**Why:** Master §0 supersedes prior INSUFFICIENT EVIDENCE *for master absence*; FINDING-006 / FINDING-024 / FINDING-027 / SSOT_POLICY §8 honesty.  
**Non-effect:** Closing F1 does not approve implementation or close Spec residuals F2–F6.

---

## Appendix A — `(outcome × reason) → apply node` (FINDING-013)

Pure total function over seed / same-fixture / soft_FU / new_*. Bijective ambiguity between KEEP_EPISODE soft-FU (`keep_followup`) and seed/same-fixture (`apply_subject`) is **removed**.

| outcome | reason | Apply node |
|---------|--------|------------|
| `NEW_FIXTURE` | `new_fixture` | `apply_boundary` |
| `NEW_EPISODE` | `low_entity_overlap` | `apply_boundary` |
| `NEW_EPISODE` | `explicit_new_episode` | `apply_boundary` |
| `KEEP_EPISODE` | `soft_followup_same_episode` | `keep_followup` |
| `KEEP_EPISODE` | `seed_subject` | `apply_subject` |
| `KEEP_EPISODE` | `same_fixture_restated` | `apply_subject` |
| `KEEP_EPISODE` | `overlap_ok_keep` | `apply_subject` |

Any additional TB-V2 reason token **must** be added to this table before use; unclassified `(outcome × reason)` ⇒ classify degrade machine (`safe_boundary_clear` path) — not silent invent.

---

## Appendix B — P2 Ingress-Order Success Criteria (FINDING-014 / CDR2-F2)

Named falsifiable pass/fail set for `ingress_order_shadow_compare` (Path B). **Separate** from locus-1 (`before_langgraph`) legacy-lag monitoring — locus-1 rates are **not** pass criteria and **not** a P2 exit substitute.

| ID | Observable | Pass | Fail (P2 NO-GO) |
|----|------------|------|-----------------|
| IO-S1 | **Suite identity** | Harness runs Path B on golden sticky suite §9.3 (Flamengo→Liverpool→soft FU) **plus** CONTAMINATION_NOTES golden switch turns; sample size **N ≥ 30** Path B shadow turns in one named suite run | Suite identity unspecified or N < 30 |
| IO-S2 | **Locus-2 rate** | `contamination_locus = inside_state_layer` rate on Path B ≤ **5%** of suite turns | Locus-2 rate > 5% |
| IO-S3 | **Switch-turn subject match** | On NEW_FIXTURE / NEW_EPISODE turns in suite: NEW subject teams = expected post-boundary subject; divergence class `subject_teams_mismatch` count = **0** on those turns | Any `subject_teams_mismatch` on switch turns |
| IO-S4 | **Contaminated soft-FU class** | Divergence class `soft_fu_on_contaminated_prior` count = **0** across Path B suite | Count ≥ 1 |
| IO-S5 | **Separation from locus-1** | P2 exit report cites IO-S1…IO-S4; does **not** treat locus-1 legacy-lag rate as pass/fail substitute | Locus-1 used as sole/primary P2 exit criterion |

**P2 exit requires:** IO-S1…IO-S5 all Pass **and** locus `(2)` rare per §17 P2 narrative. Hostile reviewer grades without inventing thresholds — all numbers are in this table. Covered by T21 / V4.

---

## Validation Contract

**Authority (FINDING-027):** This Validation Contract is **non-authoritative** relative to the external CDR/AAR checklist for implementation gating. Spec self-grade is **not** an implementation gate. Implementation missions must not treat Q2 alone as green light. External authority = CDR lineage + AAR (AAR-002 → future AAR-003 after CDR3).

| # | Question | Answer |
|---|----------|--------|
| 1 | **Ambiguities remaining?** | **YES (listed below)** — residual process/ops items. Exact i18n copy for degrade/recovery classes; Postgres vs SQLite ops threshold beyond multi-instance class rule; final env-name consolidation for stage enum vs legacy flags; full Orchestration pillar replacement timing (out of scope); DEFER-017 lock hierarchy; DEFER-018 projection fanout budget. Documento Mestre **path** resolved (SSOT Path A); Substitution still AAR-gated. |
| 2 | **Undefined responsibilities?** | **NO for the 24 ACCEPT-closed Context Manager responsibilities listed here, plus Plan 010 residual closures in v1.2.** Closed in v1.1 text: P3 commit host (Option A / C17); message rewrite authority; checkpoint↔projection durability Option A; commit stages + winner-on-divergence; per-phase rollback matrix; P0 technical ≠ Substitution; per-`thread_id` serial lease + queue/429; shared envelope multi-node norma; illegal flag matrix / stage enum; single classify degrade machine; typed EpisodeTransitionDecision; Appendix A route table; P2 ingress-order experiment structure; runtime sole-writer guard before P4; OS/SCG stage completeness letter; Frozen call-site T10/F2; ADR-001 provisional + flip triggers; `subject_generation` epoch; `thread_id` algorithm; single corrupt-checkpoint branch; deploy SoT hard assert; missing-host process-global degrade; note_* funnel+guard before P4; Validation Contract authority correction. **Closed in v1.2 residual text:** F1 SSOT pointer; Appendix B P2 criteria; Stage-5 **D2**; §12.1 shared-envelope interface; lease **5000 ms** + shared lease multi-node; **ctx proxy** guard class. **Still undefined by design / deferred:** Tool Use, Execution Manager, full Orchestration rewrite; DEFER-017 lock-order hierarchy; DEFER-018 projection fanout budget. |
| 3 | **Excessive coupling?** | **Controlled coupling:** Router↔Commit Host invoke and STS↔projections are intentional. **Forbidden coupling:** LangGraph↔engine internals; specializations↔STS private commit; Rasa↔session. Epoch + guard + shared envelope interface + D2 incomplete flag mitigate projection/OS-SCG coupling risk. |
| 4 | **Conflict with Documento Mestre?** | **Master present (Path A).** Cite `docs/architecture/master-architecture.md` (VERSION 2026.08.06) + `docs/architecture/README.md` + `docs/architecture/governance/SSOT_POLICY.md` (commit `9f53678`). This Spec is the Context Manager **specialization** under Master §5. For pillars/policies recorded in the Master: **no conflict certified** with Master Core policies (Frozen; specializations never modify Core; technical ≠ Substitution; code SoT `artifacts/aurora/`). Substitution authorization still **blocked** pending residual disposition + APPROVED AAR — not by master absence. Spec/CDR text is not a waiver (FINDING-006 / CDR2-F1 / SSOT_POLICY §8). |
| 5 | **Supports future evolution?** | **YES.** Host/checkpointer can deepen; STS schema can version; custom transition can centralize further; **contingency to drop LangGraph host** while keeping STS sole-writer is first-class with flip triggers (FINDING-020); Memory/Orchestration pillars can adopt same thread identity later without rewriting engines. Hard deploy assert closes ambiguity #5 as gate not open timeline (FINDING-024). |

### Remaining ambiguities (explicit list)

1. ~~Documento Mestre Etapa 1 requirements (absent)~~ **CLOSED for master-absence (CDR2-F1 Path A):** cite `docs/architecture/`. Substitution still AAR-gated.  
2. Final unified flag taxonomy naming (LangGraph vs `ENABLE_STS_*` vs `MIGRATION_STAGE`) — semantics binding; names consolidatable later.  
3. Exact user-visible **i18n copy** for `SUBJECT_DEGRADE_CLARIFY` / `SUBJECT_RECOVERY_CLARIFY` / `SUBJECT_HOST_UNAVAILABLE` — control-flow closed; copy deferred (ambiguity #3 reclassified).  
4. Ops threshold for mandating Postgres checkpointer beyond multi-instance shared-class rule (§12 / §12.1).  
5. ~~Timeline to retire `aurora/` mirror drift~~ **CLOSED as hard gate:** open drift = P4 NO-GO; deploy assert fail-closed (FINDING-024).  
6. DEFER-017 lock acquisition order (envelope vs checkpointer) — remains deferred; lease prose does **not** close it (CDR2-F5 / CDR2-F10).  
7. DEFER-018 projection fanout latency budget — remains deferred (CDR2-F11).  
8. ~~P2 ingress-order success criteria unpublished~~ **CLOSED** — Appendix B (FINDING-014 / CDR2-F2).  
9. ~~Stage-5 vs durable Stage-3 undefined handling~~ **CLOSED** — Disposition **D2** (§10.3) (FINDING-016 / CDR2-F3).  
10. ~~Shared envelope without interface~~ **CLOSED** — §12.1 (CDR2-F4).  
11. ~~Lease bound / multi-node lease authority~~ **CLOSED** — 5000 ms + shared lease store (CDR2-F5); DEFER-017 still deferred.  
12. ~~Sole-writer guard mechanism class unnamed~~ **CLOSED** — **ctx proxy** (§10.6) (CDR2-F6).

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
| Resolution Matrix (ACCEPT 24) | `observations/aurora_context_manager_governance_006/RESOLUTION_MATRIX.md` |
| AAR-001 | `observations/aurora_context_manager_governance_006/AAR-001.md` |
| Revision Plan 007 | `observations/aurora_context_manager_revision_plan_007/REVISION_PLAN.md` |
| Execution Report 008 | `observations/aurora_context_manager_spec_004/EXECUTION_REPORT_008.md` |
| Spec 004 v1.1 (prior) | `observations/aurora_context_manager_spec_004/SPEC_v1.1.md` |
| CDR2 | `observations/aurora_context_manager_cdr2_009/CDR2.md` |
| AAR-002 | `observations/aurora_context_manager_aar_002/AAR-002.md` |
| Residual Plan 010 | `observations/aurora_context_manager_residual_plan_010/RESIDUAL_BLOCKER_PLAN.md` |
| Master Architecture (Documento Mestre) | `docs/architecture/master-architecture.md` |
| Architecture SSOT navigation | `docs/architecture/README.md` |
| SSOT Policy | `docs/architecture/governance/SSOT_POLICY.md` |
| Execution Report 012 | `observations/aurora_context_manager_spec_004/EXECUTION_REPORT_012.md` |

---

```
FACT:
Engineering SPEC 004 v1.2 = Spec 004 v1.1 + Plan 010 residual closures
(CDR2-F1 Path A SSOT; FINDING-014/016 FULL; CDR2-F2…F6 dispositioned).
Historical SPEC.md (v1.0) and SPEC_v1.1.md untouched. No Aurora product code
modified. No new ADR ids. IMPLEMENTAÇÃO BLOQUEADA.

NEXT:
Missão 013 — CDR3 (hostile review of Spec 004 v1.2). Do not execute in Missão 012.
```
