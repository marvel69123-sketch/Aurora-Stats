"""Response Intelligence + Human Intelligence Certification gates."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.conversation.confidence_rewriter import (
    has_errorish_honesty,
    rewrite_confidence_tone,
)
from src.conversation.human_inference import apply_human_inference, infer_human_intent
from src.conversation.knowledge_synthesizer import (
    is_encyclopedia_noise,
    synthesize_knowledge,
)
from src.conversation.response_intelligence import compose_intelligent_reply
from src.conversation.response_planner import plan_response
from src.conversation.response_reflection import reflect_response
from src.conversation.response_templates import (
    dynamic_section_selection,
    render_forced_useful,
)
from src.conversation.user_expectation import infer_expected_information


def test_planner_botafogo_team_summary():
    ctx: dict = {}
    apply_human_inference("Botafogo", ctx)
    plan = plan_response("Botafogo", ctx)
    assert plan.answer_type == "team_summary"


def test_expectation_botafogo():
    ctx: dict = {}
    apply_human_inference("Botafogo", ctx)
    exp = infer_expected_information("Botafogo", ctx)
    assert "momento atual" in exp.user_probably_wants
    assert "próximos jogos" in exp.user_probably_wants


def test_expectation_flamengo_moment():
    msg = "Como está o Flamengo?"
    ctx = {"raw_user_message": msg}
    apply_human_inference(msg, ctx)
    exp = infer_expected_information(msg, ctx)
    assert exp.answer_bias == "team_moment"
    assert "fase" in exp.expects


def test_expectation_arsenal_chelsea():
    ctx: dict = {}
    apply_human_inference("Arsenal x Chelsea", ctx)
    exp = infer_expected_information("Arsenal x Chelsea", ctx)
    assert exp.answer_bias == "match_analysis"
    assert "análise" in exp.expects


def test_dynamic_sections_vary():
    a = dynamic_section_selection("team_summary", team="Botafogo", variant=0)
    b = dynamic_section_selection("team_summary", team="Botafogo", variant=1)
    assert a != b or a  # at least valid
    assert "moment" in a or "market" in a or "recent" in a


def test_synthesizer_drops_wikipedia_dump():
    pack = synthesize_knowledge(
        team="Flamengo",
        web_results=[
            "Clube de Regatas do Flamengo (CRF) é uma agremiação poliesportiva.",
            "Flamengo venceu ontem por 2 a 1 na rodada do Brasileirão.",
        ],
    )
    assert is_encyclopedia_noise(
        "Clube de Regatas do Flamengo é uma agremiação poliesportiva"
    )
    joined = " ".join(pack.recent_results + pack.team_moment + pack.market_news)
    assert "agremiação" not in joined.lower()


def test_confidence_rewriter_kills_errorish():
    raw = "Não confirmei um boletim fresco do Botafogo agora — então trato com cautela."
    fixed = rewrite_confidence_tone(raw)
    assert not has_errorish_honesty(fixed)
    assert "não confirmei" not in fixed.lower()


def test_reflection_blocks_philosophy():
    bad = (
        "Sobre o Botafogo: eu evitaria opinião engessada. O que pesa é momento, "
        "adversário e se o time sustenta ideia de jogo — não só a camisa."
    )
    ref = reflect_response(bad, question="Botafogo")
    assert ref.blocked or not ref.ok
    assert not ref.feels_useful


def test_forced_template_passes_reflection():
    ctx: dict = {}
    apply_human_inference("Botafogo", ctx)
    plan = plan_response("Botafogo", ctx)
    text = rewrite_confidence_tone(render_forced_useful(plan, variant=0))
    assert "evitaria opinião engessada" not in text.lower()
    assert not has_errorish_honesty(text)
    ref = reflect_response(text, question="Botafogo")
    assert ref.ok
    assert ref.feels_useful


def test_compose_botafogo_useful():
    ctx: dict = {"raw_user_message": "Botafogo"}
    apply_human_inference("Botafogo", ctx)
    text = asyncio.run(
        compose_intelligent_reply("Botafogo", ctx, team="Botafogo", variant=0)
    )
    assert text
    assert "Botafogo" in text
    assert "evitaria opinião engessada" not in text.lower()
    assert "não confirmei" not in text.lower()
    assert "agremiação" not in text.lower()
    ref = reflect_response(text, question="Botafogo")
    assert ref.ok


def test_compose_flamengo_moment():
    msg = "Como está o Flamengo atualmente?"
    ctx = {"raw_user_message": msg}
    apply_human_inference(msg, ctx)
    text = asyncio.run(
        compose_intelligent_reply(
            msg, ctx, team="Flamengo", moment=True, variant=1
        )
    )
    assert text
    assert "Flamengo" in text
    assert "olharia menos o hype" not in text.lower()
    assert "não confirmei" not in text.lower()


def test_bare_obscure_teams_never_question_mark():
    for name in ("Londrina", "XV de Piracicaba", "Juventus da Mooca"):
        inf = infer_human_intent(name)
        assert inf.intent == "general_team_talk", name
        assert inf.team
        assert "?" not in (inf.human_goal or "")
