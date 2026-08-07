# AURORA — IMPLEMENTATION PLAN — Execution Manager

**MISSION ID:** `execution_manager_impl_plan_028`  
**DOCUMENT:** `EXECUTION_MANAGER_IMPLEMENTATION_PLAN.md`  
**RECORD ID:** IMPL-PLAN-028  
**VERSION:** 1.0  
**DATE:** 2026-08-07  
**BRANCH:** `feat/aurora-response-selector-001`  
**CLASS:** IMPLEMENTATION_PLANNING / OPERATIONAL_EXECUTION_PLAN (documentation only)  
**ROLE:** Engineering Lead / Software Architect / Release Manager / Technical Program Manager  

**Architecture defendant (APPROVED):** `observations/execution_manager_spec_revision_025/SPEC_EXECUTION_MANAGER_v1.1.md`  
**Board approval (architecture → planning only):** `observations/execution_manager_aar_027/EXECUTION_MANAGER_AAR_001.md` (`STATUS: APPROVED`)  
**Hostile reviews:** CDR-001 (`…_cdr_024`) + CDR-002 (`…_cdr2_026`) — 0 Critical / 0 High at AAR entry  
**Pattern reference (phases/PGR discipline only — do NOT copy CM code):** Mission 016 / Plan 014 Context Manager  

**Code SoT (when eventually authorized):** `artifacts/aurora/`  
**This deliverable:** documentation only — **NO product code**, NO Spec/ADR/Master/Blueprint/SSOT edits, NO Readiness start, NO implementation start.

**Nenhuma alteração de código: SIM**

---

## Status lock (binding)

| Gate | State |
|------|--------|
| Spec EM v1.1 architecture | **APPROVED** (AAR-001) for Implementation Planning |
| This Implementation Plan | **DRAFT / PENDING PO APPROVAL** — not yet executable authority |
| Readiness Review | **NOT STARTED** |
| Product code / EM implementation | **BLOCKED** |
| Production-affecting flags | Must remain **OFF / 0%** until gated Activation after all gates |

**IMPLEMENTAÇÃO permanece BLOQUEADA** until **all** of the following are true:

1. This plan is **approved** by Product Owner / Release Manager sign-off.  
2. This plan is **Git-versioned** on the governed branch (this commit satisfies versioning; PO approval still required).  
3. **Product Owner** issues **formal authorization** to execute the plan (AAR-001 ≠ code auth).  
4. Recommended gate **Readiness Review** completes green (or explicit waiver with owner/scope/expiry) **before first product code**.

**Forbidden shortcuts:** AAR-001 APPROVED → code; this plan alone → code; skip Readiness without recorded waiver; EM CM write; LLM step selection; big-bang mega-router cut-over.

**Next recommended gate (do not start unless asked):** Readiness Review → then Phase 1 Prep first code behind flags (defaults OFF).

---

## 1. Executive Summary

This plan operationalizes Spec **Execution Manager v1.1** into phased engineering work under the locked Mission 022 family:

```text
Deterministic Sequential Pipeline
+ Step Runner
+ Shadow-first
+ Context Manager write-free
+ Tool Use separado
```

**EM role (one sentence):** thin Step Runner that coordinates declared sports/report pipelines (`analyze` / `live` / thin reports / `live_team_analyze`), invokes Tool Use ports and Frozen engines in fixed order, returns structured results with step traces, and never owns intent routing, Tool Registry, or Context Manager writes.

**Primary migration strategy:** Flag-gated **Shadow → Progressive Extraction (shim window) → Progressive Activation (PGR-01..06)** — single-deploy / Replit-compatible cut-over, not blue/green dual fleet. All production flags **OFF by default**. Zero User Impact until gates are explicitly armed.

**CM Mission 016 pattern reused for:** phase ladder, PAR/PGR discipline, One Gate One Decision, Dual Reporting close, defaults OFF. **Not reused:** CM sole-writer code, STS funnel, LangGraph host, CM feature-flag names, or any Context Manager product paths.

No new ADRs. Architectural family **UNCHANGED**. Residuals CDR2-M-001 / L-001 / L-002 closed here as Plan hygiene (§3).

---

## 2. Objetivos da Implementação

