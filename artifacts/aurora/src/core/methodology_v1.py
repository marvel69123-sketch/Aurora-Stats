"""
Aurora Methodology v1 — 15-category weighted scoring system.

Every betting decision passes through this engine before being recommended.
Category weights and all thresholds are loaded from brain/methodology.json —
nothing is hardcoded here.

Categories (each scores 0–10):
  1.  match_context       — data richness, fixture type
  2.  team_strength       — league position, season win rate
  3.  current_form        — last N results trend
  4.  motivation          — inferred from round/competition context
  5.  home_advantage      — home win rate this season
  6.  away_performance    — away win rate this season
  7.  xg_analysis         — xG quality and consistency
  8.  live_momentum       — score, events, time pressure
  9.  corners_pattern     — live pace vs baseline
  10. cards_pattern       — discipline, fouls, bookings
  11. referee_influence   — referee presence signal
  12. tactical_style      — lineup and formation availability
  13. value_bet_detection — probability edge in best market
  14. bankroll_risk       — portfolio risk across markets
  15. historical_learning — past accuracy for market / league

Public API
----------
  run(data, hn, an, meth, conf, market, learning, mcfg, brain_cfg) -> MethodologyV1Result
"""
from __future__ import annotations

from dataclasses import dataclass, field

from src.brain import BrainConfig, MethodologyConfig
from src.core.confidence_engine import ConfidenceResult
from src.core.learning_engine import LearningContext
from src.core.market_engine import MarketResult
from src.core.methodology_engine import MethodologyResult, _form_score


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class CategoryScore:
    key:          str
    name:         str     # human-readable label
    score:        float   # 0–10
    weight:       float   # configured weight
    contribution: float   # score × weight (for decomposition)
    reason:       str     # one-sentence explanation


@dataclass
class MethodologyV1Result:
    """Full output of the Aurora Methodology v1 engine."""

    categories:         dict[str, CategoryScore]  # keyed by category key
    overall_score:      float          # weighted average 0–10
    confidence:         float          # 0–10 (derived from score + data richness)
    risk:               str            # Low | Medium | High
    recommended_market: str | None     # best market label passing all gates, or None
    blocked_markets:    list[str]      # market labels that failed methodology gates
    reasons:            list[str]      # top positive + flagged negative signals
    passed:             bool           # overall_score ≥ min_score_to_recommend


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _clamp(v: float, lo: float = 0.0, hi: float = 10.0) -> float:
    return round(min(hi, max(lo, v)), 2)


def _f(val, d: float = 0.0) -> float:
    try:
        return float(str(val).replace("%", ""))
    except Exception:
        return d


def _i(val, d: int = 0) -> int:
    try:
        return int(val)
    except Exception:
        return d


def _win_rate(standing: dict | None) -> float:
    if not standing:
        return 0.33
    p = _i(standing.get("played"), 0)
    w = _i(standing.get("won"), 0)
    return w / p if p > 0 else 0.33


# ---------------------------------------------------------------------------
# Category scorers — one function per category
# ---------------------------------------------------------------------------


def _score_match_context(
    meth: MethodologyResult,
) -> tuple[float, str]:
    base = 4.0
    if meth.is_live:
        base = 8.5
    elif meth.is_finished:
        base = 7.0

    boost = (
        (0.5 if meth.has_stats else 0.0)
        + (0.5 if meth.has_xg else 0.0)
        + (0.3 if meth.has_standings else 0.0)
        + (0.2 if meth.has_events else 0.0)
    )
    score = _clamp(base + boost)

    if meth.is_live:
        context = f"Live at {meth.minute}' — full data available ({int(boost / 1.5 * 100):.0f}% signal coverage)."
    elif meth.is_finished:
        context = "Finished match — complete data for post-match analysis."
    else:
        signals = sum([meth.has_standings, meth.has_xg, meth.has_stats, meth.has_events])
        context = f"Upcoming fixture — {signals}/4 pre-match signals available."
    return score, context


