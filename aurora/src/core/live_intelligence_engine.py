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

    # ── Market suggestions ─────────────────────────────────────────────────
    markets: list[str] = []
    best_market  = f"Analisar {home} x {away}"
    rat_parts: list[str] = []

    if total_goals == 0 and minute >= 85:
        markets    = ["Under 0.5 Gols", "Empate 0x0", "Gol nos últimos 10 min"]
        best_market = "Under 0.5 Gols (0-0 fase final, jogo sem gols)"
        rat_parts.append(f"0-0 ao minuto {minute} — chance de 0x0 final aumenta")
    elif total_goals == 0 and minute >= 60:
        markets    = ["Próximo Gol", "Over 0.5 Gols", "Ambos Marcam"]
        best_market = "Over 0.5 Gols (0-0, pressão crescente por gol)"
        rat_parts.append(f"0-0 ao minuto {minute} — alta pressão por gol de abertura")
    elif goal_diff == 1 and minute >= 65:
        losing = away if score_h > score_a else home
        markets    = [f"Escanteios ({losing})", f"Próximo Gol ({losing})", "Cartões"]
        best_market = f"Escanteios ({losing} pressionando para empatar)"
        rat_parts.append(f"{losing} precisa empatar — pressão intensa com cruzamentos")
    elif goal_diff == 0 and total_goals >= 1 and minute >= 60:
        markets    = ["Próximo Gol", "Over 2.5 Gols", "Ambos Marcam"]
        best_market = f"Próximo Gol (empatado {score_h}x{score_a}, ambos atacam)"
        rat_parts.append(f"Empate {score_h}x{score_a} ao min {minute} — ambos buscam vitória")
    elif total_goals >= 3:
        markets    = ["Mais Escanteios", "Mais Cartões (frustração)"]
        best_market = "Escanteios (jogo aberto, muito espaço nas linhas)"
        rat_parts.append(f"Partida de {total_goals} gols — espaço e transições frequentes")
    else:
        markets    = [f"Analisar {home} x {away} ao vivo"]
        best_market = f"Análise completa de {home} x {away}"
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
            "match": None, "status": None, "is_live": False, "minute": None,
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
    count  = len(fixtures)
    top5   = ranked[:5]
    best   = ranked[0]

    # Build MarketEntry list
    markets: list[dict] = []
    for i, s in enumerate(top5, 1):
        prob = round(min(78, 42 + s.opportunity_score * 3.6), 1)
        ev   = round((s.opportunity_score - 5.0) * 2.0, 1)
        markets.append({
            "rank":           i,
            "market":         s.best_market,
            "probability":    prob,
            "expected_value": ev,
            "confidence":     round(s.opportunity_score, 1),
            "risk":           s.risk,
            "rationale": (
                f"**{s.home} {s.score_home}–{s.score_away} {s.away}**"
                + (f" · {s.league}" if s.league else "")
                + f" · Minuto {s.minute or '?'}\n"
                + s.rationale
                + f"\n💡 {_MOMENTUM_PT.get(s.momentum, s.momentum)}"
                + (f"\nSugestões: {', '.join(s.suggested_markets)}" if s.suggested_markets else "")
                + f"\n\nAnálise completa: \"Analisar {s.home} x {s.away}\""
            ),
        })

    high_opp = [s for s in ranked if s.opportunity_score >= 6.5]
    summary  = (
        f"**{count} partida{'s' if count != 1 else ''} ao vivo** — "
        f"{len(high_opp)} com alta oportunidade (≥6,5/10).\n\n"
        f"🏆 **Melhor oportunidade agora:**\n"
        f"**{best.home} {best.score_home}–{best.score_away} {best.away}**"
        + (f" · {best.league}" if best.league else "")
        + f" · Minuto {best.minute or '?'}\n"
        f"Oportunidade: **{best.opportunity_score:.1f}/10** "
        f"· {_MOMENTUM_PT.get(best.momentum, '')}\n"
        f"Mercado sugerido: **{best.best_market}**"
    )

    pos = [
        f"{s.home} x {s.away} ({s.score_home}–{s.score_away}, min {s.minute or '?'}): "
        f"Oportunidade {s.opportunity_score:.1f}/10"
        for s in ranked[:3] if s.opportunity_score >= 6.0
    ]
    neg = [
        f"{s.home} x {s.away}: Baixa oportunidade ({s.opportunity_score:.1f}/10)"
        for s in ranked[:3] if s.opportunity_score < 6.0
    ]

    conf_score = round(best.opportunity_score, 1)
    conf_label = "strong" if conf_score >= 8 else "moderate" if conf_score >= 6 else "adequate"

    return {
        "intent":   "live_opportunities",
        "entities": {"live_count": count, "top_opportunity": f"{best.home} x {best.away}"},
        "match":    f"{best.home} x {best.away}",
        "status":   "Live",
        "is_live":  True,
        "minute":   best.minute or None,
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
            f"Análise completa: \"Analisar {best.home} x {best.away}\"",
            "Odds ao vivo mudam rapidamente — confirme antes de apostar",
            "Score de oportunidade: avalia fase do jogo, placar e momentum",
        ],
        "final_recommendation": (
            f"Melhor oportunidade: **{best.home} x {best.away}** — "
            f"{best.best_market}. "
            f"Diga \"Analisar {best.home} x {best.away}\" para análise completa."
        ),
        "aurora_version": "Copilot v1.0",
        "brain":          brain_meta,
    }
