"""
Phase 8.4-A.7 — Partial analysis recovery.

When fixture_quality is PARTIAL (or completeness is low) but entities are valid,
produce a preliminary analysis with reduced confidence instead of refusing.

Never invents statistics. Rate-limit / 429 → confidence penalty, keep analysis.
"""

from __future__ import annotations

import re
from typing import Any

# Minimum completeness to allow preliminary_analysis (business rule)
MIN_COMPLETENESS_FOR_PRELIMINARY = 0.20

_RATE_LIMIT_RE = re.compile(
    r"(too\s+many\s+requests|rate[\s_-]?limit|429|api_fetch\s*limit)",
    re.I,
)

_REFUSAL_MARKERS = (
    "manteve a conversa com confiança muito baixa",
    "confiança muito baixa (fixture não confirmada)",
)


def is_rate_limit_error(detail: str | None) -> bool:
    if not detail:
        return False
    return bool(_RATE_LIMIT_RE.search(str(detail)))


def _has_min_signals(
    available: list[str] | set[str] | None,
    data: dict[str, Any] | None = None,
    inferred: list[str] | set[str] | None = None,
) -> bool:
    avail = {str(s) for s in (available or []) if s}
    avail |= {str(s) for s in (inferred or []) if s}
    if avail & {"teams", "fixture", "standings"}:
        return True
    if not isinstance(data, dict):
        return False
    teams = data.get("teams") or {}
    home = (teams.get("home") or {}).get("name")
    away = (teams.get("away") or {}).get("name")
    if home and away and str(home) not in {"Home", "Time A"} and str(away) not in {
        "Away",
        "Time B",
    }:
        return True
    fx = data.get("fixture") or {}
    try:
        if int(fx.get("id") or 0) > 0:
            return True
    except (TypeError, ValueError):
        pass
    st = data.get("standings") or {}
    if st.get("home") or st.get("away"):
        return True
    return False


def allow_partial_analysis(
    *,
    entity_invalid: bool = False,
    fixture_quality: str | None = None,
    data_completeness: float = 0.0,
    available_signals: list[str] | None = None,
    inferred_signals: list[str] | None = None,
    data: dict[str, Any] | None = None,
    rate_limited: bool = False,
) -> bool:
    """
    Business rule: valid entities + PARTIAL/WEAK/INCOMPLETE + min signals
    + completeness >= 0.20 → allow preliminary analysis.
    Rate-limit never forces a hard refuse when signals exist.
    """
    if entity_invalid:
        return False
    quality = str(fixture_quality or "").strip().upper()
    if quality and quality not in {"PARTIAL", "WEAK", "INCOMPLETE", ""}:
        # VALID / FOUND handled by normal path; INVALID must refuse
        if quality in {"INVALID", "FICTIONAL", "NOT_FOUND"}:
            return False
    try:
        completeness = float(data_completeness or 0.0)
    except (TypeError, ValueError):
        completeness = 0.0
    if completeness < MIN_COMPLETENESS_FOR_PRELIMINARY and not rate_limited:
        return False
    if not _has_min_signals(available_signals, data, inferred_signals):
        return False
    # Quality empty but partial signals → still allow (soft analyze)
    if not quality or quality in {"PARTIAL", "WEAK", "INCOMPLETE"}:
        return True
    # VALID with rate-limit gaps still benefits from preliminary framing
    if rate_limited and completeness < 0.85:
        return True
    return False


def detect_rate_limited(
    ictx: Any = None,
    *,
    notes: list[str] | None = None,
    penalties: list[dict[str, Any]] | None = None,
) -> bool:
    blobs: list[str] = []
    if notes:
        blobs.extend(str(n) for n in notes)
    if penalties:
        for p in penalties:
            blobs.append(str(p.get("reason") or ""))
    if ictx is not None:
        try:
            blobs.extend(str(n) for n in (getattr(ictx, "notes", None) or []))
            for p in getattr(ictx, "confidence_penalties", None) or []:
                blobs.append(str((p or {}).get("reason") or ""))
        except Exception:
            pass
    return any(is_rate_limit_error(b) for b in blobs)


def resolve_preliminary_confidence(
    score: float,
    *,
    data_completeness: float,
    rate_limited: bool = False,
) -> tuple[float, str]:
    """
    Reduced confidence for preliminary analysis — never the hard 1.5 refusal cap.
    Target band: weak (2–3.9) or adequate (4–5.5).
    """
    try:
        raw = float(score)
    except (TypeError, ValueError):
        raw = 0.0
    try:
        comp = float(data_completeness or 0.0)
    except (TypeError, ValueError):
        comp = 0.0

    # Soft floor from completeness
    floor = 2.0 + min(2.5, max(0.0, comp) * 3.0)
    capped = round(min(max(raw, floor), 5.5), 1)
    if rate_limited:
        capped = round(max(2.0, capped - 0.8), 1)
    label = "adequate" if capped >= 4.0 else "weak"
    return capped, label


