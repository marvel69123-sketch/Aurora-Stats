# MISSION 046 — Aurora Production Rollout Strategy

**TYPE:** RELEASE / GOVERNANCE / SRE PLANNING (DOCS ONLY)  
**MISSION:** 046 — Production Rollout Planning — CM + EM FROZEN entry strategy  
**DATE:** 2026-08-07  
**BRANCH:** `feat/aurora-response-selector-001`  
**PRIOR CLOSURE:** Stage 2 Operational Closure 045 ~`35535f9`  
**CM FROZEN tip:** `11e1a83` (Mission 017)  
**EM FROZEN tip:** `f140878` (Mission 044)  
**ROLES:** Engineering Governance · Release Manager · SRE Planning Lead  

**Binding constraints (this mission):**
- **NO** product code  
- **NO** Feature Flag activation / arming  
- **NO** actual rollout start  
- **DO NOT** resolve Mirror Drift  
- **DO NOT** start Mission 047+  
- Align with existing PGR ladders (DEFAULT OFF) without turning them on  

```text
Nenhuma alteração de código: SIM
Código alterado: NÃO
FLAGS ARMED: NÃO
ROLLOUT STARTED: NÃO
MIRROR DRIFT: OPEN (untreated — precondition only)
MISSION 047+: NOT STARTED
```

**Formal posture:** This package is the **official strategy** for Etapa 3 Production Rollout. Execution of any % step requires separate PO authorization after Activation preconditions (notably Mirror Drift) are dispositioned.

---

## 1. Purpose and non-goals

### Purpose

Define how Aurora enters production with **Context Manager (CM)** and **Execution Manager (EM)** after both modules are **Module FROZEN**, using the existing PGR percentage ladders already implemented behind **DEFAULT OFF**.

### Non-goals (explicit)

| Forbidden in Mission 046 | Why |
|--------------------------|-----|
| Arm any CM/EM flag | Strategy ≠ Activation |
| Raise `AURORA_SOLE_WRITER_FUNNEL_PCT` / `EM_ACTIVATION_PCT` | No live canary |
| Sync / “fix” Mirror Drift | Reserved for Mission 047 (recommended) |
| Retire `copilot_engine` | Residual R-EM-02 — separate track |
| Start Tool Use / Orchestration | Await PO — different module |
| Rewrite Master Architecture / module Specs | Docs strategy + governance addendum only |

---

## 2. Vocabulary (binding)

| Term | Meaning |
|------|---------|
| **Module FROZEN** | AEL cycle complete; gated/defaults-OFF trust; Final Acceptance APPROVED |
| **PGR capability** | Ladder code present (1→100%) with repo defaults OFF — **already true** for CM + EM |
| **Production Rollout** | Operator-armed climb of the same ladder in a **live** Deployment Window with metrics + PO gates |
| **Production Accepted** | Post-100% live plateau: sustained healthy metrics; Board/PO accepts production as default operating posture |
| **Activation license** | Authorization to arm production-affecting flags — **not** granted by Module FROZEN alone |

**Hard split (Blueprint §1.4 / Stage 2 Closure 045):**  
`Module FROZEN ≠ Activation license ≠ Production Accepted`

---

## 3. Current baseline (facts)

| Axis | State |
|------|-------|
| Etapa 1 (CM) | **FROZEN** — Stage 1 Closure 019 |
| Etapa 2 (EM) | **FROZEN** — Stage 2 Closure 045 ~`35535f9` |
| CM PGR ladder | Implemented `AURORA_PGR_01..06_ENABLE` + funnel pct — **DEFAULT OFF** |
| EM PGR ladder | Implemented `ENABLE_EM_PGR_01..06` + `EM_ACTIVATION_PCT` — **DEFAULT OFF** |
| Mirror Drift (`aurora/` ↔ `artifacts/aurora/`) | **OPEN** — Activation / full-env **NO-GO** |
| `copilot_engine` | **PRESENT** (legado) — deferred retirement |
| Production Rollout | **NOT STARTED** (this mission = strategy only) |

