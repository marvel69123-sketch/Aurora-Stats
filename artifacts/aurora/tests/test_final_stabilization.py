"""Final Stabilization — focus resolver, boundary_score, web synthesis."""

from __future__ import annotations

from src.conversation.brain_authority import (
    apply_topic_boundary,
    compute_boundary_score,
    should_clear_topic_boundary,
)
from src.conversation.context_recovery import recover_context
from src.conversation.conversation_focus import (
    apply_reference_resolution,
    get_focus,
    resolve_reference,
    update_conversation_focus,
)
from src.conversation.response_review import run_deep_thinking_engine
from src.conversation.web_intelligence import (
    build_reasoning_from_web,
    decide_web_mode,
    synthesize_web_context,
)


def test_focus_and_horario_resolver():
    ctx: dict = {}
    r = recover_context("quero saber sobre jogo do mirassol x gremio hoje", ctx)
    t = run_deep_thinking_engine(r.recovered, ctx, recovery=r.to_dict())
    update_conversation_focus(ctx, thinking=t, recovery=r.to_dict(), message=r.recovered)
    focus = get_focus(ctx)
    assert focus.get("topic_fixture") or len(focus.get("topic_teams") or []) >= 2

    res = resolve_reference("e o horario?", ctx)
    assert res["resolved"] is True
    assert res["topic_kind"] == "kickoff"
    out = apply_reference_resolution("e o horario?", ctx)
    assert "horas" in out.lower() or "horario" in out.lower() or "x" in out.lower()


def test_boundary_soft_vs_entity():
    ctx = {
        "last_match": "Mirassol x Gremio",
        "last_home": "Mirassol",
        "last_away": "Gremio",
        "conversation_focus": {
            "topic_fixture": "Mirassol x Gremio",
            "topic_team": "Mirassol",
            "topic_kind": "fixture",
        },
    }
    soft = compute_boundary_score("e o horario?", ctx)
    assert soft["clear"] is False
    assert soft["same_topic"] is True

    r = recover_context("e o santos?", ctx)
    run_deep_thinking_engine(r.recovered, ctx, recovery=r.to_dict())
    hard = compute_boundary_score(r.recovered, ctx, recovery=r.to_dict())
    assert hard["clear"] is True
    clear, why = should_clear_topic_boundary(r.recovered, ctx, recovery=r.to_dict())
    assert clear is True
    apply_topic_boundary(ctx, reason=why)
    assert ctx.get("last_match") is None


def test_web_modes():
    ctx = {"deep_thinking": {"topic_kind": "opinion", "web_need": "optional", "topic_team": "Botafogo"}}
    assert decide_web_mode("o que acha do Botafogo?", ctx) == "light"
    ctx2 = {"deep_thinking": {"topic_kind": "moment", "web_need": "optional", "topic_team": "Flamengo"}}
    assert decide_web_mode("como esta o Flamengo atualmente?", ctx2) == "deep"
    ctx3 = {
        "deep_thinking": {
            "topic_kind": "moment",
            "web_need": "required",
            "web_mode": "research",
            "topic_team": "Flamengo",
        }
    }
    assert decide_web_mode("faca uma analise detalhada do Flamengo", ctx3) == "research"
    ctx4 = {"deep_thinking": {"topic_kind": "calendar", "web_need": "none"}}
    assert decide_web_mode("jogo do Santos hoje", ctx4) == "none"


def test_web_synthesis_builds_reasoning():
    wc = synthesize_web_context(
        snippets=["Flamengo busca regularidade no Brasileirão após sequência mista."],
        team="Flamengo",
        mode="deep",
        message="como esta o Flamengo atualmente?",
    )
    assert wc["facts"]
    assert wc["confidence"] > 0
    text = build_reasoning_from_web(wc, team="Flamengo", moment=True)
    assert "Flamengo" in text
    assert "Pensando no" not in text
    # empty → local
    empty = synthesize_web_context(snippets=[], team="Botafogo", mode="light", message="acha")
    local = build_reasoning_from_web(empty, team="Botafogo", moment=False)
    assert "Botafogo" in local
    assert "Pensando no" not in local


def test_ambiguous_horario_clarification():
    ctx: dict = {}
    res = resolve_reference("e o horario?", ctx)
    assert res.get("ambiguous") is True
    assert res.get("clarification")
    assert "?" != res["clarification"].strip()
    assert "interpretando" in res["clarification"].lower()
