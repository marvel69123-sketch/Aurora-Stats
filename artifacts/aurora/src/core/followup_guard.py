"""
Aurora v3.3.1-beta — Follow-up hijacking guard.

Before reusing conversation context, compare fixture entities.
If the message names a different match, discard follow-up reuse and
start a fresh fixture context.

Does NOT change methodology / market / confidence / learning engines.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FollowupReuseDecision:
    previous_fixture: str
    new_fixture: str | None
    reuse: bool
    home: str | None = None
    away: str | None = None
    is_live: bool = False
    reason: str = ""


def _fixtures_equivalent(
    home: str,
    away: str,
    *,
    last_match: str = "",
    last_home: str = "",
    last_away: str = "",
) -> bool:
    """True when named teams refer to the same fixture already in context."""
    try:
        from src.core.entity_resolver import fold
    except Exception:
        def fold(text: str) -> str:  # type: ignore[misc]
            return (text or "").strip().lower()

    fh, fa = fold(home or ""), fold(away or "")
    if not fh or not fa:
        return False
    if last_home and last_away:
        lh, la = fold(last_home), fold(last_away)
        if {fh, fa} == {lh, la}:
            return True
    lm = fold(last_match or "")
    return bool(lm) and fh in lm and fa in lm


def _extract_named_fixture(message: str) -> tuple[str | None, str | None, bool]:
    """Best-effort home/away from cleaner + NL route (presentation/routing only)."""
    home = away = None
    is_live = False

    try:
        from src.core.fixture_input_cleaner import clean_fixture_input

        cleaned = clean_fixture_input(message)
        if cleaned.home_team and cleaned.away_team:
            home, away = cleaned.home_team, cleaned.away_team
            is_live = bool(cleaned.is_live)
    except Exception as exc:
        logger.warning("followup_guard: cleaner skipped (%s)", exc)

    try:
        from src.core.nl_router import route

        peeked = route(message)
        ents = peeked.entities or {}
        if peeked.intent == "analyze_match" and ents.get("home") and ents.get("away"):
            home = str(ents["home"]).strip()
            away = str(ents["away"]).strip()
            is_live = bool(ents.get("is_live") or is_live)
    except Exception as exc:
        logger.warning("followup_guard: nl peek skipped (%s)", exc)

    return home or None, away or None, is_live


def decide_followup_reuse(message: str, ctx: dict[str, Any] | None) -> FollowupReuseDecision:
    """
    Compare message entities against previous fixture context.

    reuse=True  → safe to resolve from last_analysis
    reuse=False → discard follow-up; analyze the new fixture / create new context
    """
    ctx = ctx or {}
    previous = str(ctx.get("last_match") or ctx.get("last_fixture") or "").strip()
    last_home = str(ctx.get("last_home") or "").strip()
    last_away = str(ctx.get("last_away") or "").strip()

    home, away, is_live = _extract_named_fixture(message)
    new_fixture = f"{home} x {away}" if home and away else None

    if not previous:
        decision = FollowupReuseDecision(
            previous_fixture="",
            new_fixture=new_fixture,
            reuse=False,
            home=home,
            away=away,
            is_live=is_live,
            reason="no_previous_fixture",
        )
        _log_decision(decision)
        return decision

    if home and away:
        same = _fixtures_equivalent(
            home,
            away,
            last_match=previous,
            last_home=last_home,
            last_away=last_away,
        )
        if same:
            decision = FollowupReuseDecision(
                previous_fixture=previous,
                new_fixture=new_fixture,
                reuse=True,
                home=home,
                away=away,
                is_live=is_live,
                reason="same_fixture",
            )
        else:
            decision = FollowupReuseDecision(
                previous_fixture=previous,
                new_fixture=new_fixture,
                reuse=False,
                home=home,
                away=away,
                is_live=is_live,
                reason="different_fixture",
            )
        _log_decision(decision)
        return decision

    # No explicit teams in message — classic follow-up may reuse context
    decision = FollowupReuseDecision(
        previous_fixture=previous,
        new_fixture=None,
        reuse=True,
        home=None,
        away=None,
        is_live=False,
        reason="no_new_teams_in_message",
    )
    _log_decision(decision)
    return decision


def _log_decision(decision: FollowupReuseDecision) -> None:
    logger.warning("PREVIOUS_FIXTURE=%r", decision.previous_fixture or None)
    logger.warning("NEW_FIXTURE=%r", decision.new_fixture)
    logger.warning("FOLLOWUP_REUSED=%s", "true" if decision.reuse else "false")
    if decision.reason:
        logger.warning(
            "[AUDIT] followup_guard: reason=%s home=%r away=%r",
            decision.reason,
            decision.home,
            decision.away,
        )


def start_new_fixture_context(
    ctx: dict[str, Any],
    home: str,
    away: str,
    *,
    is_live: bool = False,
) -> None:
    """
    Discard prior analysis blob and seed a fresh fixture context in-place.

    Called when FOLLOWUP_REUSED=false and a new A x B was named.
    """
    home = (home or "").strip()
    away = (away or "").strip()
    match = f"{home} x {away}" if home and away else ""
    ctx["last_home"] = home
    ctx["last_away"] = away
    ctx["last_match"] = match
    ctx["last_fixture"] = match
    ctx["last_intent"] = "analyze_match"
    ctx["last_is_live"] = bool(is_live)
    ctx["last_analysis"] = None
    ctx["last_market"] = None
    ctx["last_confidence"] = 0.0
    ctx["last_entities"] = [{"home": home, "away": away}] if home and away else []
    ctx.pop("last_live_at", None)
    ctx.pop("last_response_metadata", None)
    from datetime import datetime, timezone

    ctx["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    logger.warning(
        "[AUDIT] followup_guard: started NEW context for %r (cleared last_analysis)",
        match,
    )


# Re-export for router compatibility
fixtures_equivalent = _fixtures_equivalent
