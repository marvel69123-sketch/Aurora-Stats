# SSOT_FOUNDATION — Mission Report (ARCHITECTURE_GOVERNANCE)

**MISSION ID:** aurora_ssot_foundation_011  
**TYPE:** ARCHITECTURE_GOVERNANCE / SSOT_FOUNDATION  
**DATE:** 2026-08-06  
**ROLE:** Chief Software Architect / Technical Governance Lead / Configuration Manager  
**MODE:** Governance documentation only — no product code, no Spec edits, no implementation  

---

## 1. Executive Summary

This mission **establishes** the official Aurora Core architecture SSOT at `docs/architecture/`, with Documento Mestre = `docs/architecture/master-architecture.md` (v2026.08.06). Prior repo-wide searches (Audit 001, Residual Plan 010, and this mission) found **no** Documento Mestre Etapa 1. Root `AURORA_ARCHITECTURE.md` is a deploy/code map, not Core Master.

**CDR2-F1 (governance SSOT existence)** is **closable** under Path A once these files are **Git-versioned**. **AAR-002 remains NOT APPROVED**; Spec residuals and AAR-003 remain separate. Spec 004 / product code were **not** modified.

**Official answer:** The Single Source of Truth of Aurora Core architecture is the tree rooted at **`docs/architecture/`**, with normative Master content in **`docs/architecture/master-architecture.md`**.

---

## 2. Situação atual da documentação

### 2.1 Search probes (this mission)

| Probe | Result |
|-------|--------|
| File titled / named Documento Mestre Etapa 1 (or equivalent Aurora Core Etapa 1 master) | **ABSENT** |
| `docs/architecture/` prior to this mission | **ABSENT** |
| Written Substitution waiver (owner, scope, expiry, time-box) as standalone artifact | **ABSENT** (template created; not activated) |
| Root `AURORA_ARCHITECTURE.md` | Present — **code/deploy SoT**, not Core Master |
| `docs/FROZEN_MODULES.md` | Present — freeze registry (supporting) |
| Observations: Audit 001, Research 003, Spec 004, CDR1/2, AAR-001/002, Residual 010 | Present — working papers / review chain |
| `artifacts/aurora/observations/**`, roadmap architecture notes | Present — historical / product research — **not** Master |

### 2.2 Prior official labels

All of Audit 001, Research 003, Spec v1.1 (§16.4 / P0 / VC Q4 / ADR-012), CDR1 FINDING-006, CDR2-F1, AAR-001/002, and Residual Plan 010 §1.1 labeled Documento Mestre as **INSUFFICIENT EVIDENCE** / **ABSENT**. Residual Plan preferred Path A (incorporate master) over Path B (waiver).

### 2.3 Honesty constraint

This mission **does not invent** a prior “Etapa 1” history. It **establishes** the Master as of 2026-08-06.

---

## 3. Definição oficial da SSOT

| Item | Definition |
|------|------------|
| **SSOT root** | `docs/architecture/` |
| **Documento Mestre / Master Architecture** | `docs/architecture/master-architecture.md` |
| **Navigation SSOT** | `docs/architecture/README.md` |
| **Versioning / approval / freeze / traceability** | `docs/architecture/governance/SSOT_POLICY.md` |
| **Working papers** | `observations/**` until promoted via SSOT_POLICY |
| **Code/deploy SoT (not architecture Master)** | `artifacts/aurora/` per root `AURORA_ARCHITECTURE.md` |

**One-sentence official declaration:**  
**The Single Source of Truth of Aurora Core architecture is `docs/architecture/`, with binding Master Architecture at `docs/architecture/master-architecture.md`.**

---

## 4. Estrutura recomendada (and created) do repositório

Created exactly as recommended (no structural adaptation required):

```text
docs/architecture/
├── README.md
├── master-architecture.md
├── adr/
│   └── README.md
├── specifications/
│   └── README.md
├── reviews/
│   └── README.md
└── governance/
    ├── README.md
    ├── SSOT_POLICY.md
    └── SUBSTITUTION_WAIVER_TEMPLATE.md
```

Mission working paper:

```text
observations/aurora_ssot_foundation_011/
└── SSOT_FOUNDATION.md          ← this report
```

### 4.1 Master content binding (evidence)

| Topic | Source incorporated |
|-------|---------------------|
| 14 pillars scoreboard | Audit 001 §3.15 |
| LangGraph-hosted STS sole-writer | Research 003 §7 |
| Spec 004 as Context Manager specialization under Core | Spec 004 / SPEC_v1.1 (pointer; not copied) |
| Frozen engines policy | `docs/FROZEN_MODULES.md` + Audit 001 §4 |
| AAR-001/002 NOT APPROVED + freeze-while-NOT-APPROVED | AAR-001, AAR-002 |
| Technical ≠ Substitution | FINDING-006 / ADR-012 lineage |

---

## 5. Política de versionamento

Codified in `docs/architecture/governance/SSOT_POLICY.md` §3:

- Version IDs: `YYYY.MM.DD`  
- Git history = audit trail  
- Uncommitted drafts do not satisfy Board evidence gates  
- Pillar/Substitution policy flips require new Master version date  
- Spec versioning remains independent  
- Forbidden: parallel Documento Mestre outside `docs/architecture/`

