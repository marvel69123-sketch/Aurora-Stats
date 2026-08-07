# AEL Policy — REGRA Nº 29 — Dual Reporting

**DOCUMENT ID:** AURORA-AEL-REGRA-29-DUAL-REPORTING  
**VERSION:** 2026.08.07.1  
**STATUS:** OFFICIAL  
**CLASS:** Architecture Execution Law (AEL) — permanent process policy  
**SSOT ROOT:** `docs/architecture/`  
**AUTHORITY PATH:** `docs/architecture/governance/DUAL_REPORTING_POLICY.md`

---

## 1. Purpose

Institutionalize a permanent reporting obligation: every Aurora mission **must** end with **two independent reports** — one for engineering evidence and one for Product Owner understanding — so that technical closure and product comprehension never collapse into a single audience-mixed artifact.

This rule does **not** change architecture, SSOT, AEAP, or Rules 19 / 23–28. It adds a mandatory **reporting dual** at mission close.

**Obsolescence note:** Separate ad-hoc requests for “lay explanation,” “explain to PO,” or a second pass in simple language are **obsolete**. Dual Reporting (Report 1 + Report 2) is **mandatory at every mission close**; the Product Owner Report is the official lay channel.

---

## 2. Statement of the rule (REGRA Nº 29)

**Every mission MUST end with two independent reports:**

| Report | Audience | Nature |
|--------|----------|--------|
| **Report 1 — ENGINEERING REPORT** | Engineering / Board technical reviewers | Technical pattern: evidence, hashes, flags, rollback, architecture notes, validations |
| **Report 2 — PRODUCT OWNER REPORT** | Product Owner / non-technical stakeholders | Lay language only; fixed eight-section template with **official visual headers**; **no jargon**; **no implementation detail** |

The two reports are **independent**: neither may replace the other. A mission is **incomplete** if either report is missing, merged into a single mixed narrative, or if Report 2 contains engineering jargon / implementation detail.

---

## 3. Prompt Mestre — governance block (mandatory inclusion)

All future Aurora mission prompts **must** prepend or include the following copyable governance block (or an equivalent that preserves every obligation below). Agents and operators treat this as binding process law at mission close.

```text
# AURORA GOVERNANCE / REGRA Nº 29 — Dual Reporting

Every mission MUST end with TWO independent reports:

## Report 1 — ENGINEERING REPORT
Technical pattern (evidence, hashes, flags, rollback, architecture notes, validations).
May use technical vocabulary (AEAP, SSOT, pytest, feature flags, etc.).

## Report 2 — PRODUCT OWNER REPORT
Lay language only. Use the official visual headers and answer all eight questions:

📋 PRODUCT OWNER REPORT
✅ O que fizemos hoje
🧠 O que isso significa
👤 O usuário percebe diferença?
⚠️ Existe algum risco?
🎯 O que ainda falta?
📊 Quanto falta?
🏗️ Analogia simples
📝 Resumo em uma frase

Under "📊 Quanto falta?" include a text progress bar, e.g.:
██████████████████░░  80%

### Language rules (Report 2)
- Lay language only.
- No implementation detail (no file paths as the story, no code diffs, no test counts as the main narrative).
- No unexplained jargon. If a governed term must appear, explain it with a simple analogy.
- Same facts as Report 1, translated — not a different reality.

### Compatibility (non-alteration)
REGRA Nº 29 coexists with and does NOT alter: SSOT, AEAP, REGRA Nº 19, REGRAS Nº 23–28.
Canonical policy: docs/architecture/governance/DUAL_REPORTING_POLICY.md
```

**Placement:** Include this block in mission briefs, Prompt Mestre packages, and any standing “how to close a mission” checklist. Omitting Dual Reporting at close is a compliance failure even if the product work succeeded.

---

## 4. Report 1 — ENGINEERING REPORT (required content)

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

## 5. Report 2 — PRODUCT OWNER REPORT (mandatory visual template)

Report 2 **always** uses this fixed structure, in this order, with these **exact visual headers** (emoji + title). Section titles in prose forms without emoji remain acceptable only when the eight questions and order are preserved; the visual pattern below is the **official** Product Owner Report header pattern.

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

### 5.1 Mapping (visual header → question intent)

| Visual header | Intent |
|---------------|--------|
| ✅ O que fizemos hoje | What shipped / was decided in this mission |
| 🧠 O que isso significa | Meaning in simple language |
| 👤 O usuário percebe diferença? | End-user visible change: yes / no / how |
| ⚠️ Existe algum risco? | Residual risk in lay terms |
| 🎯 O que ainda falta? | Remaining work (next steps, not this mission’s done work) |
| 📊 Quanto falta? | How much is left — **with progress bar** (see §5.2) |
| 🏗️ Analogia simples | One simple analogy |
| 📝 Resumo em uma frase | Single-sentence summary |

