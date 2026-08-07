# IMPLEMENTATION PLAN — Aurora Context Manager (Missão 014)

**Mission:** IMPLEMENTATION_PLANNING / OPERATIONAL_EXECUTION_PLAN  
**Record ID:** IMPL-PLAN-014  
**Date:** 2026-08-07  
**Role:** Lead Software Engineer / Release Manager / Technical Implementation Planner  
**Language:** Portuguese headings; technical IDs English  

**Architecture defendant (APPROVED):** `observations/aurora_context_manager_spec_004/SPEC_v1.2.md`  
**Board approval (architecture → planning only):** `observations/aurora_context_manager_aar_003/AAR-003.md` (`STATUS: APPROVED`)  
**Hostile review:** `observations/aurora_context_manager_cdr3_013/CDR3.md`  
**Architecture SSOT:** `docs/architecture/master-architecture.md` + `docs/architecture/README.md` + `docs/architecture/governance/SSOT_POLICY.md` (commit `9f53678`)  

**Code SoT (when eventually authorized):** `artifacts/aurora/`  
**This deliverable:** documentation only — **NO product code**, NO ADRs, NO migrations started.

---

## Status lock (binding)

| Gate | State |
|------|--------|
| Spec 004 v1.2 architecture | **APPROVED** (AAR-003) for Implementation Planning |
| This Implementation Plan | **DRAFT / PENDING APPROVAL** — not yet versioned as executable |
| Product code / Missão 016 | **BLOCKED** |
| Feature flags production write | Must remain **OFF** until Activation phase after all gates |

**IMPLEMENTAÇÃO permanece BLOQUEADA** until **all** of the following are true:

1. This plan is **approved** (human Board / Release Manager sign-off).  
2. This plan is **Git-versioned** on the governed branch (uncommitted draft ≠ executable authority — SSOT_POLICY §3).  
3. **Product Owner** issues **formal authorization** to execute the plan (Substitution / implementation auth ≠ AAR-003 architecture approval alone — FINDING-006 / Master §8.2).  
4. Recommended gate **Missão 015 — Readiness Review** completes green (or explicit waiver with owner/scope/expiry) **before first code** (Missão 016).

**Forbidden shortcuts:** AAR-003 APPROVED → code; this plan draft → code; skip Readiness Review without recorded waiver.

**Next recommended gate (do not start unless asked):** Missão 015 Readiness Review → then Missão 016 first code behind flags.

---

## 1. Executive Summary

This plan operationalizes Spec 004 **v1.2** for the Aurora Core **Context Manager** substitution: a **SportTopicState (STS) Sole-Writer** Context Manager with phase-specific Commit Host — **P3 Minimal Commit Orchestrator (C17)** then **P4 LangGraph host (C1)** — while preserving **KEEP CUSTOM TRANSITION** (TB-V2 / `EpisodeTransition.decide`) and leaving **Frozen** sports engines, SLL, Response Selector, and OS/SCG **internals** untouched.

**Primary migration strategy:** **Flag-gated Shadow → Sole-Writer Funnel → Gated Activation** (single-deploy / Replit-compatible **cut-over**, not blue/green dual fleet).

Existing POC assets under `artifacts/aurora/` evolve into the Spec contract; they are not discarded:

| POC asset | Path |
|-----------|------|
| STS model + flags | `artifacts/aurora/src/conversation/sport_topic_state.py` |
| LangGraph host graph | `artifacts/aurora/src/conversation/langgraph_state_graph.py` |
| Shadow adapter | `artifacts/aurora/src/conversation/langgraph_state_adapter.py` |
| Router shadow hook | `artifacts/aurora/src/routers/copilot_unified_router.py` (`maybe_shadow_compare`, fail-open) |
| Flags | `ENABLE_LANGGRAPH_STATE` / `ENABLE_LANGGRAPH_STATE_SHADOW` (default OFF) |
| Related | `ENABLE_TOPIC_BOUNDARY_V2` (TB-V2); CSL / note_* cascade in router end-of-turn |

Architecture decisions are **already settled** (12 Spec ADRs; Matrix Option A hosts; Durability Option A; Stage-5 **D2**; **ctx proxy** guard; Appendix B P2 criteria). This plan invents **no new ADRs** and requires **no new architectural forks** to execute.

**Perception-critical regressions that must stay green through Activation:**

1. **Flamengo×Palmeiras → Liverpool×Chelsea → soft FU** (“Quem está melhor?”) — Spec §9.3 / T4.  
2. **Soft FU on contaminated prior** — CONTAMINATION_NOTES / IO-S4 / R9.  
3. **Inter partial** — Flamengo×Palmeiras → “Inter joga hoje?” (single-team / calendar partial boundary; TB-002 Scenario 3).

---

## 2. Objetivo da Implementação

