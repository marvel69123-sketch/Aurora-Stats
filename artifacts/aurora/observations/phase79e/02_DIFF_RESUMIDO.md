# Fase 7.9-E — Documento 2: Diff Resumido

1. Removido `que horas|horario` de `_SPORT`
2. `_UTILITY` → `UTILITY_QUERY` (sport=False)
3. `_LIVE_LISTING` + plurais jogos/partidas → `LIVE_MATCH`
4. `EMOTIONAL_QUERY` via `detect_emotional_intent` (antes de short_general)
5. Logs: `[INTENT_BEFORE]` `[INTENT_AFTER]` `[ROUTE_REASON]`
6. Prioridade: MATH → SYSTEM → MEMORY → **UTILITY** → **EMOTIONAL** → **LIVE_LISTING** → SPORT → SMALL → GENERAL
