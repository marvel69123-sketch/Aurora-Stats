# AEP Phase 3 — Results Example

## Target shape

```json
{
  "total_sessions": 1000,
  "frustration_rate": 3.2,
  "recovery_rate": 89.1,
  "top_causes": ["MISUNDERSTANDING", "TOO_GENERIC"]
}
```

## Live run (100 intentional frustration sessions, seed=42)

```
TOTAL SESSIONS: 100
FRUSTRATION RATE: 100.0%   # scenarios inject frustration by design
RECOVERY RATE: 100.0%
REPEATED FRUSTRATION RATE: 51.0%
TURNS UNTIL FRUSTRATION AVG: 2.34
TOP CAUSES: TOO_GENERIC, MISUNDERSTANDING, INVALID_RESPONSE, WRONG_INTENT, …
```

Source: `tests/frustration/results/last_frustration.json`.
