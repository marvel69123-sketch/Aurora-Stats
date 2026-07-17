"""Human Conversation Engine P0 — validation flows 1–5."""

from __future__ import annotations

import re

from src.conversation.human_conversation_engine import (
    note_hce_after_response,
    try_human_conversation,
    wants_analyze_without_fixture,
)
from src.conversation.human_conversation_state import get_hce_state
from src.conversation.master_intent_router import apply_master_intent


def _turn(msg: str, ctx: dict, *, master: str | None = None):
    m = apply_master_intent(msg, ctx)
    # Simulate router: GA then HCE (GA omitted except we pass existing None)
    p = try_human_conversation(
        msg,
        ctx,
        master_intent=master or m.intent,
        existing_payload=None,
    )
    if p:
        note_hce_after_response(ctx, msg, p)
    return m, p


def test_flow1_analyze_then_sim_continues():
    ctx: dict = {}
    _, p1 = _turn("oi", ctx)
    # oi may be None here (GA handles in router); seed social
    from src.conversation.general_assistant import try_general_assistant

    apply_master_intent("boa noite", ctx)
    ga = try_general_assistant("boa noite", "SMALL_TALK", ctx)
    assert ga

    assert wants_analyze_without_fixture("perfeito quero analisar um jogo")
    _, p = _turn("perfeito quero analisar um jogo", ctx)
    assert p is not None
    text = p["executive_summary"].lower()
    assert "?" not in text or "jogo" in text  # asks which game, not lost "?"
    assert "x" in text or "confronto" in text or "jogo" in text
    assert get_hce_state(ctx).get("last_expected_action") == "awaiting_fixture"

    _, p2 = _turn("sim", ctx)
    assert p2 is not None
    t2 = p2["executive_summary"].lower()
    assert "confronto" in t2 or "time a" in t2 or "x" in t2
    assert "oi!" not in t2  # must not restart greeting
    assert get_hce_state(ctx).get("last_expected_action") == "awaiting_fixture"


def test_flow2_live_followup_meta():
    ctx: dict = {}
    m, p = _turn("Fluminense ao vivo", ctx)
    assert m.intent in {"LIVE_MATCH", "SPORT_QUERY"}
    # HCE annotates and lets sport pipeline run
    assert p is None
    st = get_hce_state(ctx)
    assert st.get("last_entity")
    assert "placar" in (st.get("expectation_hints") or [])

    _, p2 = _turn("e agora?", ctx)
    assert p2 is not None
    assert "fluminense" in p2["executive_summary"].lower() or "agora" in p2[
        "executive_summary"
    ].lower()

    _, p3 = _turn("qual mercado?", ctx)
    assert p3 is not None
    assert "mercado" in p3["executive_summary"].lower()

    _, p4 = _turn("de onde vêm esses dados?", ctx)
    assert p4 is not None
    t = p4["executive_summary"].lower()
    assert "api" in t or "fonte" in t or "dados" in t
    assert "melhor aposta" not in t


def test_flow3_bankroll_save_stake():
    ctx: dict = {}
    _, p1 = _turn("minha banca é 100 reais", ctx)
    assert p1 is not None
    assert "100" in p1["executive_summary"]
    assert get_hce_state(ctx).get("pending_bankroll") == 100.0 or get_hce_state(ctx).get(
        "last_expected_action"
    ) in {"awaiting_bankroll_confirm", "bankroll_ready"}

    _, p2 = _turn("salve isso", ctx)
    assert p2 is not None
    assert "salvei" in p2["executive_summary"].lower() or "guardei" in p2[
        "executive_summary"
    ].lower()
    assert (ctx.get("user_profile") or {}).get("bankroll") == 100.0

    _, p3 = _turn("quanto devo arriscar?", ctx)
    assert p3 is not None
    assert "100" in p3["executive_summary"]
    assert "%" in p3["executive_summary"] or "r$" in p3["executive_summary"].lower()


def test_flow4_social_then_sport_short_followup():
    ctx: dict = {}
    for msg in [
        "oi",
        "tudo bem?",
        "bom dia",
        "beleza",
        "qual seu nome?",
        "quanto é 2+2?",
        "obrigado",
        "valeu",
        "boa tarde",
        "e ai",
        "hey",
        "blz",
        "tchau",
        "oi aurora",
        "como voce esta?",
        "quem te criou?",
        "ajuda",
        "boa noite",
        "ok",
        "perfeito",
    ]:
        apply_master_intent(msg, ctx)
        try_human_conversation(msg, ctx, master_intent="SMALL_TALK")

    m, p = _turn("Fluminense ao vivo", ctx)
    assert m.allow_sport_pipeline is True
    assert get_hce_state(ctx).get("last_entity")

    _, p2 = _turn("continua", ctx)
    assert p2 is not None
    assert "fluminense" in p2["executive_summary"].lower() or "seguindo" in p2[
        "executive_summary"
    ].lower()


def test_flow5_100_mixed_no_question_mark_lost():
    ctx: dict = {}
    lost = 0
    scripts = []
    for i in range(25):
        scripts.extend(
            [
                "oi",
                "perfeito quero analisar um jogo",
                "sim",
                "quanto é 2+2?",
                "Fluminense ao vivo",
                "e agora?",
                "de onde vêm esses dados?",
                "minha banca é 50 reais",
                "salve isso",
                "qual seu nome?",
            ]
        )
    scripts = scripts[:110]
    for msg in scripts:
        m = apply_master_intent(msg, ctx)
        p = try_human_conversation(msg, ctx, master_intent=m.intent)
        if p:
            note_hce_after_response(ctx, msg, p)
            text = str(p.get("executive_summary") or "").strip()
            if text in {"?", "?", "? 😊", "😊"} or re.fullmatch(r"[?？]+\s*😊?", text):
                lost += 1
            # Contamination: meta must not dump markets speech
            if "de onde" in msg.lower() and "over 2.5" in text.lower():
                lost += 1
    assert lost == 0


def test_hce_state_survives_hard_block():
    ctx: dict = {}
    _turn("perfeito quero analisar um jogo", ctx)
    assert get_hce_state(ctx).get("last_expected_action") == "awaiting_fixture"
    # Non-sport hard block clears focus but must keep HCE
    apply_master_intent("oi", ctx)
    assert get_hce_state(ctx).get("last_expected_action") == "awaiting_fixture"
    _, p = _turn("sim", ctx)
    assert p is not None
    assert "confronto" in p["executive_summary"].lower() or "time" in p[
        "executive_summary"
    ].lower()
