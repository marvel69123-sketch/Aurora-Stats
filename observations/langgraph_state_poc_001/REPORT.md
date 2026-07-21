# LANGGRAPH-STATE-POC-001 — Phase 1–2 Report

**Type:** Proof of concept — conversational sport **state host** + Phase 2 shadow  
**Date:** 2026-07-21  
**Scope:** SportTopicState + LangGraph graph + shadow adapter + router log-only hook + tests  
**Out of scope:** Engine replacement; Response Selector changes; sole-writer / CSL replacement; inventing fixtures/odds

**Prior conclusions respected:**

| Prior | Implication for this POC |
|-------|--------------------------|
| TB-002 sticky bleed fixed | POC must reproduce Flamengo→Liverpool→soft FU without re-bleed |
| 14 write-owners / SSOT design (`topic_state_centralization_001`) | LangGraph hosts STS as future SSOT shape; Phase 2 does not collapse live writers |
| KEEP CUSTOM TRANSITION (`topic_transition_arch_001`) | Detection stays Aurora rules (reuse TB-V2 helpers); LangGraph is host/orchestration only |

---

## 1. Architecture proposed (aspirational)

```text
User → SLL → LangGraph State (SportTopicState) → Engines → Response Selector
```

**Phase 1 status:** infrastructure under `artifacts/aurora/`.  
**Phase 2 status:** shadow compare wired **log-only** behind `ENABLE_LANGGRAPH_STATE_SHADOW`.  
Production write path (`ENABLE_LANGGRAPH_STATE`) remains **OFF** by default.

See also `ARCHITECTURE.md`.

---

## 2. Files

| Path | Purpose |
|------|---------|
| `artifacts/aurora/src/conversation/sport_topic_state.py` | `SportTopicState` + both flags |
| `artifacts/aurora/src/conversation/langgraph_state_graph.py` | Minimal graph + classify + single `_commit` writer |
| `artifacts/aurora/src/conversation/langgraph_state_adapter.py` | `shadow_from_ctx` / `compare_shadow` / `maybe_shadow_compare` |
| `artifacts/aurora/src/routers/copilot_unified_router.py` | Phase 2: fail-open `maybe_shadow_compare` after SLL/CSL/intent |
| `artifacts/aurora/tests/test_langgraph_state_poc_001.py` | Phase 1 unit tests |
| `artifacts/aurora/tests/test_langgraph_state_shadow_002.py` | Phase 2 shadow tests |
| `observations/langgraph_state_poc_001/shadow/` | Runnable harness + `shadow_compare.json` |
| `observations/langgraph_state_poc_001/REPORT.md` | This report |
| `observations/langgraph_state_poc_001/ARCHITECTURE.md` | Graph + component diagram |

**Not modified (confirmed):** `methodology_engine`, `market_engine`, `confidence_engine`,
`intelligence_engine`, `learning_engine`, Response Selector, CSL/SRF/short_mem/continuity
implementations (beyond read-only shadow projection). Sports engines untouched.

---

## 3. Feature flags (important)

| Flag | Default | Meaning |
|------|---------|---------|
| `ENABLE_LANGGRAPH_STATE` | **OFF** (`0`) | Production LangGraph **write** path (Phase 3+). Remains OFF. |
| `ENABLE_LANGGRAPH_STATE_SHADOW` | **OFF** (`0`) | Phase 2 **shadow** log-only OLD vs NEW. Enable with `1`. |

**Shadow ≠ production activation.** Turning shadow ON does **not** enable sole-writer,
does **not** replace CSL writes, and does **not** route responses through LangGraph.

Parse: unset / `0` / `false` / `off` / `no` → OFF; `1` / `true` / `on` / `yes` → ON
(same pattern as `ENABLE_TOPIC_BOUNDARY_V2`).

Rollback shadow: `ENABLE_LANGGRAPH_STATE_SHADOW=0` (or unset).

---

## 4. Phase 2 — Shadow mode

### Behavior

1. After SLL + TB-V2 + CSL + sport-intent (fail-open try/except), router calls
   `maybe_shadow_compare(message, ctx)` when shadow flag ON.
