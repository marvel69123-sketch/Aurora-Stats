# AEP Phase 5 — Aurora Health Center

## Goal

Unified, permanent health view consolidating:

- AEP (`observations/aep_v1/last_run.json`)
- Conversation Simulator (`tests/simulator/results/last_simulation.json`)
- Frustration Analytics (`tests/frustration/results/last_frustration.json`)
- LLM Judge (`tests/judge/results/last_judge.json`)

## Run

```bash
python scripts/run_health_center.py
python scripts/run_health_center.py --refresh --quick
```

Output: `observations/health/health_report.json`  
History: `observations/health/history.json`

## Status bands

| Score | Status |
|------:|--------|
| 95–100 | Excelente |
| 85–94 | Muito Boa |
| 70–84 | Boa |
| 50–69 | Atenção |
| &lt;50 | Crítica |

## Notes

- `frustration_rate` uses **organic** simulator signals (not the injected 100% frustration suite).
- `recovery_rate` comes from the frustration suite (by design, sessions inject friction).
- Trend compares against prior `history.json` entries (`up` / `down` / `flat`).
