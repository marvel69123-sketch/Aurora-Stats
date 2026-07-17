"""Aurora Brain Authority — topic boundary, recovery pair, DT SoT, calendar."""

from __future__ import annotations

import asyncio

from src.conversation.brain_authority import (
    apply_topic_boundary,
    calendar_empty_reply,
    crl_may_continue_fixture,
    ensure_fallback_for_thinking,
    hydrate_allowed,
    opinion_local_reasoning,
    should_clear_topic_boundary,
)
from src.conversation.context_recovery import apply_recovery_to_message, recover_context
from src.conversation.conversation_response_layer import plan_response
from src.conversation.conversation_reasoner import attach_reasoning, reason
from src.conversation.conversation_state import hydrate_from_legacy
from src.conversation.intelligence_fallback import (
    build_local_team_thinking,
    ensure_non_empty_payload,
)
from src.conversation.natural_conversation import detect_natural_intent
from src.conversation.response_review import run_deep_thinking_engine


def test_recovery_preserves_mirassol_gremio_pair():
    r = recover_context("quero saber sobre jogo do mirassol vs gremio hoje")
    assert "Mirassol" in r.teams
    assert "Gremio" in r.teams or "Grêmio" in r.teams
    assert r.inferred_goal == "calendar_or_fixture"
    assert "x" in r.recovered.lower() or "vs" in r.original.lower()
    assert r.teams[0] != r.teams[1]


def test_deep_thinking_fixture_pair():
    ctx: dict = {}
    r = recover_context("quero saber sobre jogo do mirassol vs gremio hoje", ctx)
    t = run_deep_thinking_engine(r.recovered, ctx, recovery=r.to_dict())
    assert t["topic_kind"] in {"fixture", "calendar"}
    assert t["needs_web"] is False


def test_topic_boundary_clears_prior_fixture():
    ctx = {
        "last_match": "Gremio x Mirassol",
        "last_home": "Gremio",
        "last_away": "Mirassol",
        "conversation_state": {"active_fixture": "Gremio x Mirassol"},
    }
    r = recover_context("juventus joga que horas?", ctx)
    run_deep_thinking_engine(
        apply_recovery_to_message("juventus joga que horas?", ctx),
        ctx,
        recovery=r.to_dict(),
    )
    clear, why = should_clear_topic_boundary(
        "juventus joga que horas?", ctx, recovery=r.to_dict()
    )
    assert clear is True
    apply_topic_boundary(ctx, reason=why)
    assert ctx.get("last_match") is None
    assert hydrate_allowed(ctx) is False
    hydrate_from_legacy(ctx)
    assert not (ctx.get("conversation_state") or {}).get("active_fixture")


def test_crl_blocked_after_boundary():
    ctx = {
        "last_match": "Gremio x Mirassol",
        "last_home": "Gremio",
        "last_away": "Mirassol",
        "deep_thinking": {
            "topic_kind": "kickoff",
            "topic_team": "Juventus",
            "user_real_want": "horário",
        },
        "block_hydrate_legacy": True,
        "brain_boundary_cleared": True,
    }
    assert crl_may_continue_fixture(ctx) is False
    # Reasoner should not USE_ACTIVE_CONTEXT
    rr = reason("juventus joga que horas?", ctx)
    attach_reasoning(ctx, rr)
    plan = plan_response("juventus joga que horas?", ctx)
    assert plan.should_short_circuit is False or plan.used_next_action != "USE_ACTIVE_CONTEXT"


def test_santos_today_calendar_intent():
    out = apply_recovery_to_message("tem jogo do santos hoje?", {})
    assert "santos" in out.lower()
    d = detect_natural_intent(out)
    assert d and d["kind"] in {"team_calendar", "calendar_today"}
    ctx: dict = {}
    r = recover_context("tem jogo do santos hoje?", ctx)
    t = run_deep_thinking_engine(out, ctx, recovery=r.to_dict())
    assert t["topic_kind"] in {"calendar", "fixture"}


def test_ensure_non_empty_calendar_not_pensando():
    ctx = {
        "deep_thinking": {
            "topic_kind": "calendar",
            "topic_team": "Gremio",
            "topic_teams": ["Mirassol", "Gremio"],
        },
        "context_recovery": {"teams": ["Mirassol", "Gremio"]},
    }
    payload = {
        "intent": "unknown",
        "entities": {},
        "executive_summary": "?",
        "final_recommendation": "?",
        "response_metadata": {},
    }
    out = ensure_non_empty_payload(
        payload, message="jogo mirassol x gremio hoje", ctx=ctx
    )
    text = out["executive_summary"]
    assert "Pensando no" not in text
    assert "Mirassol" in text or "agenda" in text.lower() or "jogo" in text.lower()


def test_no_pensando_no_in_local_thinking():
    text = build_local_team_thinking("Botafogo", moment=True)
    assert "Pensando no" not in text
    assert "Botafogo" in text


def test_opinion_local_reasoning_moment():
    text = opinion_local_reasoning("Flamengo", moment=True)
    assert "mesmo sem" in text.lower() or "momento" in text.lower()
    assert "Pensando no" not in text


def test_calendar_empty_reply_pair():
    text = calendar_empty_reply(teams=["Mirassol", "Gremio"], kind="fixture")
    assert "Mirassol" in text and "Gremio" in text
    assert "Pensando no" not in text


def test_natural_detects_kickoff():
    d = detect_natural_intent("juventus joga que horas?")
    assert d and d["kind"] == "kickoff_lookup"


def test_natural_detects_team_calendar():
    d = detect_natural_intent("jogo do Santos hoje")
    assert d and d["kind"] == "team_calendar"
    assert d.get("team") == "Santos" or "Santos" in (d.get("teams") or [])


def test_entity_pivot_santos_clears_mirassol():
    ctx = {
        "last_match": "Mirassol x Gremio",
        "last_home": "Mirassol",
        "last_away": "Gremio",
        "conversation_state": {"active_fixture": "Mirassol x Gremio"},
    }
    r = recover_context("e o santos?", ctx)
    out = apply_recovery_to_message("e o santos?", ctx)
    run_deep_thinking_engine(out, ctx, recovery=r.to_dict())
    clear, why = should_clear_topic_boundary(out, ctx, recovery=r.to_dict())
    assert clear is True, why
    apply_topic_boundary(ctx, reason=why)
    assert ctx.get("last_match") is None
    assert crl_may_continue_fixture(ctx) is False
