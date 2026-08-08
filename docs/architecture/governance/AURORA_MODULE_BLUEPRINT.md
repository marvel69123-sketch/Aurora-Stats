# Aurora Module Blueprint

**DOCUMENT ID:** AURORA-MODULE-BLUEPRINT  
**VERSION:** 2026.08.07  
**STATUS:** OFFICIAL  
**CLASS:** Architecture Execution Law (AEL) — reusable module reconstruction model  
**SSOT ROOT:** `docs/architecture/`  
**AUTHORITY PATH:** `docs/architecture/governance/AURORA_MODULE_BLUEPRINT.md`  
**SOURCE CYCLE:** Context Manager AEL (Spec 004 → Plan 014 → Mission 016 → Final Acceptance 017)  
**COMPANION:** `observations/aurora_context_manager_final_acceptance_017/LESSONS_LEARNED_CONTEXT_MANAGER.md`

---

## 0. Purpose and non-goals

This Blueprint is the **standard operating model** for reconstructing any Aurora Core module (Execution Manager, Tool Use, Orchestration, and successors). It converts the completed Context Manager AEL cycle into a reusable process — **not** a product architecture for any specific module.

| This document IS | This document is NOT |
|------------------|----------------------|
| Process / governance blueprint | A new Spec, CDR, AAR, or Master rewrite |
| Reusable checklist + gate model | Authorization to start Execution Manager |
| Consolidation of proven AEL practices | An architecture change to Context Manager |
| Indexable under `docs/architecture/governance/` | A Substitution waiver |

**Hard rule:** Publishing this Blueprint does **not** reopen architecture, edit the Master Document, mutate SSOT pillars, or start the next module. Next module starts only on **explicit Product Owner instruction**.

**Reference chain (read-only; do not modify as part of using this Blueprint):**

| Artifact class | Example (CM journey) |
|----------------|----------------------|
| Research | `observations/aurora_context_manager_research_003/` |
| Spec → CDR → AAR | Spec 004 · CDR · AAR-003 APPROVED |
| Implementation Plan | Plan 014 |
| Readiness / PO auth | 015 / 015B / 015C |
| Controlled implementation | Mission 016 Phases 1–6 + PGR-01..06 |
| Final Acceptance + Lessons | Mission 017 |
| Dual Reporting | `DUAL_REPORTING_POLICY.md` (REGRA 29) |
| SSOT | `SSOT_POLICY.md` + Master |

---

## 1. Pré-requisitos — before starting any module

Do **not** open Research-as-implementation or write product code until the following are true or explicitly waived with owner/scope/expiry.

### 1.1 Institutional prerequisites

| # | Prerequisite | Evidence |
|---|--------------|----------|
| P1 | SSOT root exists and is cited | `docs/architecture/` + `README.md` |
| P2 | Documento Mestre exists | `docs/architecture/master-architecture.md` |
| P3 | SSOT Policy known | `governance/SSOT_POLICY.md` |
| P4 | Frozen registry respected | `docs/FROZEN_MODULES.md` — do not edit Frozen engines/modules without governed approval |
| P5 | Code / deploy SoT declared | Typically `artifacts/aurora/` (runtime SoT ≠ architecture Master) |
| P6 | Dual Reporting policy known | REGRA 29 — `DUAL_REPORTING_POLICY.md` |

### 1.2 Module-track prerequisites (before Implementation)

| # | Prerequisite | Evidence |
|---|--------------|----------|
| M1 | Research package complete enough to write Spec | Research REPORT under `observations/` |
| M2 | Spec versioned under `observations/` | Spec package (vN) |
| M3 | Hostile review closed for Critical forks | CDR chain; Critical/High = 0 or dispositioned |
| M4 | Architecture liberação APPROVED | AAR STATUS **APPROVED** (not NOT APPROVED) |
| M5 | Implementation Plan drafted after AAR APPROVED | Plan package (Plan 014 pattern) |
| M6 | Plan Git-versioned on governed branch | Uncommitted draft ≠ executable authority |
| M7 | Product Owner formal authorization | PO Approval artifact (015B pattern) |
| M8 | Readiness Review READY | Readiness / Final Readiness (015 / 015C pattern) |
| M9 | Feature flags / write paths default **OFF** | Documented in Plan Go/No-Go |
| M10 | Cross-tree / mirror hygiene dispositioned **or** recorded as Activation residual from day one | Prefer close early; if OPEN, label as Activation precondition (not silent debt) |

