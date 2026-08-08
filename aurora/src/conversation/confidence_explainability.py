"""
P2.5 — Confidence Explainability (presentation layer).

Builds confidence_explanation from existing confidence scores + methodology
signals + SRF binding. Does NOT modify confidence_engine formulas.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "Confiança mede completude / riqueza dos dados, não certeza do resultado."
)


def _tier(display: int) -> str:
    if display <= 35:
        return "insuficiente"
    if display <= 54:
        return "baixa"
    if display <= 74:
        return "media"
    return "alta"


def score_to_display(score_0_10: float) -> int:
    try:
        s = float(score_0_10)
    except (TypeError, ValueError):
        s = 0.0
    # Map 0–10 → ~20–95 presentation band
    display = int(round(20 + max(0.0, min(10.0, s)) * 7.5))
    return max(0, min(99, display))


def build_confidence_explanation(
    *,
    confidence_score: float | None = None,
    confidence_label: str | None = None,
    has_xg: bool | None = None,
    has_stats: bool | None = None,
    has_standings: bool | None = None,
    has_events: bool | None = None,
    is_live_or_finished: bool | None = None,
    binding_quality: str | None = None,
    assumptions: list[str] | None = None,
    preliminary: bool = False,
    rate_limited: bool = False,
    pressure_signal: bool = False,
    momentum_signal: bool = False,
) -> dict[str, Any]:
    score = 0.0 if confidence_score is None else float(confidence_score)
    display = score_to_display(score)
    pos: list[dict[str, str]] = []
    neg: list[dict[str, str]] = []

    def add_pos(code: str, label: str) -> None:
        pos.append({"code": code, "label": label})

    def add_neg(code: str, label: str) -> None:
        neg.append({"code": code, "label": label})

    if has_xg:
        add_pos("HAS_XG", "xG disponível")
    else:
        add_neg("MISSING_XG", "xG ausente")
    if has_stats:
        add_pos("HAS_STATS", "Estatísticas da partida")
    else:
        add_neg("MISSING_STATS", "Sem estatísticas confirmadas")
    if has_standings:
        add_pos("HAS_STANDINGS", "Classificação / forma")
    elif has_standings is False:
        add_neg("MISSING_STANDINGS", "Sem classificação")
    if has_events:
        add_pos("HAS_EVENTS", "Eventos da partida")
    if is_live_or_finished:
        add_pos("LIVE_OR_FT", "Estado ao vivo ou encerrado")
    if pressure_signal:
        add_pos("PRESSURE_SIGNAL", "Pressão ofensiva")
    if momentum_signal:
        add_pos("MOMENTUM_SIGNAL", "Momentum")

    bq = str(binding_quality or "").upper()
    if bq == "FULL":
        add_pos("BINDING_FULL", "Confronto bem resolvido")
    elif bq == "PARTIAL":
        add_neg("BINDING_PARTIAL", "Fixture parcialmente resolvido")
    elif bq == "TEAM_ONLY":
        add_neg("BINDING_TEAM_ONLY", "Só time (sem confronto fechado)")
    elif bq == "AMBIGUOUS":
        add_neg("BINDING_AMBIGUOUS", "Identidade ambígua")

    if preliminary:
        add_neg("PRELIMINARY", "Análise preliminar / dados parciais")
    if rate_limited:
        add_neg("RATE_LIMIT", "Fonte temporariamente limitada")
    if assumptions:
        add_neg("ASSUMPTION_ACTIVE", "Contexto assumido")
    if not is_live_or_finished and score >= 0:
        # pre-match cap narrative (engine already applied; we only explain)
        if score <= 6.5:
            add_neg("PRE_MATCH_CAP", "Limite pré-jogo de confiança")

    # Cap bullets
    pos = pos[:3]
    neg = neg[:3]

    next_signals: list[str] = []
    for n in neg:
        code = n["code"]
        if code == "MISSING_XG":
            next_signals.append("xG")
        elif code == "MISSING_STATS":
            next_signals.append("estatísticas da partida")
        elif code == "BINDING_PARTIAL":
            next_signals.append("fixture oficial confirmado")
        elif code == "BINDING_TEAM_ONLY":
            next_signals.append("confronto Time A x Time B")

    return {
        "display_score": display,
        "tier": _tier(display),
        "meaning": "riqueza_de_dados",
        "internal_score": round(score, 2),
        "internal_label": confidence_label,
        "drivers_positive": pos,
        "drivers_negative": neg,
        "binding": {
            "quality": bq or None,
            "disclosed_assumptions": list(assumptions or []),
        },
        "next_signals": next_signals[:4],
        "disclaimer": DISCLAIMER,
    }


def _infer_flags_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    ents = payload.get("entities") or {}
    if not isinstance(ents, dict):
        ents = {}
    conf = payload.get("confidence") or {}
    if not isinstance(conf, dict):
        conf = {}
    brain = payload.get("brain") if isinstance(payload.get("brain"), dict) else {}
    inf = brain.get("inference") if isinstance(brain.get("inference"), dict) else {}
    avail = {str(x).lower() for x in (inf.get("available_signals") or [])}
    missing = {str(x).lower() for x in (inf.get("missing_signals") or [])}
    sources = " ".join(str(x).lower() for x in (conf.get("data_sources") or []))

    def has(name: str) -> bool | None:
        if name in avail:
            return True
        if name in missing:
            return False
        if name in sources:
            return True
        return None

    return {
        "score": conf.get("score"),
        "label": conf.get("label"),
        "has_xg": has("xg"),
        "has_stats": has("stats"),
        "has_standings": has("standings"),
        "has_events": has("events"),
        "is_live": bool(payload.get("is_live")),
        "preliminary": bool(ents.get("preliminary_analysis")),
        "rate_limited": bool(ents.get("rate_limited")),
        "binding_quality": ents.get("binding_quality")
        or (ents.get("srf") or {}).get("binding_quality")
        or ents.get("fixture_quality"),
        "assumptions": list(ents.get("bind_assumptions") or []),
    }


def apply_confidence_explanation(
    payload: dict[str, Any] | None,
    ctx: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return payload
    try:
        ents = dict(payload.get("entities") or {})
        intent = str(payload.get("intent") or "")
        if intent in {"clarification", "identity", "small_talk"} and not ents.get(
            "preliminary_analysis"
        ):
            return payload
        if ents.get("clarification_mode") and not ents.get("has_analysis"):
            return payload

        flags = _infer_flags_from_payload(payload)
        if isinstance(ctx, dict):
            last = ctx.get("entity_v2_last_bind")
            if isinstance(last, dict):
                flags["assumptions"] = flags["assumptions"] or list(
                    last.get("bind_assumptions") or []
                )
                flags["binding_quality"] = flags["binding_quality"] or last.get(
                    "binding_quality"
                )

        # Map fixture_quality PARTIAL → binding partial
        bq = str(flags.get("binding_quality") or "").upper()
        if bq in {"VALID"}:
            bq = "FULL"
        elif bq in {"PARTIAL", "WEAK", "INCOMPLETE"}:
            bq = "PARTIAL"

        expl = build_confidence_explanation(
            confidence_score=flags.get("score"),
            confidence_label=flags.get("label"),
            has_xg=flags.get("has_xg"),
            has_stats=flags.get("has_stats"),
            has_standings=flags.get("has_standings"),
            has_events=flags.get("has_events"),
            is_live_or_finished=flags.get("is_live"),
            binding_quality=bq,
            assumptions=flags.get("assumptions"),
            preliminary=bool(flags.get("preliminary")),
            rate_limited=bool(flags.get("rate_limited")),
        )
        ents["confidence_explanation"] = expl
        ents["p25_confidence_explain"] = True
        payload["entities"] = ents

        # Short user-facing note in knowledge_notes
        notes = list(payload.get("knowledge_notes") or [])
        bullet_pos = ", ".join(d["label"] for d in expl["drivers_positive"][:2])
        bullet_neg = ", ".join(d["label"] for d in expl["drivers_negative"][:2])
        line = (
            f"Confiança: {expl['display_score']}% ({expl['tier']}) — "
            f"{expl['meaning'].replace('_', ' ')}."
        )
        if bullet_pos:
            line += f" + {bullet_pos}."
        if bullet_neg:
            line += f" − {bullet_neg}."
        if line not in notes:
            notes.append(line)
            notes.append(DISCLAIMER)
        payload["knowledge_notes"] = notes
    except Exception as exc:
        logger.warning("confidence_explainability fail-open: %s", exc)
    return payload
