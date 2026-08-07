# AURORA — SPECIFICATION — Execution Manager v1.1

**MISSION ID:** `execution_manager_spec_revision_025`  
**DOCUMENT:** `SPEC_EXECUTION_MANAGER_v1.1.md`  
**VERSION:** 1.1  
**SUPERSEDES:** `observations/execution_manager_spec_023/SPEC_EXECUTION_MANAGER_v1.0.md` (historical; unchanged)  
**DATE:** 2026-08-07  
**BRANCH:** `feat/aurora-response-selector-001`  
**CLASS:** ARCHITECTURE_SPECIFICATION (documentation only)  
**CODE SoT (future implement):** `artifacts/aurora/`  
**STATUS:** DRAFT — awaiting Product Owner acceptance  
**IMPLEMENTATION AUTHORIZATION:** **NOT AUTHORIZED**  
**CDR2 / AAR / Implementation:** **DO NOT START** — await PO  

**Nenhuma alteração de código: SIM**

---

## Change log (v1.0 → v1.1)

| ID | Change | CDR finding |
|----|--------|-------------|
| CL-H1 | §5.2 A2 + new §5.2.1 Integrity / soft-analyze contract (abort vs soft-skip vs soft-continue); §9 integrity row aligned | **CDR-H-001** |
| CL-H2 | §4.6 expanded Orchestration↔EM wrap; §4.7 CM commit eligibility; §6.1 / §7 flow updated; NR1 clarified | **CDR-H-002** |
| CL-M1 | A13/L4: EM **forbidden** to call `attach_match_card`; emit fields only | CDR-M-001 |
| CL-M2 | `cancel(run_id)` demoted to post-Infra optional; §9 interrupt path = timeout | CDR-M-002 |
| CL-M3 | Closed `status` enum; Retry = new `run_id` default | CDR-M-003 / L-002 |
| CL-M4 | §11 + Appendix A minimum Shadow compare keys | CDR-M-004 |
| CL-M5 | §4.5 / A0: Orchestration mints `budget_token`; EM never `begin_request` | CDR-M-005 |
| CL-M6 | G6 footnote: dual-SoT **window** during climb | CDR-M-006 |
| CL-M7 | `Db.port` labeled EM-local read adapters; A9 memory = Frozen consume | CDR-M-007 |
| CL-L1 | §4.2.1 pipeline_id alias table | CDR-L-001 |
| CL-L3 | §12.1 illegal flag-combination principles | CDR-L-003 |
| CL-L4 | Appendix B step×fail-open matrix (cite 021) | CDR-L-004 |
| CL-meta | Binding sources + CDR-001; Frozen F1 → Spec v1.1; R3 wording decidable | — |

**Architectural family:** **UNCHANGED** (Mission 022 lock).  
**ARCHITECTURAL DECISION REQUIRED:** **NONE**.

---

## Hard scope locks

| Allowed | Forbidden |
|---------|-----------|
| Spec revision incorporating accepted CDR-001 findings | Product code |
| Public contracts, pipeline, states, shadow, PGR, Frozen criteria | ADR creation |
| Dual Reporting (REGRA 29) on Spec revision artifacts | Master / SSOT / Blueprint edits |
| AEAP Level 1 on Spec revision deliverables only | CDR2, AAR, Implementation Plan, rebuild |
| Preserve locked 022 family | Change architectural family |

---

## Binding sources (cited — not reinvented)

| Source | Role |
|--------|------|
| `observations/execution_manager_spec_023/SPEC_EXECUTION_MANAGER_v1.0.md` | Baseline Spec |
| `observations/execution_manager_cdr_024/EXECUTION_MANAGER_CDR_024.md` | CDR-001 findings (H-001/H-002 blockers + M/L) |
| `observations/execution_manager_discovery_020/EXECUTION_MANAGER_DISCOVERY_REPORT.md` | Absence of EM; mega-router blob; CM/Tool Use boundaries |
| `observations/execution_surface_021/EXECUTION_SURFACE_MAP.md` | Destino Futuro; Frozen order; soft-analyze must-stay; integrity Avaliar |
| `observations/execution_surface_021/EXECUTION_SURFACE_REPORT.md` | Callers, `_save_analysis_context`, contamination |
| `observations/execution_manager_research_022/EXECUTION_MANAGER_ARCHITECTURE_RESEARCH.md` | Pattern family recommendation |
| `observations/execution_manager_research_022/COMPARATIVE_ANALYSIS.md` | Framework fit / anti-patterns |
| SoT `artifacts/aurora/src/routers/copilot_unified_router.py` (read-only cite) | Soft-analyze / A2 / caller wrap golden behaviour (~L502–527, ~L3851–3908, `_save_analysis_context` L1563–1615) |
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
This Spec does **not** reopen that decision. CDR-001 High fixes are **contract clarifications**, not family changes.

---

## One-sentence Spec summary (EM role)

**The Execution Manager is the thin, deterministic Step Runner that coordinates declared sports/report pipelines (analyze / live / thin reports), invokes Tool Use ports and Frozen engines in fixed order, returns structured results with step traces, and never owns intent routing, Tool Registry, or Context Manager writes.**

---

# 1. Objetivo

