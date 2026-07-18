# AEP Phase 3 — Metrics

| Metric | Definition |
|--------|------------|
| **Frustration Rate** | % sessions with ≥1 frustration signal |
| **Recovery Rate** | % frustrated sessions that later recovered |
| **Turns Until Frustration** | Average turn index of first frustration |
| **Repeated Frustration Rate** | % frustrated sessions with ≥2 events |
| **Top Frustration Causes** | Ranked `frustration_type` counts |

## Entity / audit log fields

- `frustration_detected`
- `frustration_type`
- `frustration_score`
- `recovered_after_frustration`
- `recovery_turns`

## JSON shape

```json
{
  "total_sessions": 1000,
  "frustration_rate": 3.2,
  "recovery_rate": 89.1,
  "top_causes": ["MISUNDERSTANDING", "TOO_GENERIC"]
}
```
