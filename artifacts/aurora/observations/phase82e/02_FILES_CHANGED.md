# Fase 8.2-E — Files Changed

| Arquivo | Mudança |
|---------|---------|
| `src/conversation/context_recovery.py` | Opinion/recent-match antes de calendar; keep original |
| `src/conversation/human_inference.py` | `is_recent_match_opinion_ask`; opinion antes de calendar |
| `src/conversation/brain_authority.py` | Gate opinion permite recent-match no raw message |
| `src/conversation/intelligence_fallback.py` | Skip `calendar_authority` em recent-match opinion |
| `scripts/phase82e_opinion_routing_smoke.py` | Smoke pipeline completo |
| `observations/phase82e/*` | Docs |

## Explicitamente intactos

- `natural_conversation.detect_natural_intent`
- `conversation_repair` / `short_conversation_memory`
- ownership / ensure_soft_sections / NRF / master_intent 7.9-E
- GA
