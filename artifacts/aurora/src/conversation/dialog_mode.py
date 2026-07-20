"""
P1-B — Dialog mode resolver + anti-loop policy.

Exclusive turn modes for NC/GA redesign. Does NOT modify frozen AEP modules;
may read A.18/A.20 helpers fail-open.

Modes: SPORT | CLARIFICATION | IDENTITY | SMALL_TALK | FICTION | RESEARCH |
       UTILITY | REPAIR | UNKNOWN
GENERAL is deprecated and never returned.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any

logger = logging.getLogger(__name__)

CTX_KEY = "dialog_mode_state"

MODES = frozenset(
    {
        "SPORT",
        "CLARIFICATION",
        "IDENTITY",
        "SMALL_TALK",
        "FICTION",
        "RESEARCH",
        "UTILITY",
        "REPAIR",
        "UNKNOWN",
    }
)

_STICKY = "Entendi. Posso te ajudar"

_FICTION = re.compile(
    r"(?:"
    r"\bgoku\b|\bnaruto\b|\bvoldemort\b|\bbatman\b|\bsuperman\b|"
    r"\bpikachu\b|\bluffy\b|\bsaitama\b|\bthanos\b|"
    r"harry\s+potter|\bpotter\b|"
    r"goku\s*[xvs]+\s*naruto|"
    r"harry\s+potter\s*[xvs]+\s*voldemort|"
    r"batman\s*[xvs]+\s*superman"
    r")",
    re.I,
)

_IDENTITY = re.compile(
    r"^(?:"
    r"(?:qual\s+(?:e|é)\s+(?:o\s+)?seu\s+nome|seu\s+nome\??|"
    r"(?:voce|você)\s+(?:e|é)\s+a\s+aurora|"
    r"o\s+que\s+(?:voce|você)\s+faz|"
    r"o\s+que\s+sabe\s+fazer|"
    r"suas?\s+funcionalidades|"
    r"me\s+explica\s+o\s+que\s+(?:voce|você)\s+(?:e|é))"
    r")"
    r"[\s?!.,]*$",
    re.I,
)

_SMALL = re.compile(
    r"^(?:"
    r"(?:oi|ola|olá|e\s*ai|e\s*aí|fala|hey|hi|hello)|"
    r"bom\s+dia|boa\s+(?:tarde|noite)|"
    r"tudo\s+bem|td\s+bem|"
    r"obrigad\w*|valeu|thanks"
    r")"
    r"[\s?!.,]*$",
    re.I,
)

_FRUST = re.compile(
    r"(?:"
    r"\baff+\b|\bkkkk+\b|"
    r"ah\s+t[aá](?:[,\s]+genial)?|"
    r"nao\s+foi\s+isso|não\s+foi\s+isso|"
    r"pensa\s+um\s+pouco|preste\s+atencao|preste\s+atenção|"
    r"isso\s+esta\s+errado|isso\s+está\s+errado|"
    r"claro\s+n[eé]|"
    r"voce\s+nao\s+entendeu|você\s+não\s+entendeu|"
    r"para\s+de\s+repet|"
    r"parece\s+um\s+robo|parece\s+um\s+robô|"
    r"ja\s+falei|já\s+falei|"
    r"responde\s+direito|"
    r"voce\s+esta\s+me\s+frustr|você\s+está\s+me\s+frustr"
    r")",
    re.I,
)

_MATH = re.compile(
    r"\d+\s*[\+\-\*\/x×÷]\s*\d+",
    re.I,
)

_TIME = re.compile(
    r"\b(?:que\s+horas\s+(?:sao|são)|hora\s+atual|me\s+diga\s+as\s+horas)\b",
    re.I,
)


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


def _blob(ctx: dict[str, Any]) -> dict[str, Any]:
    b = ctx.get(CTX_KEY)
    if not isinstance(b, dict):
        b = {
            "last_mode": None,
            "last_signature": None,
            "clarify_streak": 0,
            "identity_streak": 0,
            "unknown_streak": 0,
            "awaiting_clarification": False,
            # After FICTION reply: short sport FUs must clarify, not pretend continuity
            "post_fiction_release": False,
            "counters": {
                "mode_resolved": 0,
                "anti_loop_forced": 0,
                "clarify_cap_unknown": 0,
                "sticky_blocked": 0,
            },
        }
        ctx[CTX_KEY] = b
    b.setdefault("counters", {})
    b.setdefault("post_fiction_release", False)
    for k in (
        "mode_resolved",
        "anti_loop_forced",
        "clarify_cap_unknown",
        "sticky_blocked",
    ):
        b["counters"].setdefault(k, 0)
    return b


def _bump(ctx: dict[str, Any], key: str) -> None:
    try:
        _blob(ctx)["counters"][key] = int(_blob(ctx)["counters"].get(key) or 0) + 1
    except Exception:
        pass


def is_fiction_message(message: str | None) -> bool:
    return bool(_FICTION.search(_fold(message or "")))


def is_identity_message(message: str | None) -> bool:
    return bool(_IDENTITY.match(_fold(message or "")))


def is_small_talk_message(message: str | None) -> bool:
    return bool(_SMALL.match(_fold(message or "")))


def is_frustration_message(message: str | None) -> bool:
    folded = _fold(message or "")
    if not folded:
        return False
    if _FRUST.search(folded):
        return True
    if re.fullmatch(r"k{3,}", folded):
        return True
    return False


def _has_sport_frame(ctx: dict[str, Any] | None) -> bool:
    if not isinstance(ctx, dict):
        return False
    if isinstance(ctx.get("last_match"), str) and ctx["last_match"].strip():
        return True
    try:
        from src.conversation.sport_continuity_guard import sport_anchor_active

        if sport_anchor_active(ctx):
            return True
    except Exception:
        pass
    cont = ctx.get("conversation_continuity")
    if isinstance(cont, dict) and cont.get("active"):
        return True
    return False


def _is_sport_short_fu(message: str | None) -> bool:
    try:
        from src.conversation.sport_continuity_guard import is_sport_short_followup

        return bool(is_sport_short_followup(message))
    except Exception:
        folded = _fold(message or "")
        return folded.rstrip("?!") in {
            "mercados",
            "xg",
            "pressao",
            "pressão",
            "e o outro",
            "estatisticas",
            "estatísticas",
        }


def _is_ambiguous(message: str | None, ctx: dict[str, Any] | None) -> bool:
    try:
        from src.conversation.ambiguous_context_guard import is_ambiguous_opener

        return bool(is_ambiguous_opener(message, ctx))
    except Exception:
        return False


def _is_real_fixture(message: str | None) -> bool:
    folded = _fold(message or "")
    if not folded or _FICTION.search(folded):
        return False
    return bool(
        re.search(
            r"\b[\wÀ-ÿ.''-]{2,}\s+(?:x|vs\.?|versus)\s+[\wÀ-ÿ.''-]{2,}\b",
            folded,
            re.I,
        )
    )


def resolve_dialog_mode(
    message: str,
    ctx: dict[str, Any] | None = None,
    *,
    master_intent: str | None = None,
) -> str:
    """
    Deterministic mode for this turn (P1-A priority order).
    Never returns GENERAL.

    P3 perception repairs (human-facing only; no sports engines):
    - short msgs (<=3 tokens) infer previous goal → SMALL_TALK (assume)
    - frustration → REPAIR (menus disabled downstream)
    - clarify/unknown expire after cap → ASSUME via SMALL_TALK
    - anti-sticky: do not ping-pong REPAIR↔CLARIFICATION
    """
    if not isinstance(ctx, dict):
        ctx = {}
    blob = _blob(ctx)
    intent = (master_intent or "").upper()
    folded = _fold(message)

    # Perception state (fail-open)
    _pcs = None
    _short = False
    _frust = is_frustration_message(message)
    try:
        from src.conversation.perception_conversation_state import (
            clarify_or_unknown_expired as _pcs_expired,
            current_goal_text as _pcs_goal,
            is_short_message as _pcs_short,
            menus_disabled as _pcs_menus_off,
            note_user_message as _pcs_note,
            should_assume_after_clarify as _pcs_assume,
        )

        _pcs_note(ctx, message)
        _short = _pcs_short(message)
        _pcs = True
        _menus_off = _pcs_menus_off(ctx) or _frust
        _assume = _pcs_assume(ctx) or _pcs_expired(ctx)
        _has_goal = bool(_pcs_goal(ctx))
    except Exception:
        _menus_off = _frust
        _assume = int(blob.get("clarify_streak") or 0) >= 2
        _has_goal = False
        _short = len((folded or "").split()) <= 3 and bool(folded)

    # Sport short FU with frame
    if _has_sport_frame(ctx) and _is_sport_short_fu(message):
        mode = "SPORT"
    elif is_fiction_message(message):
        mode = "FICTION"
    # After fiction wipe: short sport FUs cannot reuse a frame — clarify
    # (unless frustration / assume-cap — never sport menu under frustration)
    elif blob.get("post_fiction_release") and _is_sport_short_fu(message):
        mode = "SMALL_TALK" if (_menus_off or _assume) else "CLARIFICATION"
    elif intent in {"MATH_QUERY"} or (_MATH.search(folded or "") and len((folded or "").split()) <= 8):
        mode = "UTILITY"
    elif intent in {"UTILITY_QUERY"} or _TIME.search(folded or ""):
        mode = "UTILITY"
    elif intent in {"SYSTEM_QUERY", "CAPABILITIES_QUERY"} or is_identity_message(message):
        mode = "IDENTITY"
    elif _frust or is_frustration_message(message):
        mode = "REPAIR"
    elif _short and _has_goal:
        # Aggressive inference: <=3 tokens → continue previous goal
        mode = "SMALL_TALK"
        _bump(ctx, "short_infer")
        try:
            from src.conversation.perception_conversation_state import (
                get_perception_state as _gps,
            )

            _gps(ctx)["counters"]["infer_short"] = int(
                _gps(ctx)["counters"].get("infer_short") or 0
            ) + 1
        except Exception:
            pass
    elif intent == "SMALL_TALK" or is_small_talk_message(message):
        mode = "SMALL_TALK"
    elif _is_real_fixture(message):
        mode = "SPORT"
    elif _menus_off and _is_ambiguous(message, ctx):
        # Frustration / menus disabled: never sport clarify menu
        mode = "REPAIR" if _frust else "SMALL_TALK"
        _bump(ctx, "menu_blocked")
    elif _is_ambiguous(message, ctx):
        mode = "CLARIFICATION"
    elif intent == "GENERAL_CHAT":
        mode = "CLARIFICATION" if len((folded or "").split()) <= 6 else "UNKNOWN"
    else:
        mode = "UNKNOWN"

    # Clarify / UNKNOWN expire → assume (SMALL_TALK content path)
    if mode in {"CLARIFICATION", "UNKNOWN"} and _assume:
        mode = "SMALL_TALK"
        _bump(ctx, "clarify_expired")
        try:
            from src.conversation.perception_conversation_state import (
                get_perception_state as _gps2,
            )

            _gps2(ctx)["counters"]["clarify_expired"] = int(
                _gps2(ctx)["counters"].get("clarify_expired") or 0
            ) + 1
            _gps2(ctx)["counters"]["assume_clarify"] = int(
                _gps2(ctx)["counters"].get("assume_clarify") or 0
            ) + 1
        except Exception:
            pass

    # Legacy clarify cap: 3rd underspec → expire to assume (not UNKNOWN ping-pong)
    if mode == "CLARIFICATION" and int(blob.get("clarify_streak") or 0) >= 2:
        mode = "SMALL_TALK"
        _bump(ctx, "clarify_cap_unknown")

    # Anti-loop identity streak → assume chat, not clarify menu
    if mode == "IDENTITY" and int(blob.get("identity_streak") or 0) >= 1:
        mode = "SMALL_TALK"
        _bump(ctx, "anti_loop_forced")
    if mode == "UNKNOWN" and int(blob.get("unknown_streak") or 0) >= 1:
        mode = "SMALL_TALK"
        _bump(ctx, "anti_loop_forced")

    # Same signature: never force CLARIFICATION from REPAIR/UNKNOWN (sticky menus)
    sig = f"{mode}"
    if (
        sig == blob.get("last_signature")
        and mode in {"SMALL_TALK", "REPAIR", "UNKNOWN", "IDENTITY"}
    ):
        mode = "SMALL_TALK"
        _bump(ctx, "sticky_blocked")

    # Track perception state name
    try:
        from src.conversation.perception_conversation_state import note_state as _pcs_ns

        _pcs_ns(ctx, mode)
    except Exception:
        pass

    _bump(ctx, "mode_resolved")
    return mode


def note_mode_emitted(
    ctx: dict[str, Any] | None,
    mode: str,
    *,
    signature: str | None = None,
) -> None:
    if not isinstance(ctx, dict):
        return
    blob = _blob(ctx)
    blob["last_mode"] = mode
    blob["last_signature"] = signature or mode
    if mode == "FICTION":
        blob["post_fiction_release"] = True
    elif mode == "SPORT":
        blob["post_fiction_release"] = False
    if mode == "CLARIFICATION":
        blob["clarify_streak"] = int(blob.get("clarify_streak") or 0) + 1
        blob["awaiting_clarification"] = True
        blob["identity_streak"] = 0
        blob["unknown_streak"] = 0
    elif mode == "IDENTITY":
        blob["identity_streak"] = int(blob.get("identity_streak") or 0) + 1
        blob["clarify_streak"] = 0
        blob["awaiting_clarification"] = False
    elif mode == "UNKNOWN":
        blob["unknown_streak"] = int(blob.get("unknown_streak") or 0) + 1
        blob["clarify_streak"] = 0
        blob["awaiting_clarification"] = False
    elif mode == "SPORT":
        blob["clarify_streak"] = 0
        blob["awaiting_clarification"] = False
        blob["identity_streak"] = 0
        blob["unknown_streak"] = 0
    else:
        blob["clarify_streak"] = 0
        blob["awaiting_clarification"] = False
        if mode != "IDENTITY":
            blob["identity_streak"] = 0
        if mode != "UNKNOWN":
            blob["unknown_streak"] = 0


def _base_payload(text: str, *, intent: str, mode: str, owner: str) -> dict[str, Any]:
    try:
        from src.brain import get_brain_meta

        brain = get_brain_meta()
    except Exception:
        brain = {}
    return {
        "intent": intent,
        "match": None,
        "status": None,
        "is_live": False,
        "minute": None,
        "executive_summary": text,
        "final_recommendation": text,
        "best_markets": [],
        "confidence": {
            "score": 0.0,
            "label": "insufficient",
            "explanation": f"Dialog mode {mode} (P1-B).",
            "data_sources": ["DialogMode"],
        },
        "risk": {"level": "Unknown", "flags": [], "invalidation_conditions": []},
        "bankroll_recommendation": {
            "recommended_stake_pct": 0.0,
            "method": "quarter-Kelly",
            "examples": {},
            "no_bet": True,
            "reasoning": "",
        },
        "positive_factors": [],
        "negative_factors": [],
        "historical_references": [],
        "knowledge_notes": [],
        "aurora_version": "Copilot v1.0",
        "brain": brain,
        "response_metadata": {"mode": mode.lower(), "source": "dialog_mode"},
        "entities": {
            "dialog_mode": mode,
            "clarification_mode": mode == "CLARIFICATION",
            "response_owner": owner,
            "turn_owner": mode,
            "rewrite_locked": True,
            "has_analysis": False,
            "show_header": False,
            "skip_llm": True,
            "p1_dialog_mode": True,
        },
    }


def build_clarification_text(
    message: str | None,
    ctx: dict[str, Any] | None = None,
) -> str:
    # Frustration / cap / goal → assume answer, never sports menu
    try:
        from src.conversation.perception_conversation_state import (
            build_goal_answer,
            clarify_or_unknown_expired,
            current_goal_text,
            menus_disabled,
        )

        if menus_disabled(ctx) or clarify_or_unknown_expired(ctx) or current_goal_text(ctx):
            return build_goal_answer(ctx, reason="assume")
    except Exception:
        pass
    # Prefer A.20 wording when available (read-only)
    try:
        from src.conversation.ambiguous_context_guard import (
            build_clarification_text as _a20,
        )

        return _a20(message)
    except Exception:
        pass
    return (
        "Não quero te responder genérico.\n\n"
        "Me diga em uma frase o foco — jogo, time ou só conversa. "
        "Sem lista longa de opções."
    )


def build_unknown_text(ctx: dict[str, Any] | None = None) -> str:
    """UNKNOWN expires into goal assume — no sports option menu."""
    try:
        from src.conversation.perception_conversation_state import (
            build_goal_answer,
            clarify_or_unknown_expired,
            current_goal_text,
            menus_disabled,
        )

        if menus_disabled(ctx) or clarify_or_unknown_expired(ctx) or current_goal_text(ctx):
            return build_goal_answer(ctx, reason="assume")
    except Exception:
        pass
    return (
        "Vou seguir em modo conversa pra não travar.\n\n"
        "Me diga o foco em uma frase — sem lista de opções."
    )


def build_fiction_text(message: str | None) -> str:
    return (
        "Esse confronto parece **ficção / hipotético** — "
        "não trato como partida real de futebol.\n\n"
        "Se quiser análise esportiva, me diga um jogo real "
        "(ex.: Time A x Time B). Se for só brincadeira, pode falar o que você quer fazer."
    )


def build_repair_text(ctx: dict[str, Any] | None = None) -> str:
    """Repair must answer — never sport triage menus."""
    try:
        from src.conversation.perception_conversation_state import (
            build_goal_answer,
            should_reanswer_after_repair,
        )

        reason = (
            "repair_reanswer"
            if should_reanswer_after_repair(ctx)
            else "repair_reanswer"
        )
        return build_goal_answer(ctx, reason=reason)
    except Exception:
        return (
            "Sem menu — vamos retomar o que você pediu e avançar. "
            "Me corrige em uma frase só se eu sair do fio."
        )


def build_mode_payload(
    message: str,
    mode: str,
    ctx: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Build reply payload for non-SPORT modes. SPORT → None (pipeline owns)."""
    if mode == "SPORT":
        return None
    used_goal = False
    if mode == "CLARIFICATION":
        text = build_clarification_text(message, ctx)
        owner = "clarification_policy"
        intent = "clarification"
    elif mode == "UNKNOWN":
        text = build_unknown_text(ctx)
        owner = "unknown_policy"
        intent = "clarification"
    elif mode == "FICTION":
        text = build_fiction_text(message)
        owner = "fiction_policy"
        intent = "clarification"
    elif mode == "REPAIR":
        text = build_repair_text(ctx)
        owner = "repair_policy"
        intent = "conversation_repair"
    elif mode == "IDENTITY":
        try:
            from src.conversation.assistant_capabilities import (
                build_capabilities_payload,
                is_capabilities_ask,
            )

            if is_capabilities_ask(message):
                payload = build_capabilities_payload(message)
                if isinstance(payload, dict):
                    ents = dict(payload.get("entities") or {})
                    ents["dialog_mode"] = "IDENTITY"
                    ents["p1_dialog_mode"] = True
                    payload["entities"] = ents
                    if isinstance(ctx, dict):
                        note_mode_emitted(ctx, "IDENTITY", signature="IDENTITY:cap")
                    return payload
        except Exception:
            pass
        try:
            from src.conversation.general_assistant import reply_system

            text = reply_system(message)
        except Exception:
            text = "Eu sou a **Aurora**. Em que posso ajudar?"
        owner = "identity_policy"
        intent = "identity"
    elif mode == "SMALL_TALK":
        try:
            from src.conversation.perception_conversation_state import (
                build_goal_answer,
                current_goal_text,
                is_short_message,
                should_assume_after_clarify,
            )

            if (
                is_short_message(message)
                or should_assume_after_clarify(ctx)
                or (
                    current_goal_text(ctx)
                    and not is_small_talk_message(message)
                )
            ):
                text = build_goal_answer(
                    ctx,
                    reason="short_infer" if is_short_message(message) else "assume",
                )
                used_goal = True
            else:
                text = None
        except Exception:
            text = None
        if not used_goal:
            try:
                from src.conversation.general_assistant import reply_small_talk

                text = reply_small_talk(message)
            except Exception:
                text = "Oi! Pode falar normalmente — estou aqui."
        # Sticky GA → goal answer / soft chat — NEVER clarification menu
        if (text or "").strip().startswith(_STICKY):
            if isinstance(ctx, dict):
                _bump(ctx, "sticky_blocked")
            try:
                from src.conversation.perception_conversation_state import (
                    build_goal_answer as _bga,
                )

                text = _bga(ctx, reason="assume")
                used_goal = True
            except Exception:
                text = "Pode falar normalmente — sem menu. O que você quer continuar?"
        owner = "natural_conversation"
        intent = "conversation_assist" if used_goal else "small_talk"
    elif mode == "RESEARCH":
        try:
            from src.conversation.perception_conversation_state import (
                build_goal_answer,
                menus_disabled,
            )

            if menus_disabled(ctx):
                text = build_goal_answer(ctx, reason="assume")
                owner = "natural_conversation"
                intent = "conversation_assist"
            else:
                text = (
                    "Para pesquisar com precisão, me diga o foco em uma frase "
                    "(time, notícia ou jogo) — sem lista de opções."
                )
                owner = "clarification_policy"
                intent = "clarification"
                mode = "CLARIFICATION"
        except Exception:
            text = (
                "Para pesquisar com precisão, me diga o foco em uma frase "
                "(time, notícia ou jogo) — sem lista de opções."
            )
            owner = "clarification_policy"
            intent = "clarification"
            mode = "CLARIFICATION"
    elif mode == "UTILITY":
        return None  # GA utilities handle
    else:
        text = build_unknown_text(ctx)
        owner = "unknown_policy"
        intent = "clarification"
        mode = "UNKNOWN"

    # Strip residual menus / sticky Entendi — never redirect to clarify menu
    if _STICKY.lower() in (text or "").lower():
        if isinstance(ctx, dict):
            _bump(ctx, "sticky_blocked")
        try:
            from src.conversation.perception_conversation_state import build_goal_answer

            text = build_goal_answer(ctx, reason="assume")
        except Exception:
            text = "Vamos avançar sem template. O que você quer continuar?"

    try:
        from src.conversation.perception_conversation_state import anti_sticky_reply

        text = anti_sticky_reply(ctx, str(text or ""))
    except Exception:
        pass

    payload = _base_payload(str(text or ""), intent=intent, mode=mode, owner=owner)
    if isinstance(ctx, dict):
        note_mode_emitted(ctx, mode, signature=f"{mode}:{intent}")
        ents = dict(payload.get("entities") or {})
        ents["dialog_mode_counters"] = dict(_blob(ctx).get("counters") or {})
        if mode == "FICTION" or owner == "fiction_policy":
            ents["entity_invalid"] = True
            ents["fixture_quality"] = "INVALID"
            ents["fiction_topic"] = True
            payload["fixture_quality"] = "INVALID"
        if mode in {"CLARIFICATION", "UNKNOWN", "REPAIR"} and _blob(ctx).get(
            "post_fiction_release"
        ):
            ents["post_fiction_clarify"] = True
            ents["context_expected_waived"] = True
        if mode == "REPAIR":
            ents["repair_mode"] = True
            ents["conversation_repair"] = True
            ents["repair_must_answer"] = True
        payload["entities"] = ents
        try:
            from src.conversation.perception_conversation_state import stamp_entities

            stamp_entities(payload, ctx)
        except Exception:
            pass
    else:
        if mode == "FICTION":
            ents = dict(payload.get("entities") or {})
            ents["entity_invalid"] = True
            ents["fixture_quality"] = "INVALID"
            ents["fiction_topic"] = True
            payload["entities"] = ents
            payload["fixture_quality"] = "INVALID"
        if mode == "REPAIR":
            ents = dict(payload.get("entities") or {})
            ents["repair_mode"] = True
            ents["conversation_repair"] = True
            ents["repair_must_answer"] = True
            payload["entities"] = ents
    return payload


def try_dialog_mode_claim(
    message: str,
    ctx: dict[str, Any] | None = None,
    *,
    master_intent: str | None = None,
) -> dict[str, Any] | None:
    """
    Early/late claim for non-sport dialog modes.
    Returns None for SPORT/UTILITY (other owners).
    """
    try:
        mode = resolve_dialog_mode(message, ctx, master_intent=master_intent)
        if mode in {"SPORT", "UTILITY"}:
            return None
        return build_mode_payload(message, mode, ctx)
    except Exception as exc:
        logger.warning("dialog_mode claim fail-open: %s", exc)
        return None


def progress_act_text(message: str | None = None, ctx: dict[str, Any] | None = None) -> str:
    """NRF / anti-sticky regenerate — never Entendi / never sports menu."""
    return build_unknown_text(ctx)