| ID | Objetivo |
|----|----------|
| IO1 | Deliver Spec-compliant **Execution Manager** behind flags — extract EM-equivalent behaviour from mega-router `_run_*`, not a greenfield rewrite of Frozen engines. |
| IO2 | Preserve **soft-analyze / integrity culture** (§5.2.1) and Orchestration wrap (§4.6–§4.7). |
| IO3 | Enforce **CM write-free** (G1): never `_save_analysis_context` / STS / episode / live `last_*` seed from EM. |
| IO4 | Invoke **Tool Use via ports only** (FetchFixture / FetchLiveFeed / BudgetGate.may_run); no Tool Registry inside EM. |
| IO5 | **Shadow-first** dual-run vs legacy unified `_run_*` (Appendix A keys); fail-open; primary remains legacy until sole-path gated. |
| IO6 | **Progressive Extraction** of pipelines in declared order with Router shims; dual-SoT window honest until retirement mission. |
| IO7 | **Progressive Activation** PGR-01..06 (1→5→10→25→50→100); One Gate, One Decision; Auto-advance = False. |
| IO8 | Leave **Frozen engines** consume-only; greeting/help/identity/capabilities/fallback stay Router; no `attach_match_card` in EM. |
| IO9 | Keep deploy SoT = `artifacts/aurora/`; open `aurora/` mirror drift = **Activation NO-GO** (honesty residual OK at FA if documented). |
| IO10 | Pre-declare **legacy** `copilot_engine` / `/aurora/chat` retirement as a **separate later mission** — not Shadow peer for unified clients. |

---

## 3. Plan hygiene — residual closures (from AAR / CDR-002)

These are **contract closures for implementers**, not Spec edits and not architectural reopen.

### 3.1 CDR2-M-001 — HARD-ABORT Result terminal mapping (**CLOSED**)

| Decision | Binding for implementation |
|----------|----------------------------|
| **Chosen mapping** | HARD-ABORT → `ExecutionResult.status = Completed` + blocked/INVALID payload shape ≡ today’s `_blocked_*` / successful HTTP INVALID contract + `abort_reason = integrity_invalid_hard_abort` |
| **A2 step_traces** | Record A2 as `failed` or terminal gate with reason `integrity_invalid_hard_abort` (observability), while Result status remains `Completed` for HTTP compatibility |
| **When to use `Failed`** | Unrecoverable Step Runner / Tool Use / timeout-escalation paths **other than** integrity HARD-ABORT INVALID contract; or Interrupted→Failed policy after exhausted Retry with new `run_id` |
| **SoT snapshot requirement (Prep)** | Capture golden `_blocked_*` payload keys from `copilot_unified_router` / integrity helpers before Infra contracts freeze |

**Rationale:** Matches AAR recommendation and today’s client-visible INVALID contract (successful response with blocked payload), avoiding dual posture drift during Shadow compare.

### 3.2 CDR2-L-001 — `fixture_quality` closed enum (**CLOSED**)

Closed set for EM Result / compare (from SoT culture; Plan may document aliases but must not invent new product meanings):

| Value | Meaning (Plan) |
|-------|----------------|
| `VALID` | Integrity / quality pass |
| `PARTIAL` | Known teams / partial culture — soft-continue |
| `INVALID` | Fiction / blocked integrity |
| `VALID_LOCATED` | Soft-skip rescue located fixture (debug/culture marker when present) |

Ellipsis in Spec §4.3 is **replaced for Plan purposes** by this closed set. Unknown SoT strings discovered in Prep → inventory + allowlist amendment under Readiness — do not silently drop Appendix A integrity keys.

### 3.3 CDR2-L-002 — T0 live-team ownership (**CLOSED**)

| Stage | Owner |
|-------|-------|
| T0 `search_live_for_team` | **EM Step Runner stage** invoking **Tool Use** live-list port |
| Historical cite `L3949–4064` | Location in mega-router **today** — extraction target, not permanent Orchestration ownership |
| CM ctx seed on live opportunities | **Out of EM** (NR1 / §4.7) |

### 3.4 Optional hygiene (non-blocking)

- Refine Appendix B step×fail-open **line-level snapshots** from SoT during Prep/Infra (must not change §5.2.1).  
- Finalize env flag **names** under §12.1 principles (§8 of this Plan).

---

## 4. Phase model — Blueprint alignment + EM adaptation

### 4.1 Official phase list

| Phase | Name | Blueprint §5.1 analogue | EM adaptation justification |
|-------|------|-------------------------|------------------------------|
| **1** | Preparation | Prep | Unchanged |
| **2** | Infrastructure | Infra | Unchanged — contracts / Step Runner scaffold / illegal matrix / tests; flags OFF |
| **3** | Shadow | Shadow | Unchanged — observe-only dual-run; CM eligibility always NO |
| **4** | Progressive Extraction | Blueprint “Sole Writer” | **Adapted:** EM is **CM write-free** — Phase 4 extracts `_run_*` into EM with **Router shim** and gated sole-path flags (Spec §12 “Sole path”), not a subject sole-writer funnel |
| **5** | Progressive Activation | Gated Activation (PGR) | Unchanged — PGR-01..06 ladder only |
| **6** | Stabilization | Stabilization | Unchanged — trust defaults-OFF SoT; not definitive Activation |
| **7** | Final Acceptance | FA | Numbered as Phase 7 for EM program clarity (Blueprint FA remains docs gate after Phase 6) |

