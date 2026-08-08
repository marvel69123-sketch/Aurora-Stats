"""
Mission 016 Phase 3 — SHADOW MODE tests (Spec P2 / Appendix B / REGRA 23).

Proves:
  - Shadow isolated; production write OFF; Sole Writer OFF
  - Path A/B no-op when shadow flag OFF; observe-only when ON
  - Live ctx unchanged with shadow ON
  - Appendix B IO-S1…IO-S5 Pass (N≥30)
  - Critical pack: Flamengo→Liverpool→FU; Inter partial; soft-FU clean

Does NOT activate Sole Writer funnel / Phase 4.
"""

from __future__ import annotations

import copy
import os

from src.conversation.appendix_b_ingress_harness import (
    SUITE_NAME,
    run_appendix_b_harness,
)
from src.conversation.langgraph_state_adapter import (
    ingress_order_shadow_compare,
    maybe_shadow_compare,
)
from src.conversation.migration_flag_controller import (
    MigrationStage,
    assert_legal_flag_matrix,
    flag_snapshot,
    get_migration_stage,
    sts_sole_writer_enabled,
)
from src.conversation.minimal_commit_orchestrator import invoke_minimal_commit_orchestrator
from src.conversation.sport_topic_state import (
    SportTopicState,
    langgraph_state_enabled,
    langgraph_state_shadow_enabled,
)


def _clear_flags():
    for k in (
        "ENABLE_LANGGRAPH_STATE",
        "ENABLE_LANGGRAPH_STATE_SHADOW",
        "AURORA_MIGRATION_STAGE",
        "ENABLE_STS_SOLE_WRITER",
        "ENABLE_STS_WRITE_FUNNEL_BOUNDARY",
        "ENABLE_STS_WRITE_FUNNEL_ANALYZE",
        "ENABLE_STS_NOTE_SUBJECT_GUARDS",
        "CLAIM_SHADOW_AS_SOLE_WRITER",
    ):
        os.environ.pop(k, None)


def _flamengo_ctx() -> dict:
    return {
        "last_home": "Flamengo",
        "last_away": "Palmeiras",
        "last_match": "Flamengo x Palmeiras",
        "episode_id": "ep-flamengo",
        "last_intent": "fixture_compare",
        "csl": {
            "episode_id": "ep-flamengo",
            "teams": ["Flamengo", "Palmeiras"],
            "fixture": "Flamengo x Palmeiras",
            "topic": "comparison",
            "last_intent": "fixture_compare",
        },
        "sport_referent_frame": {
            "fixture_label": "Flamengo x Palmeiras",
            "home": "Flamengo",
            "away": "Palmeiras",
        },
    }


def _liverpool_ctx() -> dict:
    return {
        "last_home": "Liverpool",
        "last_away": "Chelsea",
        "last_match": "Liverpool x Chelsea",
        "episode_id": "ep-liverpool",
        "last_intent": "fixture_compare",
        "csl": {
            "episode_id": "ep-liverpool",
            "teams": ["Liverpool", "Chelsea"],
            "fixture": "Liverpool x Chelsea",
            "topic": "comparison",
            "last_intent": "fixture_compare",
        },
        "sport_referent_frame": {
            "fixture_label": "Liverpool x Chelsea",
            "home": "Liverpool",
            "away": "Chelsea",
        },
    }


# ---------------------------------------------------------------------------
# Defaults / writes OFF / Sole Writer OFF
# ---------------------------------------------------------------------------


def test_phase3_defaults_shadow_and_write_off():
    _clear_flags()
    assert langgraph_state_enabled() is False
    assert langgraph_state_shadow_enabled() is False
    assert sts_sole_writer_enabled() is False
    assert get_migration_stage() == MigrationStage.S0_OFF
    assert assert_legal_flag_matrix() == []
    snap = flag_snapshot()
    assert snap["production_write_active"] is False
    assert snap["ENABLE_STS_SOLE_WRITER"] is False


def test_path_a_and_b_noop_when_shadow_off():
    _clear_flags()
    ctx = _flamengo_ctx()
    before = copy.deepcopy(ctx)
    assert maybe_shadow_compare("Liverpool x Chelsea", ctx) is None
    assert ingress_order_shadow_compare("Liverpool x Chelsea", ctx) is None
    assert ctx == before


def test_c17_still_noop_without_force():
    _clear_flags()
    sts = SportTopicState.from_dict(
        {"fixture": "Flamengo x Palmeiras", "teams": ["Flamengo", "Palmeiras"]}
    )
    out = invoke_minimal_commit_orchestrator("Liverpool x Chelsea", sts)
    assert out.skipped_reason == "flags_off_orchestrator_noop"
    assert langgraph_state_enabled() is False


# ---------------------------------------------------------------------------
# REGRA 23 — shadow ON does not mutate production ctx
# ---------------------------------------------------------------------------


