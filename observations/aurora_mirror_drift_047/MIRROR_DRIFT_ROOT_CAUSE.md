# Mission 047 — Mirror Drift Root Cause Analysis

**Date:** 2026-08-07  
**Branch:** `feat/aurora-response-selector-001`  
**PO Authorization:** APPROVED — Mission 047 Mirror Drift Resolution  
**CM / EM:** FROZEN (untouched internals; probes/tests only)

---

## 1. Verdict (one line)

Mirror drift was an **ops/hygiene dual-tree lag**, not an architecture defect: CM/EM were implemented only under deploy SoT `artifacts/aurora/`, while optional local mirror `aurora/` was never re-synced.

---

## 2. Where / when / why

| Dimension | Evidence |
|-----------|----------|
| **Where** | Dual trees: `artifacts/aurora/` (SoT) vs `aurora/` (optional local mirror) |
| **When** | Emerged during CM AEL (FINDING-024 / Plan 014 IO9) and carried through EM Stabilization 043 / FA 044 as **R-EM-01**; still OPEN at Stage 2 Closure 045 and Production Rollout Strategy 046 |
| **Why** | Implementation work targeted SoT exclusively (correct for deploy). Official one-way sync `scripts/sync-aurora-mirror.sh` existed but was **not executed** after CM/EM landings. Probe functions honestly reported OPEN when EM package / CM modules were absent under `aurora/src/…` |
| **Not why** | Not a Replit deploy wiring bug; not a Frozen CM/EM logic regression; not Tool Use / new Core module |

### Pre-fix snapshot (Mission 030 / 043 / 044 lineage)

| Path class | `artifacts/aurora/` | `aurora/` |
|------------|---------------------|-----------|
| `src/execution_manager/` | Present (FROZEN EM) | **ABSENT** |
| CM STS / LangGraph / TB-V2 modules under `src/conversation/` | Present | **ABSENT** |
| `copilot_unified_router.py` | Newer SoT bytes | Lagging / drifted historically |

Tracked file counts before sync: SoT ≈ 654 paths; mirror ≈ 65 paths.

---

## 3. Deploy path truth (impact)

| Surface | Points at |
|---------|-----------|
| `artifacts/api-server/.replit-artifact/artifact.toml` | `…/artifacts/aurora` build + `start.sh` |
| `.replit` comments / `DEPLOY.md` / `AURORA_ARCHITECTURE.md` | Backend SoT = `artifacts/aurora/` |
| `aurora/` | Explicitly **optional local mirror**; never deploy origin |

**Real production risk while OPEN:** wrong-tree human/automation habit (editing or publishing from `aurora/`) could ship a tree **without** CM/EM. Autoscale Replit service itself was already SoT-correct — hence residual classified as **Activation / full-env precondition**, not live-user defect while flags OFF.

---

## 4. Architecture interactions

| Component | Interaction with drift |
|-----------|------------------------|
| **CM (STS, LangGraph, TB-V2)** | Modules SoT-only → mirror probe OPEN; defaults OFF → no user write path armed |
| **EM** | Package SoT-only → `assess_em_mirror_drift()` OPEN (R-EM-01) |
| **Unified Router** | Historical content drift vs SoT; deploy still loads SoT router |
| **Session / persistence** | Unchanged; Autoscale SQLite locality unchanged |
| **Flags / Shadow** | Defaults remain OFF; Shadow independent of mirror tree |
| **Autoscaling** | Deploy identity = SoT commit; mirror not in `artifact.toml` run path |

---

## 5. Root cause statement

**Root cause:** Process gap — optional mirror not refreshed after SoT-only CM/EM delivery — combined with honest Activation gating that correctly refused to invent RESOLVED.

**Contributing factors:** Dual-tree layout retained for local convenience; Stabilization/FA missions deferred sync by design (document OPEN).

---

## 6. Disposition options considered

1. **Sync SoT → mirror** (chosen) — restores parity probe green; preserves declared SoT; uses existing `sync-aurora-mirror.sh`.  
2. **Deprecate mirror / SoT-only policy** — already true for deploy, but Activation docs required **parity probe green** or Board waiver for full-env; deprecation alone would still need formal waiver language.  
3. **Architectural reopen** — **not required** (REGRA 19: no Master reopen).

---

```text
ROOT CAUSE: dual-tree sync lag (SoT progressed; optional aurora/ mirror stale)
DEPLOY IMPACT: wrong-tree risk if mirror used; Replit service already SoT-bound
ARCHITECTURE: no Frozen CM/EM reopen required
```
