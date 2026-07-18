# 8.4-A.9 — Regression Results

Smoke: `scripts/phase84a9_capabilities_smoke.py` → **PASS**

| Case | Input | Result |
|------|-------|--------|
| 1 | o que você faz? | `assistant_capabilities` |
| 2 | suas funcionalidades | `assistant_capabilities` |
| 3 | aurora funcionalidades | `assistant_capabilities` |
| 4 | o que sabe fazer? | `assistant_capabilities` |
| 5 | … + você não entendeu | reclass `True`, intent capabilities |
| 6 | oi → quem é você? → o que você faz? | small_talk → identity → capabilities |

Non-regression:

- `phase84a7_partial_analysis_smoke.py` → **PASS**
- `phase84a8_followup_continuity_smoke.py` → **PASS**
