"""Phase 7.9-B P0-2 — NRF anti sticky regenerate."""

from __future__ import annotations

from src.conversation.general_assistant import reply_general
from src.conversation.natural_response_filter import (
    extremely_similar,
    filter_or_regenerate,
)


def test_extremely_similar_entendi():
    a = reply_general("a")
    b = reply_general("b")
    assert extremely_similar(a, b)


def test_second_regenerate_bypasses_entendi():
    ctx: dict = {}
    g = reply_general("x")
    t1 = filter_or_regenerate(g, master_intent="GENERAL_CHAT", ctx=ctx, regenerate=g)
    t2 = filter_or_regenerate(g, master_intent="GENERAL_CHAT", ctx=ctx, regenerate=g)
    assert t1.startswith("Entendi. Posso te ajudar")
    assert not t2.startswith("Entendi. Posso te ajudar")
    assert ctx.get("nrf_last_action") == "bypass"


def test_third_also_not_entendi():
    ctx: dict = {}
    g = reply_general("x")
    filter_or_regenerate(g, master_intent="GENERAL_CHAT", ctx=ctx, regenerate=g)
    filter_or_regenerate(g, master_intent="GENERAL_CHAT", ctx=ctx, regenerate=g)
    t3 = filter_or_regenerate(g, master_intent="GENERAL_CHAT", ctx=ctx, regenerate=g)
    assert "Entendi. Posso te ajudar" not in t3