def _standings_hint(data: dict[str, Any] | None, side: str) -> str | None:
    if not isinstance(data, dict):
        return None
    row = ((data.get("standings") or {}).get(side) or {})
    if not isinstance(row, dict) or not row:
        return None
    rank = row.get("rank") or row.get("position")
    pts = row.get("points")
    form = row.get("form")
    bits: list[str] = []
    if rank is not None:
        bits.append(f"posição {rank}")
    if pts is not None:
        bits.append(f"{pts} pts")
    if form:
        bits.append(f"forma {form}")
    if not bits:
        return None
    return ", ".join(bits)


def build_preliminary_executive(
    home: str,
    away: str,
    *,
    base_summary: str | None,
    missing_signals: list[str] | None = None,
    available_signals: list[str] | None = None,
    data: dict[str, Any] | None = None,
    rate_limited: bool = False,
    confidence_label: str = "weak",
) -> str:
    """
    Preliminary framing: limitations + qualitative reading.
    Does not invent xG, scorelines, or fake stats.
    """
    hn = (home or "Time A").strip() or "Time A"
    an = (away or "Time B").strip() or "Time B"
    missing = [s for s in (missing_signals or []) if s]
    available = [s for s in (available_signals or []) if s]

    # Public-safe wording (avoid tokens the personality sanitizer strips: xG, API, Inference)
    _miss_labels = {
        "statistics": "estatísticas da partida",
        "xg": "métricas avançadas de finalização",
        "lineups": "escalações",
        "score": "placar",
        "referee": "árbitro",
        "events": "eventos",
        "standings": "classificação",
        "fixture": "partida oficial confirmada",
    }
    _avail_labels = {
        "teams": "times",
        "fixture": "partida",
        "standings": "classificação",
        "statistics": "estatísticas",
        "events": "eventos",
        "lineups": "escalações",
        "score": "placar",
    }
    miss_human = [_miss_labels.get(s, s) for s in missing]
    avail_human = [_avail_labels.get(s, s) for s in available]

    lines: list[str] = [
        f"**{hn} x {an}** — leitura preliminar",
        "",
        "Confronto reconhecido, mas com **dados parciais**. "
        "Segue uma análise preliminar — sem inventar números ausentes.",
    ]
    if rate_limited:
        lines.append(
            "Parte dos sinais ficou indisponível por limite de requisições; "
            "a leitura continua com confiança reduzida."
        )
    if miss_human:
        lines.append("Ausentes agora: " + ", ".join(miss_human) + ".")
    if avail_human:
        lines.append("Sinais disponíveis: " + ", ".join(avail_human) + ".")

    lines.extend(["", "Leitura preliminar (qualitativa):"])

    sh = _standings_hint(data, "home")
    sa = _standings_hint(data, "away")
    if sh or sa:
        if sh:
            lines.append(f"• {hn}: {sh} (classificação parcial).")
        if sa:
            lines.append(f"• {an}: {sa} (classificação parcial).")
    else:
        lines.append(
            f"• Perfis históricos de {hn} e {an} sugerem um jogo de alto nível técnico, "
            "mas sem estatísticas fechadas o veredito fica aberto."
        )

    lines.append(
        "• Sem posse, métricas avançadas ou escalações confirmadas, "
        "evito cravar ritmo ou domínio — só forças relativas e tendência geral."
    )
    lines.append(
        "• Mercados a observar com cautela (genéricos, não calculados): "
        "ambas marcam, over asiático moderado, equilíbrio do jogo."
    )
    lines.append("")
    lines.append(
        f"Confiança: **{confidence_label}** (dados parciais"
        + ("; rate limit" if rate_limited else "")
        + ")."
    )

    base = (base_summary or "").strip()
    # Drop prior refusal wrappers if engines echoed them
    low = base.lower()
    if base and not any(m in low for m in _REFUSAL_MARKERS):
        # Avoid duplicating a full structured dump; keep a short engine note
        if len(base) > 40:
            lines.extend(["", "Nota do motor (quando disponível):", base[:500]])

    return "\n".join(lines).strip()


def strip_refusal_preamble(text: str | None) -> str:
    raw = str(text or "")
    for marker in _REFUSAL_MARKERS:
        idx = raw.lower().find(marker)
        if idx >= 0:
            # remove the refusal paragraph block
            return raw[idx + len(marker) :].lstrip(" .\n")
    return raw
