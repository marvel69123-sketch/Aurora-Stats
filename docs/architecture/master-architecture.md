# Aurora Core — Master Architecture (Documento Mestre)

**DOCUMENT ID:** AURORA-CORE-MASTER  
**VERSION:** 2026.08.06  
**STATUS:** OFFICIAL — established by Missão ARCHITECTURE_GOVERNANCE / SSOT_FOUNDATION  
**SSOT ROOT:** `docs/architecture/`  
**CLASS:** Architecture governance (Documento Mestre)

---

## 0. Establishment notice (binding)

This document **establishes** the official Aurora Core Master Architecture SSOT as of **2026-08-06**.

| Fact | Statement |
|------|-----------|
| Prior “Documento Mestre Etapa 1” | **Did not exist** in-repo (Audit 001; Research 003; CDR1 FINDING-006; CDR2-F1; AAR-001/002; Residual Plan 010 §1.1). |
| Fake history | This Board **does not invent** a prior “Etapa 1” ratification ceremony or claim retroactive existence. |
| Effect on audits | For **architecture pillars and policies recorded herein**, future audits supersede the prior label **INSUFFICIENT EVIDENCE** *regarding master-document absence*. They must cite this path. |
| What remains open | Spec residual blockers (CDR2-F2…F6, PARTIAL 014/016), AAR-002 **NOT APPROVED**, and Substitution authorization remain separate. Existence of this master **closes governance blocker CDR2-F1 (Path A)** when versioned in Git; it does **not** approve implementation. |

**Authority supersession:** Working-paper proxies (Audit 001 + Research 003 + ARCH reports) remain **historical evidence**. They are no longer the navigation SSOT for Core pillars/policies once this document is Git-versioned under `docs/architecture/`.

---

## 1. Purpose and scope

### 1.1 Purpose

Define the **Aurora Core** architectural pillars, cross-cutting policies, and specialization rules so that Substitution-facing work has a certifiable master authority in-repo.

### 1.2 In scope

- 14 Aurora Core pillars (names, strategic stance, frozen/replacement posture)
- Code/deploy SoT discipline
- Frozen engines / guards policy (pointer + ratification intent)
- Context Manager specialization under Core (LangGraph-hosted STS — Research 003 / Spec 004)
- Governance chain: technical Spec acceptance ≠ Substitution authorization
- Freeze-while-NOT-APPROVED rule

### 1.3 Out of scope

- Product code changes
- Spec 004 / SPEC_v1.1 content edits (pointer only)
- Implementation Plans, migrations, feature-flag flips
- Inventing Spec residual closures

---

## 2. Evidence basis (this version)

| Evidence | Path | Used for |
|----------|------|----------|
| Audit 001 | `observations/aurora_core_audit_001/REPORT.md` | 14 pillars scoreboard; Frozen/Replacement maps; Substitution **NO**; master absence |
| Research 003 | `observations/aurora_context_manager_research_003/REPORT.md` | Primary decision: LangGraph-hosted STS Sole-Writer Context Manager |
| Spec 004 / v1.1 | `observations/aurora_context_manager_spec_004/SPEC.md`, `SPEC_v1.1.md` | Context Manager specialization contract (under review; not implementation-approved) |
| Frozen modules | `docs/FROZEN_MODULES.md` (+ `docs/FROZEN_CONVERSATION_PERSONALIZATION.md`) | Official freeze registry |
| Deploy / code map | `AURORA_ARCHITECTURE.md` (repo root) | `artifacts/aurora/` code SoT; mirror discipline |
| AAR-001 | `observations/aurora_context_manager_governance_006/AAR-001.md` | NOT APPROVED; liberação gates; FINDING-006 |
| AAR-002 | `observations/aurora_context_manager_aar_002/AAR-002.md` | NOT APPROVED; CDR2-F1 critical; residuals |
| CDR2 | `observations/aurora_context_manager_cdr2_009/CDR2.md` | Hostile review; F1 evidence gap |
| Residual Plan 010 | `observations/aurora_context_manager_residual_plan_010/RESIDUAL_BLOCKER_PLAN.md` | F1 Path A preferred; search ABSENT |

---

## 3. System identity

Aurora (present tense, evidence-bound) is a **production sports-analysis + conversational Copilot stack**. It is **not yet** a fully modular Aurora Core. Core reconstruction proceeds pillar-by-pillar under Frozen policy, shadow-first gates, and AAR authorization — never by greenwashing Substitution via CDR/AAR technical acceptance alone.

**Code / deploy Source of Truth:** `artifacts/aurora/`  
**Optional mirror:** `aurora/` — must not be assumed parity; open mirror drift is a process risk (Audit 001).  
**Frontend Copilot SoT:** `artifacts/web/`

---

## 4. The 14 Aurora Core pillars

Strategic stance below is **ratified from Audit 001 §3.15** as the opening Master baseline. Estado/Qualidade describe the audited as-is system, not a claim of completed Core modularity.

