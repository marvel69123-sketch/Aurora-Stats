# Specifications — Index (pointers only)

**SSOT ROOT:** `docs/architecture/`  
**POLICY:** Link official Spec paths. **Do not** copy Spec content wholesale into this tree.

---

## Official Spec packages (as of 2026-08-06)

| Spec | Paths | Scope | Implementation authorization |
|------|-------|-------|------------------------------|
| Spec 004 — Context Manager | `observations/aurora_context_manager_spec_004/SPEC.md` | Context Manager specialization under Aurora Core | **Blocked** (AAR-001/002 NOT APPROVED) |
| Spec 004 v1.1 | `observations/aurora_context_manager_spec_004/SPEC_v1.1.md` | Residual-closing revision after AAR-001 Matrix | Reviewable; **not** approved for implementation |
| Future Spec 004 v1.2 / v1.1.1 | *(not yet published)* | Residual Plan 010 Spec residuals only | Pending dedicated Spec mission |

---

## Relationship to Master

- Master Architecture (`../master-architecture.md`) defines Core pillars and the Context Manager **decision envelope**.  
- Spec 004 defines the **specialization contract** (STS, Commit Host phases, flags, ADRs).  
- Spec text is **not** Documento Mestre and **not** a Substitution waiver.

---

## Promotion rule

When a Spec is Board-approved for implementation, update this index with AAR citation and Master version. Until then, list status as **not authorized**.