| ID | Objetivo |
|----|----------|
| O1 | Establish a named **Execution Manager (EM)** pillar that owns **how** declared execution pipelines run after Orchestration decides they should run. |
| O2 | Extract EM-equivalent behaviour from `copilot_unified_router._run_analyze` / `_run_live` / thin `_run_bankroll|learning|knowledge` into a **Deterministic Sequential Pipeline / Step Runner** without rewriting Frozen engines. |
| O3 | Preserve the **Frozen analyze engine sequence** and structured analyze/live payload semantics users and clients rely on (Mission 021 surface), including **soft-analyze / integrity culture** (§5.2.1). |
| O4 | Enforce **hard boundaries**: CM write-free; Tool Use via ports only; greeting/help/identity/capabilities/fallback remain Router. |
| O5 | Provide **step-level contracts** (`ExecutionRequest` / `ExecutionResult` / step traces) enabling Shadow dual-run parity vs legacy `_run_*`. |
| O6 | Migrate **shadow-first**, defaults OFF, Progressive Activation ladder (Blueprint §5) — Zero User Impact until gates are armed. |
| O7 | Pre-declare **legacy retirement** of `copilot_engine` / `/aurora/chat` as a separate later mission — not silent dual-SoT forever. |
| O8 | Keep Master pillar #11 substitution path governance-compatible without editing Master in this mission. |
| O9 | Make **Orchestration↔EM↔CM** contracts decidable for soft-try, post-integrity, and CM commit eligibility (CDR-H-002) without moving writes into EM. |

**Non-goals of this mission document:** implementation, CDR2, ADR, Blueprint/Master mutation, product behaviour change.

---

# 2. Responsabilidades

EM **owns** the following (principles from 022 + extract candidates from 021):

| ID | Responsabilidade | Grounding |
|----|------------------|-----------|
| R1 | Coordinate **declared pipelines**: `analyze`, `live`, `bankroll`, `learning`, `knowledge`, and the `live_team_analyze` bridge that ends in analyze | Surface Map Destino Futuro **EM** |
| R2 | Enforce **step order / contracts** for the Frozen sports engine sequence | `_run_analyze` L543–584 order |
| R3 | Apply **execution-local gates** per §5.2.1 (integrity HARD-ABORT / SOFT-SKIP / PARTIAL soft-continue; soft-analyze fail-open culture) as Step Runner edges | Surface Map §10; Discovery Q7; CDR-H-001 |
| R4 | Invoke **Tool Use ports** (`FetchFixture`, `FetchLiveFeed`, budget-aware may-run) without owning clients/cache/registry | Research 022 Q7 |
| R5 | **Consume** Frozen engines (`run` / `consult` / `generate` / `build_live_payload`) — never retune formulas | FROZEN_MODULES / Master |
| R6 | Assemble **structured ExecutionResult** (markets, confidence, stake composition helpers, DRS stamp fields as today) for Orchestration / FE | `_run_analyze` assembly |
| R7 | Provide **per-step observability**, fail-open/skip recording, and Shadow-comparable step API | Research 022 Q1 / Q11 |
| R8 | Honor ops **budget decision tokens** (“may this I/O step run?”) without absorbing `cost_protection` / never calling `begin_request` | Mission 021 Tool Use / ops; CDR-M-005 |
| R9 | Maintain **ephemeral run scratch** (intermediate engine outputs for the run) — not conversational subject SSOT | Research 022 Q8–Q9 |
| R10 | Expose thin report pipelines (`bankroll` / `learning` / `knowledge`) as first-class EM pipelines (DB→payload sequencing) | Surface Map thin EM |

---

# 3. Não Responsabilidades

| ID | Não responsabilidade | Owner correto |
|----|----------------------|---------------|
| NR1 | Sole-write STS / episode / subject / `_save_analysis_context` (or CM-equivalent) / live `ctx["last_*"]` seed | **Context Manager** (FROZEN) — Orchestration may **invoke** CM path after eligibility (§4.7); **EM never** |
| NR2 | Intent classification, Master Intent, CUE/HCE, `sport_pipeline_blocked`, conversational layer order | **Understanding / Orchestration** |
| NR3 | Greeting / help / identity / capabilities / fallback / follow-up suggestions | **Router / Orchestration** |
| NR4 | Tool Registry, permissions, raw API clients, analyze cache implementation, web agent loop | **Tool Use** / data / ops |
| NR5 | Frozen methodology / market / confidence / learning / knowledge / decision formulas | **Engines Frozen** |
| NR6 | HTTP binding, session lifecycle, response personality / credibility / **`attach_match_card` / match_card coerce** | **Router** (EM may emit raw fields only — CDR-M-001) |
| NR7 | LLM choosing next Frozen engine / multi-agent debate as analyze controller | **Nowhere** (anti-pattern — 022) |
| NR8 | Treating `minimal_commit_orchestrator` / LangGraph STS host as EM | **CM** |
| NR9 | Big-bang mega-router rewrite or Activation full-env in Spec alone | Blueprint AEL — later gated missions |
| NR10 | Mirror drift repair (`aurora/` vs `artifacts/aurora/`) | Activation residual — separate |
| NR11 | Caller soft-try precheck, post-EM `_apply_integrity` / `assess_analyze_result`, CM commit **eligibility decision** | **Orchestration** (sequencing) + **fixture_integrity** (formula) + **CM** (write) — §4.6–§4.7 |
| NR12 | Turn-scoped `cost_protection.begin_request` / `end_request` | **Router / ops** |

