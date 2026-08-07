# CDR2 — Critical Design Review 2 (Missão 009)

**Record ID:** CDR2-009  
**Mission:** CRITICAL_DESIGN_REVIEW_2 / ARCHITECTURE_GOVERNANCE (009)  
**Role:** Independent Architecture Review Board / Principal Software Architect / Chief Technical Reviewer  
**Stance:** Hostile-but-fair. Reviewer did **not** author Spec 004 v1.1. Spec assumed flawed until proven otherwise.  
**Date:** 2026-08-06  
**Primary defendant:** `observations/aurora_context_manager_spec_004/SPEC_v1.1.md`  
**Baseline (historical):** `observations/aurora_context_manager_spec_004/SPEC.md` (v1.0 — read-only)  
**Cross-exhibits (exclusive inputs):** CDR 005, RESOLUTION_MATRIX + AAR-001, REVISION_PLAN 007, EXECUTION_REPORT_008 (claims cross-checked against Spec text — not trusted blindly)

**Absolute non-actions (this mission):** No edits to SPEC/SPEC_v1.1/CDR/Matrix/Plan/AAR; no code; no new ADRs; no implementation patches; no AAR-002 issuance; no git commit. **Only this file written.**

---

## 1. Executive Summary

Spec 004 v1.1 closes the **load-bearing contradictions** that made v1.0 non-implementable (P3 host, fake atomicity, durability window, sole-writer/note_* schedule, message authority, concurrency policy, illegal flags, rollback matrix, Validation Contract self-grade). Against REVISION_PLAN 007 completion criteria, **all 24 ACCEPT findings are present in Spec prose**; **0 ACCEPT omitted**. Cross-check of EXECUTION_REPORT_008’s “24/24 correct” claim: **not fully upheld** — **2 applications are PARTIAL** (FINDING-014 ingress-order success criteria never falsified; FINDING-016 Stage-5 OS/SCG after durable Stage-3 leaves a still-defined contamination window). **0 ACCEPT incorrectly replaced by a third Matrix architecture.**

**Critical architectural contradictions of CDR1 BLOCKER class are not re-found as open Spec-text defects.** Remaining **🔴** is **governance evidence**: Documento Mestre Etapa 1 still absent and **no written Substitution waiver** exists in-repo — correctly labeled INSUFFICIENT EVIDENCE by Spec, but still a hard AAR-001 liberação gate. Several **🟠 HIGH** residuals remain that can brick P2 greenwash, P4 multi-node credibility, or OS/SCG post-checkpoint coherence if AAR ignores them.

**Verdict for AAR-002:** Spec package is reviewable, but Board should record **NOT APPROVED** for implementation / Substitution authorization until Documento Mestre **or** waiver exists and HIGH residuals below are dispositioned. This CDR2 does **not** issue AAR-002.

| Metric | Result |
|--------|--------|
| ACCEPT present in v1.1 | **24 / 24** |
| ACCEPT omitted | **0** |
| ACCEPT fully correct vs Plan criteria | **22 / 24** |
| ACCEPT partial / incomplete | **2** (014, 016) |
| ACCEPT wrong Matrix fork / third architecture | **0** |
| Spec-text 🔴 CRITICAL blockers (CDR1 class) | **0** |
| Governance 🔴 remaining (master/waiver evidence) | **1** |
| 🟠 HIGH residuals registered | **6** |
| 🟡 MEDIUM residuals registered | **5** |
| Ready to **submit** to AAR-002 | **YES (for judgment)** |
| Recommend AAR-002 **APPROVED** | **NO** |

---

## 2. Comparação Spec 004 vs Spec 004 v1.1

