"""
Aurora Brain Upgrade — Intelligence Fallback + local thinking.

NEVER return empty / "?" / null narrative.
If WEB fails or topic is historical, think locally.

Fail-open. Additive.
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


def is_empty_or_useless(text: str | None) -> bool:
    t = (text or "").strip()
    if not t:
        return True
    if t in {"?", ".", "-", "…", "...", "null", "none", "n/a"}:
        return True
    if len(t) < 2:
        return True
    return False


def build_copa_opinion(year: str | None = None) -> str:
    y = year or "2026"
    return (
        f"Sobre a Copa de {y}, eu penso menos em placar e mais em narrativa.\n\n"
        f"Uma Copa do Mundo sempre mistura expectativa, identidade das seleções e "
        f"momentos que mudam o humor de um país em 90 minutos. Em {y}, o que mais "
        f"me interessa é: quem chega com maturidade tática, quem depende só de "
        f"estrelas individuais, e quais jogos viram história — não só resultado.\n\n"
        f"Se a pergunta for “o que achou?”, minha resposta honesta é: eu avalio "
        f"pelo sentimento coletivo e pelas surpresas. Copa boa é aquela em que "
        f"aparece um time com cara própria e jogos que a gente lembra semanas depois.\n\n"
        f"Se quiser, a gente aprofunda um jogo, uma seleção ou um momento específico "
        f"— aí a conversa fica ainda mais viva ⚽"
    )


def build_local_team_thinking(team: str, *, moment: bool = False) -> str:
    """Local opinion — never the old 'Pensando no…' template."""
    try:
        from src.conversation.brain_authority import opinion_local_reasoning

        return opinion_local_reasoning(team, moment=moment)
    except Exception:
        tip = "agora" if moment else "no momento"
        return (
            f"Sobre o {team} {tip}: eu evitaria uma opinião engessada. "
            f"Times mudam de cara em poucas semanas — ritmo, elenco disponível e "
            f"adversário pesam mais do que fama.\n\n"
            f"Se quiser, me passa o próximo jogo do {team} e a gente aprofunda."
        )


def detect_historical_copa(message: str) -> str | None:
    folded = _fold(message)
    m = re.search(
        r"\b(?:copa(?:\s+do\s+mundo)?|mundial)\s+(?:de\s+)?(20\d{2})\b",
        folded,
    )
    if m:
        return m.group(1)
    if re.search(r"\bo\s+que\s+achou\s+da\s+copa\b", folded):
        return "2026"
    return None


def try_intelligence_fallback(
    message: str,
    ctx: dict[str, Any] | None = None,
    prefs: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """
    Short-circuit thoughtful replies for topics that would otherwise
    become help-menu / empty / '?'.
    """
    try:
        try:
            from src.conversation.master_intent_router import sport_pipeline_allowed

            if not sport_pipeline_allowed(ctx):
                logger.warning(
                    "[AUDIT] IntelligenceFallback: SKIPPED — sport pipeline blocked"
                )
                return None
        except Exception:
            pass

        year = detect_historical_copa(message)
        if year:
            reply = build_copa_opinion(year)
            try:
                from src.conversation.web_intelligence import weave_web_into_draft

                reply, _ = weave_web_into_draft(reply, ctx, team="Copa do Mundo")
            except Exception:
                pass
            return _payload(reply, kind="historical_copa", year=year, prefs=prefs)

        # Recovered team opinion that natural layer might still miss
        recovery = (ctx or {}).get("context_recovery") or {}
        thinking = (ctx or {}).get("deep_thinking") or {}
        # Brain Authority — never opinion fallback on calendar topics
        try:
            from src.conversation.brain_authority import is_calendar_authority

            if is_calendar_authority(ctx):
                from src.conversation.brain_authority import calendar_empty_reply

                teams = list(recovery.get("teams") or thinking.get("topic_teams") or [])
                team = thinking.get("topic_team") or (teams[0] if teams else None)
                reply = calendar_empty_reply(
                    team=str(team) if team else None,
                    teams=teams[:2],
                    kind=str(thinking.get("topic_kind") or "calendar"),
                )
                return _payload(reply, kind="calendar_authority", team=team, prefs=prefs)
        except Exception:
            pass
        hie = (ctx or {}).get("human_inference") or {}
        if (
            recovery.get("inferred_goal") == "team_opinion"
            or thinking.get("topic_kind") in {"opinion", "moment"}
            or hie.get("intent")
            in {"general_team_talk", "team_moment", "team_analysis"}
        ) and (
            recovery.get("teams")
            or thinking.get("topic_team")
            or hie.get("team")
        ):
            team = (
                (recovery.get("teams") or [None])[0]
                or thinking.get("topic_team")
                or hie.get("team")
            )
            moment = (
                recovery.get("temporal") == "now"
                or thinking.get("topic_kind") == "moment"
                or hie.get("intent") == "team_moment"
            )
            reply = None
            try:
                import asyncio

                from src.conversation.response_intelligence import (
                    compose_intelligent_reply,
                )

                # Sync context: run compose if loop available; else structured sync path
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None
                if loop and loop.is_running():
                    # Cannot await here — use sync template path
                    reply = None
                else:
                    reply = asyncio.run(
                        compose_intelligent_reply(
                            message,
                            ctx,
                            prefs,
                            team=str(team),
                            moment=moment,
                            force_type="team_moment" if moment else "team_summary",
                        )
                    )
            except Exception:
                reply = None
            if not reply:
                try:
                    from src.conversation.response_planner import plan_response
                    from src.conversation.knowledge_synthesizer import (
                        synthesize_knowledge,
                    )
                    from src.conversation.response_templates import render_from_plan

                    if ctx is not None:
                        h = dict(ctx.get("human_inference") or {})
                        h.setdefault("team", team)
                        h.setdefault(
                            "intent",
                            "team_moment" if moment else "general_team_talk",
                        )
                        ctx["human_inference"] = h
                    plan = plan_response(message, ctx)
                    plan.team = str(team)
                    pack = synthesize_knowledge(team=str(team), ctx=ctx)
                    reply = render_from_plan(plan, pack)
                except Exception:
                    reply = build_local_team_thinking(str(team), moment=moment)
            try:
                from src.conversation.human_inference import repair_unintelligent_reply
                from src.conversation.response_reflection import reflect_response
                from src.conversation.response_templates import render_forced_useful
                from src.conversation.response_planner import plan_response

                ref = reflect_response(reply, question=message)
                if not ref.ok or ref.blocked:
                    plan = plan_response(message, ctx)
                    plan.team = str(team)
                    reply = render_forced_useful(plan)
                else:
                    reply = repair_unintelligent_reply(reply, ctx)
            except Exception:
                pass
            return _payload(reply, kind="local_team_thinking", team=team, prefs=prefs)

        return None
    except Exception as exc:
        logger.warning("try_intelligence_fallback fail-open: %s", exc)
        return None


def ensure_non_empty_payload(
    payload: dict[str, Any],
    *,
    message: str,
    ctx: dict[str, Any] | None = None,
    prefs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Absolute guard — never leave '?' / empty executive_summary."""
    try:
        if not isinstance(payload, dict):
            return payload
        summary = str(payload.get("executive_summary") or "")
        if not is_empty_or_useless(summary):
            return payload

        # Non-sport: never invent Copa/team opinion as filler
        try:
            from src.conversation.master_intent_router import sport_pipeline_allowed

            if not sport_pipeline_allowed(ctx) or (
                payload.get("entities") or {}
            ).get("general_assistant"):
                soft = "Pode falar comigo normalmente — em que posso ajudar?"
                payload = dict(payload)
                payload["executive_summary"] = soft
                payload["final_recommendation"] = soft
                return payload
        except Exception:
            pass

        year = detect_historical_copa(message)
        if year:
            reply = build_copa_opinion(year)
        else:
            try:
                from src.conversation.brain_authority import ensure_fallback_for_thinking

                reply = ensure_fallback_for_thinking(message, ctx)
            except Exception:
                recovery = (ctx or {}).get("context_recovery") or {}
                teams = recovery.get("teams") or []
                thinking = (ctx or {}).get("deep_thinking") or {}
                if thinking.get("topic_kind") in {
                    "calendar",
                    "fixture",
                    "kickoff",
                    "outlook",
                }:
                    reply = (
                        "Não consegui localizar o jogo solicitado agora. "
                        "Me passa o confronto (A x B) ou o campeonato."
                    )
                elif teams:
                    reply = build_local_team_thinking(str(teams[0]))
                else:
                    reply = (
                        "Deixa eu pensar com calma no que você perguntou.\n\n"
                        "Pelo que entendi, você quer uma leitura esportiva — não um "
                        "menu genérico. Me dá um pouco mais de contexto (time, jogo "
                        "ou tema) que eu aprofundo com honestidade."
                    )

        try:
            from src.conversation.presence_humanization import apply_presence_humanization

            reply = apply_presence_humanization(reply, prefs, family_hint="casual")
        except Exception:
            pass

        payload["executive_summary"] = reply
        payload["final_recommendation"] = reply
        ents = dict(payload.get("entities") or {})
        ents.update(
            {
                "intelligence_fallback": True,
                "has_analysis": False,
                "show_header": False,
                "skip_llm": True,
            }
        )
        payload["entities"] = ents
        meta = dict(payload.get("response_metadata") or {})
        meta["intelligence_fallback"] = {"applied": True, "reason": "empty_or_useless"}
        payload["response_metadata"] = meta
        logger.warning("[AUDIT] IntelligenceFallback: replaced empty/useless narrative")
        return payload
    except Exception as exc:
        logger.warning("ensure_non_empty_payload fail-open: %s", exc)
        return payload


