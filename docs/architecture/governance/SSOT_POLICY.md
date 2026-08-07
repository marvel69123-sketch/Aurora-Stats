# Aurora Core Architecture — SSOT Policy

**DOCUMENT ID:** AURORA-CORE-SSOT-POLICY  
**VERSION:** 2026.08.06  
**STATUS:** OFFICIAL  
**SSOT ROOT:** `docs/architecture/`

---

## 1. Purpose

Define how Aurora Core architecture truth is versioned, approved, frozen, traced, and promoted so that audits never invent parallel masters and Substitution never self-ratifies via Spec/CDR prose.

---

## 2. Official SSOT declaration

1. **Single official source:** `docs/architecture/` is the SSOT root for Aurora Core architecture.  
2. **Documento Mestre / Master Architecture:** `docs/architecture/master-architecture.md`.  
3. **Navigation SSOT:** `docs/architecture/README.md`.  
4. **`observations/`** are **working papers** until promoted under §6.  
5. Root `AURORA_ARCHITECTURE.md` is **code/deploy SoT guidance**, not the Core architecture Master.  
6. Spec packages are **specialization contracts**, not Master substitutes and not Substitution waivers.

---

## 3. Versioning policy

| Rule | Requirement |
|------|-------------|
| Version identifier | `YYYY.MM.DD` on Master and this Policy (revision date) |
| Storage | Files under `docs/architecture/` in Git |
| Audit trail | Git history is authoritative for “when established / when changed” |
| Uncommitted drafts | Do **not** satisfy Board evidence gates until committed to the repo’s governed branch |
| Breaking vs additive | Additive clarifications = minor note in changelog section or commit message; pillar recommendation flips or Substitution-policy changes = **new Master version date** + governance note |
| Spec versions | Independent (e.g. SPEC_v1.1); Master cites Spec paths, does not absorb Spec versioning |
| Forbidden | Silent path moves without README + Policy update; parallel “Documento Mestre” files outside this tree |

### 3.1 Changelog (Policy)

| Version | Date | Change |
|---------|------|--------|
| 2026.08.06 | 2026-08-06 | Initial SSOT Policy; establishes `docs/architecture/` as SSOT root |

### 3.2 Changelog (Master — pointer)

Maintain Master version header in `master-architecture.md`. First official version: **2026.08.06** (establishment).

---

## 4. Approval policy

| Action | Required authority |
|--------|--------------------|
| Establish / revise Master pillars or Substitution-facing Core policy | Architecture governance mission + human Board acknowledgment (AAR or explicit Board note) |
| Promote observation → SSOT | §6 promotion checklist |
| Approve Spec for **technical** review closure | CDR + AAR per track |
| Authorize **implementation / Substitution** | AAR STATUS **APPROVED** (or conditional with non-blocker residuals only) **after** Master or active waiver + residual criteria |
| Activate Substitution waiver (Path B) | Completed waiver artifact with owner, scope, expiry, time-box; cited from Spec P0/§16.4 when Spec is next revised |
| Edit Frozen module registry | Explicit approval + anti-regression checklist per `docs/FROZEN_MODULES.md` |

**Hard rule:** Spec self-text, CDR acceptance, and AAR NOT APPROVED records are **never** a Substitution waiver.

---

## 5. Freeze-while-NOT-APPROVED

While AAR-001 / AAR-002 (or successor AAR on the same liberação chain) remain **NOT APPROVED**:

1. Architecture for the Substitution design is **frozen against product mutation** (no code, no production write flags, no Implementation Plan execution).  
2. Governance may still **publish SSOT documentation** to close evidence blockers (e.g. Master establishment).  
3. Spec residual documentation missions may proceed; they do not unlock code.  
4. Any claim of “approved to implement” without APPROVED AAR is **void**.

---

## 6. Promotion policy (`observations/` → SSOT)

An observation artifact becomes SSOT-adjacent only when:

1. A governed file under `docs/architecture/` **points** to it as authoritative for a named concern, **or**  
2. Content is **incorporated** into Master / Policy / ADR with version bump, **and**  
3. The observation is labeled **PROMOTED** or **SUPERSEDED** in its header (or the index states supersession).

Until then: cite observations as evidence, not as Master.

---

## 7. Traceability policy

Every Master normative claim that is not definitional must cite at least one of:

- Audit 001, Research 003, Spec path, Frozen registry, AAR/CDR/Matrix path, or prior promoted ADR.

Future audits **must**:

1. Cite `docs/architecture/` for Core architecture authority.  
2. Not invent a second Documento Mestre location.  
3. Label residual unknowns **INSUFFICIENT EVIDENCE** only when evidence is truly absent — **not** for Master absence after this SSOT is Git-versioned.  
4. Keep Technical ≠ Substitution honesty (FINDING-006 / ADR-012 lineage).

---

## 8. F1 (CDR2-F1) governance closure criteria

**CDR2-F1 / AAR-002 Critical** closes for **governance SSOT existence** when **all** of the following hold:

| # | Criterion |
|---|-----------|
| (a) | `docs/architecture/master-architecture.md` exists and carries a version identifier |
| (b) | `docs/architecture/README.md` declares SSOT root = `docs/architecture/` |
| (c) | `docs/architecture/governance/SSOT_POLICY.md` exists (versioning + approval + freeze + traceability) |
| (d) | Future audits are instructed to cite `docs/architecture/` (README + this Policy + Master §0) |
| (e) | Artifacts are **Git-versioned** (committed) on the governed branch — Board evidence requires resolvable repo path in version control |

**Explicit non-effects:**

- Closing F1 **does not** set AAR-002 to APPROVED.  
- Closing F1 **does not** close Spec residuals CDR2-F2…F6 or PARTIAL 014/016.  
- Closing F1 **does not** authorize implementation.  
- AAR-003 + Spec residual plan execution remain required for liberação.

---

## 9. Waiver policy (Path B — discouraged when Master exists)

Prefer Path A (Master coverage). Use Path B only for domains the Master **cannot yet** cover, with:

- owner, scope, expiry, time-box (mandatory)  
- template: `SUBSTITUTION_WAIVER_TEMPLATE.md`  
- no waiver of dual-SoT / durability / sole-writer honesty without Board preference exception recorded in AAR  

With Master v2026.08.06 established for Core pillars/policies, **do not** issue a blanket Substitution waiver to “close F1” — F1 Path A is the intended closure.
