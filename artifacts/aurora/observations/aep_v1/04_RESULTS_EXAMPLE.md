# AEP — Results Example

## First live run (2026-07-18) — real output, not invented

```
[PASS] capabilities/cap_001_o_que_voce_faz score=1.0 ms=186
[PASS] followups/fu_001_mercados_after_match score=1.0 ms=577
[FAIL] followups/fu_002_e_dele_fixture_reuse score=0.0 ms=355 reason=fixture_reused_expected_True_got_False;loop_detected
[PASS] football/fb_001_goku_naruto_invalid score=1.0 ms=92
[PASS] repair/rp_001_voce_nao_entendeu score=1.0 ms=68
---------------------------------
TOTAL: 5
PASS : 4
FAIL : 1
SUCCESS RATE: 80.0%
SCORE AVG: 0.8
---------------------------------
```

**Regression caught:** after `Argentina x Brasil`, `e dele?` fell into `general_chat` + sticky loop (`Entendi. Posso te ajudar…`) instead of reusing fixture context. Case kept as FAIL gate until product continuity covers pronoun follow-ups.

## Target shape (all green)

```
---------------------------------
TOTAL: 5
PASS : 5
FAIL : 0
SUCCESS RATE: 100.0%
SCORE AVG: 1.0
---------------------------------
JSON report: observations/aep_v1/last_run.json
```

## Failure example

```
[FAIL] followups/fu_001_mercados_after_match score=0.0 ms=920 reason=followup_found_expected_True_got_False
---------------------------------
TOTAL: 5
PASS : 4
FAIL : 1
SUCCESS RATE: 80.0%
SCORE AVG: 0.8
---------------------------------
FAILURES:
  [followups] fu_001_mercados_after_match: followup_found_expected_True_got_False
    logs: evaluation_pass=False evaluation_score=0.0 loop_detected=False frustration_detected=False context_preserved=None
```

## JSON fragment

```json
{
  "platform": "AEP",
  "version": "1.0",
  "summary": {
    "total": 5,
    "pass": 5,
    "fail": 0,
    "success_rate": 100.0,
    "evaluation_score_avg": 1.0
  },
  "results": [
    {
      "id": "cap_001_o_que_voce_faz",
      "evaluation_pass": true,
      "evaluation_score": 1.0,
      "evaluation_fail_reason": null,
      "loop_detected": false,
      "frustration_detected": false,
      "context_preserved": null
    }
  ]
}
```

> Actual numbers come from `python scripts/run_evals.py` — never invent PASS/FAIL offline.
