# AEP — Evaluation Runner

## Command

From `artifacts/aurora`:

```bash
python scripts/run_evals.py
```

Optional filters:

```bash
python scripts/run_evals.py --category capabilities
python scripts/run_evals.py --id cap_001_o_que_voce_faz
python scripts/run_evals.py --json-out observations/aep_v1/last_run.json
```

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | All cases PASS |
| 1 | One or more FAIL |
| 2 | No cases selected |

## Validations (Phase 1)

| Signal | How measured |
|--------|----------------|
| intent | `response.intent` |
| owner | `entities.response_owner` / `turn_owner` (observational) |
| followup recovery | `followup_context_found` / `continuity_followup` / intent `follow_up` |
| context reuse | `fixture_reused` expectation (continuity signals) |
| invalid fixture | `fixture_quality == INVALID` + `entity_invalid` |
| loops | sticky small-talk markers in `executive_summary` |
| repair | `repair_mode` / `conversation_repair` / `repair_reclassified` |

## Log fields (per case)

- `evaluation_score` — 1.0 PASS, 0.0 FAIL (0.25 near-miss intent)
- `evaluation_pass` — boolean
- `evaluation_fail_reason` — semicolon-joined assertion failures
- `loop_detected` — boolean
- `frustration_detected` — boolean (user utterance markers)
- `context_preserved` — boolean when followup/fixture reuse asserted

## Report shape

```
---------------------------------
TOTAL: N
PASS : P
FAIL : F
SUCCESS RATE: R%
SCORE AVG: S
---------------------------------
```

Full machine-readable dump: `observations/aep_v1/last_run.json`.