| Dimension | Spec 004 v1.0 | Spec 004 v1.1 | CDR2 assessment |
|-----------|---------------|---------------|-----------------|
| Commit host | Graph-only `_commit` vs P3 OFF-LangGraph contradiction | Phase table: **C17 Minimal Commit Orchestrator (Option A)** for P3; C1 LangGraph for P4; dual orchestration banned | Closed in text |
| Atomicity | Cross-store “atomic” slogans | Numbered stages 1–5; “atomic” only with defined UoW; winner-on-divergence | Closed in text |
| Checkpoint ↔ projections | Absolute consistency postcondition; crash dual-SoT | Durability **Option A**; consumers refuse generation mismatch | Closed in text |
| OS/SCG | Silent best-effort after checkpoint | Stage 5 required; incomplete ⇒ fail-closed / visible incomplete | Letter closed; **residual window** (see CDR2-F3) |
| Sole-writer schedule | Guard/teeth effectively P5; note_* residual through P4 | Runtime guard + note_* funnel = **hard P4 preconditions**; P5 = retirement only | Closed in text |
| Message rewrite | Outside contract | SW-6 + T13; sticky CSL pré-STS banned after cutover | Closed in text |
| Concurrency | Last-writer-wins silence | Serial lease; conflict policy **queue** (FIFO); timeout → 429; refuse merge; T14 | Closed in text (bound/distributed lease thin) |
| Multi-node | Postgres note; local envelope | **Shared envelope SoT**; sticky complement-only; P4 multi-instance gate | Norma closed; **mechanism thin** (CDR2-F4) |
| Flags | Prose precedence | Illegal matrix I1–I7 + `MIGRATION_STAGE`; fail-closed C12/T9 | Closed; dual naming residual listed |
| Classify degrade | “safe boundary **or** no invent” | Single machine `safe_boundary_clear` with decidable inputs | Closed (naming nit) |
| Rollback | “Proven” slogan | Per-phase matrix §17.2 + drill checklist | Closed in text |
| P0 / Documento Mestre | Self-ratify via CDR accept | Technical ≠ Substitution; master **or** waiver; INSUFFICIENT EVIDENCE retained | Spec text closed; **evidence still missing** |
| ADR-001 | Overclaims POC | **PROVISIONAL** + flip triggers; POC honesty | Closed in text |
| Validation Contract | Self-grade hazard | Non-authoritative; Q2 honest closed-list | Closed in text |
| Identity | “Deterministic” handwave | SHA-256 trunc + `sts:` ns; length 36; empty/anon reject; T15 | Closed in text |
| Corrupt checkpoint | Open-or-refuse coin-flip | Refuse → AUDIT → cold STS → UX clarify; checksum/schema | Closed in text |
| Component split | C1–C16 | C17 added (authorized Option A); REJECT-011 not applied | Consistent with Matrix |
| Historical SPEC.md | — | Untouched (EXECUTION_REPORT claim; not re-hashed here beyond non-modification mandate) | OK |

**Regressions:** No intentional rollback of closed ACCEPT themes found. Clarity regressions / residual hazards: (1) §5.1 ASCII flow still draws Projection/OS-SCG **after** Commit Gate while §9.1/§10.3 nest them as stages — diagram can re-teach the old wrong mental model; (2) OS/SCG “in commit stage” **after** UoW boundary A (Stage 3) preserves a durable NEW + side-effect OLD window; (3) P2 repeatedly demands “separate success criteria” without publishing them.

---

## 3. Resultado da validação dos 24 ACCEPT

Cross-check method: REVISION_PLAN 007 **Critério de Conclusão** × Spec v1.1 prose (tables, normative rules, gates). EXECUTION_REPORT_008 used only as a claim list.

