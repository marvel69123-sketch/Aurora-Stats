"""Aurora — DEBUG audit mode tests."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.debug_audit import (
    DATA_MISSING,
    attach_debug_to_payload,
    audit_blocked,
    audit_from_analyze,
    build_debug_audit,
    debug_mode_enabled,
)


def test_missing_values_marked_data_missing():
    block = build_debug_audit({})
    assert block["fixture_found"] == DATA_MISSING
    assert block["fixture_id"] == DATA_MISSING
    assert block["data_source"] == DATA_MISSING
    assert block["markets_source"] == DATA_MISSING
    assert block["market_reasoning"] == DATA_MISSING
    assert block["fallback_used"] == DATA_MISSING
    assert block["confidence_source"] == DATA_MISSING
    assert block["corner_average"] == DATA_MISSING
    assert block["goal_average"] == DATA_MISSING
    assert block["xg_home"] == DATA_MISSING
    assert block["xg_away"] == DATA_MISSING
    assert block["form_score"] == DATA_MISSING


def test_blocked_audit_marks_stats_missing():
    raw = audit_blocked(fixture_status="FICTIONAL", home="Goku", away="Naruto")
    block = build_debug_audit(raw)
    assert block["fixture_found"] is False
    assert block["fixture_id"] == DATA_MISSING
    assert block["data_source"] == DATA_MISSING
    assert block["markets_source"] == DATA_MISSING
    assert block["market_reasoning"] == DATA_MISSING
    assert block["fallback_used"] is False
    assert block["confidence_source"] == "Fixture Integrity Guard"
    assert block["xg_home"] == DATA_MISSING
    assert block["corner_average"] == DATA_MISSING


def test_attach_debug_only_when_enabled():
    payload = {
        "intent": "analyze_match",
        "entities": {"markets_blocked": True, "fixture_status": "NOT_FOUND"},
        "fixture_status": "NOT_FOUND",
        "_audit": audit_blocked(fixture_status="NOT_FOUND"),
    }
    off = attach_debug_to_payload(dict(payload), enabled=False)
    assert "debug" not in off
    assert "_audit" not in off

    on = attach_debug_to_payload(dict(payload), enabled=True)
    assert on["debug"]["fixture_found"] is False
    assert on["debug"]["xg_away"] == DATA_MISSING
    assert "_audit" not in on


def test_xg_absent_when_no_has_xg():
    class _Meth:
        has_xg = False
        has_stats = False
        has_standings = False
        is_live = False
        minute = 0
        total_corners = 0
        h_xg_val = 0.0
        a_xg_val = 0.0
        h_gpg = 1.2
        a_gpg = 1.1

    raw = audit_from_analyze(
        fixture_located=True,
        fixture_id=99,
        is_partial=False,
        best_markets=[
            {"rationale": "Over 2.5 from Poisson."},
        ],
        data_sources=["Methodology Engine"],
        meth=_Meth(),
        used_baseline_markets=True,
    )
    block = build_debug_audit(raw)
    assert block["fixture_found"] is True
    assert block["fixture_id"] == 99
    assert block["data_source"] == "API-Football"
    assert block["markets_source"] == "DecisionCenter"
    assert "Poisson" in block["market_reasoning"]
    assert block["fallback_used"] is True
    assert block["xg_home"] == DATA_MISSING
    assert block["xg_away"] == DATA_MISSING
    assert block["goal_average"] == DATA_MISSING
    assert block["form_score"] == DATA_MISSING


def test_debug_mode_from_message_token():
    assert debug_mode_enabled(False, message="analisar flamengo x palmeiras #debug")
    assert debug_mode_enabled(True, message="oi")
    assert not debug_mode_enabled(False, message="analisar flamengo x palmeiras")
