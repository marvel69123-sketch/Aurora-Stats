"""
Aurora v4.5 — Context Reinforcement (additive).

Soft priority scores for fixture / market / topic so Aurora is less likely
to "forget" the active thread. Does NOT edit conversation_state.py.

Writes only:
  ctx["context_reinforcement"]
  soft mirrors on ctx last_* keys (already used by legacy readers)

Fail-open.
"""

from __future__ import annotations

import logging
import re
import time
import unicodedata
from typing import Any

logger = logging.getLogger(__name__)

CTX_REINFORCE_KEY = "context_reinforcement"


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _recency_score(updated_at: Any) -> float:
    """Higher when updated recently (minutes)."""
    if updated_at is None:
        return 0.35
    try:
        if isinstance(updated_at, (int, float)):
            age = max(0.0, time.time() - float(updated_at))
        else:
            # ISO-ish — treat presence as recent-ish
            return 0.75
        # 0–30 min → 1.0 … 0.2
        minutes = age / 60.0
        if minutes <= 5:
            return 1.0
        if minutes <= 30:
            return 0.85
        if minutes <= 120:
            return 0.55
        return 0.25
    except Exception:
        return 0.4


def _mention_boost(message: str, label: str | None) -> float:
    if not label:
        return 0.0
    folded = _fold(message)
    parts = [p for p in re.split(r"\s+[xX]\s+|\s+", str(label)) if len(p) >= 3]
    hits = 0
    for p in parts[:4]:
        if _fold(p) in folded:
            hits += 1
    if hits >= 2:
        return 0.35
    if hits == 1:
        return 0.2
    return 0.0


def reinforce_context(
    ctx: dict[str, Any] | None,
    message: str = "",
) -> dict[str, Any]:
    """
    Compute priority scores and re-assert active context onto ctx.
    Returns the reinforcement dict (also stored on ctx).
    """
    empty = {
        "fixture_score": 0.0,
        "market_score": 0.0,
        "recency_score": 0.0,
        "importance_score": 0.0,
        "active_fixture": None,
        "active_market": None,
        "active_topic": None,
        "conversation_goal": None,
        "signals": ["fail_open_empty"],
    }
    if ctx is None:
        return empty
    try:
        st: dict[str, Any] = {}
        try:
            from src.conversation.conversation_state import get_state

            st = get_state(ctx) or {}
        except Exception:
            st = {}

        fx = st.get("active_fixture") or ctx.get("last_match") or ctx.get("last_fixture")
        market = st.get("active_market") or ctx.get("last_market_label")
        # last_market may be a list of markets from analysis
        if not market:
            lm = ctx.get("last_market")
            if isinstance(lm, list) and lm:
                top = lm[0]
                market = top.get("market") if isinstance(top, dict) else str(top)
            elif isinstance(lm, str):
                market = lm
        topic = st.get("active_topic") or ctx.get("active_topic")
        goal = None
        cg = ctx.get("conversation_goal")
        if isinstance(cg, dict):
            goal = cg.get("goal_type") or cg.get("goal")
        elif isinstance(cg, str):
            goal = cg

        recency = _recency_score(st.get("updated_at") or ctx.get("updated_at"))
        fixture_score = 0.0
        market_score = 0.0
        if fx:
            fixture_score = _clamp(0.55 + recency * 0.3 + _mention_boost(message, str(fx)))
        if market:
            market_score = _clamp(0.5 + recency * 0.25 + _mention_boost(message, str(market)))

        # Importance: pending / recommendation / goal present
        importance = 0.3
        if st.get("pending_question") or ctx.get("ci_pending"):
            importance += 0.25
        if st.get("last_recommendation") or ctx.get("last_recommendation"):
            importance += 0.2
        if goal:
            importance += 0.15
        if fx and market:
            importance += 0.1
        importance = _clamp(importance)

        # Soft re-assert legacy mirrors (read-only for State module)
        if fx:
            ctx["last_match"] = fx
            ctx["last_fixture"] = fx
        if st.get("active_home"):
            ctx["last_home"] = st.get("active_home")
        if st.get("active_away"):
            ctx["last_away"] = st.get("active_away")
        if market and not ctx.get("last_market_label"):
            ctx["last_market_label"] = market
        if topic:
            ctx["active_topic"] = topic

        # Protect against accidental wipe: if message mentions previous fixture in history
        # and not the active one, keep active unless explicit new A x B.
        folded = _fold(message)
        has_new_fixture = bool(re.search(r"\b\w+\s+[xX]\s+\w+\b", message or ""))
        hist = list(st.get("fixture_history") or [])
        if fx and not has_new_fixture and hist:
            # Boost active fixture when user uses deixis
            if re.search(r"\b(esse|desse|neste|daquele|o\s+jogo|esse\s+jogo)\b", folded):
                fixture_score = _clamp(fixture_score + 0.15)
                importance = _clamp(importance + 0.1)

        out = {
            "fixture_score": round(fixture_score, 3),
            "market_score": round(market_score, 3),
            "recency_score": round(recency, 3),
            "importance_score": round(importance, 3),
            "active_fixture": fx,
            "active_market": market,
            "active_topic": topic,
            "conversation_goal": goal,
            "signals": ["v4.5_context_reinforcement"],
        }
        ctx[CTX_REINFORCE_KEY] = out
        return out
    except Exception as exc:
        logger.warning("reinforce_context fail-open: %s", exc)
        return empty


def context_anchor_line(ctx: dict[str, Any] | None) -> str | None:
    """Optional short anchor for deep replies (not a header badge)."""
    try:
        data = (ctx or {}).get(CTX_REINFORCE_KEY) or {}
        fx = data.get("active_fixture")
        mkt = data.get("active_market")
        if float(data.get("fixture_score") or 0) < 0.45:
            return None
        if fx and mkt:
            return f"Continuando em {fx}, com foco em {mkt}."
        if fx:
            return f"Continuando em {fx}."
        return None
    except Exception:
        return None
