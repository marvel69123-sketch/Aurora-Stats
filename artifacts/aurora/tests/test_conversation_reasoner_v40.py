"""Aurora v4.0 Sprint 1 — Conversation Reasoner foundation tests."""

from __future__ import annotations

from src.conversation.conversation_reasoner import reason
from src.conversation.conversation_state import apply_after_analysis, note_pending_team


def _seed_active(ctx: dict | None = None) -> dict:
    ctx = dict(ctx or {})
    apply_after_analysis(
        ctx,
        "Botafogo",
        "Santos",
        "Botafogo x Santos",
        {
            "best_markets": [
                {"market": "Mais de 8.5 Escanteios", "risk": "high", "rank": 1}
            ],
            "risk": {"level": "High"},
            "final_recommendation": "Mais de 8.5 Escanteios com stake reduzida",
        },
    )
    ctx["last_home"] = "Botafogo"
    ctx["last_away"] = "Santos"
    ctx["last_match"] = "Botafogo x Santos"
    ctx["last_recommendation"] = "Mais de 8.5 Escanteios com stake reduzida"
    return ctx


def _seed_two_fixtures() -> dict:
    ctx = _seed_active()
    apply_after_analysis(
        ctx,
        "Vitoria",
        "Vasco",
        "Vitoria x Vasco",
        {
            "best_markets": [{"market": "Over 2.5 Goals", "risk": "medium"}],
            "final_recommendation": "Over 2.5",
        },
    )
    ctx["prev_home"] = "Botafogo"
    ctx["prev_away"] = "Santos"
    ctx["prev_match"] = "Botafogo x Santos"
    return ctx


# ── Mandatory phrases ──────────────────────────────────────────────────────

def test_qual_parece_melhor_is_comparison():
    ctx = _seed_two_fixtures()
    r = reason("qual parece melhor?", ctx)
    assert r.reasoning_type == "COMPARISON"
    assert r.next_action == "COMPARE_HISTORY"
    assert r.requires_context is True
    assert r.confidence >= 0.7
    assert "Botafogo" in r.comparison_target or "Botafogo" in r.thought
    assert r.thought  # internal narration present


def test_esse_parece_ruim_is_rejection():
    ctx = _seed_active()
    r = reason("esse parece ruim", ctx)
    assert r.reasoning_type == "MARKET_REJECTION"
    assert r.next_action == "SEEK_ALTERNATIVE"
    assert "Mais de 8.5" in r.thought or "alternativa" in r.thought.lower()


def test_vale_a_pena_is_preference():
    ctx = _seed_active()
    r = reason("vale a pena?", ctx)
    assert r.reasoning_type == "PREFERENCE_SIGNAL"
    assert r.next_action == "PREFER_BETTER"
    assert r.confidence >= 0.7
    assert "Botafogo" in (r.active_fixture or "")


def test_oq_acha_with_context_uses_active():
    ctx = _seed_active()
    r = reason("oq acha?", ctx)
    assert r.reasoning_type in {"FOLLOWUP_FIXTURE", "EXPLANATION"}
    assert r.next_action in {"USE_ACTIVE_CONTEXT", "EXPLAIN_LAST"}
    assert r.requires_context is True
    assert "contexto" in r.thought.lower() or "ativo" in r.thought.lower()


def test_oq_acha_without_context_clarifies():
    r = reason("oq acha?", {})
    assert r.reasoning_type == "CLARIFY"
    assert r.next_action == "ASK_FIXTURE"
    assert "active_fixture" in r.missing_information


def test_nao_gostei_seek_alternative():
    ctx = _seed_active()
    r = reason("não gostei", ctx)
    assert r.reasoning_type == "MARKET_REJECTION"
    assert r.next_action == "SEEK_ALTERNATIVE"
    assert r.confidence >= 0.85


def test_e_esse_uses_active_context():
    ctx = _seed_active()
    r = reason("e esse?", ctx)
    assert r.reasoning_type in {"FOLLOWUP_FIXTURE", "FOLLOWUP_MARKET"}
    assert r.next_action == "USE_ACTIVE_CONTEXT"
    assert r.active_fixture == "Botafogo x Santos"


def test_por_que_is_explanation():
    ctx = _seed_active()
    r = reason("por que?", ctx)
    assert r.reasoning_type == "EXPLANATION"
    assert r.next_action == "EXPLAIN_LAST"
    assert r.requires_context is True


# ── Spec examples ──────────────────────────────────────────────────────────

def test_e_gols_followup_market_high_confidence():
    ctx = _seed_active()
    r = reason("e gols?", ctx)
    assert r.reasoning_type == "FOLLOWUP_MARKET"
    assert r.next_action == "PASS_MARKET_FOLLOWUP"
    assert r.confidence >= 0.9
    assert "trocar" in r.thought.lower() or "mercado" in r.thought.lower()


def test_fala_do_fla_then_oq_acha_desse_jogo_still_needs_opponent():
    ctx: dict = {}
    note_pending_team(ctx, "Flamengo")
    r1 = reason("fala do fla", ctx)
    assert r1.reasoning_type == "CLARIFY"
    assert r1.next_action == "ASK_OPPONENT"
    assert "opponent" in r1.missing_information

    r2 = reason("oq acha desse jogo?", ctx)
    assert r2.reasoning_type == "CLARIFY"
    assert r2.next_action == "ASK_OPPONENT"
    assert "Flamengo" in r2.thought or "pendente" in r2.thought.lower()


def test_reasoner_never_returns_user_reply_fields():
    """Reasoner plans only — no executive_summary / final_recommendation."""
    r = reason("não gostei", _seed_active())
    d = r.to_dict()
    assert "executive_summary" not in d
    assert "final_recommendation" not in d
    assert "user_goal" in d
    assert "thought" in d


def test_fail_open_on_bad_ctx():
    r = reason("e gols?", None)
    assert r.reasoning_type in {"CLARIFY", "AMBIGUOUS", "FOLLOWUP_MARKET"}
    assert r.confidence >= 0.0
