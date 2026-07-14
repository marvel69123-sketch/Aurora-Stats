"""Phase 6 — Personality & Communication Layer tests."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.communication.personality_layer import (
    AURORA_TAGLINE,
    cleanup_text,
    humanize_text,
    official_greeting_summary,
    polish_payload,
)


def test_cleanup_removes_context_preamble():
    raw = (
        "Estou utilizando o contexto anterior:\n"
        "**Atlanta x Colegiales**.\n\n"
        "Com base naquela análise:\n\n"
        "Ainda não vejo valor claro."
    )
    cleaned = cleanup_text(raw)
    assert "Estou utilizando" not in cleaned
    assert "Com base naquela" not in cleaned
    assert "valor claro" in cleaned


def test_humanize_stake():
    assert "ficaria de fora" in humanize_text("Nenhuma stake recomendada.").lower()


def test_humanize_slice():
    out = humanize_text("Sem slice dedicado de escanteios — mantendo o contexto.")
    assert "slice" not in out.lower()
    assert "valor claro" in out.lower() or "escanteios" in out.lower()


def test_polish_followup_payload():
    payload = {
        "intent": "follow_up",
        "executive_summary": (
            "Estou utilizando o contexto anterior:\n**Botafogo x Santos**.\n\n"
            "Com base naquela análise:\n\n"
            "Ainda não vejo um valor claro nesse mercado.\n"
            "Mas a pressão pode aumentar."
        ),
        "final_recommendation": "Contexto de Botafogo x Santos reutilizado — sem ranking forte em gols.",
        "knowledge_notes": [
            "Follow-up resolveu via conversation_context — sem nova busca.",
            "Nota útil sobre ritmo ofensivo.",
        ],
        "confidence": {
            "score": 6.0,
            "label": "adequate",
            "explanation": "Reutilizado do contexto conversacional.",
            "data_sources": [],
        },
        "bankroll_recommendation": {
            "recommended_stake_pct": 0,
            "method": "quarter-Kelly",
            "examples": {},
            "no_bet": True,
            "reasoning": "Nenhuma stake recomendada.",
        },
    }
    out = polish_payload(payload, message="e os gols?", intent="follow_up", ctx={})
    summary = out["executive_summary"]
    assert "Estou utilizando" not in summary
    assert "contexto anterior" not in summary.lower()
    assert "conversation_context" not in " ".join(out["knowledge_notes"])
    assert "Nota útil" in " ".join(out["knowledge_notes"])
    assert "contexto conversacional" not in (out["confidence"]["explanation"] or "").lower()
    # Short answers stay compact
    assert len([ln for ln in summary.splitlines() if ln.strip()]) <= 8


def test_greeting_official():
    g = official_greeting_summary()
    assert "Aurora" in g
    assert "xG" not in g
    assert "39" not in g
    assert "metodológ" not in g.lower()
    assert AURORA_TAGLINE.startswith("Aurora")


def test_playful_tone_bagunca():
    payload = {
        "intent": "follow_up",
        "executive_summary": "A leitura anterior ainda faz sentido com cautela.",
        "final_recommendation": "Cautela.",
        "knowledge_notes": [],
        "confidence": {"score": 5, "label": "adequate", "explanation": "ok", "data_sources": []},
        "bankroll_recommendation": {
            "recommended_stake_pct": 0, "method": "quarter-Kelly",
            "examples": {}, "no_bet": True, "reasoning": "",
        },
    }
    out = polish_payload(
        payload,
        message="esse jogo virou bagunça kkk",
        intent="follow_up",
        ctx={},
    )
    assert "imprevisível" in out["executive_summary"].lower() or "cautela" in out["executive_summary"].lower()
