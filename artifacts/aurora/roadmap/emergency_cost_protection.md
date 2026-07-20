# Emergency Cost Protection Mode

**Status:** Implemented (engines untouched)  
**Default:** `EMERGENCY_COST_PROTECTION=1`, daily limit **12** (clamp 10–15 via `COST_PROTECTION_DAILY_LIMIT`)

## Behavior

| Mode | How | Network |
|------|-----|---------|
| Simple (default copilot) | Prefer fresh/stale cache; suppress duplicate analyze results (10 min TTL) | Cold miss only after stale miss |
| Premium refresh | `force_refresh=true` on copilot body or `/analyze` | Bypasses fresh cache; may hit provider |
| Cert / internal | No ECPM request scope | Unrestricted |

## Limits
- **10–15 consultas/dia** per `session_id` (copilot) or `user_id` (analyze)
- Budget exhausted → soft partial (copilot/analyze soft) or HTTP 429 (hard analyze)
- Cached analyze may still be served at zero provider cost

## Metrics
`GET /aurora/cost-protection/metrics`

- `cache_hit_rate`
- `provider_calls_per_user`
- `daily_budget_remaining`

Also stamped on analyze payloads as `_cost_protection` when scope is active.

## Files
- `src/ops/cost_protection.py`
- `src/data/ingest.py` (prefer cache/stale)
- `src/routers/analyze.py` (budget, analyze cache, metrics route)
- `src/routers/copilot_unified_router.py` (`force_refresh`, begin/end scope)
