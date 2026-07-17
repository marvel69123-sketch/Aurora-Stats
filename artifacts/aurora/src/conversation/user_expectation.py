"""
User Expectation Engine — answer what the user probably wants, not only what they typed.
Fail-open. Additive. Does not invent fixtures.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

CTX_KEY = "user_expectation"


@dataclass
class UserExpectation:
    user_probably_wants: list[str] = field(default_factory=list)
    expects: list[str] = field(default_factory=list)
    completion_targets: list[str] = field(default_factory=list)
    answer_bias: str = "team_summary"  # team_summary | team_moment | match_analysis
    confidence: float = 0.7

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def infer_expected_information(
    message: str,
    ctx: dict[str, Any] | None = None,
) -> UserExpectation:
    """
    Infer what a human expects beyond the literal string.
    """
    hie = (ctx or {}).get("human_inference") or {}
    thinking = (ctx or {}).get("deep_thinking") or {}
    intent = str(hie.get("intent") or thinking.get("human_intent") or "")
    kind = str(hie.get("topic_kind") or thinking.get("topic_kind") or "")
    folded = re.sub(
        r"\s+",
        " ",
        (message or "").lower(),
    )

    if intent == "match_analysis" or kind == "match_analysis":
        wants = ["análise", "forças", "cenário", "contexto", "fragilidades"]
        exp = UserExpectation(
            user_probably_wants=wants,
            expects=wants,
            completion_targets=[
                "context",
                "strengths",
                "weaknesses",
                "expectations",
            ],
            answer_bias="match_analysis",
            confidence=0.95,
        )
    elif intent == "team_moment" or kind == "moment" or re.search(
        r"como\s+est|atualmente|momento", folded
    ):
        wants = ["fase", "problemas", "perspectiva", "pontos positivos"]
        exp = UserExpectation(
            user_probably_wants=wants,
            expects=wants,
            completion_targets=[
                "recent_form",
                "strengths",
                "issues",
                "perspective",
            ],
            answer_bias="team_moment",
            confidence=0.93,
        )
    else:
        # Bare team / general talk — Gemini completes beyond the ask
        wants = [
            "momento atual",
            "último resultado",
            "próximos jogos",
            "notícias",
        ]
        exp = UserExpectation(
            user_probably_wants=wants,
            expects=wants,
            completion_targets=[
                "current_moment",
                "recent_result",
                "next_matches",
                "news",
                "perspective",
            ],
            answer_bias="team_summary",
            confidence=0.9 if intent in {"general_team_talk", "team_analysis"} else 0.75,
        )
    if ctx is not None:
        ctx[CTX_KEY] = exp.to_dict()
    logger.warning(
        "[AUDIT] UserExpectation: bias=%s wants=%s",
        exp.answer_bias,
        exp.user_probably_wants,
    )
    return exp


def complete_expected_information(
    pack: Any,
    expectation: UserExpectation,
    *,
    team: str | None = None,
) -> Any:
    """
    Ensure expected slots exist (honest assistant tone — never invent results).
    Mutates KnowledgePack-like object.
    """
    label = team or "o time"
    # Fill missing buckets so templates/dynamic sections can speak
    if "recent_result" in expectation.completion_targets or "último resultado" in (
        expectation.expects or []
    ):
        if not getattr(pack, "recent_results", None):
            pack.recent_results = list(getattr(pack, "recent_results", None) or [])
            # placeholder signal handled by confidence rewriter in body text
            pack.recent_results = pack.recent_results or []

    if "next_matches" in expectation.completion_targets or "próximos jogos" in (
        expectation.expects or []
    ):
        pack.next_games = list(getattr(pack, "next_games", None) or [])

    if "news" in expectation.completion_targets or "notícias" in (
        expectation.expects or []
    ):
        pack.market_news = list(getattr(pack, "market_news", None) or [])

    if expectation.answer_bias == "team_moment":
        if not pack.issues:
            pack.issues = [
                f"No {label}, o que costuma pesar é pressão, oscilação e "
                f"se o elenco responde quando o plano trava."
            ]
        if not pack.strengths:
            pack.strengths = [
                f"Quando o {label} encontra regularidade e intensidade, "
                f"a conversa muda de tom — esse é o termômetro da fase."
            ]
        if not pack.team_moment:
            pack.team_moment = [
                f"A fase do {label} pede leitura pelo ritmo recente e pelo "
                f"adversário da semana — não pelo rótulo da camisa."
            ]

    if expectation.answer_bias == "team_summary":
        if not pack.team_moment:
            pack.team_moment = [
                f"Com o contexto atual do {label}, o foco útil é fase + "
                f"próximo desafio — isso costuma ser o que a torcida quer saber."
            ]
        if not pack.perspective:
            pack.perspective = [
                f"Próximo passo natural: olhar o último sinal de campo e o "
                f"próximo confronto do {label}."
            ]

    if expectation.answer_bias == "match_analysis":
        if not pack.perspective:
            pack.perspective = [
                "Cenário útil: quem impõe ritmo cedo e quem sofre nas transições "
                "costuma decidir o clima do jogo."
            ]

    # Mark completion applied
    if hasattr(pack, "perspective") and pack.perspective:
        pass
    logger.warning(
        "[AUDIT] ExpectationCompletion: bias=%s team=%r recent=%d next=%d",
        expectation.answer_bias,
        label,
        len(getattr(pack, "recent_results", []) or []),
        len(getattr(pack, "next_games", []) or []),
    )
    return pack
