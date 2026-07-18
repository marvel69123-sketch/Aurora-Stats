# Phase 8.4-A.3 — Traceback

## Production

**No application traceback obtained.**

Evidence the 500 is **not** the app’s JSON exception handler:

- Handler in `src/main.py` would return:
  `{"status":"error","detail":…,"path":"/aurora/healthz","hint":…}`
- WebFetch/edge returns bare **500** with no such body
- TLS EOF from this machine → connection often dies before ASGI responds

## Local

| Path | Result | Traceback |
|------|--------|-----------|
| `TestClient` `/aurora/healthz` | 200 | none |
| `uvicorn` workers=1 `/aurora/healthz` | 200 | none |
| Import `match_opinion_renderer` | OK | none |
| Import `natural_conversation` / unified router | OK | none |
| healthz without `API_FOOTBALL_KEY` / `OPENAI_API_KEY` | 200 | none |

## Startup contract

`_run_startup()` catches per-step failures and **continues** — DB/brain init failures log `startup FAILED: … (continuing)` and must not abort lifespan.
