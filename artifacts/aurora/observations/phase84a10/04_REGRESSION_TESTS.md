# 8.4-A.10 — Regression Tests

## Smoke

```bash
python scripts/phase84a10_pronoun_continuity_smoke.py
```

## AEP permanent gate

`tests/evals/pronouns/cases.json`

| ID | Conversation | Expect |
|----|--------------|--------|
| `pr_001_e_dele_fixture_reuse` | Argentina x Brasil → e dele? | `fixture_reused=true` |
| `pr_002_e_o_outro_entity` | Barcelona x Real Madrid → e o outro? | `entity_resolved=true` |
| `pr_003_e_esse_time_followup` | Flamengo x Palmeiras → e esse time? | `followup_found=true` |
| `pr_004_invalid_no_invention` | Goku x Naruto → e dele? | `INVALID` + no invented analysis |

Also covered by legacy gate `followups/fu_002_e_dele_fixture_reuse`.

```bash
python scripts/run_evals.py --category pronouns
python scripts/run_evals.py
```