---

# 4. Interfaces Públicas (entradas / saídas / eventos / contratos)

## 4.1 Conceptual API surface (normative shape — not code)

```text
ExecutionManager.run(request: ExecutionRequest) -> ExecutionResult
ExecutionManager.shadow_compare(request: ExecutionRequest) -> ShadowCompareResult   # observe-only
```

Optional future (post-Infra, defaults OFF — **not** required for Spec v1.1 decidability):

```text
ExecutionManager.get_pipeline(pipeline_id) -> PipelineDescriptor
ExecutionManager.cancel(run_id) -> CancelAck
```

**v1.1 interrupt path:** wall-clock `timeout_ms` → `Interrupted` (§9). Cooperative `cancel` is **future** (CDR-M-002).

## 4.2 ExecutionRequest (entrada)

| Field (logical) | Required | Description |
|-----------------|----------|-------------|
| `run_id` | yes | Unique id for this execution attempt (trace correlation). **Immutable for the attempt**; retries require a **new** `run_id` (CDR-M-003). |
| `pipeline_id` | yes | One of: `analyze` \| `live` \| `bankroll` \| `learning` \| `knowledge` \| `live_team_analyze` |
| `session_id` | yes | Correlation only — **not** authorization to write subject |
| `entities` | pipeline-dependent | e.g. home/away/team for analyze/live_team |
| `flags` | no | `prefer_live`, `force_refresh`, soft-404 recovery hints, soft-try hints from Orchestration (§4.6) |
| `budget_token` | no | Opaque allowance **minted by Orchestration/ops adapter** from turn scope; EM only consults `BudgetGate.may_run` |
| `read_projections` | no | Immutable-enough CM/Orchestration projections of subject (read-only) |
| `mode` | yes | `primary` \| `shadow` \| `dry_run` |
| `timeout_ms` | no | Wall-clock budget for the run |
| `trace_parent` | no | Observability parent span |

**Invariant:** Request carries **inputs**; EM does not pull mutable conversational memory as SSOT.

### 4.2.1 pipeline_id alias table (CDR-L-001)

| Spec `pipeline_id` | Intent / surface name (021) | Notes |
|--------------------|-----------------------------|-------|
| `analyze` | `analyze_match` / analyze branch | Primary |
| `live` | live opportunities | Primary |
| `live_team_analyze` | `live_team_analysis` | Alias: Orchestration maps intent → Spec id |
| `bankroll` | bankroll review | Thin |
| `learning` | learning recap | Thin |
| `knowledge` | knowledge search | Thin |

## 4.3 ExecutionResult (saída)

| Field (logical) | Description |
|-----------------|-------------|
| `run_id` | Echo |
| `pipeline_id` | Echo |
| `status` | **Closed enum:** `Completed` \| `Failed` \| `Interrupted` (terminal only; no ellipsis) |
| `payload` | Structured result compatible with current unified Copilot analyze/live/thin contracts |
| `step_traces[]` | Ordered per-step records (id, status, duration, error/skip reason) |
| `abort_reason` | Optional (e.g. `integrity_invalid_hard_abort`) |
| `fixture_quality` | Echo/hint from integrity culture when present (`VALID` / `PARTIAL` / `INVALID` / … as today) |
| `diagnostics` | Non-user fields (DRS stamp, data richness, engine versions if present today) |
| `shadow_meta` | Present only in shadow mode (parity flags, diff summary handle) |

**Invariant:** Result is **return-only**. No CM commit side-effect from EM.  
**Note:** Internal control state `Retry` (§8) is **not** a Result `status`; a retry attempt is a new `run()` with a new `run_id`.

## 4.4 Events (observability / orchestration hooks)

| Event | When | Consumers |
|-------|------|-----------|
| `em.run.started` | Enter Running | Observability |
| `em.step.started` / `em.step.completed` / `em.step.skipped` / `em.step.failed` | Each Step Runner stage | Observability / Shadow harness |
| `em.run.completed` / `em.run.failed` / `em.run.interrupted` | Terminal | Orchestration |
| `em.shadow.diff` | Shadow compare finished | Shadow harness (defaults OFF) |
| `em.retry.scheduled` | Orchestration/EM policy schedules a **new** run_id attempt | Observability |

Events are **signals**, not CM writes.

## 4.5 Ports (outbound contracts — Tool Use / Engines)

| Port | Direction | Owner of implementation |
|------|-----------|-------------------------|
| `FetchFixture` | EM → Tool Use / data | `analyze_fixture` / analyze router / cache ops |
| `FetchLiveFeed` | EM → Tool Use / data | `live._build_live_response` |
| `BudgetGate.may_run(step)` | EM → ops | `cost_protection` **decision surface only** — EM never calls `begin_request`/`end_request` (CDR-M-005) |
| `Engine.port(name).run|consult|generate|build_live_payload` | EM → Engines Frozen | Existing engine modules |
| `Db.port(learning_stats|knowledge_search|memory_recall)` | EM → data DBs | **EM-local read adapters** (non-registry); thin pipelines + analyze A9 consume. Not Tool Registry; not CM write (CDR-M-007) |