| Finding | Applied? | Correct? | Notes |
|---------|----------|----------|-------|
| FINDING-006 | YES | YES | §16.4, §17 P0, O9, ADR-012, VC Q4: technical ≠ Substitution; master **or** waiver fields; INSUFFICIENT EVIDENCE retained. **Operational evidence** still absent (see CDR2-F1). |
| FINDING-022 | YES | YES | §13.1 algorithm, length 36, `sts:` + checkpoint_ns, empty/anon reject; T15. |
| FINDING-020 | YES | YES | ADR-001 **PROVISIONAL**; flip triggers listed; POC not production proof (§1, R7). |
| FINDING-001 | YES | YES | Matrix **Option A** only; C17; single Commit Host term per phase; dual path banned. |
| FINDING-004 | YES | YES | §10.3 stages 1–5; crash/winner rules; atomic language constrained. |
| FINDING-021 | YES | YES | Mandatory `subject_generation` on STS + projections; §10.5 discard; T17. |
| FINDING-003 | YES | YES | Option A durability; absolute §10.1 postcondition removed; 3→4 refuse defined. |
| FINDING-016 | YES | **PARTIAL** | Silent best-effort removed; Stage 5 + fail-closed named — **meets letter**. Residual: Stage 5 **after** durable Stage 3; fail-closed does not undo checkpoint / define durable repair (CDR2-F3). EXECUTION_REPORT overclaims full closure. |
| FINDING-008 | YES | YES* | Shared envelope SoT selected; sticky non-substitute; P4 multi-instance gate. *Mechanism of sharing unspecified (CDR2-F4) — norma applied, interface incomplete for ops. |
| FINDING-007 | YES | YES* | Serial lease; singular policy **queue** (FIFO); 429; refuse merge; Race matrix; T14. *Bound value / multi-node lease store unspecified (CDR2-F5). Note: EXECUTION_REPORT label `SERIAL_QUEUE` ≠ Spec token — Spec uses **queue**; not an ACCEPT miss. |
| FINDING-009 | YES | YES | I1–I7 + `MIGRATION_STAGE`; C12/T9 fail-closed. Residual dual naming listed in VC ambiguity #2. |
| FINDING-010 | YES | YES | One named machine; ambiguity #3 = control-flow; i18n deferred. Naming nit: machine `safe_boundary_clear` includes uncontested **no-invent** row (still one decidable machine). |
| FINDING-023 | YES | YES | Single branch refuse→AUDIT→cold→clarify; checksum/schema; corruption vs unexpected shape; T18. |
| FINDING-025 | YES | YES | Process-global degrade; block legacy writers; HTTP 503; UX class; sequential fallback shadow-only; T12. |
| FINDING-012 | YES | YES | Typed DTO; no ellipsis; prior source / equality / fixture canonicalization; P1 exit refs DTO. |
| FINDING-013 | YES | YES | Appendix A total table; soft-FU vs seed ambiguity removed; T16. |
| FINDING-002 | YES | YES | SW-6; §9.1/§9.3/§10; T13 divergence fail. |
| FINDING-014 | YES | **PARTIAL** | Ingress-order path + “separate criteria” + locus-1 demoted from permanent exit — **structure applied**. **Numeric/observable success criteria never published** (CDR2-F2). Greenwash risk remains. |
| FINDING-015 | YES | YES | Runtime guard = hard P4 precondition; §10.6 fail-closed production; P5 retirement-only. Mechanism class (wrapper/proxy/freeze) unnamed — residual 🟡, not ACCEPT miss. |
| FINDING-026 | YES | YES | note_* funnel+guard before P4; §17.1; P5 dead-code only. |
| FINDING-005 | YES | YES | §17.2 matrix P1–P5; drill + checklist defines “rollback proven”. |
| FINDING-019 | YES | YES | T10 golden perception suites; F2 call-site behavioral surface. |
| FINDING-024 | YES | YES | Hard deploy assert; open mirror drift = P4 NO-GO; ambiguity #5 closed. |
| FINDING-027 | YES | YES | VC non-authoritative; Q2 honest closed-list + deferred/out-of-scope; self-grade ≠ implementation gate. |

**Excluded by mandate (correctly not applied):** REJECT-011; DEFER-017; DEFER-018.

**EXECUTION_REPORT_008 cross-check:** Claim “24/24 ACCEPT applied / none left out / no change beyond Plan” is **mostly true** for presence. Claim of clean closure without residual architectural hazard is **overstated** for 014 and 016. No evidence of unauthorized third-host architecture.

---

## 4. Lista de findings remanescentes

