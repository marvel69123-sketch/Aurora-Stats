# AURORA — SPECIFICATION — Execution Manager v1.0

**MISSION ID:** `execution_manager_spec_023`  
**DOCUMENT:** `SPEC_EXECUTION_MANAGER_v1.0.md`  
**VERSION:** 1.0  
**DATE:** 2026-08-07  
**BRANCH:** `feat/aurora-response-selector-001`  
**CLASS:** ARCHITECTURE_SPECIFICATION (documentation only)  
**CODE SoT (future implement):** `artifacts/aurora/`  
**STATUS:** DRAFT — awaiting Product Owner acceptance  
**IMPLEMENTATION AUTHORIZATION:** **NOT AUTHORIZED**  
**CDR / Implementation:** **DO NOT START** — await PO  

**Nenhuma alteração de código: SIM**

---

## Hard scope locks

| Allowed | Forbidden |
|---------|-----------|
| Complete Spec consolidating Missions 020 / 021 / 022 | Product code |
| Public contracts, pipeline, states, shadow, PGR, Frozen criteria | ADR creation |
| Dual Reporting (REGRA 29) on Spec artifacts | Master / SSOT / Blueprint edits |
| AEAP Level 1 on Spec deliverables only | CDR, Implementation Plan, rebuild |

---

## Binding sources (cited — not reinvented)

| Source | Role |
|--------|------|
| `observations/execution_manager_discovery_020/EXECUTION_MANAGER_DISCOVERY_REPORT.md` | Absence of EM; mega-router blob; CM/Tool Use boundaries; ideal order |
| `observations/execution_surface_021/EXECUTION_SURFACE_MAP.md` | Destino Futuro; Frozen engine order; `_run_*` inventory |
| `observations/execution_surface_021/EXECUTION_SURFACE_REPORT.md` | Callers, contamination, extract candidates |
| `observations/execution_manager_research_022/EXECUTION_MANAGER_ARCHITECTURE_RESEARCH.md` | Pattern family recommendation |
| `observations/execution_manager_research_022/COMPARATIVE_ANALYSIS.md` | Framework fit / anti-patterns |
| `docs/architecture/governance/AURORA_MODULE_BLUEPRINT.md` | AEL ladder, Shadow, PGR, Dual Reporting (process law) |
| `docs/architecture/master-architecture.md` | **READ ONLY** — pillar #11 Ausente / Substituir |
| `docs/architecture/governance/DUAL_REPORTING_POLICY.md` | REGRA 29 |

---

## Architectural decision LOCKED (Mission 022 — DO NOT CHANGE)

```text
Deterministic Sequential Pipeline
+ Step Runner
+ Shadow-first
+ Context Manager write-free
+ Tool Use separado
```

**If a Spec requirement would violate this lock → emit `ARCHITECTURAL DECISION REQUIRED` and STOP.**  
This Spec does **not** reopen that decision.

---

## One-sentence Spec summary (EM role)

**The Execution Manager is the thin, deterministic Step Runner that coordinates declared sports/report pipelines (analyze / live / thin reports), invokes Tool Use ports and Frozen engines in fixed order, returns structured results with step traces, and never owns intent routing, Tool Registry, or Context Manager writes.**

---

# 1. Objetivo

| ID | Objetivo |
|----|----------|
| O1 | Establish a named **Execution Manager (EM)** pillar that owns **how** declared execution pipelines run after Orchestration decides they should run. |
| O2 | Extract EM-equivalent behaviour from `copilot_unified_router._run_analyze` / `_run_live` / thin `_run_bankroll|learning|knowledge` into a **Deterministic Sequential Pipeline / Step Runner** without rewriting Frozen engines. |
| O3 | Preserve the **Frozen analyze engine sequence** and structured analyze/live payload semantics users and clients rely on (Mission 021 surface). |
| O4 | Enforce **hard boundaries**: CM write-free; Tool Use via ports only; greeting/help/identity/capabilities/fallback remain Router. |
| O5 | Provide **step-level contracts** (`ExecutionRequest` / `ExecutionResult` / step traces) enabling Shadow dual-run parity vs legacy `_run_*`. |
| O6 | Migrate **shadow-first**, defaults OFF, Progressive Activation ladder (Blueprint §5) — Zero User Impact until gates are armed. |
| O7 | Pre-declare **legacy retirement** of `copilot_engine` / `/aurora/chat` as a separate later mission — not silent dual-SoT forever. |
| O8 | Keep Master pillar #11 substitution path governance-compatible without editing Master in this mission. |

