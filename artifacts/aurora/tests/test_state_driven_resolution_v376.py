"""Aurora v3.7.6 — State Driven Resolution tests."""

from __future__ import annotations

from src.conversation.conversation_state import (
    apply_after_analysis,
    detect_human_intent,
    get_state,
)
from src.conversation.message_intelligence import process_inbound_message
from src.conversation.state_driven_resolution import (
    expand_sports_aliases,
    pre_resolve,
    suggest_alternatives,
)


def _seed_corners(ctx: dict | None = None) -> dict:
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
    ctx["last_fixture"] = "Botafogo x Santos"
    ctx["last_market"] = [{"market": "Mais de 8.5 Escanteios", "risk": "high"}]
    ctx["last_recommendation"] = "Mais de 8.5 Escanteios com stake reduzida"
    return ctx


# ── Aliases ────────────────────────────────────────────────────────────────

def test_sports_aliases_expand():
    text, hits = expand_sports_aliases("analise fogao x peixe")
    assert "botafogo" in text
    assert "santos" in text
    assert any("fogao" in h for h in hits)
    assert any("peixe" in h for h in hits)


def test_alias_vasco_gama_and_vitoria_ba():
    t1, _ = expand_sports_aliases("vasco gama hoje")
    assert "vasco" in t1
    t2, hits = expand_sports_aliases("vitoria ba")
    assert "vitoria" in t2
    assert hits


def test_pre_resolve_fogao_x_peixe():
    pr = pre_resolve("analise fogao x peixe", {})
    assert pr.home == "Botafogo"
    assert pr.away == "Santos"
    assert pr.fixture_label == "Botafogo x Santos"
    assert "botafogo" in pr.rewritten.lower()
    assert "santos" in pr.rewritten.lower()
    assert pr.confidence >= 0.85
    assert pr.needs_opponent is False


def test_pre_resolve_never_invents_opponent_for_fla():
    pr = pre_resolve("fala do fla", {})
    assert pr.needs_opponent is True
    assert pr.single_team == "Flamengo"
    assert pr.away is None
    assert pr.home is None or pr.fixture_label is None


def test_pre_resolve_reuses_active_fixture_for_corners():
    ctx = _seed_corners()
    pr = pre_resolve("e escanteios?", ctx)
    assert pr.reused_active_fixture is True
    assert pr.fixture_label == "Botafogo x Santos"
    assert "botafogo" not in pr.rewritten.lower()  # market phrase preserved


# ── Histories ──────────────────────────────────────────────────────────────

def test_market_and_fixture_history_on_switch():
    ctx = _seed_corners()
    st1 = get_state(ctx)
    assert st1["market_history"]
    assert st1["market_history"][0]["market"] == "Mais de 8.5 Escanteios"

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
    st2 = get_state(ctx)
    assert st2["active_fixture"] == "Vitoria x Vasco"
    assert st2["fixture_history"]
    assert st2["fixture_history"][0]["fixture"] == "Botafogo x Santos"
    assert any(h.get("market") == "Over 2.5 Goals" for h in st2["market_history"])


# ── Contextual generation ──────────────────────────────────────────────────

def test_suggest_conservative_uses_family():
    alts = suggest_alternatives(
        bias="conservative",
        active_market="Mais de 8.5 Escanteios",
        last_risk="high",
        market_history=[],
    )
    assert alts
    blob = " ".join(alts).lower()
    assert "escanteio" in blob or "stake" in blob or "under" in blob or "risco" in blob


def test_contextual_conservative_reply():
    ctx = _seed_corners()
    r = process_inbound_message("algo mais conservador?", ctx)
    assert r.conversational_reply
    assert "Mais de 8.5 Escanteios" in r.conversational_reply
    assert "Botafogo x Santos" in r.conversational_reply
    assert "high" in r.conversational_reply.lower() or "High" in r.conversational_reply
    assert "•" in r.conversational_reply


def test_contextual_aggressive_reply():
    ctx = _seed_corners()
    r = process_inbound_message("algo mais agressivo?", ctx)
    assert r.conversational_reply
    assert "Mais de 8.5 Escanteios" in r.conversational_reply
    assert "agressiv" in r.conversational_reply.lower()


def test_contextual_better_uses_history():
    ctx = _seed_corners()
    r = process_inbound_message("tem algo melhor?", ctx)
    assert r.conversational_reply
    assert "Mais de 8.5 Escanteios" in r.conversational_reply
    assert "Botafogo" in r.conversational_reply


def test_compare_os_dois_uses_fixture_history():
    ctx = _seed_corners()
    apply_after_analysis(
        ctx,
        "Vitoria",
        "Vasco",
        "Vitoria x Vasco",
        {
            "best_markets": [{"market": "BTTS", "risk": "medium"}],
            "final_recommendation": "BTTS",
        },
    )
    assert detect_human_intent("compare os dois") == "ASK_COMPARISON"
    r = process_inbound_message("compare os dois", ctx)
    assert r.conversational_reply
    assert "Vitoria x Vasco" in r.conversational_reply
    assert "Botafogo x Santos" in r.conversational_reply


def test_pipeline_rewrites_alias_fixture():
    r = process_inbound_message("analise fogao x peixe", {})
    assert r.needs_clarification is False
    pipe = r.message_for_pipeline.lower()
    assert "botafogo" in pipe
    assert "santos" in pipe
    assert r.metadata.get("pre_resolve")
    assert r.metadata["pre_resolve"].get("home") == "Botafogo"