### CDR2-F1 — Documento Mestre / Substitution waiver evidence still absent
- **Severity:** 🔴  
- **Evidência:** Spec v1.1 §16.4 / §17 P0 / VC Q4 / ADR-012 retain **INSUFFICIENT EVIDENCE**; repo search under exclusive mission scope finds **no** Documento Mestre Etapa 1 and **no** written waiver (owner, scope, expiry, time-box). AAR-001 Critérios para Liberação item 4 still unmet.  
- **Impacto:** Technical Spec can look “done” while Substitution / implementation authorization remains politically unblockable only by ignoring Audit 001. Governance kill if AAR-002 APPROVES implementation without master/waiver.  
- **Recomendação (register only):** AAR-002 must require master in-repo **or** explicit time-boxed waiver before any STATUS that authorizes implementation/Substitution. Do not treat CDR2/Spec self-text as waiver.

### CDR2-F2 — P2 ingress-order “success criteria” asserted but undefined
- **Severity:** 🟠  
- **Evidência:** FINDING-014 Plan criterion requires ingress-order experiment with **separate success criteria**. Spec §8.7 / §9.2 / §17 P2 / V4 repeat the phrase; **no thresholds, metrics, or pass/fail observables** are specified (unlike T14/T15 style criteria).  
- **Impacto:** P2 can still green-wash cutover readiness — the exact failure mode CDR1 X8 / F-014 attacked.  
- **Recomendação (register only):** Board must treat P2 exit as non-falsifiable until criteria are published in a subsequent Spec revision or binding test appendix. Not inventing criteria here.

### CDR2-F3 — Stage 5 OS/SCG after durable Stage 3: fail-closed ≠ durable coherence
- **Severity:** 🟠  
- **Evidência:** §10.3 UoW boundary A = Stage 3 checkpoint; Stage 5 OS/SCG required afterward; incomplete ⇒ fail-closed + visible incomplete; winner = STS authority; **no** checkpoint undo / compensation transaction defined. §5.1 ASCII still shows Projection/OS-SCG after Commit Gate. sticky_bleed secondary class = locks/anchors OLD with subject NEW.  
- **Impacto:** Production can persist NEW STS, return fail-closed/clarify, and still leave KEEP modules amplifying OLD fixture until retry — durability “success” + side-effect “failure” coexistence.  
- **Recomendação (register only):** Register as open HIGH residual for AAR disposition (repair/undo policy vs consumer-blocking incomplete flag semantics). Do not invent a new store protocol in this CDR.

### CDR2-F4 — “Shared envelope SoT” mandated without sharing contract
- **Severity:** 🟠  
- **Evidência:** §12 still describes `conversation_manager` RAM+SQLite “(shared when multi-instance)” without interface for *how* sharing is achieved; Audit 001 Memory Autoscale miss remains the known failure mode FINDING-008 accepted. Spec correctly gates horizontal scale claims, but does not make the sharing claim implementably falsifiable.  
- **Impacto:** Implementers may claim P4 multi-instance while leaving local SQLite — split-brain returns.  
- **Recomendação (register only):** AAR should treat multi-instance production write as NO-GO until a binding shared-envelope durability interface exists (without this CDR inventing Redis/Postgres/etc.).

### CDR2-F5 — Serial lease: bound and multi-node lease authority unspecified
- **Severity:** 🟠  
- **Evidência:** §8.1 “Bounded wait exceeded → HTTP 429” with **no bound**; C15 acquires/releases lease; no lease-store component for multi-process; DEFER-017 lock hierarchy still out of scope.  
- **Impacto:** Single-node mutex fantasy may pass T14 locally and fail under Autoscale / double-submit across instances.  
- **Recomendação (register only):** Flag as HIGH precondition for any multi-instance write ON claim; keep DEFER-017 visible.

### CDR2-F6 — Runtime sole-writer guard: outcome specified, mechanism class unnamed
- **Severity:** 🟠  
- **Evidência:** §10.6 mandates block + AUDIT + fail-closed when write ON; does not name enforceable surface (ctx proxy, write interceptor, frozen setters, import-time wrap, etc.). CDR1 F-015 attacked test-only theater; schedule is fixed, teeth shape is still soft.  
- **Impacto:** P4 precondition can be “satisfied” with a logging stub.  
- **Recomendação (register only):** AAR should require a named enforceable mechanism in Implementation Plan gates — not Spec invention here.

