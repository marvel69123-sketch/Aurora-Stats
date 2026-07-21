"""AURORA-PATCH-001 — Entity safety layer tests."""

from __future__ import annotations

from src.conversation.context_recovery import fuzzy_resolve_team, recover_context
from src.conversation.entity_safety import (
    extract_comparison_pair,
    filter_recovery_teams,
    judge_entity_overlap,
    ownership_lock_permitted,
    score_alias_hit,
)
from src.conversation.judge_rubric import score_turn


def test_r1_chance_never_chapecoense():
    assert fuzzy_resolve_team("chance") is None
    assert fuzzy_resolve_team("mata") is None
    assert fuzzy_resolve_team("gols") is None
    assert fuzzy_resolve_team("tudo") is None
    assert fuzzy_resolve_team("both") is None


def test_r1_exact_slang_preserved():
    assert fuzzy_resolve_team("chape") == "Chapecoense"
    assert fuzzy_resolve_team("bota") == "Botafogo"
    assert fuzzy_resolve_team("santus") == "Santos"
    assert fuzzy_resolve_team("galo") == "Atletico Mineiro"


def test_r1_recover_chance_atletico_bahia():
    msg = "quem tem mais chance amanhã atlético ou bahia?"
    r = recover_context(msg)
    assert "Chapecoense" not in r.teams
    assert any("bahia" in t.lower() for t in r.teams)
    assert any("atletico" in t.lower() or "mineiro" in t.lower() for t in r.teams)
    assert not any(n.startswith("fuzzy:chance->") for n in r.notes)


def test_r2_atletico_confidence_br_context():
    msg = "atlético ou bahia amanhã"
    c_m = score_alias_hit("atletico", "Atletico Mineiro", msg, exact=True)
    c_mad = score_alias_hit("atletico", "Atletico Madrid", msg, exact=True)
    assert c_m >= 0.91
    assert c_mad <= 0.55


def test_r2_filter_attaches_confidence():
    msg = "atlético ou bahia"
    v = filter_recovery_teams(
        msg, ["Atletico Mineiro", "Bahia"], raw_notes=[]
    )
    assert any(s.canon == "Bahia" and s.confidence >= 0.55 for s in v.teams)
    assert any("Mineiro" in s.canon and s.confidence >= 0.55 for s in v.teams)


def test_r5_comparison_operators():
    assert extract_comparison_pair("Atlético ou Bahia") is not None
    left, right = extract_comparison_pair("Atlético ou Bahia")
    assert "atletico" in left.lower().replace("á", "a") or "Atlético" in left or "atletico" in left.lower()
    assert "Bahia" in right or "bahia" in right.lower()
    assert extract_comparison_pair("Flamengo x Palmeiras") is not None
    assert extract_comparison_pair("PSG contra Bayern") is not None


def test_r5_recover_ou_pair():
    r = recover_context("Atlético ou Bahia")
    names = " ".join(r.teams).lower()
    assert "bahia" in names
    assert "atletico" in names or "mineiro" in names


def test_r3_ownership_blocked_on_comparison():
    assert ownership_lock_permitted("e o xg?", {"last_team": "Bahia"}) is True
    assert (
        ownership_lock_permitted(
            "quem tem mais chance amanhã atlético ou bahia?", {}
        )
        is False
    )


def test_r4_judge_rejects_ungrounded_entity():
    payload = {
        "intent": "follow_up",
        "executive_summary": "Continuando sobre contexto do Chapecoense. " * 3,
        "entities": {"team": "Chapecoense", "followup_context_found": True},
    }
    scores = score_turn(
        "quem tem mais chance amanhã atlético ou bahia?",
        payload,
    )
    assert scores["overall_score"] <= 4.5
    assert scores["band"] in {"Ruim", "Aceitável"}
    ov = judge_entity_overlap(
        "quem tem mais chance amanhã atlético ou bahia?",
        payload,
    )
    assert ov["overlap_ok"] is False