```text
Blueprint: Prep → Infra → Shadow → Sole Writer → PGR → Stabilization → FA
EM Plan:   Prep → Infra → Shadow → Progressive Extraction → PGR → Stabilization → FA
                 (Phase 4 = extract + shim + sole-path OFF default;
                  not CM Sole Writer)
```

**Reference only:** CM Mission 016 Phases 1–6 + PGR-01..06 gate discipline. Do not copy CM modules.

### 4.2 Mapping Spec §12 → this Plan

| Spec §12 | This Plan |
|----------|-----------|
| 1 Prep | Phase 1 |
| 2 Infra | Phase 2 |
| 3 Shadow | Phase 3 |
| 4 Sole path (gated) | Phase 4 Progressive Extraction (culminates in sole-path **capability** behind flags OFF) |
| 5 PGR ladder | Phase 5 |
| 6 Stabilization | Phase 6 |
| FA | Phase 7 |

---

## 5. Pré-requisitos

| # | Prerequisite | Evidence |
|---|--------------|----------|
| PR1 | Spec v1.1 architecturally APPROVED | AAR-001 |
| PR2 | CDR-002 Critical/High = 0 | CDR2 READY FOR AAR |
| PR3 | Residuals M-001/L-001/L-002 closed in Plan | §3 this document |
| PR4 | This plan PO-approved + Git-versioned | Board / PO |
| PR5 | Product Owner formal **execution** authorization | Signed auth (scope, flags allowed, expiry) |
| PR6 | Readiness Review green (recommended) | Checklist: flags OFF; deploy tree; Frozen registry; harness; mirror-drift |
| PR7 | Code SoT = `artifacts/aurora/` | Audit / Master §9 |
| PR8 | Illegal flag principles fail-closed; defaults OFF | Spec §12.1 / this Plan §8 |
| PR9 | CM remains FROZEN sole-writer boundary | CM FA / Spec G1 |
| PR10 | No ADR required (family locked) | Mission 022 + AAR |

**Explicit:** PR1–PR3 alone do **not** unlock code. PR4–PR5 (+ recommended PR6) mandatory before Phase 1 product work.

---

## 6. Escopo

### 6.1 In scope (future implementation missions — not this docs mission)

1. New EM package under `artifacts/aurora/src/` (Step Runner, contracts, pipelines, ports adapters).  
2. Flag / migration-stage controller + illegal matrix boot asserts.  
3. Shadow harness dual-invoking EM vs legacy `_run_*` (Appendix A).  
4. Progressive extraction of `_run_analyze` / `_run_live` / thin / `live_team_analyze` with Router shims.  
5. Orchestration wrap preservation (soft-try, post-assess, CM eligibility outside EM).  
6. PGR-01..06 percentage ladder for EM sole-path traffic.  
7. Observability events (`em.run.*` / `em.step.*` / `em.shadow.diff`).  
8. Tests per Spec §15 + regression on legacy path while flags OFF.  
9. Stabilization + Final Acceptance docs under AEL.

### 6.2 Out of scope

| ID | Out |
|----|-----|
| OOS1 | Product code in Mission 028 |
| OOS2 | Spec / ADR / Master / Blueprint / SSOT edits |
| OOS3 | Readiness / Implementation start in this mission |
| OOS4 | EM owning CM writes / `_save_analysis_context` |
| OOS5 | EM Tool Registry / raw API clients / `begin_request` |
| OOS6 | `attach_match_card` inside EM |
| OOS7 | Greeting/help/identity/capabilities/fallback → EM |
| OOS8 | Rewriting Frozen engine formulas or A3–A10 order |
| OOS9 | LLM / hierarchical manager as analyze controller |
| OOS10 | Forced deletion of legacy `copilot_engine` inside Stabilization |
| OOS11 | Mirror-drift “RESOLVED” invention |
| OOS12 | Bundling multiple PGR gates or FA with PGR-06 |
| OOS13 | Copying Context Manager product code |

### 6.3 Impact inventory (expected files — future)

**Created (authorized only after Readiness + Phase code missions):**

