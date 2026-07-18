# Fase 8.2-C — Files Changed

| Arquivo | Tipo | Mudança |
|---------|------|---------|
| `src/conversation/short_conversation_memory.py` | **NOVO** | Memória + resolve de pronomes |
| `src/routers/copilot_unified_router.py` | wire | `apply_short_memory_resolve` pré-MasterIntent; `note_short_memory` no fim |
| `scripts/phase82c_short_memory_smoke.py` | **NOVO** | Smoke T1–T3 |
| `observations/phase82c/*` | docs | Entregáveis |

## Não alterados

- `conversation_repair.py` (só import read-only de `is_repair_signal`)
- ownership / confidence / 7.9 / GA / sports engines
- `natural_conversation.py` / HIE / Recovery
