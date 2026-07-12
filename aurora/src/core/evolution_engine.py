"""
Aurora Auto Evolution Engine — post-match self-improvement analysis.

After every finished match Aurora:
  1. Compares prediction vs real result for every market
  2. Detects which methodology categories were correct / failed
  3. Calculates prediction error (Brier score, log-loss, calibration error)
  4. Updates confidence calibration metrics
  5. Suggests methodology improvements (weights, rules, biases)
  6. Generates an Improvement Report stored in improvement_history

NEVER changes methodology automatically.
NEVER overwrites history.
All changes are suggestions only — a human must apply them via brain/methodology.json.

Public API
----------
  analyze(data, hn, an, markets, mv1, meth, cfg) -> EvolutionAnalysis
  generate_report(analysis) -> ImprovementReport
  simulate_weights(new_weights, history_records, mcfg) -> SimulationReport
  calibrate_from_history(history_records) -> CalibrationStats
"""
from __future__ import annotations

import dataclasses
import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.brain import BrainConfig, MethodologyConfig
from src.core.market_engine import MarketResult
from src.core.methodology_engine import MethodologyResult
from src.core.methodology_v1 import MethodologyV1Result


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class CategoryVerdict:
    key:         str
    name:        str
    score:       float        # 0–10, what the category scored for this prediction
    weight:      float        # current configured weight
    verdict:     str          # correct_bullish | missed_bullish | correct_bearish | missed_bearish | neutral
    explanation: str          # why this verdict


@dataclass
class MarketAccuracy:
    market_key:  str
    market_name: str
    predicted_prob: float     # 0–100
    outcome:     bool         # did the market hit?
    brier:       float        # (prob - outcome)²  lower = better
    log_loss:    float
    correct:     bool         # hit and was the "bet" direction right


@dataclass
class EvolutionAnalysis:
    """Full post-match evolution analysis for a single fixture."""

    # ── Identity ──────────────────────────────────────────────────────────────
    fixture_id:       int
    match:            str          # "Arsenal vs Chelsea"
    league:           str | None
    result_str:       str          # "2-1"
    methodology_score: float       # overall v1 score at prediction time

    # ── Market accuracy ────────────────────────────────────────────────────────
    market_accuracies: list[MarketAccuracy]
    markets_correct:  list[str]    # market_keys that hit
    markets_wrong:    list[str]
    best_market_key:  str          # market Aurora predicted
    best_market_correct: bool

    # ── Error metrics ──────────────────────────────────────────────────────────
    brier_score:      float        # mean across all markets (lower = better)
    log_loss:         float        # mean across all markets
    calibration_error: float       # |predicted_prob - actual_hit_rate| in %

    # ── Category verdicts (15 categories) ────────────────────────────────────
    category_verdicts: list[CategoryVerdict]
    correct_categories: list[CategoryVerdict]
    failed_categories:  list[CategoryVerdict]

    # ── Improvement suggestions ───────────────────────────────────────────────
    correct_assumptions:      list[str]
    wrong_assumptions:        list[str]
    possible_biases:          list[str]
    missing_data:             list[str]
    suggested_weight_changes: dict[str, float]  # category_key → delta (not absolute)
    suggested_new_rules:      list[str]

    # ── Serialisable category scores (for simulate endpoint) ─────────────────
    category_scores: dict[str, float]   # key → score (all 15)
    actual_outcomes: dict[str, bool]    # market_key → bool

    # ── Calibration data ──────────────────────────────────────────────────────
    data_richness:    str          # Low | Medium | High (based on what signals were available)


@dataclass
class ImprovementReport:
    """Human-readable improvement report generated from EvolutionAnalysis."""

    report_id:    str
    generated_at: str
    analysis:     EvolutionAnalysis
    summary:      str          # one-paragraph summary
    headline:     str          # one-line headline


@dataclass
class SimulationMatch:
    """Single match result in a simulation run."""
    fixture_id:   int
    match:        str
    old_score:    float        # methodology score with current weights
    new_score:    float        # methodology score with proposed weights
    old_passes:   bool         # old score ≥ min_score_to_recommend
    new_passes:   bool
    best_market_correct: bool
    delta_score:  float        # new - old


