"""
Bankroll Engine — risk classification and stake-sizing recommendations.

Applies brain/bankroll.md rules to the market result:
  - Low risk  → full flat stake (FLAT_STAKE_PCT = 2%)
  - Medium risk → 60% of flat stake
  - High risk → 0% (do not bet)

Also applies learning-history modifier: if historical accuracy for a market
is below 40%, escalate risk one level upward.

Public API
----------
  run(market_result, learning, cfg) -> BankrollResult
"""
from __future__ import annotations

from dataclasses import dataclass, field

from src.brain import BrainConfig
from src.core.learning_engine import LearningContext
from src.core.market_engine import MarketResult, MarketScore

# Brain bankroll defaults (from brain/bankroll.md) ─ read from brain if available
_FLAT_STAKE_PCT   = 2.0   # % of bankroll per bet at full stake
_MEDIUM_MULTIPLIER = 0.6  # reduce stake for Medium-risk markets
_HIGH_MULTIPLIER   = 0.0  # never bet High-risk markets


@dataclass
class MarketRecommendation:
    """Bankroll recommendation for a single market."""
    key:          str
    label:        str
    risk:         str          # final risk after learning adjustment
    stake_pct:    float        # recommended stake as % of bankroll
    rationale:    str


@dataclass
class BankrollResult:
    """Output of the Bankroll Engine."""
    recommendations:   list[MarketRecommendation]      # all 7 markets
    top_recommendation: MarketRecommendation | None    # best actionable market
    overall_stake_pct:  float                          # total % at risk across recommendations
    learning_adjusted:  list[str]                      # markets whose risk was escalated


def _escalate_risk(risk: str) -> str:
    """Move risk one level higher: Low → Medium, Medium → High."""
    return {"Low": "Medium", "Medium": "High"}.get(risk, risk)


def _stake_for_risk(risk: str) -> float:
    if risk == "Low":
        return _FLAT_STAKE_PCT
    if risk == "Medium":
        return round(_FLAT_STAKE_PCT * _MEDIUM_MULTIPLIER, 2)
    return _HIGH_MULTIPLIER


def run(
    market_result: MarketResult,
    learning: LearningContext,
    cfg: BrainConfig,
) -> BankrollResult:
    """
    Compute stake recommendations for every market.

    Parameters
    ----------
    market_result : MarketResult from market_engine.run()
    learning      : LearningContext from learning_engine.run()
    cfg           : BrainConfig (betting_gates, bankroll rules)
    """
    recommendations: list[MarketRecommendation] = []
    learning_adjusted: list[str] = []

    for ms in market_result.ranked:
        risk = ms.risk

        # Learning adjustment: poor track record on this market → escalate risk
        acc = learning.accuracy_for(ms.key)
        if acc is not None and acc <= 40.0 and risk != "High":
            risk = _escalate_risk(risk)
            learning_adjusted.append(ms.key)

        stake_pct = _stake_for_risk(risk)

        if risk == "High":
            rationale = "High risk — stake 0%. Do not bet."
        elif risk == "Medium":
            rationale = f"Medium risk — reduced stake {stake_pct}% of bankroll."
        else:
            rationale = f"Low risk — full stake {stake_pct}% of bankroll."

        if acc is not None and ms.key in learning_adjusted:
            rationale += f" (risk escalated: historical accuracy {acc:.1f}% ≤ 40%)."

        recommendations.append(MarketRecommendation(
            key=ms.key,
            label=ms.label,
            risk=risk,
            stake_pct=stake_pct,
            rationale=rationale,
        ))

    # Top recommendation = highest-probability market that's still actionable ──
    top: MarketRecommendation | None = None
    for rec in recommendations:
        if rec.stake_pct > 0:
            top = rec
            break  # recommendations are in probability-rank order

    overall_stake_pct = round(sum(r.stake_pct for r in recommendations), 2)

    return BankrollResult(
        recommendations=recommendations,
        top_recommendation=top,
        overall_stake_pct=overall_stake_pct,
        learning_adjusted=learning_adjusted,
    )