### 5.2 Progress bar under “Quanto falta?”

Under **📊 Quanto falta?**, Report 2 **must** include a text progress bar plus a percentage that reflects how close the **scoped mission** (or the clearly named larger goal) is to completion.

**Canonical example:**

```text
██████████████████░░  80%
```

**Guidance:**

- Prefer a filled/empty block bar (`█` / `░`) followed by an integer percent.  
- State what the percent measures (this mission vs. a named larger program).  
- Do not invent false precision; round to a honest band (e.g. 75%, 90%, ~100%).  
- A small policy/docs tweak that completes Rule 29 itself may show near **100%** for that rule while still noting product roadmap elsewhere if relevant.

### 5.3 Hard constraints for Report 2 (language rules)

- Lay language only.  
- **No** implementation detail (no file paths as the story, no code diffs, no test counts as the main narrative, no flag names unless the PO already uses them as product labels).  
- **No** unexplained jargon. If a governed term must appear, explain it with a simple analogy (see §6).  
- Same facts as Report 1, translated — not a different reality.

---

## 6. Lay analogies (canonical examples)

Use these (or equally simple equivalents) when explaining recurring Aurora concepts to the Product Owner:

| Term | Lay analogy |
|------|-------------|
| **Shadow Mode** | Aluno que acompanha o professor mas ainda não responde sozinho |
| **Rollback** | Voltar rapidamente ao estado anterior |
| **AEAP Local Audit** | Revisar só a sala onde houve mudanças |
| **Sole Writer** | Uma pessoa responsável por registrar decisões oficiais |
| **Plateau Validation** | Confirmar que o novo cérebro está preparado antes de mais responsabilidade |

---

## 7. Applicability

REGRA Nº 29 applies to **all** Aurora missions from institutionalization onward, including but not limited to:

- Context Manager  
- Execution Manager  
- Tool Use  
- Orchestration  
- **All future modules**

No module, phase, or gate is exempt unless the Board issues an explicit, time-boxed written waiver citing this document.

---

## 8. Compatibility (non-alteration clause) — Rules 19–29

This policy **coexists** with and **does not alter**:

| Artifact / rule | Relationship |
|-----------------|--------------|
| **SSOT** (`docs/architecture/`, `SSOT_POLICY.md`, Master) | Unchanged; Dual Reporting is process law under governance |
| **AEAP** | Unchanged; Report 1 may record AEAP budget; Report 2 must not require AEAP jargon |
| **REGRA Nº 19** (controlled implementation / no unauthorized architecture reopen) | Unchanged |
| **REGRAS Nº 23–28** (Zero User Impact, Progressive Activation, PGR, Deployment Window, One Gate One Decision, Plateau Validation) | Unchanged |
| **REGRA Nº 29** (this policy) | Dual Reporting obligation; enhancements (Prompt Mestre block, PO visual template) do not reopen architecture |
| Master Architecture pillars / ADRs / Specs | **Not modified** by this policy alone |

**Architectural reopen:** Publishing or enhancing Dual Reporting as governance documentation is **not** an architectural change.

---

## 9. Placement and Master Document hygiene

- **Canonical policy home:** this file under `docs/architecture/governance/`.  
- **Index:** listed in `docs/architecture/governance/README.md` (and navigation pointer in `docs/architecture/README.md`).  
- **Master Architecture:** no AEL rules registry section existed at institutionalization; Master was **not** rewritten to avoid architectural reopen.  
- **Recommendation:** a future SSOT hygiene mission may add a one-line / small AEL registry pointer to Rule 29 in `master-architecture.md` without reopening pillars.

---

## 10. Compliance checklist (mission close)

A mission claiming completion under AEL must answer **YES** to all:

| # | Check |
|---|--------|
| 1 | Report 1 (Engineering) present and evidence-complete for the mission class |
| 2 | Report 2 (Product Owner) present with all eight mandatory sections (official visual headers preferred) |
| 3 | Report 2 includes progress bar + percent under “Quanto falta?” |
| 4 | Report 2 is free of implementation jargon as the primary voice |
| 5 | The two reports are separable (not a single mixed dump) |
| 6 | No claim that Dual Reporting changed SSOT, AEAP, or Rules 19 / 23–28 |
| 7 | Mission prompt / Prompt Mestre included the REGRA Nº 29 governance block (or equivalent obligations) |

---

## 11. Changelog

| Version | Date | Change |
|---------|------|--------|
| 2026.08.07 | 2026-08-07 | Initial institutionalization of REGRA Nº 29 — Dual Reporting |
| 2026.08.07.1 | 2026-08-07 | Enhancement: official Prompt Mestre governance block; mandatory PO visual header pattern; progress-bar guidance under “Quanto falta?”; language rules restated; compatibility matrix Rules 19–29; obsolete separate lay-explanation requests |