### CDR2-F7 — §5.1 flow diagram vs §9.1/§10.3 stage nesting (clarity regression)
- **Severity:** 🟡  
- **Evidência:** §5.1 places Projection refresh and OS/SCG as post-Commit-Gate arrows; §9.1 nests Stages 4–5 inside Commit Gate.  
- **Impacto:** Re-teaches pre-v1.1 ordering; implementation drift risk.  
- **Recomendação (register only):** Register diagram inconsistency for Spec errata; no architecture change invented.

### CDR2-F8 — `MIGRATION_STAGE` enum vs legacy flags dual-control surface
- **Severity:** 🟡  
- **Evidência:** §8.8 publishes both I1–I7 on legacy flags and preferred `MIGRATION_STAGE`; VC ambiguity #2 admits naming consolidation later; precedence when enum and flags disagree not fully specified.  
- **Impacto:** Config drift can recreate illegal combinations if only one surface is enforced.  
- **Recomendação (register only):** Keep as residual; illegal matrix fail-closed must win at boot regardless of naming.

### CDR2-F9 — `safe_boundary_clear` name vs uncontested no-invent row
- **Severity:** 🟡  
- **Evidência:** §15.1 machine name implies clear; second production row leaves STS unchanged.  
- **Impacto:** Low — control-flow is decidable; naming hazard for implementers.  
- **Recomendação (register only):** Naming/errata only; do not reopen F-010 fork.

### CDR2-F10 — DEFER-017 lock hierarchy still open
- **Severity:** 🟡  
- **Evidência:** RESOLUTION_MATRIX DEFER-017; Spec VC lists it; serial lease reduces but does not eliminate envelope↔checkpointer deadlock surface.  
- **Impacto:** Stuck sessions under load (latent).  
- **Recomendação (register only):** Remain deferred; do not silently treat as closed by lease text.

### CDR2-F11 — DEFER-018 projection fanout budget still open
- **Severity:** 🟡  
- **Evidência:** RESOLUTION_MATRIX DEFER-018; Spec VC lists it; no dirty-set/latency budget.  
- **Impacto:** p99 / write amplification — credibility-secondary.  
- **Recomendação (register only):** Remain deferred post-v1.1.

### CDR2-F12 — C7 vs C8 projection-trigger ownership overlap (known REJECT-011 boundary)
- **Severity:** 🟢  
- **Evidência:** C7 “Refresh projections under durability boundary”; C8 owns Projection Layer; REJECT-011 upheld.  
- **Impacto:** Implementation blob risk if unchecked — not a Spec decidability blocker beyond Board’s prior REJECT.  
- **Recomendação (register only):** No forced refactor; watch in Implementation Plan.

---

## 5. Lista de blockers remanescentes

### Critical (🔴) — block implementation / Substitution authorization

| ID | Blocker | Status vs Spec text |
|----|---------|---------------------|
| CDR2-F1 | Documento Mestre Etapa 1 **or** written Substitution waiver (owner, scope, expiry, time-box) | Spec correctly gates; **evidence missing** |

**Spec-text CRITICAL contradictions from CDR1 BLOCKER set (001–007, 009, 015, 026):** **none remain open as undecidable Spec contracts.** They are closed or (016/014) residualized at HIGH incompleteness — not re-opened as dual-architecture forks.

### High (🟠) — block confident P2 exit / P4 multi-node / side-effect credibility if ignored

| ID | Blocker |
|----|---------|
| CDR2-F2 | P2 ingress-order success criteria unpublished |
| CDR2-F3 | Stage-5 OS/SCG vs durable Stage-3 coherence |
| CDR2-F4 | Shared envelope SoT without sharing interface |
| CDR2-F5 | Lease bound + multi-node lease authority |
| CDR2-F6 | Runtime guard mechanism class unnamed |

### Not blockers for Spec v1.1 entry (tracked)