| Artifact (expected) | Role |
|---------------------|------|
| `artifacts/aurora/src/execution_manager/` (or equivalent package) | Step Runner + pipelines |
| `…/contracts.py` (or typed models) | ExecutionRequest / ExecutionResult / step_traces |
| `…/ports.py` | FetchFixture / FetchLiveFeed / BudgetGate / Engine / Db read adapters |
| `…/pipelines/analyze.py` | A0–A13 |
| `…/pipelines/live.py` | L0–L4 |
| `…/pipelines/thin_reports.py` | bankroll / learning / knowledge |
| `…/pipelines/live_team_analyze.py` | T0–T1 |
| `…/shadow.py` | shadow_compare + Appendix A differ |
| `…/flags.py` / migration controller | Illegal matrix + PGR ladder |
| Tests under `artifacts/aurora/tests/` | Contract / gate / shadow / boundary / regression |

**Altered (evolve carefully):**

| Path | Change class |
|------|--------------|
| `artifacts/aurora/src/routers/copilot_unified_router.py` | Thin shims: call EM when flags allow; keep soft-try wrap + CM eligibility + presentation; `_run_*` become shims or dual-run peers |
| Flag / env surface (existing helpers if any) | EM flags OFF default |

**Preserved (untouched internals):**

| Asset | Policy |
|-------|--------|
| Frozen sports engines | Consume-only |
| Context Manager / STS / LangGraph host | Orthogonal; write-free from EM |
| Tool Use clients / registry | Ports only from EM |
| Router conversational `_run_greeting|help|identity|capabilities|fallback` | Stay Router |
| `communication.attach_match_card` | Router only |
| `cost_protection.begin_request` / `end_request` | Router / ops |

---

## 7. Mega-router extraction order

### 7.1 What moves to EM vs what stays on Router

| Surface | Destino | Notes |
|---------|---------|-------|
| `_run_analyze` body (engines + assembly) | **EM** `analyze` | Soft-analyze A2 must-stay |
| `_run_live` | **EM** `live` | Ports + live engine |
| `_run_bankroll` / `_run_learning` / `_run_knowledge` | **EM** thin | Db.port read adapters |
| `live_team_analysis` bridge → analyze | **EM** `live_team_analyze` | T0 Tool Use + T1 analyze |
| Soft-try precheck / post-assess / CM eligibility | **Orchestration** | §4.6–§4.7 |
| `_save_analysis_context` / live `last_*` seed | **CM** | Never EM |
| `attach_match_card` | **Router** | EM emits fields only (A13/L4) |
| `_run_greeting|help|identity|capabilities|fallback` | **Router** | Explicitly NOT EM |
| `begin_request` / `end_request` | **Router/ops** | EM consults budget_token only |
| `copilot_engine` / `/aurora/chat` | **Legado** | Parallel until retirement mission |

### 7.2 Progressive Extraction order (Phase 4 waves)

Order grounded in Mission 021 Destino Futuro + risk (thin → live → analyze → composite):

| Wave | Extract first | Why |
|------|---------------|-----|
| **E0** | Package scaffold + contracts + ports mocks | Infra carry-over; no behaviour change |
| **E1** | Thin: `bankroll` → `learning` → `knowledge` | Smallest surface; no Frozen sports engines; proves Db.port + Step Runner + shim pattern |
| **E2** | `live` | Medium; Tool Use FetchLiveFeed + single Frozen live engine; Shadow keys thinner |
| **E3** | `analyze` | Highest value + highest risk; Frozen A3–A10 order locked; soft-analyze golden cases mandatory before sole-path |
| **E4** | `live_team_analyze` | Depends on E3 analyze + T0 Tool Use; last composite |

**Shadow (Phase 3) may start dual-run against analyze/live baselines even before E3 sole-path**, using Infra scaffolding — Shadow observes EM candidates without routing production traffic.

### 7.3 Compatibility & regression avoidance

| Rule | Practice |
|------|----------|
| Flags OFF | Legacy `_run_*` remains primary; existing tests green |
| Shim | When pipeline flag ON, Router calls `EM.run`; when OFF, legacy body |
| Dual-SoT window (G6) | Official executor = EM only when sole-path armed; `_run_*` may remain as shim until retirement |
| Shadow peer | **Unified** `_run_*` only — never `copilot_engine` as Shadow substitute |
| Soft-analyze | Absolute INVALID abort forbidden; golden cases 1–5 must pass before E3 sole-path |
| Match card | Strip `attach_match_card` from extracted body; Router post-EM |
| CM | Assert no subject write from EM package (boundary tests) |

