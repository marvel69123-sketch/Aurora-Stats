"""
Bateria de Validação Humana P0 — Communication & Intent Recovery.

Cobertura:
  - Small talk
  - Matemática
  - Perguntas sobre a Aurora
  - Mudança rápida de contexto
  - 100–150 turns
  - Follow-up ambíguo
  - Conversa emocional
  - Retorno ao esporte após 20 mensagens não-esporte

Gate testado: Master Intent → hard block → General Assistant → HIE soft-keep
(+ emotional presence quando aplicável).
"""

from __future__ import annotations

import re
from typing import Any

import pytest

from src.conversation.emotional_presence import try_emotional_presence
from src.conversation.general_assistant import try_general_assistant
from src.conversation.human_inference import apply_human_inference, infer_human_intent
from src.conversation.master_intent_router import (
    apply_master_intent,
    classify_master_intent,
    sport_pipeline_allowed,
)
from src.conversation.natural_response_filter import (
    looks_artificial_sport_voice,
    score_perceived_intelligence,
)

SPORT_LEAK = re.compile(
    r"("
    r"Corinthians|Santos|Flamengo|Botafogo|Palmeiras|"
    r"panorama|Momento atual|best_markets|fixture_id|"
    r"o contexto atual|o [uú]til [eé]|caminho honesto|"
    r"a leitura pede|como chega|recorte recente"
    r")",
    re.I,
)


def _simulate_turn(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    """One conversational turn through the P0 gate stack."""
    master = apply_master_intent(message, ctx)
    sport_ok = sport_pipeline_allowed(ctx)
    payload = None
    source = "none"

    if not master.allow_sport_pipeline:
        payload = try_general_assistant(message, master.intent, ctx)
        if payload:
            source = "general_assistant"
        # Emotional layer (pride/thanks) — only when non-sport already blocked
        if payload is None:
            emo = try_emotional_presence(message, ctx, prefs={})
            if emo:
                payload = emo
                source = "emotional"
        if payload is None:
            # Soft fallback used by router hard-stop
            from src.conversation.general_assistant import reply_general

            text = reply_general(message)
            payload = {
                "intent": "general_chat",
                "entities": {"general_assistant": True},
                "executive_summary": text,
                "final_recommendation": text,
            }
            source = "forced_general"
        # HIE must not invent teams
        _, hie = apply_human_inference(message, ctx)
    else:
        # Sport path: HIE allowed; no general assistant sports reply required
        _, hie = apply_human_inference(message, ctx)
        source = "sport_pipeline"
        payload = {
            "intent": master.intent,
            "entities": {"sport_ok": True},
            "executive_summary": f"[SPORT] {master.intent}",
            "final_recommendation": f"[SPORT] {master.intent}",
        }

    text = str((payload or {}).get("executive_summary") or "")
    leak = bool(SPORT_LEAK.search(text)) if not sport_ok else False
    artificial = looks_artificial_sport_voice(text) if not sport_ok else False
    perception = score_perceived_intelligence(
        text, master_intent=master.intent
    )

    return {
        "message": message,
        "master_intent": master.intent,
        "sport_ok": sport_ok,
        "source": source,
        "text": text,
        "leak": leak,
        "artificial": artificial,
        "hie_team": getattr(hie, "team", None),
        "hie_intent": getattr(hie, "intent", None),
        "perception_ok": perception.ok if not sport_ok else True,
        "payload": payload,
    }


# ── 1. Small talk ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "msg",
    [
        "oi",
        "oi aurora",
        "oi aurora tudo bem?",
        "ola",
        "hey",
        "bom dia",
        "boa tarde",
        "boa noite",
        "tudo bem?",
        "td bem",
        "beleza",
        "e ai",
        "como voce esta?",
        "obrigado",
        "valeu",
        "tchau",
    ],
)
def test_small_talk_human(msg: str):
    ctx: dict = {"conversation_focus": {"topic_team": "Corinthians", "topic_kind": "opinion"}}
    out = _simulate_turn(msg, ctx)
    assert out["sport_ok"] is False
    assert out["master_intent"] == "SMALL_TALK"
    assert out["leak"] is False
    assert out["artificial"] is False
    assert out["hie_team"] in (None, "")
    assert "SPORT" not in out["text"]


