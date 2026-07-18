# Fase 8.2-A — Test Results

## Smoke principal

Comando: `uv run python scripts/phase82a_repair_smoke.py`  
Log: `observations/phase82a/smoke_stdout.txt`

| Check | Resultado |
|-------|-----------|
| Sinais repair detectados | PASS |
| Falsos positivos (oi / flamengo / que bom) | PASS |
| `que bom` → NRE ack | PASS |
| `não foi isso` + memória Fluminense | PASS — opinião/partida ontem |
| `pensa um pouco` | PASS — sem Entendi |
| `agora entendeu?` | PASS — sem Entendi |
| Fluxo aprovação 8 turnos | **8/8 OK** |
| Template `Entendi. Posso te ajudar` | **0 ocorrências** no path repair |

Trecho (obrigatório):

```
[OK] 'não foi isso' → …Acho que interpretei errado.
     Você queria minha opinião sobre a partida de ontem do Flumin…
[OK] 'pensa um pouco' → …opinião sobre a partida do Flumin…
[OK] 'agora entendeu?' → …opinião sobre o jogo do Fluminense…
PASS — all 8.2-A repair checks
```

## Regressão 7.9-E

`uv run python scripts/phase79e_misroute_smoke.py`

| Métrica | Resultado |
|---------|-----------|
| Probes + regress roteamento | **11/11 = 100%** |

Intent spot-check: LIVE_MATCH / UTILITY_QUERY / EMOTIONAL_QUERY — OK  
`reply_general()` ainda produz Entendi quando chamado diretamente — OK (comportamento preservado fora do repair).