**Code SoT for any future arming:** `artifacts/aurora/`  
**Mirror:** `aurora/` — must not be treated as authoritative while drift OPEN.

---

## 4. Official rollout ladder

Canonical percentages (Blueprint §5 / REGRA 24–25) — **identical shape** for CM and EM:

```text
0% → 1% → 5% → 10% → 25% → 50% → 100%
```

### 4.1 Gate map (CM vs EM flags)

| Step | % | PGR ID | CM enable (env) | CM pct surface | EM enable (env) | EM pct surface |
|------|---|--------|-----------------|----------------|-----------------|----------------|
| Hold | 0 | — | all OFF | `AURORA_SOLE_WRITER_FUNNEL_PCT=0` | all OFF | `EM_ACTIVATION_PCT=0` |
| Pilot | 1 | PGR-01 | `AURORA_PGR_01_ENABLE=1` | funnel pct = 1 | `ENABLE_EM_PGR_01=1` | `EM_ACTIVATION_PCT=1` |
| Early | 5 | PGR-02 | `AURORA_PGR_02_ENABLE=1` | 5 | `ENABLE_EM_PGR_02=1` | 5 |
| Expand | 10 | PGR-03 | `AURORA_PGR_03_ENABLE=1` | 10 | `ENABLE_EM_PGR_03=1` | 10 |
| Quarter | 25 | PGR-04 | `AURORA_PGR_04_ENABLE=1` | 25 | `ENABLE_EM_PGR_04=1` | 25 |
| Half | 50 | PGR-05 | `AURORA_PGR_05_ENABLE=1` | 50 | `ENABLE_EM_PGR_05=1` | 50 |
| Full gate | 100 | PGR-06 | `AURORA_PGR_06_ENABLE=1` | 100 | `ENABLE_EM_PGR_06=1` | 100 |

### 4.2 Master / companion flags (must stay coherent)

**Context Manager (illustrative companions — still DEFAULT OFF):**
- Shadow: `ENABLE_LANGGRAPH_STATE_SHADOW` (observe-only; independent)
- Definitive LangGraph write: `ENABLE_LANGGRAPH_STATE` — **full-env Activation class**; not auto-armed by PGR-06
- Sole Writer / funnel: `ENABLE_STS_SOLE_WRITER`, stage funnel flags — required per CM runbooks when climbing write path
- Instant rollback helpers: `rollback_pgr0N_to_off()` family

**Execution Manager (Plan §8 — still DEFAULT OFF):**
- Master: `ENABLE_EXECUTION_MANAGER`
- Shadow: `ENABLE_EXECUTION_MANAGER_SHADOW` (independent; evidence prerequisite before sole-path)
- Pipelines: `ENABLE_EM_PIPELINE_*` (bankroll / learning / knowledge / live / analyze / live_team) — only arm pipelines in scope for the canary
- Instant rollback: `rollback_em_pgr0N_to_off()` / `rollback_em_all_off()`

### 4.3 CM vs EM climb policy (recommended)

| Policy | Recommendation | Rationale |
|--------|----------------|-----------|
| **Independent ladders** | CM and EM **do not** share one env switch | Separate modules, separate illegal matrices |
| **Order (default)** | Prefer **CM pilot stable** before **EM pilot**, when both affect the same user path | CM owns conversational state write; EM is CM write-free executor |
| **Parallel OK** | Shadow may run on both in parallel (observe-only) | Zero User Impact |
| **No bundling** | Never raise CM PGR-N and EM PGR-N in the same unreviewed change | REGRA 27 One Gate, One Decision |
| **Auto-advance** | **False** always | REGRA 24–25 |

**Mission IDs for live raises (illustrative — await PO; not started):**  
047 Mirror Drift → 048 Pilot 1% → 049+ progressive ladder (align with Stage 2 Closure 045 outline).