| # | Pillar | Audited estado | Audited qualidade | Strategic recommendation (Audit 001) | Master policy note |
|---|--------|----------------|-------------------|--------------------------------------|--------------------|
| 1 | Understanding | Parcial | Regular | Melhorar | Multiple classifiers coexist; SLL remains nickname SoT (Frozen candidate) |
| 2 | Context Manager | Parcial | Crítica | **Substituir** | Sole-writer STS; see §5 specialization |
| 3 | Memory | Parcial | Regular | Melhorar | Session RAM+SQLite; cross-node gap; cache ≠ SoT |
| 4 | Knowledge | Implementado | Boa | **Congelar** | `knowledge_engine` under frozen engines |
| 5 | Search | Parcial | Regular | Melhorar | No single Search contract yet |
| 6 | Planning | Parcial | Regular | Melhorar | Response-plan oriented today |
| 7 | Reasoning | Implementado | Boa | **Congelar** | Sports engines Congelar; conversational reasoner not Core-frozen |
| 8 | Reflection | Implementado | Boa | Manter | Present; presentation-heavy |
| 9 | Decision | Parcial | Regular | Melhorar | Sports Decision Center frozen; conversational decisions fragmented |
| 10 | Tool Use | Parcial | Crítica | **Substituir** | Ad-hoc tools → future Core registry (design later) |
| 11 | Execution Manager | Ausente | Crítica | **Substituir** | Absent as named pillar |
| 12 | Orchestration | Parcial | Crítica | **Substituir** | Monolithic router; LangGraph host candidate after gates |
| 13 | Learning | Parcial | Regular | **Congelar** | Learning engine formulas frozen; not closed-loop Core Learning |
| 14 | Observability | Parcial | Boa | Melhorar | Strong stamps; not unified Core telemetry |

### 4.1 Pillar governance rules

1. **One recommendation class per pillar** at Master level (Manter | Congelar | Melhorar | Substituir) until a versioned Master revision changes it.  
2. **Substituir** does **not** authorize code. It authorizes *design/Spec work* only under AAR rules.  
3. **Congelar / Frozen** assets must not be retuned for chat metrics (Audit R4).  
4. Specializations **consume** Core contracts; they **must not modify** Frozen Core internals (Spec O8 / Audit roadmap).

---

## 5. Context Manager specialization under Core

### 5.1 Binding architectural decision (Research 003)

**PRIMARY ARCHITECTURE (Context Manager pillar):**  
**LangGraph-hosted SportTopicState (STS) Sole-Writer Context Manager**

| Layer | Owner | May write sport subject? |
|-------|-------|--------------------------|
| Commit Host (P4 target: LangGraph; P3: Minimal Commit Orchestrator per Spec v1.1 Matrix Option A) | Host / order / durability | No domain invent |
| STS commit | Aurora Core Context Manager | **Yes — only** (post sole-writer cutover) |
| EpisodeTransition / TB-V2 | Aurora custom (KEEP CUSTOM TRANSITION) | Decide only; apply via STS |
| CSL / SRF / short_mem / continuity / focus / `last_*` | Projections / adapters | **No** independent subject authorship after cutover |
| OS / Sport Continuity Guard | KEEP modules | Lock/anchor via public APIs fed by STS |
| Sports engines | FROZEN | Never |

