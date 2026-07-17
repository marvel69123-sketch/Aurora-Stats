"""
Aurora v4.7 — Response Formatter Layer (stabilized).

Last-mile organization of user-facing text:
  clear · natural · no raw API vibes · depth-aware

Fail-open. Additive. Does not edit engines / State / CIL / CRL.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_ROBOTIC = [
    (re.compile(r"\bconsiderando o contexto\b", re.I), "olhando o momento"),
    (re.compile(r"\bconsidering the context\b", re.I), "olhando o momento"),
    (re.compile(r"\banalizand[oa]?\s+os\s+fatores\b", re.I), "olhando os pontos principais"),
    (re.compile(r"\banalisando os fatores\b", re.I), "olhando os pontos principais"),
    (re.compile(r"\banalyzing the factors\b", re.I), "olhando os pontos principais"),
    (re.compile(r"\bna l[oó]gica atual\b", re.I), "do jeito que vejo agora"),
    (re.compile(r"\bmercado em foco\b", re.I), "caminho que estou olhando"),
    (re.compile(r"\bcom base nos dados (?:da|do)\s+\w+\b", re.I), "pelo que vejo agora"),
    (re.compile(r"\bSOURCE[:=]\s*\w+", re.I), ""),
    (re.compile(r"\bAPI[- ]Football\b", re.I), "dados do dia"),
    (re.compile(r"\bfixture[_ ]?id\b", re.I), "partida"),
    (re.compile(r"\bleague[_ ]?id\b", re.I), "campeonato"),
    (re.compile(r"\bstatus[_ ]?code\b", re.I), "status"),
    (re.compile(r"\bendpoint\b", re.I), "fonte"),
    (re.compile(r"\bJSON\b", re.I), "resumo"),
    (re.compile(r"\bpayload\b", re.I), "resposta"),
    (re.compile(r"\bDEBUG\b"), ""),
    (re.compile(r"\bhttpx?\b", re.I), ""),
    (re.compile(r"\btraceback\b", re.I), ""),
    # Analysis pitch that must never leak into social/emotional
    (
        re.compile(
            r"\bposso ajudar com an[aá]lises?(?:\s+esportivas?)?\b[.!]?",
            re.I,
        ),
        "",
    ),
    (
        re.compile(
            r"\bposso ajudar com leituras?(?:\s+de\s+partidas?)?(?:\s+e\s+mercados?)?\b[.!]?",
            re.I,
        ),
        "",
    ),
    (
        re.compile(
            r"\bqual confronto voc[eê] gostaria de observar\??\b",
            re.I,
        ),
        "",
    ),
    (
        re.compile(
            r"\bcomo (?:sua )?assistente (?:de|esportiva)\b[.!]?",
            re.I,
        ),
        "",
    ),
]


def _scrub(text: str) -> str:
    out = text or ""
    for pat, repl in _ROBOTIC:
        out = pat.sub(repl, out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    out = re.sub(r"\s+([,.!?])", r"\1", out)
    return out.strip()


def _preserve_depth(body: str, *, kind: str | None, original: str) -> str:
    """
    Short stays short; deep stays deep.
    Social/emotional: compact. Analysis: never force-shorten.
    """
    if not body:
        return body
    if kind in {"social", "emotional"}:
        # Keep at most two short paragraphs for presence turns
        parts = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
        if len(parts) > 2:
            body = "\n\n".join(parts[:2])
        if len(body) > 360 and len(original) <= 280:
            # Accidental inflation — prefer original scrubbed length
            body = body[:360].rsplit(" ", 1)[0].rstrip(".,;") + "."
        return body.strip()
    if kind == "opinion":
        # Opinions can breathe, but avoid essay dumps
        if len(body) > 1200:
            body = body[:1200].rsplit(" ", 1)[0].rstrip() + "…"
        return body
    # analysis / calendar / generic — leave structure
    return body


def format_user_facing_text(
    text: str,
    *,
    kind: str | None = None,
    prefs: dict[str, Any] | None = None,
) -> str:
    """
    Organize prose for a human reader.
    kind: social | calendar | opinion | emotional | analysis | generic
    """
    try:
        original = text or ""
        body = _scrub(original)
        if not body:
            return body
        if kind == "calendar":
            return body
        body = re.sub(r"\.\s*\.", ".", body)
        body = _preserve_depth(body, kind=kind, original=original)
        return body
    except Exception as exc:
        logger.warning("format_user_facing_text fail-open: %s", exc)
        return text


def apply_formatter_to_payload(
    payload: dict[str, Any],
    *,
    prefs: dict[str, Any] | None = None,
    ctx: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Mutate narrative fields only. Fail-open."""
    try:
        if not isinstance(payload, dict):
            return payload
        ents = payload.get("entities") or {}
        kind = None
        if ents.get("emotional"):
            kind = "social"
        elif ents.get("natural_kind") == "calendar" or "calendar" in str(
            ents.get("natural_kind") or ""
        ):
            kind = "calendar"
        elif ents.get("agenda_formatted"):
            kind = "calendar"
        elif ents.get("opinion_time") or ents.get("natural_kind") == "team_opinion":
            kind = "opinion"
        elif ents.get("profile_memory") or payload.get("intent") in {
            "small_talk",
            "greeting",
            "emotional",
        }:
            kind = "social"
        elif payload.get("intent") in {"analyze_match", "live_opportunities"}:
            kind = "analysis"

        for field in ("executive_summary", "final_recommendation"):
            if payload.get(field):
                payload[field] = format_user_facing_text(
                    str(payload[field]),
                    kind=kind,
                    prefs=prefs,
                )

        # Strip robotic thinking labels from credibility for social/natural
        meta = dict(payload.get("response_metadata") or {})
        cred = dict(meta.get("credibility") or {})
        if cred.get("display_mode") in {"SOCIAL", "FOLLOW_UP"}:
            label = str(cred.get("thinking_label") or "")
            if re.search(
                r"considerando|analisando|comparando|analyzing|considering",
                label,
                re.I,
            ):
                cred["thinking_label"] = None
                meta["credibility"] = cred

        meta["formatter"] = {"applied": True, "kind": kind or "generic", "v": "4.7.1"}
        payload["response_metadata"] = meta
        return payload
    except Exception as exc:
        logger.warning("apply_formatter_to_payload fail-open: %s", exc)
        return payload
