# Fase 8.2-A — Files Changed

| Arquivo | Tipo | Mudança |
|---------|------|---------|
| `src/conversation/conversation_repair.py` | **NOVO** | Detecção, memória mínima, payload repair |
| `src/routers/copilot_unified_router.py` | wire | Early repair antes do GA; forced path; `note_repair_memory`; HCE kind allowlist |
| `src/conversation/natural_response_engine.py` | mínimo | `_ACK` + `que bom`; preservar `hce_kind=conversation_repair` |
| `scripts/phase82a_repair_smoke.py` | **NOVO** | Smoke do fluxo 8.2-A |
| `observations/phase82a/*` | docs | Este pacote de entregáveis |

## Não alterados (explícito)

- `turn_ownership.py` / ownership 7.9-C/D
- `ensure_soft_sections.py` / confidence 7.9-A
- `natural_response_filter.py` / anti-loop 7.9-B
- `master_intent_router.py` / misroutes 7.9-E
- Sports / market / decision / methodology engines
- `general_assistant.reply_general` (permanece; só deixa de ser chamado no path repair)
