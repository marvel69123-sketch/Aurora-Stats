# Regression risks — 8.3-B

| Risk | Mitigation |
|------|------------|
| Cold `"sim"` rewritten | Requires `active` continuity + team |
| Repair signal rewritten | `is_repair_signal` short-circuits resolve |
| Window never expires | Decay each non-resolve turn; max 3 |
| Wrong team | Prefer continuity → short → repair memory |
| GA still steals | Rewrite forces SPORT_QUERY via MasterIntent |
