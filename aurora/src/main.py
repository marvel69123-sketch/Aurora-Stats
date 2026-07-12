import os
import uvicorn
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from src.routers import fixtures, leagues, teams, players, standings, live, analyze, report, score, brain_router, learning_router, memory_router, decision_router, evolution_router, knowledge_router, intelligence_router
from src.routers import copilot_router, copilot_unified_router
from src.brain import get_config as _init_brain
from src.knowledge_db import init_db as _init_db, init_knowledge_items as _init_knowledge_items
from src.learning_db import init_learning_db as _init_learning
from src.memory_db import init_memory_db as _init_memory
from src.chat_db import init_chat_db as _init_chat

app = FastAPI(
    title="Aurora",
    description="Live football match statistics powered by API-Football",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
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


@app.on_event("startup")
async def _startup():
    """Pre-load file-brain cache and initialise all SQLite databases on startup."""
    _init_brain()
    _init_db()
    _init_knowledge_items()
    _init_learning()
    _init_memory()
    _init_chat()


@app.get("/aurora/healthz", tags=["Health"])
async def health():
    from src.brain import get_brain_meta
    return {"status": "ok", "service": "Aurora", "brain": get_brain_meta()}


# Backward-compat redirects — keep old /aurora/docs paths working
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