---

## 5. Criteria to advance each step

Every raise is a **Production Gate Review (Prod-PGR)** reusing REGRA 25–28 discipline in a live Deployment Window.

### 5.1 Common advance criteria (all steps 1%→100%)

| ID | Criterion | Measurable bar (Aurora) |
|----|-----------|-------------------------|
| A1 | **Technical validation PASS** | Checklist in §7 signed by Release/SRE; rollback drill evidence within last 7 days at this or prior step |
| A2 | **PO approval** | Explicit Product Owner authorization for **this % only** (REGRA 25/26/27) |
| A3 | **Zero critical regressions** | No Sev-1 / Sev-0 user-facing incidents attributed to CM/EM in the observation window; no unexplained dual-write / illegal-matrix trip |
| A4 | **Rollback functional** | Documented restore to 0% / prior plateau ≤ **5 minutes** operator time; verified by drill or real rollback |
| A5 | **Latency acceptable** | See `ROLLOUT_METRICS.md` — p95 request/path latency within budget vs pre-arm baseline |
| A6 | **Errors below threshold** | Error rate and timeout rate within budgets in `ROLLOUT_METRICS.md` |
| A7 | **Healthy logs** | No sustained `[AUDIT]` illegal / dual_write_blocked / unexpected rollback storms; Shadow mismatch rate within budget |
| A8 | **Mandatory metrics green** | All metrics in §8 / `ROLLOUT_METRICS.md` collected and within step thresholds |
| A9 | **Plateau hold (REGRA 28)** | Prior % held for minimum Deployment Window (§5.3) without rollback |
| A10 | **Mirror Drift policy satisfied for this step** | See §9 — pilot may proceed under constraints; **full-env / >pilot** requires disposition |

### 5.2 Step-specific emphasis

| Step | Extra emphasis |
|------|----------------|
| **1%** | Canary cohort sticky; blast radius minimal; Shadow comparison preferred ON (observe); SRE on-call present for first window |
| **5%** | Confirm canary math + session stickiness; first real multi-user diversity |
| **10%** | Confirm no silent legacy dual-path confusion (`copilot_engine` PRESENT); CM/EM interaction on shared paths |
| **25%** | Stress on CPU/memory headroom; fallback usage trend stable or improving |
| **50%** | Response quality sample review (human or judge) mandatory; CM/EM failure rates ≤ half of abort threshold |
| **100%** | Full gated posture; still **not** automatic `ENABLE_LANGGRAPH_STATE` / definitive Activation without separate PO; enter Production Accepted observation |

### 5.3 Minimum Deployment Windows (REGRA 26)

| Step | Minimum observation window before next raise | Notes |
|------|-----------------------------------------------|-------|
| 1% | **48 hours** wall-clock **or** ≥ **N=500** gated sessions (whichever later) | Pilot — prefer both |
| 5% | **48 hours** or ≥ **N=1 000** gated sessions | |
| 10% | **72 hours** or ≥ **N=2 000** | |
| 25% | **72 hours** or ≥ **N=5 000** | |
| 50% | **96 hours** or ≥ **N=10 000** | Quality sample required |
| 100% | **7 days** Production Accepted hold | Then Board/PO **Production Accepted** decision |

If traffic is too low to hit N, **wall-clock minimum still binds**; do not skip plateaus.

---

## 6. Rollback criteria (return to 0%)

**Instant rollback target:** effective activation **0%**, PGR enable flags **OFF**, masters that were raised for the canary restored to pre-arm posture (prefer `rollback_*_to_off` helpers).

### 6.1 Mandatory immediate rollback to 0% (any step)

Trigger **any one** of the following → **rollback now**, then incident review:

| ID | Condition |
|----|-----------|
| R1 | **Sev-0 / Sev-1** user-facing outage or data-corruption class event attributed to CM or EM path |
| R2 | **Error rate** on gated cohort ≥ **2×** pre-arm baseline **or** absolute ≥ **5%** of gated requests for **≥ 15 minutes** |
| R3 | **Timeout rate** ≥ **3%** of gated requests for **≥ 15 minutes** |
| R4 | **p95 latency** ≥ **2×** pre-arm baseline for **≥ 15 minutes** |
| R5 | Illegal matrix / dual-write / unexpected sole-writer violation detected in production logs |
| R6 | Rollback helper **fails** or cannot restore 0% within **5 minutes** → escalate + force env clear + redeploy last-known-good config |
| R7 | Mirror Drift discovered to have caused **wrong-tree deploy** of CM/EM during an armed window |
| R8 | CM failure rate or EM failure rate ≥ abort thresholds in `ROLLOUT_METRICS.md` |
| R9 | Sustained **fallback storm** (fallback usage ≥ **25%** of gated turns for **≥ 30 minutes**) without approved waiver |
| R10 | PO or Release Manager issues **STOP** / kill-switch order |

### 6.2 Soft rollback (step-down, not necessarily 0%)

| Condition | Action |
|-----------|--------|
| Metrics yellow (warning thresholds) for full window | Hold plateau; extend window; do **not** advance |
| Isolated pipeline fault (EM) | Disable that `ENABLE_EM_PIPELINE_*` only; keep lower PGR if metrics allow |
| Quality regression without hard errors | Step down one PGR rung **or** 0% if quality Sev ≥ High |

**After any hard rollback to 0%:** next raise requires **new** technical validation + **new** PO approval (no auto re-arm).

---

## 7. Approval model (REGRA 25 / 26 / 27)

Each % increase needs **both**:

1. **Technical validation** (Release Manager / SRE / Engineering lead)  
2. **Product Owner approval** (formal, this-%-only)

```text
PROPOSED PRODUCTION GATE AUTHORIZATION TEMPLATE

PRODUCT OWNER AUTHORIZATION
APPROVED | REJECTED | HOLD
MISSION: <id>
MODULE: CM | EM | BOTH (if separate missions preferred: use two auths)
GATE: Prod-PGR-0N @ <pct>%
DEPLOYMENT WINDOW: <start>–<end>
MIRROR DRIFT STATUS: RESOLVED | WAIVED(Board) | OPEN→NO-GO for this step
TECHNICAL VALIDATION: PASS (signer + evidence path)
ROLLBACK DRILL: PASS (<date>)
AUTO-ADVANCE: FALSE
NEXT GATE: NOT AUTHORIZED
```

**One Gate, One Decision:** a mission that arms 5% must not also arm 10%, Stabilization reopen, Mirror sync, or Tool Use.

---

## 8. Mandatory metrics (summary)

Full definitions, formulas, and thresholds: **`ROLLOUT_METRICS.md`**.

| Metric class | Required |
|--------------|----------|
| Latency (p50/p95/p99) | YES |
| Errors | YES |
| Timeouts | YES |
| CPU | YES |
| Memory | YES |
| Response quality | YES (sample + score) |
| CM failures | YES |
| EM failures | YES |
| Fallback usage | YES |
| Shadow usage / Shadow mismatch | YES |

---

## 9. Mirror Drift — treatment before full rollout (DO NOT resolve here)

**Status entering Mission 046:** **OPEN** (R-EM-01).

| Rollout ambition | Mirror Drift requirement |
|------------------|---------------------------|
| Shadow-only (observe) | Allowed while OPEN (prefer SoT = `artifacts/aurora/`) |
| **Pilot 1%** on SoT only | Conditionally allowed **only if** deploy path is proven to use `artifacts/aurora/` exclusively; wrong-tree risk documented; Board/PO accept residual |
| **> pilot (recommended ≥5%)** | **Mission 047 Mirror Drift Resolution (or Board waiver with expiry)** is a **prerequisite** |
| **Full-env / 100% / Production Accepted** | Mirror Drift must be **RESOLVED** (parity probe green) **or** explicit time-boxed Board waiver — inventing RESOLVED is **forbidden** |