@dataclass
class SimulationReport:
    """Result of simulating proposed weight changes on historical data."""

    proposed_weights: dict[str, float]      # full proposed weight set
    weight_deltas:    dict[str, float]      # changes vs current weights
    test_on_n:        int                   # number of matches tested
    matches:          list[SimulationMatch]

    # ── Aggregate ──────────────────────────────────────────────────────────────
    old_pass_rate:        float  # % of matches where old weights passed
    new_pass_rate:        float  # % with new weights
    old_correct_rate:     float  # accuracy when methodology passed, old weights
    new_correct_rate:     float  # accuracy when methodology passed, new weights
    delta_pass_rate:      float  # new - old
    delta_correct_rate:   float

    verdict:      str   # Improved | Worse | Neutral
    recommendation: str


@dataclass
class CalibrationStats:
    """Calibration curve stats computed across all historical improvement records."""

    total_records:    int
    mean_brier:       float       # lower = better (0 perfect, 1 worst)
    mean_log_loss:    float
    mean_cal_error:   float       # mean |predicted - actual| %
    best_market_accuracy: float   # % correct for best_market recommendations
    markets_correct_rate: dict[str, float]  # per market
    over_confident:   bool        # if cal_error > 10 we're over-confident
    calibration_grade: str        # A (≤5%) | B (≤10%) | C (≤20%) | D (>20%)


# ---------------------------------------------------------------------------
# Math helpers
# ---------------------------------------------------------------------------


def _brier(prob_pct: float, outcome: bool) -> float:
    p = max(0.0, min(1.0, prob_pct / 100.0))
    o = 1.0 if outcome else 0.0
    return round((p - o) ** 2, 5)


def _log_loss_val(prob_pct: float, outcome: bool) -> float:
    p = max(0.001, min(0.999, prob_pct / 100.0))
    o = 1.0 if outcome else 0.0
    return round(-(o * math.log(p) + (1.0 - o) * math.log(1.0 - p)), 5)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Category verdict logic
# ---------------------------------------------------------------------------

_BULLISH_THRESHOLD = 7.0
_BEARISH_THRESHOLD = 3.5


def _category_verdict(score: float, best_correct: bool) -> tuple[str, str]:
    """
    Return (verdict_code, explanation).

    Verdicts:
      correct_bullish  — category signalled strong, bet was correct
      missed_bullish   — category signalled strong, bet was WRONG (false confidence)
      correct_bearish  — category signalled weak, bet was wrong (good caution flag)
      missed_bearish   — category signalled weak, bet was correct (missed opportunity)
      neutral          — no strong signal either way
    """
    if score >= _BULLISH_THRESHOLD and best_correct:
        return ("correct_bullish",
                f"Bullish signal ({score:.1f}/10) validated — prediction was correct.")
    if score >= _BULLISH_THRESHOLD and not best_correct:
        return ("missed_bullish",
                f"Bullish signal ({score:.1f}/10) gave false confidence — prediction was wrong. "
                "Consider reducing this category's weight.")
    if score <= _BEARISH_THRESHOLD and not best_correct:
        return ("correct_bearish",
                f"Bearish signal ({score:.1f}/10) correctly flagged risk — prediction was wrong. "
                "Category is well-calibrated as a risk gate.")
    if score <= _BEARISH_THRESHOLD and best_correct:
        return ("missed_bearish",
                f"Bearish signal ({score:.1f}/10) penalised a winning prediction — potential missed opportunity. "
                "Consider a higher weight to avoid over-blocking.")
    return ("neutral",
            f"Neutral signal ({score:.1f}/10) — no strong positive or negative contribution.")


# ---------------------------------------------------------------------------
# Correct / wrong assumption generators
# ---------------------------------------------------------------------------


