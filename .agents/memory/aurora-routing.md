---
name: Aurora service routing
description: FastAPI on :8080, proxied at /aurora/*; paths not rewritten; knowledge DB is SQLite at artifacts/aurora/aurora.db with 40 seed items.
---

## Service config

- FastAPI app: `artifacts/aurora/src/main.py`, runs on `PORT=8080`
- Workflow: `artifacts/api-server: Aurora` runs `uvicorn main:app --host 0.0.0.0 --port 8080 --reload` from `artifacts/aurora/`
- Proxied at `/aurora/*` — paths are NOT rewritten, so FastAPI must handle full `/aurora/...` prefixes (done via `prefix=` on routers)
- Docs: `/aurora/docs` (Swagger), `/aurora/redoc`

## Knowledge DB

- SQLite at `artifacts/aurora/aurora.db`
- 40 seed items — verified with `count_knowledge_items()`
- Searches return results for BTTS (5), corners (6), kelly (1)
- Seeded in `src/knowledge_db.py` → `_seed_knowledge_items()`

## Error handling

- 404s from `analyze.py._find_fixture` are caught by the outer `try/except` in `copilot()` in `copilot_unified_router.py`
- The handler checks `isinstance(exc, HTTPException) and exc.status_code == 404` and returns a friendly Portuguese message with the team names and troubleshooting tips
