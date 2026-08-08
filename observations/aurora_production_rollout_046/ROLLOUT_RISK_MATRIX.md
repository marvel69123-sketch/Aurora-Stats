# MISSION 046 — Production Rollout Risk Matrix

**DOCUMENT:** `ROLLOUT_RISK_MATRIX.md`  
**MISSION:** 046 — Production Rollout Planning  
**COMPANION:** `PRODUCTION_ROLLOUT_STRATEGY.md` · `ROLLOUT_METRICS.md`  
**CLASS:** Release / SRE risk register (docs only)  
**STATUS:** OFFICIAL strategy — risks **registered**, not treated by product changes here

```text
Nenhuma alteração de código: SIM
FLAGS ARMED: NÃO
ROLLOUT STARTED: NÃO
MIRROR DRIFT: OPEN (untreated)
```

---

## 1. How to read this matrix

| Field | Meaning |
|-------|---------|
| **Likelihood** | L / M / H — while defaults OFF today vs if armed without controls |
| **Impact** | L / M / H / Crit — user or governance damage if realized |
| **Now (defaults OFF)** | Residual risk with current FROZEN / OFF posture |
| **If armed poorly** | Risk if Etapa 3 proceeds without this strategy |
| **Treatment** | Strategy control — **not** executed in Mission 046 |

Severity key: **Crit** > **H** > **M** > **L**.

---

## 2. Risk register

| ID | Risk | Now (OFF) | If armed poorly | Likelihood→Impact (armed) | Mitigation (strategy) | Owner | Gate |
|----|------|-----------|-----------------|---------------------------|------------------------|-------|------|
| RR-01 | **Mirror Drift** causes wrong-tree deploy of CM/EM | L | Crit | H→Crit | Mission **047** disposition before >pilot; SoT=`artifacts/aurora/`; parity probe | Release / SRE | Before ≥5% / full-env |
| RR-02 | Inventing Mirror Drift **RESOLVED** | Process H if attempted | Crit (governance) | M→Crit | Forbidden; honest OPEN until evidence | Board / Eng | Continuous |
| RR-03 | Arming CM/EM without PO (REGRA 25/27) | L | H | M→H | Formal PO auth per %; One Gate, One Decision | PO + Release | Every raise |
| RR-04 | Bundling multiple % raises | L | H | M→H | Separate Prod-PGR missions | Release | Every raise |
| RR-05 | Skipping Deployment Window (REGRA 26/28) | L | H | M→H | Minimum windows in strategy §5.3 | SRE | Every raise |
| RR-06 | Rollback helper untested / broken | L | Crit | L→Crit | Drill ≤7 days before raise; abort if >5 min | SRE | Pre-arm |
| RR-07 | Latency / timeout regression at scale | L | H | M→H | `ROLLOUT_METRICS` abort rules; step-down | SRE | Armed windows |
| RR-08 | Error / fallback storm | L | H | M→H | Abort thresholds; kill-switch to 0% | SRE | Armed windows |
| RR-09 | CM sole-writer dual-write / illegal matrix in prod | L | Crit | L→Crit | Keep illegal matrix; alert on trips; instant OFF | Eng CM | Armed windows |
| RR-10 | EM illegal matrix / pipeline misfire | L | H | M→H | Per-pipeline disable; EM abort metrics | Eng EM | Armed windows |
| RR-11 | Shadow writes to production subject | L | Crit | L→Crit | Shadow observe-only invariant; page alert | Eng | Shadow ON |
| RR-12 | Response quality regression (loops, ownership) | L | H | M→H | Quality samples per step; hold on drop | PO + Eng | ≥1% |
| RR-13 | **`copilot_engine` PRESENT** confuses dual-path ops | L–M | M–H | M→M/H | Track `legacy_copilot_share`; dedicated retirement mission later | Eng | ≥10% |
| RR-14 | CPU/memory exhaustion under 50–100% | L | H | M→H | Headroom gates; scale before 50% | SRE | ≥25% |
| RR-15 | Conflating Module FROZEN with Production Accepted | Process | H | M→H | AEL extension addendum vocabulary | Governance | Continuous |
| RR-16 | Starting Tool Use mid-rollout | Process | H | M→H | Await PO; separate module AEL | PO | Continuous |
| RR-17 | Auto-re-arm after rollback | L | H | L→H | Require new tech + PO auth | Release | Post-rollback |
| RR-18 | Missing mandatory metrics / blind canary | L | H | M→H | Pre-arm checklist NO-GO if gaps | SRE | Pre-arm |
| RR-19 | CM + EM raised same day without interaction review | L | H | M→H | Prefer sequential pilots; dual-raise needs explicit PO | Release | Pilot phase |
| RR-20 | Definitive `ENABLE_LANGGRAPH_STATE` / full EM master ON mistaken for PGR-06 | L | Crit | M→Crit | PGR-06 ≠ full-env Activation; separate PO | Board / PO | At 100% |

---

## 3. Residual register (carried from Stage 2 — untreated here)

| ID | Residual | Status | Rollout implication |
|----|----------|--------|---------------------|
| R-EM-01 | Mirror Drift `aurora/` ↔ `artifacts/aurora/` | **OPEN** | Blocks >pilot / full-env until Mission 047 or Board waiver |
| R-EM-02 | `copilot_engine` PRESENT | **PRESENT** | Track share; do not invent retirement |
| R3 | Definitive Activation | **NOT STARTED** | Separate from Prod-PGR ladder strategy |
| R4 | Tool Use / Orchestration | **NOT STARTED** | Out of scope |
| R5 | Production Rollout execution | **NOT STARTED** | Strategy only in 046 |

---

## 4. Risk heat (armed without controls)

```text
Crit : RR-01, RR-02, RR-06, RR-09, RR-11, RR-20
H    : RR-03, RR-04, RR-05, RR-07, RR-08, RR-10, RR-12, RR-14, RR-15, RR-16, RR-17, RR-18, RR-19
M    : RR-13
L    : (none material once armed poorly)
```

**With strategy followed + Mirror dispositioned:** residual risk expected **L–M** during pilot, rising only if metrics ignored.

**With defaults OFF (current):** end-user risk **LOW**; process risk if someone arms early **HIGH**.

---

## 5. Go / No-Go risk gates

| Decision | NO-GO if |
|----------|----------|
| Start Pilot 1% | Mandatory metrics missing; rollback drill FAIL; no PO auth; deploy SoT unclear |
| Raise >1% | Mirror Drift still OPEN without Board waiver; prior window metrics abort/warn unresolved |
| Raise to 100% | Any Crit risk open untreated; quality sample incomplete |
| Production Accepted | Mirror not RESOLVED/waived; 7-day hold incomplete; Sev-1 in hold window |
| Any raise | Previous rollback without RCA + new PO auth |

---

## 6. Escalation

| Trigger | Escalate to |
|---------|-------------|
| Abort metric trip | SRE on-call → Release Manager → PO |
| Wrong-tree / Mirror incident | Release + Board; freeze all raises |
| Governance violation (arm without PO) | Immediate 0%; Board review |
| Shadow write violation | Sev-1; Eng + Board |

---

## 7. Explicit non-treatments (Mission 046)

This risk matrix **does not**:
- Resolve Mirror Drift  
- Retire `copilot_engine`  
- Arm or disarm flags  
- Start Mission 047+  
- Change product code  

Treatment owners act only after **formal PO authorization**.
