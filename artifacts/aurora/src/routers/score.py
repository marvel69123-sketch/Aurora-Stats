"""
/aurora/score — Betting-grade probability scores for a fixture.

Pulls all data from analyze_fixture() then runs a multi-signal model:
  • Pre-match prior  — standings rank, venue win-rate, recent form
  • xG Poisson model — Poisson win/draw/loss from expected goals
  • Live adjustment  — current score weighted by time elapsed
  • Market models    — BTTS, Over 2.5, Over 8.5 corners, Over 4.5 cards
"""
from __future__ import annotations

import math

from fastapi import APIRouter, Query
from pydantic import BaseModel

from src.routers.analyze import analyze_fixture

router = APIRouter()

# ---------------------------------------------------------------------------
# Status sets
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
    summary: str

    home_win: MarketScore
    draw: MarketScore
    away_win: MarketScore
    btts: MarketScore
    over_25_goals: MarketScore
    over_85_corners: MarketScore
    over_45_cards: MarketScore


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
    cutoff = int(threshold + 0.5)          # e.g. 2.5 → 3, 8.5 → 9
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
    """Normalised form 0–1 (1 = all wins in last n)."""
    if not form:
        return 0.5
    tail = list(form[-n:])
    if not tail:
        return 0.5
    pts = sum(3 if c == "W" else 1 if c == "D" else 0 for c in tail)
    return pts / (3 * len(tail))


def _venue_win_rate(standing: dict | None, venue: str) -> float:
    """Win rate at home or away; falls back to overall then to 0.33."""
    if not standing:
        return 0.33
    rec = (standing.get(f"{venue}_record") or {})
    played = _i(rec.get("played"), 0)
    won = _i(rec.get("won"), 0)
    if played > 0:
        return won / played
    # overall fallback
    p = _i(standing.get("played"), 0)
    w = _i(standing.get("won"), 0)
    return w / p if p > 0 else 0.33


def _goals_per_game(standing: dict | None, default: float = 1.1) -> float:
    if not standing:
        return default
    gf = _f(standing.get("goals_for"), 0.0)
    p = _f(standing.get("played"), 0.0)
    return gf / p if p > 0 else default


# ---------------------------------------------------------------------------
# Poisson match-result model
# ---------------------------------------------------------------------------


def _poisson_result(h_lam: float, a_lam: float, max_goals: int = 7) -> tuple[float, float, float]:
    """Return (P_home_win, P_draw, P_away_win) via Poisson model."""
    h_win = draw = a_win = 0.0
    for hg in range(max_goals + 1):
        ph = _poisson(h_lam, hg)
        for ag in range(max_goals + 1):
            pa = _poisson(a_lam, ag)
            p = ph * pa
            if hg > ag:
                h_win += p
            elif hg == ag:
                draw += p
            else:
                a_win += p
    return h_win, draw, a_win


# ---------------------------------------------------------------------------
# Risk / market helpers
# ---------------------------------------------------------------------------


def _risk(prob: float, confidence: float) -> str:
    if confidence >= 7.0 and prob >= 68.0:
        return "Low"
    if confidence >= 5.0 and prob >= 52.0:
        return "Medium"
    return "High"


def _market(prob: float, conf: float, explanation: str) -> MarketScore:
    return MarketScore(
        probability=round(min(100.0, max(0.0, prob)), 1),
        confidence=round(min(10.0, max(0.0, conf)), 1),
        risk=_risk(prob, conf),
        explanation=explanation,
    )


# ---------------------------------------------------------------------------
# Core scoring engine
# ---------------------------------------------------------------------------