| ID | Objetivo |
|----|----------|
| IO1 | Deliver Spec-compliant **STS sole-writer** Context Manager behind flags, evolving the existing LangGraph STS POC — not a greenfield rewrite. |
| IO2 | Enforce **classify-before-commit** order via legal Commit Host per phase (C17 in funnel; C1 LangGraph in production write). |
| IO3 | Preserve **KEEP CUSTOM TRANSITION**; demote ≥14 write-owners to projections/adapters after cutover. |
| IO4 | Harden **shadow + ingress-order** (Appendix B) before any production subject write. |
| IO5 | Complete **sole-writer funnel** (note_* + analyze + boundary apply → STS) **before** enabling `ENABLE_LANGGRAPH_STATE`. |
| IO6 | Activate production write only under illegal-flag fail-closed matrix + **ctx proxy** guard + rollback drill. |
| IO7 | Protect betting credibility: fail-closed production subject path; fail-open shadow; Stage-5 **D2** consumer block. |
| IO8 | Leave Frozen engines / SLL / RS / OS-SCG internals untouched; specializations consume snapshot API only. |
| IO9 | Keep deploy SoT = `artifacts/aurora/`; open `aurora/` mirror drift = **P4 NO-GO**. |

---

## 3. Escopo

### 3.1 In scope

1. Evolution of POC STS / LangGraph graph / adapter / router integration boundary under Spec contracts.  
2. **C17 Minimal Commit Orchestrator** (P3) with identical edges/stages/semantics as P4 host.  
3. Typed `EpisodeTransitionDecision` + Appendix A routing; TB-V2 detect reuse; dual materializer retirement schedule.  
4. Projection / façade layer with mandatory `subject_generation` epoch.  
5. Feature-flag / `MIGRATION_STAGE` controller + illegal matrix I1–I7.  
6. Checkpoint / `thread_id` mapping / serial lease (5000 ms → 429) / shared-envelope interface when multi-instance claimed.  
7. Runtime sole-writer guard as **ctx proxy**; note_* subject funnel + guard before P4 exit.  
8. OS/SCG adapters via public APIs; Stage-5 **D2** (`stage5_os_scg_incomplete`).  
9. Test harnesses for T1–T22 / critical regressions / rollback drill.  
10. Flag-gated Activation and P5 writer retirement **after** guard zero-hit window.

### 3.2 Out of scope

| ID | Out |
|----|-----|
| OOS1 | New architecture / new ADR ids / reopening settled Matrix forks |
| OOS2 | Rasa DialogueStateTracker; LangGraph as sport-domain SoT |
| OOS3 | Rewriting Frozen engines, SLL internals, Response Selector subject authorship, OS/SCG algorithms |
| OOS4 | Full Orchestration / Tool Use / Execution Manager pillar replacement |
| OOS5 | Big-bang deletion of `last_*` / CSL / SRF keys without projection phase |
| OOS6 | Enabling `ENABLE_LANGGRAPH_STATE` by default or claiming bleed “fixed” while write OFF |
| OOS7 | Closing DEFER-017 / DEFER-018 in this plan’s execution (remain deferred) |
| OOS8 | Treating AAR-003 or this plan alone as Substitution waiver without Product Owner auth |
| OOS9 | Starting Missão 015/016 or committing this plan unless separately asked |

---

## 4. Pré-requisitos

| # | Prerequisite | Evidence / owner |
|---|--------------|------------------|
| PR1 | Spec 004 v1.2 architecturally APPROVED | AAR-003 |
| PR2 | CDR3 residual liberação Critical/High = 0 | CDR3-013 |
| PR3 | Architecture SSOT Path A present | `docs/architecture/` @ `9f53678` |
| PR4 | This plan approved + Git-versioned | Board / Release Manager |
| PR5 | Product Owner formal execution authorization | Signed auth note (owner, scope, flags allowed, expiry) |
| PR6 | Missão 015 Readiness Review green (recommended) | Checklist: flags OFF defaults; deploy tree; Frozen registry; harness inventory; mirror-drift status |
| PR7 | Code SoT confirmed = `artifacts/aurora/` | Audit 001 / Master §9 / Spec §16.1 |
| PR8 | POC baseline present and tests discoverable | Paths in §1; `test_langgraph_state_poc_001.py`, `test_langgraph_state_shadow_002.py`, TB-V2 tests |
| PR9 | Illegal combinations remain fail-closed; production write defaults OFF | Spec §8.8 |
| PR10 | ADR-001 provisional honesty retained (flip triggers known) | Spec ADR-001 |

**Explicit:** Meeting PR1–PR3 alone does **not** unlock code. PR4–PR5 (and recommended PR6) are mandatory before Missão 016.

---

## 5. Inventário de Impacto

Deploy / edit SoT: **`artifacts/aurora/`**. Mirror `aurora/` must not be assumed parity; open drift blocks Activation (P4 NO-GO).

### 5.1 Altered (evolve in place)