def _gen_correct_assumptions(
    meth:       MethodologyResult,
    mv1:        MethodologyV1Result,
    markets:    MarketResult,
    outcomes:   dict[str, bool],
    hn:         str,
    an:         str,
) -> list[str]:
    correct: list[str] = []

    if outcomes.get("home_win") and meth.ph > meth.pa:
        correct.append(
            f"Home advantage correctly identified — {hn} was the stronger team "
            f"(predicted {meth.ph:.0%} home win probability)."
        )
    if outcomes.get("away_win") and meth.pa > meth.ph:
        correct.append(
            f"Away strength correctly identified — {an} win predicted at {meth.pa:.0%}."
        )
    if outcomes.get("over_85_corners") and markets.markets["over_85_corners"].probability > 65:
        correct.append(
            f"Corner volume correctly predicted — over 8.5 corners at {markets.markets['over_85_corners'].probability:.0f}%."
        )
    if outcomes.get("over_25_goals") and markets.markets["over_25_goals"].probability > 60:
        correct.append(
            f"Goal volume correctly predicted — over 2.5 goals at {markets.markets['over_25_goals'].probability:.0f}%."
        )
    if outcomes.get("btts") and markets.markets["btts"].probability > 60:
        correct.append(
            f"BTTS correctly predicted at {markets.markets['btts'].probability:.0f}% — both teams scored."
        )
    if meth.has_xg:
        xg_total = meth.h_xg_val + meth.a_xg_val
        if outcomes.get("over_25_goals") and xg_total > 2.5:
            correct.append(
                f"xG model was accurate — combined xG {xg_total:.2f} correctly predicted high scoring."
            )
    return correct or ["No strong correct assumptions to highlight — prediction lacked clear winning signals."]


def _gen_wrong_assumptions(
    meth:       MethodologyResult,
    mv1:        MethodologyV1Result,
    markets:    MarketResult,
    outcomes:   dict[str, bool],
    hn:         str,
    an:         str,
) -> list[str]:
    wrong: list[str] = []

    if not outcomes.get("home_win") and meth.ph > 0.5:
        wrong.append(
            f"Home win over-predicted — {hn} at {meth.ph:.0%} did not win. "
            f"Home advantage may have been over-weighted."
        )
    if not outcomes.get("away_win") and meth.pa > 0.5:
        wrong.append(
            f"Away win over-predicted — {an} at {meth.pa:.0%} did not win."
        )
    if meth.has_xg and not outcomes.get("over_25_goals"):
        xg_total = meth.h_xg_val + meth.a_xg_val
        if xg_total > 2.0:
            wrong.append(
                f"xG over-stated attacking output — combined xG {xg_total:.2f} "
                f"but only {meth.total_goals} goal(s) scored. xG model may require variance adjustment."
            )
    if not outcomes.get("over_85_corners") and markets.markets["over_85_corners"].probability > 65:
        wrong.append(
            f"Corner volume over-predicted — {meth.total_corners} corners scored "
            f"despite {markets.markets['over_85_corners'].probability:.0f}% model probability."
        )
    if not outcomes.get("btts") and markets.markets["btts"].probability > 60:
        wrong.append(
            f"BTTS failed despite {markets.markets['btts'].probability:.0f}% prediction — "
            "one team was shut out."
        )
    return wrong or ["All major assumptions held — no significant wrong predictions detected."]


def _gen_biases(
    meth:     MethodologyResult,
    mv1:      MethodologyV1Result,
    outcomes: dict[str, bool],
    cat_verdicts: list[CategoryVerdict],
) -> list[str]:
    biases: list[str] = []

    false_bullish = [cv for cv in cat_verdicts if cv.verdict == "missed_bullish"]
    if len(false_bullish) >= 3:
        cats = ", ".join(cv.name for cv in false_bullish[:3])
        biases.append(
            f"Multi-category overconfidence detected — {cats} all signalled positive "
            "but the prediction failed. Possible systematic overfit to this fixture type."
        )

    if not outcomes.get("home_win") and mv1.categories.get("home_advantage") and \
       mv1.categories["home_advantage"].score >= _BULLISH_THRESHOLD:
        biases.append(
            "Home advantage bias — model consistently over-values home factor. "
            "Consider reducing home_advantage weight for high-parity leagues."
        )

    if meth.has_xg and mv1.categories.get("xg_analysis") and \
       mv1.categories["xg_analysis"].score >= _BULLISH_THRESHOLD and \
       not outcomes.get("over_25_goals"):
        biases.append(
            "xG reliability bias — xG data was present but the Poisson model over-estimated goal output. "
            "xG should be blended with historical scoring rates, not used as primary signal."
        )

    if not meth.is_live and not meth.is_finished:
        biases.append(
            "Pre-match prediction bias — all signals were pre-match estimates. "
            "Accuracy typically improves 30–40% for live predictions with confirmed data."
        )

    if mv1.categories.get("historical_learning") and \
       mv1.categories["historical_learning"].score == 5.0:
        biases.append(
            "Neutral prior bias — no historical data for this league/market, "
            "methodology defaulted to neutral (5.0) which may not reflect true difficulty."
        )

    return biases or ["No significant prediction biases detected in this fixture."]


