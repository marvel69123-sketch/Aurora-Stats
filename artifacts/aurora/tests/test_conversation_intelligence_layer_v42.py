"""Aurora v4.2 — Conversation Intelligence Layer tests."""

from __future__ import annotations

from src.conversation.conversation_intelligence_layer import (
    humanize_text,
    refine_crl_reply,
    resolve_context_priority,
    run_intelligence,
)
from src.conversation.conversation_reasoner import attach_reasoning, reason
from src.conversation.conversation_response_layer import plan_response
from src.conversation.conversation_state import apply_after_analysis, note_pending_team


def _seed_bahia(ctx: dict | None = None) -> dict:
    ctx = dict(ctx or {})
    apply_after_analysis(
        ctx,
        "Bahia",
        "Chapecoense",
        "Bahia x Chapecoense",
        {
            "best_markets": [{"market": "Mais de 8.5 Escanteios", "risk": "medium"}],
            "risk": {"level": "Medium"},
            "final_recommendation": "Mais de 8.5 Escanteios",
        },
    )
    ctx["last_match"] = "Bahia x Chapecoense"
    ctx["last_home"] = "Bahia"
    ctx["last_away"] = "Chapecoense"
    return ctx


def _pipeline(message: str, ctx: dict):
    thought = reason(message, ctx)
    attach_reasoning(ctx, thought)
    cil = run_intelligence(message, ctx)
    plan = plan_response(message, ctx)
    refined = refine_crl_reply(plan.reply_text, ctx)
    if refined:
        plan.reply_text = refined
    return thought, cil, plan


# ── Scenario 1: compare markets on active fixture ──────────────────────────

def test_scenario1_qual_parece_melhor_compares_markets():
    ctx = _seed_bahia()
    _pipeline("e escanteios?", ctx)
    _pipeline("e gols?", ctx)
    _r, cil, plan = _pipeline("qual parece melhor?", ctx)

    goal = ctx.get("conversation_goal") or {}
    assert goal.get("goal_type") == "COMPARE_MARKETS"
    assert cil.selected_interpretation == "COMPARE_MARKETS"
    assert plan.mode == "COMPARISON_REPLY"
    assert plan.should_short_circuit is True
    text = (plan.reply_text or "").lower()
    assert "bahia" in text or "chapecoense" in text
    assert "confronto?" not in text
    assert "qual jogo" not in text
    # Should mention market comparison, not ask for a new fixture
    assert "escanteio" in text or "gol" in text or "mercado" in text or "caminho" in text


# ── Scenario 2: pending beats old fixture ──────────────────────────────────

def test_scenario2_pending_fla_beats_old_fixture():
    ctx = _seed_bahia()
    note_pending_team(ctx, "Flamengo")
    assert resolve_context_priority(ctx)["priority_winner"] == "pending_question"

    _r, cil, plan = _pipeline("oq acha desse jogo?", ctx)
    goal = ctx.get("conversation_goal") or {}
    assert goal.get("goal_type") == "CONTINUE_PENDING"
    assert cil.selected_interpretation == "CONTINUE_PENDING"
    text = plan.reply_text or ""
    assert "Flamengo" in text
    assert "Chapecoense" not in text
    assert "Bahia" not in text
    assert "adversário" in text.lower() or "adversario" in text.lower()


def test_scenario2_fala_do_fla_chain():
    ctx = _seed_bahia()
    _r1, cil1, plan1 = _pipeline("fala do fla", ctx)
    # Start pending explicitly (as router/CI would) and continue
    note_pending_team(ctx, "Flamengo")
    _r2, cil2, plan2 = _pipeline("oq acha desse jogo?", ctx)
    assert cil2.selected_interpretation == "CONTINUE_PENDING"
    assert "Flamengo" in (plan2.reply_text or "")
    assert "Chapecoense" not in (plan2.reply_text or "")


# ── Scenario 3: humanizer avoids stock openers ─────────────────────────────

def test_scenario3_humanizer_varies_and_strips_templates():
    ctx = _seed_bahia()
    robotic = "Na minha leitura, me parece que eu vejo valor nisso."
    out = humanize_text(robotic, family="opinion", ctx=ctx)
    low = out.lower()
    # Should not keep the stacked robotic opener cluster
    assert not low.startswith("na minha leitura")
    assert "me parece que eu vejo valor" not in low

    phrases = []
    for msg in ("por que?", "vale a pena?", "e esse?", "não gostei"):
        _r, _cil, plan = _pipeline(msg, dict(ctx))
        phrases.append((plan.reply_text or "")[:48])
    # Not all replies should start with the same stock opener
    starts = [p.split(",")[0].lower() for p in phrases if p]
    assert len(set(starts)) >= 2


# ── Scenario 4: long conversation coherence ────────────────────────────────

def test_scenario4_long_conversation_memory_and_low_repetition():
    ctx = _seed_bahia()
    script = [
        "e escanteios?",
        "e gols?",
        "qual parece melhor?",
        "por que?",
        "vale a pena?",
        "não gostei",
        "algo mais conservador?",
        "e esse?",
        "e cartões?",
        "oq acha?",
        "tem algo melhor?",
        "por que?",
        "e gols?",
        "qual parece melhor?",
        "não gostei",
        "algo mais agressivo?",
        "e escanteios?",
        "vale a pena?",
        "e esse?",
        "oq acha?",
        "por que?",
        "tem algo melhor?",
    ]
    replies: list[str] = []
    for msg in script:
        _r, cil, plan = _pipeline(msg, ctx)
        assert cil.confidence >= 0.0
        if plan.reply_text:
            replies.append(plan.reply_text)
        # Never invent opponent for pending-less path; fixture memory stays Bahia
        assert (ctx.get("conversation_state") or {}).get("active_fixture") == "Bahia x Chapecoense"

    assert len(replies) >= 18
    # Coherence: last compare/market answers still mention Bahia context often enough
    bahia_hits = sum(1 for r in replies if "Bahia" in r or "bahia" in r.lower())
    assert bahia_hits >= 6
    # Naturalness proxy: not every reply starts identically
    openers = [r[:24].lower() for r in replies]
    assert len(set(openers)) >= 8
    # Template ban: stacked "na minha leitura" should be rare at start
    robotic_starts = sum(1 for r in replies if r.lower().startswith("na minha leitura"))
    assert robotic_starts <= 2


def test_priority_order_explicit():
    ctx = _seed_bahia()
    note_pending_team(ctx, "Flamengo")
    view = resolve_context_priority(ctx)
    assert view["priority_winner"] == "pending_question"
    assert view["active_fixture"] == "Bahia x Chapecoense"
