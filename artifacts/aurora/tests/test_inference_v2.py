"""Unit tests for Inference Layer V2 — no network."""
from __future__ import annotations

from src.core.inference_context import (
    InferenceContext,
    build_partial_analyze_data,
    calculate_confidence_penalty,
    calculate_data_completeness,
    scan_analyze_data,
)


def test_calculate_data_completeness_empty():
    assert calculate_data_completeness([], []) == 0.0


def test_calculate_data_completeness_ratio():
    assert calculate_data_completeness(["a", "b"], ["c"]) == round(2 / 3, 3)


def test_calculate_confidence_penalty_missing_fixture():
    p = calculate_confidence_penalty(["fixture", "xg"], [])
    assert p >= 3.0
    assert p <= 8.0


def test_inferred_reduces_penalty_vs_full_missing():
    full = calculate_confidence_penalty(["fixture"], [])
    inferred = calculate_confidence_penalty([], ["fixture"])
    assert inferred < full


def test_inference_context_apply_to_score():
    ctx = InferenceContext()
    ctx.mark_missing("fixture", "not found")
    ctx.mark_missing("xg")
    ctx.finalize()
    adj = ctx.apply_to_score(7.0)
    assert 0.0 <= adj < 7.0


def test_build_partial_analyze_data_has_inference():
    data = build_partial_analyze_data(
        "Team A", "Team B", reason="No fixture found"
    )
    assert data["_partial"] is True
    assert data["fixture"]["id"] == 0
    assert data["teams"]["home"]["name"] == "Team A"
    exp = data["_inference"]["explainability"]
    assert "dados_encontrados" in exp
    assert "dados_faltantes" in exp
    assert "inferencias_realizadas" in exp


def test_scan_analyze_data_marks_xg_missing():
    data = build_partial_analyze_data("A", "B", reason="x")
    ctx = scan_analyze_data(data)
    assert "xg" in ctx.missing_signals or "xg" in ctx.inferred_signals
    assert ctx.data_completeness < 1.0


def test_knowledge_notes_pt_explainability():
    ctx = InferenceContext()
    ctx.mark_available("teams")
    ctx.mark_missing("xg", "sem xG")
    ctx.mark_inferred("standings", "default GPG")
    notes = ctx.knowledge_notes_pt()
    assert any("encontrados" in n.lower() for n in notes)
    assert any("faltantes" in n.lower() for n in notes)
    assert any("infer" in n.lower() for n in notes)