**Fallback (Research 003 shortlist #2):** Custom STS sole-writer without LangGraph — contingency if ADR flip criteria fire; same STS event funnel and custom transition.

**Forbidden:** Adopt Rasa/LangGraph as **sport-domain logic** SoT; enable production LangGraph write while multi-writer remains (Audit R3 dual-SoT).

### 5.2 Spec 004 / v1.1 status under Master

Spec 004 (incl. SPEC_v1.1) is the **Context Manager specialization package** under Aurora Core. It is:

- **In-review / reviewable** for technical contract quality  
- **Not** approved for implementation (AAR-001 / AAR-002 = **NOT APPROVED**)  
- Bound by: technical Spec acceptance **≠** Substitution Phase authorization  

Normative detail lives in the Spec package (see `docs/architecture/specifications/`). This Master does **not** copy Spec wholesale and does **not** edit Spec content.

### 5.3 Conceptual migration posture (Research 003 — summary)

P0 governance → P1 transition hygiene → P2 shadow hardening → P3 sole-writer funnel (gated) → P4 production host write → P5 writer retirement.  
Production write flags remain **OFF** until authorized Implementation Plan after APPROVED AAR.

---

## 6. Frozen policy (engines, guards, FE)

### 6.1 Official freeze registry

Binding product freeze list: [`docs/FROZEN_MODULES.md`](../FROZEN_MODULES.md).

Includes (non-exhaustive; registry wins): Integrity Guard / PARTIAL / Resolver; MatchHeader; Premium Live; featured market / live stats FE; Decision Center / Market / Confidence / Methodology / Learning / Knowledge engines; FollowUp Engine; Analyze / payloads; Conversation Personalization System v3.6.x.

### 6.2 Core Frozen Candidates (Audit 001 §4 — ratified intent)

During Core reconstruction, the following remain **Frozen Candidates** unless a signed redesign brief supersedes them under SSOT_POLICY:

- Sports engines: methodology, market, confidence, intelligence, learning, decision_center, knowledge  
- AEP / conversation guards: ownership_stability, sport_continuity_guard, ambiguous_context_guard, fiction_context_jump_guard  
- Understanding anchors: sports_language (SLL), entity_safety  
- follow_up_engine; Analyze / Integrity; response_selector (read-only consumer of subject); fixture_status as `is_live` SoT  
- FE Conversation Personalization (must not modify Core intelligence)

**Explicitly NOT frozen as Core Context SSOT:** CSL, SRF, short_mem, conversation_state, multi-writer cascade — operational today; target = projections under sole-writer STS.

### 6.3 Sacred freeze rules (from FROZEN_MODULES)

1. Never regress.  
2. Evolve additively.  
3. Do not touch what is good without protocol.  
4. Personalization never alters intelligence.  
5. Frozen modules have maximum protection priority; pre-merge failure → **ABORT MERGE**.

---

## 7. Replacement posture (strategic, not authorized)

Audit 001 Replacement Candidates (design direction only): multi-writer sport state → STS sole-writer; parallel transition detectors → single EpisodeTransition.decide; ad-hoc Tool Use → Core registry; mega-router → Core Orchestrator; mirror dual-tree risk → single SoT discipline.

**Do not** open Substitution by swapping methodology/market/confidence/intelligence/learning first.

---

## 8. Governance chain and freeze-while-NOT-APPROVED

| Record | Status | Binding effect |
|--------|--------|----------------|
| AAR-001 | **NOT APPROVED** | Blocks implementation / Substitution |
| AAR-002 | **NOT APPROVED** | Blocks implementation / Substitution; lists CDR2-F1 + HIGH residuals |
| Future AAR-003 | Required for liberação | Must record APPROVED (or conditional with non-blocker residuals only) |

### 8.1 Frozen architecture rule (while NOT APPROVED)

While the AAR chain for Context Manager / Substitution remains **NOT APPROVED**:

1. **No product code**, migrations, or production write-flag enablement for the Substitution design.  
2. **No silent Spec self-ratification** as Substitution authority.  
3. Governance documentation may still be published (this Master, SSOT policy, residual plans) to close evidence gaps.  
4. Spec residual closure proceeds only via dedicated documentation missions; implementation remains blocked until liberação criteria in AAR-002 are met.

### 8.2 Technical acceptance ≠ Substitution

CDR/AAR technical acceptance of Spec prose **does not** authorize Substitution Phase. Substitution requires Master (this document) **or** a written waiver (owner, scope, expiry, time-box) **plus** residual disposition **plus** APPROVED AAR — per AAR-001/002 Critérios para Liberação.

### 8.3 CDR2-F1 closure mapping

| Path | Artifact | This mission |
|------|----------|--------------|
| **Path A (preferred)** | Documento Mestre in-repo | **This file** under `docs/architecture/master-architecture.md` |
| Path B | Written Substitution waiver | Template only: `governance/SUBSTITUTION_WAIVER_TEMPLATE.md` — **not activated**; prefer Master coverage |

---

## 9. Code SoT and observation discipline

| Concern | Rule |
|---------|------|
| Runtime code SoT | `artifacts/aurora/` |
| Architecture SSOT | `docs/architecture/` |
| Observations | Working papers until promoted via `SSOT_POLICY.md` |
| Cache | Never Source of Truth for audits |
| Assumptions | Forbidden as evidence; unknowns labeled INSUFFICIENT EVIDENCE |

---

## 10. Versioning

- Version format: `YYYY.MM.DD` (document version = establishment/revision date).  
- Changes require governance process in [`governance/SSOT_POLICY.md`](./governance/SSOT_POLICY.md).  
- Git history is the audit trail; uncommitted Master does not satisfy F1 for Board purposes until committed/versioned per policy.

---

## 11. Validation (Master self-check)

| # | Question | Answer |
|---|----------|--------|
| 1 | Is this the official Documento Mestre / Master Architecture? | **YES** — established 2026-08-06 at this path |
| 2 | Were pillars invented without Audit 001? | **NO** — scoreboard from Audit 001 §3.15 |
| 3 | Was LangGraph-STS invented here? | **NO** — Research 003 §7 primary decision; Spec 004 specialization |
| 4 | Does this approve implementation? | **NO** — AAR-001/002 remain NOT APPROVED |
| 5 | Does this close CDR2-F1 Path A (governance evidence)? | **YES, when Git-versioned** — see SSOT_FOUNDATION mission report |
| 6 | Spec / product code modified by this document? | **NO** |
