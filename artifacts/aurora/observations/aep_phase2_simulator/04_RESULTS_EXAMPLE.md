# AEP Phase 2 — Results Example

## Target JSON shape

```json
{
  "total_runs": 5000,
  "success_rate": 94.3,
  "loops": 21,
  "context_loss": 7,
  "fallbacks": 31,
  "top_failures": [
    {"reason": "loop_detected", "count": 21},
    {"reason": "context_lost", "count": 7}
  ]
}
```

Full report also includes `metrics`, `by_persona`, and `failure_details`.

## Live 100-run snapshot (seed=42)

```
TOTAL RUNS: 100
SUCCESS RATE: 57.0%
LOOPS: 43
CONTEXT LOSS: 0
FALLBACKS: 0
INTENT FLIPS: 4
CONTEXT PRESERVATION: 100.0%
INTENT ACCURACY: 100.0%
AVG TURNS BEFORE FAIL: 1.74
```

| Persona | Success | Fail | Insight |
|---------|---------|------|---------|
| beginner | 19 | 0 | stable |
| short_followup | 20 | 0 | 8.4-A.8/A.10 holding |
| confused | 16 | 4 | some repair/loop gaps |
| chaotic | 2 | 18 | early pronouns / fiction edges |
| advanced | 0 | 21 | kelly/xG/pressão → GA loop after fixture |

Top failure: `loop_detected` (43). Source: `tests/simulator/results/last_simulation.json`.
