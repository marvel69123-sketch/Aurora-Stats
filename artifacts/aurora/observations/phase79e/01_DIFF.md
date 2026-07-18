# Fase 7.9-E — Documento 1: Diff

## `master_intent_router.py`
- Removido `que horas|horario` de `_SPORT`
- Novo `_UTILITY` → `UTILITY_QUERY` (sport=False)
- Novo `_LIVE_LISTING` + plurais jogos/partidas → `LIVE_MATCH`
- `EMOTIONAL_QUERY` via `detect_emotional_intent`
- Logs: `[INTENT_BEFORE]` `[INTENT_AFTER]` `[ROUTE_REASON]`

## `emotional_presence.py` (classificador)
- Patterns: sadness, loneliness, support
- Replies mínimas para esses kinds

## `general_assistant.py` (entrega do route utility)
- `UTILITY_QUERY` → `reply_utility_time`
- `EMOTIONAL_QUERY` → `None` (emotional_presence owns)

**Não alterados:** NRF, ownership, fallback, frontend, UX visual