**Forbidden:** EM importing raw API clients or owning Tool Registry.

## 4.6 Caller contract (Orchestration / Router) — normative wrap

Grounded in Mission 021 Surface Map §9 / §58 integrity Avaliar + SoT `_copilot_inner` ~L3851–3908.

### 4.6.1 Ownership split (decidable)

| Concern | Owner | EM role |
|---------|-------|---------|
| Whether / which `pipeline_id` to run | Orchestration | Receives request |
| Named-fixture **precheck** (`assess_named_fixture`) | Orchestration (sequencing) + `fixture_integrity` (formula) | Does not own formula |
| **Soft-try** when precheck would INVALID | **Orchestration** — still call EM `analyze` (must-stay 021) | Runs pipeline with flags |
| Derive `prefer_live` when soft-trying blocked names | Orchestration (`is_live` OR precheck blocked) | Honors `flags.prefer_live` |
| Soft fetch + **A2 integrity gate** inside pipeline | **EM** per §5.2.1 | HARD-ABORT / SOFT-SKIP / PARTIAL |
| Post-EM integrity assess / `_apply_integrity` | **Orchestration** | Consumes `ExecutionResult` |
| CM / `_save_analysis_context` (or equivalent) | **CM** write; Orchestration **eligibility gate** (§4.7) | **Forbidden** |
| Live ctx `last_*` seed | CM residual / Orchestration — **out of EM** | Forbidden |
| Presentation / `attach_match_card` | Router | EM emits fields only |

### 4.6.2 Analyze sequence (Orchestration wrap — not EM)

```text
1. Orchestration: intent allow + entities resolved
2. Orchestration: precheck = assess_named_fixture(home, away)   # formula outside EM
3. If soft-try path (precheck blocked OR normal analyze):
     flags.prefer_live := entities.is_live OR precheck.is_blocked
     result := EM.run(ExecutionRequest{pipeline_id=analyze, flags…})
4. Orchestration reads result.payload / abort_reason / fixture_quality
5. If precheck.blocked AND payload still INVALID/fiction markers:
     replace with blocked_integrity_payload(precheck)   # user-facing INVALID
   Else:
     post := assess_analyze_result(...)                 # formula outside EM
     payload := apply_integrity(payload, post)
6. CM commit eligibility (§4.7) — NEVER inside EM
7. Router presentation
```

**Normative:** Soft-analyze must-stay means Orchestration **must not** refuse to call EM solely because precheck is INVALID. Fiction that remains INVALID after EM (no fixture rescue) is collapsed by Orchestration to blocked payload — EM may also HARD-ABORT internally per §5.2.1 when rescue did not locate a fixture.

### 4.6.3 Soft-404 / recovery

Outer soft-404 / exception recovery that re-issues analyze remains **Orchestration-initiated** (flags on a new `ExecutionRequest`). Distinct from soft-analyze alias rescue (CDR evidence: soft-analyze ≠ soft-404).

## 4.7 CM commit eligibility matrix (CDR-H-002)

| Condition after Orchestration post-integrity | May call `_save_analysis_context` / CM sole-write equivalent? | Notes |
|----------------------------------------------|--------------------------------------------------------------|-------|
| `post.is_blocked == false` AND `payload.fixture_quality != INVALID` | **YES** — Orchestration invokes **CM path** | Today ~L3905–3908 |
| Soft-analyze rescued fixture (`fixture_id > 0`) and post not blocked | **YES** | Live/API rescue path |
| Precheck blocked and payload still INVALID / fiction / NOT_FOUND | **NO** — clear follow-up poison (`last_analysis`/`last_market` null pattern) | Do not seed CM |
| EM HARD-ABORT integrity (`abort_reason=integrity_invalid_hard_abort`) | **NO** | Same as blocked |
| Shadow / dry_run mode | **NO** | Zero User Impact |
| Thin pipelines / greeting / help / … | Out of this matrix; not analyze CM seed | — |
| Live opportunities inline `ctx["last_*"]` seed | **Not EM**; CM residual / Orchestration — migrate to CM sole-writer later | NR1 |

**Who may call `_save_analysis_context` equivalent:** Orchestration (today) migrating to **CM sole-writer API** — **never EM**, never Shadow EM, never Tool Use.

**Invariant G1:** EM remains write-free even when Orchestration eligibility is YES.

---

# 5. Pipeline (Step Runner stages)

## 5.1 Pipeline catalog (v1.1)

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
| A0 | `budget_check` | Gate | Consult `budget_token` via `BudgetGate.may_run` only (token minted upstream) |
| A1 | `fetch_fixture` | Tool Use port | `FetchFixture` (`analyze_fixture`, soft, force_refresh) |
| A2 | `integrity_gate` | Conditional edge | **See §5.2.1** (not absolute abort) |
| A3 | `methodology` | Frozen engine | `methodology_engine.run` |
| A4 | `learning` | Frozen engine | `learning_engine.run` |
| A5 | `confidence` | Frozen engine | `confidence_engine.run` |
| A6 | `market` | Frozen engine | `market_engine.run` |
| A7 | `methodology_v1` | Frozen engine | `methodology_v1.run` |
| A8 | `decision_center` | Frozen engine | `decision_center.run` |
| A9 | `knowledge_consult` | Frozen + memory read | `memory_db.recall_context` + `knowledge_engine.consult` — **consume only**; not CM write (CDR-M-007) |
| A10 | `intelligence` | Frozen engine | `intelligence_engine.generate` |
| A11 | `partial_inference_assembly` | EM assembly | partial / inference / confidence / stake helpers |
| A12 | `structured_payload` | EM assembly | Markets, labels, diagnostics, DRS stamp fields as today |
| A13 | `match_card_fields` | Emit only | Emit raw fields Router needs; **EM MUST NOT** call `attach_match_card` (CDR-M-001) |

