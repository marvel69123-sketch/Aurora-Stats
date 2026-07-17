"""
Aurora v4.3 — Human Presence Layer (HPL).

Makes replies feel present and human — especially social turns.
Additive. Fail-open. Does NOT edit frozen State/CRL/Reasoner/FollowUp.

Uses ConversationIntent from CUE when available.
"""

from __future__ import annotations

import logging
import random
import re
from typing import Any

logger = logging.getLogger(__name__)

HPL_CTX_KEY = "human_presence"
HPL_RECENT_KEY = "hpl_recent_lines"

_PRESENCE_FAMILIES: dict[str, list[str]] = {
    "greeting_wellbeing": [
        "Oi! Tudo certo por aqui. Como você está?",
        "Tudo bem por aqui. Em que posso ajudar hoje?",
        "Oi! Por aqui está tudo certo — e você?",
        "Tudo certo! Quer olhar algum jogo ou só bater um papo?",
    ],
    "greeting": [
        "Oi! Bom te ver por aqui.",
        "Oi! Pode falar — estou por aqui.",
        "Oi! Se quiser, a gente já olha um confronto.",
    ],
    "wellbeing": [
        "Tudo certo por aqui, obrigada por perguntar. E você?",
        "Por aqui vai bem. Como posso ajudar?",
        "Tudo bem sim. Quer continuar de onde paramos ou começar outro jogo?",
    ],
    "thanks": [
        "Disponha — qualquer coisa é só chamar.",
        "Por nada. Se quiser aprofundar, estou aqui.",
        "Que bom. Seguimos quando você quiser.",
    ],
    "farewell": [
        "Até mais — boa sorte nos jogos!",
        "Falou! Quando quiser, a gente retoma.",
        "Até logo. Cuida aí.",
    ],
    "ack": [
        "Entendi o que você quis dizer.",
        "Boa pergunta.",
        "Entendi o ponto.",
        "Certo, vamos por aí.",
    ],
    "opinion": [
        "Se eu estivesse olhando esse jogo agora, ",
        "Minha impressão inicial é que ",
        "Particularmente, ",
        "Se eu tivesse que escolher, ",
    ],
    "doubt": [
        "Posso estar enganada, mas ",
        "Eu teria alguma cautela aqui: ",
        "Não fecharia 100% ainda, porque ",
    ],
    "explain": [
        "O que me faz pensar isso é ",
        "O fio da minha leitura: ",
        "O ponto que pesa para mim: ",
    ],
}


def _pick(family: str, ctx: dict[str, Any] | None) -> str:
    opts = list(_PRESENCE_FAMILIES.get(family) or _PRESENCE_FAMILIES["ack"])
    recent = list((ctx or {}).get(HPL_RECENT_KEY) or [])
    fresh = [o for o in opts if o not in recent]
    choice = random.choice(fresh or opts)
    if ctx is not None:
        ctx[HPL_RECENT_KEY] = ([choice] + recent)[:8]
    return choice


def is_social_presence_turn(intent: dict[str, Any] | None) -> bool:
    if not intent:
        return False
    if intent.get("explicit_goal") == "SOCIAL":
        return True
    social = intent.get("social_intents") or []
    return bool(social) and float(intent.get("confidence") or 0) >= 0.8


def build_social_presence_reply(
    message: str,
    intent: dict[str, Any] | None,
    ctx: dict[str, Any] | None = None,
) -> str | None:
    """Human social reply — not the old brochure small-talk."""
    intent = intent or {}
    social = list(intent.get("social_intents") or [])
    if not social and intent.get("explicit_goal") != "SOCIAL":
        return None

    if "FAREWELL" in social:
        return _pick("farewell", ctx)
    if "THANKS" in social:
        return _pick("thanks", ctx)
    if "GREETING" in social and "WELL_BEING_CHECK" in social:
        return _pick("greeting_wellbeing", ctx)
    if "WELL_BEING_CHECK" in social:
        return _pick("wellbeing", ctx)
    if "GREETING" in social:
        return _pick("greeting", ctx)
    return _pick("greeting_wellbeing", ctx)


def build_presence_payload(reply: str, brain: dict[str, Any] | None = None) -> dict[str, Any]:
    """Soft payload compatible with CopilotResponse (no markets / no header)."""
    try:
        from src.conversation.message_intelligence import build_conversational_payload

        payload = build_conversational_payload(reply, brain)
    except Exception:
        payload = {
            "intent": "conversation_assist",
            "entities": {},
            "best_markets": [],
            "match_card": None,
            "executive_summary": reply,
            "final_recommendation": reply,
            "brain": brain or {},
        }
    ents = dict(payload.get("entities") or {})
    ents.update(
        {
            "social": True,
            "human_presence": True,
            "show_header": False,
            "crl_mode": "QUICK_REPLY",
        }
    )
    payload["entities"] = ents
    payload["intent"] = "small_talk"
    meta = dict(payload.get("response_metadata") or {})
    meta.update(
        {
            "mode": "human_presence",
            "source": "conversation.human_presence",
            "show_header": False,
            "crl_mode": "QUICK_REPLY",
        }
    )
    payload["response_metadata"] = meta
    payload["best_markets"] = []
    payload["match_card"] = None
    return payload


def apply_presence_to_text(
    text: str,
    *,
    family: str,
    ctx: dict[str, Any] | None = None,
    intent: dict[str, Any] | None = None,
) -> str:
    """
    Soft presence prefix for analytical short replies (does not edit CRL).
    Skips if text already feels present / social.
    """
    body = (text or "").strip()
    if not body:
        return body
    low = body.lower()
    # Don't double-prefix social answers
    if any(low.startswith(x) for x in ("oi", "tudo", "boa ", "entendi", "disponha", "até")):
        return body
    # Avoid stacking old robotic openers — strip lightly
    body = re.sub(
        r"^(na minha leitura|me parece|eu vejo valor)[,:]?\s*",
        "",
        body,
        count=1,
        flags=re.I,
    ).strip()
    if body:
        body = body[0].upper() + body[1:]

    fam = family
    if intent:
        g = str(intent.get("explicit_goal") or "")
        if g in {"ASK_OPINION", "ASK_RISK_EVAL"}:
            fam = "opinion"
        elif g == "ASK_EXPLANATION":
            fam = "explain"
        elif g in {"REJECT", "ASK_BETTER_OPTION"}:
            fam = "doubt"

    # For opinion/explain/doubt families, prefix is a clause opener
    if fam in {"opinion", "doubt", "explain"}:
        prefix = _pick(fam, ctx)
        if prefix.endswith(" ") or prefix.endswith(","):
            if body[:1].isupper():
                body = body[0].lower() + body[1:]
            return f"{prefix}{body}"
        return f"{prefix} {body}"

    # Ack-style presence line then body
    if random.random() < 0.55:
        ack = _pick("ack", ctx)
        return f"{ack}\n\n{body}"
    return body


def micro_reason(intent: dict[str, Any] | None) -> dict[str, str]:
    """Internal micro-reasoning for audit (not user-facing)."""
    intent = intent or {}
    return {
        "understood_intent": str(intent.get("understood_intent") or intent.get("explicit_goal") or ""),
        "implicit_meaning": str(intent.get("implicit_meaning") or ""),
        "human_response_strategy": (
            "social_presence"
            if intent.get("explicit_goal") == "SOCIAL"
            else "presence_enriched_analysis"
            if intent.get("rewrite_for_pipeline")
            else "presence_soft_prefix"
        ),
    }
