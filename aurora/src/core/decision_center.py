"""
Aurora Decision Center — comprehensive multi-market evaluation engine.

Evaluates every available market before making a recommendation.
Markets compared (23 total across 10 types):

  1.  Match Winner       — home_win, draw, away_win
  2.  Draw No Bet        — dnb_home, dnb_away
  3.  Double Chance      — dc_1x (Home/Draw), dc_x2 (Draw/Away), dc_12 (Home/Away)
  4.  Asian Handicap     — ah_home (-0.5), ah_away (+0.5)
  5.  Goals Over/Under   — over 1.5 / 2.5 / 3.5 / 4.5 / under 2.5
  6.  BTTS               — btts_yes, btts_no
  7.  Corners            — over 8.5, over 9.5
  8.  Cards              — over 3.5, over 4.5
  9.  Player Goals       — anytime scorer (most likely attacker)
  10. Player Assists     — anytime assist (most likely creator)

Each market is evaluated on 8 dimensions:
  probability, confidence, live_confidence, expected_value,
  methodology_score, historical_accuracy, bankroll_suitability, risk

Markets below min_confidence are automatically rejected.
Returns all evaluated markets sorted best→worst, plus Top 5 opportunities.

Public API
----------
  run(data, hn, an, decision, mv1, learning, cfg) -> DecisionCenterResult
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from src.brain import BrainConfig
from src.core.confidence_engine import ConfidenceResult
from src.core.learning_engine import LearningContext
from src.core.methodology_engine import MethodologyResult
from src.core.methodology_v1 import MethodologyV1Result


# ---------------------------------------------------------------------------
# Market type → relevant methodology v1 category weights
# ---------------------------------------------------------------------------

_CAT_WEIGHTS: dict[str, dict[str, float]] = {
    "match_winner":   {"team_strength": 0.30, "current_form": 0.25, "xg_analysis": 0.20,
                       "live_momentum": 0.15, "home_advantage": 0.10},
    "draw_no_bet":    {"team_strength": 0.30, "current_form": 0.25, "xg_analysis": 0.20,
                       "live_momentum": 0.15, "home_advantage": 0.10},
    "double_chance":  {"team_strength": 0.35, "current_form": 0.30,
                       "xg_analysis": 0.20, "live_momentum": 0.15},
    "asian_handicap": {"team_strength": 0.35, "current_form": 0.25,
                       "xg_analysis": 0.20, "live_momentum": 0.20},
    "goals":          {"xg_analysis": 0.45, "live_momentum": 0.30, "team_strength": 0.25},
    "btts":           {"xg_analysis": 0.40, "team_strength": 0.30, "current_form": 0.30},
    "corners":        {"corners_pattern": 0.55, "tactical_style": 0.25, "live_momentum": 0.20},
    "cards":          {"cards_pattern": 0.50, "referee_influence": 0.25,
                       "tactical_style": 0.15, "live_momentum": 0.10},
    "player_goals":   {"xg_analysis": 0.50, "live_momentum": 0.30, "match_context": 0.20},
    "player_assists": {"xg_analysis": 0.45, "live_momentum": 0.30, "tactical_style": 0.25},
}

# Break-even probability per market type (accounts for typical bookmaker margin).
# EV = (probability - break_even) / break_even × 100
_BREAK_EVEN: dict[str, float] = {
    "home_win":        53.0,
    "draw":            55.0,
    "away_win":        53.0,
    "dnb_home":        55.0,
    "dnb_away":        55.0,
    "dc_1x":           73.0,
    "dc_x2":           73.0,
    "dc_12":           71.0,
    "ah_home":         52.0,
    "ah_away":         52.0,
    "over_15_goals":   53.0,
    "over_25_goals":   54.0,
    "over_35_goals":   56.0,
    "over_45_goals":   59.0,
    "under_25_goals":  54.0,
    "btts_yes":        54.0,
    "btts_no":         54.0,
    "over_85_corners": 57.0,
    "over_95_corners": 59.0,
    "over_35_cards":   55.0,
    "over_45_cards":   57.0,
    "player_to_score": 62.0,
    "player_to_assist": 65.0,
}


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class MarketEvaluation:
    """Full 8-dimension evaluation of a single market."""

    market_id:            str          # e.g. "dnb_home"
    market_name:          str          # e.g. "Arsenal DNB"
    market_type:          str          # e.g. "draw_no_bet"

    probability:          float        # 0–100
    confidence:           float        # 0–10 (data-quality score)
    live_confidence:      float        # 0–10 (boosted by live signal richness)
    expected_value:       float        # % edge vs break-even (positive = value)
    methodology_score:    float        # 0–10 weighted from v1 relevant categories
    historical_accuracy:  float | None # 0–100 from learning engine, None if no data
    bankroll_suitability: str          # Low | Medium | High (risk classification)
    risk:                 str          # Low | Medium | High

    composite_score:      float        # 0–100 final ranking score
    explanation:          str
    actionable:           bool
    rank:                 int          # 1 = best actionable; 0 = rejected
    rejected_reason:      str | None


@dataclass
class DecisionCenterResult:
    hn:             str
    an:             str
    fixture_id:     int

    all_markets:    list[MarketEvaluation]  # all 23 evaluated, best→worst
    actionable:     list[MarketEvaluation]  # passed all gates
    rejected:       list[MarketEvaluation]  # failed one or more gates
    top_5:          list[MarketEvaluation]  # top 5 actionable (or best available)
    best:           MarketEvaluation | None

    total_evaluated:  int
    total_actionable: int
    total_rejected:   int


# ---------------------------------------------------------------------------
# Math helpers
# ---------------------------------------------------------------------------


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return round(min(hi, max(lo, v)), 2)


def _poisson(lam: float, k: int) -> float:
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def _poisson_over(lam: float, threshold: float) -> float:
    cutoff = int(threshold + 0.5)
    return max(0.0, 1.0 - sum(_poisson(lam, k) for k in range(cutoff)))


def _poisson_btts(h_lam: float, a_lam: float) -> float:
    p_h_no_goal = _poisson(h_lam, 0)
    p_a_no_goal = _poisson(a_lam, 0)
    return max(0.0, 1.0 - p_h_no_goal - p_a_no_goal + p_h_no_goal * p_a_no_goal)


def _live_confidence(base: float, meth: MethodologyResult) -> float:
    """Boost confidence when live signal data is rich."""
    if not (meth.is_live or meth.is_finished):
        return round(base, 1)
    boost = (
        (0.5 if meth.has_stats else 0.0)
        + (0.5 if meth.has_xg else 0.0)
        + (0.3 if meth.has_events else 0.0)
        + (0.2 if meth.minute >= 60 else 0.0)
    )
    return round(min(10.0, base + boost), 1)


def _methodology_score_for(
    market_type: str,
    mv1: MethodologyV1Result,
) -> float:
    """Compute a market-specific methodology score from the relevant v1 categories."""
    cat_weights = _CAT_WEIGHTS.get(market_type, {})
    if not cat_weights:
        return round(mv1.overall_score, 2)

    total_w = sum(cat_weights.values())
    score   = 0.0
    for cat_key, weight in cat_weights.items():
        cs = mv1.categories.get(cat_key)
        cat_score = cs.score if cs else mv1.overall_score
        score += cat_score * (weight / total_w)
    return round(score, 2)


def _expected_value(probability: float, market_id: str) -> float:
    """EV = (probability - break_even) / break_even × 100 (percentage)."""
    be = _BREAK_EVEN.get(market_id, 55.0)
    if be <= 0:
        return 0.0
    return round((probability - be) / be * 100.0, 1)


def _composite(
    prob:     float,
    conf:     float,
    ev:       float,
    meth_sc:  float,
    hist_acc: float | None,
) -> float:
    """
    Weighted composite score 0–100 for ranking.
      probability  → 25%
      confidence   → 20%
      expected_val → 20%   (normalized: ev=-25→0, ev=0→50, ev=+25→100)
      methodology  → 20%
      history      → 15%
    """
    p = _clamp(prob,     0.0, 100.0)
    c = _clamp(conf * 10, 0.0, 100.0)
    e = _clamp(ev * 2.0 + 50.0, 0.0, 100.0)
    m = _clamp(meth_sc * 10.0,  0.0, 100.0)
    h = hist_acc if hist_acc is not None else 50.0

    return round(p * 0.25 + c * 0.20 + e * 0.20 + m * 0.20 + h * 0.15, 2)


# ---------------------------------------------------------------------------
# Per-market probability computers
# ---------------------------------------------------------------------------


def _compute_probabilities(
    data:  dict,
    hn:    str,
    an:    str,
    meth:  MethodologyResult,
    conf:  ConfidenceResult,
    cfg:   BrainConfig,
) -> dict[str, tuple[float, float, str]]:
    """
    Return {market_id: (probability_pct, confidence_0_10, explanation)}.
    """
    ph, pd, pa = meth.ph, meth.pd, meth.pa

    # Goals lambda — prefer xG, fall back to standings GPG
    h_lam = meth.h_xg_val if meth.has_xg else meth.h_gpg
    a_lam = meth.a_xg_val if meth.has_xg else meth.a_gpg
    total_lam = max(h_lam + a_lam, 0.5)

    # For live/finished matches, adjust lambda based on remaining time
    if meth.is_live and meth.minute > 0 and meth.minute < 90:
        remaining_frac = max(0.0, (90 - meth.minute) / 90.0)
        goals_remaining_lam = total_lam * remaining_frac
        scored_so_far = meth.total_goals
    else:
        goals_remaining_lam = total_lam
        scored_so_far = 0

    c_overall = conf.overall
    c_stats   = conf.stats_conf
    c_corner  = conf.corner_conf
    c_card    = conf.card_conf

    probs: dict[str, tuple[float, float, str]] = {}

    # ── 1. Match Winner ──────────────────────────────────────────────────────
    probs["home_win"]  = (round(ph * 100, 1), c_overall, f"{hn} probability from three-layer Poisson model.")
    probs["draw"]      = (round(pd * 100, 1), round(c_overall * 0.85, 1), "Draw probability — reduced confidence (draws hardest to predict).")
    probs["away_win"]  = (round(pa * 100, 1), c_overall, f"{an} probability from three-layer Poisson model.")

    # ── 2. Draw No Bet ───────────────────────────────────────────────────────
    denom = ph + pa if (ph + pa) > 0 else 1.0
    dnb_h = ph / denom
    dnb_a = pa / denom
    probs["dnb_home"] = (round(dnb_h * 100, 1), round(c_overall * 0.95, 1),
                         f"{hn} to win outright — draw excluded from market.")
    probs["dnb_away"] = (round(dnb_a * 100, 1), round(c_overall * 0.95, 1),
                         f"{an} to win outright — draw excluded from market.")

    # ── 3. Double Chance ────────────────────────────────────────────────────
    probs["dc_1x"] = (round((ph + pd) * 100, 1), round(c_overall * 0.90, 1),
                      f"{hn} or Draw — only {an} win loses.")
    probs["dc_x2"] = (round((pa + pd) * 100, 1), round(c_overall * 0.90, 1),
                      f"Draw or {an} — only {hn} win loses.")
    probs["dc_12"] = (round((ph + pa) * 100, 1), round(c_overall * 0.92, 1),
                      f"{hn} or {an} win — draw loses. Draw probability: {pd:.0%}.")

    # ── 4. Asian Handicap ────────────────────────────────────────────────────
    # AH -0.5 Home = P(home wins) | AH +0.5 Away = P(away wins or draws)
    probs["ah_home"] = (round(ph * 100, 1), round(c_overall * 0.92, 1),
                        f"{hn} AH -0.5: must win outright by any margin.")
    probs["ah_away"] = (round((pa + pd) * 100, 1), round(c_overall * 0.92, 1),
                        f"{an} AH +0.5: away win or draw both return a profit.")

    # ── 5. Goals Over/Under ─────────────────────────────────────────────────
    if meth.is_finished:
        o15 = 1.0 if meth.total_goals >= 2 else 0.0
        o25 = 1.0 if meth.total_goals >= 3 else 0.0
        o35 = 1.0 if meth.total_goals >= 4 else 0.0
        o45 = 1.0 if meth.total_goals >= 5 else 0.0
    elif meth.is_live and meth.minute > 0:
        # Combine already-scored goals with Poisson expectation for remaining time
        o15_r = _poisson_over(goals_remaining_lam, max(0, 1.5 - scored_so_far))
        o25_r = _poisson_over(goals_remaining_lam, max(0, 2.5 - scored_so_far))
        o35_r = _poisson_over(goals_remaining_lam, max(0, 3.5 - scored_so_far))
        o45_r = _poisson_over(goals_remaining_lam, max(0, 4.5 - scored_so_far))
        o15 = o15_r if scored_so_far < 2 else 1.0
        o25 = o25_r if scored_so_far < 3 else 1.0
        o35 = o35_r if scored_so_far < 4 else 1.0
        o45 = o45_r if scored_so_far < 5 else 1.0
    else:
        o15 = _poisson_over(total_lam, 1.5)
        o25 = meth.o25_pct / 100.0
        o35 = _poisson_over(total_lam, 3.5)
        o45 = _poisson_over(total_lam, 4.5)

    xg_note = f" Combined xG {meth.h_xg_val + meth.a_xg_val:.2f}." if meth.has_xg else ""
    probs["over_15_goals"]  = (round(o15 * 100, 1), c_stats, f"Over 1.5 goals.{xg_note} λ={total_lam:.2f}.")
    probs["over_25_goals"]  = (round(o25 * 100, 1), c_stats, f"Over 2.5 goals.{xg_note} λ={total_lam:.2f}.")
    probs["over_35_goals"]  = (round(o35 * 100, 1), c_stats, f"Over 3.5 goals.{xg_note} λ={total_lam:.2f}.")
    probs["over_45_goals"]  = (round(o45 * 100, 1), c_stats, f"Over 4.5 goals.{xg_note} λ={total_lam:.2f}.")
    probs["under_25_goals"] = (round((1 - o25) * 100, 1), c_stats, f"Under 2.5 goals.{xg_note} λ={total_lam:.2f}.")

    # ── 6. BTTS ─────────────────────────────────────────────────────────────
    if meth.is_finished:
        btts_p = 1.0 if (meth.h_goals >= 1 and meth.a_goals >= 1) else 0.0
    elif meth.is_live and meth.h_goals >= 1 and meth.a_goals >= 1:
        btts_p = 1.0
    elif meth.is_live and meth.minute > 0:
        # One or both teams yet to score — recompute from remaining lambda
        if meth.h_goals == 0:
            p_h_scores_rem = 1 - _poisson(h_lam * (90 - meth.minute) / 90, 0)
        else:
            p_h_scores_rem = 1.0
        if meth.a_goals == 0:
            p_a_scores_rem = 1 - _poisson(a_lam * (90 - meth.minute) / 90, 0)
        else:
            p_a_scores_rem = 1.0
        btts_p = p_h_scores_rem * p_a_scores_rem
    else:
        btts_p = _poisson_btts(h_lam, a_lam)

    btts_note = f"{hn} {meth.h_gpg:.2f} G/game, {an} {meth.a_gpg:.2f} G/game."
    probs["btts_yes"] = (round(btts_p * 100, 1),  c_stats, f"BTTS Yes. {btts_note}")
    probs["btts_no"]  = (round((1 - btts_p) * 100, 1), c_stats, f"BTTS No — at least one team fails to score. {btts_note}")

    # ── 7. Corners ──────────────────────────────────────────────────────────
    o85c = meth.o85c_pct
    # Estimate over 9.5 from baseline ratio (~75% of over 8.5 probability)
    o95c = _clamp(o85c * 0.78, 0.0, 99.9)
    avg_c90 = cfg.baselines.avg_corners_per_90
    if meth.is_live and meth.minute > 0:
        pace  = meth.total_corners / meth.minute * 90.0
        cexpl = f"{meth.total_corners} corners in {meth.minute}' → pace {pace:.1f}/90 (baseline {avg_c90})."
    else:
        cexpl = f"Pre-match estimate — baseline {avg_c90:.1f} corners/90."
    probs["over_85_corners"] = (round(o85c, 1), c_corner, cexpl)
    probs["over_95_corners"] = (round(o95c, 1), round(c_corner * 0.90, 1),
                                 f"Over 9.5 corners — higher threshold than 8.5 line.")

    # ── 8. Cards ────────────────────────────────────────────────────────────
    o45k = meth.o45k_pct
    # Over 3.5 cards ~ higher probability than 4.5
    o35k = _clamp(o45k * 1.30, 0.0, 99.9)
    avg_k90 = cfg.baselines.avg_cards_per_90
    if meth.is_live and meth.minute > 0:
        frate = meth.total_fouls / meth.minute if meth.minute > 0 else 0
        kexpl = (f"{meth.total_cards} cards in {meth.minute}' "
                 f"({meth.total_fouls} fouls, {frate:.2f}/min).")
    else:
        kexpl = f"Pre-match estimate — baseline {avg_k90:.1f} cards/90."
    probs["over_45_cards"] = (round(o45k, 1), c_card, kexpl)
    probs["over_35_cards"] = (round(o35k, 1), round(c_card * 0.93, 1), f"Over 3.5 cards — lower threshold. {kexpl}")

    # ── 9. Player Goals & 10. Player Assists ─────────────────────────────────
    _add_player_markets(data, hn, an, h_lam, a_lam, meth, probs)

    return probs


def _add_player_markets(
    data:  dict,
    hn:    str,
    an:    str,
    h_lam: float,
    a_lam: float,
    meth:  MethodologyResult,
    probs: dict,
) -> None:
    """Estimate player anytime scorer / assist probabilities."""
    lineups = data.get("lineups", {}) or {}
    events  = data.get("events",  []) or []

    # P(team scores at all) — used to scale player probability
    p_h_scores = 1.0 - _poisson(h_lam, 0)
    p_a_scores = 1.0 - _poisson(a_lam, 0)

    def _get_striker(lu_dict: dict, side_name: str) -> tuple[str, str]:
        """Return (player_name, position_key)."""
        start = lu_dict.get("startXI") or []
        for entry in start:
            p = entry.get("player") or entry
            pos = str(p.get("pos") or p.get("position") or "")
            if pos.upper() in ("F", "FW", "ST", "CF", "LW", "RW", "SS"):
                return p.get("name", f"{side_name} Striker"), pos
        # No striker found — use first outfield player
        for entry in start:
            p = entry.get("player") or entry
            pos = str(p.get("pos") or p.get("position") or "")
            if pos.upper() not in ("GK",) and p.get("name"):
                return p.get("name", side_name), pos
        return f"{side_name} Striker", "FW"

    h_lu = lineups.get("home") or {}
    a_lu = lineups.get("away") or {}

    h_striker, _ = _get_striker(h_lu, hn)
    a_striker, _ = _get_striker(a_lu, an)

    # Top striker accounts for ~30-40% of team goals (use 0.33 as base)
    scorer_share = 0.33

    # Check if this player already scored (live) — adjust probability
    def _goal_count(player_name: str) -> int:
        name_lower = player_name.lower()
        return sum(
            1 for e in events
            if e.get("type") == "Goal"
            and name_lower in (
                (e.get("player") if isinstance(e.get("player"), dict) else {})
                .get("name", "").lower()
            )
        )

    h_scored = _goal_count(h_striker)
    a_scored = _goal_count(a_striker)

    # Live remaining goal probability
    if meth.is_live and meth.minute > 0:
        rem = max(0.0, (90 - meth.minute) / 90.0)
        h_rem_lam = h_lam * rem
        a_rem_lam = a_lam * rem
        h_p_score = 1.0 - _poisson(h_rem_lam, 0)
        a_p_score = 1.0 - _poisson(a_rem_lam, 0)
    else:
        h_p_score = p_h_scores
        a_p_score = p_a_scores

    h_anytime_prob = min(99.0, (h_p_score * scorer_share + h_scored * 0.25) * 100)
    a_anytime_prob = min(99.0, (a_p_score * scorer_share + a_scored * 0.25) * 100)

    # Pick the best opportunity (highest probability player)
    if h_anytime_prob >= a_anytime_prob:
        best_scorer_prob  = h_anytime_prob
        best_assister_prob = h_anytime_prob * 0.72
        scorer_name   = h_striker
        assister_name = h_striker
    else:
        best_scorer_prob  = a_anytime_prob
        best_assister_prob = a_anytime_prob * 0.72
        scorer_name   = a_striker
        assister_name = a_striker

    # Confidence is lower for player markets (more uncertain)
    p_conf = round(max(2.0, min(7.0, (p_h_scores + p_a_scores) * 2.5)), 1)

    probs["player_to_score"] = (
        round(best_scorer_prob, 1),
        p_conf,
        f"{scorer_name} anytime scorer — estimated {scorer_share:.0%} of team goals.",
    )
    probs["player_to_assist"] = (
        round(best_assister_prob, 1),
        round(p_conf * 0.90, 1),
        f"{assister_name} anytime assist — estimated from expected goals.",
    )


# ---------------------------------------------------------------------------
# Market metadata
# ---------------------------------------------------------------------------

def _market_name(market_id: str, hn: str, an: str, probs: dict) -> str:
    """Human-readable market label."""
    _names = {
        "home_win":        f"{hn} Win",
        "draw":            "Draw",
        "away_win":        f"{an} Win",
        "dnb_home":        f"{hn} Draw No Bet",
        "dnb_away":        f"{an} Draw No Bet",
        "dc_1x":           f"{hn} or Draw (1X)",
        "dc_x2":           f"Draw or {an} (X2)",
        "dc_12":           f"{hn} or {an} (12 — No Draw)",
        "ah_home":         f"{hn} Asian Handicap -0.5",
        "ah_away":         f"{an} Asian Handicap +0.5",
        "over_15_goals":   "Over 1.5 Goals",
        "over_25_goals":   "Over 2.5 Goals",
        "over_35_goals":   "Over 3.5 Goals",
        "over_45_goals":   "Over 4.5 Goals",
        "under_25_goals":  "Under 2.5 Goals",
        "btts_yes":        "BTTS Yes",
        "btts_no":         "BTTS No",
        "over_85_corners": "Over 8.5 Corners",
        "over_95_corners": "Over 9.5 Corners",
        "over_35_cards":   "Over 3.5 Cards",
        "over_45_cards":   "Over 4.5 Cards",
        "player_to_score": "Player to Score (Anytime)",
        "player_to_assist": "Player to Assist (Anytime)",
    }
    name = _names.get(market_id, market_id)
    # Embed player name if it's in the explanation
    if market_id in ("player_to_score", "player_to_assist") and market_id in probs:
        expl = probs[market_id][2]
        player = expl.split(" anytime")[0] if " anytime" in expl else ""
        if player and len(player) < 30:
            name = name.replace("Player", player, 1)
    return name


def _market_type(market_id: str) -> str:
    _types = {
        "home_win": "match_winner", "draw": "match_winner", "away_win": "match_winner",
        "dnb_home": "draw_no_bet", "dnb_away": "draw_no_bet",
        "dc_1x": "double_chance", "dc_x2": "double_chance", "dc_12": "double_chance",
        "ah_home": "asian_handicap", "ah_away": "asian_handicap",
        "over_15_goals": "goals", "over_25_goals": "goals", "over_35_goals": "goals",
        "over_45_goals": "goals", "under_25_goals": "goals",
        "btts_yes": "btts", "btts_no": "btts",
        "over_85_corners": "corners", "over_95_corners": "corners",
        "over_35_cards": "cards", "over_45_cards": "cards",
        "player_to_score": "player_goals", "player_to_assist": "player_assists",
    }
    return _types.get(market_id, "other")


def _rejection_reason(
    prob: float, conf: float, risk: str, cfg: BrainConfig
) -> str | None:
    g = cfg.gates
    if prob < g.min_probability:
        return f"Probability {prob:.1f}% < minimum {g.min_probability:.0f}%"
    if conf < g.min_confidence:
        return f"Confidence {conf:.1f} < minimum {g.min_confidence:.1f}"
    if risk not in g.allowed_risk_levels:
        return f"Risk '{risk}' not in allowed levels {list(g.allowed_risk_levels)}"
    return None


# ---------------------------------------------------------------------------
# Engine entry point
# ---------------------------------------------------------------------------

ALL_MARKET_IDS = [
    "home_win", "draw", "away_win",
    "dnb_home", "dnb_away",
    "dc_1x", "dc_x2", "dc_12",
    "ah_home", "ah_away",
    "over_15_goals", "over_25_goals", "over_35_goals", "over_45_goals", "under_25_goals",
    "btts_yes", "btts_no",
    "over_85_corners", "over_95_corners",
    "over_35_cards", "over_45_cards",
    "player_to_score", "player_to_assist",
]


def run(
    data:     dict,
    hn:       str,
    an:       str,
    fixture_id: int,
    meth:     MethodologyResult,
    conf:     ConfidenceResult,
    mv1:      MethodologyV1Result,
    learning: LearningContext,
    cfg:      BrainConfig,
) -> DecisionCenterResult:
    """
    Evaluate all 23 markets and return a ranked DecisionCenterResult.

    Parameters
    ----------
    data       : raw analyze_fixture() dict
    hn / an    : home / away team names
    fixture_id : fixture integer id
    meth       : MethodologyResult (Poisson model)
    conf       : ConfidenceResult
    mv1        : MethodologyV1Result (15-category gate)
    learning   : LearningContext (historical accuracy)
    cfg        : BrainConfig (operational thresholds)
    """
    # Compute raw probabilities for all markets
    probs = _compute_probabilities(data, hn, an, meth, conf, cfg)

    evaluations: list[MarketEvaluation] = []

    for mid in ALL_MARKET_IDS:
        if mid not in probs:
            continue

        prob, raw_conf, expl = probs[mid]
        mtype  = _market_type(mid)
        lconf  = _live_confidence(raw_conf, meth)
        ev     = _expected_value(prob, mid)
        msc    = _methodology_score_for(mtype, mv1)
        risk   = cfg.risk_level(prob, raw_conf)
        hist   = learning.accuracy_for(mid)
        comp   = _composite(prob, raw_conf, ev, msc, hist)
        reject = _rejection_reason(prob, raw_conf, risk, cfg)

        evaluations.append(MarketEvaluation(
            market_id=mid,
            market_name=_market_name(mid, hn, an, probs),
            market_type=mtype,
            probability=prob,
            confidence=raw_conf,
            live_confidence=lconf,
            expected_value=ev,
            methodology_score=msc,
            historical_accuracy=hist,
            bankroll_suitability=risk,
            risk=risk,
            composite_score=comp,
            explanation=expl,
            actionable=reject is None,
            rank=0,
            rejected_reason=reject,
        ))

    # Sort: actionable first, then by composite score desc
    evaluations.sort(key=lambda e: (not e.actionable, -e.composite_score))

    # Assign ranks (only actionable get a rank)
    action_rank = 1
    for ev_item in evaluations:
        if ev_item.actionable:
            ev_item.rank = action_rank
            action_rank += 1

    actionable = [e for e in evaluations if e.actionable]
    rejected   = [e for e in evaluations if not e.actionable]

    # Top 5: prefer actionable, fall back to best overall if fewer than 5
    if len(actionable) >= 5:
        top_5 = actionable[:5]
    else:
        top_5 = actionable + [e for e in rejected if e not in actionable][: 5 - len(actionable)]
        top_5 = top_5[:5]

    best = actionable[0] if actionable else (evaluations[0] if evaluations else None)

    return DecisionCenterResult(
        hn=hn,
        an=an,
        fixture_id=fixture_id,
        all_markets=evaluations,
        actionable=actionable,
        rejected=rejected,
        top_5=top_5,
        best=best,
        total_evaluated=len(evaluations),
        total_actionable=len(actionable),
        total_rejected=len(rejected),
    )
