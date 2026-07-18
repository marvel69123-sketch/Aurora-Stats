# Health Center — Metrics

| Metric | Source |
|--------|--------|
| Overall Health Score | Weighted blend 0–100 |
| Conversation Success | Simulator success rate |
| AEP Success | AEP `success_rate` |
| Loop Rate | Simulator `loop_rate` |
| Context Preservation | Simulator metrics |
| Frustration Rate | Organic simulator frustration |
| Recovery Rate | Frustration suite |
| LLM Overall Score | Judge `overall` |
| Naturalness / Credibility | Judge dimensions |
| Trend by Version | `history.json` + `backend_commit` |

## Compact output

```json
{
  "health_score": 91.4,
  "status": "Muito Boa",
  "loop_rate": 0.3,
  "frustration_rate": 2.1,
  "llm_overall": 8.4,
  "trend": "up"
}
```
