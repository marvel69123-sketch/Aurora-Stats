# MISSION 048 — Pilot Rollout 1% (Prod-PGR-01)

**TYPE:** RELEASE / SRE / PRODUCTION PILOT (ops arming via env — repo defaults remain OFF)  
**MISSION:** 048 — Pilot Rollout 1% Production ONLY  
**DATE:** 2026-08-07  
**BRANCH:** `feat/aurora-response-selector-001`  
**STRATEGY SoT:** `observations/aurora_production_rollout_046/`  
**MIRROR DRIFT:** **RESOLVED** (Mission 047 ~`f96de33`)  
**CM FROZEN tip:** `11e1a83` (Mission 017)  
**EM FROZEN tip:** `f140878` (Mission 044)  
**AEAP:** Level 1 (observation + ops runbook; no architecture change)

```text
PRODUCT OWNER AUTHORIZATION
APPROVED
MISSION 048
Pilot Rollout
1% Production
```

```text
STATUS THIS WORKSPACE ........ RUNBOOK_READY_AWAITING_OPS
LIVE PRODUCTION ACCESSIBLE ... NO
REPO DEFAULTS ................ OFF (unchanged)
PERCENT AUTHORIZED ........... 1% ONLY (NOT 5%)
AUTO-ADVANCE ................. FALSE
FLAGS COMMITTED ON ........... NO
```

---

## 1. Executive posture

| Item | Value |
|------|--------|
| Goal | First Pilot Rollout at **1%** real traffic |
| This agent session | Prepared **exact arming runbook**, observation checklist, rollback-to-0%, local canary validation |
| Live arming | **Not performed** — Replit/live deploy, `gh`, Replit CLI, and production metrics endpoints are **not accessible** from this workspace |
| Honesty | No production latency/error metrics are invented |

**Code SoT for deploy:** `artifacts/aurora/`  
**Repo policy:** keep DEFAULT OFF in git; operators set env on the live deployment only.

---

## 2. Production access probe (this workspace)

| Probe | Result |
|-------|--------|
| Replit CLI (`replit`) | ABSENT |
| GitHub CLI (`gh`) | ABSENT |
| Listening app ports (5000/8000/8080/3000/5173) | NONE |
| Local `.env` PGR / EM activation keys | ABSENT (only `API_FOOTBALL_KEY`, `PYTHONPATH`) |
| Ability to read live prod dashboards / logs | NONE |
| Deploy config present (`.replit`, `DEPLOY.md`) | YES (docs only — cannot publish from here) |

**Conclusion:** treat this mission close as **runbook + local validation**. Ops must apply env on production and return observation evidence.

---

## 3. Gate scope (ONE GATE — REGRA 27)

| Allowed | Forbidden |
|---------|-----------|
| Prod-PGR-01 @ **1%** | Raise to **5%** / PGR-02 |
| CM pilot and/or EM pilot as separate arm steps | Bundle CM+EM raises in one unreviewed change without explicit PO note |
| Shadow observe-only companions | `ENABLE_LANGGRAPH_STATE=1` (definitive write Activation) |
| Immediate rollback to **0%** | Architecture / FROZEN module edits |
| Ops env on live deploy | Committing DEFAULT ON in repo |

**Recommended order (Strategy 046 §4.3):** prefer **CM 1% stable** before **EM 1%** on the same user path. Parallel Shadow OK. This runbook documents **both** ladders for ops; default recommended first arm = **CM only**.

---

## 4. Exact arming runbook (1% ONLY)

Deploy identity before arm: record commit SHA of `artifacts/aurora/`, env name, confirm SoT path (post-047 Mirror RESOLVED). Capture **pre-arm baseline** per `ROLLOUT_METRICS.md` (≤24h old).

### 4.1 Pre-arm checklist (NO-GO if any fail)

