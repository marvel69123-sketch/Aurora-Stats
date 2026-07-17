"""Aurora v4.5.2 — product polish: personality, natural intents, empty-card guards."""

from __future__ import annotations

import asyncio
import re

from src.conversation.human_presence import (
    build_presence_payload,
    build_social_presence_reply,
    is_social_presence_turn,
)
from src.conversation.natural_conversation import (
    build_capabilities_reply,
    build_team_opinion_reply,
    detect_natural_intent,
    try_natural_conversation,
)
from src.conversation.presence_humanization import apply_presence_humanization
from src.conversation.conversational_understanding import understand
from src.conversation.reflection_credibility import apply_credibility_to_payload, run_reflection


def test_personality_emoji_high_on_wellbeing():
    prefs = {"emojis": "high", "enthusiasm": "high"}
    base = "Tudo certo por aqui, obrigada por perguntar. E você?"
    # high always adds emoji
    outs = {apply_presence_humanization(base, prefs, family_hint="wellbeing") for _ in range(8)}
    assert any(re.search(r"[\U0001F300-\U0001FAFF]", o) for o in outs)
    assert any("!" in o or "feliz" in o.lower() for o in outs)


def test_personality_emoji_none_stays_clean():
    prefs = {"emojis": "none", "enthusiasm": "low"}
    base = "Tudo certo por aqui, obrigada por perguntar."
    out = apply_presence_humanization(base, prefs, family_hint="wellbeing")
    assert not re.search(r"[\U0001F300-\U0001FAFF]", out)


def test_farewell_night_emoji_family():
    prefs = {"emojis": "high", "enthusiasm": "high"}
    out = apply_presence_humanization("Boa noite — quando quiser, a gente retoma.", prefs)
    assert "🌙" in out or "✨" in out or "😊" in out


def test_detect_calendar_intents():
    assert detect_natural_intent("hoje teve jogo?")["kind"] in {"had_games_today", "calendar_today"}
    assert detect_natural_intent("quais jogos amanha?")["kind"] == "calendar_tomorrow"
    assert detect_natural_intent("Quais jogos do Brasileirao amanha?")["kind"] == "calendar_tomorrow"
    assert detect_natural_intent("proxima rodada")["kind"] == "calendar_round"


def test_detect_team_opinion():
    d = detect_natural_intent("o que voce acha do Bahia?")
    assert d and d["kind"] == "team_opinion"
    assert d.get("team") == "Bahia"
    reply = build_team_opinion_reply("Bahia")
    assert "Bahia" in reply
    assert "Analisar" not in reply or "analiso" in reply.lower()


def test_detect_capabilities_consegue():
    d = detect_natural_intent("o que voce consegue fazer?")
    assert d and d["kind"] == "capabilities"
    reply = build_capabilities_reply()
    assert "Análises" in reply or "analis" in reply.lower()
    assert "Agenda" in reply or "agenda" in reply.lower()


def test_capabilities_payload_no_markets_and_social_cred():
    payload = {
        "intent": "capabilities",
        "entities": {"natural_conversation": True, "has_analysis": False},
        "best_markets": [],
        "executive_summary": build_capabilities_reply(),
        "final_recommendation": build_capabilities_reply(),
        "confidence": {"score": 0.0, "label": "insufficient", "explanation": "", "data_sources": []},
        "risk": {"level": "Unknown", "flags": [], "invalidation_conditions": []},
        "bankroll_recommendation": {
            "recommended_stake_pct": 0.0,
            "method": "q",
            "examples": {},
            "no_bet": True,
            "reasoning": "",
        },
        "positive_factors": [],
        "negative_factors": [],
        "historical_references": [],
        "knowledge_notes": ["x"],  # even with notes
        "response_metadata": {"has_analysis": False},
    }
    refl = run_reflection("o que voce consegue fazer?", {}, payload["executive_summary"])
    out = apply_credibility_to_payload(payload, refl, {})
    cred = (out.get("response_metadata") or {}).get("credibility") or {}
    assert cred.get("display_mode") == "SOCIAL"
    assert out.get("best_markets") == []


def test_hpl_plus_humanization_pipeline():
    ctx: dict = {}
    intent = understand("como voce esta?", ctx)
    assert is_social_presence_turn(intent.to_dict())
    reply = build_social_presence_reply("como voce esta?", intent.to_dict(), ctx)
    assert reply
    hum = apply_presence_humanization(
        reply,
        {"emojis": "high", "enthusiasm": "high"},
        family_hint="wellbeing",
    )
    payload = build_presence_payload(hum, {})
    assert payload["best_markets"] == []
    assert payload.get("intent") == "small_talk"


def test_natural_conversation_team_async():
    payload = asyncio.run(
        try_natural_conversation(
            "o que acha do Bahia?",
            {},
            {"emojis": "none", "enthusiasm": "medium"},
        )
    )
    assert payload
    assert payload["best_markets"] == []
    assert "Bahia" in (payload.get("executive_summary") or "")
    assert (payload.get("entities") or {}).get("natural_kind") == "team_opinion"


def test_long_mix_natural_and_social():
    script = [
        "oi",
        "como voce esta?",
        "o que voce gosta de fazer?",
        "o que voce consegue fazer?",
        "o que acha do Bahia?",
        "hoje teve jogo?",
        "quais jogos amanha?",
        "obrigado",
        "boa noite",
    ]
    kinds = []
    for msg in script:
        d = detect_natural_intent(msg)
        if d:
            kinds.append(d["kind"])
        else:
            cue = understand(msg, {})
            if cue.explicit_goal == "SOCIAL":
                kinds.append("social")
            else:
                kinds.append(cue.explicit_goal or "other")
    assert "capabilities" in kinds
    assert "team_opinion" in kinds
    assert "social" in kinds
    assert any(k.startswith("calendar") or k == "had_games_today" for k in kinds)