**Recommended Mission 047 (await PO — not started):**
1. Inventory drift paths (router / `copilot_engine` / EM package absence under `aurora/`)  
2. Sync or retire mirror ambiguity  
3. Publish green parity probe  
4. Dual Reporting close  
5. Unlock >pilot production raises  

This mission **registers** the rule only — **no sync performed**.

---

## 10. Observability minimum

See `ROLLOUT_METRICS.md` § Observability. Minimum before any arming:

| Layer | Minimum |
|-------|---------|
| **Dashboards** | One CM panel + one EM panel + one shared SRE overview (latency/errors/CPU/mem/fallback/Shadow) |
| **Logs** | Structured `[AUDIT]` for PGR arm/rollback; funnel commit/skip/block; EM pipeline outcome; illegal matrix |
| **Alerts** | Page on R1–R5 class; ticket on warning thresholds |
| **Snapshots** | Pre-arm baseline export; per-step end-of-window export archived under `observations/` |

---

## 11. AEL evolution (recommendation → governance addendum)

**Recommended official AEL extension after Module FROZEN:**

```text
… → Stabilization → Final Acceptance → Module FROZEN
      → Production Rollout (Prod-PGR 1%→100%)
      → Production Accepted
```

Canonical addendum (proposed/adopted under governance, **without** reopening module Specs or Master pillars):

- [`docs/architecture/governance/AEL_PRODUCTION_EXTENSION_ADDENDUM.md`](../../docs/architecture/governance/AEL_PRODUCTION_EXTENSION_ADDENDUM.md)

Blueprint gains a **pointer only** (no Spec rewrite). Module SSOT architecture remains untouched.

---

## 12. Risk summary

Full matrix: **`ROLLOUT_RISK_MATRIX.md`**.

Top risks if strategy is ignored:
- Arming while Mirror Drift OPEN on dual-tree deploys  
- Bundling CM+EM raises  
- Skipping Deployment Windows  
- Conflating Module FROZEN with Production Accepted  

---

## 13. Recommended Etapa 3 sequence (NOT started)

| Mission | Theme | Status |
|---------|-------|--------|
| **046** | Production Rollout Strategy (this) | **COMPLETE (docs)** |
| **047** | Mirror Drift Resolution | **AWAIT PO** |
| **048** | Pilot 1% (CM and/or EM — one gate) | **AWAIT PO** (after 047 policy) |
| **049+** | 5→10→25→50→100 live | **AWAIT PO** between raises |
| **PA** | Production Accepted Board decision | After 100% hold |

**Also not started:** Tool Use module; `copilot_engine` retirement.

---

## 14. Compliance matrix (Mission 046)

| Rule / policy | This mission |
|---------------|--------------|
| REGRA 19 | No architecture reopen; docs + governance addendum pointer only |
| REGRA 23 | No flags armed; Zero User Impact preserved |
| REGRA 24–28 | Ladder + windows + one-gate **defined**, not executed |
| REGRA 29 | Dual Reporting in `REPORT.md` |
| Blueprint §5.9 | Mirror Drift = Activation/full-rollout precondition — untreated |
| Stage 2 Closure 045 | Etapa 3 outline honored; 047+ not started |

---

## 15. Final posture block

```text
════════════════════════════════════════
MISSION 046 STATUS ........... SUCCESS (STRATEGY ONLY)
PRODUCT CODE ................. NONE
FLAGS ENABLED ................ NO
ROLLOUT STARTED .............. NO
CM ........................... FROZEN (defaults OFF)
EM ........................... FROZEN (defaults OFF)
MIRROR DRIFT ................. OPEN (untreated)
COPILOT_ENGINE ............... PRESENT (untreated)
NEXT ......................... AWAIT PO (e.g. 047 Mirror Drift)
════════════════════════════════════════
```