def _score_team_strength(
    data: dict,
) -> tuple[float, str]:
    sh = data["standings"]["home"]
    sa = data["standings"]["away"]
    teams = data["teams"]
    hn = teams["home"]["name"]
    an = teams["away"]["name"]

    h_wr = _win_rate(sh)
    a_wr = _win_rate(sa)
    avg_wr = (h_wr + a_wr) / 2.0
    score = _clamp(avg_wr * 10.0)

    h_pct = f"{h_wr:.0%}"
    a_pct = f"{a_wr:.0%}"
    context = f"{hn} win rate {h_pct}, {an} win rate {a_pct} — combined strength {avg_wr:.0%}."
    return score, context


def _score_current_form(
    data: dict,
    n: int,
) -> tuple[float, str]:
    sh = data["standings"]["home"]
    sa = data["standings"]["away"]
    teams = data["teams"]
    hn = teams["home"]["name"]
    an = teams["away"]["name"]

    h_form_str = (sh.get("form") or "") if sh else ""
    a_form_str = (sa.get("form") or "") if sa else ""

    h_fs = _form_score(h_form_str, n)
    a_fs = _form_score(a_form_str, n)
    best  = max(h_fs, a_fs)
    score = _clamp(best * 10.0)

    def fmt(f: str, n: int) -> str:
        icons = {"W": "W", "D": "D", "L": "L"}
        return "".join(icons.get(c, c) for c in f[-n:]) or "N/A"

    context = (
        f"{hn} form: {fmt(h_form_str, n)} · "
        f"{an} form: {fmt(a_form_str, n)} — "
        f"lead team at {best:.0%}."
    )
    return score, context


def _score_motivation(
    data: dict,
) -> tuple[float, str]:
    lg    = data.get("league", {})
    round_name = (lg.get("round") or "").lower()

    high_keywords   = ["final", "semi", "quarter", "playoff", "cup", "champion"]
    medium_keywords = ["relegation", "title", "europe", "europa", "ucl", "last"]

    if any(k in round_name for k in high_keywords):
        score = 9.0
        context = f"High-stakes fixture ({lg.get('round', 'Cup/Playoff')}) — peak motivation expected."
    elif any(k in round_name for k in medium_keywords):
        score = 7.0
        context = f"Important league phase ({lg.get('round', 'N/A')}) — elevated motivation."
    else:
        score = 5.0
        context = f"Regular season match ({lg.get('round', 'N/A')}) — standard motivation level."
    return _clamp(score), context


def _score_home_advantage(
    data: dict,
    threshold: float,
) -> tuple[float, str]:
    sh = data["standings"]["home"]
    teams = data["teams"]
    hn = teams["home"]["name"]

    if sh and sh.get("home_record"):
        hr = sh["home_record"]
        p  = _i(hr.get("played"), 0)
        w  = _i(hr.get("won"), 0)
        wr = w / p if p > 0 else _win_rate(sh)
        score = _clamp(wr * 10.0)
        context = f"{hn} home record: {w}W/{p}P ({wr:.0%}) — {'strong' if wr >= threshold else 'weak'} home fortress."
    elif sh:
        wr = _win_rate(sh)
        score = _clamp(wr * 8.0)
        context = f"{hn} overall win rate {wr:.0%} (no venue split available)."
    else:
        score = 4.0
        context = f"{hn} home advantage — no standings data, using prior."
    return score, context


def _score_away_performance(
    data: dict,
    threshold: float,
) -> tuple[float, str]:
    sa = data["standings"]["away"]
    teams = data["teams"]
    an = teams["away"]["name"]

    if sa and sa.get("away_record"):
        ar = sa["away_record"]
        p  = _i(ar.get("played"), 0)
        w  = _i(ar.get("won"), 0)
        wr = w / p if p > 0 else _win_rate(sa)
        score = _clamp(wr * 10.0)
        context = f"{an} away record: {w}W/{p}P ({wr:.0%}) — {'solid' if wr >= threshold else 'poor'} away form."
    elif sa:
        wr = _win_rate(sa)
        score = _clamp(wr * 7.5)
        context = f"{an} overall win rate {wr:.0%} (no venue split available)."
    else:
        score = 3.5
        context = f"{an} away performance — no standings data, using prior."
    return score, context


