"""
Human Conversation Engine — understand what the user meant, not only what they typed.

Additive. Fail-open.
Does NOT modify MasterIntentRouter / FollowUp / FactPolicy / LivePipeline / HIE core.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any

logger = logging.getLogger(__name__)


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


def _payload(text: str, *, kind: str, intent: str = "conversation_assist") -> dict[str, Any]:
    try:
        from src.brain import get_brain_meta

        brain = get_brain_meta()
    except Exception:
        brain = {}
    return {
        "intent": intent,
        "entities": {
            "human_conversation": True,
            "hce_kind": kind,
            "has_analysis": False,
            "show_header": False,
            "skip_llm": True,
        },
        "match": None,
        "status": None,
        "is_live": False,
        "minute": None,
        "executive_summary": text,
        "best_markets": [],
        "confidence": {
            "score": 0.0,
            "label": "insufficient",
            "explanation": "Continuidade conversacional (HCE).",
            "data_sources": ["HumanConversationEngine"],
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
        "final_recommendation": text,
        "aurora_version": "Copilot v1.0",
        "brain": brain,
        "response_metadata": {
            "mode": "human_conversation",
            "source": kind,
            "show_header": False,
        },
    }


_ANALYZE_OPEN = re.compile(
    r"("
    r"quero\s+analisar|"
    r"vamos\s+analisar|"
    r"analisar\s+um\s+jogo|"
    r"analisa\s+um\s+jogo|"
    r"quero\s+uma\s+analise|"
    r"pode\s+analisar|"
    r"bora\s+analisar"
    r")",
    re.I,
)

_HAS_FIXTURE = re.compile(
    r"\b\w+\s+[xX]\s+\w+\b|\bvs\.?\b",
    re.I,
)


def wants_analyze_without_fixture(message: str) -> bool:
    folded = _fold(message)
    if not _ANALYZE_OPEN.search(folded) and not (
        "analisar" in folded and "jogo" in folded
    ):
        return False
    if _HAS_FIXTURE.search(message or ""):
        return False
    # Has explicit two teams via "e" is ambiguous — require x/vs
    return True


def _extract_soft_entity(message: str) -> str | None:
    try:
        from src.conversation.conversational_understanding import _extract_teams

        teams = _extract_teams(_fold(message))
        if teams:
            return teams[0]
    except Exception:
        pass
    m = re.search(
        r"\b(fluminense|flamengo|botafogo|santos|corinthians|palmeiras|"
        r"sao\s+paulo|vasco|bahia|mirassol|gremio|internacional)\b",
        _fold(message),
        re.I,
    )
    if m:
        return m.group(1).title().replace("Sao Paulo", "São Paulo")
    return None


def try_human_conversation(
    message: str,
    ctx: dict[str, Any] | None,
    *,
    master_intent: str | None = None,
    existing_payload: dict[str, Any] | None = None,
    prefs: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """
    Short-circuit when we can resolve human meaning from HCE state.
    Returns payload or None (pipeline continues).
    """
    try:
        from src.conversation.conversation_expectation import (
            infer_turn_expectation,
            soft_followup_reply,
        )
        from src.conversation.human_conversation_state import (
            get_hce_state,
            note_assistant_question,
            note_sport_turn,
            update_hce_state,
        )
        from src.conversation.memory_intent_handler import (
            handle_memory_or_bankroll,
            is_bankroll_declare,
            is_memory_intent,
            is_stake_question,
        )
        from src.conversation.meta_question_handler import (
            is_meta_question,
            reply_meta_question,
        )
        from src.conversation.short_answer_resolver import (
            is_short_answer,
            resolve_short_answer,
        )

        if ctx is None:
            ctx = {}

        state = get_hce_state(ctx)
        update_hce_state(
            ctx,
            last_user_message=message,
            last_master_intent=master_intent,
        )
        state = get_hce_state(ctx)

        # 1) Meta questions — always win over generic GA / sport repeat
        if is_meta_question(message):
            text = reply_meta_question(message, state, ctx)
            update_hce_state(
                ctx,
                last_intent="meta",
                last_topic="meta",
                last_expected_action=state.get("last_expected_action") or "sport_followup",
            )
            logger.warning("[AUDIT] HCE: meta_question")
            return _payload(text, kind="meta_question", intent="conversation_assist")

        # 2) Memory / bankroll
        if is_memory_intent(message) or is_bankroll_declare(message) or is_stake_question(
            message
        ):
            mem = handle_memory_or_bankroll(message, ctx, state)
            if mem:
                fields: dict[str, Any] = {
                    "last_intent": "memory",
                    "last_topic": "bankroll",
                    "last_expected_action": mem.get("expected_action"),
                }
                if mem.get("bankroll") is not None:
                    fields["last_bankroll"] = mem["bankroll"]
                if mem.get("pending_bankroll") is not None:
                    fields["pending_bankroll"] = mem["pending_bankroll"]
                update_hce_state(ctx, **fields)
                if mem.get("pending_bankroll") is not None:
                    note_assistant_question(
                        ctx,
                        "Quer que eu salve a banca?",
                        expected_action="awaiting_bankroll_confirm",
                        topic="bankroll",
                    )
                    update_hce_state(
                        ctx, pending_bankroll=mem["pending_bankroll"], last_bankroll=mem["pending_bankroll"]
                    )
                logger.warning("[AUDIT] HCE: memory kind=%s", mem.get("kind"))
                return _payload(
                    str(mem["text"]),
                    kind=str(mem.get("kind") or "memory"),
                    intent="bankroll_review"
                    if "bankroll" in str(mem.get("kind"))
                    or "stake" in str(mem.get("kind"))
                    else "conversation_assist",
                )

        # 3) Short answers against pending expectation
        if is_short_answer(message):
            resolved = resolve_short_answer(message, state)
            if resolved:
                exp = resolved.get("expected_action")
                update_hce_state(
                    ctx,
                    last_intent="short_answer",
                    last_topic=resolved.get("topic") or state.get("last_topic"),
                    last_entity=resolved.get("entity") or state.get("last_entity"),
                    last_expected_action=exp,
                )
                if resolved.get("clear_pending") or exp is None:
                    update_hce_state(
                        ctx,
                        last_expected_action=None,
                        pending_question=None,
                        last_question=None,
                    )
                elif exp == "awaiting_fixture":
                    note_assistant_question(
                        ctx,
                        "Me diga o confronto Time A x Time B",
                        expected_action="awaiting_fixture",
                        topic="analyze_match",
                    )
                logger.warning(
                    "[AUDIT] HCE: short_answer kind=%s expected=%s",
                    resolved.get("kind"),
                    exp,
                )
                return _payload(
                    str(resolved["text"]),
                    kind=str(resolved.get("kind") or "short_answer"),
                )
            # Short answer with no thread — soft acknowledge, don't restart as help menu
            if len(_fold(message).split()) <= 2:
                text = (
                    "Certo. Estou aqui — se quiser analisar um jogo, me diga o confronto. "
                    "Se for outra coisa, pode falar."
                )
                update_hce_state(ctx, last_intent="short_loose", last_topic="social")
                logger.warning("[AUDIT] HCE: short_loose")
                return _payload(text, kind="short_loose", intent="small_talk")

        # 4) Soft sport follow-ups (e agora? / qual mercado?)
        soft = soft_followup_reply(message, state)
        if soft:
            update_hce_state(ctx, last_intent="soft_followup", last_topic="sport")
            logger.warning("[AUDIT] HCE: soft_followup")
            return _payload(soft, kind="soft_followup")

        # 4b) "qual mercado?" while still waiting for a fixture — stay in the thread
        if re.search(r"\bqual\s+mercado|melhor\s+mercado|que\s+mercado\b", _fold(message)):
            if state.get("last_expected_action") == "awaiting_fixture":
                text = (
                    "Ainda não abri a análise — preciso do confronto "
                    "(*Time A x Time B*). Aí eu falo de mercado com base nisso."
                )
                note_assistant_question(
                    ctx,
                    "Qual jogo você quer analisar?",
                    expected_action="awaiting_fixture",
                    topic="analyze_match",
                )
                logger.warning("[AUDIT] HCE: market_before_fixture")
                return _payload(text, kind="market_before_fixture")

        # 5) "quero analisar um jogo" without fixture — never "?"
        if wants_analyze_without_fixture(message):
            text = (
                "Perfeito — vamos analisar. "
                "Qual jogo? Me diga no formato *Time A x Time B* "
                "(se for ao vivo, pode acrescentar *ao vivo*)."
            )
            note_assistant_question(
                ctx,
                "Qual jogo você quer analisar?",
                expected_action="awaiting_fixture",
                topic="analyze_match",
            )
            update_hce_state(ctx, last_intent="await_fixture", last_topic="analyze_match")
            logger.warning("[AUDIT] HCE: await_fixture")
            return _payload(text, kind="await_fixture", intent="conversation_assist")

        # 6) Annotate expectation for live/team turns — do not steal sport pipeline
        exp = infer_turn_expectation(message)
        entity = _extract_soft_entity(message)
        if entity and (exp.get("live") or master_intent in {"SPORT_QUERY", "LIVE_MATCH"}):
            note_sport_turn(
                ctx,
                entity=entity,
                topic="sport",
                expected=list(exp.get("hints") or []),
                live=bool(exp.get("live")),
            )
            # Clear fixture-wait — user moved into a concrete sport thread
            update_hce_state(
                ctx,
                last_expected_action="sport_followup",
                pending_question=None,
                last_question=None,
            )
            # Let sport pipeline answer; HCE only remembered the thread
            return None

        # 7) If GA already answered math/system/small_talk well, don't override
        if existing_payload and (
            (existing_payload.get("entities") or {}).get("assistant_kind")
            in {"math", "system", "small_talk"}
        ):
            update_hce_state(
                ctx,
                last_topic="social"
                if (existing_payload.get("entities") or {}).get("assistant_kind")
                == "small_talk"
                else "general",
                last_intent=str(
                    (existing_payload.get("entities") or {}).get("assistant_kind")
                ),
            )
            return None

        # 8) Override weak generic GA when we have sport thread + vague general
        if existing_payload and (
            (existing_payload.get("entities") or {}).get("assistant_kind") == "general"
        ):
            if state.get("last_expected_action") == "awaiting_fixture":
                text = (
                    "Ainda estou no modo análise — me diga o confronto "
                    "*Time A x Time B* quando quiser."
                )
                return _payload(text, kind="resume_await_fixture")

        return None
    except Exception as exc:
        logger.warning("try_human_conversation fail-open: %s", exc)
        return None


def note_hce_after_response(
    ctx: dict[str, Any] | None,
    message: str,
    payload: dict[str, Any] | None,
) -> None:
    """Passive: remember what Aurora just said / asked."""
    try:
        if not isinstance(ctx, dict) or not isinstance(payload, dict):
            return
        from src.conversation.human_conversation_state import (
            note_assistant_question,
            update_hce_state,
        )

        text = str(
            payload.get("executive_summary") or payload.get("final_recommendation") or ""
        )
        ents = dict(payload.get("entities") or {})
        kind = ents.get("hce_kind") or ents.get("assistant_kind") or ""

        # Only explicit HCE await — never infer from capabilities copy mentioning "Time A x Time B"
        if ents.get("hce_kind") in {"await_fixture", "short_await_fixture", "resume_await_fixture"}:
            note_assistant_question(
                ctx,
                "Qual jogo você quer analisar?",
                expected_action="awaiting_fixture",
                topic="analyze_match",
            )
            return

        # Capture match from analysis payloads
        match = payload.get("match") or {}
        home = match.get("home") or ents.get("home")
        away = match.get("away") or ents.get("away")
        if home and away:
            from src.conversation.human_conversation_state import note_sport_turn

            note_sport_turn(
                ctx,
                entity=f"{home} x {away}",
                topic="sport",
                live=bool(payload.get("is_live")),
            )
            return

        update_hce_state(
            ctx,
            last_assistant_kind=kind,
            last_assistant_preview=text[:180],
        )
    except Exception as exc:
        logger.warning("note_hce_after_response fail-open: %s", exc)