| Module / path | Change class |
|---------------|--------------|
| `artifacts/aurora/src/conversation/sport_topic_state.py` | STS schema + `subject_generation` + commit API; flag helpers retained |
| `artifacts/aurora/src/conversation/langgraph_state_graph.py` | P4 host: stages 1–5, Commit Gate, typed classify consume DTO |
| `artifacts/aurora/src/conversation/langgraph_state_adapter.py` | Shadow + `ingress_order_shadow_compare` (Appendix B) + hydrate metrics |
| `artifacts/aurora/src/conversation/topic_boundary_v2.py` | Decide KEEP; **apply** demoted to STS funnel (no independent subject invent after cutover) |
| `artifacts/aurora/src/routers/copilot_unified_router.py` | Shadow hook preserved; later Commit Host invoke; message-authority (SW-6); note_* cascade funnel |
| CSL / SRF / short_mem / continuity / focus / conversation_state / pronoun_continuity / message_intelligence / entity_resolver_v2 / brain_authority apply paths | Subject writes → STS events / projections; public non-subject APIs retained |
| OS / SCG **call sites** only | Stage-5 adapters; no internal algorithm edits |
| Feature-flag / migration stage controller (new surface on existing flag helpers) | Illegal matrix + stage enum |

### 5.2 Created (authorized only after Missão 016+)

| Artifact | Role |
|----------|------|
| Minimal Commit Orchestrator **C17** module (new file under conversation/ or adjacent) | P3 legal Commit Host |
| `EpisodeTransition.decide` + typed DTO (if not already centralized) | P1 hygiene |
| Projection / façade helpers + epoch tagging | ADR-010 |
| ctx proxy sole-writer guard | Spec §10.6 / CDR2-F6 |
| Serial lease + queue (process-local first; shared store if multi-instance claimed) | FINDING-007 / CDR2-F5 |
| Checkpoint backend wiring (dev → durable → shared if scaled) | Spec §13 |
| Expanded golden / ingress-order / concurrency / recovery suites | T1–T22 |

### 5.3 Removed (only in late Activation / P5)

| Item | Rule |
|------|------|
| Dead legacy subject writers | **After** ctx proxy proves **zero hits**; P5 retires code only — does not introduce enforcement |
| Dual materializers (TB-V2 apply ∥ host apply) | Retired after cutover stage; illegal I5 |

### 5.4 Preserved (untouched internals)

| Asset | Policy |
|-------|--------|
| Frozen sports engines (methodology, market, confidence, intelligence, learning, decision_center, knowledge, …) | `docs/FROZEN_MODULES.md` / Spec F1–F2 |
| SLL | KEEP perception SoT |
| Response Selector | Read-only consumer of STS / epoch-checked projections |
| OS / SCG module internals | Public API only |
| Conversation Personalization / specializations | Must not patch Core STS internals |
| External `POST /aurora/copilot` shape | Plus documented 429 / 503 classes only |

---

## 6. Sequência Oficial

Six **execution phases** (Prep → Activation). Spec conceptual **P0–P5** map into these phases; do not invent a second migration topology.

```text
Spec P0 ──────────────► Prep
Spec P1 + host skeleton ► Infra
Spec P2 + P3 funnel ───► Migration
Router / RS / OS-SCG ──► Integration
T1–T22 + drills ───────► Validation
Spec P4 write + P5 ────► Activation
```

---

### Phase 1 — Prep

**Objective:** Confirm governance unlock and baseline readiness; freeze scope against architecture reopen.

**Deliverables:**

- Signed plan approval + Git version of this document.  
- Product Owner formal auth (scope, allowed flags, environments).  
- Missão 015 Readiness Review checklist results (or recorded waiver).  
- Inventory of 14 write-owners + note_* cascade call sites (from centralization_001 + router).  
- Confirm defaults: `ENABLE_LANGGRAPH_STATE=0`, `ENABLE_LANGGRAPH_STATE_SHADOW=0`, TB-V2 independent.  
- Mirror-drift status note (`artifacts/aurora/` vs `aurora/`).

**Completion criteria:**

- PR4–PR6 satisfied.  
- No product code merged yet.  
- Board confirms **no new ADR** required to start Infra.

**Risks:** Treating AAR-003 as code auth; skipping Readiness Review; starting edits on mirror tree.

---

### Phase 2 — Infra

**Objective:** Build Commit Host / STS / transition / flag / durability scaffolding with flags still OFF for production write.

**Deliverables:**

- STS evolution: authoritative fields + `subject_generation` + Commit Gate stages 1–5 contract.  
- **C17 Minimal Commit Orchestrator** (same edges as graph: `init_load → classify → apply_* → commit`).  
- LangGraph graph evolution path prepared for P4 (ADR-001 provisional).  
- Typed `EpisodeTransitionDecision` + Appendix A consumer in classify.  
- Flag / `MIGRATION_STAGE` controller (`S0`…`S4_RETIRE`) + illegal matrix fail-closed boot asserts.  
- `thread_id` mapper (`sts:` + SHA-256 trunc per Spec §13.1).  
- Checkpoint store (dev InMemory/SQLite) + checksum/schema version.  
- Shadow adapter hardened; Path B ingress-order hook design (post-SLL pre-CSL).  
- Serial lease (local) with **5000 ms → HTTP 429**.

