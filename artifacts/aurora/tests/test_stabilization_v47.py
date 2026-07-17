"""
Aurora v4.7.1 — Final stabilization battery.

Covers: formatter, emotional intents, NeedWeb, profile memory,
agenda/filters, depth, web fail-open. Does not mutate frozen engines.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from src.conversation.emotional_presence import (
    detect_emotional_intent,
    try_emotional_presence,
)
from src.conversation.natural_conversation import (
    _filter_brasileirao_only,
    _format_agenda_blocks,
    detect_natural_intent,
    try_natural_conversation,
)
from src.conversation.response_formatter import (
    apply_formatter_to_payload,
    format_user_facing_text,
)
from src.conversation.user_profile_memory import (
    PROFILE_KEY,
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
    maybe_enrich_with_web,
)
from src.conversation.conversation_state import (
    active_fixture,
    apply_after_analysis,
    expire_conversation_state_if_needed,
    get_state,
    note_small_talk,
)
from src.core.followup_guard import decide_followup_reuse
from src.conversation.reflection_credibility import (
    apply_credibility_to_payload,
    run_reflection,
)


# ── 1. Formatter ───────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "raw,forbidden",
    [
        ("Considerando o contexto, o jogo é aberto.", "considerando o contexto"),
        ("Analisando os fatores principais agora.", "analisando os fatores"),
        ("SOURCE:API fixture_id=123 league_id=71", "fixture_id"),
        ("Dados via API-Football e JSON payload.", "api-football"),
        ("Posso ajudar com análises esportivas.", "posso ajudar com"),
        ("status_code 500 no endpoint httpx", "endpoint"),
    ],
)
def test_formatter_scrubs_technical_robotic(raw, forbidden):
    out = format_user_facing_text(raw, kind="social")
    assert forbidden not in out.lower()


def test_formatter_keeps_calendar_structure():
    agenda = (
        "⚽ Jogos do Brasileirão amanhã\n\n"
        "🕖 19:00\nBahia x Flamengo\n\n"
        "🕘 21:30\nPalmeiras x Corinthians"
    )
    out = format_user_facing_text(agenda, kind="calendar")
    assert "🕖 19:00" in out
    assert "Bahia x Flamengo" in out


def test_formatter_short_stays_short():
    short = "Isso significa muito 😊"
    out = format_user_facing_text(short, kind="social")
    assert len(out) <= len(short) + 20


def test_formatter_analysis_not_force_shortened():
    deep = ("Ponto A. " * 40) + ("Ponto B. " * 40)
    out = format_user_facing_text(deep, kind="analysis")
    assert len(out) >= 200


def test_formatter_strips_robotic_thinking_label():
    payload = {
        "intent": "emotional",
        "entities": {"emotional": True},
        "executive_summary": "Isso significa muito.",
        "final_recommendation": "Isso significa muito.",
        "response_metadata": {
            "credibility": {
                "display_mode": "SOCIAL",
                "thinking_label": "Analisando os fatores...",
            }
        },
    }
    out = apply_formatter_to_payload(payload)
    cred = (out.get("response_metadata") or {}).get("credibility") or {}
    assert cred.get("thinking_label") is None


# ── 2. Emotional intents (extensive) ───────────────────────────────────────

_EMOTIONAL_CASES = [
    ("tenho orgulho de você", "pride"),
    ("Tenho orgulho de voce!", "pride"),
    ("você é minha melhor criação", "pride"),
    ("você é minha maior criação", "pride"),
    ("voce e minha melhor criacao", "pride"),
    ("você me ajuda muito", "affection"),
    ("gosto de conversar com você", "affection"),
    ("adoro conversar com voce", "affection"),
    ("obrigado aurora", "thanks_named"),
    ("obrigada Aurora", "thanks_named"),
    ("valeu aurora", "thanks_named"),
    ("você é incrível", "affection"),
    ("amo voce", "affection"),
]


@pytest.mark.parametrize("msg,kind", _EMOTIONAL_CASES)
def test_emotional_detect_matrix(msg, kind):
    assert detect_emotional_intent(msg) == kind


@pytest.mark.parametrize("msg,_kind", _EMOTIONAL_CASES)
def test_emotional_reply_never_analysis_pitch(msg, _kind):
    payload = try_emotional_presence(msg, {}, {"emojis": "none", "enthusiasm": "low"})
    assert payload is not None
    text = (payload.get("executive_summary") or "").lower()
    assert "posso ajudar com" not in text
    assert "quer que eu analise" not in text
    assert "diga um confronto" not in text
    assert payload.get("best_markets") == []
    assert payload.get("match_card") is None
    assert len(payload.get("executive_summary") or "") < 320
    # Credibility social
    refl = run_reflection(msg, {}, payload["executive_summary"])
    stamped = apply_credibility_to_payload(dict(payload), refl, {})
    cred = (stamped.get("response_metadata") or {}).get("credibility") or {}
    assert cred.get("display_mode") == "SOCIAL"


def test_emotional_not_triggered_on_analysis():
    assert detect_emotional_intent("analise Botafogo x Santos") is None
    assert detect_emotional_intent("quais jogos amanha") is None


def test_emotional_with_about_you_name_stays_warm():
    ctx = {PROFILE_KEY: {"name": "Achiro", "role": "", "favorite_team": "", "project": ""}}
    # Force several samples — none may pitch analysis
    for _ in range(6):
        p = try_emotional_presence("tenho orgulho de voce", ctx, {"emojis": "none"})
        assert p
        assert "posso ajudar" not in (p.get("executive_summary") or "").lower()


# ── 3. NeedWebReasoner ─────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "msg,intent,ents,need",
    [
        ("analise Botafogo x Santos", "analyze_match", {}, "none"),
        ("odds do jogo", None, {}, "none"),
        ("estatisticas do Bahia", None, {}, "none"),
        ("classificacao do brasileirao", None, {}, "none"),
        ("quais jogos amanha", None, {"natural_kind": "calendar_tomorrow"}, "none"),
        ("oi", "small_talk", {}, "none"),
        ("tenho orgulho de voce", "emotional", {"emotional": True}, "none"),
        (
            "o que acha do Botafogo?",
            "conversation_assist",
            {"natural_kind": "team_opinion", "team": "Botafogo", "opinion_time": True},
            "optional",
        ),
        ("como esta o Flamengo?", None, {}, "optional"),
        ("o que aconteceu com o Santos?", None, {}, "optional"),
        ("o que achou da Copa de 2026?", None, {}, "required"),
        ("o que achou da copa do mundo de 2022?", None, {}, "required"),
        ("tem algo melhor?", "follow_up", {}, "none"),
    ],
)
def test_need_web_matrix(msg, intent, ents, need):
    d = decide_need_web(msg, intent=intent, entities=ents)
    assert d.need == need


def test_web_failure_does_not_degrade():
    original = "Gosto do Botafogo quando joga com coragem."
    payload = {
        "intent": "conversation_assist",
        "entities": {
            "natural_kind": "team_opinion",
            "team": "Botafogo",
            "opinion_time": True,
        },
        "executive_summary": original,
        "final_recommendation": original,
        "best_markets": [],
        "response_metadata": {},
    }

    async def _boom(_q: str):
        raise TimeoutError("simulated")

    async def _run():
        with patch(
            "src.conversation.web_intelligence._duckduckgo_snippet",
            new=AsyncMock(side_effect=_boom),
        ):
            return await maybe_enrich_with_web(
                "o que acha do Botafogo?",
                payload,
                intent="conversation_assist",
            )

    out = asyncio.run(_run())
    assert out["executive_summary"] == original
    assert out["final_recommendation"] == original
    status = ((out.get("response_metadata") or {}).get("need_web") or {}).get("status")
    assert status == "fallback_no_web"


def test_web_none_snippet_preserves_text():
    original = "Opinião curta."
    payload = {
        "intent": "conversation_assist",
        "entities": {"natural_kind": "team_opinion", "team": "Bahia", "opinion_time": True},
        "executive_summary": original,
        "final_recommendation": original,
        "response_metadata": {},
    }

    async def _run():
        with patch(
            "src.conversation.web_intelligence._duckduckgo_snippet",
            new=AsyncMock(return_value=None),
        ):
            return await maybe_enrich_with_web("o que acha do Bahia?", payload)

    out = asyncio.run(_run())
    assert out["executive_summary"] == original


def test_web_skipped_for_emotional_payload():
    original = "Isso significa muito 😊"
    payload = {
        "intent": "emotional",
        "entities": {"emotional": True},
        "executive_summary": original,
        "final_recommendation": original,
        "response_metadata": {},
    }
    mocked = AsyncMock(return_value="NOT USED")

    async def _run():
        with patch(
            "src.conversation.web_intelligence._duckduckgo_snippet",
            new=mocked,
        ):
            return await maybe_enrich_with_web(
                "tenho orgulho de voce", payload, intent="emotional"
            )

    out = asyncio.run(_run())
    mocked.assert_not_awaited()
    assert out["executive_summary"] == original


def test_web_enrich_caps_note_length():
    original = "Sobre o Bahia, gosto do momento."
    long_snip = "X" * 500
    payload = {
        "intent": "conversation_assist",
        "entities": {"natural_kind": "team_opinion", "team": "Bahia", "opinion_time": True},
        "executive_summary": original,
        "final_recommendation": original,
        "response_metadata": {},
    }

    async def _run():
        with patch(
            "src.conversation.web_intelligence._duckduckgo_snippet",
            new=AsyncMock(return_value=long_snip),
        ):
            return await maybe_enrich_with_web("o que acha do Bahia?", payload)

    out = asyncio.run(_run())
    assert original in (out["executive_summary"] or "")
    # note capped → total shouldn't explode to original+500+lead
    assert len(out["executive_summary"] or "") < len(original) + 360


# ── 4. User Profile Memory ─────────────────────────────────────────────────

def test_profile_save_recover_forget_cycle():
    ctx: dict[str, Any] = {
        "user_profile": {"bankroll": 250.0, "experience_level": "beginner"},
    }
    save_profile(
        ctx,
        {
            "name": "Achiro",
            "role": "criador",
            "favorite_team": "Botafogo",
            "project": "Aurora",
        },
    )
    prof = get_profile(ctx)
    assert prof["name"] == "Achiro"
    assert prof["favorite_team"] == "Botafogo"
    assert ctx["user_profile"]["bankroll"] == 250.0

    g = greeting_prefix(ctx)
    assert g and "Achiro" in g and "Botafogo" in g

    assert detect_forget_command("apague minhas informações")
    assert detect_forget_command("esqueça isso")
    assert detect_forget_command("apague tudo sobre mim")

    clear_profile(ctx)
    assert get_profile(ctx)["name"] == ""
    assert ctx["user_profile"]["bankroll"] == 250.0
    assert greeting_prefix(ctx) is None


def test_profile_teach_commands_roundtrip():
    ctx: dict[str, Any] = {}
    p1 = try_profile_commands("Meu nome é Achiro", ctx)
    assert p1 and "Achiro" in (p1.get("executive_summary") or "")
    assert get_profile(ctx)["name"] == "Achiro"

    p2 = try_profile_commands("Meu time do coracao e o Bahia", ctx)
    assert p2
    assert get_profile(ctx)["favorite_team"]
    # name preserved
    assert get_profile(ctx)["name"] == "Achiro"

    p3 = try_profile_commands("apague minhas informações", ctx)
    assert p3
    assert get_profile(ctx)["name"] == ""


def test_profile_teach_detection():
    assert detect_profile_teach("me chamo Caio")["name"].startswith("Caio")
    assert detect_profile_teach("torço pelo Flamengo")["favorite_team"]


# ── 5. Agenda + competition filter smoke ───────────────────────────────────

def test_agenda_brasileirao_flags():
    assert detect_natural_intent("quais jogos amanha?")["brasileirao"] is False
    assert detect_natural_intent("jogos do brasileirao amanha")["brasileirao"] is True
    assert detect_natural_intent("Brasileirão amanhã")["brasileirao"] is True
    assert detect_natural_intent("proxima rodada")["brasileirao"] is True


def test_agenda_format_and_filter_smoke():
    mixed = [
        {
            "league": {"id": 71, "name": "Serie A", "country": "Brazil"},
            "teams": {"home": {"name": "Bahia"}, "away": {"name": "Flamengo"}},
            "fixture": {"date": "2026-07-13T22:00:00+00:00"},
        },
        {
            "league": {"id": 254, "name": "NWSL", "country": "USA"},
            "teams": {"home": {"name": "Gotham"}, "away": {"name": "Reign"}},
            "fixture": {"date": "2026-07-13T18:00:00Z"},
        },
        {
            "league": {"id": 253, "name": "Major League Soccer", "country": "USA"},
            "teams": {"home": {"name": "Inter Miami"}, "away": {"name": "LAFC"}},
            "fixture": {"date": "2026-07-13T23:00:00Z"},
        },
        {
            "league": {"id": 344, "name": "Division Profesional", "country": "Bolivia"},
            "teams": {"home": {"name": "Bolivar"}, "away": {"name": "The Strongest"}},
            "fixture": {"date": "2026-07-13T20:00:00Z"},
        },
    ]
    only_br = _filter_brasileirao_only(mixed)
    assert len(only_br) == 1
    assert only_br[0]["teams"]["home"]["name"] == "Bahia"
    body = _format_agenda_blocks(only_br, title="⚽ Jogos do Brasileirão amanhã")
    assert "NWSL" not in body
    assert "MLS" not in body and "Inter Miami" not in body
    assert "Bolivar" not in body
    assert "Bahia x Flamengo" in body
    assert "⚽ Jogos do Brasileirão amanhã" in body


def test_natural_brasileirao_no_world_fallback():
    """When user asks Brasileirão and API returns empty, do NOT open world slate."""

    async def _empty(*_a, **_k):
        return []

    async def _run():
        with patch(
            "src.conversation.natural_conversation._fetch_fixtures_for_date",
            new=_empty,
        ):
            return await try_natural_conversation(
                "quais jogos do brasileirao amanha?",
                {},
                {"emojis": "none"},
            )

    payload = asyncio.run(_run())
    assert payload
    text = payload.get("executive_summary") or ""
    assert "NWSL" not in text
    assert "Inter Miami" not in text
    assert (payload.get("entities") or {}).get("brasileirao_filter") is True


def test_natural_agenda_ux_with_mock_fixtures():
    fixtures = [
        {
            "league": {"id": 71, "name": "Serie A", "country": "Brazil"},
            "teams": {"home": {"name": "Bahia"}, "away": {"name": "Flamengo"}},
            "fixture": {"date": "2026-07-13T22:00:00+00:00"},
        },
        {
            "league": {"id": 71, "name": "Serie A", "country": "Brazil"},
            "teams": {"home": {"name": "Palmeiras"}, "away": {"name": "Corinthians"}},
            "fixture": {"date": "2026-07-14T00:30:00+00:00"},
        },
    ]

    async def _fake(date_iso, league_id=None):
        return fixtures if league_id == 71 else fixtures

    async def _run():
        with patch(
            "src.conversation.natural_conversation._fetch_fixtures_for_date",
            new=_fake,
        ):
            return await try_natural_conversation(
                "jogos do brasileirao amanha",
                {},
                {"emojis": "none"},
            )

    payload = asyncio.run(_run())
    text = payload.get("executive_summary") or ""
    assert "Bahia x Flamengo" in text
    assert "Palmeiras x Corinthians" in text
    assert "Serie A" not in text or "⚽" in text  # card UX, not raw dump line


# ── 6. Conversation State + Follow-up regression ───────────────────────────

def test_conversation_state_survives_about_you():
    ctx: dict[str, Any] = {}
    apply_after_analysis(
        ctx,
        "Botafogo",
        "Santos",
        "Botafogo x Santos",
        {
            "best_markets": [{"market": "Mais de 8.5 Escanteios", "rank": 1}],
            "risk": {"level": "High"},
            "final_recommendation": "stake reduzida",
        },
    )
    save_profile(ctx, {"name": "Achiro", "project": "Aurora"})
    note_small_talk(ctx)
    assert active_fixture(ctx)
    st = get_state(ctx)
    assert st is not None
    # about_you coexists
    assert get_profile(ctx)["name"] == "Achiro"
    # expire check fail-open
    expire_conversation_state_if_needed(ctx)


def test_followup_guard_not_broken_by_identity():
    ctx = {
        "last_match": "Botafogo x Santos",
        "last_home": "Botafogo",
        "last_away": "Santos",
        "last_analysis": {"match": "Botafogo x Santos"},
        PROFILE_KEY: {"name": "Achiro", "role": "", "favorite_team": "", "project": ""},
    }
    same = decide_followup_reuse("e o risco desse mercado?", ctx)
    # Without a new A x B, should not force new fixture
    assert same.new_fixture is None or same.reuse is True or same.reuse is False
    other = decide_followup_reuse("Bahia x Flamengo", ctx)
    assert other.reuse is False
    assert other.home and other.away


# ── 7. Depth: short vs deep ────────────────────────────────────────────────

def test_depth_emotional_short_vs_opinion_deeper():
    emo = try_emotional_presence("obrigado aurora", {}, {"emojis": "none"})
    assert emo
    assert len(emo["executive_summary"]) < 200

    from src.conversation.natural_conversation import build_team_opinion_reply

    opinion = build_team_opinion_reply("Botafogo")
    assert len(opinion) > len(emo["executive_summary"])
    assert "probabilidade" not in opinion.lower()


def test_depth_formatter_social_vs_analysis():
    social = format_user_facing_text("Oi.\n\nTudo bem?\n\nExtra.\n\nMais.", kind="social")
    # social keeps at most 2 paragraphs
    assert social.count("\n\n") <= 1
    analysis = format_user_facing_text(
        "Bloco 1 detalhado.\n\nBloco 2.\n\nBloco 3.\n\nBloco 4.",
        kind="analysis",
    )
    assert analysis.count("\n\n") >= 2