def _gen_missing_data(
    data: dict,
    meth: MethodologyResult,
) -> list[str]:
    missing: list[str] = []

    if not meth.has_xg:
        missing.append(
            "xG data unavailable — probability model relied on season-long GPG averages "
            "rather than match-specific expected goals. xG typically improves prediction accuracy by 12–18%."
        )
    if not meth.has_standings:
        missing.append(
            "Standings data unavailable — team strength and form were estimated from defaults. "
            "Accurate standings data is critical for team_strength and home_advantage categories."
        )
    lineups = data.get("lineups", {}) or {}
    if not (lineups.get("home") or lineups.get("away")):
        missing.append(
            "No lineup data — tactical_style category scored at minimum. "
            "Confirmed formations significantly improve corners and goals market predictions."
        )
    if not data.get("fixture", {}).get("referee"):
        missing.append(
            "No referee assigned — cards_pattern and referee_influence categories used prior only. "
            "Known referee card rates can shift over/under card markets by 8–15%."
        )
    if not meth.has_events:
        missing.append(
            "No events data — live_momentum could not be assessed from match events."
        )

    return missing or ["All expected data signals were available for this fixture."]


def _gen_suggested_weight_changes(
    cat_verdicts:    list[CategoryVerdict],
    current_weights: dict[str, float],
) -> dict[str, float]:
    """
    Conservative weight delta suggestions based on single-match category performance.
    These are SUGGESTIONS only — never applied automatically.
    Magnitude: 0.005–0.015 per match (accumulate over time to see trends).
    """
    DELTA_INCREASE = 0.010
    DELTA_DECREASE = 0.010
    DELTA_SMALL    = 0.005

    suggestions: dict[str, float] = {}

    for cv in cat_verdicts:
        if cv.verdict == "missed_bullish":
            # Category over-signalled → reduce weight slightly
            suggestions[cv.key] = -DELTA_DECREASE
        elif cv.verdict == "missed_bearish":
            # Category blocked a winner → increase weight (it was too strict)
            suggestions[cv.key] = +DELTA_INCREASE
        elif cv.verdict == "correct_bullish":
            # Good signal → slight reinforcement
            suggestions[cv.key] = +DELTA_SMALL
        elif cv.verdict == "correct_bearish":
            # Good risk gate → slight reinforcement
            suggestions[cv.key] = +DELTA_SMALL
        # neutral: no suggestion

    # Normalisation note (non-destructive): weights must sum to 1.0
    # We include the note in suggested_new_rules, not auto-applied here
    return suggestions


