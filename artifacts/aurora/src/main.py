"""
Aurora — Live football match statistics API
FastAPI application factory + lifespan.
"""
from __future__ import annotations

import logging
import os
import traceback
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.routers import (
    analyze,
    brain_router,
    copilot_router,
    copilot_unified_router,
    decision_router,
    evolution_router,
    fixtures,
    intelligence_router,
    knowledge_router,
    leagues,
    learning_router,
    live,
    memory_router,
    players,
    report,
    score,
    standings,
    teams,
)

logger = logging.getLogger("aurora")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)


def _run_startup() -> None:
    """Initialize brain cache + SQLite DBs. Never raise to the ASGI lifespan."""
    from src.brain import get_config as _init_brain
    from src.chat_db import init_chat_db as _init_chat
    from src.knowledge_db import init_db as _init_db
    from src.knowledge_db import init_knowledge_items as _init_knowledge_items
    from src.learning_db import init_learning_db as _init_learning
    from src.memory_db import init_memory_db as _init_memory

    steps = [
        ("brain", _init_brain),
        ("knowledge_db", _init_db),
        ("knowledge_items", _init_knowledge_items),
        ("learning_db", _init_learning),
        ("memory_db", _init_memory),
        ("chat_db", _init_chat),
    ]
    for name, fn in steps:
        try:
            fn()
            logger.info("startup ok: %s", name)
        except Exception:
            logger.exception("startup FAILED: %s (continuing)", name)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Aurora lifespan startup begin cwd=%s", os.getcwd())
    _run_startup()
    logger.info("Aurora lifespan startup complete")
    yield
    logger.info("Aurora lifespan shutdown")


app = FastAPI(
    title="Aurora",
    description="Live football match statistics powered by API-Football",
    version="1.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(live.router, prefix="/aurora", tags=["Live"])
app.include_router(fixtures.router, prefix="/aurora/fixtures", tags=["Fixtures"])
app.include_router(leagues.router, prefix="/aurora/leagues", tags=["Leagues"])
app.include_router(teams.router, prefix="/aurora/teams", tags=["Teams"])
app.include_router(players.router, prefix="/aurora/players", tags=["Players"])
app.include_router(standings.router, prefix="/aurora/standings", tags=["Standings"])
app.include_router(analyze.router, prefix="/aurora", tags=["Analyze"])
app.include_router(report.router, prefix="/aurora", tags=["Report"])
app.include_router(score.router, prefix="/aurora", tags=["Score"])
app.include_router(brain_router.router, prefix="/aurora", tags=["Brain"])
app.include_router(learning_router.router, prefix="/aurora", tags=["Learning"])
app.include_router(memory_router.router, prefix="/aurora", tags=["Memory"])
app.include_router(decision_router.router, prefix="/aurora", tags=["Decision"])
app.include_router(evolution_router.router, prefix="/aurora", tags=["Evolution"])
app.include_router(knowledge_router.router, prefix="/aurora", tags=["Knowledge"])
app.include_router(intelligence_router.router, prefix="/aurora", tags=["Intelligence"])
app.include_router(copilot_router.router, prefix="/aurora", tags=["Copilot"])
app.include_router(copilot_unified_router.router, prefix="/aurora", tags=["Copilot"])


@app.exception_handler(Exception)
async def _unhandled_exception(request: Request, exc: Exception):
    """Log full traceback for 500s (Replit deploy diagnosis)."""
    if isinstance(exc, (StarletteHTTPException, RequestValidationError)):
        raise exc
    tb = traceback.format_exc()
    logger.error("Unhandled error on %s %s\n%s", request.method, request.url.path, tb)
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "detail": str(exc),
            "path": request.url.path,
            "hint": "Check Aurora logs for full traceback",
        },
    )


@app.get("/aurora/healthz", tags=["Health"])
@app.get("/aurora", tags=["Health"], include_in_schema=False)
@app.get("/aurora/", tags=["Health"], include_in_schema=False)
async def health():
    """
    Liveness probe used by Replit Autoscale.

    Must stay dependency-light: never call API-Football here.
    """
    brain_meta: dict = {"brain_version": "unknown"}
    try:
        from src.brain import get_brain_meta

        brain_meta = get_brain_meta()
    except Exception as exc:
        logger.warning("healthz: brain meta unavailable: %s", exc)
        brain_meta = {"brain_version": "unavailable", "error": str(exc)}

    return {
        "status": "ok",
        "service": "Aurora",
        "version": "1.1.0",
        "brain": brain_meta,
    }


@app.get("/aurora/docs", include_in_schema=False)
async def aurora_docs_redirect():
    return RedirectResponse(url="/docs")


@app.get("/aurora/redoc", include_in_schema=False)
async def aurora_redoc_redirect():
    return RedirectResponse(url="/redoc")


@app.get("/aurora/openapi.json", include_in_schema=False)
async def aurora_openapi_redirect():
    return RedirectResponse(url="/openapi.json")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("src.main:app", host="0.0.0.0", port=port, reload=True)
