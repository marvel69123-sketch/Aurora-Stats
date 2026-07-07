"""
/aurora/score — Betting-grade probability scores for a fixture.

Reads AURORA_BRAIN operational parameters via src.brain.get_config() before
computing any prediction. All numeric thresholds (risk levels, signal weights,
market baselines, confidence caps) come from brain/version.json — never hardcoded.

Model layers (applied in order):
  1. Pre-match prior  — standings venue win-rate + recent form (brain weights)
  2. xG Poisson model — Poisson win/draw/loss blended by brain xg_blend_weight
  3. Live adjustment  — current score × time_weight (brain max_live_score_weight)
  4. Market models    — BTTS, Over 2.5, Over 8.5 corners, Over 4.5 cards
     (all baselines from brain market_baselines)
  5. Risk + actionability — thresholds from brain confidence_thresholds / betting_gates
"""
from __future__ import annotations

import math
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from src.brain import get_brain_meta, get_config
from src.routers.analyze import analyze_fixture

router = APIRouter()

# ---------------------------------------------------------------------------
# Match-status sets
# ---------------------------------------------------------------------------

_LIVE = {"1H", "2H", "ET", "P", "BT", "HT", "SUSP", "INT", "LIVE"}
_FINISHED = {"FT", "AET", "PEN", "AWD", "WO"}

# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class MarketScore(BaseModel):
    probability: float
    confidence: float
    risk: str
    actionable: bool
    explanation: str


class ScoreResponse(BaseModel):
    match: str
    fixture_id: int
    date: str
    status: str
    minute: int | None

    overall_confidence: float
    risk_level: str
    best_market: str
    recommended_markets: list[str]
    summary: str

    home_win: MarketScore
    draw: MarketScore
    away_win: MarketScore
    btts: MarketScore
    over_25_goals: MarketScore
    over_85_corners: MarketScore
    over_45_cards: MarketScore

    brain: dict[str, Any]


# ---------------------------------------------------------------------------
# Math helpers
# ---------------------------------------------------------------------------


def _f(val, default: float = 0.0) -> float:
    try:
        return float(str(val).replace("%", ""))
    except Exception:
        return default


def _i(val, default: int = 0) -> int:
    try:
        return int(val)
    except Exception:
        return default


def _poisson(lam: float, k: int) -> float:
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def _poisson_over(lam: float, threshold: float) -> float:
    """P(X > threshold) where threshold may be x.5."""
    cutoff = int(threshold + 0.5)
    return max(0.0, 1.0 - sum(_poisson(lam, k) for k in range(cutoff)))


def _normalize(*vals: float) -> tuple[float, ...]:
    total = sum(vals)
    if total <= 0:
        n = len(vals)
        return tuple(1.0 / n for _ in vals)
    return tuple(v / total for v in vals)


# ---------------------------------------------------------------------------
# Feature helpers
# ---------------------------------------------------------------------------


def _form_score(form: str | None, n: int = 5) -> float:
    if not form:
        return 0.5
    tail = list(form[-n:])
    if not tail:
        return 0.5
    pts = sum(3 if c == "W" else 1 if c == "D" else 0 for c in tail)
    return pts / (3 * len(tail))


def _venue_win_rate(standing: dict | None, venue: str) -> float:
    if not standing:
        return 0.33
    rec = standing.get(f"{venue}_record") or {}
    played = _i(rec.get("played"), 0)
    won = _i(rec.get("won"), 0)
    if played > 0:
        return won / played
    p = _i(standing.get("played"), 0)
    w = _i(standing.get("won"), 0)
    return w / p if p > 0 else 0.33


def _goals_per_game(standing: dict | None, default: float) -> float:
    if not standing:
        return default
    gf = _f(standing.get("goals_for"), 0.0)
    p = _f(standing.get("played"), 0.0)
    return gf / p if p > 0 else default


# ---------------------------------------------------------------------------
# Poisson match-result model
# ---------------------------------------------------------------------------


def _poisson_result(h_lam: float, a_lam: float, max_goals: int) -> tuple[float, float, float]:
    h_win = draw = a_win = 0.0
    for hg in range(max_goals + 1):
        ph = _poisson(h_lam, hg)
        for ag in range(max_goals + 1):
            p = ph * _poisson(a_lam, ag)
            if hg > ag:
                h_win += p
            elif hg == ag:
                draw += p
            else:
                a_win += p
    return h_win, draw, a_win