def _score_xg_analysis(
    meth: MethodologyResult,
    high_combined: float,
    consistency_tol: float,
) -> tuple[float, str]:
    if not meth.has_xg:
        score   = 3.5
        context = "xG not available — scoring rates inferred from season standings only."
        return score, context

    total_xg = meth.h_xg_val + meth.a_xg_val
    base = 6.5

    if total_xg > high_combined:
        base += 1.0

    if meth.is_live or meth.is_finished:
        actual = float(meth.total_goals)
        if abs(total_xg - actual) <= consistency_tol:
            base += 1.5
        else:
            base += 0.5

    score   = _clamp(base)
    context = (
        f"xG available — {meth.h_xg_val:.2f} vs {meth.a_xg_val:.2f} "
        f"(combined {total_xg:.2f}; {'high' if total_xg > high_combined else 'low'} attacking intent)."
    )
    return score, context


def _score_live_momentum(
    meth: MethodologyResult,
    data: dict,
    late_minute: int,
) -> tuple[float, str]:
    if not (meth.is_live or meth.is_finished):
        return 3.0, "Pre-match — no live momentum data yet."

    base = 6.0

    if meth.is_finished:
        score   = _clamp(base + 1.0)
        context = (
            f"Final score {meth.h_goals}–{meth.a_goals} — complete momentum picture available."
        )
        return score, context

    events = data.get("events", [])
    recent = [e for e in events if e.get("minute") and e["minute"] >= meth.minute - 15]
    recent_goals = [e for e in recent if e.get("type") == "Goal"]

    boost = 0.0
    if meth.minute >= late_minute:
        boost += 0.7
    if recent_goals:
        boost += 0.8
    if meth.h_goals != meth.a_goals:
        boost += 0.5

    score = _clamp(base + boost)
    desc  = (
        f"{meth.h_goals}–{meth.a_goals} at {meth.minute}'"
        + (f", {len(recent_goals)} recent goal(s)" if recent_goals else "")
        + ("." if meth.minute >= late_minute else " — match still open.")
    )
    context = f"Live momentum: {desc}"
    return score, context


def _score_corners_pattern(
    meth: MethodologyResult,
    high_pace: float,
    low_pace: float,
) -> tuple[float, str]:
    if not (meth.is_live or meth.is_finished):
        return 4.5, f"Pre-match corners — baseline ~{high_pace:.1f}/90 applied, no live data."

    if meth.minute > 0:
        pace = meth.total_corners / meth.minute * 90.0
        if pace >= high_pace:
            score = _clamp(7.0 + (pace - high_pace) * 0.3)
            context = f"{meth.total_corners} corners in {meth.minute}' → {pace:.1f}/90 (above {high_pace} baseline — high-corner match)."
        elif pace <= low_pace:
            score = _clamp(3.0 + (pace / low_pace) * 2.0)
            context = f"{meth.total_corners} corners in {meth.minute}' → {pace:.1f}/90 (below {low_pace} baseline — low-corner match)."
        else:
            score = 5.5
            context = f"{meth.total_corners} corners in {meth.minute}' → {pace:.1f}/90 (on-baseline)."
    else:
        score   = 4.5
        context = "Match started but no minute data — corner pace unknown."
    return score, context


def _score_cards_pattern(
    meth: MethodologyResult,
    high_fouls_rate: float,
    low_fouls_rate: float,
) -> tuple[float, str]:
    if not (meth.is_live or meth.is_finished):
        return 4.0, "Pre-match cards — historical baseline applied, no live foul data."

    if meth.minute > 0:
        foul_rate = meth.total_fouls / meth.minute
        card_rate = meth.total_cards / meth.minute

        if foul_rate >= high_fouls_rate:
            score   = _clamp(7.0 + card_rate * 15.0)
            context = (
                f"{meth.total_cards} cards, {meth.total_fouls} fouls in {meth.minute}' "
                f"({foul_rate:.2f} fouls/min — high-intensity disciplinary match)."
            )
        elif foul_rate <= low_fouls_rate:
            score   = _clamp(3.0 + foul_rate * 10.0)
            context = (
                f"{meth.total_cards} cards, {meth.total_fouls} fouls in {meth.minute}' "
                f"({foul_rate:.2f} fouls/min — clean match so far)."
            )
        else:
            score   = 5.0
            context = (
                f"{meth.total_cards} cards, {meth.total_fouls} fouls in {meth.minute}' "
                f"({foul_rate:.2f} fouls/min — average discipline)."
            )
    else:
        score   = 4.0
        context = "Match started but no minute data — discipline pattern unknown."
    return score, context


