# AEP Phase 2 — Conversation Simulator Architecture

## Goal

Discover **unknown** conversational failures at scale — without human-driven chats and without changing production engines.

## Layout

```
scripts/run_simulations.py
tests/simulator/
  personas.py      # 5 personas + script generators
  detectors.py     # automatic failure flags
  engine.py        # session runner via TestClient
  metrics.py       # aggregate KPIs + JSON report
  results/         # last_simulation.json
```

## Flow

```
RNG seed
  → Persona picker
  → Multi-turn user script (utterances only)
  → POST /aurora/copilot (debug)
  → Detectors per turn
  → Conversation success / fail
  → Aggregate metrics JSON
```

## Isolation

| Layer | Touched? |
|-------|----------|
| Market / Opinion / FollowUp / Calendar / Ownership / Partial | No |
| Copilot HTTP | Read-only (TestClient) |
| AEP eval cases | Untouched (parallel track) |

## Scale

`--runs` ∈ {100, 1000, 5000, 10000} (or `--allow-custom-runs`).

## Integration with AEP v1

- Simulator **discovers**; AEP cases **guard** known regressions.
- Promote recurring simulator failures into `tests/evals/**/cases.json`.
- Shared loop / frustration heuristics from `tests/evals/harness.py`.