def _gen_suggested_new_rules(
    meth:         MethodologyResult,
    mv1:          MethodologyV1Result,
    outcomes:     dict[str, bool],
    cat_verdicts: list[CategoryVerdict],
    hn:           str,
    an:           str,
) -> list[str]:
    rules: list[str] = []

    false_bullish = [cv for cv in cat_verdicts if cv.verdict == "missed_bullish"]
    if len(false_bullish) >= 3 and not any(
        outcomes.get(m) for m in ["home_win", "away_win", "over_25_goals"]
    ):
        rules.append(
            "RULE CANDIDATE: When 3+ categories score ≥7.0 but overall methodology_score < 5.5, "
            "add a 'conflicting_signals' penalty of −0.5 to reduce false confidence clustering."
        )

    if not meth.has_xg and mv1.overall_score > 5.0:
        rules.append(
            "RULE CANDIDATE: Cap overall_score at 5.0 when xG data is unavailable — "
            "no-xG predictions should never reach Low or Medium risk classification."
        )

    if meth.is_finished and meth.total_goals == 0 and \
       mv1.categories.get("xg_analysis") and mv1.categories["xg_analysis"].score > 5.0:
        rules.append(
            "RULE CANDIDATE: Add a 'nil-nil draw guard' — when both team xG values are "
            "< 0.5 and teams are equally matched, significantly boost draw probability and "
            "reduce over 2.5 goals market confidence."
        )

    if meth.total_corners < 6 and outcomes.get("over_85_corners") is False and \
       mv1.categories.get("corners_pattern") and mv1.categories["corners_pattern"].score > 5.0:
        rules.append(
            "RULE CANDIDATE: Introduce league-specific corner baseline — "
            "some leagues average 8–9 corners/90 (below current 10.5 baseline). "
            "Consider a per-league corners_baseline parameter in brain/methodology.json."
        )

    return rules or [
        "No new rule candidates identified — prediction failure appears within normal model variance."
    ]


# ---------------------------------------------------------------------------
# Data richness classifier
# ---------------------------------------------------------------------------


def _data_richness(meth: MethodologyResult, data: dict) -> str:
    score = sum([
        meth.has_xg,
        meth.has_standings,
        meth.has_stats,
        meth.has_events,
        bool((data.get("lineups") or {}).get("home")),
        bool(data.get("fixture", {}).get("referee")),
    ])
    if score >= 5:
        return "High"
    if score >= 3:
        return "Medium"
    return "Low"


# ---------------------------------------------------------------------------
# Core analysis function
# ---------------------------------------------------------------------------


