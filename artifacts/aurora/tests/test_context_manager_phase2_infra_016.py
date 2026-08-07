"""
Mission 016 Phase 2 — Infra unit tests (Plan 014: T2/T9/T15/T16 + STS commit).

Flags remain OFF by default. force=True used only for isolated orchestrator /
shadow scaffolding. No production write activation.
"""

from __future__ import annotations

import os
import threading
import time

import pytest

from src.conversation.episode_transition import (
    APPENDIX_A_ROUTE_TABLE,
    EpisodeTransition,
    EpisodeTransitionDecision,
    build_decision_from_classify,
    normalize_reason,
    route_appendix_a,
    select_apply_node,
)
from src.conversation.langgraph_state_adapter import ingress_order_shadow_compare
from src.conversation.migration_flag_controller import (
    IllegalFlagMatrixError,
    MigrationStage,
    assert_legal_flag_matrix,
    collect_illegal_combinations,
    flag_snapshot,
    get_migration_stage,
)
from src.conversation.minimal_commit_orchestrator import (
    invoke_minimal_commit_orchestrator,
)
from src.conversation.serial_lease import (
    DEFAULT_LEASE_WAIT_MS,
    LeaseTimeoutError,
    SerialLeaseStore,
)
from src.conversation.sport_topic_state import (
    SportTopicState,
    langgraph_state_enabled,
    langgraph_state_shadow_enabled,
)
from src.conversation.sts_checkpoint import (
    CHECKPOINT_SCHEMA_VERSION,
    InMemoryCheckpointStore,
    build_checkpoint,
    compute_checksum,
    hydrate_sts_from_checkpoint,
    refuse_contaminated_hydrate,
    validate_checkpoint,
)
from src.conversation.sts_commit_gate import CommitEvent, run_commit_gate
from src.conversation.thread_identity import (
    SessionIdentityError,
    map_session_to_thread_id,
    resolve_thread_identity,
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
        "ENABLE_TB_V2_APPLY_MATERIALIZER",
        "ENABLE_STS_HOST_APPLY_MATERIALIZER",
        "AURORA_ADR001_FLIP_CONTINGENCY_HOST",
    ):
        os.environ.pop(k, None)


# ---------------------------------------------------------------------------
# Defaults / T9 flag matrix
# ---------------------------------------------------------------------------


def test_t9_defaults_off_and_stage_s0():
    _clear_flags()
    assert langgraph_state_enabled() is False
    assert langgraph_state_shadow_enabled() is False
    assert get_migration_stage() == MigrationStage.S0_OFF
    assert collect_illegal_combinations() == []
    assert assert_legal_flag_matrix() == []
    snap = flag_snapshot()
    assert snap["production_write_active"] is False
    assert snap["migration_stage"] == "S0_OFF"


def test_t9_illegal_i1_write_without_sole_writer():
    _clear_flags()
    os.environ["ENABLE_LANGGRAPH_STATE"] = "1"
    try:
        ids = {v["id"] for v in collect_illegal_combinations()}
        assert "I1" in ids
        assert "I2" in ids  # funnel incomplete
        assert "I3" in ids  # note_* unguarded
        with pytest.raises(IllegalFlagMatrixError):
            assert_legal_flag_matrix(raise_on_illegal=True)
    finally:
        _clear_flags()


def test_t9_shadow_not_write():
    _clear_flags()
    os.environ["ENABLE_LANGGRAPH_STATE_SHADOW"] = "1"
    try:
        assert langgraph_state_shadow_enabled() is True
        assert langgraph_state_enabled() is False
        assert get_migration_stage() == MigrationStage.S1_SHADOW
        # Shadow alone is legal
        assert collect_illegal_combinations() == []
    finally:
        _clear_flags()


def test_t9_i7_claim_shadow_as_sole_writer():
    _clear_flags()
    os.environ["ENABLE_LANGGRAPH_STATE_SHADOW"] = "1"
    os.environ["CLAIM_SHADOW_AS_SOLE_WRITER"] = "1"
    try:
        ids = {v["id"] for v in collect_illegal_combinations()}
        assert "I7" in ids
    finally:
        _clear_flags()


# ---------------------------------------------------------------------------
# T2 — typed DTO / classify outcomes
# ---------------------------------------------------------------------------


def test_t2_dto_fields_and_outcomes():
    _clear_flags()
    sts = SportTopicState()
    d1 = EpisodeTransition.decide("Flamengo x Palmeiras", sts)
    assert d1.outcome == "KEEP_EPISODE"
    assert d1.reason == "seed_subject"
    assert "clubs" in d1.current_entities
    assert d1.prior_subject.get("source") == "STS_SNAPSHOT"
    assert "subject_generation" in d1.prior_subject
    assert d1.entity_equality.get("algorithm") == "CANONICAL_CLUB_SET_EQUALITY"

    sts2 = SportTopicState(
        teams=["Flamengo", "Palmeiras"],
        fixture="Flamengo x Palmeiras",
        subject="Flamengo x Palmeiras",
        subject_generation=1,
    )
    d2 = EpisodeTransition.decide("Liverpool x Chelsea", sts2)
    assert d2.outcome == "NEW_FIXTURE"
    assert d2.reason == "new_fixture"

    d3 = EpisodeTransition.decide("Quem está melhor?", sts2)
    assert d3.outcome == "KEEP_EPISODE"
    assert d3.reason == "soft_followup_same_episode"

    d4 = EpisodeTransition.decide("Inter joga hoje?", sts2)
    assert d4.outcome == "NEW_EPISODE"
    assert d4.reason == "low_entity_overlap"

    d5 = EpisodeTransition.decide("Flamengo x Palmeiras", sts2)
    assert d5.outcome == "KEEP_EPISODE"
    assert d5.reason == "same_fixture_restated"


