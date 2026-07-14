"""Phase 6.4 — Small talk + UX communication tests."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.communication.small_talk import detect_social_kind, try_small_talk
from src.communication.personality_layer import cleanup_text, polish_payload


def test_small_talk_hi():
    p = try_small_talk("oi", {})
    assert p is not None
    assert p["intent"] == "small_talk"
    assert "Aurora" in p["executive_summary"]
    assert "xG" not in p["executive_summary"]


def test_small_talk_bom_dia():
    assert detect_social_kind("bom dia") == "good_morning"
    p = try_small_talk("Bom dia!", {})
    assert p is not None
    assert "Bom dia" in p["executive_summary"]


def test_small_talk_how_are_you():
    assert detect_social_kind("como você está?") == "how_are_you"
    p = try_small_talk("como você está?", {})
    assert "pronta" in p["executive_summary"].lower() or "bem" in p["executive_summary"].lower()


def test_small_talk_likes_football():
    p = try_small_talk("você gosta de futebol?", {})
    assert p is not None
    assert "futebol" in p["executive_summary"].lower()


def test_small_talk_does_not_steal_match():
    assert try_small_talk("bom dia França x Espanha", {}) is None
    assert try_small_talk("analise flamengo x palmeiras", {}) is None


def test_cleanup_golden_rule():
    t = cleanup_text("[REGRA DE OURO] Nunca aposte sem EV.\nLeitura calma.")
    assert "REGRA DE OURO" not in t
    assert "Leitura calma" in t


def test_polish_analyze_compresses():
    long = (
        "França apresenta vantagem individual.\n\n"
        "A Espanha controla a posse.\n\n"
        "Poisson model indicates over 2.5 with methodology score 7.2 and 39 regras.\n\n"
        "Mais um parágrafo técnico denso sobre VE e Kelly sizing interno."
    )
    out = polish_payload(
        {
            "intent": "analyze_match",
            "match": "France x Spain",
            "executive_summary": long,
            "final_recommendation": "Aguardar escalações.",
            "best_markets": [
                {"market": "Over 2.5 gols", "probability": 55, "expected_value": 2},
                {"market": "BTTS", "probability": 52, "expected_value": 1},
            ],
            "knowledge_notes": ["[REGRA DE OURO] foo", "Nota útil"],
            "confidence": {"score": 6, "label": "adequate", "explanation": "ok", "data_sources": []},
            "bankroll_recommendation": {
                "recommended_stake_pct": 0, "method": "quarter-Kelly",
                "examples": {}, "no_bet": True, "reasoning": "",
            },
        },
        message="Analise França x Espanha",
        intent="analyze_match",
    )
    summary = out["executive_summary"]
    assert "39 regras" not in summary.lower()
    assert "Poisson" not in summary
    assert "Kelly" not in summary
    assert "vantagem individual" in summary or "cautelosa" in summary.lower() or "escanteios" in summary.lower()


def test_sanitize_hides_metrics_from_public_prose():
    dirty = (
        "Dados parciais para France x Spain. A Aurora continuou a análise "
        "com confiança reduzida em vez de abortar.\n\n"
        "Mais de 8.5 Escanteios — 72% prob · VE +26.5% · Risco Alto\n"
        "Menos de 2.5 Gols. λ=2.10.\n"
        "Best-mercado (over_85_corners) precisão 100.0%.\n"
        "Análise parcial: a partida não foi confirmada na API."
    )
    out = polish_payload(
        {
            "intent": "analyze_match",
            "match": "France x Spain",
            "executive_summary": dirty,
            "final_recommendation": (
                "Análise parcial para France x Spain: a partida não foi confirmada "
                "na API. Confiança 0.0/10, VE +26.5%."
            ),
            "best_markets": [{"market": "Mais de 8.5 Escanteios", "probability": 72, "expected_value": 26.5}],
            "positive_factors": [
                "Aprendizado Histórico (10.0/10): Best-mercado (over_85_corners) precisão 100.0%"
            ],
            "knowledge_notes": [],
            "confidence": {"score": 0, "label": "insufficient", "explanation": "api", "data_sources": []},
            "bankroll_recommendation": {
                "recommended_stake_pct": 0, "method": "quarter-Kelly",
                "examples": {}, "no_bet": True, "reasoning": "",
            },
        },
        message="analise frança x espanha",
        intent="analyze_match",
    )
    summary = out["executive_summary"]
    final = out["final_recommendation"]
    for leak in ("VE", "λ", "/10", "Best-mercado", "API", "abortar", "over_85"):
        assert leak not in summary, leak
        assert leak not in final, leak
    strengths = (out.get("response_metadata") or {}).get("public_strengths") or []
    assert strengths
    assert all("Best-mercado" not in s and "/10" not in s for s in strengths)