### 7.4 What stays in mega-router during / after extraction

- HTTP binding, session, personality / credibility presentation  
- Intent / Understanding / `sport_pipeline_blocked`  
- Orchestration wrap (soft-try, prefer_live derivation, post-integrity, CM eligibility call)  
- Conversational `_run_*` (greeting/help/…)  
- Thin shim stubs calling EM  
- Legacy retirement deferred to dedicated mission

---

## 8. Feature flags (all OFF by default)

Final env names (Plan closure of Spec §12 deferred names). Production-affecting defaults = **OFF / 0%**.

| Flag | Default | Purpose |
|------|---------|---------|
| `ENABLE_EXECUTION_MANAGER_SHADOW` | **OFF** | Dual-run observe-only; fail-open |
| `ENABLE_EXECUTION_MANAGER` | **OFF** | Master sole-path allow (still needs pipeline + PGR) |
| `ENABLE_EM_PIPELINE_BANKROLL` | **OFF** | Route bankroll via EM |
| `ENABLE_EM_PIPELINE_LEARNING` | **OFF** | Route learning via EM |
| `ENABLE_EM_PIPELINE_KNOWLEDGE` | **OFF** | Route knowledge via EM |
| `ENABLE_EM_PIPELINE_LIVE` | **OFF** | Route live via EM |
| `ENABLE_EM_PIPELINE_ANALYZE` | **OFF** | Route analyze via EM |
| `ENABLE_EM_PIPELINE_LIVE_TEAM` | **OFF** | Route live_team_analyze via EM |
| `ENABLE_EM_PGR_01` … `ENABLE_EM_PGR_06` | **OFF** | Independent ladder gates (1/5/10/25/50/100) |
| `EM_ACTIVATION_PCT` | **0** | Configured percentage; effective pct requires prior PGR armed |

### 8.1 Illegal combinations (fail-closed boot / runtime assert)

| ID | Illegal |
|----|---------|
| I1 | Sole-path ON without Shadow evidence recorded for that pipeline (Readiness/PAR gate — operator policy) |
| I2 | Same flag meaning both Shadow-only and sole-path without dual-run harness |
| I3 | Any flag authorizing EM CM sole-write (**nonexistent capability** — hard reject if attempted) |
| I4 | Shadow path that can pass §4.7 YES / write subject |
| I5 | Using `copilot_engine` as Shadow peer for unified clients |
| I6 | `EM_ACTIVATION_PCT > 0` without corresponding PGR gate armed |
| I7 | Bundled auto-advance PGR-N → PGR-N+1 |
| I8 | Production defaults ON in repo |

### 8.2 Instant rollback helpers (to implement in Infra+)

| Helper | Effect |
|--------|--------|
| `rollback_em_shadow_off()` | `ENABLE_EXECUTION_MANAGER_SHADOW=0` |
| `rollback_em_sole_path_off()` | Master + all pipeline flags OFF; pct→0 |
| `rollback_em_pgrXX_to_off()` | Clear that PGR + clamp pct to prior plateau / 0 |

---

## 9. Phases — detailed contracts

---

### Phase 1 — Preparation

**Objective:** Governance unlock, baselines, residual labeling, harness inventory — **no user impact**.

**Scope:**
- Confirm PR4–PR6 (plan approval, PO exec auth, Readiness).  
- Capture golden baselines of legacy `_run_analyze` / `_run_live` / thin payloads (Appendix A keys).  
- Snapshot `_blocked_*` HARD-ABORT shape (M-001).  
- Inventory call sites and Destino Futuro (021) checklist.  
- Mirror-drift status note (`artifacts/aurora/` vs `aurora/`).  
- Confirm all EM flags absent or OFF.  
- Label Activation residuals (legacy copilot_engine present; mirror drift).

**Expected files (docs/harness only in Prep; code only after auth):**
- Observation/readiness checklists under later readiness mission  
- Baseline JSON fixtures under `observations/` or `artifacts/aurora/tests/` fixtures (when code authorized)

**Entry criteria:** PO approved this Plan; exec auth issued; Readiness green or waived.  
**Exit criteria (PAR-1):** Baselines captured; residuals labeled; flags OFF confirmed; no product behaviour change; Board confirms no ADR needed.

**Risks:** Treating AAR as code auth; editing Spec; starting extraction early.  
**Rollback:** Revert Prep docs/commits; no runtime flags to clear.  
**Tests:** Inventory scripts / baseline capture reproducibility (no product mutation).  
**Observability:** N/A runtime.  
**Flags:** All OFF / absent.