**Completion criteria:**

- Unit tests for STS commit, DTO, Appendix A, flag matrix (T2/T9/T15/T16) green in CI against `artifacts/aurora/`.  
- `ENABLE_LANGGRAPH_STATE` still OFF; shadow may be exercised in non-prod only.  
- Dual-orchestration ban verified: no second invent commit path.

**Risks:** Inventing divergent C17 vs C1 semantics; enabling write early; coupling LangGraph to engine internals (ADR-005).

---

### Phase 3 — Migration

**Objective:** Shadow hardening (Spec P2) then sole-writer funnel (Spec P3) without LangGraph production write.

**Deliverables:**

- Expand shadow suite: Flamengo→Liverpool→FU, soft-FU contaminated prior, Inter partial; CONTAMINATION_NOTES loci.  
- `ingress_order_shadow_compare` harness meeting **Appendix B IO-S1…IO-S5** (N≥30; locus-2 ≤5%; switch mismatch = 0; contaminated soft-FU = 0).  
- Funnel flags: boundary/analyze/note_* subject paths call STS.commit via **C17** only; dual-write forbidden.  
- Projections write-through with epoch; consumers discard mismatch.  
- OS/SCG Stage-5 wiring + **D2** flag semantics (no 2PC).  
- ADR-001 kill-criteria evaluation checkpoint (P2/P3).

**Completion criteria:**

- Appendix B Pass + locus `(2)` rare (T21 / V4).  
- Funnel proves single path on C17; `ENABLE_LANGGRAPH_STATE` remains OFF.  
- note_* subject fields funnelled or no-op toward STS (FINDING-026 progress measurable).  
- Stage-5 incomplete ⇒ `stage5_os_scg_incomplete` blocks coherent-NEW soft-FU/analyze (T19).

**Risks:** Declaring P2 exit via locus-1 rates alone (IO-S5 fail); dual-SoT-by-schedule; incomplete note_* before later Activation.

---

### Phase 4 — Integration

**Objective:** Wire Commit Host into router pipeline; message authority; RS/OS/SCG collaboration surfaces; preserve Frozen call-site goldens.

**Deliverables:**

- Router: acquire lease → SLL → Commit Host invoke → projection refresh → OS/SCG public APIs → engines (untouched) → Response Selector reads STS/projections with epoch check.  
- SW-6: intent/compare rewrite uses STS / pós-SLL teams — never CSL sticky pré-STS after cutover stage.  
- Preserve fail-open shadow hook until cutover policy retires it to monitoring.  
- TB-V2: detect OK; apply materializer retired or gated against dual apply (I5).  
- T10 Frozen call-site perception goldens binding OS/SCG/RS observables.  
- Deploy hard assert: required STS/LangGraph modules present under `artifacts/aurora/`.

**Completion criteria:**

- Integration tests for order classify-before-commit (T3), message authority (T13), orphan clear (T5), note_csl guard (T6).  
- Critical scenarios green on funnel path (write still OFF or staging-only funnel flags).  
- Specializations do not import/patch STS private commit.

**Risks:** Reintroducing sticky CSL rewrite; touching Frozen internals “for convenience”; router dual-path drift.

---

### Phase 5 — Validation

**Objective:** Prove Spec test/validation contracts and rollback drill **before** production write ON.

**Deliverables:**

- Full suite mapping T1–T22 / V1–V9 executed and recorded.  
- Concurrency: parallel same-`thread_id` serialize; >5000 ms → 429 (T14).  
- Recovery: restart hydrate; Stage 3→4 crash consumers refuse mismatch; corrupt checkpoint single branch (T8/T18).  
- Host unavailable degrade (T12) on staging with write simulated.  
- **P4 rollback drill checklist** dry-run with write briefly ON in non-prod then OFF (Spec §17.2).  
- Mirror-drift audit; multi-instance claim decision (if yes: shared envelope §12.1 + shared lease + shared checkpointer — else single-node scope only).  
- ctx proxy guard proves blocks on illegal writers (T1/T11) — hard precondition for Activation.

**Completion criteria:**

- Go/No-Go checklist (§10) all Go items met for gated write.  
- Rollback drill signed (flag OFF path, guard remains blocking, AUDIT lines present).  
- No open Critical/High defects on sticky-bleed / soft-FU / Inter partial / D2 / dual-SoT.

**Risks:** Greenwashing Validation with shadow-only evidence; skipping rollback drill; claiming multi-instance without §12.1.

---

### Phase 6 — Activation

**Objective:** Gated production host write (Spec P4) then writer retirement (Spec P5).

**Deliverables:**

- Enable `ENABLE_LANGGRAPH_STATE` **only** with sole-writer guard ON (**ctx proxy**), note_* guarded, illegal matrix green, deploy assert green, no open mirror drift.  
- Stage enum → `S3_PROD_WRITE`; monitor guard hit counter.  
- Production path uses LangGraph host (C1) unless ADR-001 flip recorded → contingency host.  
- After zero-hit window: `S4_RETIRE` — delete/retire dead writers (P5).  
- Post-activation soak: critical regressions + AUDIT dashboards.