Initial Master + Policy version: **2026.08.06**.

---

## 6. Política de governança

Codified in `SSOT_POLICY.md` §§4–7 and Master §8:

1. Observations are working papers until promoted.  
2. Spec/CDR/AAR prose ≠ Substitution waiver.  
3. While AAR chain is NOT APPROVED: freeze product mutation; allow governance doc publication.  
4. Future audits must cite `docs/architecture/`; must not invent masters.  
5. Waiver Path B available via template only; **not used** to close F1 — Path A Master preferred and delivered.  
6. Traceability: normative Master claims cite Audit/Research/Spec/Frozen/AAR evidence.

---

## 7. Critérios de encerramento do blocker F1

Per `SSOT_POLICY.md` §8 and AAR-002 liberação item 1 (Path A):

| # | Criterion | Status after this mission |
|---|-----------|---------------------------|
| (a) | `docs/architecture/master-architecture.md` exists and is versioned (`2026.08.06`) | **YES** (file); **Git commit pending** for Board-final evidence |
| (b) | README declares SSOT root = `docs/architecture/` | **YES** |
| (c) | Policies exist (`SSOT_POLICY.md`) | **YES** |
| (d) | Future audits must cite `docs/architecture/`, not invent | **YES** (README + Policy + Master §0) |
| (e) | Git-versioned on governed branch | **PENDING human/Board commit** (this mission does not commit unless asked) |

### 7.1 F1 closable?

| Question | Answer |
|----------|--------|
| Is F1 closable after this mission for **governance SSOT existence**? | **YES**, when criteria (a)–(d) are on disk **and** (e) Git versioning is completed |
| Does F1 closure approve AAR-002? | **NO** — AAR-002 stays **NOT APPROVED** until Spec residuals + CDR3 + AAR-003 liberação criteria |
| Does F1 closure authorize implementation? | **NO** |
| Was Path B waiver activated? | **NO** — template only |

**Board recording suggestion:** Next AAR (AAR-003 or interim Board note) should mark **CDR2-F1 CLOSED (Path A)** citing `docs/architecture/master-architecture.md` @ v2026.08.06 after commit; Spec residual mission should then replace bare INSUFFICIENT EVIDENCE with **pointer** to that path (Spec edit = separate mission).

---

## 8. Recomendação final

1. **Commit** the `docs/architecture/**` tree + this mission report to the governed branch (Configuration Manager / human owner) so F1 evidence is Git-resolvable.  
2. **Do not** treat F1 closure as AAR APPROVED.  
3. Execute Residual Plan 010 Spec residual track (v1.2/v1.1.1) → CDR3 → AAR-003 separately.  
4. In the Spec residual mission, update P0/§16.4/ADR-012/VC Q4 to **cite** `docs/architecture/master-architecture.md` (pointer only — no master invention, no Spec wholesale rewrite of Core pillars).  
5. Keep Frozen engines and freeze-while-NOT-APPROVED intact.  
6. Prefer Master Path A; do not issue a blanket Substitution waiver now that Master exists.

---

## Validation Contract

| # | Question | Answer |
|---|----------|--------|
| 1 | Documento Mestre previously existed in-repo? | **NO** |
| 2 | Official SSOT defined and filed under `docs/architecture/`? | **YES** |
| 3 | Master evidence-bound (Audit 001, Research 003, Spec pointer, Frozen, AAR chain)? | **YES** |
| 4 | Fake “Etapa 1” history invented? | **NO** — establishment dated 2026-08-06 |
| 5 | Spec 004 / SPEC_v1.1 edited? | **NO** |
| 6 | Product code / Context Manager architecture implementation changed? | **NO** |
| 7 | F1 closable for governance SSOT existence? | **YES**, contingent on Git versioning (commit) |
| 8 | AAR-002 APPROVED by this mission? | **NO** — remains NOT APPROVED |
| 9 | Waiver activated? | **NO** (template only) |
| 10 | Commit performed by this mission? | **NO** (not requested) |

---

## Return-to-parent package

### Paths created

- `docs/architecture/README.md`
- `docs/architecture/master-architecture.md`
- `docs/architecture/adr/README.md`
- `docs/architecture/specifications/README.md`
- `docs/architecture/reviews/README.md`
- `docs/architecture/governance/README.md`
- `docs/architecture/governance/SSOT_POLICY.md`
- `docs/architecture/governance/SUBSTITUTION_WAIVER_TEMPLATE.md`
- `observations/aurora_ssot_foundation_011/SSOT_FOUNDATION.md`

### Official SSOT declaration (one sentence)

**The Single Source of Truth of Aurora Core architecture is `docs/architecture/`, with binding Master Architecture at `docs/architecture/master-architecture.md`.**

### Documento Mestre previously existed?

**NO**

### Is F1 closable after this mission?

**YES** — for governance SSOT existence — **if** the created files are **Git-versioned** (committed). AAR-002 remains NOT APPROVED until Spec residuals + new AAR.

### Spec/code untouched?

**YES** — confirmed: no Spec 004 / SPEC_v1.1 edits; no product code; no Context Manager implementation changes.