def _score_referee_influence(
    data: dict,
) -> tuple[float, str]:
    referee = data.get("fixture", {}).get("referee")
    if referee:
        score   = 5.5
        context = f"Referee: {referee} — appointed but no historical card stats in system."
    else:
        score   = 3.0
        context = "No referee information available — influence cannot be assessed."
    return _clamp(score), context


def _score_tactical_style(
    data: dict,
) -> tuple[float, str]:
    lineups = data.get("lineups", {})
    h_lu    = lineups.get("home")
    a_lu    = lineups.get("away")

    if h_lu and a_lu:
        hf = h_lu.get("formation") or "?"
        af = a_lu.get("formation") or "?"
        attack_formations = {"4-3-3", "4-2-3-1", "3-4-3", "4-4-2"}
        h_atk = hf in attack_formations
        a_atk = af in attack_formations
        score = 6.5 + (0.75 if h_atk else 0.0) + (0.75 if a_atk else 0.0)
        context = (
            f"{data['teams']['home']['name']} {hf} vs "
            f"{data['teams']['away']['name']} {af} — "
            f"{'both attack-minded' if h_atk and a_atk else 'mixed tactical styles'}."
        )
    elif h_lu or a_lu:
        lu = h_lu or a_lu
        side = "home" if h_lu else "away"
        score = 5.0
        context = f"Only {side} lineup confirmed ({lu.get('formation', '?')}) — partial tactical insight."
    else:
        score   = 3.0
        context = "No lineup data available — tactical style cannot be assessed."
    return _clamp(score), context


def _score_value_bet_detection(
    market: MarketResult,
    value_min_prob: float,
    value_min_conf: float,
) -> tuple[float, str]:
    best = market.best

    if best.probability >= value_min_prob and best.confidence >= value_min_conf:
        edge = best.probability - value_min_prob
        score = _clamp(7.0 + edge * 0.1)
        context = (
            f"Value detected: {best.label} at {best.probability:.0f}% "
            f"(≥{value_min_prob:.0f}% gate), confidence {best.confidence:.1f}/10."
        )
    elif best.probability >= value_min_prob:
        score   = 5.5
        context = (
            f"{best.label} at {best.probability:.0f}% — probability qualifies "
            f"but confidence {best.confidence:.1f} < {value_min_conf} gate."
        )
    elif best.probability >= 50.0:
        score   = 4.5
        context = (
            f"Best market {best.label} at {best.probability:.0f}% — "
            f"below {value_min_prob:.0f}% value threshold."
        )
    else:
        score   = 2.5
        context = f"No market exceeds 50% probability — no value edge detected."
    return score, context


def _score_bankroll_risk(
    market: MarketResult,
) -> tuple[float, str]:
    counts = {"Low": 0, "Medium": 0, "High": 0}
    for ms in market.markets.values():
        counts[ms.risk] = counts.get(ms.risk, 0) + 1

    if counts["Low"] >= 2:
        score   = _clamp(8.0 + counts["Low"] * 0.5)
        context = f"{counts['Low']} Low-risk markets available — healthy bankroll profile."
    elif counts["Low"] == 1:
        score   = 6.5
        context = f"1 Low-risk market, {counts['Medium']} Medium-risk — acceptable bankroll exposure."
    elif counts["Medium"] >= 2:
        score   = 5.0
        context = f"No Low-risk markets — {counts['Medium']} Medium-risk. Reduced stakes advised."
    elif counts["Medium"] == 1:
        score   = 3.5
        context = f"Only 1 Medium-risk market available — high overall portfolio risk."
    else:
        score   = 1.5
        context = f"All {counts['High']} markets are High-risk — portfolio exposure critical."
    return score, context