**Completion criteria:**

- Spec P4 hard preconditions (1)–(9) all observable.  
- Guard zero-hit window before P5 deletions.  
- Rollback path proven under load (flag OFF ≤ minutes; see §8).  
- Context Manager remains Replacement Candidate until a later audit proposes Congelar (Spec F5/F6) — not automatic here.

**Risks:** Activating before funnel/guard; dual-SoT; P5 deleting before zero-hit; ops burden triggering ADR-001 flip mid-soak.

---

## 7. Estratégia de Migração

### 7.1 Primary strategy name

**Flag-gated Shadow → Sole-Writer Funnel → Gated Activation**  
*(also: “shadow-first sole-writer cut-over”)*

### 7.2 Justification

| Principle | Why |
|-----------|-----|
| Shadow before write | ADR-006; Audit R3 dual-SoT; POC honesty (FINDING-020) |
| Funnel before LangGraph write | P3 before P4; FINDING-015/026; illegal I1–I3 |
| Flags + stage enum | Instant posture change without rebuild; illegal matrix fail-closed |
| Dual-SoT prohibited once write ON | ADR-007; projections are epoch-tagged mirrors only |
| KEEP CUSTOM TRANSITION | Domain policy stays Aurora; host only orders/commits |
| Incremental projections | ADR-010 — no big-bang key deletion |

### 7.3 Blue/green vs cut-over (Aurora Replit / single-deploy reality)

Aurora’s typical deploy is **single process / single Replit (or equivalent) deploy tree** rooted at `artifacts/aurora/`, not a dual-fleet blue/green platform.

| Approach | Fit | Plan choice |
|----------|-----|-------------|
| **Blue/green** (two live fleets, traffic shift) | Poor fit without second environment + shared session/lease/checkpointer discipline | **Not primary** |
| **Flag cut-over** (same deploy; flags flip posture) | Matches Replit/single-deploy; rollback = flag OFF | **Primary** |
| Canary % traffic | Optional later if edge/proxy supports; not required for Spec compliance | Optional, non-blocking |

**Cut-over mechanics:**

1. Deploy code with all production write flags **OFF** (safe).  
2. Enable shadow / funnel flags in controlled environments.  
3. Activate write only after Validation Go.  
4. Instant rollback: `ENABLE_LANGGRAPH_STATE=0` (+ stage ≤ `S2_FUNNEL`); **keep ctx proxy ON during drain**; do not re-enable unguarded legacy writers.

Horizontal multi-instance is **out of single-node Activation scope** unless §12.1 + shared lease + shared checkpointer are met; otherwise claim single-node only (P4 NO-GO if falsely claimed).

---

## 8. Plano de Rollback

Aligned to Spec §17.2. “Rollback proven” = **drill executed** + checklist observables — not a slogan.

| Point | Trigger | Actions | Time target | Data to preserve |
|-------|---------|---------|-------------|------------------|
| R-Prep | Auth/scope mismatch | Stop; no code | N/A | Plan + auth records |
| R-Infra | Dual host invent / flag matrix broken | Revert Infra PR; flags OFF | < 1 deploy cycle | None durable yet |
| R-Migration (P2) | Appendix B red / ADR-001 flip | Disable shadow flags; write stays OFF; file flip eval | Minutes (env flag) | Shadow metrics only |
| R-Migration (P3) | Funnel divergence / dual path | Disable funnel write-through; keep `ENABLE_LANGGRAPH_STATE=0` | Minutes | Staging checkpoints may reset; projections may lag |
| R-Integration | Message-authority / Frozen golden fail | Revert router wiring PR; restore prior artifact revision | One deploy | Session envelopes pre-change |
| R-Validation | Rollback drill fail | Block Activation; remain ≤ S2 | N/A | Drill AUDIT logs |
| R-Activation (P4) | Bleed / dual-SoT / guard hits / deploy assert / mirror drift | **Immediate:** `ENABLE_LANGGRAPH_STATE=0`; stage ≤ S2; guard ON during drain; 429/503 in-flight; no merge | **≤ 5 minutes** flag flip; deploy revert if needed ≤ 1 cycle | **Last durable checkpoint** retained; do not wipe sessions blindly |
| R-P5 | Guard non-zero / writer resurrect | Stop deletions; restore prior revision; re-enter P4 monitoring | One deploy | Guard metrics; forbid further retirement |

**P4 rollback drill checklist (must be signed in Validation):**

- [ ] Flag OFF path exercised  
- [ ] Guard remains blocking illegal writers  
- [ ] Checkpoint resume verified  
- [ ] Projection generation refuse verified  
- [ ] OS/SCG incomplete (D2) path visible  
- [ ] Lease 429 path exercised  
- [ ] AUDIT lines present for drill  

