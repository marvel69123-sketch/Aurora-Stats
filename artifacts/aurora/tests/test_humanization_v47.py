"""Aurora v4.7 — humanization, identity memory, agenda, web reasoner, formatter."""

from __future__ import annotations

import asyncio
import re

from src.conversation.emotional_presence import (
    detect_emotional_intent,
    try_emotional_presence,
)
from src.conversation.natural_conversation import (
    _filter_brasileirao_only,
    _format_agenda_blocks,
    detect_natural_intent,
    build_team_opinion_reply,
)
from src.conversation.response_formatter import (
    apply_formatter_to_payload,
    format_user_facing_text,
)
from src.conversation.user_profile_memory import (
    clear_profile,
    detect_forget_command,
    detect_profile_teach,
    get_profile,
    greeting_prefix,
    save_profile,
    try_profile_commands,
)
from src.conversation.web_intelligence import (
    decide_need_web,
    semantic_cache_plan,
)
from src.conversation.reflection_credibility import apply_credibility_to_payload, run_reflection


def test_emotional_pride_not_analysis_pitch():
    kind = detect_emotional_intent("tenho orgulho de voce")
    assert kind == "pride"
    assert detect_emotional_intent("voce e minha maior criacao") == "pride"
    payload = try_emotional_presence("tenho orgulho de voce", {}, {"emojis": "none"})
    assert payload
    text = (payload.get("executive_summary") or "").lower()
    assert "posso ajudar com" not in text
    assert "leituras" not in text
    assert payload["best_markets"] == []
    assert payload.get("intent") == "emotional"


def test_emotional_affection_and_thanks():
    assert detect_emotional_intent("voce me ajuda muito") == "affection"
    assert detect_emotional_intent("obrigado aurora") == "thanks_named"
    p = try_emotional_presence("gosto de conversar com voce", {})
    assert p
    text = (p.get("executive_summary") or "").lower()
    assert "feliz" in text or "gosto" in text or "deix" in text


def test_about_you_separate_from_betting_profile():
    ctx = {
        "user_profile": {"bankroll": 500.0, "experience_level": "beginner"},
        "about_you": {},
    }
    save_profile(ctx, {"name": "Achiro", "project": "Aurora"})
    assert get_profile(ctx)["name"] == "Achiro"
    assert ctx["user_profile"]["bankroll"] == 500.0  # untouched
    clear_profile(ctx)
    assert get_profile(ctx)["name"] == ""
    assert ctx["user_profile"]["bankroll"] == 500.0


def test_profile_teach_and_forget():
    assert detect_profile_teach("Meu nome é Achiro") == {"name": "Achiro"}
    assert detect_forget_command("apague minhas informações")
    ctx: dict = {}
    payload = try_profile_commands("Meu nome é Achiro", ctx)
    assert payload
    assert get_profile(ctx)["name"] == "Achiro"
    payload2 = try_profile_commands("apague minhas informações", ctx)
    assert payload2
    assert get_profile(ctx)["name"] == ""


def test_greeting_prefix_with_project():
    ctx = {}
    save_profile(ctx, {"name": "Achiro", "project": "Aurora"})
    g = greeting_prefix(ctx)
    assert g and "Achiro" in g
    assert "Aurora" in g or "testes" in g.lower()


def test_brasileirao_flag_not_always_true():
    d = detect_natural_intent("quais jogos amanha?")
    assert d["kind"] == "calendar_tomorrow"
    assert d["brasileirao"] is False
    d2 = detect_natural_intent("Quais jogos do Brasileirao amanha?")
    assert d2["kind"] == "calendar_tomorrow"
    assert d2["brasileirao"] is True
    d3 = detect_natural_intent("proxima rodada")
    assert d3["brasileirao"] is True


