# AEP Phase 4 — LLM Judge Architecture

## Goal

Automatically score conversational quality (0–10) without changing production engines.

## Components

```
src/conversation/judge_rubric.py           # deterministic rubric SoT
src/conversation/llm_judge_observability.py # entity/debug stamp
tests/judge/
  engine.py / metrics.py / optional_llm.py
scripts/run_llm_judge.py
```

## Modes

1. **Rubric (default)** — scores from observables (intent, continuity, loops, INVALID honesty, length, frustration recovery).
2. **LLM soft blend (optional)** — `AURORA_JUDGE_LLM=1` + API key; cannot override low credibility floors.

## Integrations

| Surface | Integration |
|---------|-------------|
| Conversation Simulator | `llm_judge` slice on simulation JSON |
| Frustration Analytics | shares session turns / recovery signals in rubric |
| developer_audit_mode | `debug.llm_judge` via `attach_debug_to_payload` |