**Non-goals of this mission document:** implementation, CDR, ADR, Blueprint/Master mutation, product behaviour change.

---

# 2. Responsabilidades

EM **owns** the following (principles from 022 + extract candidates from 021):

| ID | Responsabilidade | Grounding |
|----|------------------|-----------|
| R1 | Coordinate **declared pipelines**: `analyze`, `live`, `bankroll`, `learning`, `knowledge`, and the `live_team_analysis` bridge that ends in analyze | Surface Map Destino Futuro **EM** |
| R2 | Enforce **step order / contracts** for the Frozen sports engine sequence | `_run_analyze` L543–584 order |
| R3 | Apply **execution-local gates** (e.g. integrity INVALID early abort; PARTIAL / soft-analyze fail-open culture) as Step Runner edges | Surface Map; Discovery Q7 |
| R4 | Invoke **Tool Use ports** (`FetchFixture`, `FetchLiveFeed`, budget-aware may-run) without owning clients/cache/registry | Research 022 Q7 |
| R5 | **Consume** Frozen engines (`run` / `consult` / `generate` / `build_live_payload`) — never retune formulas | FROZEN_MODULES / Master |
| R6 | Assemble **structured ExecutionResult** (markets, confidence, stake composition helpers, DRS stamp fields as today) for Orchestration / FE | `_run_analyze` assembly |
| R7 | Provide **per-step observability**, fail-open/skip recording, and Shadow-comparable step API | Research 022 Q1 / Q11 |
| R8 | Honor ops **budget decision tokens** (“may this I/O step run?”) without absorbing `cost_protection` | Mission 021 Tool Use / ops |
| R9 | Maintain **ephemeral run scratch** (intermediate engine outputs for the run) — not conversational subject SSOT | Research 022 Q8–Q9 |
| R10 | Expose thin report pipelines (`bankroll` / `learning` / `knowledge`) as first-class EM pipelines (DB→payload sequencing) | Surface Map thin EM |

---

# 3. Não Responsabilidades

| ID | Não responsabilidade | Owner correto |
|----|----------------------|---------------|
| NR1 | Sole-write STS / episode / subject / `_save_analysis_context` / live `ctx["last_*"]` seed | **Context Manager** (FROZEN) |
| NR2 | Intent classification, Master Intent, CUE/HCE, `sport_pipeline_blocked`, conversational layer order | **Understanding / Orchestration** |
| NR3 | Greeting / help / identity / capabilities / fallback / follow-up suggestions | **Router / Orchestration** |
| NR4 | Tool Registry, permissions, raw API clients, analyze cache implementation, web agent loop | **Tool Use** / data / ops |
| NR5 | Frozen methodology / market / confidence / learning / knowledge / decision formulas | **Engines Frozen** |
| NR6 | HTTP binding, session lifecycle, response personality / credibility / match_card coerce as product UX shell | **Router** (match_card attach may remain Router adapter post-EM) |
| NR7 | LLM choosing next Frozen engine / multi-agent debate as analyze controller | **Nowhere** (anti-pattern — 022) |
| NR8 | Treating `minimal_commit_orchestrator` / LangGraph STS host as EM | **CM** |
| NR9 | Big-bang mega-router rewrite or Activation full-env in Spec alone | Blueprint AEL — later gated missions |
| NR10 | Mirror drift repair (`aurora/` vs `artifacts/aurora/`) | Activation residual — separate |

---

# 4. Interfaces Públicas (entradas / saídas / eventos / contratos)

## 4.1 Conceptual API surface (normative shape — not code)

```text
ExecutionManager.run(request: ExecutionRequest) -> ExecutionResult
ExecutionManager.shadow_compare(request: ExecutionRequest) -> ShadowCompareResult   # observe-only
```

Optional future (post-Infra, defaults OFF):

```text
ExecutionManager.get_pipeline(pipeline_id) -> PipelineDescriptor
ExecutionManager.cancel(run_id) -> CancelAck
```