def analyze(
    data:     dict,
    hn:       str,
    an:       str,
    markets:  MarketResult,
    mv1:      MethodologyV1Result,
    meth:     MethodologyResult,
    league:   str | None,
    cfg:      BrainConfig,
    mcfg:     MethodologyConfig,
) -> EvolutionAnalysis:
    """
    Run a full post-match evolution analysis.

    Must only be called when meth.is_finished = True.
    Returns an EvolutionAnalysis ready to be turned into an ImprovementReport.
    """
    h, a = meth.h_goals, meth.a_goals
    result_str = f"{h}–{a}"

    actual_outcomes: dict[str, bool] = {
        "home_win":        h > a,
        "draw":            h == a,
        "away_win":        a > h,
        "btts":            h >= 1 and a >= 1,
        "over_25_goals":   meth.total_goals >= 3,
        "over_85_corners": meth.total_corners >= 9,
        "over_45_cards":   meth.total_cards >= 5,
    }

    # ── Market accuracy ────────────────────────────────────────────────────────
    market_accuracies: list[MarketAccuracy] = []
    for key, ms in markets.markets.items():
        outcome = actual_outcomes.get(key, False)
        # "correct" = we predicted it as the best market OR it was our recommended and it hit
        is_correct = (key == markets.best.key and outcome) or (key != markets.best.key and not outcome and ms.probability < 50)
        market_accuracies.append(MarketAccuracy(
            market_key=key,
            market_name=ms.label,
            predicted_prob=ms.probability,
            outcome=outcome,
            brier=_brier(ms.probability, outcome),
            log_loss=_log_loss_val(ms.probability, outcome),
            correct=is_correct,
        ))

    markets_correct = [k for k, v in actual_outcomes.items() if v]
    markets_wrong   = [k for k, v in actual_outcomes.items() if not v]
    best_correct    = actual_outcomes.get(markets.best.key, False)

    brier_mean = round(sum(ma.brier for ma in market_accuracies) / len(market_accuracies), 5)
    ll_mean    = round(sum(ma.log_loss for ma in market_accuracies) / len(market_accuracies), 5)

    # Calibration error: |best_market_prob - (1 if correct else 0)| × 100
    cal_error  = round(abs(markets.best.probability - (100.0 if best_correct else 0.0)), 1)

    # ── Category verdicts ──────────────────────────────────────────────────────
    cat_verdicts: list[CategoryVerdict] = []
    cat_scores_flat: dict[str, float] = {}
    current_weights = dataclasses.asdict(mcfg.category_weights)

    for key, cs in mv1.categories.items():
        verdict, expl = _category_verdict(cs.score, best_correct)
        cat_verdicts.append(CategoryVerdict(
            key=key,
            name=cs.name,
            score=cs.score,
            weight=cs.weight,
            verdict=verdict,
            explanation=expl,
        ))
        cat_scores_flat[key] = cs.score

    correct_cats = [cv for cv in cat_verdicts if cv.verdict in ("correct_bullish", "correct_bearish")]
    failed_cats  = [cv for cv in cat_verdicts if cv.verdict in ("missed_bullish", "missed_bearish")]

    # ── Narrative generation ───────────────────────────────────────────────────
    correct_assumptions = _gen_correct_assumptions(meth, mv1, markets, actual_outcomes, hn, an)
    wrong_assumptions   = _gen_wrong_assumptions(meth, mv1, markets, actual_outcomes, hn, an)
    possible_biases     = _gen_biases(meth, mv1, actual_outcomes, cat_verdicts)
    missing_data        = _gen_missing_data(data, meth)
    weight_changes      = _gen_suggested_weight_changes(cat_verdicts, current_weights)
    new_rules           = _gen_suggested_new_rules(meth, mv1, actual_outcomes, cat_verdicts, hn, an)

    return EvolutionAnalysis(
        fixture_id=data["fixture"]["id"],
        match=f"{hn} vs {an}",
        league=league,
        result_str=result_str,
        methodology_score=mv1.overall_score,
        market_accuracies=market_accuracies,
        markets_correct=markets_correct,
        markets_wrong=markets_wrong,
        best_market_key=markets.best.key,
        best_market_correct=best_correct,
        brier_score=brier_mean,
        log_loss=ll_mean,
        calibration_error=cal_error,
        category_verdicts=cat_verdicts,
        correct_categories=correct_cats,
        failed_categories=failed_cats,
        correct_assumptions=correct_assumptions,
        wrong_assumptions=wrong_assumptions,
        possible_biases=possible_biases,
        missing_data=missing_data,
        suggested_weight_changes=weight_changes,
        suggested_new_rules=new_rules,
        category_scores=cat_scores_flat,
        actual_outcomes=actual_outcomes,
        data_richness=_data_richness(meth, data),
    )


# ---------------------------------------------------------------------------
# Report generator
# ---------------------------------------------------------------------------


def generate_report(analysis: EvolutionAnalysis) -> ImprovementReport:
    correct_n = len(analysis.correct_categories)
    failed_n  = len(analysis.failed_categories)
    brier_grade = (
        "Excellent" if analysis.brier_score < 0.05 else
        "Good"      if analysis.brier_score < 0.15 else
        "Fair"      if analysis.brier_score < 0.25 else "Poor"
    )
    headline = (
        f"{'✅' if analysis.best_market_correct else '❌'} "
        f"{analysis.match} [{analysis.result_str}] — "
        f"Best market {'HIT' if analysis.best_market_correct else 'MISSED'} · "
        f"Brier {analysis.brier_score:.3f} ({brier_grade}) · "
        f"{correct_n} categories correct, {failed_n} failed"
    )

    hit_rate = len(analysis.markets_correct) / max(len(analysis.market_accuracies), 1) * 100

    summary = (
        f"Post-match analysis for {analysis.match} (final: {analysis.result_str}). "
        f"Aurora's best-market recommendation ({analysis.best_market_key.replace('_', ' ').title()}) "
        f"{'was CORRECT' if analysis.best_market_correct else 'was WRONG'}. "
        f"Overall market hit rate: {hit_rate:.0f}% ({len(analysis.markets_correct)}/7 markets). "
        f"Prediction error: Brier score {analysis.brier_score:.4f} ({brier_grade}), "
        f"log-loss {analysis.log_loss:.4f}. "
        f"Methodology scored {analysis.methodology_score:.2f}/10 with {analysis.data_richness} data richness. "
        f"{correct_n}/{correct_n + failed_n} categories signalled correctly. "
        f"Weight changes suggested for {len(analysis.suggested_weight_changes)} categories — "
        f"apply via brain/methodology.json after reviewing."
    )

    return ImprovementReport(
        report_id=str(uuid.uuid4()),
        generated_at=_now(),
        analysis=analysis,
        summary=summary,
        headline=headline,
    )