**In-flight policy (Activation rollback):** fail-closed subject mutate; queue drain; refuse merge; UX clarify classes as Spec §14/§15.

---

## 9. Estratégia de Testes

Map to Spec §18 T1–T22. Environments: unit (CI) → integration (artifacts tree) → staging soak → gated prod Activation.

| Layer | Covers | Key IDs / scenarios |
|-------|--------|---------------------|
| **Unit** | STS commit sole mutator; DTO; Appendix A; flag matrix; ctx proxy teeth | T1, T2, T9, T11, T16 |
| **Integration** | Host order; router invoke; projections; OS/SCG adapters; note_* funnel | T3, T5, T6, T13, T19 |
| **Regression (critical)** | Flamengo→Liverpool→soft FU; soft FU contaminated prior; Inter partial; orphan clear; note_csl blocked | T4, T5, T6; TB-002 Scenario 3; CONTAMINATION_NOTES; IO-S4 |
| **Shadow / ingress-order** | Live ctx unchanged; loci; Appendix B N≥30 | T7, T21; IO-S1…IO-S5 |
| **Perf** | Lean checkpoint; turn latency budgets for host+lease (no Spec numeric SLA invent — measure & record baseline) | R6 watch |
| **Concurrency** | Same `thread_id` serialize; 5000 ms → 429; no last-writer-wins; shared lease if multi-instance | T14 |
| **Recovery** | Restart hydrate; Stage 3→4 mismatch refuse; corrupt checkpoint cold+AUDIT+clarify; host unavailable 503 | T8, T12, T18 |
| **Real / live validation** | Staging copilot turns on golden sticky + Inter partial + soft FU; compare AUDIT stamps | V6; TB-002 live_validation lineage |

**Critical regression pack (must remain green through Activation):**

1. **Flamengo×Palmeiras → Liverpool×Chelsea → “Quem está melhor?”** — T2 Liverpool subject; T3 keep Liverpool; no “Mantendo foco Flamengo”; message authority Liverpool (Spec §9.3 / T4 / T13).  
2. **Soft FU contaminated prior** — soft keep must not heal OLD Flamengo after failed switch; IO-S4 count = 0 on Path B.  
3. **Inter partial** — Flamengo×Palmeiras → “Inter joga hoje?”: boundary/low_entity_overlap; subject Internacional (or Inter entity); **no** Flamengo fixture reuse; no mantendo-foco Flamengo (`test_scenario4_partial_boundary_single_team` / TB-002 Scenario 3).

**Honesty rule:** Shadow NEW_STATE correctness ≠ production sole-writer proof (FINDING-020). Activation requires write-ON evidence.

---

## 10. Critérios Go/No-Go

### Go (all required for Activation)

| # | Criterion |
|---|-----------|
| G1 | Plan approved + Git-versioned + Product Owner formal auth |
| G2 | Missão 015 Readiness Review green (or explicit waiver) |
| G3 | Appendix B IO-S1…IO-S5 Pass; locus-2 rare |
| G4 | P3 funnel single-path proven on C17; note_* funnel+guard ready |
| G5 | ctx proxy sole-writer guard blocks illegal writers on production path (not logging stub) |
| G6 | Illegal flag matrix I1–I7 fail-closed; defaults OFF until flip |
| G7 | T4 + soft-FU contamination + Inter partial green with intended posture |
| G8 | T10 Frozen call-site goldens green |
| G9 | T14 concurrency + T8/T18 recovery green |
| G10 | Rollback drill checklist signed |
| G11 | Deploy SoT assert green; **no open mirror drift** |
| G12 | Multi-instance: either unclaimed (single-node) **or** §12.1 + shared lease + shared checkpointer met |
| G13 | ADR-001 flip triggers evaluated; contingency path documented if flipped |

### No-Go (any one blocks Activation)

| # | Condition |
|---|-----------|
| NG1 | Dual-SoT-by-schedule (write ON without guard/funnel) |
| NG2 | Appendix B fail or locus-1 used as sole P2 exit |
| NG3 | Critical regression red (Flamengo→Liverpool→FU / soft FU / Inter partial) |
| NG4 | Open `aurora/` vs `artifacts/aurora/` drift |
| NG5 | Multi-instance write claimed without shared envelope/lease/checkpointer |
| NG6 | Stage-5 incomplete silently treated as coherent NEW (D2 violated) |
| NG7 | Host missing with write ON without process-global degrade |
| NG8 | Product Owner auth absent or expired |
| NG9 | New architectural fork / unauthorized ADR invented mid-flight |

---

## 11. Critérios para Frozen

Relative to Context Manager work (Spec §20):