def test_agenda_ux_blocks():
    items = [
        {
            "teams": {"home": {"name": "Bahia"}, "away": {"name": "Flamengo"}},
            "fixture": {"date": "2026-07-13T22:00:00+00:00"},
            "league": {"id": 71, "name": "Serie A", "country": "Brazil"},
        },
        {
            "teams": {"home": {"name": "Palmeiras"}, "away": {"name": "Corinthians"}},
            "fixture": {"date": "2026-07-14T00:30:00+00:00"},
            "league": {"id": 71, "name": "Serie A", "country": "Brazil"},
        },
    ]
    body = _format_agenda_blocks(items, title="⚽ Jogos do Brasileirão amanhã")
    assert "⚽ Jogos do Brasileirão amanhã" in body
    assert "Bahia x Flamengo" in body
    assert "Palmeiras x Corinthians" in body
    assert re.search(r"[🕖🕘🕕🕒]\s+\d{2}:\d{2}", body)


def test_brasileirao_filter_excludes_foreign():
    mixed = [
        {
            "league": {"id": 71, "name": "Serie A", "country": "Brazil"},
            "teams": {"home": {"name": "A"}, "away": {"name": "B"}},
            "fixture": {"date": "2026-07-13T22:00:00Z"},
        },
        {
            "league": {"id": 254, "name": "NWSL", "country": "USA"},
            "teams": {"home": {"name": "X"}, "away": {"name": "Y"}},
            "fixture": {"date": "2026-07-13T18:00:00Z"},
        },
        {
            "league": {"id": 253, "name": "Major League Soccer", "country": "USA"},
            "teams": {"home": {"name": "M"}, "away": {"name": "N"}},
            "fixture": {"date": "2026-07-13T19:00:00Z"},
        },
    ]
    filtered = _filter_brasileirao_only(mixed)
    assert len(filtered) == 1
    assert filtered[0]["league"]["id"] == 71


def test_team_opinion_is_conversational():
    reply = build_team_opinion_reply("Botafogo")
    assert "Botafogo" in reply
    assert "probabilidade" not in reply.lower()
    assert "EV" not in reply
    d = detect_natural_intent("o que acha do Botafogo?")
    assert d and d["kind"] == "team_opinion"


def test_formatter_scrubs_robotic():
    out = format_user_facing_text("Considerando o contexto, o fixture_id parece ok.")
    assert "considerando o contexto" not in out.lower()
    assert "fixture_id" not in out.lower()
    payload = {
        "intent": "emotional",
        "entities": {"emotional": True},
        "executive_summary": "Analisando os fatores com carinho.",
        "final_recommendation": "Analisando os fatores com carinho.",
        "response_metadata": {
            "credibility": {
                "display_mode": "SOCIAL",
                "thinking_label": "Considerando o contexto...",
            }
        },
    }
    outp = apply_formatter_to_payload(payload)
    assert "analisando os fatores" not in (outp["executive_summary"] or "").lower()
    cred = (outp.get("response_metadata") or {}).get("credibility") or {}
    assert cred.get("thinking_label") is None


def test_need_web_cases():
    assert decide_need_web("analise Botafogo x Santos", intent="analyze_match").need == "none"
    assert decide_need_web(
        "o que acha do Botafogo?",
        entities={"natural_kind": "team_opinion", "team": "Botafogo"},
    ).need == "optional"
    assert decide_need_web("o que achou da Copa de 2026?").need == "required"
    assert decide_need_web("oi", intent="small_talk").need == "none"
    plan = semantic_cache_plan()
    assert plan["status"] == "prepared_not_active"
    assert "Botafogo" in plan["entities"]


def test_emotional_credibility_social():
    payload = try_emotional_presence("voce e minha melhor criacao", {})
    assert payload
    refl = run_reflection("voce e minha melhor criacao", {}, payload["executive_summary"])
    out = apply_credibility_to_payload(payload, refl, {})
    cred = (out.get("response_metadata") or {}).get("credibility") or {}
    assert cred.get("display_mode") == "SOCIAL"
    assert out.get("best_markets") == []


def test_emotional_async_smoke():
    # ensure try_emotional is sync-safe under asyncio loop
    async def _run():
        return try_emotional_presence("obrigado aurora", {"about_you": {"name": "Caio"}})

    p = asyncio.run(_run())
    assert p and p["intent"] == "emotional"