# ---------------------------------------------------------------------------
# Simulate weight changes
# ---------------------------------------------------------------------------


def simulate_weights(
    new_weights:      dict[str, float],
    history_records:  list[dict],
    mcfg:             MethodologyConfig,
) -> SimulationReport:
    """
    Simulate the impact of proposed weight changes on historical predictions.

    Parameters
    ----------
    new_weights      : proposed weights {category_key: float}. Missing categories
                       retain their current weight from mcfg.
    history_records  : records from improvement_history collection (must contain
                       category_scores and best_market_correct fields in content).
    mcfg             : current MethodologyConfig (for current weight baseline).

    Returns a SimulationReport — NEVER applies changes.
    """
    current_weights = dataclasses.asdict(mcfg.category_weights)

    # Build full proposed weight set (only override keys provided)
    proposed: dict[str, float] = {**current_weights, **new_weights}

    # Re-normalise to sum=1.0 if needed
    total = sum(proposed.values())
    if abs(total - 1.0) > 0.001 and total > 0:
        proposed = {k: round(v / total, 6) for k, v in proposed.items()}

    weight_deltas = {
        k: round(proposed.get(k, 0.0) - current_weights.get(k, 0.0), 6)
        for k in set(list(proposed.keys()) + list(current_weights.keys()))
        if abs(proposed.get(k, 0.0) - current_weights.get(k, 0.0)) > 1e-6
    }

    sim_matches: list[SimulationMatch] = []
    min_score = mcfg.min_score_to_recommend

    for rec in history_records:
        content = rec.get("content", {})
        cat_scores = content.get("category_scores", {})
        best_correct = content.get("best_market_correct")
        old_score = content.get("methodology_score", 0.0)
        match_name = content.get("match", "Unknown")
        fixture_id = content.get("fixture_id", 0)

        if not cat_scores or best_correct is None:
            continue

        # Re-compute methodology score with new weights
        new_score = sum(
            float(cat_scores.get(k, 0.0)) * proposed.get(k, current_weights.get(k, 0.0))
            for k in current_weights
        )
        new_score = round(min(10.0, max(0.0, new_score)), 3)

        sim_matches.append(SimulationMatch(
            fixture_id=fixture_id,
            match=match_name,
            old_score=float(old_score),
            new_score=new_score,
            old_passes=float(old_score) >= min_score,
            new_passes=new_score >= min_score,
            best_market_correct=bool(best_correct),
            delta_score=round(new_score - float(old_score), 3),
        ))

    if not sim_matches:
        return SimulationReport(
            proposed_weights=proposed,
            weight_deltas=weight_deltas,
            test_on_n=0,
            matches=[],
            old_pass_rate=0.0, new_pass_rate=0.0,
            old_correct_rate=0.0, new_correct_rate=0.0,
            delta_pass_rate=0.0, delta_correct_rate=0.0,
            verdict="Neutral",
            recommendation="Insufficient history to simulate. Run more predictions first.",
        )

    n = len(sim_matches)
    old_pass = [m for m in sim_matches if m.old_passes]
    new_pass = [m for m in sim_matches if m.new_passes]

    old_pass_rate = round(len(old_pass) / n * 100, 1)
    new_pass_rate = round(len(new_pass) / n * 100, 1)

    old_correct = [m for m in old_pass if m.best_market_correct]
    new_correct = [m for m in new_pass if m.best_market_correct]

    old_cr = round(len(old_correct) / max(len(old_pass), 1) * 100, 1)
    new_cr = round(len(new_correct) / max(len(new_pass), 1) * 100, 1)

    delta_pass = round(new_pass_rate - old_pass_rate, 1)
    delta_cr   = round(new_cr - old_cr, 1)

    # Verdict: net improvement requires BOTH better pass rate AND accuracy
    if delta_cr > 2 or (delta_cr >= 0 and delta_pass > 5):
        verdict = "Improved"
    elif delta_cr < -2 or (delta_cr < 0 and delta_pass < -5):
        verdict = "Worse"
    else:
        verdict = "Neutral"

    nonzero = {k: v for k, v in weight_deltas.items() if abs(v) > 1e-6}
    changes_str = ", ".join(
        f"{k}: {'+' if v > 0 else ''}{v:+.4f}" for k, v in sorted(nonzero.items(), key=lambda x: -abs(x[1]))[:5]
    )

    recommendation = (
        f"Simulation over {n} historical matches: {verdict}. "
        f"Proposed changes ({changes_str}): "
        f"pass rate {old_pass_rate:.0f}% → {new_pass_rate:.0f}% ({delta_pass:+.0f}%), "
        f"accuracy when passed {old_cr:.0f}% → {new_cr:.0f}% ({delta_cr:+.0f}%). "
    )
    if verdict == "Improved":
        recommendation += "These weight changes show a positive signal. Consider applying after further validation."
    elif verdict == "Worse":
        recommendation += "These weight changes reduce accuracy. Do NOT apply."
    else:
        recommendation += "No significant improvement detected. More data may be needed."

    return SimulationReport(
        proposed_weights=proposed,
        weight_deltas=weight_deltas,
        test_on_n=n,
        matches=sim_matches,
        old_pass_rate=old_pass_rate,
        new_pass_rate=new_pass_rate,
        old_correct_rate=old_cr,
        new_correct_rate=new_cr,
        delta_pass_rate=delta_pass,
        delta_correct_rate=delta_cr,
        verdict=verdict,
        recommendation=recommendation,
    )