## 4.2 ExecutionRequest (entrada)

| Field (logical) | Required | Description |
|-----------------|----------|-------------|
| `run_id` | yes | Unique id for this execution attempt (trace correlation) |
| `pipeline_id` | yes | One of: `analyze` \| `live` \| `bankroll` \| `learning` \| `knowledge` \| `live_team_analyze` |
| `session_id` | yes | Correlation only — **not** authorization to write subject |
| `entities` | pipeline-dependent | e.g. home/away/team for analyze/live_team |
| `flags` | no | `prefer_live`, `force_refresh`, soft-404 recovery hints from Orchestration |
| `budget_token` | no | Opaque allowance from ops / cost_protection decision |
| `read_projections` | no | Immutable-enough CM/Orchestration projections of subject (read-only) |
| `mode` | yes | `primary` \| `shadow` \| `dry_run` |
| `timeout_ms` | no | Wall-clock budget for the run |
| `trace_parent` | no | Observability parent span |

**Invariant:** Request carries **inputs**; EM does not pull mutable conversational memory as SSOT.

## 4.3 ExecutionResult (saída)

| Field (logical) | Description |
|-----------------|-------------|
| `run_id` | Echo |
| `pipeline_id` | Echo |
| `status` | See §8 (`Completed` \| `Failed` \| `Interrupted` \| … terminal) |
| `payload` | Structured result compatible with current unified Copilot analyze/live/thin contracts |
| `step_traces[]` | Ordered per-step records (id, status, duration, error/skip reason) |
| `abort_reason` | Optional (e.g. `integrity_invalid`) |
| `diagnostics` | Non-user fields (DRS stamp, data richness, engine versions if present today) |
| `shadow_meta` | Present only in shadow mode (parity flags, diff summary handle) |

**Invariant:** Result is **return-only**. No CM commit side-effect from EM.

## 4.4 Events (observability / orchestration hooks)

| Event | When | Consumers |
|-------|------|-----------|
| `em.run.started` | Enter Running | Observability |
| `em.step.started` / `em.step.completed` / `em.step.skipped` / `em.step.failed` | Each Step Runner stage | Observability / Shadow harness |
| `em.run.completed` / `em.run.failed` / `em.run.interrupted` | Terminal | Orchestration |
| `em.shadow.diff` | Shadow compare finished | Shadow harness (defaults OFF) |
| `em.retry.scheduled` | Retry policy engaged | Observability |

Events are **signals**, not CM writes.

## 4.5 Ports (outbound contracts — Tool Use / Engines)

| Port | Direction | Owner of implementation |
|------|-----------|-------------------------|
| `FetchFixture` | EM → Tool Use / data | `analyze_fixture` / analyze router / cache ops |
| `FetchLiveFeed` | EM → Tool Use / data | `live._build_live_response` |
| `BudgetGate.may_run(step)` | EM → ops | `cost_protection` decision surface |
| `Engine.port(name).run|consult|generate|build_live_payload` | EM → Engines Frozen | Existing engine modules |
| `Db.port(learning_stats|knowledge_search|memory_recall)` | EM → data DBs | Existing DB helpers (thin pipelines / knowledge step) |

**Forbidden:** EM importing raw API clients or owning Tool Registry.

## 4.6 Caller contract (Orchestration / Router)

1. Orchestration decides **whether** and **which** `pipeline_id` to run (today: `_copilot_inner` branches).  
2. Orchestration builds `ExecutionRequest` (entities, flags, read projections).  
3. EM returns `ExecutionResult`.  
4. Orchestration / Router present payload; **CM** commits subject on a **separate** path after success acceptance (today: `_save_analysis_context` must migrate ownership to CM — **not** into EM).

---

# 5. Pipeline (Step Runner stages)

## 5.1 Pipeline catalog (v1.0)

| pipeline_id | Source today (Mission 021) | Nature |
|-------------|----------------------------|--------|
| `analyze` | `_run_analyze` | Primary Frozen sports sequence |
| `live` | `_run_live` | Live feed + `live_intelligence_engine` |
| `live_team_analyze` | live_team bridge → `_run_analyze(..., prefer_live=True)` | Composite: Tool Use live search then `analyze` |
| `bankroll` | `_run_bankroll` | Thin DB→payload |
| `learning` | `_run_learning` | Thin DB→payload |
| `knowledge` | `_run_knowledge` | Thin DB→payload |

