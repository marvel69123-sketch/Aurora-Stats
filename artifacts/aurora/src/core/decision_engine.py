"""
Decision Engine — central brain of Aurora.

Orchestrates all seven specialist engines in the order defined by
the Aurora methodology:

  1. Collect data          → data dict from analyze_fixture() (caller's job)
  2. Load brain knowledge  → get_config() from src.brain
  3. Methodology Engine    → three-layer Poisson model
  4. Learning Engine       → historical context from prediction_history
  5. Confidence Engine     → data-richness scoring
  6. Bankroll Engine       → risk classification + stake sizing
  7. Market Engine         → rank all seven markets
  8. Report Engine         → explanations + text report
  9. Return DecisionResult → single unified output for any endpoint

Both /aurora/score and /aurora/report call this engine.
The result contains everything both endpoints need — no business logic
remains in the routers.

Public API
----------
  run(data) -> DecisionResult
"""
from __future__ import annotations

from dataclasses import dataclass

from src.brain import BrainConfig, get_brain_meta, get_config
from src.core import (
    bankroll_engine,
    confidence_engine,
    learning_engine,
    market_engine,
    methodology_engine,
    report_engine,
)
from src.core.bankroll_engine import BankrollResult
from src.core.confidence_engine import ConfidenceResult
from src.core.learning_engine import LearningContext
from src.core.market_engine import MarketResult
from src.core.methodology_engine import MethodologyResult


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class DecisionResult:
    """
    Unified output of the Decision Engine.

    Every endpoint derives its response from this object — no business logic
    is allowed in routers beyond HTTP serialization.
    """

    # ── Match identity ─────────────────────────────────────────────────────
    fixture_id: int
    date:       str | None
    hn:         str          # home team name
    an:         str          # away team name
    league:     str | None
    status:     str
    minute:     int | None

    # ── Engine outputs ─────────────────────────────────────────────────────
    methodology: MethodologyResult
    confidence:  ConfidenceResult
    learning:    LearningContext
    bankroll:    BankrollResult
    markets:     MarketResult

    # ── Report layer ───────────────────────────────────────────────────────
    summary:     str          # one-line summary for /score
    report_text: str          # full plain-text report for /report

    # ── Brain metadata ─────────────────────────────────────────────────────
    brain_meta:  dict

    # ── Convenience accessors ──────────────────────────────────────────────

    @property
    def overall_confidence(self) -> float:
        return round(self.confidence.overall, 1)

    @property
    def best_market_label(self) -> str:
        return self.markets.best.label

    @property
    def risk_level(self) -> str:
        return self.markets.best.risk

    @property
    def recommended_market_labels(self) -> list[str]:
        return [ms.label for ms in self.markets.recommended]


# ---------------------------------------------------------------------------
# Engine entry point
# ---------------------------------------------------------------------------


def run(data: dict) -> DecisionResult:
    """
    Run all Aurora engines in sequence and return a DecisionResult.

    Parameters
    ----------
    data : dict returned by analyze_fixture()
            Must contain: fixture, teams, score, statistics, events,
            standings, league, lineups.
    """

    # ── Step 2: Load Aurora Brain knowledge ──────────────────────────────────
    cfg: BrainConfig = get_config()

    # ── Extract shared identifiers ───────────────────────────────────────────
    fx     = data["fixture"]
    teams  = data["teams"]
    league = data.get("league", {}).get("name")
    hn     = teams["home"]["name"]
    an     = teams["away"]["name"]

    # ── Step 3: Methodology Engine ───────────────────────────────────────────
    meth = methodology_engine.run(data, cfg)

    # ── Step 4: Learning Engine ──────────────────────────────────────────────
    learning = learning_engine.run(league=league)

    # ── Step 5: Confidence Engine ────────────────────────────────────────────
    conf = confidence_engine.run(meth, cfg)

    # ── Step 6: Bankroll Engine ──────────────────────────────────────────────
    # (needs market result first for risk classification; bankroll uses market risks)
    # Build markets first so bankroll can rank by market probability
    mkts = market_engine.run(hn, an, data, meth, conf, cfg)
    bank = bankroll_engine.run(mkts, learning, cfg)

    # ── Step 7: Markets already ranked above ──────────────────────────────────
    # (market_engine.run already ranked and identified best / recommended)

    # ── Step 8: Report Engine ────────────────────────────────────────────────
    summary     = report_engine.build_summary(hn, an, meth, mkts)
    report_text = report_engine.build_text(data, hn, an, mkts)

    # ── Step 9: Return DecisionResult ────────────────────────────────────────
    return DecisionResult(
        fixture_id=fx["id"],
        date=fx.get("date"),
        hn=hn,
        an=an,
        league=league,
        status=fx["status"]["long"],
        minute=meth.minute if meth.is_live and meth.minute else None,
        methodology=meth,
        confidence=conf,
        learning=learning,
        bankroll=bank,
        markets=mkts,
        summary=summary,
        report_text=report_text,
        brain_meta=get_brain_meta(),
    )