### 1.3 Forbidden shortcuts

- AAR APPROVED → code (skip Plan / PO / Readiness)  
- Plan draft → code (skip Git versioning + PO auth)  
- “Almost READY” → first merge with production write ON  
- Inventing residual closures (e.g. claiming mirror drift RESOLVED without evidence)  
- Auto-starting the next module after Final Acceptance  

### 1.4 Vocabulary split (mandatory)

| Term | Meaning |
|------|---------|
| **Module FROZEN** | AEL implementation cycle complete; Stabilization trusts gated/defaults-OFF SoT use; Final Acceptance APPROVED |
| **Activation FROZEN / authorized** | Definitive full-env cut-over authorized after Activation preconditions (e.g. mirror parity) are closed |
| **Implementation complete ≠ Activation license** | Never conflate the two in plans or acceptance |

Bake this split into every Implementation Plan Go/No-Go table.

---

## 2. Pesquisa — how to conduct Research

### 2.1 Goal

Produce an evidence package that answers: *what exists, what hurts, what must not break, what is Frozen, what is in/out of scope* — without designing Substitution as a fait accompli.

### 2.2 Method

1. **Locate SoTs** — architecture SSOT (`docs/architecture/`), code SoT (`artifacts/aurora/` or declared path), freeze registries.  
2. **Inventory reality** — current writers, flags, adapters, tests, deploy trees, known findings.  
3. **Map risks** — user-visible regressions, dual-SoT / mirror drift, Frozen module boundaries.  
4. **Defer architecture forks** — Research may surface forks; it does **not** settle them (CDR/AAR do).  
5. **Publish under `observations/`** — Research REPORT is a working paper, not Master.  
6. **Close with Dual Reporting** — Engineering evidence + Product Owner visual template (REGRA 29).  

### 2.3 Research exit criteria

| Criterion | Pass when |
|-----------|-----------|
| Scope clarity | In/out of scope stated; Frozen modules listed as untouchable internals |
| Evidence trail | Paths, findings IDs, and open residuals named honestly |
| No fake authority | Research does not claim Substitution authorization |
| Handoff | Enough material for Spec drafting without guessing Critical forks away |

---

## 3. Auditoria — AEAP Level 1 / 2 / 3

**AEAP** = Aurora Architecture Execution Audit Practice. Audits are **budgeted** and proportional. Global audit sprawl is forbidden by default during Controlled Implementation.

### 3.1 When to use each level

| Level | Use when | Scope | Forbidden |
|-------|----------|-------|-----------|
| **LEVEL 1** | Default for every implementation phase / PGR gate / Stabilization delta | New + modified files in the delta + **direct** dependencies only | Global repo audit; reopening settled Spec/Master |
| **LEVEL 2** | Material cross-cutting risk, multi-tree deploy claim, or Board-requested depth after LEVEL 1 findings | Delta + selected adjacent surfaces with written budget (X/Y/Z/N) | Silent expansion beyond budget; using L2 to reopen architecture |
| **LEVEL 3** | Hostile / liberação-class events (major Spec revision, CDR reopen, Substitution readiness crisis) | Explicit Board-scoped audit mission | Treating L3 as routine phase close; starting L3 without PO/Board ask |

### 3.2 LEVEL 1 operating pattern (default)

Record in every phase/gate completion report:

```text
AUDIT BUDGET
Nível escolhido: LEVEL 1
Arquivos novos: N
Arquivos modificados: M
Dependências diretas: D
Arquivos reaproveitados: R
Auditorias reaproveitadas: (CDR / AAR / prior phase IDs)
```

**Reuse prior hostile reviews** (CDR/AAR) — do not re-litigate settled Critical forks under LEVEL 1.

