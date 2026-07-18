# Fase 7.9-E — Documento 3: Antes vs Depois

| Mensagem | ANTES intent/source | DEPOIS intent/source |
|----------|---------------------|----------------------|
| quais jogos estão ao vivo? | GENERAL / Entendi | **LIVE_MATCH** / live_listing |
| quais partidas acontecendo agora? | GENERAL | **LIVE_MATCH** |
| que horas são? | SPORT | **UTILITY_QUERY** / clock |
| horário atual | SPORT/GENERAL | **UTILITY_QUERY** |
| estou triste | GENERAL / Entendi | **EMOTIONAL_QUERY** / sadness |
| me sinto sozinho | GENERAL | **EMOTIONAL_QUERY** / loneliness |
| não vou desistir de você | GENERAL | **EMOTIONAL_QUERY** / support |
| aurora é minha maior criação | EMOTIONAL/pride (ok) | **EMOTIONAL_QUERY** / pride |
| juventus joga que horas? | SPORT | **SPORT** (preservado) |