| ID | Criterion | Plan application |
|----|-----------|------------------|
| F1 | Listed in `docs/FROZEN_MODULES.md` / Audit Frozen Candidates | Engines, OS, SCG, guards, Decision Center, Knowledge, follow_up_engine, analyze integrity, FE personalization — **no internal edits** |
| F2 | CM work only touches public API call-site ordering/args | Covered by T10 goldens — behavioral collaboration surface |
| F3 | Response Selector read-only w.r.t. fixture SoT | Integration review gate |
| F4 | SLL remains perception KEEP | Not replaced by host |
| F5 | STS/Commit Host sole-writer + recovery + golden bleed green under production flag | **Later** audit may propose Congelar CM — **not automatic** in Missões 014–016 |
| F6 | Until F5, CM remains Replacement Candidate; flags default OFF | Activation does not change default-off in repo without auth |

**Explicitly not Frozen as subject SSOT:** CSL, SRF, short_mem, conversation_state, multi-writer cascade.

**Non-negotiable during all phases:** Frozen engines untouched in diffs; specializations never modify Core STS private commit.

---

## 12. Matriz de Riscos

| ID | Risk | Sev | Phase peak | Mitigation |
|----|------|-----|------------|------------|
| R1 | Dual-SoT if write ON while 14 writers remain | 🔴 | Activation | P3 before P4; ctx proxy; note_* guard; T11 |
| R2 | Governance / Substitution self-ratification | 🔴 | Prep | PO auth; AAR ≠ code; SSOT Path A honesty |
| R3 | Sticky bleed returns | 🔴 | Integration+ | Sole-writer + order + message authority; fail-closed prod |
| R4 | LangGraph becomes sport-logic SoT | 🟠 | Infra | KEEP CUSTOM; nodes call Aurora detect only |
| R5 | Mirror drift `aurora/` vs artifacts | 🟠 | Validation | Hard deploy assert; P4 NO-GO |
| R6 | Checkpoint bloat / latency | 🟡 | Infra+ | Lean STS snapshots |
| R7 | LangGraph ops burden / ADR-001 flip | 🟡 | Migration+ | Provisional ADR; contingency host; pin versions |
| R8 | Split transition detectors persist | 🟠 | Migration | P1 DTO + Appendix A; retire parallel apply |
| R9 | Soft FU on contaminated prior | 🔴 | Migration | Switch-turn NEW commit; Appendix B IO-S4 |
| R10 | OS/SCG internal redesign temptation | 🟠 | Integration | Adapters + D2 only |
| R11 | Concurrent same-session corruption | 🔴 | Validation | Serial lease 5000 ms; T14 |
| R12 | Multi-node stale envelope | 🟠 | Activation | §12.1 or single-node scope |
| R13 | Inter partial regress (single-team calendar) | 🟠 | Regression | TB-002 Scenario 3 in critical pack |
| R14 | Plan executed without versioning / PO auth | 🔴 | Prep | Status lock § top; Missão 015 gate |
| R15 | C7/C8 overlap under REJECT-011 (CDR3-R6) | 🟢 | Infra | Watch Commit Gate vs projection ownership; no third architecture |

DEFER-017 / DEFER-018 remain **deferred** — do not silently close in implementation PRs.

---

## 13. Cronograma Conceitual until Frozen

Conceptual windows (calendar length is Board-owned; order is binding). “Frozen” here means **CM proposed for Congelar after F5**, not Instant Freeze of engines (already frozen).

| Window | Content | Exit |
|--------|---------|------|
| **W0** | Plan approval + Git version + PO auth + Missão 015 | Prep complete — code still blocked until W0 done |
| **W1** | Infra (C17, STS epoch, flags, checkpoint, lease) | Phase 2 complete |
| **W2** | Migration P2 shadow + Appendix B | IO-S1…IO-S5 Pass |
| **W3** | Migration P3 sole-writer funnel + D2 + note_* | Funnel single-path; write still OFF |
| **W4** | Integration router / SW-6 / T10 | Integration green |
| **W5** | Validation full T/V + rollback drill | Go checklist green |
| **W6** | Activation P4 gated write soak | P4 preconditions met; guard monitoring |
| **W7** | P5 writer retirement after zero-hit | Dead writers retired |
| **W8** | Post-soak audit package → optional later **Congelar** proposal for CM | Spec F5 — separate governance mission |

**Parallelism allowed:** test harness authoring during W1–W2; documentation/AUDIT dashboards during W4–W5.  
**Forbidden parallelism:** Activation coding before W0; write ON before W3 funnel evidence.

---

## 14. Checklist Final

### Governance

- [ ] AAR-003 APPROVED acknowledged (architecture only)  
- [ ] This plan **approved** by Board / Release Manager  
- [ ] This plan **Git-versioned** on governed branch  
- [ ] Product Owner **formal auth** recorded (scope, flags, expiry)  
- [ ] Missão 015 Readiness Review complete (or waiver filed)  
- [ ] Explicit: **no Missão 016 code** until above  

### Architecture fidelity

- [ ] Sole-writer STS + KEEP CUSTOM TRANSITION retained  
- [ ] P3 = C17 Minimal Commit Orchestrator; P4 = LangGraph (unless ADR-001 flip)  
- [ ] No new ADRs; no Matrix third options  
- [ ] Stage-5 **D2**; ctx proxy; Appendix B; 5000 ms lease  
- [ ] Frozen engines / SLL / RS / OS-SCG internals untouched  

