# MISSION 046 — Rollout Metrics Catalog

**DOCUMENT:** `ROLLOUT_METRICS.md`  
**MISSION:** 046 — Production Rollout Planning  
**COMPANION:** `PRODUCTION_ROLLOUT_STRATEGY.md` · `ROLLOUT_RISK_MATRIX.md`  
**CLASS:** SRE / Release metrics contract (docs only)  
**STATUS:** OFFICIAL strategy metrics — **not instrumented or armed by this mission**

```text
Nenhuma alteração de código: SIM
FLAGS ARMED: NÃO
ROLLOUT STARTED: NÃO
```

---

## 1. Purpose

Define the **mandatory metric set**, measurement method, baselines, warning/abort thresholds, and observability surfaces required before and during any future CM/EM production percentage raise.

This document does **not** create dashboards in product code. It is the contract operators must satisfy when PO authorizes live Prod-PGR steps.

---

## 2. Baseline capture (before first arming)

| Artifact | Required content | When |
|----------|------------------|------|
| Pre-arm baseline | Latency p50/p95/p99, error %, timeout %, CPU, memory, fallback %, quality sample score | ≤ 24h before Pilot 1% |
| Cohort definition | How canary sessions are selected (hash bucket / sticky key) for CM and EM | Before arming |
| Deploy identity | Commit SHA of `artifacts/aurora/`, env name, confirm mirror not serving writes | Every arm |
| Flag snapshot | Dump of CM + EM flag/pct posture (all expected OFF pre-arm) | Every arm / rollback |

Store baselines under `observations/aurora_production_rollout_*/baselines/` (future missions) — **not created here**.

---

## 3. Mandatory metrics

### 3.1 Latency

| Metric | Definition | Source (typical) | Warning | Abort / rollback |
|--------|------------|------------------|---------|------------------|
| `lat_p50` | Median end-to-end request/path latency for gated cohort | APM / access logs | ≥ 1.3× baseline | — |
| `lat_p95` | 95th percentile | APM / access logs | ≥ 1.5× baseline | ≥ **2.0×** baseline for ≥ 15 min |
| `lat_p99` | 99th percentile | APM / access logs | ≥ 1.8× baseline | ≥ **2.5×** baseline for ≥ 15 min |
| `lat_cm_commit_p95` | CM sole-writer / funnel commit path | CM `[AUDIT]` + timers | ≥ 1.5× | ≥ 2.0× ≥ 15 min |
| `lat_em_pipeline_p95` | EM sole-path pipeline latency (armed pipelines) | EM observability | ≥ 1.5× | ≥ 2.0× ≥ 15 min |

**Absolute floor (if baseline missing):** treat `lat_p95` > **8s** (interactive chat path) as abort until a Board waiver sets otherwise.

### 3.2 Errors

| Metric | Definition | Warning | Abort |
|--------|------------|---------|-------|
| `err_rate_gated` | 5xx + unhandled exceptions / gated requests | ≥ 1.5× baseline or ≥ 2% abs | ≥ **2×** baseline or ≥ **5%** abs for ≥ 15 min |
| `err_rate_control` | Same on non-gated cohort | Used as live control | Divergence ≥ 3 pp sustained → investigate |
| `illegal_matrix_trips` | Fail-closed illegal flag combinations | Any unexpected trip | **Immediate** rollback if production path armed illegally |
| `dual_write_blocked` | CM funnel dual-write blocks | Spike vs baseline | Sustained spike → hold/rollback |

### 3.3 Timeouts

| Metric | Definition | Warning | Abort |
|--------|------------|---------|-------|
| `timeout_rate` | Timed-out gated requests / gated requests | ≥ 1.5% | ≥ **3%** for ≥ 15 min |
| `upstream_timeout_rate` | Provider/API timeouts inside EM/CM paths | ≥ 2% | ≥ 5% ≥ 15 min |

### 3.4 CPU

| Metric | Definition | Warning | Abort |
|--------|------------|---------|-------|
| `cpu_avg_host` | Average CPU % on serving hosts | ≥ 70% sustained 30 min | ≥ **90%** sustained 15 min **and** latency abort co-trigger |
| `cpu_p95_host` | p95 CPU | ≥ 80% | ≥ 95% with user impact |

Compare gated vs control hosts when split; otherwise compare to pre-arm baseline.

### 3.5 Memory

| Metric | Definition | Warning | Abort |
|--------|------------|---------|-------|
| `mem_rss_p95` | Process RSS p95 | ≥ 1.3× baseline | ≥ **1.6×** baseline or OOM events |
| `mem_growth_rate` | RSS growth / hour during window | Unbounded linear growth | OOMKill / restart loop → **immediate** rollback |

### 3.6 Response quality

| Metric | Definition | Warning | Abort |
|--------|------------|---------|-------|
| `quality_sample_score` | Blind or side-by-side sample (human or approved judge) on gated vs control | Drop ≥ 5 points (0–100 scale) | Drop ≥ **10 points** or Sev-High product complaint cluster |
| `quality_complaint_rate` | User complaints / gated sessions | ≥ 2× control | ≥ 3× control ≥ 1 window day |
| `ownership_loop_rate` | Known Aurora anti-loop / ownership regressions | Any material rise vs Stage 2 baselines | Sev-High → rollback |

**Sampling minimum:** ≥ **30** gated turns reviewed before leaving 1% and 5%; ≥ **50** before leaving 25%; ≥ **100** before leaving 50%.

### 3.7 CM failures

