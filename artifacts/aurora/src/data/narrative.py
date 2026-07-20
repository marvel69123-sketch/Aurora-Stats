"""
P2b Wave 3 — Contextual narrative from confirmed NMB signals only.
Never invents stats, odds, injuries, or opponents.
"""

from __future__ import annotations

from typing import Any

from src.data.nmb import NormalizedMatchBundle


def _q(nmb: NormalizedMatchBundle, name: str) -> str:
    s = nmb.signals.get(name)
    return str(s.quality) if s else "missing"


def _val(nmb: NormalizedMatchBundle, name: str) -> Any:
    s = nmb.signals.get(name)
    return s.value if s else None


def build_contextual_narrative(nmb: NormalizedMatchBundle) -> dict[str, Any] | None:
    """
    Structured context bullets for premium presentation / explainability.
    Only references confirmed (or clearly labeled inferred) facts.
    """
    bullets: list[str] = []
    tags: list[str] = []

    if nmb.home and nmb.away:
        bullets.append(f"Confronto: {nmb.home} x {nmb.away}.")
        tags.append("fixture_label")

    cal = _val(nmb, "calendar")
    if _q(nmb, "calendar") == "confirmed" and isinstance(cal, dict):
        bits = []
        if cal.get("league"):
            bits.append(str(cal["league"]))
        if cal.get("round"):
            bits.append(str(cal["round"]))
        if cal.get("match_date"):
            bits.append(str(cal["match_date"]))
        if bits:
            bullets.append("Calendário: " + " · ".join(bits) + ".")
            tags.append("calendar")

    status = nmb.status_short
    if status and _q(nmb, "status") == "confirmed":
        bullets.append(f"Status confirmado: {status}.")
        tags.append("status")

    lm = _val(nmb, "live_momentum")
    if _q(nmb, "live_momentum") == "confirmed" and isinstance(lm, dict):
        if lm.get("is_live"):
            minute = lm.get("minute")
            score = lm.get("score") or {}
            bullets.append(
                f"Leitura ao vivo"
                + (f" ({minute}')" if minute is not None else "")
                + (
                    f" placar {score.get('home')}-{score.get('away')}."
                    if score.get("home") is not None
                    else "."
                )
            )
            tags.append("live")
        elif lm.get("is_finished"):
            bullets.append("Partida encerrada — contexto pós-jogo disponível.")
            tags.append("finished")

    xg = _val(nmb, "xg")
    xgq = _q(nmb, "xg")
    if xgq == "confirmed" and isinstance(xg, dict):
        bullets.append(
            f"xG confirmado: casa {xg.get('home')} · fora {xg.get('away')}."
        )
        tags.append("xg")
    elif xgq == "inferred" and isinstance(xg, dict):
        bullets.append(
            "xG ausente no provedor — prior de GPG da classificação marcado como inferido (não é xG da partida)."
        )
        tags.append("xg_inferred")

    lu = _val(nmb, "lineups")
    if _q(nmb, "lineups") == "confirmed" and isinstance(lu, dict):
        hf = ((lu.get("home") or {}) or {}).get("formation")
        af = ((lu.get("away") or {}) or {}).get("formation")
        if hf or af:
            bullets.append(
                f"Formações: {hf or '—'} vs {af or '—'}."
            )
            tags.append("lineups")
        if lu.get("both_xi"):
            bullets.append("Escalação titular confirmada para ambos os lados.")
            tags.append("xi_confirmed")

    inj = _val(nmb, "injuries")
    if _q(nmb, "injuries") == "confirmed" and isinstance(inj, dict):
        total = int(inj.get("total") or 0)
        if total > 0:
            bullets.append(f"Desfalques reportados pelo provedor: {total}.")
            tags.append("injuries")
        else:
            bullets.append("Consulta de desfalques sem registros no provedor.")
            tags.append("injuries_empty")

    odds = _val(nmb, "odds")
    if _q(nmb, "odds") == "confirmed" and isinstance(odds, dict):
        x = odds.get("1x2") or {}
        if any(x.get(k) is not None for k in ("home", "draw", "away")):
            bullets.append(
                f"Odds 1X2 ({odds.get('bookmaker') or 'book'}): "
                f"{x.get('home')} / {x.get('draw')} / {x.get('away')}."
            )
            tags.append("odds")

    st = _val(nmb, "standings")
    if _q(nmb, "standings") == "confirmed" and isinstance(st, dict):
        hr = (st.get("home") or {}).get("rank")
        ar = (st.get("away") or {}).get("rank")
        if hr is not None or ar is not None:
            bullets.append(f"Classificação: casa #{hr} · fora #{ar}.")
            tags.append("standings")

    if not bullets:
        return None

    missing_premium = [
        n
        for n in ("odds", "lineups", "calendar", "injuries", "xg")
        if _q(nmb, n) in {"missing", "empty", "rate_limited"}
    ]

    return {
        "bullets": bullets,
        "tags": tags,
        "missing_premium": missing_premium,
        "premium_ready": len(tags) >= 4 and "odds" in tags,
        "source": "confirmed_signals_only",
        "never_invent": True,
    }


def narrative_quality(narrative: dict[str, Any] | None) -> str:
    if not narrative or not narrative.get("bullets"):
        return "missing"
    return "confirmed"
