# Phase 8.4-A.3 — Root cause

## Primary conclusion

**`/aurora/healthz` 500 em produção não é reproduzível no código atual.**  
Localmente o backend sobe e healthz retorna 200 com `backend_commit=872bd19`.

O sintoma de produção (500 sem body JSON + SSL EOF + aliases “isn't live yet”) aponta para:

**Autoscale / edge com processo API ausente ou em crash-loop — logs só no Replit.**

## Checklist das hipóteses

| # | Hipótese | Veredito |
|---|----------|----------|
| 1 | Logs deploy | Inacessíveis daqui — obrigatório no Replit UI |
| 2 | Traceback startup | Não capturado em prod; local startup **OK** |
| 3 | Falha de import | Local **OK** (incl. mop + router) |
| 4 | Falha de migration | N/A — SQLite `CREATE IF NOT EXISTS`, fail-open no lifespan |
| 5 | Env vars | healthz **não** exige API keys; local 200 sem keys |
| 6 | Erro de banco | Local init OK; falhas são engolidas no startup |
| 7 | Startup hooks | Completam com sucesso localmente |
| 8 | `match_opinion_renderer` | **NÃO** — lazy import só em opinion path; healthz não toca |
| 9 | Chilean aliases | **NÃO causa healthz 500** — `ohiggins` está em `team_aliases.py`; `verify-layout.sh` checava arquivo errado (`copilot_engine.py`) e quebrava só o **deploy prep** local |
| 10 | Worker crash loop | **Provável no Replit** (edge 500 + TLS EOF); `start.sh` já usa `--workers 1` |

## O que NÃO é a causa

- Patch 8.3-A / `match_opinion_renderer.py`
- Ausência de `API_FOOTBALL_KEY` no healthz
- Lógica do handler `health()` (try/except + fail-open)

## Causa raiz operacional (melhor evidência)

Deployment Autoscale **não está servindo** um uvicorn saudável no host
`aurora-stats.marvel69123-sketch.replit.app`, apesar do SoT Git conter código que healthz’a OK.
