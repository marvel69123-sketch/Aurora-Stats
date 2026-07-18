# AEP — Architecture (v1.0)

## Purpose

Aurora Evaluation Platform (AEP) is a **permanent, non-invasive** evaluation layer that runs scripted conversations against `/aurora/copilot` and asserts conversational correctness **before deploy**.

Hard rule: **evaluation framework only** — no changes to Opinion Renderer, Followup Engine, Market Engine, Calendar, Partial Analysis, Ownership, or sport engines.

## Phase 1 (implemented)

```
scripts/run_evals.py          # CLI runner
tests/evals/
  harness.py                  # client + validators + scoring
  schema.py                   # case schema validation
  capabilities/cases.json
  followups/cases.json
  football/cases.json
  repair/cases.json
  onboarding|identity|partial|regression/cases.json  # reserved
observations/aep_v1/          # docs + last_run.json
```

### Runtime flow

1. Load all `tests/evals/**/cases.json`
2. For each case: open a dedicated `session_id`, POST each step to `/aurora/copilot` with `debug=true`
3. Extract observed signals from response + `entities` audit fields
4. Compare against `expect` (intent, followup, invalid, repair, loops)
5. Emit per-case logs + aggregate PASS/FAIL/SCORE report

### Isolation guarantees

| Layer | Touched? |
|-------|----------|
| Engines / ownership / market / calendar / partial | No |
| Copilot HTTP surface | Read-only (TestClient) |
| Case definitions | JSON under `tests/evals/` |
| Scoring / loop / frustration heuristics | Inside harness only |

## Phase 2 (planned — not implemented)

### 1) Frustration Analytics — **implemented** (`tests/frustration/`, `scripts/run_frustration.py`)

- Detects markers + classifies cause; tracks recovery
- Stamps `frustration_*` on entities; `debug.frustration` in audit mode
- Does **not** change production reply text

### 2) Conversation Simulator — **implemented** (`tests/simulator/`, `scripts/run_simulations.py`)

- Generates multi-turn scripts from 5 personas
- Seeds only **user** utterances (never invent match facts)
- Auto-detects loops / context loss / intent flips / hallucination risk
- Results: `tests/simulator/results/last_simulation.json`

### 3) LLM Judge — **implemented** (`tests/judge/`, `scripts/run_llm_judge.py`)

- Rubric scores 0–10 (+ optional LLM soft blend)
- Always subordinated to hard assertions (intent/owner/invalid/loops)
- Judge cannot override an INVALID / no-invention credibility floor

### 4) Aurora Health Center — **implemented** (`scripts/run_health_center.py`)

- Consolidates AEP + Simulator + Frustration + Judge → `observations/health/health_report.json`
- Health score = weighted blend (success, loops, context, frustration, recovery, LLM scores)
- Trend tracked in `observations/health/history.json`

```
┌────────────┐   ┌──────────────────┐   ┌─────────────┐
│ Case Bank  │──▶│ Eval Runner (P1) │──▶│ Report JSON │
└────────────┘   └────────┬─────────┘   └──────┬──────┘
                          │                    │
               ┌──────────▼──────────┐         │
               │ Simulator (P2)      │         │
               └──────────┬──────────┘         │
                          │                    │
               ┌──────────▼──────────┐   ┌─────▼────────┐
               │ LLM Judge (P2)      │──▶│ Health Center│
               └─────────────────────┘   └──────────────┘
```
