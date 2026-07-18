# 8.4-A.11 — Advanced Football Continuity

## Module

`src/conversation/advanced_football_continuity.py`

## Position

```
… → pronoun continuity → Advanced Football Continuity → MasterIntent / GA
```

## Detected terms

xg / expected goals · pressão · momentum · kelly · odd justa · probabilidade · value · edge · stake · confiança  
(+ market-adjacent: ambas marcam, over/under lines)

## Behavior

| Prior context | Action |
|---------------|--------|
| Valid/PARTIAL fixture | Reuse fixture; conceptual answer or FollowUp engine content |
| INVALID fiction | Refuse — no invented metrics |
| No fixture | Skip (fail-open to normal routing) |

## Audit

- `advanced_term_detected`
- `advanced_term`
- `advanced_fixture_reused`
- `advanced_before_fallback`