### POC evolution paths cited

- [ ] `artifacts/aurora/src/conversation/sport_topic_state.py`  
- [ ] `artifacts/aurora/src/conversation/langgraph_state_graph.py`  
- [ ] `artifacts/aurora/src/conversation/langgraph_state_adapter.py`  
- [ ] Router shadow hook in `copilot_unified_router.py`  
- [ ] Flags `ENABLE_LANGGRAPH_STATE` / `_SHADOW`; TB-V2; note_* cascade  

### Migration / safety

- [ ] Shadow → funnel → gated activation sequence respected  
- [ ] Dual-SoT banned on write ON  
- [ ] Rollback drill signed before Activation  
- [ ] Mirror drift = NO-GO checked  
- [ ] Critical pack: Flamengo→Liverpool→FU; soft FU; Inter partial  

### Exit

- [ ] Go/No-Go all Go  
- [ ] Activation soak + guard zero-hit before P5  
- [ ] F5 Congelar proposal deferred to later audit (not auto)

---

## Validation Contract answers

**Authority:** This plan’s Validation Contract is **operational**. Spec self-grade remains **non-authoritative** for implementation gating (FINDING-027). External authority chain: CDR3 + AAR-003 + **approved versioned plan** + **Product Owner auth** (+ recommended Missão 015).

| # | Question | Answer |
|---|----------|--------|
| 1 | Ambiguities remaining that block planning? | **NO for execution planning of APPROVED Spec v1.2.** Residual ops items remain: i18n copy for degrade/recovery UX classes; final flag taxonomy naming consolidation; Postgres mandate threshold beyond multi-instance class; DEFER-017/018. None invent a new architecture. |
| 2 | Undefined responsibilities for implementers? | **NO for Context Manager Spec responsibilities C1–C17 + commit stages + projections + guard.** Still out of scope by design: Tool Use, Execution Manager, full Orchestration rewrite. |
| 3 | Excessive new architectural decisions before first code? | **NO.** Architecture APPROVED; ADR count remains 12; this plan only sequences Spec P0–P5 into Prep→Activation. |
| 4 | Conflict with Documento Mestre / SSOT? | **NO.** Plan cites Master §5 specialization; code SoT `artifacts/aurora/`; technical ≠ Substitution retained. |
| 5 | Is product code authorized now? | **NO.** IMPLEMENTAÇÃO BLOQUEADA until plan approved + versioned + PO formal auth (+ recommended Missão 015 before Missão 016). |
| 6 | Primary migration strategy? | **Flag-gated Shadow → Sole-Writer Funnel → Gated Activation** (single-deploy cut-over; not blue/green primary). |
| 7 | Official phase count? | **6** — Prep, Infra, Migration, Integration, Validation, Activation. |
| 8 | Critical regressions named? | **YES** — Flamengo→Liverpool→soft FU; soft FU contaminated prior; Inter partial. |
| 9 | Next recommended gate? | **Missão 015 Readiness Review** before first code (**Missão 016**). Do not start unless asked. |
| 10 | Was any product code modified in Missão 014? | **NO** — only this plan document. |

---

## Evidence index

| Topic | Path |
|-------|------|
| Spec 004 v1.2 | `observations/aurora_context_manager_spec_004/SPEC_v1.2.md` |
| AAR-003 | `observations/aurora_context_manager_aar_003/AAR-003.md` |
| CDR3 | `observations/aurora_context_manager_cdr3_013/CDR3.md` |
| Master Architecture | `docs/architecture/master-architecture.md` |
| SSOT Policy | `docs/architecture/governance/SSOT_POLICY.md` |
| SSOT README | `docs/architecture/README.md` |
| Research 003 | `observations/aurora_context_manager_research_003/REPORT.md` |
| Centralization / 14 writers | `observations/topic_state_centralization_001/REPORT.md` |
| KEEP CUSTOM TRANSITION | `observations/topic_transition_arch_001/REPORT.md` |
| LangGraph POC | `observations/langgraph_state_poc_001/REPORT.md` |
| Contamination notes | `observations/langgraph_state_poc_001/shadow/CONTAMINATION_NOTES.md` |
| TB-002 Inter partial | `observations/topic_boundary_002/live_validation/TRANSCRIPT.md` (Scenario 3) |
| Frozen registry | `docs/FROZEN_MODULES.md` |

---

```
FACT:
Missão 014 Implementation Plan written for Spec 004 v1.2 (AAR-003 APPROVED architecture).
Primary strategy: Flag-gated Shadow → Sole-Writer Funnel → Gated Activation (6 phases).
IMPLEMENTAÇÃO BLOQUEADA until plan approved + versioned + Product Owner formal auth.
Recommended next: Missão 015 Readiness Review before Missão 016 first code.
NO product code modified. NO new ADRs. NO migrations started.
ONLY FILE: observations/aurora_context_manager_impl_plan_014/IMPLEMENTATION_PLAN.md
```