def _score_historical_learning(
    learning: LearningContext,
    market: MarketResult,
    good_acc: float,
    poor_acc: float,
) -> tuple[float, str]:
    if not learning.has_history:
        return 5.0, "No prediction history yet — methodology score neutral (unproven track record)."

    # Try league-specific accuracy first
    if learning.league_accuracy is not None:
        acc = learning.league_accuracy
        context_prefix = f"League accuracy {acc:.1f}% ({learning.league_name})"
    else:
        # Fall back to best-market accuracy
        acc = learning.accuracy_for(market.best.key)
        if acc is None:
            return 5.0, "Insufficient resolved predictions for this market — score neutral."
        context_prefix = f"Best-market ({market.best.key}) accuracy {acc:.1f}%"

    if acc >= good_acc:
        score   = _clamp(7.0 + (acc - good_acc) / 10.0)
        context = f"{context_prefix} — strong historical performance (≥{good_acc:.0f}% gate)."
    elif acc >= poor_acc:
        score   = _clamp(4.0 + (acc - poor_acc) / (good_acc - poor_acc) * 3.0)
        context = f"{context_prefix} — acceptable but not strong ({poor_acc:.0f}–{good_acc:.0f}% range)."
    else:
        score   = _clamp(1.0 + acc / poor_acc * 3.0)
        context = f"{context_prefix} — below {poor_acc:.0f}% threshold — poor track record, caution flagged."
    return score, context


# ---------------------------------------------------------------------------
# Aggregation and gating
# ---------------------------------------------------------------------------


def _build_reasons(
    categories: dict[str, CategoryScore],
    blocked: list[str],
) -> list[str]:
    """Generate top positive signals and flagged negatives for the response."""
    ranked = sorted(categories.values(), key=lambda c: c.score, reverse=True)
    reasons: list[str] = []

    for cs in ranked[:3]:
        reasons.append(f"✅ [{cs.name}] {cs.reason}")

    weak = [c for c in ranked if c.score < 4.0]
    for cs in weak[-2:]:
        reasons.append(f"⚠️  [{cs.name}] {cs.reason}")

    if blocked:
        reasons.append(f"🚫 Blocked markets: {', '.join(blocked)}")

    return reasons


def _determine_risk(score: float, mcfg: MethodologyConfig) -> str:
    if score >= mcfg.low_risk_above:
        return "Low"
    if score >= mcfg.medium_risk_above:
        return "Medium"
    return "High"


def _gate_markets(
    overall_score: float,
    categories: dict[str, CategoryScore],
    market: MarketResult,
    mcfg: MethodologyConfig,
) -> tuple[str | None, list[str]]:
    """
    Apply methodology gates. Return (recommended_market_label, blocked_labels).
    """
    blocked: list[str] = []
    all_labels = [ms.label for ms in market.ranked]

    # Gate 1: overall score must meet minimum
    if overall_score < mcfg.min_score_to_recommend:
        return None, all_labels

    # Gate 2: blocking categories
    for cat_key, min_score in mcfg.blocking_thresholds.items():
        cs = categories.get(cat_key)
        if cs and cs.score < min_score:
            return None, all_labels  # all markets blocked

    # Gate 3: market-specific pattern gates
    market_blocks: dict[str, bool] = {}

    corners_score = categories.get("corners_pattern")
    if corners_score and corners_score.score < mcfg.corners_min_pattern_score:
        market_blocks["over_85_corners"] = True

    cards_score = categories.get("cards_pattern")
    if cards_score and cards_score.score < mcfg.cards_min_pattern_score:
        market_blocks["over_45_cards"] = True

    # Find first market passing all gates
    recommended: str | None = None
    for ms in market.ranked:
        if market_blocks.get(ms.key):
            blocked.append(ms.label)
        else:
            if recommended is None and ms.actionable:
                recommended = ms.label
            elif recommended is None:
                pass  # keep scanning for actionable

    # Collect all non-recommended as blocked (from methodology perspective)
    remaining_blocked = [ms.label for ms in market.ranked if ms.label != recommended and ms.label not in blocked]
    blocked = list(dict.fromkeys(blocked + remaining_blocked))  # preserve order, dedupe

    return recommended, blocked


# ---------------------------------------------------------------------------
# Engine entry point
# ---------------------------------------------------------------------------


CATEGORY_NAMES = {
    "match_context":       "Match Context",
    "team_strength":       "Team Strength",
    "current_form":        "Current Form",
    "motivation":          "Motivation",
    "home_advantage":      "Home Advantage",
    "away_performance":    "Away Performance",
    "xg_analysis":         "xG Analysis",
    "live_momentum":       "Live Momentum",
    "corners_pattern":     "Corners Pattern",
    "cards_pattern":       "Cards Pattern",
    "referee_influence":   "Referee Influence",
    "tactical_style":      "Tactical Style",
    "value_bet_detection": "Value Bet Detection",
    "bankroll_risk":       "Bankroll Risk",
    "historical_learning": "Historical Learning",
}


