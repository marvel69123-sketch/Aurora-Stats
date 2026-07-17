"""
Aurora Final Stabilization — Conversation Focus + Reference Resolver.

Short memory for legitimate follow-ups without sticky fixture contamination.
Fail-open. Additive.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any

logger = logging.getLogger(__name__)

FOCUS_KEY = "conversation_focus"
MEMORY_KEY = "short_memory_window"
MEMORY_MAX = 5

_FOLLOW_HORARIO = re.compile(
    r"\b(e\s+o\s+horario|o\s+horario|que\s+horas|horario)\b", re.I
)
_FOLLOW_AMANHA = re.compile(r"\b(e\s+amanha|amanha)\b", re.I)
_FOLLOW_HOJE = re.compile(r"\b(e\s+hoje|hoje)\b", re.I)
_FOLLOW_ANTERIOR = re.compile(r"\b(e\s+o\s+anterior|o\s+anterior|anterior)\b", re.I)
_FOLLOW_ELE = re.compile(
    r"\b("
    r"como\s+(?:ele|ela)\s+(?:esta|vai)|"
    r"como\s+esta\s+atualmente|"
    r"como\s+esta\s+agora|"
    r"e\s+agora|"
    r"e\s+(?:ele|ela)\b|"
    r"^(?:ele|ela)\??$"
    r")",
    re.I,
)
_ENTITY_PIVOT = re.compile(r"\be\s+(?:o|a|do|da)\s+(\w+)", re.I)


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


def get_focus(ctx: dict[str, Any] | None) -> dict[str, Any]:
    if not ctx:
        return {}
    raw = ctx.get(FOCUS_KEY)
    return dict(raw) if isinstance(raw, dict) else {}


def get_memory(ctx: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not ctx:
        return []
    raw = ctx.get(MEMORY_KEY)
    return list(raw) if isinstance(raw, list) else []


def update_conversation_focus(
    ctx: dict[str, Any],
    *,
    thinking: dict[str, Any] | None = None,
    recovery: dict[str, Any] | None = None,
    message: str = "",
    resolved: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist short focus after a successful turn understanding."""
    try:
        thinking = thinking or (ctx.get("deep_thinking") or {})
        recovery = recovery or (ctx.get("context_recovery") or {})
        prev = get_focus(ctx)
        teams = list(recovery.get("teams") or thinking.get("topic_teams") or [])
        team = thinking.get("topic_team") or (teams[0] if teams else None)
        fixture = None
        if len(teams) >= 2:
            fixture = f"{teams[0]} x {teams[1]}"
        elif prev.get("topic_fixture") and thinking.get("topic_kind") in {
            "kickoff",
            "calendar",
            "fixture",
            None,
        }:
            # keep fixture on soft follow-ups unless entity pivot
            fixture = prev.get("topic_fixture")

        if isinstance(resolved, dict) and resolved.get("resolved"):
            team = resolved.get("topic_team") or team
            fixture = resolved.get("topic_fixture") or fixture
            kind = resolved.get("topic_kind") or thinking.get("topic_kind")
        else:
            kind = thinking.get("topic_kind") or prev.get("topic_kind")

        # Prefer explicit pair from thinking
        tteams = list(thinking.get("topic_teams") or [])
        if len(tteams) >= 2 and not fixture:
            fixture = f"{tteams[0]} x {tteams[1]}"
            teams = tteams[:2] or teams
        if len(teams) >= 2 and not fixture:
            fixture = f"{teams[0]} x {teams[1]}"

        focus = {
            "topic_kind": kind,
            "topic_team": team or prev.get("topic_team"),
            "topic_teams": teams[:2] or list(prev.get("topic_teams") or [])[:2],
            "topic_fixture": fixture,
            "last_intent": recovery.get("inferred_goal") or thinking.get("topic_kind"),
            "last_subject": team or fixture or prev.get("last_subject"),
            "last_message": (message or "")[:120],
        }
        ctx[FOCUS_KEY] = focus

        # short memory window
        mem = get_memory(ctx)
        mem.append(
            {
                "kind": focus.get("topic_kind"),
                "team": focus.get("topic_team"),
                "fixture": focus.get("topic_fixture"),
                "intent": focus.get("last_intent"),
            }
        )
        ctx[MEMORY_KEY] = mem[-MEMORY_MAX:]
        logger.warning(
            "[AUDIT] ConversationFocus: kind=%s team=%r fixture=%r mem=%d",
            focus.get("topic_kind"),
            focus.get("topic_team"),
            focus.get("topic_fixture"),
            len(ctx[MEMORY_KEY]),
        )
        return focus
    except Exception as exc:
        logger.warning("update_conversation_focus fail-open: %s", exc)
        return get_focus(ctx)