**Explicitly NOT EM pipelines:** `greeting`, `help`, `identity`, `capabilities`, `fallback` — remain Router.

## 5.2 Analyze pipeline — Frozen engine sequence (LOCKED to surface)

Aligns with Mission 021 §5 / `_run_analyze` order:

| Stage # | Step id | Kind | Action |
|---------|---------|------|--------|
| A0 | `budget_check` | Gate | Respect budget_token / may-run |
| A1 | `fetch_fixture` | Tool Use port | `FetchFixture` (`analyze_fixture`, soft, force_refresh) |
| A2 | `integrity_gate` | Conditional edge | INVALID → abort pipeline (execution-local); PARTIAL continues under current culture |
| A3 | `methodology` | Frozen engine | `methodology_engine.run` |
| A4 | `learning` | Frozen engine | `learning_engine.run` |
| A5 | `confidence` | Frozen engine | `confidence_engine.run` |
| A6 | `market` | Frozen engine | `market_engine.run` |
| A7 | `methodology_v1` | Frozen engine | `methodology_v1.run` |
| A8 | `decision_center` | Frozen engine | `decision_center.run` |
| A9 | `knowledge_consult` | Frozen + memory | `memory_db.recall_context` + `knowledge_engine.consult` |
| A10 | `intelligence` | Frozen engine | `intelligence_engine.generate` |
| A11 | `partial_inference_assembly` | EM assembly | partial / inference / confidence / stake helpers (`_resolve_fixture_confidence`, `_parse_stake`, `_compose_final`, …) |
| A12 | `structured_payload` | EM assembly | Markets, labels, diagnostics, DRS stamp fields as today |
| A13 | `match_card_hint` | Optional adapter | Prefer Router-owned `attach_match_card`; EM may emit fields Router needs — **not** FE shell |

**Normative rule:** Stages A3–A10 order is **Frozen contract**. Changing order requires `ARCHITECTURAL DECISION REQUIRED`.

## 5.3 Live pipeline

| Stage # | Step id | Kind | Action |
|---------|---------|------|--------|
| L0 | `budget_check` | Gate | may-run |
| L1 | `fetch_live_feed` | Tool Use port | `FetchLiveFeed` |
| L2 | `live_intelligence` | Frozen engine | `live_intelligence_engine.build_live_payload` |
| L3 | `structured_payload` | EM assembly | Live opportunities payload |
| L4 | `match_card_hint` | Optional adapter | Same ownership note as analyze |

## 5.4 Live-team-analyze composite

| Stage # | Step id | Action |
|---------|---------|--------|
| T0 | `search_live_for_team` | Tool Use live list search (Orchestration today L3949–4064) |
| T1 | `delegate_analyze` | Run `analyze` with `prefer_live=True` (same Step Runner) |

CM ctx seed on live_opportunities remains **out of EM** (NR1).

## 5.5 Thin report pipelines

| pipeline_id | Steps (conceptual) |
|-------------|--------------------|
| `bankroll` | `load_learning_stats` → `assemble_bankroll_payload` |
| `learning` | `load_learning_stats` → `assemble_learning_payload` |
| `knowledge` | `search_knowledge_items` → `assemble_knowledge_payload` |

No Frozen sports engines; still EM-owned sequencing (Mission 021 thin EM).

## 5.6 Step Runner semantics

- **Sequential by default**; conditional edges only for declared gates (integrity, soft-404 recovery hints from Orchestration).  
- **No LLM routing** between Frozen steps.  
- Each step: typed inputs from prior scratch + request; typed outputs into scratch; append `step_traces` entry.  
- Fail-open per step **where current culture fail-opens**; integrity INVALID remains abort.  
- Step Runner is Aurora-owned (Process Framework *principles*); **no** mandated framework dependency in Spec v1.0.

---

# 6. Comunicação

## 6.1 Context Manager (CM)

| Direction | Rule |
|-----------|------|
| Orchestration → CM | Subject commit **after** accepted success (separate from EM) |
| EM → CM | **Forbidden** sole-write / `_save_analysis_context` ownership |
| CM → EM | Read projections only via `ExecutionRequest.read_projections` |

