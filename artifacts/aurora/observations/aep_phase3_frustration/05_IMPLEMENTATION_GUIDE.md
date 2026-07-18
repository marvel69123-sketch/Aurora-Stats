# AEP Phase 3 — Implementation Guide

## Run

```bash
cd artifacts/aurora
python scripts/run_frustration.py --sessions 100
python scripts/run_frustration.py --sessions 1000 --quiet
```

## With Simulator / AEP

```bash
python scripts/run_simulations.py --runs 100 --quiet
# → last_simulation.json includes frustration_analytics

python scripts/run_evals.py
# → repair / confusion cases expose frustration_* entity fields
```

## developer_audit_mode

Call `/aurora/copilot` with `"debug": true`.  
When frustration fields are present on `entities`, they also appear under:

```json
{ "debug": { "frustration": { "frustration_detected": true, "frustration_type": "MISUNDERSTANDING", ... } } }
```

## Add a marker

1. Append to `_MARKER_SPECS` in `frustration_observability.py`
2. Add phrase to `FRUSTRATION_PHRASES` / scenarios if needed
3. Re-run `run_frustration.py`

## Do not

- Rewrite `executive_summary` from this layer
- Treat frustration analytics exit code as a hard deploy gate (UX signal, not structural SoT)
