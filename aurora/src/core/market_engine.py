"""
Market Engine — assembles, explains, and ranks all seven betting markets.

Takes raw probabilities from the Methodology Engine and confidence scores
from the Confidence Engine. Produces fully scored MarketScore objects with
explanations, then ranks them and identifies the best / recommended markets.

Markets covered:
  home_win, draw, away_win, btts, over_25_goals, over_85_corners, over_45_cards

Public API
----------
  run(hn, an, data, methodology, confidence, cfg) -> MarketResult
"""
from __future__ import annotations

from dataclasses import dataclass, field

from src.brain import BrainConfig
from src.core.confidence_engine import ConfidenceResult
from src.core.methodology_engine import MethodologyResult


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class MarketScore:
    key:         str    # snake_case identifier
    label:       str    # human-readable label (may include team name)
    probability: float  # 0–100
    confidence:  float  # 0–10
    risk:        str    # Low | Medium | High
    actionable:  bool   # passes all brain betting gates
    explanation: str


@dataclass
class MarketResult:
    markets:     dict[str, MarketScore]   # keyed by snake_case key
    ranked:      list[MarketScore]        # all 7, sorted by probability desc
    best:        MarketScore              # highest probability market
    recommended: list[MarketScore]        # actionable markets only


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return round(min(hi, max(lo, v)), 1)


def _clamp_conf(v: float) -> float:
    return round(min(10.0, max(0.0, v)), 1)


def _build_explanations(
    hn: str,
    an: str,
    data: dict,
    m: MethodologyResult,
    cfg: BrainConfig,
) -> dict[str, str]:
    """Generate one plain-English explanation sentence per market."""
    sh = data["standings"]["home"]
    sa = data["standings"]["away"]

    def _i(val, d=0):
        try: return int(val)
        except Exception: return d

    expl: dict[str, str] = {}

    # home_win ────────────────────────────────────────────────────────────────
    if sh and sh.get("home_record"):
        hr = sh["home_record"]
        expl["home_win"] = (
            f"{hn} win {_i(hr.get('won'))}/{_i(hr.get('played'))} at home this season "
            f"(form: {(sh.get('form') or '')[-5:] or 'N/A'})."
        )
    else:
        expl["home_win"] = f"{hn} home advantage applied; no standings data."
    if m.has_xg:
        expl["home_win"] += f" xG: {m.h_xg_val:.2f}–{m.a_xg_val:.2f}."

    # draw ────────────────────────────────────────────────────────────────────
    xg_gap = abs(m.h_xg_val - m.a_xg_val)
    if m.has_xg:
        expl["draw"] = (
            f"xG gap only {xg_gap:.2f} — closely contested, draw very plausible."
            if xg_gap < 0.25
            else f"xG gap {xg_gap:.2f} reduces draw probability."
        )
    else:
        expl["draw"] = "Estimated from standings form — draw rate typical for this tier."

    # away_win ────────────────────────────────────────────────────────────────
    if sa and sa.get("away_record"):
        ar = sa["away_record"]
        expl["away_win"] = (
            f"{an} win {_i(ar.get('won'))}/{_i(ar.get('played'))} away this season "
            f"(form: {(sa.get('form') or '')[-5:] or 'N/A'})."
        )
    else:
        expl["away_win"] = f"{an} away record applied; no standings data."
    if m.has_xg:
        expl["away_win"] += f" xG: {m.h_xg_val:.2f}–{m.a_xg_val:.2f}."

    # btts ────────────────────────────────────────────────────────────────────
    expl["btts"] = f"{hn} {m.h_gpg:.2f} G/game, {an} {m.a_gpg:.2f} G/game (season avg)."
    if (m.is_live or m.is_finished) and m.has_score:
        if m.h_goals >= 1 and m.a_goals >= 1:
            expl["btts"] += " Both have already scored — BTTS confirmed."
        elif m.is_finished:
            expl["btts"] += f" FT {m.h_goals}–{m.a_goals}: not both scored."
        else:
            expl["btts"] += f" Score {m.h_goals}–{m.a_goals} at {m.minute}'."

    # over_25_goals ───────────────────────────────────────────────────────────
    if m.has_xg:
        total_xg = m.h_xg_val + m.a_xg_val
        pace = "High-scoring pace." if total_xg > 2.5 else "Low-scoring pace."
        expl["over_25_goals"] = f"Combined xG {total_xg:.2f}. {pace}"
    else:
        expl["over_25_goals"] = (
            f"Season scoring rates: {m.h_gpg:.2f} + {m.a_gpg:.2f} = {m.h_gpg + m.a_gpg:.2f} G/game."
        )
    if (m.is_live or m.is_finished) and m.has_score:
        g = m.total_goals
        expl["over_25_goals"] += f" {g} goal{'s' if g != 1 else ''} scored so far."

    # over_85_corners ─────────────────────────────────────────────────────────
    avg_c90 = cfg.baselines.avg_corners_per_90
    if (m.is_live or m.is_finished) and m.has_score and m.minute > 0:
        pace = m.total_corners / m.minute * 90.0
        expl["over_85_corners"] = f"{m.total_corners} corners in {m.minute}' → pace {pace:.1f}/90."
    else:
        expl["over_85_corners"] = f"Pre-match baseline of ~{avg_c90} corners/game applied."

    # over_45_cards ───────────────────────────────────────────────────────────
    avg_k90 = cfg.baselines.avg_cards_per_90
    if (m.is_live or m.is_finished) and m.has_score and m.minute > 0:
        expl["over_45_cards"] = (
            f"{m.total_cards} card{'s' if m.total_cards != 1 else ''} "
            f"in {m.minute}' ({m.total_fouls} total fouls)."
        )
    else:
        expl["over_45_cards"] = f"Pre-match baseline of ~{avg_k90} cards/game applied."

    return expl


