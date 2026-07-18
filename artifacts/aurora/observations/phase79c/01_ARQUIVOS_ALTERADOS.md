# Fase 7.9-C — Documento 1: Arquivos Alterados

| Arquivo | Ação |
|---------|------|
| `src/conversation/turn_ownership.py` | defer GA general; presence pass; logs OWNER_* + FINAL_SOURCE; overwrite_blocked |
| `src/routers/copilot_unified_router.py` | `can_presence_claim` nos gates; `finalize_presence_ownership`; FINAL_SOURCE pré-response |
| `scripts/phase79c_p0_3_smoke.py` | smoke obrigatório |
| `tests/test_ownership_79c.py` | unit tests |

**Não alterados:** NRF, fallback forced, intents, GA, Recovery, Frontend, UX