- [ ] PO auth for Mission 048 / 1% only on file  
- [ ] Mirror Drift **RESOLVED** (047) or Board waiver  
- [ ] Dashboards live: SRE Overview + CM + EM panels  
- [ ] Alerts for R1–R5 class armed  
- [ ] Pre-arm baseline exported under `observations/aurora_pilot_rollout_048/baselines/` (ops)  
- [ ] Rollback drill PASS within last 7 days (or drill now in staging)  
- [ ] Repo/git defaults still OFF (verify no DEFAULT ON merge)  
- [ ] Confirm **no** `AURORA_PGR_02*` / `ENABLE_EM_PGR_02*` / pct=`5`

### 4.2 Context Manager — PGR-01 @ 1%

**Operator env (Replit Secrets / deployment env — NOT git):**

```bash
# CM Prod-PGR-01 — 1% ONLY
export AURORA_PGR_01_ENABLE=1
export AURORA_SOLE_WRITER_FUNNEL_PCT=1
export ENABLE_STS_WRITE_FUNNEL_BOUNDARY=1
export ENABLE_LANGGRAPH_STATE=0
# Prefer Shadow observe-only (optional but recommended):
# export ENABLE_LANGGRAPH_STATE_SHADOW=1

# HARD FORBIDDEN this mission:
# export AURORA_PGR_02_ENABLE=1
# export AURORA_SOLE_WRITER_FUNNEL_PCT=5
```

**In-process helper (if operator REPL available):**

```python
# Instant rollback CM → 0%
from src.conversation.progressive_gate_review import rollback_pgr01_to_off
rollback_pgr01_to_off()
```

**Code runbook SoT:** `operator_enable_pgr01_instructions()` in  
`artifacts/aurora/src/conversation/progressive_gate_review.py`

### 4.3 Execution Manager — PGR-01 @ 1% (optional second gate)

Only after CM pilot green **or** with separate explicit PO note for EM-first.

```bash
# EM Prod-PGR-01 — 1% ONLY
export ENABLE_EM_PGR_01=1
export EM_ACTIVATION_PCT=1
export ENABLE_EXECUTION_MANAGER=1
export ENABLE_EXECUTION_MANAGER_SHADOW=1
# Pipelines: leave OFF unless intentionally in canary scope
# export ENABLE_EM_PIPELINE_ANALYZE=1
# export ENABLE_EM_PIPELINE_LIVE=1

# HARD FORBIDDEN this mission:
# export ENABLE_EM_PGR_02=1
# export EM_ACTIVATION_PCT=5
```

**In-process helper:**

```python
from src.execution_manager.progressive_gate import rollback_em_pgr01_to_off
rollback_em_pgr01_to_off()
```

**Code runbook SoT:** `operator_enable_em_pgr01_instructions()` in  
`artifacts/aurora/src/execution_manager/progressive_gate.py`

### 4.4 Post-arm verification (T+0)

1. Dump flag snapshot (CM `flag_snapshot` / PGR snapshot; EM `em_pgr_flag_snapshot`).  
2. Confirm effective pct **= 1** (not 5/10/…).  
3. Confirm canary bucket sticky key defined.  
4. Confirm `[AUDIT]` arm lines present; no illegal-matrix trips.  
5. Start observation clock (Strategy: **48h** or ≥ **N=500** gated sessions, whichever later).

---

## 5. Observation checklist (during 1% window)

Cadence: first **2 hours** live abort metrics only; then per Strategy 046 reporting cadence.

