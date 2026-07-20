"""
Phase 8.2-A / 8.4-A.9 — Conversation Repair (isolated).

Detects human correction / frustration signals and answers in repair mode
instead of falling through to GeneralAssistant.reply_general().

Phase 8.4-A.9: on repair, reclassify the previous user question and allow
intent switch (e.g. wrong general_chat → assistant_capabilities).

Fail-open. Does not touch ownership / confidence / sports / 7.9 modules.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any

logger = logging.getLogger(__name__)

CTX_KEY = "repair_memory"

_REPAIR = re.compile(
    r"("
    r"nao\s+foi\s+(?:isso|essa|este|o\s+que)|"
    r"nao\s+era\s+(?:isso|essa|este)|"
    r"nao\s+(?:e|eh|é)\s+(?:isso|essa)|"
    r"voce\s+nao\s+entendeu|"
    r"nao\s+(?:voce\s+)?entendeu|"
    r"nao\s+entendeu\s+o\s+que|"
    r"pensa\s+um\s+pouco|"
    r"preste\s+atencao|"
    r"presta\s+atencao|"
    r"\baff+\b|"
    r"\breleia\b|"
    r"agora\s+entendeu|"
    r"voce\s+esta\s+em\s+loop|"
    r"para+a*\s+de\s+(?:repet|fica)|"
    r"para\s+de\s+fica(?:r)?\s+em\s+loop|"
    r"voce\s+interpretou\s+errado|"
    r"interpretou\s+errado|"
    r"voce\s+errou|"
    r"isso\s+nao\s+(?:e|eh|é)\s+o\s+que|"
    r"parece\s+um\s+robo|"
    r"responde\s+direito|"
    r"ja\s+falei|"
    r"isso\s+esta\s+errado|"
    r"voce\s+esta\s+me\s+frustr"
    r")",
    re.I,
)

_MATCH_OPINION = re.compile(
    r"("
    r"\bachou\b|\bopiniao\b|"
    r"o\s+que\s+(?:voce\s+)?acha|"
    r"ultimo\s+jogo|ontem|"
    r"partida"
    r")",
    re.I,
)

_TEAM_PAT = re.compile(
    r"\b("
    r"fluminense|flamengo|botafogo|palmeiras|corinthians|"
    r"sao\s+paulo|santos|vasco|gremio|internacional|"
    r"atletico\s+mineiro|cruzeiro|bahia|fortaleza|"
    r"bragantino|cuiaba|juventude|vitoria|mirassol"
    r")\b",
    re.I,
)

_TEAM_TITLE = {
    "fluminense": "Fluminense",
    "flamengo": "Flamengo",
    "botafogo": "Botafogo",
    "palmeiras": "Palmeiras",
    "corinthians": "Corinthians",
    "sao paulo": "São Paulo",
    "santos": "Santos",
    "vasco": "Vasco",
    "gremio": "Grêmio",
    "internacional": "Internacional",
    "atletico mineiro": "Atlético Mineiro",
    "cruzeiro": "Cruzeiro",
    "bahia": "Bahia",
    "fortaleza": "Fortaleza",
    "bragantino": "Bragantino",
    "cuiaba": "Cuiabá",
    "juventude": "Juventude",
    "vitoria": "Vitória",
    "mirassol": "Mirassol",
}


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


def is_repair_signal(message: str) -> bool:
    return bool(_REPAIR.search(_fold(message)))


def _title_team(raw: str) -> str:
    key = _fold(raw)
    return _TEAM_TITLE.get(key) or (raw[:1].upper() + raw[1:] if raw else raw)


def _extract_team_from_text(text: str) -> str | None:
    m = _TEAM_PAT.search(_fold(text or ""))
    if not m:
        return None
    return _title_team(m.group(1))


def _extract_team_from_payload(payload: dict[str, Any] | None) -> str | None:
    if not isinstance(payload, dict):
        return None
    ents = dict(payload.get("entities") or {})
    team = ents.get("team")
    if isinstance(team, str) and team.strip():
        return team.strip()
    teams = ents.get("teams")
    if isinstance(teams, (list, tuple)) and teams:
        t0 = teams[0]
        if isinstance(t0, str) and t0.strip():
            return t0.strip()
    match = payload.get("match") if isinstance(payload.get("match"), dict) else {}
    for key in ("home", "away"):
        val = match.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def get_repair_memory(ctx: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(ctx, dict):
        return {}
    raw = ctx.get(CTX_KEY)
    return dict(raw) if isinstance(raw, dict) else {}


def note_repair_memory(
    ctx: dict[str, Any] | None,
    message: str,
    payload: dict[str, Any] | None,
) -> None:
    """Minimal sticky memory for repair only: last Q, last team, last reply, intent."""
    if not isinstance(ctx, dict):
        return
    try:
        mem = get_repair_memory(ctx)
        text = ""
        if isinstance(payload, dict):
            text = str(
                payload.get("executive_summary")
                or payload.get("final_recommendation")
                or ""
            ).strip()

        if is_repair_signal(message):
            mem["repair_active"] = True
            if text:
                mem["last_assistant_reply"] = text[:240]
            ctx[CTX_KEY] = mem
            return

        mem["repair_active"] = False
        q = (message or "").strip()
        if q:
            mem["last_user_question"] = q[:240]
        if isinstance(payload, dict):
            prev_intent = str(payload.get("intent") or "").strip()
            if prev_intent:
                mem["last_intent"] = prev_intent
            ents = payload.get("entities") or {}
            if isinstance(ents, dict) and ents.get("assistant_kind"):
                mem["last_assistant_kind"] = ents.get("assistant_kind")
        team = (
            _extract_team_from_payload(payload)
            or _extract_team_from_text(message)
            or mem.get("last_team")
        )
        if isinstance(team, str) and team.strip():
            mem["last_team"] = team.strip()
        if text:
            mem["last_assistant_reply"] = text[:240]
        ctx[CTX_KEY] = mem
    except Exception as exc:
        logger.warning("note_repair_memory fail-open: %s", exc)


def _try_reclassify_previous(ctx: dict[str, Any] | None) -> dict[str, Any] | None:
    """
    Phase 8.4-A.9 — recover last user question and re-run intent classification.
    Returns a new payload when a better intent is available (capabilities first).
    """
    mem = get_repair_memory(ctx)
    last_q = str(mem.get("last_user_question") or "").strip()
    if not last_q:
        return None
    previous_intent = str(mem.get("last_intent") or "unknown")

    try:
        from src.conversation.assistant_capabilities import (
            build_capabilities_payload,
            is_capabilities_ask,
        )

        if is_capabilities_ask(last_q):
            payload = build_capabilities_payload(
                last_q,
                repair_reclassified=True,
                previous_intent=previous_intent,
            )
            ents = dict(payload.get("entities") or {})
            ents["conversation_repair"] = True
            ents["repair_mode"] = True
            payload["entities"] = ents
            logger.warning(
                "[AUDIT] ConversationRepair: RECLASSIFIED %r → assistant_capabilities "
                "prev=%r",
                last_q[:60],
                previous_intent,
            )
            return payload
    except Exception as exc:
        logger.warning("repair capabilities reclass skipped (%s)", exc)

    # Broader reclassify via MasterIntent (identity / help)
    try:
        from src.conversation.master_intent_router import classify_master_intent

        mi = classify_master_intent(last_q)
        if mi.intent == "CAPABILITIES_QUERY":
            from src.conversation.assistant_capabilities import build_capabilities_payload

            payload = build_capabilities_payload(
                last_q,
                repair_reclassified=True,
                previous_intent=previous_intent,
            )
            ents = dict(payload.get("entities") or {})
            ents["conversation_repair"] = True
            ents["repair_mode"] = True
            payload["entities"] = ents
            return payload
        if mi.intent == "SYSTEM_QUERY":
            from src.conversation.general_assistant import try_general_assistant

            ga = try_general_assistant(last_q, "SYSTEM_QUERY", ctx)
            if isinstance(ga, dict):
                ents = dict(ga.get("entities") or {})
                ents["conversation_repair"] = True
                ents["repair_mode"] = True
                ents["repair_reclassified"] = True
                ents["previous_intent"] = previous_intent
                ents["new_intent"] = ga.get("intent")
                ga["entities"] = ents
                logger.warning(
                    "[AUDIT] ConversationRepair: RECLASSIFIED %r → %s prev=%r",
                    last_q[:60],
                    ga.get("intent"),
                    previous_intent,
                )
                return ga
    except Exception as exc:
        logger.warning("repair master reclass skipped (%s)", exc)

    return None


def _build_repair_reply(message: str, ctx: dict[str, Any] | None) -> str:
    """
    Repair must ANSWER the prior goal — never sport triage menus.
    repair_count > 1 → forced re-answer from perception state.
    """
    try:
        from src.conversation.perception_conversation_state import (
            build_goal_answer,
            note_state,
            note_user_message,
            should_reanswer_after_repair,
            strip_menus,
        )

        note_user_message(ctx, message)
        note_state(ctx, "REPAIR")
        # Always contentful answer from goal; cap just strengthens wording
        text = build_goal_answer(
            ctx,
            reason="repair_reanswer",
        )
        if should_reanswer_after_repair(ctx):
            text = "Sem perguntar de novo.\n\n" + text
        return strip_menus(text)
    except Exception:
        pass

    mem = get_repair_memory(ctx)
    team = mem.get("last_team")
    if not isinstance(team, str) or not team.strip():
        team = _extract_team_from_text(mem.get("last_user_question") or "") or None
    last_q = str(mem.get("last_user_question") or "").strip()

    # Fallback answer path (still no menus)
    if team and last_q:
        return (
            f"Sem menu — retomando: você falou de {team} (“{last_q[:100]}”). "
            f"Sobre o {team}, te respondo em conversa direta (opinião/contexto), "
            "sem inventar placar ou odd. O que priorizar: forma, rivalidade ou sensação?"
        )
    if last_q:
        return (
            f"Sem menu — retomando o que você pediu: “{last_q[:140]}”. "
            "Vou responder em cima disso. Se não for isso, me corrige em uma frase."
        )
    if team:
        return (
            f"Sem menu — voltando ao {team}. Te dou uma leitura conversacional "
            "sem inventar número. Qual o foco?"
        )
    return (
        "Sem menu — vou avançar com o que já temos na conversa. "
        "Me diga só o foco em uma frase."
    )


def _payload(text: str) -> dict[str, Any]:
    try:
        from src.brain import get_brain_meta

        brain = get_brain_meta()
    except Exception:
        brain = {}
    return {
        "intent": "conversation_repair",
        "entities": {
            "conversation_repair": True,
            "human_conversation": True,
            "hce_kind": "conversation_repair",
            "assistant_kind": "conversation_repair",
            "has_analysis": False,
            "show_header": False,
            "skip_llm": True,
            "repair_mode": True,
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
            "explanation": "Modo repair conversacional (correção humana).",
            "data_sources": ["ConversationRepair"],
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
            "mode": "conversation_repair",
            "source": "conversation_repair",
            "show_header": False,
        },
    }


def try_conversation_repair(
    message: str,
    ctx: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """
    If the user signals correction/frustration, reclassify prior question when
    possible; otherwise return a repair clarification payload.
    """
    try:
        if not is_repair_signal(message):
            return None

        reclass = _try_reclassify_previous(ctx)
        if isinstance(reclass, dict):
            try:
                from src.conversation.pipeline_trace import trace as _ptrace

                _ptrace(
                    "ENGINE",
                    engine="conversation_repair",
                    kind="reclassify",
                    fallback=False,
                    new_intent=reclass.get("intent"),
                )
            except Exception:
                pass
            return reclass

        text = _build_repair_reply(message, ctx)
        # Never ship the sticky GA template from this path
        if text.strip().startswith("Entendi. Posso te ajudar"):
            text = (
                "Sem menu — retomando o fio da conversa e avançando no que você pediu."
            )
        try:
            from src.conversation.perception_conversation_state import (
                anti_sticky_reply,
                stamp_entities,
                strip_menus,
            )

            text = anti_sticky_reply(ctx, strip_menus(text))
        except Exception:
            pass
        logger.warning(
            "[AUDIT] ConversationRepair: signal matched team=%r q=%r",
            get_repair_memory(ctx).get("last_team"),
            (get_repair_memory(ctx).get("last_user_question") or "")[:60],
        )
        try:
            from src.conversation.pipeline_trace import trace as _ptrace

            _ptrace(
                "ENGINE",
                engine="conversation_repair",
                kind="repair",
                fallback=False,
            )
        except Exception:
            pass
        payload = _payload(text)
        try:
            from src.conversation.perception_conversation_state import stamp_entities

            stamp_entities(payload, ctx)
            ents = dict(payload.get("entities") or {})
            ents["repair_must_answer"] = True
            payload["entities"] = ents
        except Exception:
            pass
        return payload
    except Exception as exc:
        logger.warning("try_conversation_repair fail-open: %s", exc)
        return None