LangGraph STS host / `minimal_commit_orchestrator` remain CM — orthogonal.

## 6.2 Tool Use

| Direction | Rule |
|-----------|------|
| EM → Tool Use | Invoke narrow ports only |
| Tool Use → EM | Return data / errors / cache-hit metadata |
| EM owns registry? | **No** |
| Web intelligence gather/enrich | Stays Tool Use / Orchestration-adjacent (Mission 021); not analyze core stages |

## 6.3 Router / Orchestration

| Direction | Rule |
|-----------|------|
| Router/Orchestration → EM | `run(ExecutionRequest)` after intent + sport pipeline allow |
| EM → Router | `ExecutionResult.payload` for presentation layers |
| Follow-up reuse without engines | Stays Router (skips EM) |
| Greeting/help/… | Stays Router (never calls EM) |

## 6.4 Engines Frozen

| Direction | Rule |
|-----------|------|
| EM → Engines | Consume public `run` / `consult` / `generate` / `build_live_payload` |
| Engines → EM | Step outputs into scratch |
| EM modifies formulas? | **No** |

## 6.5 Orchestration future

Future Orchestration pillar may own conversational layer order independently; EM contract remains **pipeline runner**. Spec v1.0 does not redesign Orchestration.

## 6.6 Legacy parallel

| Surface | Communication rule (migration target) |
|---------|----------------------------------------|
| `copilot_engine.dispatch` / `_handle_*` | Parallel until dedicated retirement mission; Shadow parity primary vs **unified** `_run_*` |
| Dual HTTP `/chat` | Remains mounted until retirement; not EM public API |

---

# 7. Fluxo de Execução (diagram)

```text
[Client / FE]
      │
      ▼
POST /aurora/copilot  (Router)
      │
      ▼
_copilot_inner  (Orchestration / Understanding)
  • Master Intent, guards, sport_pipeline_blocked
  • follow-up reuse? ──yes──► return last_analysis (skip EM)
  • greeting/help/… ─────────► Router helpers (skip EM)
      │
      │ pipeline allowed (analyze|live|thin|live_team)
      ▼
┌─────────────────────────────────────────────┐
│           EXECUTION MANAGER                 │
│     Deterministic Sequential Step Runner    │
│                                             │
│  ExecutionRequest ──► states: Idle→Running  │
│                                             │
│  [Tool Use ports]  FetchFixture / LiveFeed  │
│         │                                   │
│  [Gates] integrity / budget                 │
│         │                                   │
│  [Frozen engines] methodology → … → intel   │
│         │                                   │
│  assemble ExecutionResult + step_traces     │
└─────────────────────────────────────────────┘
      │
      │ ExecutionResult
      ▼
Router presentation (formatter, personality, match_card coerce)
      │
      ▼
Context Manager sole-writer path (SEPARATE — not EM)
  • commit subject / apply_after_analysis (CM ownership)
      │
      ▼
HTTP CopilotResponse

Shadow mode (defaults OFF):
  Orchestration → EM.shadow_compare || dual-invoke
  compare payload/step_traces vs legacy _run_* 
  primary path remains legacy until gated cut-over
```

---

# 8. Estados

| Estado | Meaning | Transitions |
|--------|---------|-------------|
| **Idle** | No active run for `run_id` | → Running on `run()` |
| **Running** | Step Runner advancing | → Completed / Failed / Interrupted / Retry |
| **Completed** | Terminal success (`status=Completed`) | End |
| **Failed** | Terminal failure (unrecoverable step or integrity abort without fallback payload) | End |
| **Interrupted** | Cancel / timeout / external interrupt before terminal success | End (or → Retry if policy allows new run_id) |
| **Retry** | Transient failure scheduled for another attempt | → Running (new or same run_id per policy) / → Failed |

**Notes:**

- Shadow runs use the same state machine with `mode=shadow`; failures are **fail-open** to primary path (Zero User Impact).  
- `Retry` is an EM-local control state; Orchestration may also choose to re-issue a new `ExecutionRequest`.

---

# 9. Tratamento de Erros

