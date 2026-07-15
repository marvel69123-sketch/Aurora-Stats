"""
Match Card builder (Aurora v3.3.1-beta) — presentation only.

Assembles logos, score, competition, venue, momentum and predictability
from analyze/live payloads already fetched by engines. Does NOT call
methodology / market / confidence engines.
"""

from __future__ import annotations

from typing import Any

AURORA_MATCH_VERSION = "Aurora v3.3.1-beta"

_MOMENTUM_UI: dict[str, dict[str, str]] = {
    "home_pressing": {
        "label": "Pressão do mandante",
        "side": "home",
        "detail": "O placar favorece a equipe visitante — o mandante tende a buscar mais o gol.",
    },
    "away_pressing": {
        "label": "Pressão do visitante",
        "side": "away",
        "detail": "O placar favorece o mandante — o visitante tende a buscar mais o gol.",
    },
    "balanced": {
        "label": "Equilíbrio",
        "side": "neutral",
        "detail": "Partida equilibrada no placar — atenção ao ritmo dos próximos minutos.",
    },
    "game_over": {
        "label": "Placar definido",
        "side": "neutral",
        "detail": "Diferença grande no placar — o cenário tende a se estabilizar.",
    },
}

_PRED_LABEL: dict[str, str] = {
    "strong": "Alta previsibilidade",
    "moderate": "Previsibilidade moderada",
    "adequate": "Previsibilidade adequada",
    "weak": "Baixa previsibilidade",
    "insufficient": "Previsibilidade muito baixa",
    # i18n may already have translated the confidence label
    "alta": "Alta previsibilidade",
    "moderada": "Previsibilidade moderada",
    "adequada": "Previsibilidade adequada",
    "fraca": "Baixa previsibilidade",
    "insuficiente": "Previsibilidade muito baixa",
    "muito baixa": "Previsibilidade muito baixa",
}


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_str(value: Any) -> str | None:
    """Coerce API scalars to str for Pydantic MatchCard fields."""
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.lower() in {"unknown", "n/a", "na", "null", "none", "undefined"}:
            return None
        return text
    if isinstance(value, (int, float, bool)):
        return str(value)
    return None


def _logo_str(value: Any) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return None


def _competition_block(league: dict[str, Any]) -> dict[str, Any] | None:
    """Build competition dict or None — never emit Unknown labels."""
    name = _safe_str(league.get("name"))
    if not name:
        return None
    return {
        "name": name,
        "logo": _logo_str(league.get("logo")),
        "country": _safe_str(league.get("country")),
        "round": _safe_str(league.get("round")),
    }


def _team_block(name: str, logo: Any = None) -> dict[str, Any]:
    return {
        "name": (name or "").strip() or "Time",
        "logo": _logo_str(logo),
    }


def _momentum_from_score(score_h: int | None, score_a: int | None) -> dict[str, str] | None:
    if score_h is None or score_a is None:
        return None
    diff = abs(score_h - score_a)
    if diff >= 2:
        key = "game_over"
    elif score_h > score_a:
        key = "away_pressing"
    elif score_a > score_h:
        key = "home_pressing"
    else:
        key = "balanced"
    return dict(_MOMENTUM_UI[key])


def build_predictability(
    confidence: dict[str, Any] | None,
    *,
    is_live: bool = False,
) -> dict[str, Any] | None:
    """Human predictability blurb from existing confidence section."""
    if not isinstance(confidence, dict):
        return None
    try:
        score = float(confidence.get("score") or 0.0)
    except (TypeError, ValueError):
        score = 0.0
    label_key = str(confidence.get("label") or "insufficient")
    title = _PRED_LABEL.get(label_key, _PRED_LABEL["insufficient"])
    if is_live:
        summary = (
            "Leitura ao vivo com base no ritmo atual da partida. "
            "A previsibilidade pode mudar rápido conforme o jogo evolui."
        )
    elif score >= 7.5:
        summary = (
            "Os sinais disponíveis permitem uma leitura mais firme neste momento. "
            "Ainda assim, escalações e o ritmo inicial podem alterar o cenário."
        )
    elif score >= 5.0:
        summary = (
            "Há sinais úteis, mas ainda falta confirmação para uma leitura mais segura. "
            "Vale observar com calma antes de uma entrada agressiva."
        )
    else:
        summary = (
            "Ainda faltam sinais claros para uma leitura confiante. "
            "Prefira acompanhar a evolução da partida antes de decidir."
        )
    return {
        "score": round(score, 1),
        "label": title,
        "summary": summary,
    }


def build_match_card_from_analyze(
    data: dict[str, Any],
    *,
    is_live: bool,
    minute: int | None,
    status_label: str | None,
    confidence: dict[str, Any] | None = None,
    momentum_key: str | None = None,
) -> dict[str, Any] | None:
    """Build match_card from analyze_fixture payload."""
    if not isinstance(data, dict):
        return None
    teams = data.get("teams") or {}
    home = teams.get("home") or {}
    away = teams.get("away") or {}
    hn = home.get("name")
    an = away.get("name")
    if not hn and not an:
        return None

    league = data.get("league") or {}
    fx = data.get("fixture") or {}
    venue = fx.get("venue") or {}
    score_block = (data.get("score") or {}).get("current") or {}
    sh = _safe_int(score_block.get("home"))
    sa = _safe_int(score_block.get("away"))

    momentum = None
    if momentum_key and momentum_key in _MOMENTUM_UI:
        momentum = dict(_MOMENTUM_UI[momentum_key])
    elif is_live:
        momentum = _momentum_from_score(sh, sa)

    competition = _competition_block(league if isinstance(league, dict) else {})

    venue_out = None
    venue_name = _safe_str(venue.get("name"))
    if venue_name:
        venue_out = {
            "name": venue_name,
            "city": _safe_str(venue.get("city")),
        }

    score_out = None
    if sh is not None and sa is not None and (is_live or sh > 0 or sa > 0):
        score_out = {"home": sh, "away": sa}

    return {
        "home": _team_block(str(hn or ""), home.get("logo")),
        "away": _team_block(str(an or ""), away.get("logo")),
        "score": score_out,
        "competition": competition,
        "venue": venue_out,
        "status_label": _safe_str(status_label),
        "minute": _safe_int(minute),
        "is_live": bool(is_live),
        "momentum": momentum,
        "predictability": build_predictability(confidence, is_live=bool(is_live)),
    }


