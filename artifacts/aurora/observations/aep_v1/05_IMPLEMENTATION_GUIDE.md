# AEP — Implementation Guide

## Add a new eval case

1. Open (or create) `tests/evals/<category>/cases.json`
2. Append an object:

```json
{
  "id": "reg_00x_short_name",
  "category": "regression",
  "description": "why this guards a real bug",
  "steps": [
    {"message": "first user turn"},
    {"message": "second user turn"}
  ],
  "expect": {
    "intent": "assistant_capabilities",
    "followup_found": true,
    "fixture_reused": true,
    "fixture_quality": "INVALID",
    "entity_invalid": true,
    "repair_mode": true,
    "no_loop": true,
    "no_invented_analysis": true
  }
}
```

3. Run:

```bash
python scripts/run_evals.py --id reg_00x_short_name
```

4. Commit the JSON case with the product patch that should keep it green.

## Expect keys (Phase 1)

| Key | Meaning |
|-----|---------|
| `intent` | Exact intent string (or list of allowed) |
| `followup_found` | Continuity recovered on last turn |
| `fixture_reused` | Prior fixture/context reused |
| `fixture_quality` | e.g. `INVALID` |
| `entity_invalid` | Fiction / invalid entities |
| `repair_mode` | Repair path active |
| `no_loop` | Ban sticky small-talk loops |
| `no_invented_analysis` | Refuse fake market/analysis text on INVALID |

## CI / pre-deploy gate (recommended)

```bash
cd artifacts/aurora
python scripts/run_evals.py
```

Treat exit code `1` as deploy blocker.

## Do not

- Patch engines from inside AEP to force green tests
- Invent match odds / fixtures inside cases
- Put secrets or live DB dumps in `cases.json`

## Phase 2 next steps (design only)

1. Frustration Analytics module reading harness log fields
2. Conversation Simulator emitting JSON cases into `tests/evals/regression/`
3. LLM Judge as optional soft score column
4. Health Center consuming `last_run.json` history