---

### Phase 2 — Infrastructure

**Objective:** Contracts, Step Runner scaffolding, ports, illegal matrix, unit tests — flags OFF; **no production routing**.

**Scope:**
- `ExecutionRequest` / `ExecutionResult` / closed `status` enum / `fixture_quality` closed set (§3.2).  
- Step Runner core + pipeline stubs (analyze/live/thin/live_team).  
- Ports: FetchFixture, FetchLiveFeed, BudgetGate.may_run, Engine.port, Db.port (read adapters).  
- Flag controller + I1–I8 fail-closed.  
- HARD-ABORT → Completed+blocked mapping wired in analyze stub.  
- Boundary lints/tests: forbid `_save_analysis_context`, `attach_match_card`, `begin_request` in EM package.  
- Optional post-Infra: `cancel(run_id)` deferred (CDR-M-002) — **not required**.

**Expected files:** EM package + flag controller + unit tests (paths §6.3).

**Entry:** PAR-1.  
**Exit (PAR-2):** Contract/order/gate unit tests green; defaults OFF; no Router sole-path wiring required yet (may add dead hooks OFF).

**Risks:** Coupling EM to CM host checkpointer; inventing Tool Registry; enabling flags early.  
**Rollback:** Disable package imports behind flags; revert Infra commits; flags OFF.  
**Tests:** Contract; A3–A10 order snapshot; §5.2.1 golden 1–3 on stubs; illegal matrix; boundary negative tests.  
**Observability:** Structured logging hooks for `em.step.*` (may be no-op sinks).  
**Flags:** Defined, default OFF.

---

### Phase 3 — Shadow

**Objective:** Dual-run observe-only EM vs legacy unified `_run_*`; fail-open; **Zero User Impact**.

**Scope:**
- `EM.shadow_compare` / dual-invoke from Orchestration hook when `ENABLE_EXECUTION_MANAGER_SHADOW=1`.  
- Primary path = legacy `_run_*`.  
- Appendix A mandatory keys + noise allowlist.  
- §4.7 always NO for shadow; no CM write.  
- Metrics: parity rate, diff counts, fail-open count, per-pipeline coverage.  
- Disable path: `rollback_em_shadow_off()`.

**Shadow behaviour:**
1. On eligible pipeline request, run legacy primary.  
2. Best-effort run EM in `mode=shadow` with same logical inputs.  
3. Compare; emit `em.shadow.diff`; never replace primary.  
4. Shadow exception → log + continue primary.

**Entry:** PAR-2.  
**Exit (PAR-3):** Shadow evidence for thin + live + analyze (as available); fail-open proven; CM write absent; Appendix A keys not dropped.

**Risks:** Shadow latency; false diffs from noise; accidental sole-path enable.  
**Rollback:** Shadow flag OFF — instant, no user impact.  
**Tests:** Shadow harness; fail-open injection; CM eligibility NO assert; compare-key presence.  
**Observability:** `em.shadow.diff`, parity dashboards/logs.  
**Flags:** Only Shadow may be operator-armed in non-prod; repo default OFF.

---

### Phase 4 — Progressive Extraction (mega-router `_run_*`)

**Objective:** Move pipeline bodies into EM behind **pipeline flags OFF by default**; legacy becomes shim; sole-path **capability** exists but master/PGR remain OFF until Phase 5.

**Scope (waves E1→E4):**
- E1 thin reports extraction + shims.  
- E2 live extraction + shim.  
- E3 analyze extraction + soft-analyze preservation + strip match_card.  
- E4 live_team_analyze composite (T0 EM+Tool Use).  
- Dual-SoT window honesty documented (G6).  
- Orchestration wrap stays outside EM.  
- PAR after each wave recommended (or single PAR-4 with wave checklist — PO chooses; default **wave PARs** for analyze).

**Entry:** PAR-3 (Shadow credible for pipelines being sole-path-enabled later).  
**Exit (PAR-4):** All EM pipelines extractable via flags; defaults OFF; legacy shim works; regression green on OFF path; boundary tests green; soft-analyze golden 1–5 green on EM path in test harness.

**Risks:** Behaviour drift vs legacy; soft-analyze regression; CM contamination; match_card leakage into EM.  
**Rollback:** Pipeline flags OFF → legacy bodies; sole-path OFF.  
**Tests:** Per-pipeline parity vs golden; integration analyze/live; compatibility of HTTP payload shape; non-regression with flags OFF.  
**Observability:** `em.run.*` / `em.step.*` on EM path (when exercised in tests/non-prod).  
**Flags:** Pipeline flags exist default OFF; `ENABLE_EXECUTION_MANAGER` default OFF.