- DEFER-017, DEFER-018 (CDR2-F10/F11)  
- Diagram/naming/overlap nits (CDR2-F7/F8/F9/F12)

---

## 6. Recomendação técnica

1. **Treat Spec 004 v1.1 as the sole technical defendant for AAR-002** — v1.0 is historical; do not implement from v1.0.  
2. **Do not authorize implementation code** on the basis of EXECUTION_REPORT_008 alone; this CDR2 finds **2 PARTIAL ACCEPT applications** and **1 governance evidence gap**.  
3. **Disposition path (register only):** AAR-002 should either (a) **NOT APPROVED** pending master/waiver + HIGH residual disposition, or (b) **conditional** posture that explicitly enumerates residuals as NO-GO for P2 exit / multi-instance P4 — Board choice; this CDR2 recommends (a) for implementation authorization.  
4. **Do not invent** lock products, envelope stores, or OS/SCG 2PC in Spec under CDR2 authority — problems registered only.  
5. **Next process step:** AAR-002 only (human/Board). No Implementation Plan until AAR liberação criteria met.

**Architecture consistency (narrow):** Phase host model, durability Option A, epoch freshness, sole-writer schedule, message authority, illegal flags, and Validation Contract authority are **internally consistent enough** to be judged. Residual HIGH items are **coherence/completeness** faults, not a return to v1.0 dual-orchestration contradiction.

---

## 7. Parecer para o AAR-002

| Question | Objective answer |
|----------|------------------|
| Critical blockers remain? | **YES — governance evidence (CDR2-F1).** Spec-text CRITICAL forks from CDR1: **NO.** |
| High blockers that block implementation? | **YES** for multi-instance P4 / unfalsifiable P2 / OS-SCG durable window / guard teeth (CDR2-F2…F6), if Board equates “implementation” with production-write readiness. Single-node shadow/funnel design work remains gated by AAR liberação rules. |
| Architecture consistent? | **Mostly YES** at contract level; **not fully** at Stage-5/envelope/lease/P2-criteria completeness. |
| Ready for AAR-002? | **YES to convene / submit for judgment.** |

### Binding parecer

Because **critical governance blocker CDR2-F1 remains** (Documento Mestre / waiver evidence absent), and **HIGH residuals CDR2-F2…F6** still threaten credibility gates, this Board recommends that **AAR-002 stay NOT APPROVED** for implementation and Substitution authorization.

Spec 004 v1.1 is nonetheless **apta a ser submetida ao AAR-002** as the revised technical package for that final Board decision. **This CDR2 does not issue AAR-002** and does not authorize an Implementation Plan.

```
STATUS RECOMMENDATION FOR AAR-002:
NOT APPROVED (implementation / Substitution)

SPEC v1.1 SUBMISSION:
APTA FOR AAR-002 JUDGMENT

IMPLEMENTATION:
STILL BLOCKED
```

---

## Validation Contract (CDR2)

| Check | Result |
|-------|--------|
| 24 ACCEPT verified against Spec text (not blind trust of EXECUTION_REPORT)? | **YES** — 24 present; 22 fully correct; 2 partial (014, 016) |
| Any new architectural requirements invented as “must add to Spec”? | **NO** — residuals registered only; DEFER-017/018 not reopened as ACCEPT |
| Any exclusive-input documents modified? | **NO** |
| Output restricted to `observations/aurora_context_manager_cdr2_009/CDR2.md`? | **YES** |
| AAR-002 started / issued? | **NO** |
| Code / commits? | **NONE** |

```
FACT:
CDR2-009 hostile review of Spec 004 v1.1 complete.
24/24 ACCEPT present; 22/24 fully correct; 2/24 partial (014, 016).
Spec-text CDR1 CRITICAL forks closed; governance master/waiver evidence still absent.
HIGH residuals: P2 criteria, Stage-5/OS coherence, shared envelope mechanism,
lease multi-node/bound, runtime guard mechanism class.
Recommend AAR-002 NOT APPROVED for implementation; package apta for AAR-002 judgment.
Only CDR2.md written. No AAR-002. No commit.
```
