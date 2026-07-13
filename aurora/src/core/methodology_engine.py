"""
Methodology Engine — three-layer Poisson probability model.

Layer 1 · Pre-match prior     : venue win-rate × brain venue_weight + form × form_weight
Layer 2 · xG Poisson blend    : expected-goals Poisson weighted by brain xg_blend_weight
Layer 3 · Live score adjust   : current score weighted by time elapsed (max: max_live_score_weight)

All numeric constants come from brain config — never hardcoded here.

Public API
----------
  run(data, cfg) -> MethodologyResult
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from src.brain import BrainConfig

# ---------------------------------------------------------------------------
# Match-status sets
# ---------------------------------------------------------------------------

LIVE_STATUSES     = {"1H", "2H", "ET", "P", "BT", "HT", "SUSP", "INT", "LIVE"}
FINISHED_STATUSES = {"FT", "AET", "PEN", "AWD", "WO"}

# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class MethodologyResult:
    """All computed probabilities and raw signals from the mathematical model."""

    # ── Context flags ──────────────────────────────────────────────────────
    is_live:       bool
    is_finished:   bool
    minute:        int
    has_score:     bool
    has_stats:     bool
    has_xg:        bool
    has_standings: bool
    has_events:    bool

    # ── Match state ────────────────────────────────────────────────────────
    h_goals:     int
    a_goals:     int
    total_goals: int

    # ── Scoring rates ──────────────────────────────────────────────────────
    h_xg_val: float   # xG if available, else 0
    a_xg_val: float
    h_gpg:    float   # goals per game (from standings)
    a_gpg:    float

    # ── Physical stats ─────────────────────────────────────────────────────
    total_corners: int
    total_cards:   int
    total_fouls:   int

    # ── Match result probabilities (0–1, normalized) ───────────────────────
    ph: float   # P(home win)
    pd: float   # P(draw)
    pa: float   # P(away win)

    # ── Market probabilities (0–100 scale) ────────────────────────────────
    btts_pct:  float
    o25_pct:   float
    o85c_pct:  float
    o45k_pct:  float


# ---------------------------------------------------------------------------
# Math primitives
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


def _poisson_result(
    h_lam: float, a_lam: float, max_goals: int
) -> tuple[float, float, float]:
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
    won    = _i(rec.get("won"), 0)
    if played > 0:
        return won / played
    p = _i(standing.get("played"), 0)
    w = _i(standing.get("won"), 0)
    return w / p if p > 0 else 0.33


def _goals_per_game(standing: dict | None, default: float) -> float:
    if not standing:
        return default
    gf = _f(standing.get("goals_for"), 0.0)
    p  = _f(standing.get("played"), 0.0)
    return gf / p if p > 0 else default


# ---------------------------------------------------------------------------
# Engine entry point
# ---------------------------------------------------------------------------


def run(data: dict, cfg: BrainConfig) -> MethodologyResult:  # noqa: C901
    """
    Apply the three-layer probability model to raw fixture data.

    Parameters
    ----------
    data : dict returned by analyze_fixture()
    cfg  : BrainConfig loaded from brain/version.json
    """
    bl = cfg.baselines
    wt = cfg.weights

    fx     = data["fixture"]
    sc     = data["score"]
    hs     = data["statistics"]["home"]
    as_    = data["statistics"]["away"]
    events = data["events"]
    sh     = data["standings"]["home"]
    sa     = data["standings"]["away"]

    status_short = fx["status"]["short"]
    is_finished  = status_short in FINISHED_STATUSES
    is_live      = status_short in LIVE_STATUSES
    minute       = _i(fx["status"]["minute"], 0)

    h_goals     = _i(sc["current"]["home"], 0)
    a_goals     = _i(sc["current"]["away"], 0)
    total_goals = h_goals + a_goals
    has_score   = sc["current"]["home"] is not None

    has_stats     = any(hs.get(k) is not None for k in ("shots_total", "possession", "corners"))
    has_xg        = hs.get("xg") is not None and as_.get("xg") is not None
    has_standings = sh is not None and sa is not None
    has_events    = bool(events)

    h_xg_val = _f(hs.get("xg"), 0.0)
    a_xg_val = _f(as_.get("xg"), 0.0)
    h_gpg    = _goals_per_game(sh, bl.default_home_gpg)
    a_gpg    = _goals_per_game(sa, bl.default_away_gpg)

    # ── Layer 1: Standings prior ────────────────────────────────────────────
    vw = wt.venue_weight_in_prior
    fw = wt.form_weight_in_prior
    h_prior = _venue_win_rate(sh, "home") * vw + _form_score(sh.get("form") if sh else None) * fw
    a_prior = _venue_win_rate(sa, "away") * vw + _form_score(sa.get("form") if sa else None) * fw
    d_prior = max(bl.draw_base_rate, 1.0 - h_prior - a_prior)
    ph, pd, pa = _normalize(h_prior, d_prior, a_prior)

    # ── Layer 2: xG Poisson blend ───────────────────────────────────────────
    if has_xg and (h_xg_val + a_xg_val) > 0:
        xg_h, xg_d, xg_a = _poisson_result(h_xg_val, a_xg_val, bl.max_goals_poisson)
        pw  = 1.0 - wt.xg_blend_weight
        ph  = ph * pw + xg_h * wt.xg_blend_weight
        pd  = pd * pw + xg_d * wt.xg_blend_weight
        pa  = pa * pw + xg_a * wt.xg_blend_weight
        ph, pd, pa = _normalize(ph, pd, pa)

    # ── Layer 3: Live / finished score adjustment ───────────────────────────
    if (is_live or is_finished) and has_score:
        max_tw = wt.max_live_score_weight
        time_w = max_tw if is_finished else min(max_tw, minute / 90.0 * max_tw)

        if h_goals > a_goals:
            sh_h, sh_d, sh_a = 0.82, 0.11, 0.07
        elif a_goals > h_goals:
            sh_h, sh_d, sh_a = 0.07, 0.11, 0.82
        else:
            base_d = 0.36 + total_goals * 0.04
            half   = (1.0 - base_d) / 2.0
            sh_h, sh_d, sh_a = _normalize(half, base_d, half)

        pw  = 1.0 - time_w
        ph  = ph * pw + sh_h * time_w
        pd  = pd * pw + sh_d * time_w
        pa  = pa * pw + sh_a * time_w
        ph, pd, pa = _normalize(ph, pd, pa)

    # ── Market: BTTS ────────────────────────────────────────────────────────
    if has_xg and (h_xg_val + a_xg_val) > 0:
        btts_base = (1.0 - _poisson(h_xg_val, 0)) * (1.0 - _poisson(a_xg_val, 0)) * 100.0
    else:
        btts_base = (1.0 - _poisson(h_gpg, 0)) * (1.0 - _poisson(a_gpg, 0)) * 100.0

    if (is_live or is_finished) and has_score:
        if h_goals >= 1 and a_goals >= 1:
            btts_pct = 100.0
        elif is_finished:
            btts_pct = 0.0
        else:
            rem = max(0, 90 - minute)
            if h_goals >= 1:
                btts_pct = (1.0 - _poisson((a_xg_val if has_xg else a_gpg) * rem / 90.0, 0)) * 100.0
            elif a_goals >= 1:
                btts_pct = (1.0 - _poisson((h_xg_val if has_xg else h_gpg) * rem / 90.0, 0)) * 100.0
            else:
                lh = (h_xg_val if has_xg else h_gpg) * rem / 90.0
                la = (a_xg_val if has_xg else a_gpg) * rem / 90.0
                btts_pct = (1.0 - _poisson(lh, 0)) * (1.0 - _poisson(la, 0)) * 100.0
    else:
        btts_pct = btts_base
    btts_pct = min(100.0, max(0.0, btts_pct))

    # ── Market: Over 2.5 goals ──────────────────────────────────────────────
    total_lam = (h_xg_val + a_xg_val) if (has_xg and h_xg_val + a_xg_val > 0) else (h_gpg + a_gpg)
    if (is_live or is_finished) and has_score:
        if total_goals >= 3:
            o25_pct = 100.0
        elif is_finished:
            o25_pct = 0.0
        else:
            rem    = max(0, 90 - minute)
            scaled = total_lam * rem / 90.0
            needed = max(0, 3 - total_goals)
            o25_pct = (_poisson_over(scaled, needed - 1) * 100.0) if needed > 0 else 100.0
    else:
        o25_pct = _poisson_over(total_lam, 2.5) * 100.0
    o25_pct = min(100.0, max(0.0, o25_pct))

    # ── Market: Over 8.5 corners ────────────────────────────────────────────
    total_corners = _i(hs.get("corners"), 0) + _i(as_.get("corners"), 0)
    avg_c90       = bl.avg_corners_per_90
    if (is_live or is_finished) and has_score:
        if total_corners > 8:
            o85c_pct = 100.0
        elif is_finished:
            o85c_pct = 0.0
        else:
            rem    = max(0, 90 - minute)
            rate   = (total_corners / minute) if minute > 0 else (avg_c90 / 90.0)
            lam    = rate * rem
            needed = max(0, 9 - total_corners)
            o85c_pct = (_poisson_over(lam, needed - 1) * 100.0) if needed > 0 else 100.0
    else:
        o85c_pct = _poisson_over(avg_c90, 8.5) * 100.0
    o85c_pct = min(100.0, max(0.0, o85c_pct))

    # ── Market: Over 4.5 cards ──────────────────────────────────────────────
    total_cards = (
        _i(hs.get("yellow_cards"), 0) + _i(hs.get("red_cards"), 0)
        + _i(as_.get("yellow_cards"), 0) + _i(as_.get("red_cards"), 0)
    )
    total_fouls = _i(hs.get("fouls"), 0) + _i(as_.get("fouls"), 0)
    avg_k90     = bl.avg_cards_per_90
    if (is_live or is_finished) and has_score:
        if total_cards > 4:
            o45k_pct = 100.0
        elif is_finished:
            o45k_pct = 0.0
        else:
            rem      = max(0, 90 - minute)
            raw_rate = (total_cards / minute) if minute > 0 else (avg_k90 / 90.0)
            foul_r   = (total_fouls / minute * 0.15) if minute > 0 else 0.0
            lam      = max(raw_rate, foul_r) * rem
            needed   = max(0, 5 - total_cards)
            o45k_pct = (_poisson_over(lam, needed - 1) * 100.0) if needed > 0 else 100.0
    else:
        o45k_pct = _poisson_over(avg_k90, 4.5) * 100.0
    o45k_pct = min(100.0, max(0.0, o45k_pct))

    return MethodologyResult(
        is_live=is_live, is_finished=is_finished, minute=minute,
        has_score=has_score, has_stats=has_stats, has_xg=has_xg,
        has_standings=has_standings, has_events=has_events,
        h_goals=h_goals, a_goals=a_goals, total_goals=total_goals,
        h_xg_val=h_xg_val, a_xg_val=a_xg_val,
        h_gpg=h_gpg, a_gpg=a_gpg,
        total_corners=total_corners, total_cards=total_cards, total_fouls=total_fouls,
        ph=ph, pd=pd, pa=pa,
        btts_pct=btts_pct, o25_pct=o25_pct,
        o85c_pct=o85c_pct, o45k_pct=o45k_pct,
    )
