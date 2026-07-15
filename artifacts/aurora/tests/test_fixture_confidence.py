"""Fixture-quality confidence mapping (v3.3.1-beta)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.routers.copilot_unified_router import _resolve_fixture_confidence


def test_degraded_never_moderate():
    score, label = _resolve_fixture_confidence(
        7.8, fixture_located=False, degraded=True,
    )
    assert label == "insufficient"
    assert score <= 1.5


def test_partial_fixture_very_low():
    score, label = _resolve_fixture_confidence(
        6.5, fixture_located=False, degraded=False,
    )
    assert label == "insufficient"
    assert score <= 1.5


def test_located_healthy_moderate_or_strong():
    s1, l1 = _resolve_fixture_confidence(5.0, fixture_located=True, degraded=False)
    assert l1 == "moderate"
    assert s1 >= 6.0

    s2, l2 = _resolve_fixture_confidence(8.2, fixture_located=True, degraded=False)
    assert l2 == "strong"
    assert s2 >= 7.5


def test_located_but_degraded_forced_low():
    score, label = _resolve_fixture_confidence(
        9.0, fixture_located=True, degraded=True,
    )
    assert label == "insufficient"
    assert score <= 1.5
