# AEL Policy — REGRA Nº 29 — Dual Reporting

**DOCUMENT ID:** AURORA-AEL-REGRA-29-DUAL-REPORTING  
**VERSION:** 2026.08.07  
**STATUS:** OFFICIAL  
**CLASS:** Architecture Execution Law (AEL) — permanent process policy  
**SSOT ROOT:** `docs/architecture/`  
**AUTHORITY PATH:** `docs/architecture/governance/DUAL_REPORTING_POLICY.md`

---

## 1. Purpose

Institutionalize a permanent reporting obligation: every Aurora mission **must** end with **two independent reports** — one for engineering evidence and one for Product Owner understanding — so that technical closure and product comprehension never collapse into a single audience-mixed artifact.

This rule does **not** change architecture, SSOT, AEAP, or Rules 19 / 23–28. It adds a mandatory **reporting dual** at mission close.

---

## 2. Statement of the rule (REGRA Nº 29)

**Every mission MUST end with two independent reports:**

| Report | Audience | Nature |
|--------|----------|--------|
| **Report 1 — ENGINEERING REPORT** | Engineering / Board technical reviewers | Technical pattern: evidence, hashes, flags, rollback, architecture notes, validations |
| **Report 2 — PRODUCT OWNER REPORT** | Product Owner / non-technical stakeholders | Lay language only; fixed eight-section template; **no jargon**; **no implementation detail** |

The two reports are **independent**: neither may replace the other. A mission is **incomplete** if either report is missing, merged into a single mixed narrative, or if Report 2 contains engineering jargon / implementation detail.

---

## 3. Report 1 — ENGINEERING REPORT (required content)

Report 1 follows the **current technical observation / completion pattern** already used in Aurora missions. At minimum it must cover, when applicable:

| Area | Expected content |
|------|------------------|
| Identity | Mission ID, branch, commit message(s), commit hash(es) |
| Scope | What was in / out of scope; gate ID if gated (e.g. PGR-XX) |
| Evidence | Tests run, results, flags/env vars, artifacts paths |
| Architecture / governance | ADRs touched or explicitly untouched; Master / Spec citations |
| Safety | Rollback path, fail-safe defaults, shadow / sole-writer posture |
| Validations | Checklists, AEAP budget used, Rule compliance matrix |
| Residual | Open items, blockers, next gate (without executing it) |

Report 1 **may** use technical vocabulary (AEAP, SSOT, hashes, pytest, feature flags, etc.).

---

## 4. Report 2 — PRODUCT OWNER REPORT (mandatory template)

Report 2 **always** uses this fixed structure, in this order, with these exact section titles:

1. **O que fizemos hoje?**  
2. **O que isso significa em linguagem simples?**  
3. **O usuário percebe alguma diferença?**  
4. **Existe algum risco?**  
5. **O que ainda falta?**  
6. **Quanto falta para terminar?**  
7. **Analogia simples.**  
8. **Resumo em uma frase.**

### 4.1 Hard constraints for Report 2

- Lay language only.  
- **No** implementation detail (no file paths as the story, no code diffs, no test counts as the main narrative, no flag names unless the PO already uses them as product labels).  
- **No** unexplained jargon. If a governed term must appear, explain it with a simple analogy (see §5).  
- Same facts as Report 1, translated — not a different reality.

---

## 5. Lay analogies (canonical examples)

Use these (or equally simple equivalents) when explaining recurring Aurora concepts to the Product Owner:

| Term | Lay analogy |
|------|-------------|
| **Shadow Mode** | Aluno que acompanha o professor mas ainda não responde sozinho |
| **Rollback** | Voltar rapidamente ao estado anterior |
| **AEAP Local Audit** | Revisar só a sala onde houve mudanças |
| **Sole Writer** | Uma pessoa responsável por registrar decisões oficiais |
| **Plateau Validation** | Confirmar que o novo cérebro está preparado antes de mais responsabilidade |

---

## 6. Applicability

REGRA Nº 29 applies to **all** Aurora missions from institutionalization onward, including but not limited to:

- Context Manager  
- Execution Manager  
- Tool Use  
- Orchestration  
- **All future modules**

No module, phase, or gate is exempt unless the Board issues an explicit, time-boxed written waiver citing this document.

---

## 7. Compatibility (non-alteration clause)

This policy **coexists** with and **does not alter**:

| Artifact / rule | Relationship |
|-----------------|--------------|
| **SSOT** (`docs/architecture/`, `SSOT_POLICY.md`, Master) | Unchanged; Dual Reporting is process law under governance |
| **AEAP** | Unchanged; Report 1 may record AEAP budget; Report 2 must not require AEAP jargon |
| **REGRA Nº 19** (controlled implementation / no unauthorized architecture reopen) | Unchanged |
| **REGRAS Nº 23–28** (Zero User Impact, Progressive Activation, PGR, Deployment Window, One Gate One Decision, Plateau Validation) | Unchanged |
| Master Architecture pillars / ADRs / Specs | **Not modified** by this policy alone |

**Architectural reopen:** Publishing Dual Reporting as governance documentation is **not** an architectural change.

---

## 8. Placement and Master Document hygiene

- **Canonical policy home:** this file under `docs/architecture/governance/`.  
- **Index:** listed in `docs/architecture/governance/README.md` (and navigation pointer in `docs/architecture/README.md`).  
- **Master Architecture:** no AEL rules registry section existed at institutionalization; Master was **not** rewritten to avoid architectural reopen.  
- **Recommendation:** a future SSOT hygiene mission may add a one-line / small AEL registry pointer to Rule 29 in `master-architecture.md` without reopening pillars.

---

## 9. Compliance checklist (mission close)

A mission claiming completion under AEL must answer **YES** to all:

| # | Check |
|---|--------|
| 1 | Report 1 (Engineering) present and evidence-complete for the mission class |
| 2 | Report 2 (Product Owner) present with all eight mandatory sections |
| 3 | Report 2 is free of implementation jargon as the primary voice |
| 4 | The two reports are separable (not a single mixed dump) |
| 5 | No claim that Dual Reporting changed SSOT, AEAP, or Rules 19 / 23–28 |

---

## 10. Changelog

| Version | Date | Change |
|---------|------|--------|
| 2026.08.07 | 2026-08-07 | Initial institutionalization of REGRA Nº 29 — Dual Reporting |
