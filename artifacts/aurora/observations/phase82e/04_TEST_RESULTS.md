# Fase 8.2-E — Test Results

Comando: `uv run python scripts/phase82e_opinion_routing_smoke.py`  
Log: `observations/phase82e/smoke_stdout.txt`

## Opinion (pipeline completo)

| Mensagem | HIE topic | nat | opinion_time | fallback | recent |
|----------|-----------|-----|--------------|----------|--------|
| o que você achou do jogo do fluminense ontem? | opinion | team_opinion | **True** | None | True |
| como foi a partida do flamengo? | opinion | team_opinion | **True** | None | True |
| o flamengo jogou bem? | opinion | team_opinion | **True** | None | True |
| o que você achou da atuação do flamengo? | opinion | team_opinion | **True** | None | True |
| como você viu o último jogo do santos? | opinion | team_opinion | **True** | None | True |

**Nunca** `calendar_authority` nesses casos.

## Agenda (intacta)

| Mensagem | Resultado |
|----------|-----------|
| quando é o próximo jogo? | não-opinion |
| tem jogo hoje? | calendar_today / não-opinion |
| tem jogo do fluminense hoje? | calendar_or_fixture / team_calendar |
| proximo jogo do palmeiras | calendar / team_calendar |

## Regressões

| Suite | Resultado |
|-------|-----------|
| 8.2-A repair | PASS |
| 8.2-C short memory | PASS |
| 7.9-E misroutes | **11/11** |

**PASS — 8.2-E opinion routing (full pipeline)**
