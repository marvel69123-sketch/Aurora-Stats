# Aurora Core Architecture — SSOT Navigation Index

**STATUS:** OFFICIAL  
**ESTABLISHED:** 2026-08-06 (Missão ARCHITECTURE_GOVERNANCE / SSOT_FOUNDATION)  
**DOCUMENT CLASS:** Navigation SSOT (not product Spec)

---

## Official SSOT Declaration

**SSOT root = `docs/architecture/`**

This directory tree is the **single official source of truth** for Aurora Core architecture pillars, policies, and navigation to governed artifacts.

| Class | Authority |
|-------|-----------|
| Architecture pillars & Core policies | `docs/architecture/master-architecture.md` |
| Navigation / SSOT locator | **this file** |
| Versioning, approval, traceability | `docs/architecture/governance/SSOT_POLICY.md` |
| Working papers / audits / CDRs / AARs (pre-promotion) | `observations/**` — **not** SSOT until promoted via governance |

**Rule:** Future audits, CDRs, and AARs **must cite** `docs/architecture/` for Aurora Core architecture authority. They must **not invent** a parallel Documento Mestre path, invent “Etapa 1” history, or treat Spec/CDR/AAR prose as a master-document substitute.

---

## Relationship to other trees

| Path | Role | SSOT? |
|------|------|-------|
| `docs/architecture/` | Official Aurora Core architecture SSOT | **YES** |
| `docs/FROZEN_MODULES.md` | Frozen product-module registry (policy pointer from master) | Supporting official policy (product freeze) |
| `AURORA_ARCHITECTURE.md` (repo root) | Deploy / code-path map (artifacts SoT for runtime code) | **NO** — code/deploy SoT, not Core architecture master |
| `observations/**` | Working papers, audits, research, Specs-in-review, CDRs, AARs | **NO** until promoted |
| `artifacts/aurora/observations/**`, `artifacts/aurora/roadmap/**` | Historical / product research artifacts | **NO** |

---

## Tree index

```text
docs/architecture/
├── README.md                 ← this file (SSOT navigation)
├── master-architecture.md    ← Aurora Core Master Architecture (Documento Mestre)
├── adr/                      ← Architecture Decision Records index + pointer policy
├── specifications/           ← index of official Spec paths (pointers only)
├── reviews/                  ← CDR index
└── governance/               ← AAR / matrix / policy index + SSOT_POLICY
```

| Document | Path | Purpose |
|----------|------|---------|
| Master Architecture (Documento Mestre) | [`master-architecture.md`](./master-architecture.md) | 14 pillars + Core policies; closes prior “INSUFFICIENT EVIDENCE” for pillars/policies recorded therein |
| ADR index | [`adr/README.md`](./adr/README.md) | Pointer policy; Spec-embedded ADRs remain authoritative until extracted |
| Specifications index | [`specifications/README.md`](./specifications/README.md) | Links to Spec packages under `observations/` (no wholesale copy) |
| Reviews (CDR) index | [`reviews/README.md`](./reviews/README.md) | Links to CDR packages |
| Governance index | [`governance/README.md`](./governance/README.md) | AARs, matrices, SSOT policy, waiver template |
| SSOT Policy | [`governance/SSOT_POLICY.md`](./governance/SSOT_POLICY.md) | Versioning, approval, freeze-while-NOT-APPROVED, traceability |
| Substitution Waiver Template | [`governance/SUBSTITUTION_WAIVER_TEMPLATE.md`](./governance/SUBSTITUTION_WAIVER_TEMPLATE.md) | Time-boxed waiver form (prefer master coverage; do not use to bypass Spec residuals) |

---

## Governance status snapshot (as of establishment)

| Artifact | Status | Implication |
|----------|--------|-------------|
| AAR-001 | **NOT APPROVED** | Implementation / Substitution blocked |
| AAR-002 | **NOT APPROVED** | Implementation / Substitution blocked; CDR2-F1 was master/waiver absence |
| Spec 004 / SPEC_v1.1 | Reviewable; **not** authorized for implementation | Context Manager specialization under Core |
| Architecture freeze rule | While AAR chain is NOT APPROVED, architecture is **frozen** for product mutation | Docs may close governance gaps; code/Spec content edits require their own missions |

---

## How to cite

```text
Architecture authority: docs/architecture/master-architecture.md (vYYYY.MM.DD)
SSOT root: docs/architecture/
```

For Context Manager specialization detail, cite Spec path via [`specifications/README.md`](./specifications/README.md) **after** confirming AAR authorization state — Spec acceptance ≠ Substitution authorization.