def _score(data: dict) -> ScoreResponse:  # noqa: C901
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

    # ── Data-richness confidence ─────────────────────────────────────────────
    signals = [has_stats, has_xg, has_standings, has_events, is_live or is_finished]
    base_conf = 3.0 + sum(signals) * 1.3
    if not (is_live or is_finished):
        base_conf = min(base_conf, 6.5)
    overall_confidence = min(10.0, base_conf)

    # ── Pre-match prior from standings ───────────────────────────────────────
    h_venue_wr = _venue_win_rate(sh, "home")
    a_venue_wr = _venue_win_rate(sa, "away")
    h_form = _form_score(sh.get("form") if sh else None)
    a_form = _form_score(sa.get("form") if sa else None)

    h_prior = h_venue_wr * 0.6 + h_form * 0.4
    a_prior = a_venue_wr * 0.6 + a_form * 0.4
    d_prior = max(0.12, 1.0 - h_prior - a_prior)
    ph, pd, pa = _normalize(h_prior, d_prior, a_prior)

    # ── xG Poisson adjustment ────────────────────────────────────────────────
    h_xg_val = _f(hs.get("xg"), 0.0)
    a_xg_val = _f(as_.get("xg"), 0.0)

    if has_xg and (h_xg_val + a_xg_val) > 0:
        xg_h, xg_d, xg_a = _poisson_result(h_xg_val, a_xg_val)
        ph = ph * 0.4 + xg_h * 0.6
        pd = pd * 0.4 + xg_d * 0.6
        pa = pa * 0.4 + xg_a * 0.6
        ph, pd, pa = _normalize(ph, pd, pa)

    # ── Live / finished score adjustment ────────────────────────────────────
    if (is_live or is_finished) and has_score:
        time_w = 1.0 if is_finished else min(0.88, minute / 90 * 0.88)

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

    ph_pct = ph * 100.0
    pd_pct = pd * 100.0
    pa_pct = pa * 100.0

    # ── BTTS ──────────────────────────────────────────────────────────────────
    h_gpg = _goals_per_game(sh, 1.2)
    a_gpg = _goals_per_game(sa, 0.9)

    # Poisson probability each team scores ≥1
    if has_xg and (h_xg_val + a_xg_val) > 0:
        h_score_p = 1.0 - _poisson(h_xg_val, 0)
        a_score_p = 1.0 - _poisson(a_xg_val, 0)
        btts_base = h_score_p * a_score_p * 100.0
    else:
        h_score_p = 1.0 - _poisson(h_gpg, 0)
        a_score_p = 1.0 - _poisson(a_gpg, 0)
        btts_base = h_score_p * a_score_p * 100.0

    if (is_live or is_finished) and has_score:
        both_scored = h_goals >= 1 and a_goals >= 1
        if both_scored:
            btts_pct = 100.0
        elif is_finished:
            btts_pct = 0.0
        else:
            remaining = max(0, 90 - minute)
            if h_goals >= 1:          # only away needs to score
                lam = (a_xg_val if has_xg else a_gpg) * remaining / 90.0
                btts_pct = (1.0 - _poisson(lam, 0)) * 100.0
            elif a_goals >= 1:        # only home needs to score
                lam = (h_xg_val if has_xg else h_gpg) * remaining / 90.0
                btts_pct = (1.0 - _poisson(lam, 0)) * 100.0
            else:                     # neither has scored yet
                lh = (h_xg_val if has_xg else h_gpg) * remaining / 90.0
                la = (a_xg_val if has_xg else a_gpg) * remaining / 90.0
                btts_pct = (1.0 - _poisson(lh, 0)) * (1.0 - _poisson(la, 0)) * 100.0
    else:
        btts_pct = btts_base

    btts_pct = min(100.0, max(0.0, btts_pct))

    # ── Over 2.5 goals ────────────────────────────────────────────────────────
    if has_xg and (h_xg_val + a_xg_val) > 0:
        total_lam = h_xg_val + a_xg_val
    else:
        total_lam = h_gpg + a_gpg

    if (is_live or is_finished) and has_score:
        if total_goals >= 3:
            o25_pct = 100.0
        elif is_finished:
            o25_pct = 0.0
        else:
            remaining = max(0, 90 - minute)
            scaled_lam = total_lam * remaining / 90.0
            needed = max(0, 3 - total_goals)
            o25_pct = _poisson_over(scaled_lam, needed - 1) * 100.0 if needed > 0 else 100.0
    else:
        o25_pct = _poisson_over(total_lam, 2.5) * 100.0

    o25_pct = min(100.0, max(0.0, o25_pct))

    # ── Over 8.5 corners ─────────────────────────────────────────────────────
    h_cor = _i(hs.get("corners"), 0)
    a_cor = _i(as_.get("corners"), 0)
    total_cor = h_cor + a_cor
    avg_corners_90 = 10.5          # league baseline

    if (is_live or is_finished) and has_score:
        if total_cor > 8:
            o85c_pct = 100.0
        elif is_finished:
            o85c_pct = 0.0
        else:
            remaining = max(0, 90 - minute)
            rate = (total_cor / minute) if minute > 0 else (avg_corners_90 / 90.0)
            lam = rate * remaining
            needed = max(0, 9 - total_cor)
            o85c_pct = _poisson_over(lam, needed - 1) * 100.0 if needed > 0 else 100.0
    else:
        o85c_pct = _poisson_over(avg_corners_90, 8.5) * 100.0

    o85c_pct = min(100.0, max(0.0, o85c_pct))

    # ── Over 4.5 cards ────────────────────────────────────────────────────────
    h_yel = _i(hs.get("yellow_cards"), 0)
    h_red = _i(hs.get("red_cards"), 0)
    a_yel = _i(as_.get("yellow_cards"), 0)
    a_red = _i(as_.get("red_cards"), 0)
    total_cards = h_yel + h_red + a_yel + a_red
    h_fouls = _i(hs.get("fouls"), 0)
    a_fouls = _i(as_.get("fouls"), 0)
    avg_cards_90 = 3.5

    if (is_live or is_finished) and has_score:
        if total_cards > 4:
            o45k_pct = 100.0
        elif is_finished:
            o45k_pct = 0.0
        else:
            remaining = max(0, 90 - minute)
            raw_rate = (total_cards / minute) if minute > 0 else (avg_cards_90 / 90.0)
            foul_rate = ((h_fouls + a_fouls) / minute * 0.15) if minute > 0 else 0.0
            rate = max(raw_rate, foul_rate)
            lam = rate * remaining
            needed = max(0, 5 - total_cards)
            o45k_pct = _poisson_over(lam, needed - 1) * 100.0 if needed > 0 else 100.0
    else:
        o45k_pct = _poisson_over(avg_cards_90, 4.5) * 100.0

    o45k_pct = min(100.0, max(0.0, o45k_pct))

    # ── Best market ───────────────────────────────────────────────────────────
    markets = {
        f"{hn} Win": ph_pct,
        "Draw": pd_pct,
        f"{an} Win": pa_pct,
        "BTTS Yes": btts_pct,
        "Over 2.5 Goals": o25_pct,
        "Over 8.5 Corners": o85c_pct,
        "Over 4.5 Cards": o45k_pct,
    }
    best_market = max(markets, key=lambda k: markets[k])
    best_prob = markets[best_market]

    # ── Overall risk ──────────────────────────────────────────────────────────
    risk_level = _risk(best_prob, overall_confidence)

    # ── Per-market confidence deltas ─────────────────────────────────────────
    # Corner/card models have less data so get capped confidence
    stats_conf = min(10.0, overall_confidence + (0.8 if has_xg else 0.0))
    corner_conf = min(8.0, overall_confidence - 1.0) if (is_live or is_finished) else 4.5
    card_conf = min(8.0, overall_confidence - 1.0) if (is_live or is_finished) else 4.0

    # ── Explanations ─────────────────────────────────────────────────────────
    # Home win
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

    # Draw
    xg_gap = abs(h_xg_val - a_xg_val)
    if has_xg:
        if xg_gap < 0.25:
            draw_exp = f"xG gap only {xg_gap:.2f} — closely contested, draw very plausible."
        else:
            draw_exp = f"xG gap {xg_gap:.2f} reduces draw probability."
    else:
        draw_exp = "Estimated from standings form — draw rate typical for this tier."

    # Away win
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

    # BTTS
    btts_exp = f"{hn} {h_gpg:.2f} G/game, {an} {a_gpg:.2f} G/game (season avg)."
    if (is_live or is_finished) and has_score:
        if h_goals >= 1 and a_goals >= 1:
            btts_exp += " Both have already scored — BTTS confirmed."
        elif is_finished:
            btts_exp += f" FT {h_goals}–{a_goals}: not both scored."
        else:
            btts_exp += f" Score {h_goals}–{a_goals} at {minute}'."

    # Over 2.5
    if has_xg:
        o25_exp = (
            f"Combined xG {h_xg_val + a_xg_val:.2f}. "
            + ("High-scoring pace." if (h_xg_val + a_xg_val) > 2.5 else "Low-scoring pace.")
        )
    else:
        o25_exp = f"Season scoring rates: {h_gpg:.2f} + {a_gpg:.2f} = {h_gpg + a_gpg:.2f} G/game."
    if (is_live or is_finished) and has_score:
        o25_exp += f" {total_goals} goal{'s' if total_goals != 1 else ''} scored so far."

    # Over 8.5 corners
    if (is_live or is_finished) and has_score and minute > 0:
        pace = total_cor / minute * 90.0
        o85c_exp = f"{total_cor} corners in {minute}' → pace {pace:.1f}/90."
    else:
        o85c_exp = f"Pre-match baseline of ~{avg_corners_90} corners/game applied."

    # Over 4.5 cards
    if (is_live or is_finished) and has_score and minute > 0:
        o45k_exp = (
            f"{total_cards} card{'s' if total_cards != 1 else ''} in {minute}' "
            f"({h_fouls + a_fouls} total fouls)."
        )
    else:
        o45k_exp = f"Pre-match baseline of ~{avg_cards_90} cards/game applied."

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
        summary=summary,
        home_win=_market(ph_pct, overall_confidence, hw_exp),
        draw=_market(pd_pct, overall_confidence * 0.85, draw_exp),
        away_win=_market(pa_pct, overall_confidence, aw_exp),
        btts=_market(btts_pct, stats_conf, btts_exp),
        over_25_goals=_market(o25_pct, stats_conf, o25_exp),
        over_85_corners=_market(o85c_pct, corner_conf, o85c_exp),
        over_45_cards=_market(o45k_pct, card_conf, o45k_exp),
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

    Uses a multi-signal model:
    - **Standings prior**: venue win-rate + recent form (last 5)
    - **xG Poisson model**: expected goals → win/draw/loss via Poisson distribution
    - **Live adjustment**: current score weighted by time elapsed (0 → 88% at 90')
    - **BTTS**: Poisson scoring probability for each team, confirmed by live goals
    - **Over 2.5 goals**: Poisson on combined xG / season averages
    - **Over 8.5 corners**: current pace extrapolated to 90'
    - **Over 4.5 cards**: current card rate + foul intensity

    Returns probabilities (0–100), per-market confidence (0–10) and risk,
    plus overall confidence, best market, and risk level.
    """
    data = await analyze_fixture(home=home, away=away)
    return _score(data)