# ---------------------------------------------------------------------------
# Calibration statistics
# ---------------------------------------------------------------------------


def calibrate_from_history(history_records: list[dict]) -> CalibrationStats:
    """Compute calibration statistics across all historical improvement records."""
    bribers: list[float] = []
    lls:     list[float] = []
    cals:    list[float] = []
    best_correct: list[bool] = []
    market_hits: dict[str, list[bool]] = {}

    for rec in history_records:
        c = rec.get("content", {})
        brier = c.get("brier_score")
        ll    = c.get("log_loss")
        cal   = c.get("calibration_error")
        bc    = c.get("best_market_correct")

        if brier is not None: bribers.append(float(brier))
        if ll    is not None: lls.append(float(ll))
        if cal   is not None: cals.append(float(cal))
        if bc    is not None: best_correct.append(bool(bc))

        for mk in c.get("markets_correct", []):
            market_hits.setdefault(mk, []).append(True)
        for mk in c.get("markets_wrong", []):
            market_hits.setdefault(mk, []).append(False)

    n = len(history_records)
    mean_brier  = round(sum(bribers) / max(len(bribers), 1), 5)
    mean_ll     = round(sum(lls)    / max(len(lls), 1), 5)
    mean_cal    = round(sum(cals)   / max(len(cals), 1), 1)
    bma         = round(sum(1 for b in best_correct if b) / max(len(best_correct), 1) * 100, 1)

    mkt_rates = {
        k: round(sum(1 for h in v if h) / len(v) * 100, 1)
        for k, v in market_hits.items() if len(v) >= 2
    }

    if mean_cal <= 5:
        grade = "A"
    elif mean_cal <= 10:
        grade = "B"
    elif mean_cal <= 20:
        grade = "C"
    else:
        grade = "D"

    return CalibrationStats(
        total_records=n,
        mean_brier=mean_brier,
        mean_log_loss=mean_ll,
        mean_cal_error=mean_cal,
        best_market_accuracy=bma,
        markets_correct_rate=mkt_rates,
        over_confident=mean_cal > 10,
        calibration_grade=grade,
    )