# ---------------------------------------------------------------------------
# Market builder (uses brain config for risk / actionability)
# ---------------------------------------------------------------------------


def _market(prob: float, conf: float, explanation: str, overall_conf: float) -> MarketScore:
    from src.brain import get_config as _cfg
    cfg = _cfg()
    prob_c = round(min(100.0, max(0.0, prob)), 1)
    conf_c = round(min(10.0, max(0.0, conf)), 1)
    return MarketScore(
        probability=prob_c,
        confidence=conf_c,
        risk=cfg.risk_level(prob_c, conf_c),
        actionable=cfg.is_actionable(prob_c, conf_c, overall_conf),
        explanation=explanation,
    )


# ---------------------------------------------------------------------------
# Core scoring engine — reads brain config once per call
# ---------------------------------------------------------------------------


def _score(data: dict) -> ScoreResponse:  # noqa: C901
    cfg = get_config()                   # ← all thresholds come from the brain
    bl = cfg.baselines
    wt = cfg.weights

    fx = data["fixture"]
    teams = data["teams"]
    sc = data["score"]
    hs = data["statistics"]["home"]
    as_ = data["statistics"]["away"]
    events = data["events"]
    sh = data["standings"]["home"]
    sa = data["standings"]["away"]

    status_short = fx["status"]["short"]
    is_finished = status_short in _FINISHED
    is_live = status_short in _LIVE
    minute = _i(fx["status"]["minute"], 0)

    hn = teams["home"]["name"]
    an = teams["away"]["name"]

    h_goals = _i(sc["current"]["home"], 0)
    a_goals = _i(sc["current"]["away"], 0)
    total_goals = h_goals + a_goals
    has_score = sc["current"]["home"] is not None

    has_stats = any(hs.get(k) is not None for k in ("shots_total", "possession", "corners"))
    has_xg = hs.get("xg") is not None and as_.get("xg") is not None
    has_standings = sh is not None and sa is not None
    has_events = bool(events)

    # ── Data-richness confidence (brain: pre_match_confidence_cap) ───────────
    signals = [has_stats, has_xg, has_standings, has_events, is_live or is_finished]
    base_conf = 3.0 + sum(signals) * 1.3
    if not (is_live or is_finished):
        base_conf = min(base_conf, cfg.pre_match_confidence_cap)
    overall_confidence = min(10.0, base_conf)

    # ── Pre-match prior (brain: venue_weight_in_prior, form_weight_in_prior) ─
    h_venue_wr = _venue_win_rate(sh, "home")
    a_venue_wr = _venue_win_rate(sa, "away")
    h_form = _form_score(sh.get("form") if sh else None)
    a_form = _form_score(sa.get("form") if sa else None)

    vw = wt.venue_weight_in_prior
    fw = wt.form_weight_in_prior
    h_prior = h_venue_wr * vw + h_form * fw
    a_prior = a_venue_wr * vw + a_form * fw
    d_prior = max(bl.draw_base_rate, 1.0 - h_prior - a_prior)
    ph, pd, pa = _normalize(h_prior, d_prior, a_prior)

    # ── xG Poisson blend (brain: xg_blend_weight) ────────────────────────────
    h_xg_val = _f(hs.get("xg"), 0.0)
    a_xg_val = _f(as_.get("xg"), 0.0)

    if has_xg and (h_xg_val + a_xg_val) > 0:
        xg_h, xg_d, xg_a = _poisson_result(h_xg_val, a_xg_val, bl.max_goals_poisson)
        prior_w = 1.0 - wt.xg_blend_weight
        ph = ph * prior_w + xg_h * wt.xg_blend_weight
        pd = pd * prior_w + xg_d * wt.xg_blend_weight
        pa = pa * prior_w + xg_a * wt.xg_blend_weight
        ph, pd, pa = _normalize(ph, pd, pa)

    # ── Live / finished score adjustment (brain: max_live_score_weight) ──────
    if (is_live or is_finished) and has_score:
        max_tw = wt.max_live_score_weight
        time_w = max_tw if is_finished else min(max_tw, minute / 90.0 * max_tw)

        if h_goals > a_goals:
            sh_h, sh_d, sh_a = 0.82, 0.11, 0.07
        elif a_goals > h_goals:
            sh_h, sh_d, sh_a = 0.07, 0.11, 0.82
        else:
            base_d = 0.36 + total_goals * 0.04
            half = (1.0 - base_d) / 2.0
            sh_h, sh_d, sh_a = _normalize(half, base_d, half)

        prior_w = 1.0 - time_w
        ph = ph * prior_w + sh_h * time_w
        pd = pd * prior_w + sh_d * time_w
        pa = pa * prior_w + sh_a * time_w
        ph, pd, pa = _normalize(ph, pd, pa)

    ph_pct, pd_pct, pa_pct = ph * 100.0, pd * 100.0, pa * 100.0

    # ── BTTS (brain: default_home_gpg, default_away_gpg) ─────────────────────
    h_gpg = _goals_per_game(sh, bl.default_home_gpg)
    a_gpg = _goals_per_game(sa, bl.default_away_gpg)

    if has_xg and (h_xg_val + a_xg_val) > 0:
        btts_base = (1.0 - _poisson(h_xg_val, 0)) * (1.0 - _poisson(a_xg_val, 0)) * 100.0
    else:
        btts_base = (1.0 - _poisson(h_gpg, 0)) * (1.0 - _poisson(a_gpg, 0)) * 100.0

    if (is_live or is_finished) and has_score:
        both_scored = h_goals >= 1 and a_goals >= 1
        if both_scored:
            btts_pct = 100.0
        elif is_finished:
            btts_pct = 0.0
        else:
            remaining = max(0, 90 - minute)
            if h_goals >= 1:
                lam = (a_xg_val if has_xg else a_gpg) * remaining / 90.0
                btts_pct = (1.0 - _poisson(lam, 0)) * 100.0
            elif a_goals >= 1:
                lam = (h_xg_val if has_xg else h_gpg) * remaining / 90.0
                btts_pct = (1.0 - _poisson(lam, 0)) * 100.0
            else:
                lh = (h_xg_val if has_xg else h_gpg) * remaining / 90.0
                la = (a_xg_val if has_xg else a_gpg) * remaining / 90.0
                btts_pct = (1.0 - _poisson(lh, 0)) * (1.0 - _poisson(la, 0)) * 100.0
    else:
        btts_pct = btts_base

    btts_pct = min(100.0, max(0.0, btts_pct))

    # ── Over 2.5 goals ────────────────────────────────────────────────────────
    total_lam = (h_xg_val + a_xg_val) if (has_xg and h_xg_val + a_xg_val > 0) else (h_gpg + a_gpg)

    if (is_live or is_finished) and has_score:
        if total_goals >= 3:
            o25_pct = 100.0
        elif is_finished:
            o25_pct = 0.0
        else:
            remaining = max(0, 90 - minute)
            scaled = total_lam * remaining / 90.0
            needed = max(0, 3 - total_goals)
            o25_pct = (_poisson_over(scaled, needed - 1) * 100.0) if needed > 0 else 100.0
    else:
        o25_pct = _poisson_over(total_lam, 2.5) * 100.0

    o25_pct = min(100.0, max(0.0, o25_pct))

    # ── Over 8.5 corners (brain: avg_corners_per_90) ─────────────────────────
    total_cor = _i(hs.get("corners"), 0) + _i(as_.get("corners"), 0)
    avg_c90 = bl.avg_corners_per_90

    if (is_live or is_finished) and has_score:
        if total_cor > 8:
            o85c_pct = 100.0
        elif is_finished:
            o85c_pct = 0.0
        else:
            remaining = max(0, 90 - minute)
            rate = (total_cor / minute) if minute > 0 else (avg_c90 / 90.0)
            lam = rate * remaining
            needed = max(0, 9 - total_cor)
            o85c_pct = (_poisson_over(lam, needed - 1) * 100.0) if needed > 0 else 100.0
    else:
        o85c_pct = _poisson_over(avg_c90, 8.5) * 100.0

    o85c_pct = min(100.0, max(0.0, o85c_pct))

    # ── Over 4.5 cards (brain: avg_cards_per_90) ─────────────────────────────
    h_yel = _i(hs.get("yellow_cards"), 0)
    h_red = _i(hs.get("red_cards"), 0)
    a_yel = _i(as_.get("yellow_cards"), 0)
    a_red = _i(as_.get("red_cards"), 0)
    total_cards = h_yel + h_red + a_yel + a_red
    total_fouls = _i(hs.get("fouls"), 0) + _i(as_.get("fouls"), 0)
    avg_k90 = bl.avg_cards_per_90

    if (is_live or is_finished) and has_score:
        if total_cards > 4:
            o45k_pct = 100.0
        elif is_finished:
            o45k_pct = 0.0
        else:
            remaining = max(0, 90 - minute)
            raw_rate = (total_cards / minute) if minute > 0 else (avg_k90 / 90.0)
            foul_rate = (total_fouls / minute * 0.15) if minute > 0 else 0.0
            lam = max(raw_rate, foul_rate) * remaining
            needed = max(0, 5 - total_cards)
            o45k_pct = (_poisson_over(lam, needed - 1) * 100.0) if needed > 0 else 100.0
    else:
        o45k_pct = _poisson_over(avg_k90, 4.5) * 100.0

    o45k_pct = min(100.0, max(0.0, o45k_pct))

    # ── Per-market confidence adjustments (brain caps) ────────────────────────
    xg_boost = 0.8 if has_xg else 0.0
    stats_conf = min(10.0, overall_confidence + xg_boost)
    corner_conf = min(8.0, overall_confidence - 1.0) if (is_live or is_finished) else 4.5
    card_conf = min(8.0, overall_confidence - 1.0) if (is_live or is_finished) else 4.0

    # ── Explanations ─────────────────────────────────────────────────────────
    if sh and sh.get("home_record"):
        hr = sh["home_record"]
        hw_exp = (
            f"{hn} win {_i(hr.get('won'))}/{_i(hr.get('played'))} at home this season "
            f"(form: {(sh.get('form') or '')[-5:] or 'N/A'})."
        )
    else:
        hw_exp = f"{hn} home advantage applied; no standings data."
    if has_xg:
        hw_exp += f" xG: {h_xg_val:.2f}–{a_xg_val:.2f}."

    xg_gap = abs(h_xg_val - a_xg_val)
    if has_xg:
        draw_exp = (
            f"xG gap only {xg_gap:.2f} — closely contested, draw very plausible."
            if xg_gap < 0.25
            else f"xG gap {xg_gap:.2f} reduces draw probability."
        )
    else:
        draw_exp = "Estimated from standings form — draw rate typical for this tier."

    if sa and sa.get("away_record"):
        ar = sa["away_record"]
        aw_exp = (
            f"{an} win {_i(ar.get('won'))}/{_i(ar.get('played'))} away this season "
            f"(form: {(sa.get('form') or '')[-5:] or 'N/A'})."
        )
    else:
        aw_exp = f"{an} away record applied; no standings data."
    if has_xg:
        aw_exp += f" xG: {h_xg_val:.2f}–{a_xg_val:.2f}."

    btts_exp = f"{hn} {h_gpg:.2f} G/game, {an} {a_gpg:.2f} G/game (season avg)."
    if (is_live or is_finished) and has_score:
        if h_goals >= 1 and a_goals >= 1:
            btts_exp += " Both have already scored — BTTS confirmed."
        elif is_finished:
            btts_exp += f" FT {h_goals}–{a_goals}: not both scored."
        else:
            btts_exp += f" Score {h_goals}–{a_goals} at {minute}'."

    if has_xg:
        o25_exp = (
            f"Combined xG {h_xg_val + a_xg_val:.2f}. "
            + ("High-scoring pace." if (h_xg_val + a_xg_val) > 2.5 else "Low-scoring pace.")
        )
    else:
        o25_exp = f"Season scoring rates: {h_gpg:.2f} + {a_gpg:.2f} = {h_gpg + a_gpg:.2f} G/game."
    if (is_live or is_finished) and has_score:
        o25_exp += f" {total_goals} goal{'s' if total_goals != 1 else ''} scored so far."

    if (is_live or is_finished) and has_score and minute > 0:
        pace = total_cor / minute * 90.0
        o85c_exp = f"{total_cor} corners in {minute}' → pace {pace:.1f}/90."
    else:
        o85c_exp = f"Pre-match baseline of ~{avg_c90} corners/game applied (brain v{get_brain_meta()['brain_version']})."

    if (is_live or is_finished) and has_score and minute > 0:
        o45k_exp = f"{total_cards} card{'s' if total_cards != 1 else ''} in {minute}' ({total_fouls} total fouls)."
    else:
        o45k_exp = f"Pre-match baseline of ~{avg_k90} cards/game applied (brain v{get_brain_meta()['brain_version']})."

    # ── Best market + overall risk (brain thresholds) ─────────────────────────
    market_probs = {
        f"{hn} Win": ph_pct,
        "Draw": pd_pct,
        f"{an} Win": pa_pct,
        "BTTS Yes": btts_pct,
        "Over 2.5 Goals": o25_pct,
        "Over 8.5 Corners": o85c_pct,
        "Over 4.5 Cards": o45k_pct,
    }
    best_market = max(market_probs, key=lambda k: market_probs[k])
    best_prob = market_probs[best_market]
    risk_level = cfg.risk_level(best_prob, overall_confidence)

    # ── Recommended markets (pass all betting gates) ──────────────────────────
    market_confs = {
        f"{hn} Win": overall_confidence,
        "Draw": overall_confidence * 0.85,
        f"{an} Win": overall_confidence,
        "BTTS Yes": stats_conf,
        "Over 2.5 Goals": stats_conf,
        "Over 8.5 Corners": corner_conf,
        "Over 4.5 Cards": card_conf,
    }
    recommended_markets = [
        name
        for name, prob in market_probs.items()
        if cfg.is_actionable(prob, market_confs[name], overall_confidence)
    ]

    # ── Summary ───────────────────────────────────────────────────────────────
    score_str = f"{h_goals}–{a_goals}" if has_score else "upcoming"
    summary = (
        f"{hn} vs {an} [{score_str}] · "
        f"Confidence {overall_confidence:.1f}/10 · "
        f"Best market: {best_market} ({best_prob:.0f}%) · "
        f"Risk: {risk_level}."
    )

    return ScoreResponse(
        match=f"{hn} vs {an}",
        fixture_id=fx["id"],
        date=fx["date"],
        status=fx["status"]["long"],
        minute=minute if (is_live and minute) else None,
        overall_confidence=round(overall_confidence, 1),
        risk_level=risk_level,
        best_market=best_market,
        recommended_markets=recommended_markets,
        summary=summary,
        home_win=_market(ph_pct, overall_confidence, hw_exp, overall_confidence),
        draw=_market(pd_pct, overall_confidence * 0.85, draw_exp, overall_confidence),
        away_win=_market(pa_pct, overall_confidence, aw_exp, overall_confidence),
        btts=_market(btts_pct, stats_conf, btts_exp, overall_confidence),
        over_25_goals=_market(o25_pct, stats_conf, o25_exp, overall_confidence),
        over_85_corners=_market(o85c_pct, corner_conf, o85c_exp, overall_confidence),
        over_45_cards=_market(o45k_pct, card_conf, o45k_exp, overall_confidence),
        brain=get_brain_meta(),
    )


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get("/score", response_model=ScoreResponse, summary="Match Score Prediction")
async def score_fixture(
    home: str = Query(..., description="Home team name (full or partial)"),
    away: str = Query(..., description="Away team name (full or partial)"),
) -> ScoreResponse:
    """
    Compute betting-grade probability scores for a fixture.

    **AURORA_BRAIN** operational parameters are loaded from brain files before
    every prediction — thresholds, weights, and baselines are never hardcoded.

    **Model layers:**
    - **Standings prior**: venue win-rate × brain `venue_weight` + form × brain `form_weight`
    - **xG Poisson**: expected goals → win/draw/loss blended by brain `xg_blend_weight`
    - **Live score**: current score × time_weight (up to brain `max_live_score_weight` at 90')
    - **BTTS / Over 2.5**: Poisson on xG or season GPG
    - **Corners / Cards**: pace extrapolated to 90' vs brain baselines

    **Response includes:**
    - `recommended_markets`: markets that pass all brain betting_gates
    - `actionable` per market: whether the brain gates allow acting on it
    - `brain`: version metadata of the brain used for this prediction
    """
    data = await analyze_fixture(home=home, away=away)
    return _score(data)