| Metric | Definition | Warning | Abort |
|--------|------------|---------|-------|
| `cm_fail_rate` | Funnel commit failures + hard CM exceptions / CM-eligible gated turns | ≥ 2% | ≥ **5%** ≥ 15 min |
| `cm_skip_unexpected` | Unexpected `SOLE_WRITER_FUNNEL skipped` rate | Spike vs plan | Investigate; hold advance |
| `cm_rollback_events` | Production `rollback_pgr*_to_off` invocations | Any unplanned | Incident + root cause before re-arm |

### 3.8 EM failures

| Metric | Definition | Warning | Abort |
|--------|------------|---------|-------|
| `em_fail_rate` | EM sole-path failures / EM-gated requests | ≥ 2% | ≥ **5%** ≥ 15 min |
| `em_pipeline_fail{name}` | Per `ENABLE_EM_PIPELINE_*` failure rate | ≥ 3% | ≥ 8% → disable that pipeline flag |
| `em_illegal_trips` | EM illegal matrix I1–I8 production trips | Any | Immediate posture correction / rollback |

### 3.9 Fallback usage

| Metric | Definition | Warning | Abort |
|--------|------------|---------|-------|
| `fallback_rate` | Turns that left gated CM/EM path for legacy/fallback / gated turns | ≥ 10% | ≥ **25%** ≥ 30 min → hard rollback |
| `legacy_copilot_share` | Share still served by `copilot_engine` when EM armed | Track only (PRESENT by design) | Unexpected **increase** while EM % rises → hold |

### 3.10 Shadow usage

| Metric | Definition | Warning | Abort |
|--------|------------|---------|-------|
| `shadow_armed` | Shadow flag ON during window (boolean + %) | Prefer ON for pilot | — |
| `shadow_invoke_rate` | Shadow observe invocations / eligible traffic | Drop to ~0 unexpectedly | Investigate instrumentation |
| `shadow_mismatch_rate` | Material Shadow vs primary disagreement rate | ≥ 5% | ≥ **15%** ≥ 30 min → hold or rollback sole-path; keep Shadow for diagnosis |
| `shadow_write_violations` | Any Shadow path attempting production subject write | **Any** | **Immediate** rollback + Sev-1 review |

---

## 4. Step thresholds (quick reference)

| Step | Extra metric gates before advance |
|------|-----------------------------------|
| 0% → 1% | Baseline captured; rollback drill PASS; dashboards live; Mirror policy for pilot satisfied |
| 1% → 5% | All abort metrics green for full 1% window; quality sample ≥ 30 |
| 5% → 10% | Same + Shadow mismatch < warning |
| 10% → 25% | Same + CPU/mem headroom green |
| 25% → 50% | Same + quality sample ≥ 50 |
| 50% → 100% | Same + quality sample ≥ 100; no Sev-1 in window |
| 100% → Production Accepted | 7-day hold; all mandatory metrics green; Mirror RESOLVED or Board waiver |

---

## 5. Observability

### 5.1 Dashboards (minimum)

| Dashboard | Panels |
|-----------|--------|
| **SRE Overview** | lat_p95, err_rate_gated, timeout_rate, cpu, mem, fallback_rate, active pct CM, active pct EM |
| **CM Rollout** | funnel commit/skip/block, cm_fail_rate, PGR enable state, Shadow mismatch, dual_write_blocked |
| **EM Rollout** | em_fail_rate, per-pipeline success, PGR enable state, Shadow invoke/mismatch, illegal trips |

### 5.2 Logs (minimum)

| Stream | Must include |
|--------|--------------|
| CM audit | `[AUDIT] PGR-0N …`, `rollback_to_off`, `SOLE_WRITER_FUNNEL commit|skipped|blocked_*|dual_write_blocked` |
| EM audit | PGR arm/rollback, pipeline outcome, illegal matrix, Shadow observe-only markers |
| Deploy | commit SHA, env, flag snapshot at boot / on change |

### 5.3 Alerts (minimum)

| Alert | Severity | Condition |
|-------|----------|-----------|
| `aurora_rollout_latency_abort` | Page | lat_p95 abort rule |
| `aurora_rollout_error_abort` | Page | err_rate abort rule |
| `aurora_rollout_timeout_abort` | Page | timeout abort rule |
| `aurora_rollout_shadow_write` | Page | any Shadow write violation |
| `aurora_rollout_illegal_matrix` | Page | illegal trip while armed |
| `aurora_rollout_fallback_storm` | Page | fallback abort rule |
| `aurora_rollout_metric_gap` | Ticket | mandatory metric missing > 10 min during armed window |

### 5.4 Minimum metrics checklist (pre-arm)

- [ ] Latency p50/p95/p99  
- [ ] Errors  
- [ ] Timeouts  
- [ ] CPU  
- [ ] Memory  
- [ ] Response quality sampling plan  
- [ ] CM failures  
- [ ] EM failures  
- [ ] Fallback usage  
- [ ] Shadow usage / mismatch  

**If any box unchecked → NO-GO for arming.**

---

## 6. Reporting cadence during armed windows

| Cadence | Audience | Content |
|---------|----------|---------|
| First 2 hours @ 1% | SRE + Release | Live abort metrics only |
| End of each Deployment Window | Eng + PO | Dual Reporting lite: metrics table + Go/No-Go for next % |
| After rollback | Eng + PO | Incident + root cause + re-arm criteria |

---

## 7. Explicit non-claims

This mission does **not**:
- Enable metrics exporters in product code  
- Create production dashboards in cloud accounts  
- Arm Shadow or PGR flags  
- Declare baselines already captured for live traffic  

Those are prerequisites for Mission **048+** execution missions after PO authorization.
