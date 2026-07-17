"""
Football ontology — what humans normally expect in each answer type.
Additive. Never invents fixtures/stats.
"""

from __future__ import annotations

from typing import Final

TEAM_SUMMARY: Final[list[str]] = [
    "current_moment",
    "recent_result",
    "next_matches",
    "news",
    "perspective",
]

TEAM_MOMENT: Final[list[str]] = [
    "recent_form",
    "strengths",
    "issues",
    "perspective",
]

MATCH_ANALYSIS: Final[list[str]] = [
    "context",
    "strengths",
    "weaknesses",
    "expectations",
]

TEAM_TALK: Final[list[str]] = [
    "current_moment",
    "recent_result",
    "perspective",
]

ANSWER_SECTIONS: Final[dict[str, list[str]]] = {
    "team_summary": TEAM_SUMMARY,
    "team_moment": TEAM_MOMENT,
    "match_analysis": MATCH_ANALYSIS,
    "team_talk": TEAM_TALK,
}

DEPTH_BY_TYPE: Final[dict[str, str]] = {
    "team_summary": "medium",
    "team_moment": "deep",
    "match_analysis": "deep",
    "team_talk": "medium",
}
