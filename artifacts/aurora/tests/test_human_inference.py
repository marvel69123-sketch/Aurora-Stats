"""Human Understanding Phase — intent inference (not classical NLP)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.conversation.brain_authority import should_block_analysis_engines
from src.conversation.human_inference import (
    apply_human_inference,
    infer_human_intent,
    looks_like_encyclopedia_dump,
    repair_unintelligent_reply,
    thinking_delay_ok,
)
from src.conversation.natural_conversation import detect_natural_intent


def test_analisar_arsenal_chelsea_is_match_analysis():
    inf = infer_human_intent("Analisar Arsenal x Chelsea")
    assert inf.intent == "match_analysis"
    assert inf.priority == "very_high"
    assert inf.home and "arsenal" in inf.home.lower()
    assert inf.away and "chelsea" in inf.away.lower()
    assert inf.strong_verb == "analisar"
    assert "agenda" not in (inf.human_goal or "").lower()


def test_bare_pair_is_match_analysis_not_calendar():
    inf = infer_human_intent("Arsenal x Chelsea")
    assert inf.intent == "match_analysis"
    assert detect_natural_intent("Arsenal x Chelsea") is None


def test_analisar_pair_not_stolen_by_natural_calendar():
    assert detect_natural_intent("Analisar Arsenal x Chelsea") is None


def test_bare_botafogo_is_general_team_talk():
    inf = infer_human_intent("Botafogo")
    assert inf.intent == "general_team_talk"
    assert inf.team and "botafogo" in inf.team.lower()
    assert "?" not in (inf.human_goal or "")
    nat = detect_natural_intent("Botafogo")
    assert nat is not None
    assert nat["kind"] == "team_opinion"


def test_como_esta_flamengo_is_moment():
    inf = infer_human_intent("Como está o Flamengo?")
    assert inf.intent == "team_moment"
    assert inf.topic_kind == "moment"


def test_como_esta_survives_recovery_rewrite():
    ctx = {"raw_user_message": "Como está o Flamengo?"}
    # Simulate recovery stripping moment → opinion phrasing
    msg, inf = apply_human_inference("o que acha do Flamengo", ctx)
    assert inf.intent == "team_moment"
    assert "Flamengo" in (inf.team or msg)


def test_e_o_botafogo_keeps_team_talk():
    inf = infer_human_intent("E o Botafogo?")
    assert inf.intent == "general_team_talk"
    assert inf.team and "botafogo" in inf.team.lower()


def test_pair_hoje_is_calendar_not_analyze():
    inf = infer_human_intent("Mirassol x Grêmio hoje")
    assert inf.intent == "calendar_or_fixture"
    assert inf.topic_kind in {"fixture", "calendar"}


def test_match_analysis_does_not_block_engines():
    ctx: dict = {}
    apply_human_inference("Analisar Arsenal x Chelsea", ctx)
    assert should_block_analysis_engines(ctx) is False
    assert ctx["deep_thinking"]["topic_kind"] == "match_analysis"


def test_thinking_delay_rejects_encyclopedia_and_question_mark():
    dump = (
        "Clube de Regatas do Flamengo (CRF) é uma agremiação poliesportiva "
        "brasileira com sede na cidade do Rio de Janeiro."
    )
    assert looks_like_encyclopedia_dump(dump) is True
    assert thinking_delay_ok(dump) is False
    assert thinking_delay_ok("?") is False
    fixed = repair_unintelligent_reply(
        dump, {"deep_thinking": {"topic_team": "Flamengo", "topic_kind": "opinion"}}
    )
    assert "?" not in fixed.strip() or len(fixed) > 3
    assert "agremiação" not in fixed.lower()
    assert "Flamengo" in fixed or "flamengo" in fixed.lower()


def test_apply_rewrites_and_sets_entities():
    ctx: dict = {}
    msg, inf = apply_human_inference("Analisar Arsenal x Chelsea", ctx)
    assert inf.intent == "match_analysis"
    assert ctx.get("human_inference", {}).get("intent") == "match_analysis"
    assert "analisar" in msg.lower()
