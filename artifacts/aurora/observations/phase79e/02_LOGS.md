# Fase 7.9-E — Documento 2: Logs

```text
[INTENT_BEFORE] message_prefix=quais jogos estão ao vivo? prev_intent=none
[INTENT_AFTER]  intent=LIVE_MATCH confidence=0.94 sport_ok=True
[ROUTE_REASON]  intent=LIVE_MATCH reason=live_listing sport_ok=True
```

```text
[INTENT_AFTER] intent=UTILITY_QUERY reason=utility_time sport_ok=False
[INTENT_AFTER] intent=EMOTIONAL_QUERY reason=emotional:sadness sport_ok=False
```

Stdout: `observations/phase79e/smoke_stdout.txt`
