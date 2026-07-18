"""
Response Planner Engine — decide WHAT to answer before writing.
Understand → Think → Plan (this module) → Research → Synthesize → Respond.
Fail-open. Additive. Does not touch Follow-up / Boundary / Memory / DT Authority.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from typing import Any

from src.conversation.football_expectations import ANSWER_SECTIONS, DEPTH_BY_TYPE

logger = logging.getLogger(__name__)

CTX_KEY = "response_plan"


@dataclass
class ResponsePlan:
    answer_type: str
    sections: list[str] = field(default_factory=list)
    required_information: list[str] = field(default_factory=list)
    depth: str = "medium"
    team: str | None = None
    home: str | None = None
    away: str | None = None
    question: str = ""
    source_intent: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def plan_response(
    message: str,
    ctx: dict[str, Any] | None = None,
) -> ResponsePlan:
    """
    Build answer plan from Human Inference + DeepThinking (read-only).
    """
    hie = (ctx or {}).get("human_inference") or {}
    thinking = (ctx or {}).get("deep_thinking") or {}
    intent = str(hie.get("intent") or thinking.get("human_intent") or "")
    kind = str(thinking.get("topic_kind") or hie.get("topic_kind") or "")
    team = hie.get("team") or thinking.get("topic_team")
    home = hie.get("home")
    away = hie.get("away")
    teams = list(hie.get("teams") or thinking.get("topic_teams") or [])
    if not home and len(teams) >= 2:
        home, away = teams[0], teams[1]
    if not team and teams:
        team = teams[0]

    # Match analysis — plan for briefing only if engines don't answer;
    # Natural should not own this path.
    if intent == "match_analysis" or kind == "match_analysis":
        plan = ResponsePlan(
            answer_type="match_analysis",
            sections=list(ANSWER_SECTIONS["match_analysis"]),
            required_information=[
                "fixture_context",
                "comparative_strengths",
                "risks",
                "scenario",
            ],
            depth=DEPTH_BY_TYPE["match_analysis"],
            team=team,
            home=home,
            away=away,
            question=(message or "").strip(),
            source_intent=intent or "match_analysis",
        )
    elif intent == "team_moment" or kind == "moment":
        plan = ResponsePlan(
            answer_type="team_moment",
            sections=list(ANSWER_SECTIONS["team_moment"]),
            required_information=[
                "recent_form",
                "strengths",
                "issues",
                "honest_perspective",
            ],
            depth=DEPTH_BY_TYPE["team_moment"],
            team=str(team) if team else None,
            question=(message or "").strip(),
            source_intent=intent or "team_moment",
        )
    elif (
        "recent_match" in (hie.get("what_user_expects") or [])
        or (
            isinstance(ctx, dict)
            and (ctx.get("user_expectation") or {}).get("answer_bias") == "match_opinion"
        )
    ):
        # Phase 8.3-A — match opinion plan (not panorama sections)
        plan = ResponsePlan(
            answer_type="match_opinion",
            sections=list(ANSWER_SECTIONS.get("match_opinion") or ["match_reading"]),
            required_information=["match_reading", "honest_opinion"],
            depth="medium",
            team=str(team) if team else None,
            question=(message or "").strip(),
            source_intent=intent or "general_team_talk",
        )
    elif intent in {"general_team_talk", "team_analysis"} or kind == "opinion":
        plan = ResponsePlan(
            answer_type="team_summary",
            sections=list(ANSWER_SECTIONS["team_summary"]),
            required_information=[
                "current_moment",
                "recent_signal",
                "next_challenge",
                "perspective",
            ],
            depth=DEPTH_BY_TYPE["team_summary"],
            team=str(team) if team else None,
            question=(message or "").strip(),
            source_intent=intent or "general_team_talk",
        )
    else:
        plan = ResponsePlan(
            answer_type="team_talk",
            sections=list(ANSWER_SECTIONS["team_talk"]),
            required_information=["current_moment", "perspective"],
            depth="medium",
            team=str(team) if team else None,
            question=(message or "").strip(),
            source_intent=intent or "unknown",
        )

    if ctx is not None:
        ctx[CTX_KEY] = plan.to_dict()
    logger.warning(
        "[AUDIT] ResponsePlanner: type=%s sections=%s team=%r depth=%s",
        plan.answer_type,
        plan.sections,
        plan.team,
        plan.depth,
    )
    return plan