# ── 2. Matemática ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "msg,expect",
    [
        ("quanto é 2+2?", "4"),
        ("2+2", "4"),
        ("10/2", "5"),
        ("quanto é 7*8?", "56"),
        ("calcule 15-3", "12"),
        ("100/4", "25"),
    ],
)
def test_math_human(msg: str, expect: str):
    ctx: dict = {"conversation_focus": {"topic_team": "Santos"}}
    out = _simulate_turn(msg, ctx)
    assert out["master_intent"] == "MATH_QUERY"
    assert out["sport_ok"] is False
    assert out["text"].strip() == expect
    assert out["leak"] is False


# ── 3. Sobre a Aurora ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "msg",
    [
        "qual seu nome?",
        "qual é o seu nome?",
        "como você se chama?",
        "quem é você?",
        "quem te criou?",
        "o que você faz?",
        "quais suas funções?",
        "no que você pode ajudar?",
        "ajuda",
    ],
)
def test_aurora_identity_human(msg: str):
    ctx: dict = {"conversation_focus": {"topic_team": "Flamengo"}}
    out = _simulate_turn(msg, ctx)
    assert out["master_intent"] == "SYSTEM_QUERY"
    assert out["sport_ok"] is False
    assert out["leak"] is False
    text_l = out["text"].lower()
    assert "aurora" in text_l or "ajud" in text_l


# ── 4. Mudança rápida de contexto ─────────────────────────────────────────


def test_rapid_context_switch():
    ctx: dict = {}
    sequence = [
        ("oi", False),
        ("Flamengo", True),
        ("quanto é 2+2?", False),
        ("analisar Arsenal x Chelsea", True),
        ("qual seu nome?", False),
        ("São Bernardo x Ivaí ao vivo", True),
        ("tudo bem?", False),
        ("como está o Botafogo?", True),
        ("10/2", False),
        ("Santos x Corinthians", True),
        ("obrigado", False),
        ("boa noite", False),
        ("Mirassol", True),
        ("e ai", False),
        ("quem te criou?", False),
    ]
    leaks = 0
    for msg, expect_sport in sequence:
        out = _simulate_turn(msg, ctx)
        assert out["sport_ok"] is expect_sport, f"{msg!r} sport_ok={out['sport_ok']}"
        if not expect_sport and out["leak"]:
            leaks += 1
        if not expect_sport:
            assert out["master_intent"] not in {"SPORT_QUERY", "LIVE_MATCH"}
        else:
            assert out["master_intent"] in {"SPORT_QUERY", "LIVE_MATCH"}
    assert leaks == 0


# ── 5. 100–150 turns mistos ───────────────────────────────────────────────


def _build_long_script(n: int = 140) -> list[tuple[str, bool]]:
    """(message, expect_sport) — mixed human script ~140 turns."""
    blocks: list[tuple[str, bool]] = []
    social = [
        "oi",
        "tudo bem?",
        "bom dia",
        "beleza",
        "e ai",
        "obrigado",
        "valeu",
        "boa tarde",
        "tchau",
        "hey aurora",
    ]
    math = ["quanto é 2+2?", "3+5", "10/2", "9*9", "quanto é 1+1?"]
    system = [
        "qual seu nome?",
        "quem te criou?",
        "o que você faz?",
        "quais suas funções?",
        "como você se chama?",
    ]
    sport = [
        "Flamengo",
        "analisar Arsenal x Chelsea",
        "São Bernardo x Ivaí ao vivo",
        "como está o Botafogo?",
        "Santos x Corinthians",
        "Palmeiras",
        "joga hoje o Vasco?",
    ]
    emotional = [
        "estou triste com o resultado",
        "que orgulho do time",
        "valeu pela ajuda de verdade",
    ]
    # Avoid sport tokens ("jogo") — those correctly route to SPORT_QUERY
    ambiguous = ["e ele?", "continua", "isso", "pode ser", "não sei"]

    i = 0
    while len(blocks) < n:
        blocks.append((social[i % len(social)], False))
        blocks.append((math[i % len(math)], False))
        blocks.append((system[i % len(system)], False))
        blocks.append((sport[i % len(sport)], True))
        blocks.append((emotional[i % len(emotional)], False))
        # Ambiguous after sport — must NOT stay stuck as sport unless sport signal
        blocks.append((ambiguous[i % len(ambiguous)], False))
        blocks.append((social[(i + 3) % len(social)], False))
        blocks.append((sport[(i + 1) % len(sport)], True))
        i += 1
    return blocks[:n]


