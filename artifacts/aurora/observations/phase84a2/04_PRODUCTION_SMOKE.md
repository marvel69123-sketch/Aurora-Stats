# Phase 8.4-A.2 — Production smoke

## Teste pedido

```text
"o que você achou do jogo do fluminense ontem?"
Esperado: response_type=match_opinion
Nunca: team_summary / panorama / agenda
```

## Resultado

| Etapa | Status |
|-------|--------|
| `GET …/aurora/healthz` | **FAIL** (500 / SSL) |
| `POST …/aurora/copilot` com a pergunta | **NÃO EXECUTADO** (pré-requisito healthz) |
| Prova `response_type=match_opinion` em prod | **NÃO OBTIDA** |

## Smoke de código (SoT = remote, não runtime)

No tree que inclui `93a9abc` (ainda em `origin/main`):

```text
[OK] type=match_opinion opinion_time=True
PASS — 8.3-A opinion renderer
```

Isso valida o **código no Git**, não o processo Autoscale.

## Como validar após healthz voltar

1. `GET /aurora/healthz` → anotar `backend_commit` (esperado `872bd19` / `93a9abc`+)
2. `POST /aurora/copilot` `{ "message": "o que você achou do jogo do fluminense ontem?", "debug": true }`
3. Checar entities / DEBUG: `response_type=match_opinion`, sem “panorama”
