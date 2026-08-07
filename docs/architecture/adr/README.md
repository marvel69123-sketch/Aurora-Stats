# Architecture Decision Records (ADR) — Index

**SSOT ROOT:** `docs/architecture/`  
**STATUS:** Index + pointer policy (bootstrap)

---

## Policy

1. **Normative ADRs** for Context Manager currently live **inside** Spec 004 / SPEC_v1.1 (e.g. ADR-001 provisional LangGraph host, ADR-012 master/waiver honesty). Those Spec-embedded ADRs remain authoritative until explicitly extracted.  
2. **Do not duplicate** ADR bodies here. This folder is the **locator** and future home for Core-wide ADRs promoted under `SSOT_POLICY.md`.  
3. New Core-wide ADRs (non-Spec) should be added as `docs/architecture/adr/ADR-NNN-title.md` and listed below after governance approval.  
4. Observations may draft ADRs; they are working papers until promoted.

---

## Current pointers (not copies)

| ADR / decision | Authoritative location | Status |
|----------------|------------------------|--------|
| LangGraph as Commit Host (provisional) | Spec 004 / SPEC_v1.1 (ADR-001) | Provisional; flip criteria in Spec |
| Technical acceptance ≠ Substitution; master or waiver | Spec 004 / SPEC_v1.1 (ADR-012) + Master §8 | Binding governance |
| LangGraph-hosted STS Sole-Writer (primary) | Research 003 §7 → Master §5 | Binding architecture decision at Master level |
| KEEP CUSTOM TRANSITION | Research 003 + Spec 004 | Binding |

---

## Local ADR inventory

| ID | File | Notes |
|----|------|-------|
| — | *(none extracted yet)* | Bootstrap: index only |