def test_path_a_shadow_on_ctx_unchanged_write_off():
    _clear_flags()
    os.environ["ENABLE_LANGGRAPH_STATE_SHADOW"] = "1"
    try:
        assert langgraph_state_enabled() is False
        ctx = _flamengo_ctx()
        before = copy.deepcopy(ctx)
        r = maybe_shadow_compare("Liverpool x Chelsea", ctx)
        assert r is not None
        assert r["shadow_only"] is True
        assert r["production_write_enabled"] is False
        assert r["new"]["fixture"] == "Liverpool x Chelsea"
        assert ctx == before
        assert get_migration_stage() == MigrationStage.S1_SHADOW
    finally:
        _clear_flags()


def test_path_b_shadow_on_ctx_unchanged_write_off():
    _clear_flags()
    os.environ["ENABLE_LANGGRAPH_STATE_SHADOW"] = "1"
    try:
        ctx = _flamengo_ctx()
        before = copy.deepcopy(ctx)
        r = ingress_order_shadow_compare(
            "Liverpool x Chelsea",
            ctx,
            sll_clubs=["Liverpool", "Chelsea"],
        )
        assert r is not None
        assert r["shadow_path"] == "B_ingress_order"
        assert r["appendix_b_ready"] is True
        assert r["production_write_enabled"] is False
        assert "Liverpool" in (r["new"]["teams"] or [])
        assert "subject_teams_mismatch" not in (r["divergence_classes"] or [])
        assert ctx == before
    finally:
        _clear_flags()


def test_critical_sticky_path_b_loci():
    """Flamengo→Liverpool (lagging OLD)→soft FU clean — Path B."""
    _clear_flags()
    try:
        r1 = ingress_order_shadow_compare(
            "Flamengo x Palmeiras",
            {},
            sll_clubs=["Flamengo", "Palmeiras"],
            force=True,
        )
        assert r1 is not None
        assert r1["new"]["fixture"] == "Flamengo x Palmeiras"

        r2 = ingress_order_shadow_compare(
            "Liverpool x Chelsea",
            _flamengo_ctx(),
            sll_clubs=["Liverpool", "Chelsea"],
            force=True,
        )
        assert r2 is not None
        assert r2["old"]["fixture"] == "Flamengo x Palmeiras"
        assert r2["new"]["fixture"] == "Liverpool x Chelsea"
        assert r2["contamination_locus"] == "before_langgraph"
        assert "subject_teams_mismatch" not in (r2["divergence_classes"] or [])

        r3 = ingress_order_shadow_compare(
            "Quem está melhor?",
            _liverpool_ctx(),
            force=True,
        )
        assert r3 is not None
        assert r3["new"]["fixture"] == "Liverpool x Chelsea"
        assert "Flamengo" not in (r3["new"]["teams"] or [])
        assert "soft_fu_on_contaminated_prior" not in (r3["divergence_classes"] or [])
    finally:
        _clear_flags()


def test_inter_partial_path_b():
    _clear_flags()
    try:
        r = ingress_order_shadow_compare(
            "Inter joga hoje?",
            _flamengo_ctx(),
            sll_clubs=["Inter"],
            expected_teams=["Inter"],
            force=True,
        )
        assert r is not None
        assert r["new"]["turn_route"] == "apply_boundary"
        assert any("Inter" in str(t) for t in (r["new"]["teams"] or []))
        assert "Flamengo" not in (r["new"]["teams"] or [])
        assert "subject_teams_mismatch" not in (r["divergence_classes"] or [])
    finally:
        _clear_flags()


# ---------------------------------------------------------------------------
# Appendix B harness — IO-S1…IO-S5
# ---------------------------------------------------------------------------


def test_appendix_b_harness_pass():
    _clear_flags()
    # force=True: tests enable Path B in-process; env shadow remains default OFF
    out = run_appendix_b_harness(force=True)
    grade = out["grade"]
    assert out["harness"] == SUITE_NAME
    assert grade["n"] >= 30
    assert grade["overall_pass"] is True
    for cid in ("IO-S1", "IO-S2", "IO-S3", "IO-S4", "IO-S5"):
        assert grade["criteria"][cid]["pass"] is True, grade["criteria"][cid]
    assert grade["production_write_enabled"] is False
    assert grade["locus1_monitoring_only"] is True
    assert langgraph_state_enabled() is False
    assert sts_sole_writer_enabled() is False


def test_appendix_b_harness_with_shadow_env_on_still_no_write():
    _clear_flags()
    os.environ["ENABLE_LANGGRAPH_STATE_SHADOW"] = "1"
    try:
        out = run_appendix_b_harness(force=False)
        assert out["grade"]["overall_pass"] is True
        assert langgraph_state_enabled() is False
        assert out["flags"]["ENABLE_LANGGRAPH_STATE"] is False
    finally:
        _clear_flags()