# ---------------------------------------------------------------------------
# T16 — Appendix A route table
# ---------------------------------------------------------------------------


def test_t16_appendix_a_route_table_coverage():
    expected = {
        ("NEW_FIXTURE", "new_fixture"): "apply_boundary",
        ("NEW_EPISODE", "low_entity_overlap"): "apply_boundary",
        ("NEW_EPISODE", "explicit_new_episode"): "apply_boundary",
        ("KEEP_EPISODE", "soft_followup_same_episode"): "keep_followup",
        ("KEEP_EPISODE", "seed_subject"): "apply_subject",
        ("KEEP_EPISODE", "same_fixture_restated"): "apply_subject",
        ("KEEP_EPISODE", "overlap_ok_keep"): "apply_subject",
    }
    assert APPENDIX_A_ROUTE_TABLE == expected
    for key, node in expected.items():
        assert route_appendix_a(*key) == node

    # seed / same-fixture / soft_FU / new_* via select_apply_node
    for outcome, reason, node in [
        ("KEEP_EPISODE", "seed_subject", "apply_subject"),
        ("KEEP_EPISODE", "same_fixture_restated", "apply_subject"),
        ("KEEP_EPISODE", "soft_followup_same_episode", "keep_followup"),
        ("NEW_FIXTURE", "new_fixture", "apply_boundary"),
        ("NEW_EPISODE", "low_entity_overlap", "apply_boundary"),
    ]:
        dec = EpisodeTransitionDecision(outcome=outcome, reason=reason)
        assert select_apply_node(dec) == node

    assert normalize_reason("overlap_ok") == "overlap_ok_keep"
    assert normalize_reason("new_fixture_no_prior_label") == "new_fixture"


# ---------------------------------------------------------------------------
# T15 — thread_id identity
# ---------------------------------------------------------------------------


def test_t15_thread_id_mapping_and_reject_empty():
    tid = map_session_to_thread_id("session-abc")
    assert tid.startswith("sts:")
    assert len(tid) == 36
    assert tid == map_session_to_thread_id("session-abc")
    assert map_session_to_thread_id("session-xyz") != tid

    ident = resolve_thread_identity("session-abc")
    assert ident.thread_id == tid
    assert ident.checkpoint_ns == "aurora.context_manager.sts"

    for bad in (None, "", "   ", "anon", "anonymous"):
        with pytest.raises(SessionIdentityError):
            map_session_to_thread_id(bad)


# ---------------------------------------------------------------------------
# STS commit gate + subject_generation
# ---------------------------------------------------------------------------


def test_sts_commit_gate_bumps_generation_and_stages():
    _clear_flags()
    sts = SportTopicState()
    assert sts.subject_generation == 0
    tid = map_session_to_thread_id("commit-test-1")
    store = InMemoryCheckpointStore()
    events = [
        CommitEvent(
            kind="replace_subject",
            reason="seed_subject",
            teams=["Flamengo", "Palmeiras"],
            fixture="Flamengo x Palmeiras",
            subject="Flamengo x Palmeiras",
            topic="comparison",
        )
    ]
    result = run_commit_gate(
        sts, events, thread_id=tid, persist=True, store=store
    )
    assert result.ok
    assert result.stage_completed >= 3
    assert result.sts.subject_generation == 1
    assert result.sts.fixture == "Flamengo x Palmeiras"
    assert result.projection_plan.get("subject_generation") == 1
    assert result.checkpoint is not None
    assert result.write_through_applied is False

    loaded, meta = hydrate_sts_from_checkpoint(tid, store)
    assert meta.get("checksum_ok") is True
    assert loaded.fixture == "Flamengo x Palmeiras"
    assert loaded.subject_generation == 1


def test_checkpoint_corrupt_single_recovery_branch():
    store = InMemoryCheckpointStore()
    tid = map_session_to_thread_id("corrupt-1")
    sts = SportTopicState(teams=["A"], fixture="A x B", subject_generation=2)
    rec = build_checkpoint(tid, sts)
    store.save(rec)
    # Tamper payload checksum
    raw = store._data[tid]
    raw["checksum"] = "deadbeef"
    bad = validate_checkpoint(raw)
    assert bad.corrupt is True
    cold, audit = refuse_contaminated_hydrate(bad)
    assert cold.fixture is None
    assert audit["recovery_ux"] == "SUBJECT_RECOVERY_CLARIFY"

    # unexpected schema
    weird = build_checkpoint(tid, sts).to_dict()
    weird["schema_version"] = CHECKPOINT_SCHEMA_VERSION + 99
    weird["checksum"] = compute_checksum(
        sts=weird["sts"],
        subject_generation=weird["subject_generation"],
        projection_plan=weird["projection_plan"],
        schema_version=weird["schema_version"],
    )
    shaped = validate_checkpoint(weird)
    assert shaped.unexpected_shape is True


