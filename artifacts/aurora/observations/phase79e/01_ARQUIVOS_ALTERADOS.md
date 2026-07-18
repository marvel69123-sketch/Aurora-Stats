# Fase 7.9-E — Documento 1: Arquivos Alterados

| Arquivo | Papel |
|---------|--------|
| `src/conversation/master_intent_router.py` | prioridade + LIVE_LISTING + UTILITY + EMOTIONAL + logs |
| `src/conversation/emotional_presence.py` | classificador sadness/loneliness/support |
| `src/conversation/general_assistant.py` | entrega UTILITY_QUERY; EMOTIONAL → None |
| `tests/test_misroute_79e.py` | unit |
| `scripts/phase79e_misroute_smoke.py` | smoke obrigatório |

**Não alterados:** NRF, ownership, forced ownership, fallback, frontend, UX