def build_match_card_from_live_fixture(
    fx: dict[str, Any],
    *,
    confidence: dict[str, Any] | None = None,
    momentum_key: str | None = None,
) -> dict[str, Any] | None:
    """Build match_card from live.py match object."""
    if not isinstance(fx, dict):
        return None
    home = fx.get("home") or {}
    away = fx.get("away") or {}
    hn = home.get("name")
    an = away.get("name")
    if not hn and not an:
        return None

    status = fx.get("status") or {}
    league = fx.get("league") or {}
    sh = _safe_int(home.get("score"))
    sa = _safe_int(away.get("score"))
    minute = _safe_int(status.get("minute"))

    key = momentum_key
    if not key:
        # Align with live_intelligence_engine heuristic (presentation mirror only)
        if sh is not None and sa is not None:
            diff = abs(sh - sa)
            if diff >= 2:
                key = "game_over"
            elif sh > sa:
                key = "away_pressing"
            elif sa > sh:
                key = "home_pressing"
            else:
                key = "balanced"

    momentum = dict(_MOMENTUM_UI[key]) if key in _MOMENTUM_UI else None

    competition = _competition_block(league if isinstance(league, dict) else {})

    score_out = None
    if sh is not None and sa is not None:
        score_out = {"home": sh, "away": sa}

    return {
        "home": _team_block(str(hn or ""), home.get("logo")),
        "away": _team_block(str(an or ""), away.get("logo")),
        "score": score_out,
        "competition": competition,
        "venue": None,  # live feed does not include venue
        "status_label": (
            _safe_str(status.get("long"))
            or _safe_str(status.get("short"))
            or "Ao vivo"
        ),
        "minute": minute,
        "is_live": True,
        "momentum": momentum,
        "predictability": build_predictability(confidence, is_live=True),
    }


def normalize_match_card(card: dict[str, Any] | None) -> dict[str, Any] | None:
    """Re-coerce a match_card dict so CopilotResponse/MatchCard always validates."""
    if not isinstance(card, dict):
        return None
    home = card.get("home") if isinstance(card.get("home"), dict) else {}
    away = card.get("away") if isinstance(card.get("away"), dict) else {}
    hn = _safe_str(home.get("name"))
    an = _safe_str(away.get("name"))
    if not hn and not an:
        return None

    score = card.get("score")
    score_out = None
    if isinstance(score, dict):
        sh, sa = _safe_int(score.get("home")), _safe_int(score.get("away"))
        if sh is not None and sa is not None:
            score_out = {"home": sh, "away": sa}

    competition = card.get("competition")
    competition_out = None
    if isinstance(competition, dict):
        competition_out = _competition_block(competition)

    venue = card.get("venue")
    venue_out = None
    if isinstance(venue, dict) and _safe_str(venue.get("name")):
        venue_out = {
            "name": _safe_str(venue.get("name")),
            "city": _safe_str(venue.get("city")),
        }

    momentum = card.get("momentum")
    momentum_out = None
    if isinstance(momentum, dict) and _safe_str(momentum.get("label")):
        momentum_out = {
            "label": _safe_str(momentum.get("label")),
            "side": _safe_str(momentum.get("side")),
            "detail": _safe_str(momentum.get("detail")),
        }

    predictability = card.get("predictability")
    predictability_out = None
    if isinstance(predictability, dict) and _safe_str(predictability.get("label")):
        try:
            pscore = float(predictability.get("score") or 0.0)
        except (TypeError, ValueError):
            pscore = 0.0
        predictability_out = {
            "score": round(pscore, 1),
            "label": _safe_str(predictability.get("label")) or "",
            "summary": _safe_str(predictability.get("summary")) or "",
        }

    return {
        "home": _team_block(hn or "Time", home.get("logo")),
        "away": _team_block(an or "Time", away.get("logo")),
        "score": score_out,
        "competition": competition_out,
        "venue": venue_out,
        "status_label": _safe_str(card.get("status_label")),
        "minute": _safe_int(card.get("minute")),
        "is_live": bool(card.get("is_live")),
        "momentum": momentum_out,
        "predictability": predictability_out,
    }


def attach_match_card(payload: dict[str, Any], card: dict[str, Any] | None) -> dict[str, Any]:
    """Attach match_card + version bump when card is present."""
    if not isinstance(payload, dict):
        return payload
    cleaned = normalize_match_card(card) if isinstance(card, dict) else None
    if not cleaned:
        return payload
    payload = dict(payload)
    payload["match_card"] = cleaned
    payload["aurora_version"] = AURORA_MATCH_VERSION
    return payload