# ---------------------------------------------------------------------------
# C17 orchestrator — force path; default noop
# ---------------------------------------------------------------------------


def test_c17_default_noop_flags_off():
    _clear_flags()
    sts = SportTopicState(teams=["Flamengo"], fixture=None, subject="Flamengo")
    out = invoke_minimal_commit_orchestrator("Liverpool x Chelsea", sts)
    assert out.skipped is True
    assert out.skipped_reason == "flags_off_orchestrator_noop"
    assert out.sts.subject == "Flamengo"


def test_c17_force_same_edges_sticky_scenario():
    _clear_flags()
    sts = SportTopicState()
    r1 = invoke_minimal_commit_orchestrator(
        "Flamengo x Palmeiras", sts, session_id="c17-sess", force=True
    )
    assert r1.skipped is False
    assert r1.apply_node == "apply_subject"
    assert r1.sts.fixture == "Flamengo x Palmeiras"
    assert r1.decision is not None
    assert r1.commit is not None
    assert r1.commit.sts.subject_generation >= 1

    r2 = invoke_minimal_commit_orchestrator(
        "Liverpool x Chelsea",
        r1.sts,
        session_id="c17-sess",
        force=True,
    )
    assert r2.apply_node == "apply_boundary"
    assert r2.sts.fixture == "Liverpool x Chelsea"
    assert "Flamengo" not in r2.sts.teams

    r3 = invoke_minimal_commit_orchestrator(
        "Quem está melhor?",
        r2.sts,
        session_id="c17-sess",
        force=True,
    )
    assert r3.apply_node == "keep_followup"
    assert r3.sts.fixture == "Liverpool x Chelsea"


def test_c17_not_dual_when_langgraph_write_on():
    _clear_flags()
    os.environ["ENABLE_LANGGRAPH_STATE"] = "1"
    try:
        sts = SportTopicState(teams=["A"], subject="A")
        out = invoke_minimal_commit_orchestrator("B x C", sts)
        assert out.skipped is True
        assert "p4_langgraph_host" in (out.skipped_reason or "")
    finally:
        _clear_flags()


# ---------------------------------------------------------------------------
# Serial lease 5000 ms → 429
# ---------------------------------------------------------------------------


def test_serial_lease_timeout_maps_to_429():
    store = SerialLeaseStore()
    tid = map_session_to_thread_id("lease-1")
    h1 = store.acquire(tid, wait_ms=DEFAULT_LEASE_WAIT_MS)
    assert store.is_held(tid)

    # Hold lease in main; second acquire with short wait must 429
    with pytest.raises(LeaseTimeoutError) as ei:
        store.acquire(tid, wait_ms=50)
    assert ei.value.http_status == 429
    store.release(h1)
    # After release, acquire succeeds
    h2 = store.acquire(tid, wait_ms=100)
    store.release(h2)


def test_serial_lease_serializes_same_thread():
    store = SerialLeaseStore()
    tid = map_session_to_thread_id("lease-2")
    order: list[int] = []

    def worker(n: int):
        with store.hold(tid, wait_ms=2000):
            order.append(n)
            time.sleep(0.05)

    t1 = threading.Thread(target=worker, args=(1,))
    t2 = threading.Thread(target=worker, args=(2,))
    t1.start()
    time.sleep(0.01)
    t2.start()
    t1.join()
    t2.join()
    assert order == [1, 2]


# ---------------------------------------------------------------------------
# Ingress-order hook scaffolding (inactive by default)
# ---------------------------------------------------------------------------


def test_ingress_order_hook_off_by_default_force_ok():
    _clear_flags()
    assert ingress_order_shadow_compare("Flamengo x Palmeiras", {}) is None
    result = ingress_order_shadow_compare(
        "Flamengo x Palmeiras",
        {},
        force=True,
    )
    assert result is not None
    assert result["shadow_path"] == "B_ingress_order"
    assert result["locus_design"] == "post_sll_pre_csl"
    assert result["production_write_enabled"] is False
    assert result["appendix_b_ready"] is False


def test_build_decision_from_classify_helper():
    d = build_decision_from_classify(
        raw_route="apply_boundary",
        raw_reason="new_fixture",
        clubs=["Liverpool", "Chelsea"],
        fixture_label="Liverpool x Chelsea",
        prior_teams=["Flamengo", "Palmeiras"],
        prior_fixture="Flamengo x Palmeiras",
        prior_subject_generation=3,
    )
    assert d.outcome == "NEW_FIXTURE"
    assert select_apply_node(d) == "apply_boundary"
    assert d.prior_subject["subject_generation"] == 3
