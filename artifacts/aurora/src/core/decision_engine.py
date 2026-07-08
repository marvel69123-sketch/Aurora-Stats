"""
Decision Engine — central brain of Aurora.

Orchestrates all engines in the order defined by the Aurora methodology:

  1. Collect data          → data dict from analyze_fixture() (caller's job)
  2. Load brain knowledge  → get_config() + get_methodology_config()
  3. Methodology Engine    → three-layer Poisson model (raw probabilities)
  4. Learning Engine       → historical context from prediction_history
  5. Confidence Engine     → data-richness scoring
  6. Market Engine         → rank and explain all seven markets
  7. Methodology v1        → 15-category weighted scoring + market gating
  8. Bankroll Engine       → risk classification + stake sizing
  9. Report Engine         → text report + summary string
 10. Return DecisionResult → single unified output for any endpoint

Both /aurora/score and /aurora/report call this engine.
The result contains everything both endpoints need — no business logic
remains in the routers.

Public API
----------
  run(data) -> DecisionResult
"""
from __future__ import annotations

from dataclasses import dataclass

from src.brain import BrainConfig, MethodologyConfig, get_brain_meta, get_config, get_methodology_config
from src.core import (
    bankroll_engine,
    confidence_engine,
    learning_engine,
    market_engine,
    methodology_engine,
    methodology_v1,
    report_engine,
)
from src.core.bankroll_engine import BankrollResult
from src.core.confidence_engine import ConfidenceResult
from src.core.learning_engine import LearningContext
from src.core.market_engine import MarketResult
from src.core.methodology_engine import MethodologyResult
from src.core.methodology_v1 import MethodologyV1Result


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
    methodology:    MethodologyResult
    confidence:     ConfidenceResult
    learning:       LearningContext
    markets:        MarketResult
    methodology_v1: MethodologyV1Result   # ← Aurora Methodology v1
    bankroll:       BankrollResult

    # ── Report layer ───────────────────────────────────────────────────────
    summary:     str
    report_text: str

    # ── Brain metadata ─────────────────────────────────────────────────────
    brain_meta:  dict

    # ── Convenience accessors ──────────────────────────────────────────────

    @property
    def overall_confidence(self) -> float:
        return round(self.confidence.overall, 1)

    @property
    def best_market_label(self) -> str:
        """Methodology v1 recommended market if one passed, else probability-best."""
        return self.methodology_v1.recommended_market or self.markets.best.label

    @property
    def risk_level(self) -> str:
        return self.methodology_v1.risk

    @property
    def recommended_market_labels(self) -> list[str]:
        """Markets recommended by Methodology v1 (passes all gates)."""
        rec = self.methodology_v1.recommended_market
        return [rec] if rec else []


# ---------------------------------------------------------------------------
# Engine entry point
# ---------------------------------------------------------------------------


def run(data: dict) -> DecisionResult:
    """
    Run the full Aurora decision pipeline and return a DecisionResult.

    Parameters
    ----------
    data : dict returned by analyze_fixture()
            Must contain: fixture, teams, score, statistics, events,
            standings, league, lineups.
    """

    # ── Step 2: Load Aurora Brain knowledge ──────────────────────────────────
    cfg:  BrainConfig      = get_config()
    mcfg: MethodologyConfig = get_methodology_config()

    # ── Extract shared identifiers ───────────────────────────────────────────
    fx     = data["fixture"]
    teams  = data["teams"]
    league = data.get("league", {}).get("name")
    hn     = teams["home"]["name"]
    an     = teams["away"]["name"]

    # ── Step 3: Methodology Engine (Poisson math) ────────────────────────────
    meth = methodology_engine.run(data, cfg)

    # ── Step 4: Learning Engine ──────────────────────────────────────────────
    learning = learning_engine.run(league=league)

    # ── Step 5: Confidence Engine ────────────────────────────────────────────
    conf = confidence_engine.run(meth, cfg)

    # ── Step 6: Market Engine ────────────────────────────────────────────────
    mkts = market_engine.run(hn, an, data, meth, conf, cfg)

    # ── Step 7: Aurora Methodology v1 ────────────────────────────────────────
    mv1 = methodology_v1.run(
        data=data, hn=hn, an=an,
        meth=meth, conf=conf, market=mkts,
        learning=learning, mcfg=mcfg, brain_cfg=cfg,
    )

    # ── Step 8: Bankroll Engine ──────────────────────────────────────────────
    bank = bankroll_engine.run(mkts, learning, cfg)

    # ── Step 9: Report Engine ────────────────────────────────────────────────
    summary     = report_engine.build_summary(hn, an, meth, mkts)
    report_text = report_engine.build_text(data, hn, an, mkts)

    # ── Step 10: Return DecisionResult ───────────────────────────────────────
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
        markets=mkts,
        methodology_v1=mv1,
        bankroll=bank,
        summary=summary,
        report_text=report_text,
        brain_meta=get_brain_meta(),
    )