---

### Phase 5 — Progressive Activation (PGR-01..06)

**Objective:** Climb traffic percentage to EM sole-path with **One Gate, One Decision**.

| Gate | Pct | Mission rule |
|------|-----|--------------|
| PGR-01 | 1% | ONLY 1% |
| PGR-02 | 5% | ONLY 5% |
| PGR-03 | 10% | ONLY 10% |
| PGR-04 | 25% | ONLY 25% |
| PGR-05 | 50% | ONLY 50% |
| PGR-06 | 100% | ONLY 100% — do **not** start Stabilization in same mission |

**Scope each PGR:** Arm prior plateau validation; authorize one gate; rollback helper; Dual Reporting; await PO before next.

**Entry:** PAR-4 + PO auth for Activation climb.  
**Exit:** PGR-06 implemented (default OFF; operator-armed 100% path) + PO approval before Phase 6.

**Risks:** Bundling gates; climbing without Shadow evidence; mirror drift ignored.  
**Rollback:** `rollback_em_pgrXX_to_off()` → prior plateau / 0%.  
**Tests:** Plateau re-run prior suites; activation pct math; illegal I6/I7.  
**Observability:** Effective pct, error rate vs legacy, shadow residual diffs.  
**Flags:** PGR flags OFF default; pct 0 default.

**Auto-advance:** **False**. REGRA 27/28 binding.

---

### Phase 6 — Stabilization

**Objective:** Trust question for gated / defaults-OFF SoT — **not** definitive full-env Activation.

**Scope:**
- Observability posture; validation suite green at defaults OFF.  
- Confirm rollback drills.  
- Document Activation NO-GOs (mirror drift, legacy retirement not done).  
- **Do not** force-delete legacy `_run_*` bodies or `copilot_engine`.  
- **Do not** flip repo defaults ON.

**Entry:** PGR-06 PO-approved.  
**Exit:** Stabilization SUCCESS (gated trust) with honesty residuals listed.

**Risks:** Claiming Activation complete; deleting legacy prematurely.  
**Rollback:** Flags OFF / 0%.  
**Tests:** Full EM suite + legacy OFF-path regression.  
**Observability:** Stabilization complete flags (docs/ops), not user-facing change.  
**Flags:** Defaults remain OFF.

---

### Phase 7 — Final Acceptance

**Objective:** Close EM AEL cycle per Spec §16 Frozen criteria F1–F14 (docs/governance). Declare residuals / Activation NO-GOs explicitly.

**Scope:** Dual Reporting; FA verdict APPROVED/FROZEN **for implementation cycle** vs Activation still blocked if drift OPEN; await PO; **do not auto-start** next module.

**Entry:** Phase 6 SUCCESS.  
**Exit:** FA record published; Master/Blueprint untouched; product defaults OFF unless separate Activation mission.

**Risks:** Silent Master rewrite; claiming Substitution complete without Activation auth.  
**Rollback:** Docs revert.  
**Tests:** Evidence package completeness checklist.  
**Observability:** N/A.  
**Flags:** Unchanged OFF unless separate governed Activation.

---

## 10. Shadow — behaviour, metrics, compare, disable

| Topic | Plan |
|-------|------|
| **Behaviour** | Dual-run; primary = legacy; EM `mode=shadow`; fail-open; no CM write |
| **Compare** | Appendix A mandatory keys; noise allowlist extensible in Infra without dropping mandatory keys |
| **Metrics** | Runs shadowed, parity %, hard diffs, soft noise diffs, shadow errors, p95 shadow latency |
| **Disable** | `ENABLE_EXECUTION_MANAGER_SHADOW=0` / `rollback_em_shadow_off()` |
| **Host** | Separate from CM LangGraph STS graph |
| **Peer** | Unified `_run_*` only |

---

## 11. Rollback matrix

| Layer | Trigger criteria (examples) | Action |
|-------|----------------------------|--------|
| **Per-phase** | PAR fail; critical regression in phase scope | Revert phase commits; flags OFF for that phase surface |
| **Shadow** | Shadow error storm; latency budget exceed | Shadow OFF — no user impact |
| **Pipeline flag** | Parity fail for one pipeline | That `ENABLE_EM_PIPELINE_*=0` |
| **PGR** | Error-rate / integrity regression vs plateau | `rollback_em_pgrXX_to_off()` |
| **Global sole-path** | Multi-pipeline user-visible break | `ENABLE_EXECUTION_MANAGER=0` + all pipeline OFF + pct 0 |
| **Global EM kill** | Suspected CM write from EM; soft-analyze break; Frozen order change | Global OFF + STOP + architecture reopen process if needed |
| **Docs** | Plan error | Revert docs commit under `observations/execution_manager_impl_plan_028/` |