### 3.3 Escalation

Escalate LEVEL only with a written reason in the mission report. Escalation ≠ architecture reopen. Architecture reopen requires a governed Spec/CDR/AAR mission under REGRA 19.

---

## 4. Arquitetura — Spec → CDR → AAR → Revision → Readiness

Govern **hard before coding**. Architecture must be settled before Implementation Planning and before first product code.

```text
Research
   → Spec (vN under observations/)
   → CDR (hostile review)
   → AAR (Board liberação)
        ├─ NOT APPROVED → freeze product mutation; revision plan / residual plan
        └─ APPROVED → Implementation Plan (planning only)
   → Revision cycles as needed (Spec vN+1 / CDR2 / AAR-00N) until Critical = 0
   → Readiness Review (may be NOT READY)
   → PO Approval + Final Readiness READY
   → Implementation (Mission N) — still defaults OFF
```

### 4.1 Spec

- Specialization contract under `observations/` — **not** a Master substitute.  
- States ADRs / decisions, invariants, out-of-scope, Frozen boundaries, Activation preconditions.  
- Spec self-text is **never** a Substitution waiver (SSOT Policy).

### 4.2 CDR (hostile review)

- Attacks forks, ambiguity, and “planning with unresolved Criticals.”  
- Critical/High must be dispositioned before claiming architecture ready for planning/code.  
- Multiple CDR rounds are normal (CDR → CDR2 → CDR3 pattern).

### 4.3 AAR

- Board liberação record.  
- **NOT APPROVED** ⇒ freeze-while-NOT-APPROVED: no implementation execution, no production write flags.  
- **APPROVED** unlocks **Implementation Planning**, not automatic code.

### 4.4 Revision

- Residual Blocker Plans and Spec revisions close evidence gaps.  
- Prefer honesty: OPEN residuals with classification (architecture vs Activation vs docs hygiene).

### 4.5 Readiness (Phase B governance)

Status locks that actually block:

1. Plan approved (human Board / Release Manager as required by track).  
2. Plan **Git-versioned**.  
3. **Product Owner** formal authorization to execute.  
4. Readiness Review **READY** (or explicit time-boxed waiver).  

**After PO approval:** flip plan status-lock prose in a tiny docs-hygiene commit so historical “DRAFT / PENDING” does not confuse later agents (lesson from Plan 014).

---

## 5. Implementação — Deployment Ladder

**Concept — Deployment Ladder:** a single-deploy, flag-gated climb from invisible work to progressive activation — never a big-bang cut-over. Canonical progressive percentages:

```text
0% → 1% → 5% → 10% → 25% → 50% → 100%
```

(Exact flag names are module-specific; the **ladder shape and gate discipline** are mandatory.)

### 5.1 Phase model (reuse everywhere)

| Phase | Name | Intent | User impact at default |
|-------|------|--------|------------------------|
| **1** | Preparation | Harness, flags OFF, probes, baselines, residual labeling | None |
| **2** | Infrastructure | Contracts, controllers, illegal matrix scaffolding, tests | None |
| **3** | Shadow | Observe-only / student mode; fail-open shadow; no production subject write | None |
| **4** | Sole Writer | Single official write funnel behind flags; legacy may remain until dedicated retirement | None at default OFF |
| **5** | Gated Activation | PGR ladder only; **One Gate, One Decision** | None at default OFF/0% |
| **6** | Stabilization | Trust question for gated/defaults-OFF SoT — **not** definitive Activation | None |
| **FA** | Final Acceptance | APPROVED / FROZEN for module AEL cycle; Activation residuals explicit | N/A (docs) |

### 5.2 Controlled Implementation (REGRA 19)

During Phases 1–6:

- **No** unauthorized architecture reopen  
- **No** ADR / Master Document edits unless a separate governed mission says so  
- Out-of-scope discovery → **STOP** and report; do not “just fix” Frozen engines  
- Prefer AEAP LEVEL 1 budgets per phase/gate  

### 5.3 Zero User Impact (REGRA 23)