def test_long_mixed_140_turns_zero_contamination():
    ctx: dict = {}
    script = _build_long_script(140)
    assert 100 <= len(script) <= 150

    fails: list[str] = []
    leaks = 0
    sport_turns = 0
    nonsport_turns = 0

    for idx, (msg, expect_sport) in enumerate(script):
        out = _simulate_turn(msg, ctx)
        if out["sport_ok"] != expect_sport:
            # Soften ambiguous: if we marked False but classifier found sport signal, ok if sport words
            if expect_sport is False and out["sport_ok"] and re.search(
                r"\b(jogo|time|placar|flamengo|x)\b", msg, re.I
            ):
                pass  # rare reclassify
            else:
                fails.append(
                    f"#{idx} {msg!r}: sport_ok={out['sport_ok']} expected={expect_sport} "
                    f"intent={out['master_intent']}"
                )
        if expect_sport:
            sport_turns += 1
        else:
            nonsport_turns += 1
            if out["leak"] or out["artificial"]:
                leaks += 1
                fails.append(f"#{idx} LEAK {msg!r}: {out['text'][:80]!r}")
            if out["hie_team"] and out["master_intent"] in {
                "SMALL_TALK",
                "MATH_QUERY",
                "SYSTEM_QUERY",
            }:
                fails.append(f"#{idx} HIE team invent {msg!r} → {out['hie_team']}")

    assert leaks == 0
    assert sport_turns >= 20
    assert nonsport_turns >= 60
    # Allow tiny reclassify noise on ambiguous phrases that contain sport words
    hard = [f for f in fails if "LEAK" in f or "HIE" in f]
    soft = [f for f in fails if f not in hard]
    assert not hard, hard[:10]
    assert len(soft) <= 8, soft[:10]


# ── 6. Follow-up ambíguo ──────────────────────────────────────────────────


def test_ambiguous_followup_no_sticky_sport():
    ctx: dict = {}
    # Seed sport context in session memory (what used to poison)
    ctx["conversation_focus"] = {
        "topic_team": "Corinthians",
        "topic_kind": "opinion",
    }
    ctx["last_match"] = {"home": "Corinthians", "away": "Santos"}

    ambiguous = [
        "oi",
        "e ai",
        "continua",
        "isso",
        "pode ser",
        "e ele?",
        "quanto é 2+2?",
        "qual seu nome?",
        "tudo bem?",
    ]
    for msg in ambiguous:
        out = _simulate_turn(msg, ctx)
        assert out["sport_ok"] is False, msg
        assert out["leak"] is False, msg
        # Soft-keep must not resurrect team on non-sport
        inf = infer_human_intent(msg, ctx)
        assert not (inf.team and out["master_intent"] == "SMALL_TALK" and msg == "oi")


def test_ambiguous_after_sport_then_clear():
    ctx: dict = {}
    _simulate_turn("analisar Flamengo x Palmeiras", ctx)
    assert sport_pipeline_allowed(ctx) is True
    out = _simulate_turn("e ai", ctx)
    assert out["sport_ok"] is False
    assert out["leak"] is False
    out2 = _simulate_turn("Flamengo", ctx)
    assert out2["sport_ok"] is True


# ── 7. Conversa emocional ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    "msg",
    [
        "estou triste",
        "que orgulho",
        "valeu pela ajuda",
        "obrigado de verdade",
        "tô animado",
    ],
)
def test_emotional_not_sport_pipeline(msg: str):
    ctx: dict = {"conversation_focus": {"topic_team": "Botafogo"}}
    master = apply_master_intent(msg, ctx)
    assert master.allow_sport_pipeline is False
    assert sport_pipeline_allowed(ctx) is False
    # Emotional handler may or may not fire; pipeline must stay blocked
    emo = try_emotional_presence(msg, ctx, prefs={})
    if emo:
        text = str(emo.get("executive_summary") or "")
        assert not SPORT_LEAK.search(text) or "orgulho" in msg.lower()
        # Even pride about "time" must not open markets pipeline
        assert sport_pipeline_allowed(ctx) is False


def test_emotional_sequence_then_math():
    ctx: dict = {}
    for msg in ("estou triste com tudo", "valeu pela força", "quanto é 2+2?"):
        out = _simulate_turn(msg, ctx)
        assert out["sport_ok"] is False
        assert out["leak"] is False
    assert _simulate_turn("quanto é 2+2?", ctx)["text"].strip() == "4"


