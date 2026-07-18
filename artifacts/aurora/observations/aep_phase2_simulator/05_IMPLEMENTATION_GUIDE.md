# AEP Phase 2 — Implementation Guide

## Run

```bash
cd artifacts/aurora
python scripts/run_simulations.py --runs 100
python scripts/run_simulations.py --runs 1000
python scripts/run_simulations.py --runs 5000 --quiet
python scripts/run_simulations.py --runs 10000 --quiet --seed 7
python scripts/run_simulations.py --runs 100 --persona chaotic
```

Output: `tests/simulator/results/last_simulation.json`

## Promote a discovery to AEP

1. Open `failure_details` in the JSON report
2. Copy the failing turn sequence into `tests/evals/<category>/cases.json`
3. Add hard `expect` keys (`fixture_reused`, `intent`, `no_loop`, …)
4. Gate with `python scripts/run_evals.py`

## Add a persona

1. Add utterance bank + `script_*` in `tests/simulator/personas.py`
2. Register in `PERSONAS` + `_GENERATORS`
3. Smoke with `--persona <id> --runs 100`

## Do not

- Patch engines to silence simulator noise
- Invent match odds inside persona banks
- Treat simulator exit code as deploy gate (exploratory by default) — use AEP for gates