- Defaults **OFF** / **0%** in repo and normal environments  
- Operator must **explicitly arm** a gate  
- Instant rollback helpers to OFF/0%  
- Shadow isolation preserved while climbing  

### 5.4 Progressive Activation + PGR (REGRAS 24–25)

- Each percentage raise is an **independent mission/gate** (PGR-01..06 pattern).  
- Do not bundle PGR-N with PGR-N+1, Stabilization, or Activation.  
- Higher stages **fail-closed** until unlocked.  
- Auto-advance = **False**.  

### 5.5 Deployment Window (REGRA 26)

Even in test-only environments: observation/validation posture, measurable window, recorded evidence — not “ship and forget.”

### 5.6 One Gate, One Decision (REGRA 27)

One commit / mission answers **one** gate decision. Example: PGR-04 (25%) contains **only** PGR-04 — nothing for 50%, nothing for Phase 6.

### 5.7 Plateau Validation (REGRA 28)

Prior gate must be stable (and PO-approved as required) before the next raise. No skipping plateaus because “tests are green locally.”

### 5.8 Operational AEL prompt pattern (CONTINUE)

Prefer **short CONTINUE prompts** between gates:

```text
CONTINUE — <MODULE> Mission <ID> — <Phase or PGR-XX only>
- One Gate, One Decision: ONLY this gate
- Defaults OFF; AEAP LEVEL 1; Dual Reporting at close
- Do NOT start next gate / next module
- Await PO after completion
```

Long Prompt Mestre packages remain for mission opens; **CONTINUE** keeps agents from bundling the ladder.

### 5.9 Mirror-drift / deploy hygiene as Activation precondition

If a secondary tree (e.g. `aurora/` mirror) drifts from deploy SoT (`artifacts/aurora/`):

- Treat as **Activation NO-GO** while OPEN  
- Do **not** invent RESOLVED  
- May still FROZEN the **implementation** cycle if honesty is documented (CM 017 pattern)  
- Prefer closing or formally waiving in Prep — do not surprise Final Acceptance  

### 5.10 Legacy retirement

Pre-declare in the Plan whether “implementation FROZEN” may leave legacy paths present until a dedicated Activation / P5-class mission. Do not force legacy deletion inside Stabilization.

### 5.11 Final Acceptance

Artifact-only review against architecture + plan + phase/PGR reports + Stabilization trust + residual honesty. Outputs:

- Final Acceptance record  
- Lessons Learned (module-specific)  
- Dual Reporting  
- Explicit **await PO** — no auto-start next module  

---

## 6. Governança

### 6.1 SSOT

- Architecture truth: `docs/architecture/`  
- Working papers: `observations/**` until promoted  
- Spec ≠ Master ≠ Substitution waiver  

### 6.2 Documento Mestre