**Normative rule:** Stages A3–A10 order is **Frozen contract**. Changing order requires `ARCHITECTURAL DECISION REQUIRED`.

### 5.2.1 Integrity / soft-analyze contract (CDR-H-001 — decidable)

**Normative equivalence:** A2 semantics ≡ Mission 021 must-stay + SoT `_run_analyze` integrity block ~L502–527 (including alias / live-API soft-skip), with Orchestration soft-try wrap §4.6 preserved.

`fixture_integrity` **formulas** remain outside EM (Frozen-adjacent). EM owns **sequencing edges** only.

| Outcome id | When (after A1 fetch + named assess inside EM) | EM action | Result posture |
|------------|------------------------------------------------|-----------|----------------|
| **HARD-ABORT** | Named assess `is_blocked` **AND** soft fetch did **not** locate a real `fixture_id` | Abort remaining Frozen engines (A3–A10); return structured blocked/INVALID payload consistent with today | `status=Failed` or Completed-with-blocked-payload per today’s `_blocked_*` return shape; `abort_reason=integrity_invalid_hard_abort`; step A2=`failed` or terminal gate |
| **SOFT-SKIP** (alias soft-skip / live-API rescue) | Named assess `is_blocked` **AND** soft fetch **did** locate `fixture_id` | **Do not** early-abort; record `em.step.skipped` reason `integrity_soft_skip_fixture_located`; continue A3+ | Continues engines; Orchestration post-assess may still apply (§4.6) |
| **SOFT-CONTINUE (PARTIAL)** | Assess / culture = PARTIAL (known teams, no fixture) — not INVALID fiction | Continue with fallback analysis + markets culture | Engines run; payload may carry partial markers |
| **PASS** | Not blocked | Continue | Normal |

**Golden cases (normative tests later):**

1. Fiction / unknown names, no fixture located → HARD-ABORT (no engines).  
2. Alias-missing names but soft analyze located `fixture_id` → SOFT-SKIP → engines run.  
3. Known teams, no fixture (PARTIAL) → SOFT-CONTINUE.  
4. Orchestration precheck INVALID still **calls** EM (soft-try) with `prefer_live` derived — must not be Spec-forbidden.  
5. After EM, still INVALID → Orchestration collapses to blocked; **no CM commit** (§4.7).

**Anti-pattern:** Implementing A2 as “any INVALID → abort always” (regresses soft-analyze UX).

## 5.3 Live pipeline

| Stage # | Step id | Kind | Action |
|---------|---------|------|--------|
| L0 | `budget_check` | Gate | may-run via token |
| L1 | `fetch_live_feed` | Tool Use port | `FetchLiveFeed` |
| L2 | `live_intelligence` | Frozen engine | `live_intelligence_engine.build_live_payload` |
| L3 | `structured_payload` | EM assembly | Live opportunities payload |
| L4 | `match_card_fields` | Emit only | Same as A13 — **no** `attach_match_card` in EM |

## 5.4 Live-team-analyze composite

| Stage # | Step id | Action |
|---------|---------|--------|
| T0 | `search_live_for_team` | Tool Use live list search (Orchestration today L3949–4064) |
| T1 | `delegate_analyze` | Run `analyze` with `prefer_live=True` (same Step Runner) |

CM ctx seed on live_opportunities remains **out of EM** (NR1 / §4.7).

## 5.5 Thin report pipelines

| pipeline_id | Steps (conceptual) |
|-------------|--------------------|
| `bankroll` | `load_learning_stats` → `assemble_bankroll_payload` |
| `learning` | `load_learning_stats` → `assemble_learning_payload` |
| `knowledge` | `search_knowledge_items` → `assemble_knowledge_payload` |

No Frozen sports engines; still EM-owned sequencing (Mission 021 thin EM). DB access via labeled **read adapters** (CDR-M-007).

## 5.6 Step Runner semantics

- **Sequential by default**; conditional edges only for declared gates (§5.2.1 integrity; soft-404 recovery hints from Orchestration).  
- **No LLM routing** between Frozen steps.  
- Each step: typed inputs from prior scratch + request; typed outputs into scratch; append `step_traces` entry.  
- Fail-open per step per **Appendix B**; integrity uses §5.2.1 (not blanket abort).  
- Step Runner is Aurora-owned (Process Framework *principles*); **no** mandated framework dependency in Spec v1.1.

---

# 6. Comunicação

## 6.1 Context Manager (CM)