def run(
    data:      dict,
    hn:        str,
    an:        str,
    meth:      MethodologyResult,
    conf:      ConfidenceResult,
    market:    MarketResult,
    learning:  LearningContext,
    mcfg:      MethodologyConfig,
    brain_cfg: BrainConfig,
) -> MethodologyV1Result:
    """
    Score all 15 methodology categories and return a unified recommendation.

    Parameters
    ----------
    data       : raw analyze_fixture() dict
    hn / an    : home / away team names
    meth       : MethodologyResult (Poisson model output)
    conf       : ConfidenceResult
    market     : MarketResult (ranked markets)
    learning   : LearningContext (historical accuracy)
    mcfg       : MethodologyConfig (weights + thresholds from brain/methodology.json)
    brain_cfg  : BrainConfig (operational parameters from version.json)
    """
    sc = mcfg.scorers
    wt = mcfg.category_weights

    # ── Run all 15 scorers ──────────────────────────────────────────────────
    raw: dict[str, tuple[float, str]] = {
        "match_context":       _score_match_context(meth),
        "team_strength":       _score_team_strength(data),
        "current_form":        _score_current_form(data, sc.get("form_window", 5)),
        "motivation":          _score_motivation(data),
        "home_advantage":      _score_home_advantage(data, sc.get("home_strength_threshold", 0.50)),
        "away_performance":    _score_away_performance(data, sc.get("away_strength_threshold", 0.30)),
        "xg_analysis":         _score_xg_analysis(meth, sc.get("xg_high_combined", 2.5), sc.get("xg_consistency_tolerance", 0.5)),
        "live_momentum":       _score_live_momentum(meth, data, sc.get("live_momentum_late_minute", 70)),
        "corners_pattern":     _score_corners_pattern(meth, sc.get("corners_high_pace", 11.0), sc.get("corners_low_pace", 8.0)),
        "cards_pattern":       _score_cards_pattern(meth, sc.get("cards_high_fouls_per_min", 0.40), sc.get("cards_low_fouls_per_min", 0.20)),
        "referee_influence":   _score_referee_influence(data),
        "tactical_style":      _score_tactical_style(data),
        "value_bet_detection": _score_value_bet_detection(market, sc.get("value_min_probability", 60.0), sc.get("value_min_confidence", 5.5)),
        "bankroll_risk":       _score_bankroll_risk(market),
        "historical_learning": _score_historical_learning(learning, market, sc.get("learning_good_accuracy", 60.0), sc.get("learning_poor_accuracy", 40.0)),
    }

    # ── Assemble CategoryScore objects ──────────────────────────────────────
    categories: dict[str, CategoryScore] = {}
    overall_score = 0.0
    for key, (score, reason) in raw.items():
        weight = wt.get(key, 0.0)
        contrib = round(score * weight, 4)
        overall_score += contrib
        categories[key] = CategoryScore(
            key=key,
            name=CATEGORY_NAMES.get(key, key),
            score=round(score, 2),
            weight=round(weight, 4),
            contribution=contrib,
            reason=reason,
        )

    overall_score = round(_clamp(overall_score), 2)

    # ── Derive confidence from overall_score + data signal count ────────────
    methodology_confidence = round(
        min(10.0, overall_score * 0.7 + conf.overall * 0.3), 1
    )

    # ── Risk classification ──────────────────────────────────────────────────
    risk = _determine_risk(overall_score, mcfg)

    # ── Market gating ────────────────────────────────────────────────────────
    passed = overall_score >= mcfg.min_score_to_recommend
    recommended_market, blocked_markets = _gate_markets(
        overall_score, categories, market, mcfg
    )

    # ── Human-readable reasons ───────────────────────────────────────────────
    reasons = _build_reasons(categories, blocked_markets)

    return MethodologyV1Result(
        categories=categories,
        overall_score=overall_score,
        confidence=methodology_confidence,
        risk=risk,
        recommended_market=recommended_market,
        blocked_markets=blocked_markets,
        reasons=reasons,
        passed=passed,
    )
