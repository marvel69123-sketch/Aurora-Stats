# Phase 8.4-A.3 — Startup logs

## Replit deploy logs

| Source | Access |
|--------|--------|
| Build `b3b68a8f-2c2f-4c22-b037-fcb4dcd3cd8e` | **NOT available** from Cursor (no Replit shell / Deployments API) |
| Autoscale container stdout/stderr | **NOT available** |

Operator must open: Replit → Deployments → latest → **Build / Runtime logs**.

## Local production-like startup (captured)

Command: `uvicorn main:app --host 127.0.0.1 --port 18081 --workers 1`  
CWD: `artifacts/aurora`  
Commit identity: `backend_commit=872bd19`

```text
Aurora lifespan startup begin
AURORA_BRAIN loaded — version=1.0.0
startup ok: brain
startup ok: knowledge_db
startup ok: knowledge_items
startup ok: learning_db
startup ok: memory_db
startup ok: chat_db
Aurora lifespan startup complete
Application startup complete.
Uvicorn running on http://127.0.0.1:18081
GET /aurora/healthz → 200
{"status":"ok",...,"backend_commit":"872bd19"}
```

Logs: `_uvicorn_err.txt` / `_uvicorn_out.txt` in this folder.

## Production edge observation

| Probe | Result |
|-------|--------|
| WebFetch `…/aurora/healthz` | HTTP **500** (no FastAPI JSON body) |
| Local httpx/curl to same host | **SSL UNEXPECTED_EOF** |
| Other `*.replit.app` aliases | 404 “isn't live yet” |

→ consistent with **upstream process down / crash-loop / edge failure**, not with the FastAPI handler returning its own 500 payload.
