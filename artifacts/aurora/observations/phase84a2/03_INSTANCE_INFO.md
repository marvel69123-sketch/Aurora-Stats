# Phase 8.4-A.2 — Instance info

## 2) Existe mais de uma instância ativa?

### Artefatos Replit (config)

| Artifact | ID / path | Role |
|----------|-----------|------|
| API | `3B4_FFSkEVBkAeYMFRJ2e` (`artifacts/api-server/.replit-artifact`) | FastAPI via `artifacts/aurora/start.sh` :8080 |
| Web | `artifacts/web` | SPA static (`dist/public`), path `/` |

`.replit`: `deploymentTarget = "autoscale"` — Autoscale **pode** ter N réplicas; não há API neste ambiente para listar.

### Hosts observados

| Host | Estado |
|------|--------|
| `aurora-stats.marvel69123-sketch.replit.app` | responde (500) — **único candidato “vivo”** |
| 3+ aliases `*.replit.app` | 404 “This app isn't live yet” |

**Resposta:** há **vários hostnames**, mas só um parece apontar para um deployment; os outros estão mortos. Número de réplicas Autoscale por trás do host vivo: **desconhecido**.

## 3) Backend atual contém `match_opinion_renderer.py`?

| Escopo | Contém? |
|--------|---------|
| `origin/main` @ `872bd19` | **SIM** |
| Processo Autoscale vivo | **NÃO VERIFICADO** (sem shell no Replit / sem healthz) |

`start.sh` usa **1 worker** uvicorn — reduz flakiness multi-process, mas não garante que o pull incluiu mop se o deploy estiver stale ou quebrado.

## 5) O frontend aponta para qual deployment?

`useChat.ts`:

```ts
const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");
fetch(`${BASE}/aurora/copilot`, …)
```

→ **same-origin** relativo ao host que serve a SPA.  
Não há segundo base URL hardcoded. FE e API devem ser o **mesmo** deployment Autoscale (`/` + `/aurora/*`).

Se o FE carregar de um preview/dev e a API de outro, isso seria config de ambiente — **não** evidenciado nesta sonda.