| Metric class | Watch | Abort → rollback 0% |
|--------------|-------|---------------------|
| Latency p95 | ≤ 1.5× baseline warning | ≥ **2.0×** ≥ 15 min |
| Errors gated | ≤ 2% abs warning band | ≥ **2×** baseline or ≥ **5%** ≥ 15 min |
| Timeouts | ≤ 1.5% warning | ≥ **3%** ≥ 15 min |
| CM fail rate | ≤ 2% warning | ≥ **5%** ≥ 15 min |
| EM fail rate | ≤ 2% warning | ≥ **5%** ≥ 15 min |
| Fallback | ≤ 10% warning | ≥ **25%** ≥ 30 min |
| Shadow mismatch | ≤ 5% warning | ≥ **15%** ≥ 30 min (hold/rollback sole-path) |
| Illegal / dual-write / Shadow write | — | **Immediate** |
| Quality sample | plan ≥ 30 before leaving 1% | Drop ≥ 10 pts / Sev-High → rollback |
| Logs | healthy `[AUDIT]` | rollback storms / illegal → stop |

Full definitions: `observations/aurora_production_rollout_046/ROLLOUT_METRICS.md`.

---

## 6. Rollback to 0% (≤ 5 minutes operator time)

### 6.1 Triggers (any one → rollback now)

R1 Sev-0/1 · R2 error spike · R3 timeout · R4 p95 · R5 illegal/dual-write · R6 helper fail · R7 wrong-tree deploy · R8 CM/EM abort thresholds · R9 fallback storm · R10 PO/Release STOP.

### 6.2 CM rollback (preferred)

```bash
unset AURORA_PGR_01_ENABLE
unset AURORA_SOLE_WRITER_FUNNEL_PCT
# or set both to 0 / empty
export AURORA_PGR_01_ENABLE=0
export AURORA_SOLE_WRITER_FUNNEL_PCT=0
# Redeploy/restart if env is boot-time only
```

Or: `rollback_pgr01_to_off()`.

### 6.3 EM rollback (preferred)

```bash
export ENABLE_EM_PGR_01=0
export EM_ACTIVATION_PCT=0
# Optional full sole-path kill if needed: disable ENABLE_EXECUTION_MANAGER / pipelines
```

Or: `rollback_em_pgr01_to_off()`.

### 6.4 After rollback

- Export post-rollback snapshot + incident notes into this observation folder.  
- **Do not** re-arm without new technical validation + **new** PO approval.  
- **Do not** “compensate” by jumping to 5%.

---

## 7. Local / canary validation performed (non-prod)

| Check | Result |
|-------|--------|
| Repo defaults OFF (CM `pgr01_enable`, funnel pct, EM effective pct) | **PASS** — False / 0 / 0 |
| Force-arm CM 1% then `rollback_pgr01_to_off()` | **PASS** — True→False, pct 1→0 |
| Force-arm EM 1% then `rollback_em_pgr01_to_off()` | **PASS** — effective 1→0 |
| Pytest SoT: `test_context_manager_phase5_pgr01_016.py` + `test_em_phase5_pgr01.py` | **27 passed** |
| Repo defaults left ON after validation | **NO** — cleaned / helpers restore OFF |
| Live production traffic armed | **NO** |

---

## 8. What ops must return after live arm

Append or replace evidence in `PRODUCTION_OBSERVATION_REPORT.md`:

- Arm timestamp, SHA, env name, which ladder (CM / EM / both)  
- Observation window start/end  
- Latency / errors / timeouts / CM / EM / fallback / Shadow table  
- Incidents / rollback (yes/no + reason)  
- Go/No-Go for **holding 1%** only — **5% not authorized**

---

## 9. Final mission block (this workspace)

```text
════════════════════════════════════════
MISSION 048 STATUS .... RUNBOOK_READY_AWAITING_OPS
PERCENT ARMED LIVE .... 0% (ops pending)
PERCENT AUTHORIZED .... 1% ONLY
REPO DEFAULTS ......... OFF
PRODUCTION ACCESS ..... NO
LOCAL VALIDATION ...... PASS (27 tests + arm/rollback probe)
MIRROR DRIFT .......... RESOLVED (047)
NEXT .................. OPS apply §4 on production → observe ≥48h/N=500 → report
5% .................... NOT AUTHORIZED — AWAIT PO
════════════════════════════════════════
```
