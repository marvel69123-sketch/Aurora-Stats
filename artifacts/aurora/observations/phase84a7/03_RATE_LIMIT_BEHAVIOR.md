# 8.4-A.7 — Rate Limit Behavior

## Policy

Errors matching:

- `Too many requests`
- `429`
- `rate limit` / `api_fetch limit`

**MUST NOT** produce a hard “não consigo analisar” / refusal executive.

They **MUST**:

1. Apply a confidence penalty (`InferenceContext.register_failure` + optional `rate_limit` stage)
2. Keep `preliminary_analysis = true` when entities are valid and min signals exist
3. Mention the limitation in the preliminary text (without inventing missing numbers)

## Implementation

| Layer | Behavior |
|-------|----------|
| `analyze._safe_get` | On soft failure + rate-limit match → penalty + note “mantendo análise preliminar”; return empty response list |
| `InferenceContext.register_failure` | Detects rate-limit detail → min penalty 1.0; does not invent a football “missing slot” for pure `api_rate_limit` |
| `allow_partial_analysis(rate_limited=True)` | Allows preliminary even if completeness &lt; 0.20 when min signals exist |
| `resolve_preliminary_confidence` | Extra −0.8 when rate-limited; floor still ≥ 2.0 |
| `build_preliminary_executive` | Explicit sentence about unavailable signals due to request limit |

## Expected user-visible outcome

Useful preliminary reading + reduced confidence + explicit limitation — not abort.