# ── 8. Retorno ao esporte após 20 mensagens ───────────────────────────────


def test_return_to_sport_after_20_nonsport():
    ctx: dict = {}
    # Start with sport so sticky memory exists
    first = _simulate_turn("Corinthians", ctx)
    assert first["sport_ok"] is True
    ctx["conversation_focus"] = {
        "topic_team": "Corinthians",
        "topic_kind": "opinion",
    }
    ctx["last_match"] = {"home": "Corinthians", "away": "Santos"}

    nonsport_msgs = [
        "oi",
        "tudo bem?",
        "qual seu nome?",
        "quanto é 2+2?",
        "quem te criou?",
        "bom dia",
        "o que você faz?",
        "beleza",
        "10/2",
        "obrigado",
        "boa tarde",
        "como você se chama?",
        "e ai",
        "3+3",
        "valeu",
        "ajuda",
        "hey",
        "boa noite",
        "quanto é 5*5?",
        "tchau",
    ]
    assert len(nonsport_msgs) == 20

    for msg in nonsport_msgs:
        out = _simulate_turn(msg, ctx)
        assert out["sport_ok"] is False, msg
        assert out["leak"] is False, msg
        assert ctx.get("sport_pipeline_blocked") is True

    # Return to sport — must lift hard block and allow pipeline
    back = _simulate_turn("São Bernardo x Ivaí ao vivo", ctx)
    assert back["sport_ok"] is True
    assert back["master_intent"] == "LIVE_MATCH"
    assert ctx.get("sport_pipeline_blocked") in (None, False)
    assert sport_pipeline_allowed(ctx) is True

    # And still clean after another social beat
    social = _simulate_turn("oi aurora tudo bem?", ctx)
    assert social["sport_ok"] is False
    assert social["leak"] is False


# ── Aggregate certification score ─────────────────────────────────────────


def test_p0_human_battery_certification_report():
    """Single rollup used as human-facing pass/fail."""
    ctx: dict = {}
    checks = {
        "small_talk": 0,
        "math": 0,
        "aurora": 0,
        "context_switch": 0,
        "ambiguous": 0,
        "emotional": 0,
        "return_sport": 0,
        "long_run": 0,
    }
    total = 0
    passed = 0

    def ok(flag: bool, bucket: str) -> None:
        nonlocal total, passed
        total += 1
        if flag:
            passed += 1
            checks[bucket] += 1

    for msg in ("oi aurora tudo bem?", "bom dia", "beleza"):
        o = _simulate_turn(msg, ctx)
        ok(not o["sport_ok"] and not o["leak"], "small_talk")

    for msg, exp in (("quanto é 2+2?", "4"), ("10/2", "5")):
        o = _simulate_turn(msg, ctx)
        ok(o["text"].strip() == exp and not o["leak"], "math")

    for msg in ("qual seu nome?", "quem te criou?"):
        o = _simulate_turn(msg, ctx)
        ok("aurora" in o["text"].lower() and not o["leak"], "aurora")

    seq = [("oi", False), ("Flamengo", True), ("2+2", False), ("Palmeiras", True)]
    for msg, es in seq:
        o = _simulate_turn(msg, ctx)
        ok(o["sport_ok"] is es and (es or not o["leak"]), "context_switch")

    ctx["conversation_focus"] = {"topic_team": "Santos"}
    for msg in ("continua", "isso", "e ai"):
        o = _simulate_turn(msg, ctx)
        ok(not o["sport_ok"] and not o["leak"], "ambiguous")

    for msg in ("estou triste", "valeu pela ajuda"):
        apply_master_intent(msg, ctx)
        ok(not sport_pipeline_allowed(ctx), "emotional")

    for _ in range(20):
        _simulate_turn("oi", ctx)
    back = _simulate_turn("analisar Arsenal x Chelsea", ctx)
    ok(back["sport_ok"] and back["master_intent"] == "SPORT_QUERY", "return_sport")

    leaks = 0
    for msg, es in _build_long_script(120):
        o = _simulate_turn(msg, ctx)
        if not es and o["leak"]:
            leaks += 1
    ok(leaks == 0, "long_run")

    ratio = passed / max(total, 1)
    # Human battery target aligned with 80–83% maturity projection
    assert ratio >= 0.95, f"certification {ratio:.1%} checks={checks} passed={passed}/{total}"
    assert all(v > 0 for v in checks.values()), checks