- `master-architecture.md` is the Core pillars/policies home.  
- Module Specs specialize; they do not replace Master.  
- Blueprint / Dual Reporting live under **governance/** without requiring Master pillar rewrites.

### 6.3 Rules 19–29 (binding process law)

| Rule | Name | One-line obligation |
|------|------|---------------------|
| **19** | Controlled Implementation | No unauthorized architecture reopen during code phases |
| **23** | Zero User Impact | Defaults OFF; user-invisible until explicit arming |
| **24** | Progressive Activation | Climb the percentage ladder; no big-bang |
| **25** | Progressive Gate Review (PGR) | Each raise is an independent reviewable gate |
| **26** | Deployment Window | Observe/validate in a defined window |
| **27** | One Gate, One Decision | Never bundle gates or sneak Stabilization into a PGR |
| **28** | Plateau Validation | Prior gate stable before next raise |
| **29** | Dual Reporting | Engineering Report + Product Owner Report every mission close |

Canonical Dual Reporting policy: [`DUAL_REPORTING_POLICY.md`](./DUAL_REPORTING_POLICY.md).

### 6.4 Dual Reporting (REGRA 29) — minimum

Every mission ends with **two independent reports**:

1. **Engineering Report** — evidence, hashes, flags, rollback, AEAP budget, residuals  
2. **Product Owner Report** — lay language, official visual template + progress bar  

```text
📋 PRODUCT OWNER REPORT
✅ O que fizemos hoje
🧠 O que isso significa
👤 O usuário percebe diferença?
⚠️ Existe algum risco?
🎯 O que ainda falta?
📊 Quanto falta?
🏗️ Analogia simples
📝 Resumo em uma frase
```

### 6.5 PAR / PGR / Final Acceptance (see §7)

Phase Acceptance Reviews (PAR) close phases; Progressive Gate Reviews (PGR) close activation steps; Final Acceptance freezes the module AEL cycle.

### 6.6 Await PO (standing rule)

Confirm in every phase/gate close: **await Product Owner; no Execution Manager / next-module auto-start.**

---

## 7. Gates — PAR, PGR, Final Acceptance

### 7.1 PAR — Phase Acceptance Review

| Item | Definition |
|------|------------|
| **What** | Accept that a **phase** (Prep, Infra, Shadow, Sole Writer, Stabilization) met its contract |
| **When** | End of Phases 1–4 and 6 (and analogous phases on future modules) |
| **Produces** | Completion report + Dual Reporting; unlocks **only** the next authorized phase |
| **Does not** | Authorize skipping PGR discipline or definitive Activation |

Pattern IDs (CM): PAR-01..PAR-04 for Phases 1–4; Stabilization has its own completion + Final Acceptance.

### 7.2 PGR — Progressive Gate Review

| Item | Definition |
|------|------------|
| **What** | Accept a **single** activation percentage step |
| **When** | Phase 5 ladder: 1 → 5 → 10 → 25 → 50 → 100 |
| **Produces** | Gate-only completion report; PO approval before next raise |
| **Does not** | Bundle multiple percentages; start Stabilization; flip definitive full-env write by default |

**One Gate, One Decision** is the PGR constitution.

### 7.3 Final Acceptance

| Item | Definition |
|------|------------|
| **What** | Board/QA/Release review that the **module AEL cycle** may be APPROVED / FROZEN |
| **When** | After Stabilization SUCCESS and complete evidence chain |
| **Produces** | Final Acceptance + Lessons Learned + Dual Reporting |
| **May FROZEN while** | Activation residuals remain OPEN **if** classified correctly (e.g. mirror drift = Activation precondition) |
| **Must not** | Invent residual closures; auto-start next module; conflate Module FROZEN with Activation license |

---

## 8. Critérios para Frozen

A module **may** be declared **FROZEN** when **all** of the following hold:

| # | Criterion |
|---|-----------|
| F1 | Spec architecturally APPROVED (AAR) and cited Plan exists |
| F2 | PO authorization + Readiness READY (or governed waiver) preceded code |
| F3 | Phases 1–4 complete with PAR-style acceptance evidence |
| F4 | PGR ladder complete for the planned gated activation **implementation** (defaults still OFF/0% in repo unless operator-armed) |
| F5 | Stabilization SUCCESS for **gated / defaults-OFF** trust |
| F6 | Shadow / Sole Writer / Rollback / Flags OFF / Observability validated per plan |
| F7 | AEAP discipline recorded; REGRA 19 and 23–29 complied with |
| F8 | Residuals honestly classified (architecture vs Activation vs docs hygiene) — no invented RESOLVED |
| F9 | Final Acceptance APPROVED with explicit Module FROZEN vs Activation split |
| F10 | Dual Reporting present on Final Acceptance |
| F11 | Next module **not** started; await PO recorded |

**Not required for Module FROZEN (unless the Plan says otherwise):**

- Definitive full-env Activation ON  
- Mirror drift RESOLVED (if documented as Activation residual)  
- Legacy writer retirement completed  

**Forbidden:** Declaring FROZEN while Critical architecture residuals are hidden, Stabilization failed, or defaults are ON without Activation authorization.

---

## 9. Lições Aprendidas — from Context Manager

Consolidated from `LESSONS_LEARNED_CONTEXT_MANAGER.md` and the CM journey (003→017). Apply to **every** future module.

### 9.1 What worked (keep)

1. **Hostile review ladder before code** — CDR→AAR prevented planning with unresolved Critical forks.  
2. **Status locks that block** — Plan lock + NOT READY until PO + Final Readiness.  
3. **One Gate, One Decision** — PGR-01..06 as independent missions.  
4. **Stabilization as its own phase** — separates “built” from “trusted gated” from “Activation authorized.”  
5. **Honest residual tracking** — OPEN mirror drift without false closure.  
6. **Dual Reporting** — engineering + PO visual template.  
7. **AEAP LEVEL 1 discipline** — local budgets, no global thrash.  
8. **Deploy SoT clarity** — `artifacts/aurora/` as code SoT; mirror non-parity = Activation precondition.  

### 9.2 What to do differently (improve)

1. Close or formally waive mirror/deploy hygiene **early** (Prep), or label Activation residual from day one.  
2. Flip plan status-lock prose right after PO approval (docs hygiene).  
3. Keep Rules 19–29 discoverable via governance index (this Blueprint + Dual Reporting).  
4. Separate **Module FROZEN** vs **Activation** vocabulary in the Plan template.  
5. Pre-declare legacy retirement off-ramp.  
6. Mechanically **await PO** — never auto-chain the next module.  

### 9.3 One-line Board memory

> **Govern hard before coding; raise activation one gate at a time; freeze the module when Stabilization trusts defaults-OFF; never invent residual closures; never auto-start the next brain.**

### 9.4 Attention points for the next module (e.g. Execution Manager)

When PO authorizes a new module, inherit:

- Defaults OFF / rollback culture / PGR ladder  
- Consume frozen interfaces; do not reopen prior Sole Writer / Shadow contracts casually  
- Respect Frozen engines registry  
- Plan + Git + PO + Readiness before code  
- AEAP LEVEL 1 per phase; Dual Report every close  
- Track cross-tree drift from day 0  
- **Do not** treat a prior module’s FROZEN as Activation license for that module or a start order for the next  

---

## 10. Checklist Oficial — reusable for any module

Copy this checklist into the module’s tracking observation folder. Mark PASS / FAIL / N/A with evidence paths.

### A. Institutional

- [ ] A1 SSOT `docs/architecture/` cited  
- [ ] A2 Documento Mestre cited  
- [ ] A3 SSOT Policy + Dual Reporting Policy known  
- [ ] A4 Frozen registry checked; out-of-scope internals listed  
- [ ] A5 Code/deploy SoT declared; mirror posture labeled  

### B. Research & Architecture

- [ ] B1 Research REPORT published under `observations/`  
- [ ] B2 Spec vN published  
- [ ] B3 CDR hostile review; Critical/High dispositioned  
- [ ] B4 AAR **APPROVED** (not NOT APPROVED)  
- [ ] B5 Revision/residual plans closed or explicitly carried with classification  

### C. Planning & Unlock

- [ ] C1 Implementation Plan (014 pattern) after AAR APPROVED  
- [ ] C2 Plan Git-versioned  
- [ ] C3 PO formal authorization  
- [ ] C4 Readiness READY (or waiver)  
- [ ] C5 Status-lock prose updated after approval  
- [ ] C6 Go/No-Go table splits Module FROZEN vs Activation  
- [ ] C7 Defaults OFF / illegal matrix / rollback called out  

### D. Implementation ladder

- [ ] D1 Phase 1 Prep complete (+ PAR)  
- [ ] D2 Phase 2 Infra complete (+ PAR)  
- [ ] D3 Phase 3 Shadow complete (+ PAR)  
- [ ] D4 Phase 4 Sole Writer complete (+ PAR)  
- [ ] D5 PGR-01 (1%) only — PO before next  
- [ ] D6 PGR-02 (5%) only — PO before next  
- [ ] D7 PGR-03 (10%) only — PO before next  
- [ ] D8 PGR-04 (25%) only — PO before next  
- [ ] D9 PGR-05 (50%) only — PO before next  
- [ ] D10 PGR-06 (100%) only — PO before Stabilization  
- [ ] D11 Phase 6 Stabilization SUCCESS (gated trust)  
- [ ] D12 Each phase/gate: AEAP LEVEL 1 budget + Dual Reporting  
- [ ] D13 CONTINUE prompts used; no gate bundling  

### E. Operations posture at freeze candidate

- [ ] E1 Feature flags default OFF  
- [ ] E2 Shadow intact  
- [ ] E3 Sole Writer consistent when armed  
- [ ] E4 Rollback validated to OFF/0%  
- [ ] E5 Observability sufficient  
- [ ] E6 Activation residuals honest (e.g. mirror OPEN = NO-GO for full-env)  

### F. Final Acceptance & Frozen

- [ ] F1 Final Acceptance APPROVED  
- [ ] F2 Module status **FROZEN** with scope text  
- [ ] F3 Activation **not** silently authorized  
- [ ] F4 Lessons Learned published  
- [ ] F5 Dual Reporting (Eng + PO visual template + progress bar)  
- [ ] F6 Await PO — next module **NOT STARTED**  

### G. Compliance matrix

- [ ] G1 REGRA 19 Controlled Implementation  
- [ ] G2 REGRA 23 Zero User Impact  
- [ ] G3 REGRA 24 Progressive Activation  
- [ ] G4 REGRA 25 PGR  
- [ ] G5 REGRA 26 Deployment Window  
- [ ] G6 REGRA 27 One Gate, One Decision  
- [ ] G7 REGRA 28 Plateau Validation  
- [ ] G8 REGRA 29 Dual Reporting  

---

## 11. Prompt fragments (copy pack)

### 11.1 Mission open (abbrev)

```text
# AURORA MODULE — <NAME> — Mission <ID>
Follow docs/architecture/governance/AURORA_MODULE_BLUEPRINT.md
SSOT: docs/architecture/ | Code SoT: artifacts/aurora/ (or declared)
REGRA 19, 23–29 mandatory | AEAP LEVEL 1 default
Defaults OFF | One Gate One Decision | Await PO | No next-module auto-start
Include Dual Reporting Prompt Mestre block (REGRA 29)
```

### 11.2 CONTINUE (gate)

```text
CONTINUE — ONLY <PGR-XX | Phase N> — no other gate
Defaults OFF | AEAP LEVEL 1 | Dual Reporting at close | Await PO
```

### 11.3 Phase close footer (required claims)

```text
Nenhuma alteração de código: SIM|NÃO
Architecture / Master / ADR touched: NO (unless authorized mission)
Next gate started: NO
Next module started: NO
Await: Product Owner
```

---

## 12. Compatibility and maintenance

| Topic | Rule |
|-------|------|
| Master Architecture | **Not** rewritten by this Blueprint alone |
| Context Manager product code | **Untouched** — CM is FROZEN |
| Future SSOT hygiene | May add a one-line Master pointer to this Blueprint without reopening pillars |
| Conflicts | If a module Spec conflicts with this process law, stop and escalate — do not silently drop gates |

### Changelog

| Version | Date | Change |
|---------|------|--------|
| 2026.08.07 | 2026-08-07 | Initial official Aurora Module Blueprint from CM AEL cycle (Mission 018) |
| 2026.08.07.1 | 2026-08-07 | Pointer to post-FROZEN AEL Production Extension (Mission 046) — no Spec/Master rewrite |

---

## 11. Post-FROZEN lifecycle (pointer)

Module FROZEN ends the **implementation** AEL cycle defined above. Live entry continues under a separate governance addendum — **not** a reopen of module Specs or Master pillars:

```text
Module FROZEN → Production Rollout → Production Accepted
```

**Canonical addendum:** [`AEL_PRODUCTION_EXTENSION_ADDENDUM.md`](./AEL_PRODUCTION_EXTENSION_ADDENDUM.md)  
**Strategy package (working paper):** `observations/aurora_production_rollout_046/`

Publishing or citing this pointer does **not** arm feature flags, start Production Rollout, or authorize the next module.

---

**End of Aurora Module Blueprint.**  
**Next module / live rollout:** only on explicit Product Owner instruction.
