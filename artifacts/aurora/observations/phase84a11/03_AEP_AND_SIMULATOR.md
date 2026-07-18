# 8.4-A.11 — AEP + Simulator Results

## AEP

```
TOTAL: 15
PASS : 15
FAIL : 0
SUCCESS RATE: 100.0%
advanced: 4/4 PASS
```

Cases: `tests/evals/advanced/cases.json`
- Argentina → xg?
- Argentina → pressão?
- Argentina → kelly?
- Argentina → qual o edge?

## Simulator (permanent persona)

```bash
python scripts/run_simulations.py --runs 100 --persona advanced_football_v2 --quiet
python scripts/run_simulations.py --runs 100 --persona advanced --quiet
```

| Persona | Success | Loops |
|---------|---------|-------|
| `advanced_football_v2` | **100%** (100/100) | **0** |
| `advanced` | **100%** (100/100) | **0** |

### Success criteria

| Criterion | Result |
|-----------|--------|
| advanced persona ≥ 95% PASS | **100%** ✓ |
| Loop Rate < 5% | **0%** ✓ |
