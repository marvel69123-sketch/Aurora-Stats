"""
/aurora/report — Human-readable plain-text match report.

All section builders, formatting helpers, and analysis logic have moved to
src/core/report_engine.py. This router is a thin HTTP wrapper:

  1. Fetch raw fixture data via analyze_fixture()
  2. Delegate to decision_engine.run() to get the full DecisionResult
  3. Return decision.report_text — pre-built by the Report Engine

No formatting logic lives here.
"""
from fastapi import APIRouter, Query
from fastapi.responses import PlainTextResponse

from src.core.decision_engine import run as _decide
from src.routers.analyze import analyze_fixture

router = APIRouter()


@router.get("/report", response_class=PlainTextResponse)
async def match_report(
    home: str = Query(..., description="Home team name (full or partial)"),
    away: str = Query(..., description="Away team name (full or partial)"),
):
    """
    Return a human-readable match report for the given home/away teams.

    Internally runs the full Aurora Decision Engine pipeline and returns the
    pre-assembled text report from the Report Engine.

    Sections: Match header, Score, Statistics, Cards, Events, Lineups,
    Standings, Tactical summary, Momentum, Betting insights, Aurora's pick.
    """
    data     = await analyze_fixture(home=home, away=away)
    decision = _decide(data)
    return decision.report_text
