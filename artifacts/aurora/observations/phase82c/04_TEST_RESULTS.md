# Fase 8.2-C — Test Results

Comando: `uv run python scripts/phase82c_short_memory_smoke.py`  
Log: `observations/phase82c/smoke_stdout.txt`

| Teste | Resultado |
|-------|-----------|
| T1 último jogo → achou dele? | **PASS** → `…último jogo do Flamengo?` · MasterIntent `SPORT_QUERY` |
| T2 flamengo → e o palmeiras? → e dele? | **PASS** → Palmeiras (não Flamengo) |
| T3 não foi isso (repair) | **PASS** · Fluminense preservado · sem Entendi |

Regressão 8.2-A: `phase82a_repair_smoke.py` → **PASS**

```
[T1] 'o que você achou dele?' → 'o que você achou do último jogo do Flamengo?' master=SPORT_QUERY
[T2] 'e o dele?' → 'o que você achou do último jogo do Palmeiras?'
[T3] repair ok …
PASS — all 8.2-C short memory checks
```
