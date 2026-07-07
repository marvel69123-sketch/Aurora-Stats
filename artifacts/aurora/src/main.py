import os
import uvicorn
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from src.routers import fixtures, leagues, teams, players, standings, live, analyze

app = FastAPI(
    title="Aurora",
    description="Live football match statistics powered by API-Football",
    version="1.0.0",
    docs_url="/aurora/docs",
    redoc_url="/aurora/redoc",
    openapi_url="/aurora/openapi.json",
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


@app.get("/aurora/healthz", tags=["Health"])
async def health():
    return {"status": "ok", "service": "Aurora"}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("src.main:app", host="0.0.0.0", port=port, reload=True)