| Classe | Policy (v1.0) |
|--------|----------------|
| **Timeout** | Exceed `timeout_ms` → `Interrupted` (+ partial step_traces). Shadow: discard shadow result, keep primary. Primary gated path: fail-open to safe Orchestration fallback **unless** integrity already aborted with explicit user-facing INVALID contract. |
| **Falha (step)** | Record `step.failed`; apply per-step fail-open if current `_run_analyze` culture fail-opens that step; else escalate to run `Failed`. |
| **Falha (integrity INVALID)** | Abort remaining Frozen engines; return structured abort payload consistent with today (execution-local gate). |
| **Retry** | Only for **declared transient** Tool Use / I/O errors (fetch timeouts, 5xx) with bounded attempts; **never** retry Frozen formula disagreement. Budget_token must still allow. |
| **Fallback** | Soft-404 / recovery paths remain Orchestration-initiated (today outer exception recovery calling analyze again) — EM accepts flags; does not invent intent fallback. Router `_run_fallback` is **not** EM. |
| **Cancelamento** | `cancel(run_id)` cooperative between steps; enter `Interrupted`; no CM write. |

**Anti-pattern:** Silent catch-all that hides step failures without `step_traces` (breaks Shadow).

---

# 10. Observabilidade

Mandatory for Spec-compliant EM (implementation later):

| Signal | Requirement |
|--------|-------------|
| `run_id` / `pipeline_id` / `mode` | On every run |
| Per-step timing | duration_ms in `step_traces` |
| Per-step status | started/completed/skipped/failed + reason |
| Engine identity | module name + existing version metadata if already exposed |
| Budget / cache outcomes | From Tool Use port metadata (hit/miss/blocked) — not invented |
| Shadow diff handle | When `mode=shadow` |
| Correlation | `session_id` + `trace_parent` without writing subject |

Aligns with Research 022 auditability theme (Process Framework / OTel principles) without mandating a vendor.

---

# 11. Shadow

| Rule | Spec |
|------|------|
| Default | **OFF** (REGRA 23) |
| Purpose | Dual-run EM vs legacy unified `_run_analyze` / `_run_live` (and thin pipelines as extracted) |
| User impact | **None** — student mode; primary path remains legacy blob until gated sole path |
| Compare | Structured payload fields + step order + abort reasons; tolerate non-semantic noise via declared allowlist (Plan/Infra later) |
| Fail posture | Shadow failure **never** breaks primary |
| CM | Shadow EM **must not** write subject |
| Host | Separate from CM LangGraph STS graph (Research 022 / 003 boundary) |

Shadow is Phase 3 of Blueprint ladder for this module (see §12).

---

# 12. Progressive Activation

Follow Blueprint §5 Deployment Ladder (module-specific flag names deferred to Implementation Plan):

```text
0% → 1% → 5% → 10% → 25% → 50% → 100%
```

| Phase | Intent for EM |
|-------|----------------|
| **1 Prep** | Harness, flags OFF, baselines of `_run_*` payloads, residual labeling |
| **2 Infra** | Contracts, Step Runner scaffolding, illegal matrix (e.g. EM+CM-write), tests |
| **3 Shadow** | Dual-run observe-only |
| **4 Sole path (gated)** | EM becomes official executor behind flags; legacy `_run_*` may remain until retirement mission |
| **5 PGR ladder** | One Gate, One Decision per percentage |
| **6 Stabilization** | Trust question defaults-OFF SoT |
| **FA** | Final Acceptance of EM AEL cycle — Activation residuals explicit (mirror drift NO-GO honesty) |

**Rules:** Auto-advance = False; REGRA 27; Plateau Validation REGRA 28; await PO between gates.

---

# 13. Rollback

| Layer | Action |
|-------|--------|
| Flag rollback | Instant OFF / 0% helpers (Blueprint) |
| Shadow rollback | Disable shadow dual-run; no user impact |
| Sole-path rollback | Route Orchestration back to legacy `_run_*` in mega-router |
| Spec/docs rollback | Revert Spec commits under `observations/execution_manager_spec_023/` |
| Forbidden | Rollback that reopens CM writers inside EM; rollback that “fixes” Frozen engines |

Legacy `copilot_engine` remains available as parallel until retirement — not a substitute Shadow strategy for unified clients.

---

# 14. Segurança / guarantees