# ---------------------------------------------------------------------------
# Engine entry point
# ---------------------------------------------------------------------------


def run(
    hn: str,
    an: str,
    data: dict,
    methodology: MethodologyResult,
    confidence: ConfidenceResult,
    cfg: BrainConfig,
) -> MarketResult:
    """
    Assemble, score, and rank all seven markets.

    Parameters
    ----------
    hn, an       : home and away team names
    data         : raw analyze_fixture() output (for standings lookups)
    methodology  : MethodologyResult
    confidence   : ConfidenceResult
    cfg          : BrainConfig
    """
    m   = methodology
    c   = confidence

    expl = _build_explanations(hn, an, data, m, cfg)

    # Raw probability / confidence pairs per market ─────────────────────────
    specs: list[tuple[str, str, float, float]] = [
        ("home_win",        f"{hn} Win",        m.ph * 100.0,  c.overall),
        ("draw",            "Draw",              m.pd * 100.0,  c.overall * 0.85),
        ("away_win",        f"{an} Win",         m.pa * 100.0,  c.overall),
        ("btts",            "BTTS Yes",          m.btts_pct,    c.stats_conf),
        ("over_25_goals",   "Over 2.5 Goals",    m.o25_pct,     c.stats_conf),
        ("over_85_corners", "Over 8.5 Corners",  m.o85c_pct,    c.corner_conf),
        ("over_45_cards",   "Over 4.5 Cards",    m.o45k_pct,    c.card_conf),
    ]

    markets: dict[str, MarketScore] = {}
    for key, label, prob_raw, conf_raw in specs:
        prob = _clamp(prob_raw)
        conf = _clamp_conf(conf_raw)
        risk = cfg.risk_level(prob, conf)
        markets[key] = MarketScore(
            key=key,
            label=label,
            probability=prob,
            confidence=conf,
            risk=risk,
            actionable=cfg.is_actionable(prob, conf, c.overall),
            explanation=expl.get(key, ""),
        )

    ranked      = sorted(markets.values(), key=lambda ms: ms.probability, reverse=True)
    best        = ranked[0]
    recommended = [ms for ms in ranked if ms.actionable]

    return MarketResult(
        markets=markets,
        ranked=ranked,
        best=best,
        recommended=recommended,
    )
