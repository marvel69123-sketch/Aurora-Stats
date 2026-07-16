"""
Aurora Live Intelligence Engine — Phase 7.

Ranks live football fixtures (in the processed format from live.py's
_build_live_response) by betting opportunity value and generates
CopilotResponse-compatible payloads with actionable market suggestions.

Opportunity score (0–10) is computed from:
  - Game phase (minute)
  - Score state and goal difference
  - Tactical momentum indicators (who is losing / pushing forward)

Public API
----------
  score_fixture(fx: dict) -> LiveFixtureScore
  top_live_opportunities(fixtures: list[dict]) -> list[LiveFixtureScore]
  build_live_payload(fixtures: list[dict], brain_meta: dict) -> dict
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass
class LiveFixtureScore:
    fixture_id:        int
    home:              str
    away:              str
    league:            str
    minute:            int | None
    score_home:        int
    score_away:        int
    opportunity_score: float          # 0.0 – 10.0
    momentum:          str            # "home_pressing"|"away_pressing"|"balanced"|"game_over"
    best_market:       str
    rationale:         str
    risk:              str            # "Low"|"Medium"|"High"
    suggested_markets: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_int(val) -> int:
    try:
        return int(val or 0)
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------------------------
# Scoring — uses the processed format produced by live.py _build_live_response
# ---------------------------------------------------------------------------

def score_fixture(fx: dict) -> LiveFixtureScore:
    """
    Score a single live fixture (processed format from _build_live_response).

    Expected keys:
      fx["fixture_id"]        int
      fx["status"]["minute"]  int | None
      fx["league"]["name"]    str
      fx["home"]["name"]      str
      fx["home"]["score"]     int | None
      fx["away"]["name"]      str
      fx["away"]["score"]     int | None
    """
    fid    = fx.get("fixture_id", 0)
    home   = (fx.get("home") or {}).get("name", "Home")
    away   = (fx.get("away") or {}).get("name", "Away")
    league = (fx.get("league") or {}).get("name", "")
    minute = _safe_int((fx.get("status") or {}).get("minute"))
    score_h = _safe_int((fx.get("home") or {}).get("score", 0))
    score_a = _safe_int((fx.get("away") or {}).get("score", 0))
    total_goals = score_h + score_a
    goal_diff   = abs(score_h - score_a)

    # ── Opportunity score ──────────────────────────────────────────────────
    opp = 5.0

    # Game phase
    if 60 <= minute <= 75:
        opp += 2.5
    elif 75 < minute <= 85:
        opp += 2.0
    elif 85 < minute <= 97:
        opp += 1.5
    elif minute < 30:
        opp -= 1.5
    elif 30 <= minute < 60:
        opp += 0.5

    # Score state
    if total_goals == 0:
        if minute >= 60:
            opp += 2.0
        elif minute >= 45:
            opp += 1.0
    elif goal_diff == 0:
        opp += 1.5 if minute >= 60 else 0.5
    elif goal_diff == 1:
        opp += 1.5 if minute >= 60 else 0.5
    elif goal_diff == 2:
        opp -= 0.5
    elif goal_diff >= 3:
        opp -= 3.0

    if total_goals >= 4:
        opp -= 1.5

    opp = max(0.0, min(10.0, opp))

    # ── Momentum ───────────────────────────────────────────────────────────
    if goal_diff >= 2:
        momentum = "game_over"
    elif score_h > score_a:
        momentum = "away_pressing"
    elif score_a > score_h:
        momentum = "home_pressing"
    else:
        momentum = "balanced"

    # ── Market suggestions (same-fixture labels only — no foreign team names) ─
    markets: list[str] = []
    best_market = "Próximo Gol"
    rat_parts: list[str] = []

    if total_goals == 0 and minute >= 85:
        markets = ["Under 0.5 Gols", "Empate", "Próximo Gol"]
        best_market = "Under 0.5 Gols"
        rat_parts.append(f"0-0 ao minuto {minute} — chance de 0x0 final aumenta")
    elif total_goals == 0 and minute >= 60:
        markets = ["Próximo Gol", "Over 0.5 Gols", "Ambos Marcam"]
        best_market = "Over 0.5 Gols"
        rat_parts.append(f"0-0 ao minuto {minute} — alta pressão por gol de abertura")
    elif goal_diff == 1 and minute >= 65:
        losing = away if score_h > score_a else home
        markets = ["Escanteios", "Próximo Gol", "Cartões"]
        best_market = "Escanteios"
        rat_parts.append(f"{losing} precisa empatar — pressão intensa com cruzamentos")
    elif goal_diff == 0 and total_goals >= 1 and minute >= 60:
        markets = ["Próximo Gol", "Over 2.5 Gols", "Ambos Marcam"]
        best_market = "Próximo Gol"
        rat_parts.append(f"Empate {score_h}x{score_a} ao min {minute} — ambos buscam vitória")
    elif total_goals >= 3:
        markets = ["Escanteios", "Cartões"]
        best_market = "Escanteios"
        rat_parts.append(f"Partida de {total_goals} gols — espaço e transições frequentes")
    else:
        markets = ["Próximo Gol", "Escanteios", "Ambos Marcam"]
        best_market = "Próximo Gol"
        rat_parts.append(f"Jogo {score_h}x{score_a} ao minuto {minute}")

    if league:
        rat_parts.append(f"Liga: {league}")

    rationale = " · ".join(rat_parts)

    # ── Risk ───────────────────────────────────────────────────────────────
    risk = "Medium" if opp >= 5.0 else "High"

    return LiveFixtureScore(
        fixture_id        = fid,
        home              = home,
        away              = away,
        league            = league,
        minute            = minute,
        score_home        = score_h,
        score_away        = score_a,
        opportunity_score = round(opp, 1),
        momentum          = momentum,
        best_market       = best_market,
        rationale         = rationale,
        risk              = risk,
        suggested_markets = markets,
    )


def top_live_opportunities(fixtures: list[dict]) -> list[LiveFixtureScore]:
    """Score all fixtures, return sorted best-first."""
    if not fixtures:
        return []
    return sorted(
        (score_fixture(fx) for fx in fixtures),
        key=lambda s: s.opportunity_score,
        reverse=True,
    )


# ---------------------------------------------------------------------------
# Payload builder
# ---------------------------------------------------------------------------

_MOMENTUM_PT: dict[str, str] = {
    "home_pressing":  "Casa pressionando",
    "away_pressing":  "Visitante pressionando",
    "balanced":       "Jogo equilibrado",
    "game_over":      "Resultado praticamente decidido",
}


def build_live_payload(fixtures: list[dict], brain_meta: dict) -> dict:
    """Build a CopilotResponse-compatible payload from processed live fixtures."""
    if not fixtures:
        return {
            "intent": "live_opportunities",
            "entities": {"live_count": 0},
            "match": None, "status": "Live", "is_live": True, "minute": None,
            "executive_summary": (
                "Nenhuma partida ao vivo no momento. "
                "Volte mais tarde ou analise uma partida futura."
            ),
            "best_markets": [],
            "confidence": {
                "score": 0.0, "label": "insufficient",
                "explanation": "Sem partidas ao vivo.",
                "data_sources": ["Feed ao vivo API-Football"],
            },
            "risk": {"level": "Unknown", "flags": [], "invalidation_conditions": []},
            "bankroll_recommendation": {
                "recommended_stake_pct": 0.0, "method": "quarter-Kelly",
                "examples": {}, "no_bet": True,
                "reasoning": "Sem oportunidades ao vivo.",
            },
            "positive_factors": [], "negative_factors": [],
            "historical_references": [], "knowledge_notes": [],
            "final_recommendation": (
                "Nenhuma oportunidade ao vivo agora. "
                "Analise uma partida futura: \"Analisar [Time A] x [Time B]\""
            ),
            "aurora_version": "Copilot v1.0",
            "brain": brain_meta,
        }

    ranked = top_live_opportunities(fixtures)
    count = len(fixtures)
    best = ranked[0]

    # CRITICAL: best_markets must belong ONLY to the same fixture as MatchHeader.
    # Never pack top-5 different fixtures into best_markets (context leak).
    markets: list[dict] = []
    for i, mkt_name in enumerate((best.suggested_markets or [best.best_market])[:5], 1):
        label = (mkt_name or "").strip()
        if not label:
            continue
        if re.search(r"an[aá]lise\s+completa|analisar\b", label, re.I):
            continue
        prob = round(min(78, 42 + best.opportunity_score * 3.6), 1)
        ev = round((best.opportunity_score - 5.0) * 2.0, 1)
        markets.append({
            "rank": i,
            "market": label,
            "probability": prob,
            "expected_value": ev,
            "confidence": round(best.opportunity_score, 1),
            "risk": best.risk,
            "rationale": best.rationale,
        })
    if not markets and best.best_market:
        markets.append({
            "rank": 1,
            "market": best.best_market,
            "probability": round(min(78, 42 + best.opportunity_score * 3.6), 1),
            "expected_value": round((best.opportunity_score - 5.0) * 2.0, 1),
            "confidence": round(best.opportunity_score, 1),
            "risk": best.risk,
            "rationale": best.rationale,
        })

    high_opp = [s for s in ranked if s.opportunity_score >= 6.5]
    mom_pt = _MOMENTUM_PT.get(best.momentum, "")
    summary = (
        f"**📊 Cenário atual**\n\n"
        f"Entre as {count} partida{'s' if count != 1 else ''} monitorada{'s' if count != 1 else ''}, "
        f"o confronto **{best.home} x {best.away}**"
        + (f" ({best.league})" if best.league else "")
        + f" apresenta o contexto mais interessante neste momento"
        + (f" — minuto {best.minute}" if best.minute is not None else "")
        + f" ({best.score_home}–{best.score_away}).\n\n"
    )
    if best.momentum == "away_pressing":
        summary += (
            "O visitante aumenta a pressão em busca do empate, "
            "favorecendo mercados relacionados a escanteios e próximo gol."
        )
    elif best.momentum == "home_pressing":
        summary += (
            "O mandante aumenta a pressão, "
            "abrindo espaço para mercados de escanteios e próximo gol."
        )
    elif best.momentum == "balanced":
        summary += (
            "O confronto está equilibrado, com ambas as equipes criando oportunidades."
        )
    elif best.momentum == "game_over":
        summary += (
            "O placar já aponta para um desfecho mais definido — "
            "vale cautela antes de entrar em mercados agressivos."
        )
    else:
        summary += f"{mom_pt}." if mom_pt else "Acompanhe a evolução do ritmo da partida."

    if high_opp and best.opportunity_score >= 6.5:
        summary += (
            f"\n\nMercado em evidência: **{best.best_market}**."
        )

    pos = [
        f"{s.home} x {s.away}: contexto favorável no minuto {s.minute or '?'}"
        for s in ranked[:3] if s.opportunity_score >= 6.0
    ]
    neg = [
        f"{s.home} x {s.away}: cenário menos atrativo neste momento"
        for s in ranked[:3] if s.opportunity_score < 6.0
    ]

    conf_score = round(best.opportunity_score, 1)
    conf_label = "strong" if conf_score >= 8 else "moderate" if conf_score >= 6 else "adequate"

    return {
        "intent":   "live_opportunities",
        "entities": {
            "live_count":      count,
            "top_opportunity": f"{best.home} x {best.away}",
            "live_home":       best.home,
            "live_away":       best.away,
        },
        "match":    None, "status": "Live", "is_live": True, "minute": None,
        "executive_summary":  summary,
        "best_markets":       markets,
        "confidence": {
            "score":        conf_score,
            "label":        conf_label,
            "explanation":  (
                f"Score baseado em fase do jogo, placar e momentum. "
                f"{count} partida{'s' if count != 1 else ''} avaliada{'s' if count != 1 else ''}."
            ),
            "data_sources": ["Feed ao vivo API-Football", "Live Intelligence Engine v1.0"],
        },
        "risk": {
            "level": best.risk,
            "flags": [
                "Apostas ao vivo têm odds em constante atualização",
                "Confirme sempre as odds antes de enviar a aposta",
            ],
            "invalidation_conditions": [
                "Gol marcado antes de confirmar a aposta",
                "Mudança de placar ou cartão vermelho",
            ],
        },
        "bankroll_recommendation": {
            "recommended_stake_pct": 0.0,
            "method":                "quarter-Kelly",
            "examples":              {},
            "no_bet":                True,
            "reasoning": f"Analise a partida para stake: \"Analisar {best.home} x {best.away}\".",
        },
        "positive_factors":      pos,
        "negative_factors":      neg,
        "historical_references": [],
        "knowledge_notes": [
            "Odds ao vivo mudam rapidamente — confirme antes de apostar.",
            "A leitura considera fase do jogo, placar e ritmo da partida.",
        ],
        "final_recommendation": (
            f"Neste momento, o cenário mais interessante é **{best.home} x {best.away}**, "
            f"com foco em **{best.best_market}**. "
            f"Se quiser aprofundar, peça a análise completa desse confronto."
        ),
        "aurora_version": "Copilot v1.0",
        "brain":          brain_meta,
    }