def _payload(
    reply: str,
    *,
    kind: str,
    prefs: dict[str, Any] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    try:
        from src.conversation.presence_humanization import apply_presence_humanization

        reply = apply_presence_humanization(reply, prefs, family_hint="team_opinion")
    except Exception:
        pass
    try:
        from src.conversation.message_intelligence import build_conversational_payload

        payload = build_conversational_payload(reply, {})
    except Exception:
        payload = {
            "intent": "conversation_assist",
            "entities": {},
            "best_markets": [],
            "executive_summary": reply,
            "final_recommendation": reply,
            "confidence": {
                "score": 0.0,
                "label": "insufficient",
                "explanation": "",
                "data_sources": [],
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
            "brain": {},
        }
    payload["intent"] = "conversation_assist"
    payload["executive_summary"] = reply
    payload["final_recommendation"] = reply
    ents = dict(payload.get("entities") or {})
    ents.update(
        {
            "intelligence_fallback": True,
            "fallback_kind": kind,
            "natural_conversation": True,
            "opinion_time": kind in {"historical_copa", "local_team_thinking"},
            "has_analysis": False,
            "show_header": False,
            "skip_llm": True,
            **{k: v for k, v in extra.items() if v is not None},
        }
    )
    if kind == "historical_copa":
        ents["natural_kind"] = "historical_copa"
    payload["entities"] = ents
    payload["best_markets"] = []
    payload["match_card"] = None
    meta = dict(payload.get("response_metadata") or {})
    meta.update(
        {
            "mode": "intelligence_fallback",
            "source": "conversation.intelligence_fallback",
            "skip_llm": True,
        }
    )
    payload["response_metadata"] = meta
    return payload
