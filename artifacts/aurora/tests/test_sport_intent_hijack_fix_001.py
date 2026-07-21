"""SPORT-INTENT-HIJACK-FIX-001 — stale CSL must not rewrite new A x B fixtures."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure artifacts/aurora is on path when run via .tools/python312
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.conversation.sport_intent_layer import (  # noqa: E402
    COMPARE_STRENGTH,
    RECENT_FORM,
    _skill_compare_strength,
    apply_sport_intent_layer,
    apply_sport_intent_resolve,
)


def _seed_flamengo(ctx: dict | None = None) -> dict:
    base = ctx if isinstance(ctx, dict) else {}
    base["csl"] = {
        "teams": ["Flamengo", "Palmeiras"],
        "fixture": "Flamengo x Palmeiras",
        "topic": "comparison",
    }
    base["last_match"] = "Flamengo x Palmeiras"
    return base


def test_case1_liverpool_x_chelsea_not_hijacked_by_flamengo_csl():
    """Seed Flamengo CSL → 'Liverpool x Chelsea' must keep Liverpool/Chelsea."""
    os.environ["ENABLE_SPORT_INTENTS"] = "1"
    ctx = _seed_flamengo()
    out = apply_sport_intent_resolve("Liverpool x Chelsea", ctx)
    assert "Liverpool" in out
    assert "Chelsea" in out
    assert "Flamengo" not in out
    assert "Palmeiras" not in out
    # force_refresh_entities: CSL subject slots updated from message
    csl = ctx.get("csl") or {}
    teams = csl.get("teams") or []
    assert any("Liverpool" in str(t) for t in teams)
    assert any("Chelsea" in str(t) for t in teams)
    assert ctx.get("sport_intent_new_fixture") is True
    assert ctx.get("ignore_previous_fixture") is True

    # Follow-up after refresh must use Liverpool, not Flamengo
    r2 = apply_sport_intent_layer("Quem está melhor?", ctx)
    assert r2.intent == RECENT_FORM
    routed = r2.routed_text or ""
    assert "Liverpool" in routed
    assert "Chelsea" in routed
    assert "Flamengo" not in routed


def test_case2_bare_followup_preserves_flamengo_continuity():
    """Seed Flamengo → bare 'Quem está melhor?' keeps Flamengo/Palmeiras."""
    os.environ["ENABLE_SPORT_INTENTS"] = "1"
    ctx = _seed_flamengo()
    r = apply_sport_intent_layer("Quem está melhor?", ctx)
    assert r.applied is True
    assert r.intent == RECENT_FORM
    routed = r.routed_text or ""
    assert "Flamengo" in routed
    assert "Palmeiras" in routed
    assert ctx.get("sport_intent_new_fixture") is not True


def test_case3_soft_entity_switch_does_not_wipe_inter():
    """
    Soft FU 'E o Grêmio?' must not be treated as full new-fixture wipe.
    Sport intent may no-op; Inter CSL must remain intact (no Flamengo hijack).
    """
    os.environ["ENABLE_SPORT_INTENTS"] = "1"
    ctx = {
        "csl": {
            "teams": ["Inter", "Grêmio"],
            "fixture": "Inter x Grêmio",
            "topic": "comparison",
        },
        "last_match": "Inter x Grêmio",
    }
    out = apply_sport_intent_resolve("E o Grêmio?", ctx)
    # No crash; message left alone or soft-shaped without Flamengo bleed
    assert "Flamengo" not in (out or "")
    csl = ctx.get("csl") or {}
    teams = [str(t) for t in (csl.get("teams") or [])]
    assert any("Inter" in t for t in teams)
    assert ctx.get("sport_intent_new_fixture") is not True
    assert ctx.get("ignore_previous_fixture") is not True


def test_compare_strength_unit_old_csl_new_fixture():
    """Unit: _skill_compare_strength must not rewrite new A x B with stale CSL."""
    os.environ["ENABLE_SPORT_INTENTS"] = "1"
    ctx = _seed_flamengo()
    rewritten = _skill_compare_strength("Liverpool x Chelsea", ctx)
    assert rewritten is None  # leave message sides intact

    # apply path also safe
    r = apply_sport_intent_layer("Liverpool x Chelsea", ctx)
    assert r.intent == COMPARE_STRENGTH
    text = r.routed_text or ""
    assert "Liverpool" in text and "Chelsea" in text
    assert "Flamengo" not in text


def test_compare_strength_bare_followup_uses_csl():
    """Bare compare follow-up without sides may inject CSL (continuity OK)."""
    os.environ["ENABLE_SPORT_INTENTS"] = "1"
    ctx = _seed_flamengo()
    rewritten = _skill_compare_strength("quem é mais forte?", ctx)
    assert rewritten is not None
    assert "Flamengo" in rewritten
    assert "Palmeiras" in rewritten


def test_flag_disabled_noop_even_with_stale_csl():
    os.environ["ENABLE_SPORT_INTENTS"] = "0"
    try:
        ctx = _seed_flamengo()
        msg = "Liverpool x Chelsea"
        out = apply_sport_intent_resolve(msg, ctx)
        assert out == msg
        assert ctx.get("sport_intent_new_fixture") is not True
    finally:
        os.environ["ENABLE_SPORT_INTENTS"] = "1"
