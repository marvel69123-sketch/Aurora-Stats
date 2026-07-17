"""
Response Intelligence Engine — Expectation → Rank → Dynamic structure → Reflect.

Does NOT alter Follow-up / Boundary / Memory / DeepThinking Authority modules.
Fail-open. Additive.
"""

from __future__ import annotations

import logging
import random
from typing import Any

logger = logging.getLogger(__name__)


async def compose_intelligent_reply(
    message: str,
    ctx: dict[str, Any] | None = None,
    prefs: dict[str, Any] | None = None,
    *,
    team: str | None = None,
    moment: bool = False,
    force_type: str | None = None,
    variant: int | None = None,
) -> str | None:
    """
    Full pipeline for team talk / moment (and soft match briefing).
    """
    try:
        from src.conversation.master_intent_router import sport_pipeline_allowed

        if not sport_pipeline_allowed(ctx):
            logger.warning(
                "[AUDIT] ResponseIntelligence: BLOCKED — non-sport master intent"
            )
            return None

        from src.conversation.confidence_rewriter import (
            has_errorish_honesty,
            rewrite_confidence_tone,
        )
        from src.conversation.information_ranking import rank_information
        from src.conversation.knowledge_synthesizer import (
            collect_api_next_games,
            synthesize_knowledge,
        )
        from src.conversation.response_planner import plan_response
        from src.conversation.response_reflection import reflect_response
        from src.conversation.response_templates import (
            render_dynamic,
            render_forced_useful,
        )
        from src.conversation.user_expectation import (
            complete_expected_information,
            infer_expected_information,
        )

        if ctx is None:
            ctx = {}

        hie = dict(ctx.get("human_inference") or {})
        if team and not hie.get("team"):
            hie["team"] = team
        if moment and hie.get("intent") not in {"match_analysis"}:
            hie["intent"] = "team_moment"
            hie["topic_kind"] = "moment"
        elif team and not hie.get("intent"):
            hie["intent"] = "general_team_talk"
            hie["topic_kind"] = "opinion"
        if force_type == "team_moment":
            hie["intent"] = "team_moment"
            hie["topic_kind"] = "moment"
        elif force_type == "team_summary":
            hie["intent"] = "general_team_talk"
        elif force_type == "match_analysis":
            hie["intent"] = "match_analysis"
        ctx["human_inference"] = hie

        expectation = infer_expected_information(message, ctx)
        plan = plan_response(message, ctx)
        if team and not plan.team:
            plan.team = team
        # Align plan type with expectation bias when stronger
        if expectation.answer_bias == "team_moment" and plan.answer_type != "match_analysis":
            plan.answer_type = "team_moment"
        if expectation.answer_bias == "match_analysis":
            plan.answer_type = "match_analysis"

        api_games = await collect_api_next_games(plan.team)
        if api_games:
            ctx["next_games_hints"] = api_games

        pack = synthesize_knowledge(
            team=plan.team,
            home=plan.home,
            away=plan.away,
            api_results=api_games,
            ctx=ctx,
        )
        pack = complete_expected_information(pack, expectation, team=plan.team)
        rank_information(pack, expects=expectation.expects)

        if variant is None:
            variant = random.randint(0, 2)

        reply = render_dynamic(plan, pack, variant=variant)
        reply = rewrite_confidence_tone(reply)

        reflection = reflect_response(
            reply, question=plan.question or message, answer_type=plan.answer_type
        )
        ctx["response_reflection"] = reflection.to_dict()
        ctx["response_variant"] = variant

        if (
            not reflection.ok
            or reflection.blocked
            or has_errorish_honesty(reply)
            or not reflection.feels_useful
        ):
            logger.warning(
                "[AUDIT] ResponseIntelligence: regenerating reasons=%s",
                reflection.reasons,
            )
            reply = render_forced_useful(plan, variant=(variant + 1) % 3)
            reply = rewrite_confidence_tone(reply)
            reflection2 = reflect_response(
                reply, question=plan.question or message, answer_type=plan.answer_type
            )
            ctx["response_reflection"] = reflection2.to_dict()
            if not reflection2.ok or has_errorish_honesty(reply):
                reply = rewrite_confidence_tone(render_forced_useful(plan, variant=2))

        try:
            from src.conversation.presence_humanization import (
                apply_presence_humanization,
            )

            reply = apply_presence_humanization(
                reply, prefs, family_hint="team_opinion"
            )
            reply = rewrite_confidence_tone(reply)
        except Exception:
            pass

        from src.conversation.human_inference import looks_like_encyclopedia_dump
        from src.conversation.response_reflection import does_answer_feel_useful

        if looks_like_encyclopedia_dump(reply) or not does_answer_feel_useful(reply):
            reply = rewrite_confidence_tone(render_forced_useful(plan, variant=0))

        logger.warning(
            "[AUDIT] ResponseIntelligence: type=%s team=%r len=%d signal=%s variant=%s",
            plan.answer_type,
            plan.team,
            len(reply or ""),
            pack.has_real_signal,
            variant,
        )
        return reply
    except Exception as exc:
        logger.warning("compose_intelligent_reply fail-open: %s", exc)
        return None


def should_use_response_intelligence(ctx: dict[str, Any] | None) -> bool:
    try:
        from src.conversation.brain_authority import is_calendar_authority
        from src.conversation.human_inference import is_match_analysis

        if is_match_analysis(ctx):
            return False
        if is_calendar_authority(ctx):
            return False
    except Exception:
        pass
    hie = (ctx or {}).get("human_inference") or {}
    thinking = (ctx or {}).get("deep_thinking") or {}
    intent = hie.get("intent") or thinking.get("human_intent")
    kind = thinking.get("topic_kind") or hie.get("topic_kind")
    return intent in {
        "general_team_talk",
        "team_moment",
        "team_analysis",
    } or kind in {"opinion", "moment"}