| Guarantee | Statement |
|-----------|-----------|
| **G1 CM write-free** | EM never sole-writes sport subject / STS / episode |
| **G2 Determinism** | Analyze Frozen step order fixed; no LLM step selection |
| **G3 Tool Use separation** | No Tool Registry inside EM; ports only |
| **G4 Frozen consume-only** | Engine formulas untouchable by EM missions |
| **G5 Zero User Impact default** | Flags OFF; Shadow fail-open |
| **G6 No dual production SoT** | After sole-path ON, one official executor for unified analyze/live; legacy retirement scheduled — not three silent paths |
| **G7 Budget respect** | I/O steps honor budget_token / may-run |
| **G8 Traceability** | Every run yields step_traces suitable for Shadow parity |
| **G9 Isolation from CM host** | EM Step Runner must not reuse STS checkpointer as write SSOT |
| **G10 Router conversational purity** | Greeting/help/identity/capabilities/fallback never enter EM |

---

# 15. Testabilidade

| Class | Intent ( Spec — tests run in later missions) |
|-------|-----------------------------------------------|
| Contract tests | `ExecutionRequest` / `ExecutionResult` schema; illegal fields rejected |
| Pipeline order tests | Analyze A3–A10 order frozen snapshot |
| Gate tests | Integrity INVALID aborts before engines |
| Port mock tests | FetchFixture / FetchLiveFeed failures → Retry/Failed per policy |
| Thin pipeline tests | bankroll/learning/knowledge assembly without engines |
| Shadow harness | Byte/semantic compare vs captured `_run_analyze` golden payloads |
| Boundary tests | Assert EM module has **no** calls to subject writers / `_save_analysis_context` |
| Non-regression | Existing analyze/live integration tests remain green on legacy path while flags OFF |
| Negative | LLM-router / hierarchical manager **absent** from EM core |

---

# 16. Critérios de Frozen

EM AEL cycle may be declared **FROZEN** (Final Acceptance) only when **all** apply:

| ID | Criterion |
|----|-----------|
| F1 | Spec v1.0 (this document) PO-accepted; CDR/AAR completed under later missions without violating locked family |
| F2 | Implementation follows Deterministic Sequential Pipeline + Step Runner + Shadow-first + CM-write-free + Tool Use separado |
| F3 | Analyze Frozen engine order unchanged vs Mission 021 surface (or ADR-authorized change — none in this Spec) |
| F4 | Shadow dual-run evidence recorded; fail-open proven |
| F5 | Defaults OFF / 0% in repo for production-affecting flags |
| F6 | PGR ladder discipline documented; no bundled gates |
| G/F7 | Boundary tests prove no CM sole-write from EM |
| F8 | Tool Use remains ported; no in-EM registry absorbing API/web |
| F9 | Greeting/help/identity/capabilities/fallback remain Router |
| F10 | Legacy `copilot_engine` retirement **pre-declared** (may still be present — honesty residual OK if Activation NO-GOs listed) |
| F11 | Mirror drift treated honestly (OPEN = Activation NO-GO) |
| F12 | Dual Reporting present on FA; await PO; no auto-start next module |
| F13 | Master / Blueprint not casually rewritten by EM implementation missions (governed reopen only) |

**Technical Spec acceptance ≠ authorization to implement or activate.**  
This mission ends at Spec + Dual Reporting.

---

## Migration target (descriptive — not Plan)

Mega-router extraction order (from Discovery Q12 + Surface Map):

1. Spec accepted (this mission) → CDR/AAR (later) → Implementation Plan + Readiness (later).  
2. Prep/Infra with defaults OFF.  
3. Shadow vs `_run_analyze` / `_run_live`.  
4. Gated sole path for unified helper; legacy retirement mission separate.  
5. Do not couple full Tool Use registry or Activation full-env in the same climb without own gates.

---

## Explicit non-starts

| Item | Status |
|------|--------|
| Product code | **NOT STARTED** |
| ADR | **NOT CREATED** |
| Master / SSOT / Blueprint edits | **NOT DONE** |
| CDR | **NOT STARTED** — await PO |
| Implementation Plan | **NOT STARTED** |

---

## Handoff

**Await Product Owner** acceptance of Spec Execution Manager v1.0.  
Do **not** start CDR or implementation.

---

*End of SPEC_EXECUTION_MANAGER_v1.0.md*
