# AEP Phase 3 — Detectors

## User markers

| Signal | Default category |
|--------|------------------|
| não entendeu / você não entendeu | MISUNDERSTANDING |
| não foi isso | WRONG_INTENT |
| preste atenção | MISUNDERSTANDING |
| releia | MISUNDERSTANDING |
| pensa / pensa um pouco | MISUNDERSTANDING |
| ??? | TOO_GENERIC |
| aff | TOO_GENERIC |
| hã? | MISUNDERSTANDING |
| não respondeu | INVALID_RESPONSE |
| isso está errado | HALLUCINATION_RISK |

## Categories

- `MISUNDERSTANDING`
- `LOST_CONTEXT` — refined when prior intent was GA/small_talk
- `TOO_GENERIC` — refined when prior reply was sticky loop
- `WRONG_INTENT`
- `REPETITION` — second+ frustration in session
- `INVALID_RESPONSE`
- `OVER_REFUSAL`
- `HALLUCINATION_RISK`

## Recovery

After a frustration event, the next (or same-turn) reply is `recovered=true` when it is substantive and not a sticky GA loop (repair / capabilities / follow-up / continuity count as recovery).