def clear_focus_on_boundary(ctx: dict[str, Any]) -> None:
    """Hard topic change — drop fixture focus, keep light memory note."""
    try:
        prev = get_focus(ctx)
        ctx[FOCUS_KEY] = {
            "topic_kind": None,
            "topic_team": None,
            "topic_teams": [],
            "topic_fixture": None,
            "last_intent": "topic_boundary",
            "last_subject": None,
            "last_message": prev.get("last_message"),
        }
    except Exception:
        pass


def resolve_reference(
    message: str,
    ctx: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Resolve ambiguous follow-ups against conversation_focus.
    Returns resolved intent hints for DeepThinking / Natural.
    """
    result: dict[str, Any] = {
        "resolved": False,
        "ambiguous": False,
        "rewrite": None,
        "topic_kind": None,
        "topic_team": None,
        "topic_fixture": None,
        "confidence": 0.0,
        "reason": "none",
        "clarification": None,
    }
    try:
        focus = get_focus(ctx)
        folded = _fold(message)
        if not folded:
            return result

        # Explicit entity pivot — not a soft follow-up
        if (
            _ENTITY_PIVOT.search(folded)
            and not _FOLLOW_HORARIO.search(folded)
            and not _FOLLOW_ANTERIOR.search(folded)
            and not _FOLLOW_ELE.search(folded)
        ):
            m = _ENTITY_PIVOT.search(folded)
            result.update(
                {
                    "resolved": False,
                    "reason": "entity_pivot",
                    "confidence": 0.9,
                    "topic_team": m.group(1) if m else None,
                }
            )
            return result

        has_focus = bool(
            focus.get("topic_team")
            or focus.get("topic_fixture")
            or focus.get("topic_kind")
        )

        # horário → kickoff of focused fixture/team
        if _FOLLOW_HORARIO.search(folded) and len(folded) < 40:
            if focus.get("topic_fixture"):
                result.update(
                    {
                        "resolved": True,
                        "topic_kind": "kickoff",
                        "topic_fixture": focus["topic_fixture"],
                        "topic_team": focus.get("topic_team"),
                        "rewrite": f"que horas é o jogo {focus['topic_fixture']}?",
                        "confidence": 0.88,
                        "reason": "horario_of_fixture",
                    }
                )
                return result
            if focus.get("topic_team"):
                result.update(
                    {
                        "resolved": True,
                        "topic_kind": "kickoff",
                        "topic_team": focus["topic_team"],
                        "rewrite": f"{focus['topic_team']} joga que horas?",
                        "confidence": 0.85,
                        "reason": "horario_of_team",
                    }
                )
                return result
            result.update(
                {
                    "ambiguous": True,
                    "confidence": 0.4,
                    "reason": "horario_no_focus",
                    "clarification": (
                        "Posso estar interpretando errado, mas você está perguntando "
                        "sobre o horário de qual jogo ou time? Me diga o confronto "
                        "(ex.: Mirassol x Grêmio) que eu afunilo."
                    ),
                }
            )
            return result

        # amanhã / hoje as calendar continuation
        if (_FOLLOW_AMANHA.search(folded) or _FOLLOW_HOJE.search(folded)) and len(
            folded
        ) < 36:
            when = "amanhã" if _FOLLOW_AMANHA.search(folded) else "hoje"
            if focus.get("topic_fixture"):
                result.update(
                    {
                        "resolved": True,
                        "topic_kind": "fixture",
                        "topic_fixture": focus["topic_fixture"],
                        "topic_team": focus.get("topic_team"),
                        "rewrite": f"jogo {focus['topic_fixture']} {when}",
                        "confidence": 0.86,
                        "reason": f"calendar_continue_{when}",
                    }
                )
                return result
            if focus.get("topic_team"):
                result.update(
                    {
                        "resolved": True,
                        "topic_kind": "calendar",
                        "topic_team": focus["topic_team"],
                        "rewrite": f"jogo do {focus['topic_team']} {when}",
                        "confidence": 0.84,
                        "reason": f"team_calendar_{when}",
                    }
                )
                return result

        # como ele está → moment of focused team
        if _FOLLOW_ELE.search(folded):
            if focus.get("topic_team"):
                result.update(
                    {
                        "resolved": True,
                        "topic_kind": "moment",
                        "topic_team": focus["topic_team"],
                        "rewrite": f"como está o {focus['topic_team']} atualmente?",
                        "confidence": 0.87,
                        "reason": "pronoun_moment",
                    }
                )
                return result
            result.update(
                {
                    "ambiguous": True,
                    "confidence": 0.45,
                    "reason": "pronoun_no_team",
                    "clarification": (
                        "Posso estar interpretando errado, mas você está perguntando "
                        "como está qual time no momento? Me confirma o clube."
                    ),
                }
            )
            return result

        # e o anterior — resolve to prior subject without inventing fixtures
        if _FOLLOW_ANTERIOR.search(folded) and len(folded) < 40:
            mem = get_memory(ctx)
            prior = None
            for item in reversed(mem[:-1] if mem else []):
                if item.get("fixture") or item.get("team"):
                    prior = item
                    break
            if prior and prior.get("fixture"):
                result.update(
                    {
                        "resolved": True,
                        "topic_kind": "fixture",
                        "topic_fixture": prior["fixture"],
                        "topic_team": prior.get("team"),
                        "rewrite": f"fale do jogo {prior['fixture']}",
                        "confidence": 0.78,
                        "reason": "anterior_from_memory",
                    }
                )
                return result
            if prior and prior.get("team"):
                result.update(
                    {
                        "resolved": True,
                        "topic_kind": "opinion",
                        "topic_team": prior["team"],
                        "rewrite": f"o que acha do {prior['team']}?",
                        "confidence": 0.75,
                        "reason": "anterior_team_from_memory",
                    }
                )
                return result
            if focus.get("topic_fixture"):
                result.update(
                    {
                        "resolved": True,
                        "topic_kind": "fixture",
                        "topic_fixture": focus["topic_fixture"],
                        "topic_team": focus.get("topic_team"),
                        "rewrite": (
                            f"me fala do confronto {focus['topic_fixture']} "
                            f"(contexto anterior da conversa)"
                        ),
                        "confidence": 0.72,
                        "reason": "anterior_same_fixture",
                    }
                )
                return result
            if focus.get("topic_team"):
                result.update(
                    {
                        "resolved": True,
                        "topic_kind": "opinion",
                        "topic_team": focus["topic_team"],
                        "rewrite": f"o que acha do {focus['topic_team']}?",
                        "confidence": 0.7,
                        "reason": "anterior_same_team",
                    }
                )
                return result
            result.update(
                {
                    "ambiguous": True,
                    "confidence": 0.35,
                    "reason": "anterior_no_focus",
                    "clarification": (
                        "Posso estar interpretando errado — você quer voltar ao "
                        "assunto anterior de qual jogo ou time?"
                    ),
                }
            )
            return result

        return result
    except Exception as exc:
        logger.warning("resolve_reference fail-open: %s", exc)
        return result


def apply_reference_resolution(
    message: str,
    ctx: dict[str, Any] | None = None,
) -> str:
    """
    Rewrite ambiguous follow-up using focus. Stores ctx['reference_resolution'].
    """
    try:
        res = resolve_reference(message, ctx)
        if ctx is not None:
            ctx["reference_resolution"] = res
        if res.get("ambiguous") and res.get("clarification"):
            if ctx is not None:
                ctx["pending_clarification"] = res["clarification"]
            logger.warning(
                "[AUDIT] ReferenceResolver: AMBIGUOUS reason=%s",
                res.get("reason"),
            )
            return message
        if res.get("resolved") and res.get("rewrite"):
            logger.warning(
                "[AUDIT] ReferenceResolver: %r → %r reason=%s conf=%.2f",
                message,
                res["rewrite"],
                res.get("reason"),
                float(res.get("confidence") or 0),
            )
            # Merge into deep_thinking hints
            if ctx is not None:
                th = dict(ctx.get("deep_thinking") or {})
                if res.get("topic_kind"):
                    th["topic_kind"] = res["topic_kind"]
                if res.get("topic_team"):
                    th["topic_team"] = res["topic_team"]
                if res.get("topic_fixture"):
                    th["topic_fixture"] = res["topic_fixture"]
                    parts = str(res["topic_fixture"]).split(" x ")
                    if len(parts) == 2:
                        th["topic_teams"] = parts
                ctx["deep_thinking"] = th
            return str(res["rewrite"])
        return message
    except Exception as exc:
        logger.warning("apply_reference_resolution fail-open: %s", exc)
        return message


def confidence_clarification_payload(
    clarification: str,
    prefs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Intelligent ambiguity — never '?'."""
    try:
        from src.conversation.presence_humanization import apply_presence_humanization

        text = apply_presence_humanization(
            clarification, prefs, family_hint="casual"
        )
    except Exception:
        text = clarification
    return {
        "intent": "conversation_assist",
        "entities": {
            "confidence_clarification": True,
            "has_analysis": False,
            "show_header": False,
            "skip_llm": True,
        },
        "executive_summary": text,
        "final_recommendation": text,
        "response_metadata": {
            "mode": "confidence_clarification",
            "source": "conversation.conversation_focus",
        },
        "knowledge_notes": [],
        "suggested_follow_ups": [],
    }