2. Captures **OLD_STATE** from ctx (CSL / last_* / SRF / episode / intent) — read-only.
3. Runs LangGraph STS update on an **isolated copy** (`force=True`) → **NEW_STATE**.
4. Logs `[AUDIT] LANGGRAPH_SHADOW OLD_STATE=... NEW_STATE=...` with fixture / episode /
   intent / teams + `contamination_locus`.
5. Returns a dict for tests; **does not** mutate live ctx subject stores, message,
   payload, or response.

### Contamination loci

| Code | Name | Meaning (Phase 2) |
|------|------|-------------------|
| (1) | `before_langgraph` | OLD already wrong vs this turn's stated fixture (legacy lag / sticky) |
| (2) | `inside_state_layer` | Message states a fixture; isolated NEW still wrong after graph |
| (3) | `after_state_commit` | N/A for live ctx (no write-back). Soft-FU keep-fail on isolated STS only |

### Critical scenario finding

**Flamengo×Palmeiras → Liverpool×Chelsea → Quem está melhor?**

With simulated multi-writer lag on T2 (ctx still Flamengo while user says Liverpool):

- **OLD** = Flamengo×Palmeiras (wrong vs message)
- **NEW** = Liverpool×Chelsea (graph boundary correct)
- **Primary locus: (1) before_langgraph**

T3 soft FU with correct prior keeps Liverpool (NEW ok). Soft FU cannot heal a
contaminated OLD if Liverpool never landed in live ctx — that contamination is
diagnosed on the switch turn as (1), not inside LangGraph classify.

Harness artifact: `observations/langgraph_state_poc_001/shadow/shadow_compare.json`

---

## 5. Comparison: multi-writer vs LangGraph STS

| Concern | Today (multi-writer) | LangGraph STS (target) |
|---------|----------------------|-------------------------|
| Sticky bleed / fixture contamination | Mitigated by TB-V2 order+clear when flag ON; residual note_* cascade | Single `_commit` owns episode rotate + subject replace |
| Ownership of subject | 14 session writers | One graph updater; OS lock remains external module |
| Duplication (last_* ↔ csl ↔ srf) | Divergent copies possible | STS snapshot is SoT; projections become read-through later |
| Transition logic | Split detectors | Aurora classify reused inside graph nodes (KEEP CUSTOM) |

---

## 6. Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Dual SoT if Phase 3 wires writes carelessly | High | Phase 2: shadow+log only; production flag OFF |
| Scope creep into engines / RS | High | Hard do-not; engines/RS untouched |
| `langgraph` missing in deploy | Low | try/except; sequential fallback in shadow; fail-open |
| False confidence that production is centralized | Med | Docs + dual flags + explicit “shadow ≠ activation” |

---

## 7. Phase 3 plan (not implemented)

1. Behind `ENABLE_LANGGRAPH_STATE`: graph influences soft-FU subject read path.
2. Boundary materialization may funnel through STS.commit while projecting to `last_*`/CSL.
3. Rollback: flag off → legacy path only. Shadow can remain for divergence metrics.

---

## 8. Tests

```powershell
$env:PYTHONPATH = ""
.\.tools\python312\python.exe -c "import sys; sys.path.insert(0, r'artifacts\aurora'); import pytest; raise SystemExit(pytest.main(['artifacts/aurora/tests/test_langgraph_state_poc_001.py', 'artifacts/aurora/tests/test_langgraph_state_shadow_002.py', '-q']))"
```

Shadow harness:

```powershell
.\.tools\python312\python.exe observations\langgraph_state_poc_001\shadow\run_shadow_harness.py
```

---

```
FACT:
Phase 2 delivers SHADOW MODE behind ENABLE_LANGGRAPH_STATE_SHADOW (default OFF).
Router hook is fail-open, log-only, isolated STS update — no production write path.
ENABLE_LANGGRAPH_STATE remains default OFF. Critical scenario locus = (1)
before_langgraph under lagging multi-writer simulation. Engines and Response
Selector untouched.

RISKS:
(1) Dual SoT if Phase 3 enables write without retiring legacy writers carefully.
(2) Soft FU inherits contaminated OLD — shadow documents this; sole-writer is Phase 3+.

RECOMMENDATION:
Phase 2 shadow is READY for staging log collection. Do NOT flip
ENABLE_LANGGRAPH_STATE until divergence metrics and soft-FU suites stay green.
```