| Direction | Rule |
|-----------|------|
| Orchestration → CM | Subject commit **only if** §4.7 eligibility YES (separate from EM) |
| EM → CM | **Forbidden** sole-write / `_save_analysis_context` / equivalent |
| CM → EM | Read projections only via `ExecutionRequest.read_projections` |
| Eligibility decision | Orchestration (predicates); write authority → CM |

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
| Router/Orchestration → EM | `run(ExecutionRequest)` after intent + sport pipeline allow (+ soft-try wrap §4.6) |
| EM → Router | `ExecutionResult.payload` for presentation layers |
| Follow-up reuse without engines | Stays Router (skips EM) |
| Greeting/help/… | Stays Router (never calls EM) |
| Post-integrity + CM eligibility | Orchestration after EM (§4.6–§4.7) |

## 6.4 Engines Frozen

| Direction | Rule |
|-----------|------|
| EM → Engines | Consume public `run` / `consult` / `generate` / `build_live_payload` |
| Engines → EM | Step outputs into scratch |
| EM modifies formulas? | **No** |

## 6.5 Orchestration future

Future Orchestration pillar may own conversational layer order independently; EM contract remains **pipeline runner**. Spec v1.1 defines the **wrap** around EM for integrity/CM eligibility without redesigning Orchestration internals.

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
      │  cost_protection.begin/end_request  ← Router/ops (NOT EM)
      ▼
_copilot_inner  (Orchestration / Understanding)
  • Master Intent, guards, sport_pipeline_blocked
  • follow-up reuse? ──yes──► return last_analysis (skip EM)
  • greeting/help/… ─────────► Router helpers (skip EM)
      │
      │ pipeline allowed (analyze|live|thin|live_team)
      ▼
┌─ Orchestration WRAP (NOT EM) ─────────────────────────┐
│  precheck assess_named_fixture                        │
│  soft-try: still call EM if precheck INVALID          │
│  prefer_live := is_live OR precheck.blocked           │
│  mint budget_token from turn scope                    │
└───────────────────────────┬───────────────────────────┘
                            ▼
┌─────────────────────────────────────────────┐
│           EXECUTION MANAGER                 │
│     Deterministic Sequential Step Runner    │
│                                             │
│  ExecutionRequest ──► states: Idle→Running  │
│  [Tool Use] FetchFixture / LiveFeed         │
│  [A2] HARD-ABORT | SOFT-SKIP | PARTIAL      │
│  [Frozen engines] methodology → … → intel   │
│  assemble ExecutionResult + step_traces     │
│  NO CM write / NO attach_match_card         │
└─────────────────────────────────────────────┘
      │
      │ ExecutionResult
      ▼
┌─ Orchestration WRAP (NOT EM) ─────────────────────────┐
│  post-assess / apply_integrity                        │
│  CM commit eligibility matrix (§4.7)                  │
│    YES → CM sole-write path (_save_analysis_context   │
│          equivalent) — NEVER EM                       │
│    NO  → do not poison follow-up context              │
└───────────────────────────┬───────────────────────────┘
                            ▼
Router presentation (formatter, personality, attach_match_card)
      │
      ▼
HTTP CopilotResponse

Shadow mode (defaults OFF):
  Orchestration → EM.shadow_compare || dual-invoke
  compare payload/step_traces vs legacy _run_*
  primary path remains legacy until gated cut-over
  Shadow EM must not write subject / must not pass §4.7 YES