**Forbidden rollbacks:** Reopening CM writers inside EM; “fixing” Frozen formulas; dropping §5.2.1 soft-analyze.

---

## 12. Test strategy

| Class | When | Intent |
|-------|------|--------|
| **Unit** | Phase 2+ | Contracts, order A3–A10, integrity edges, flags matrix, ports mocks |
| **Integration** | Phase 3–4 | Router shim → EM; soft-try wrap; thin/live/analyze payloads |
| **Shadow** | Phase 3+ | Appendix A compare; fail-open; CM NO |
| **Regression** | All phases | Existing analyze/live tests green with flags OFF |
| **Compatibility** | Phase 4+ | HTTP CopilotResponse shape; blocked INVALID contract (M-001); match_card still Router |
| **Boundary / negative** | Phase 2+ | No CM write / no attach_match_card / no begin_request / no LLM router in EM |
| **PGR / plateau** | Phase 5 | Prior gate suites re-green before raise |
| **Golden soft-analyze** | Before E3 sole-path | Spec §5.2.1 cases 1–5 |

---

## 13. Observability

Mandatory signals (Spec §10) when EM path runs:

- `run_id` / `pipeline_id` / `mode`  
- Per-step timing + status + skip/fail reasons (incl. `integrity_soft_skip_fixture_located`)  
- Budget/cache metadata from ports  
- Shadow diff handle  
- Correlation `session_id` + `trace_parent` without subject write  

Events: `em.run.*`, `em.step.*`, `em.shadow.diff`, `em.retry.scheduled`.

---

## 14. Governance confirmation (Plan-time)

| Constraint | Confirmation |
|------------|--------------|
| **SSOT** | Plan under `observations/`; Code SoT remains `artifacts/aurora/`; no Spec-as-Master |
| **Blueprint** | Ladder reused; Phase 4 adapted (Extraction vs Sole Writer) with justification §4 |
| **Master** | Pillar #11 RO Substituir — Plan does **not** rewrite Master; code still gated |
| **Frozen Engines** | Consume-only; A3–A10 order change = ARCHITECTURAL DECISION REQUIRED |
| **CM** | Write-free confirmed; eligibility outside EM; Shadow NO |
| **Tool Use** | Ports only; independent registry; T0 Tool Use from EM stage |
| **Rules 19–29** | Controlled path; ZUI; Progressive Activation; PGR; Window; One Gate; Plateau; Dual Reporting |
| **AEAP** | Level 1 per phase/gate budgets at implementation time |
| **Legacy** | `copilot_engine` retirement pre-declared separate; not Shadow peer |
| **Mirror drift** | Activation NO-GO while OPEN |

---

## 15. Go / No-Go summary

| Gate | Go when | No-Go when |
|------|---------|------------|
| Start Readiness | This Plan PO-approved | Plan rejected / architecture reopen |
| Start Phase 1 code | Readiness green + exec auth | Auth missing; Spec reopen |
| Start Shadow arming | PAR-2 + harness ready | Contract tests red |
| Start Extraction E3 analyze | Soft-analyze goldens green | Absolute-abort regression |
| Start PGR-01 | PAR-4 + Shadow evidence | Sole-path without Shadow |
| Start Phase 6 | PGR-06 PO YES | Bundled with PGR-06 |
| Definitive Activation | Separate mission + drift closed/waived | Drift OPEN silent claim |
| FA FROZEN cycle | F1–F14 evidence | Missing Dual Reporting / honesty residuals |

---

## 16. Explicit non-starts (this mission)

| Item | Status |
|------|--------|
| Product code | **NOT STARTED** |
| Readiness | **NOT STARTED** |
| Spec / ADR / Master / Blueprint / SSOT edits | **NOT DONE** |
| Shadow / sole-path / PGR arming | **NOT DONE** |
| Next module auto-start | **FORBIDDEN** |

---

## 17. Handoff

```text
Await Product Owner acceptance of EXECUTION_MANAGER_IMPLEMENTATION_PLAN (Mission 028).
Do NOT start Readiness or product code until PO authorizes.
Nenhuma alteração de código: SIM
```

**Recommended next (PO-gated):** Readiness Review → Phase 1 Preparation (first code behind flags OFF).

---

*End of EXECUTION_MANAGER_IMPLEMENTATION_PLAN.md*
