# Fase 7.9-A — Documento 1: Arquivos Alterados

Patch: **P0-1 only** (`ensure_soft_sections`)

| Arquivo | Ação |
|---------|------|
| `src/conversation/ensure_soft_sections.py` | **Criado** — helper defensivo |
| `src/routers/copilot_unified_router.py` | **Alterado** — chama `ensure_soft_sections` imediatamente antes de `CopilotResponse` |
| `scripts/phase79a_p0_1_smoke.py` | **Criado** — smoke dos 5 probes + forced incomplete |
| `tests/test_ensure_soft_sections_79a.py` | **Criado** — unit tests |

## Não alterados (restritos)

- NRF / `natural_response_filter`
- Ownership / `turn_ownership`
- GeneralAssistant
- Fallback / forced dict
- Recovery
- Intents / MasterIntent
- Frontend / UX / prompts