```

---

# 8. Estados

| Estado | Meaning | Transitions |
|--------|---------|-------------|
| **Idle** | No active run for `run_id` | → Running on `run()` |
| **Running** | Step Runner advancing | → Completed / Failed / Interrupted / Retry |
| **Completed** | Terminal success (`status=Completed`) | End |
| **Failed** | Terminal failure (unrecoverable step or HARD-ABORT without usable continuation) | End |
| **Interrupted** | Timeout / external interrupt before terminal success | End (or Orchestration schedules Retry with **new** `run_id`) |
| **Retry** | Control state: transient failure scheduled | → Running **only** with a **new** `run_id` / → Failed |

**Notes:**

- Shadow runs use the same state machine with `mode=shadow`; failures are **fail-open** to primary path (Zero User Impact).  
- `Retry` is never a Result `status` (§4.3). Default policy: **new `run_id` per attempt** (CDR-M-003).

---

# 9. Tratamento de Erros

| Classe | Policy (v1.1) |
|--------|----------------|
| **Timeout** | Exceed `timeout_ms` → `Interrupted` (+ partial step_traces). Shadow: discard shadow result, keep primary. Primary gated path: fail-open to safe Orchestration fallback **unless** integrity HARD-ABORT already returned explicit INVALID contract. |
| **Falha (step)** | Record `step.failed`; apply Appendix B fail-open; else escalate to run `Failed`. |
| **Falha (integrity)** | Apply §5.2.1: HARD-ABORT vs SOFT-SKIP vs PARTIAL — **not** absolute abort on every INVALID. |
| **Retry** | Only for **declared transient** Tool Use / I/O errors (fetch timeouts, 5xx) with bounded attempts and **new** `run_id`; **never** retry Frozen formula disagreement. Budget_token must still allow. |
| **Fallback** | Soft-404 / recovery paths remain Orchestration-initiated — EM accepts flags; does not invent intent fallback. Router `_run_fallback` is **not** EM. |
| **Cancelamento** | Spec v1.1: interrupt via timeout. Future optional `cancel(run_id)` post-Infra (CDR-M-002); when present → `Interrupted`; no CM write. |

**Anti-pattern:** Silent catch-all that hides step failures without `step_traces` (breaks Shadow).

---

# 10. Observabilidade

Mandatory for Spec-compliant EM (implementation later):

| Signal | Requirement |
|--------|-------------|
| `run_id` / `pipeline_id` / `mode` | On every run |
| Per-step timing | duration_ms in `step_traces` |
| Per-step status | started/completed/skipped/failed + reason (incl. `integrity_soft_skip_fixture_located`) |
| Engine identity | module name + existing version metadata if already exposed |
| Budget / cache outcomes | From Tool Use port metadata (hit/miss/blocked) — not invented |
| Shadow diff handle | When `mode=shadow` |
| Correlation | `session_id` + `trace_parent` without writing subject |

Aligns with Research 022 auditability theme without mandating a vendor.

---

# 11. Shadow

| Rule | Spec |
|------|------|
| Default | **OFF** (REGRA 23) |
| Purpose | Dual-run EM vs legacy unified `_run_analyze` / `_run_live` (and thin pipelines as extracted) |
| User impact | **None** — student mode; primary path remains legacy blob until gated sole path |
| Compare | **Appendix A** mandatory keys + declared noise allowlist; Plan/Infra may extend allowlist but must not drop mandatory keys |
| Fail posture | Shadow failure **never** breaks primary |
| CM | Shadow EM **must not** write subject; §4.7 always NO in shadow |
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
| **2 Infra** | Contracts, Step Runner scaffolding, illegal matrix (§12.1), tests |
| **3 Shadow** | Dual-run observe-only |
| **4 Sole path (gated)** | EM becomes **official** unified executor behind flags; legacy `_run_*` may remain as **shim** until retirement mission (dual-SoT **window** — CDR-M-006) |
| **5 PGR ladder** | One Gate, One Decision per percentage |
| **6 Stabilization** | Trust question defaults-OFF SoT |
| **FA** | Final Acceptance of EM AEL cycle — Activation residuals explicit (mirror drift NO-GO honesty) |

**Rules:** Auto-advance = False; REGRA 27; Plateau Validation REGRA 28; await PO between gates.

### 12.1 Illegal flag-combination principles (CDR-L-003)

Sketch only — final env names in Implementation Plan:

| Principle | Illegal |
|-----------|---------|
| Shadow + sole conflicting | Shadow observe-only must not be the same flag as sole-path ON without explicit dual-run harness |
| EM write flags | **No** flag may authorize EM CM sole-write (nonexistent capability) |
| Shadow CM write | Any combination that lets shadow EM commit subject |
| Defaults | Production-affecting flags default OFF |
| Legacy as Shadow substitute | Using `copilot_engine` as Shadow peer for unified clients |

---

# 13. Rollback

| Layer | Action |
|-------|--------|
| Flag rollback | Instant OFF / 0% helpers (Blueprint) |
| Shadow rollback | Disable shadow dual-run; no user impact |
| Sole-path rollback | Route Orchestration back to legacy `_run_*` in mega-router |
| Spec/docs rollback | Revert Spec commits under `observations/execution_manager_spec_revision_025/` (v1.0 remains under `…_spec_023/`) |
| Forbidden | Rollback that reopens CM writers inside EM; rollback that “fixes” Frozen engines; rollback that drops soft-analyze §5.2.1 |

Legacy `copilot_engine` remains available as parallel until retirement — **not** a substitute Shadow strategy for unified clients.

---

# 14. Segurança / guarantees

| Guarantee | Statement |
|-----------|-----------|
| **G1 CM write-free** | EM never sole-writes sport subject / STS / episode / `_save_analysis_context` equivalent |
| **G2 Determinism** | Analyze Frozen step order fixed; no LLM step selection |
| **G3 Tool Use separation** | No Tool Registry inside EM; ports only |
| **G4 Frozen consume-only** | Engine formulas untouchable by EM missions |
| **G5 Zero User Impact default** | Flags OFF; Shadow fail-open |
| **G6 One official executor (with window)** | After sole-path ON, one *official* unified executor; `_run_*` shim allowed until retirement mission; `copilot_engine` never counts as Shadow substitute; Discovery three-path risk acknowledged during climb (CDR-M-006) |
| **G7 Budget respect** | I/O steps honor budget_token / may-run; EM never owns turn `begin_request` |
| **G8 Traceability** | Every run yields step_traces suitable for Shadow parity |
| **G9 Isolation from CM host** | EM Step Runner must not reuse STS checkpointer as write SSOT |
| **G10 Router conversational purity** | Greeting/help/identity/capabilities/fallback never enter EM |
| **G11 Soft-analyze preservation** | §5.2.1 + §4.6 soft-try must remain; absolute INVALID abort is forbidden |
| **G12 CM eligibility outside EM** | §4.7 predicates live in Orchestration/CM path |

---

# 15. Testabilidade

| Class | Intent (Spec — tests run in later missions) |
|-------|-----------------------------------------------|
| Contract tests | `ExecutionRequest` / `ExecutionResult` schema; closed status enum; illegal fields rejected |
| Pipeline order tests | Analyze A3–A10 order frozen snapshot |
| Gate tests | §5.2.1 golden cases 1–5 (HARD-ABORT / SOFT-SKIP / PARTIAL / soft-try / no CM on INVALID) |
| Port mock tests | FetchFixture / FetchLiveFeed failures → Retry/Failed per policy |
| Thin pipeline tests | bankroll/learning/knowledge assembly without engines |
| Shadow harness | Appendix A mandatory keys vs captured `_run_analyze` golden payloads |
| Boundary tests | Assert EM module has **no** calls to subject writers / `_save_analysis_context` / `attach_match_card` / `begin_request` |
| Orchestration wrap tests | Soft-try still invokes EM; eligibility matrix YES/NO |
| Non-regression | Existing analyze/live integration tests remain green on legacy path while flags OFF |
| Negative | LLM-router / hierarchical manager **absent** from EM core |

---

# 16. Critérios de Frozen

EM AEL cycle may be declared **FROZEN** (Final Acceptance) only when **all** apply:

| ID | Criterion |
|----|-----------|
| F1 | Spec **v1.1** (this document) PO-accepted; CDR2/AAR completed under later missions without violating locked family |
| F2 | Implementation follows Deterministic Sequential Pipeline + Step Runner + Shadow-first + CM-write-free + Tool Use separado |
| F3 | Analyze Frozen engine order unchanged vs Mission 021 surface (or ADR-authorized change — none in this Spec) |
| F4 | Shadow dual-run evidence recorded; fail-open proven; Appendix A keys compared |
| F5 | Defaults OFF / 0% in repo for production-affecting flags |
| F6 | PGR ladder discipline documented; no bundled gates |
| G/F7 | Boundary tests prove no CM sole-write from EM; no `_save_analysis_context` in EM |
| F8 | Tool Use remains ported; no in-EM registry absorbing API/web |
| F9 | Greeting/help/identity/capabilities/fallback remain Router |
| F10 | Legacy `copilot_engine` retirement **pre-declared** (may still be present — honesty residual OK if Activation NO-GOs listed) |
| F11 | Mirror drift treated honestly (OPEN = Activation NO-GO) |
| F12 | Dual Reporting present on FA; await PO; no auto-start next module |
| F13 | Master / Blueprint not casually rewritten by EM implementation missions (governed reopen only) |
| F14 | Soft-analyze / §5.2.1 golden cases proven; Orchestration wrap + §4.7 eligibility proven |

**Technical Spec acceptance ≠ authorization to implement or activate.**  
This mission ends at Spec v1.1 + Dual Reporting. **Do not start CDR2.**

---

## Migration target (descriptive — not Plan)

1. Spec v1.1 accepted (this mission) → CDR2 (later, PO-gated) → Implementation Plan + Readiness (later).  
2. Prep/Infra with defaults OFF.  
3. Shadow vs `_run_analyze` / `_run_live` (Appendix A).  
4. Gated sole path for unified helper; legacy retirement mission separate; dual-SoT window explicit.  
5. Do not couple full Tool Use registry or Activation full-env in the same climb without own gates.

---

## Explicit non-starts

| Item | Status |
|------|--------|
| Product code | **NOT STARTED** |
| ADR | **NOT CREATED** |
| Master / SSOT / Blueprint edits | **NOT DONE** |
| CDR2 | **NOT STARTED** — await PO |
| AAR | **NOT STARTED** |
| Implementation Plan | **NOT STARTED** |

---

## Appendix A — Shadow minimum compare keys (CDR-M-004)

| Class | Keys / signals | Mandatory? |
|-------|----------------|------------|
| Identity | `pipeline_id`, terminal `status`, `abort_reason` | YES |
| Integrity | `fixture_quality`, fiction/entity_invalid markers when present | YES |
| Markets | `best_markets` (ids/labels/order as semantic) | YES |
| Engine order | `step_traces[].step_id` sequence for A3–A10 | YES |
| Soft-skip | A2 skip reason when SOFT-SKIP | YES |
| Fixture | `fixture_id` presence/equality when located | YES |
| Noise (deferred allowlist) | timestamps, DRS stamp churn, non-semantic narrative whitespace | Compare-tolerant / allowlisted later |

---

## Appendix B — Step × fail-open matrix (CDR-L-004)

Cite Mission 021 / SoT `_run_analyze` culture; Plan may refine without changing §5.2.1.

| Step | On failure | Policy |
|------|------------|--------|
| A0 budget_check | may-run false | Skip/block I/O steps per token; do not invent fetch |
| A1 fetch_fixture | soft miss / error | Soft culture — continue toward integrity assess; Orchestration soft-404 may re-issue |
| A2 integrity_gate | — | §5.2.1 outcomes (not generic fail-open) |
| A3–A10 Frozen engines | exception / empty | Prefer record `step.failed` + fail-open where today’s culture continues; else Failed — Plan snapshots line-level culture |
| A9 memory/knowledge | miss | Fail-open consult empty (consume) |
| A11–A12 assembly | helper error | Fail-open defaults consistent with today |
| A13 fields | missing | Omit fields; Router owns card |
| L1 fetch_live | error | Retry/Failed per I/O policy |
| Thin DB loads | empty/error | Thin empty payload / Failed per today’s thin helpers |

---

## Handoff

**Await Product Owner** acceptance of Spec Execution Manager **v1.1**.  
Do **not** start CDR2, AAR, or implementation.

---

*End of SPEC_EXECUTION_MANAGER_v1.1.md*
