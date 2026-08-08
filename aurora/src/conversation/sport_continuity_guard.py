"""
8.4-A.18 — Sport Continuity Guard.

Status: FROZEN (AEP P0 stabilization closed — do not patch without P1 redesign).

Keeps short sport follow-ups on SPORT when a compact sport_context_anchor is active.
TTL 2–4 turns. No infinite soft-hold. No sticky ownership_stability reclaim.
Fail-open.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any

logger = logging.getLogger(__name__)

CTX_KEY = "sport_continuity_guard"
ANCHOR_TTL_TURNS = 4  # hard max
ANCHOR_TTL_MIN = 2

_OBS_KEYS = (
    "sport_anchor_created",
    "sport_anchor_used",
    "sport_anchor_expired",
    "nc_blocked_by_sport",
    "ga_blocked_by_sport",
    "continuity_preserved",
    "continuity_lost",
)

_SHORT_FU = re.compile(
    r"^(?:"
    r"(?:e\s+)?(?:a\s+|o\s+|as\s+|os\s+)?"
    r"(?:pressao|pressão|xg|kelly|edge|stake|value|momentum|odds?|odd|"
    r"estatisticas?|estatísticas?|mercados?|mercado|placar|favorito|"
    r"escanteios?|chutes?|posse|probabilidade|confianca|confiança|"
    r"criterio\s+de\s+kelly|critério\s+de\s+kelly)"
    r"|"
    r"e\s+(?:dele|dela|do\s+outro|da\s+outra|esse|essa|desse|dessa|ele|ela|agora|ai|aí)"
    r"|"
    r"(?:e\s+)?(?:o\s+)?outro"
    r"|"
    r"(?:mais\s+detalhes|todos\s+os\s+mercados|explica\s+melhor|e\s+agora)"
    r"|"
    r"(?:markets?|pressure|score|stats?|xg|corners?)"
    r")"
    r"(?:\s+\w+){0,3}"
    r"\s*[?!]*$",
    re.I,
)

# Explicit non-sport — never force SPORT continuity
_NON_SPORT = re.compile(
    r"^(?:"
    r"(?:oi|ola|olá|e\s*ai|e\s*aí|boa\s*(?:noite|tarde|dia)|bom\s+dia|fala|hey|hi|hello)"
    r"|"
    r"(?:qual\s+(?:e|é)\s+(?:o\s+)?seu\s+nome|seu\s+nome|(?:voce|você)\s+e\s+a\s+aurora)"
    r"|"
    r"(?:o\s+que\s+(?:voce|você)\s+faz|o\s+que\s+sabe\s+fazer|suas?\s+funcionalidades)"
    r"|"
    r"(?:pesquisa\s+o\s+\w+|me\s+fala\s+do\s+\w+)"
    r")"
    r"[\s?!.,]*$",
    re.I,
)


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


def _blob(ctx: dict[str, Any]) -> dict[str, Any]:
    b = ctx.get(CTX_KEY)
    if not isinstance(b, dict):
        b = {"counters": {}, "anchor": None, "turn_index": 0}
        ctx[CTX_KEY] = b
    if not isinstance(b.get("counters"), dict):
        b["counters"] = {}
    for k in _OBS_KEYS:
        b["counters"].setdefault(k, 0)
    return b


def bump(ctx: dict[str, Any] | None, key: str, *, n: int = 1) -> None:
    if not isinstance(ctx, dict) or key not in _OBS_KEYS:
        return
    try:
        _blob(ctx)["counters"][key] = int(_blob(ctx)["counters"].get(key) or 0) + n
    except Exception:
        pass


def get_guard_counters(ctx: dict[str, Any] | None) -> dict[str, int]:
    if not isinstance(ctx, dict):
        return {k: 0 for k in _OBS_KEYS}
    return dict(_blob(ctx).get("counters") or {})


def is_sport_short_followup(message: str | None) -> bool:
    """sport_short_followup_detector"""
    folded = _fold(message or "")
    if not folded or len(folded.split()) > 8:
        return False
    if _NON_SPORT.match(folded):
        return False
    try:
        from src.conversation.pronoun_continuity import is_pronoun_followup

        if is_pronoun_followup(message):
            return True
    except Exception:
        pass
    try:
        from src.conversation.advanced_football_continuity import (
            is_advanced_football_followup,
        )

        if is_advanced_football_followup(message):
            return True
    except Exception:
        pass
    try:
        from src.conversation.conversation_continuity import _is_short_followup

        if _is_short_followup(message or ""):
            return True
    except Exception:
        pass
    return bool(_SHORT_FU.match(folded))


def is_non_sport_message(message: str | None) -> bool:
    folded = _fold(message or "")
    if not folded:
        return False
    if _NON_SPORT.match(folded):
        return True
    if folded.startswith("pesquisa ") or folded.startswith("me fala do "):
        return True
    return False


def get_sport_anchor(ctx: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(ctx, dict):
        return None
    anchor = _blob(ctx).get("anchor")
    if not isinstance(anchor, dict) or not anchor.get("active"):
        return None
    if int(anchor.get("turns_left") or 0) <= 0:
        return None
    return anchor


def sport_anchor_active(ctx: dict[str, Any] | None) -> bool:
    return get_sport_anchor(ctx) is not None


def create_sport_context_anchor(
    ctx: dict[str, Any] | None,
    *,
    fixture: str | None = None,
    home: str | None = None,
    away: str | None = None,
    teams: list[str] | None = None,
    competition: str | None = None,
    market_context: Any = None,
    ttl_turns: int = ANCHOR_TTL_TURNS,
    reason: str = "sport_analysis",
) -> dict[str, Any] | None:
    """Persist compact sport_context_anchor (never invents odds)."""
    if not isinstance(ctx, dict):
        return None
    # 8.4-A.20 — bootstrap guard: no sport_anchor while ambiguous
    try:
        from src.conversation.ambiguous_context_guard import bootstrap_blocked

        if bootstrap_blocked(ctx, reason=reason):
            logger.warning(
                "[AUDIT] SportAnchor: BLOCKED bootstrap reason=%s", reason
            )
            return None
    except Exception:
        pass
    fx = (fixture or "").strip() or None
    if not fx:
        lm = ctx.get("last_match")
        if isinstance(lm, str) and lm.strip():
            fx = lm.strip()
    if not fx and not home and not (teams or []):
        return None

    team_list = [t for t in (teams or []) if isinstance(t, str) and t.strip()]
    if home and home not in team_list:
        team_list.insert(0, home)
    if away and away not in team_list:
        team_list.append(away)
    if not home and fx and " x " in fx.lower():
        parts = re.split(r"\s+x\s+", fx, maxsplit=1, flags=re.I)
        if len(parts) == 2:
            home, away = parts[0].strip(), parts[1].strip()
            if home and home not in team_list:
                team_list.insert(0, home)
            if away and away not in team_list:
                team_list.append(away)

    ttl = max(ANCHOR_TTL_MIN, min(ANCHOR_TTL_TURNS, int(ttl_turns)))
    blob = _blob(ctx)
    prev = blob.get("anchor") if isinstance(blob.get("anchor"), dict) else None
    anchor = {
        "active": True,
        "fixture": fx,
        "home": home,
        "away": away,
        "teams": team_list,
        "competition": competition,
        "market_context": market_context
        if market_context is not None
        else (prev or {}).get("market_context"),
        "turns_left": ttl,
        "reason": reason,
    }
    blob["anchor"] = anchor
    # Mirror into session keys used by continuity resolvers (no invention)
    if fx:
        ctx.setdefault("last_match", fx)
    bump(ctx, "sport_anchor_created")
    logger.warning(
        "[AUDIT] SportAnchor: CREATED fixture=%r teams=%s ttl=%s reason=%s",
        fx,
        team_list,
        ttl,
        reason,
    )
    return anchor


def refresh_sport_anchor(ctx: dict[str, Any] | None, *, ttl_turns: int | None = None) -> None:
    """Refresh TTL on successful sport continuity use (capped)."""
    if not isinstance(ctx, dict):
        return
    anchor = get_sport_anchor(ctx)
    if not anchor:
        return
    ttl = max(ANCHOR_TTL_MIN, min(ANCHOR_TTL_TURNS, int(ttl_turns or ANCHOR_TTL_TURNS)))
    anchor["turns_left"] = ttl
    _blob(ctx)["anchor"] = anchor


def expire_sport_anchor(ctx: dict[str, Any] | None, *, reason: str = "expired") -> None:
    if not isinstance(ctx, dict):
        return
    blob = _blob(ctx)
    anchor = blob.get("anchor")
    if isinstance(anchor, dict) and anchor.get("active"):
        bump(ctx, "sport_anchor_expired")
        bump(ctx, "continuity_lost")
        anchor["active"] = False
        anchor["turns_left"] = 0
        anchor["expire_reason"] = reason
        blob["anchor"] = anchor
        logger.warning("[AUDIT] SportAnchor: EXPIRED reason=%s", reason)


def tick_sport_anchor(ctx: dict[str, Any] | None, *, used: bool = False) -> None:
    """
    Advance TTL. Successful sport use refreshes; unused turns decrement.
    """
    if not isinstance(ctx, dict):
        return
    blob = _blob(ctx)
    blob["turn_index"] = int(blob.get("turn_index") or 0) + 1
    anchor = blob.get("anchor")
    if not isinstance(anchor, dict) or not anchor.get("active"):
        return
    if used:
        refresh_sport_anchor(ctx, ttl_turns=ANCHOR_TTL_TURNS)
        bump(ctx, "sport_anchor_used")
        bump(ctx, "continuity_preserved")
        return
    left = int(anchor.get("turns_left") or 0) - 1
    anchor["turns_left"] = left
    blob["anchor"] = anchor
    if left <= 0:
        expire_sport_anchor(ctx, reason="ttl_turns")


def should_block_nc(ctx: dict[str, Any] | None, message: str | None) -> bool:
    """NC block: active sport_anchor + short_followup → natural_conversation must not claim."""
    if not isinstance(ctx, dict):
        return False
    if is_non_sport_message(message):
        return False
    if not sport_anchor_active(ctx):
        return False
    if not is_sport_short_followup(message):
        return False
    bump(ctx, "nc_blocked_by_sport")
    return True


def should_block_ga_sport(ctx: dict[str, Any] | None, message: str | None) -> bool:
    """GA block while valid sport continuity (anchor + short FU)."""
    if not isinstance(ctx, dict):
        return False
    if is_non_sport_message(message):
        return False
    if not sport_anchor_active(ctx):
        return False
    if not is_sport_short_followup(message):
        return False
    bump(ctx, "ga_blocked_by_sport")
    return True


def _minimal_sport_hold(message: str, ctx: dict[str, Any], anchor: dict[str, Any]) -> dict[str, Any]:
    """One-shot SPORT continuity prose — conversation_continuity owner, not sticky OS."""
    label = anchor.get("fixture") or (anchor.get("teams") or ["o jogo"])[0]
    team = None
    teams = anchor.get("teams") or []
    if teams:
        team = teams[0]
    text = (
        f"Seguindo **{label}**. "
        f"Pode pedir mercados, placar, estatísticas, pressão/xG, escanteios ou 'e o outro?'."
    )
    return {
        "intent": "follow_up",
        "entities": {
            "followup": True,
            "continuity_followup": True,
            "followup_before_fallback": True,
            "sport_continuity_guard": True,
            "sport_anchor_used": True,
            "team": team,
            "followup_resolved_team": team,
            "followup_resolved_fixture": anchor.get("fixture"),
            "turn_owner": "SPORT",
            "response_owner": "conversation_continuity",
            "rewrite_locked": True,
            "show_header": False,
            "continuity_kind": "sport_continuity_guard",
        },
        "executive_summary": text,
        "final_recommendation": text,
        "knowledge_notes": [
            f"8.4-A.18 sport_continuity_guard msg={message[:80]!r} fixture={anchor.get('fixture')!r}"
        ],
        "aurora_version": "Aurora v3.3.2-beta",
    }


def try_sport_continuity_claim(
    message: str,
    ctx: dict[str, Any] | None,
    *,
    brain: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """
    When anchor active + short FU: claim via existing resolvers, else minimal SPORT hold.
    Never uses ownership_stability soft-hold loop.
    """
    if not isinstance(ctx, dict):
        return None
    try:
        if is_non_sport_message(message):
            return None
        if not is_sport_short_followup(message):
            return None

        anchor = get_sport_anchor(ctx)
        if not anchor:
            # Opportunistic arm from session memory (no invention)
            fx = ctx.get("last_match") if isinstance(ctx.get("last_match"), str) else None
            if fx:
                create_sport_context_anchor(ctx, fixture=fx, reason="session_memory")
                anchor = get_sport_anchor(ctx)
        if not anchor:
            return None

        # Ensure continuity window armed for resolvers
        try:
            from src.conversation.conversation_continuity import _arm

            _arm(
                ctx,
                mode="sport_continuity_guard",
                team=(anchor.get("teams") or [None])[0],
                fixture=anchor.get("fixture"),
                turns=min(4, int(anchor.get("turns_left") or 3)),
            )
        except Exception:
            pass

        # Priority: continuity → pronoun → advanced
        try:
            from src.conversation.conversation_continuity import (
                apply_continuity_resolve,
                try_contextual_short_followup,
            )

            apply_continuity_resolve(message, ctx)
            payload = try_contextual_short_followup(message, ctx, brain=brain)
            if isinstance(payload, dict):
                tick_sport_anchor(ctx, used=True)
                ents = dict(payload.get("entities") or {})
                ents["sport_continuity_guard"] = True
                ents["sport_anchor_used"] = True
                ents.setdefault("turn_owner", "SPORT")
                ents.setdefault("response_owner", "conversation_continuity")
                ents["rewrite_locked"] = True
                payload["entities"] = ents
                payload["intent"] = "follow_up"
                return payload
        except Exception as exc:
            logger.warning("sport_continuity_guard: continuity skipped (%s)", exc)

        try:
            from src.conversation.pronoun_continuity import try_pronoun_continuity

            payload = try_pronoun_continuity(message, ctx, brain=brain)
            if isinstance(payload, dict):
                tick_sport_anchor(ctx, used=True)
                ents = dict(payload.get("entities") or {})
                ents["sport_continuity_guard"] = True
                ents["sport_anchor_used"] = True
                ents.setdefault("turn_owner", "SPORT")
                ents.setdefault("response_owner", "pronoun_continuity")
                ents["rewrite_locked"] = True
                payload["entities"] = ents
                payload["intent"] = "follow_up"
                return payload
        except Exception as exc:
            logger.warning("sport_continuity_guard: pronoun skipped (%s)", exc)

        try:
            from src.conversation.advanced_football_continuity import (
                try_advanced_football_continuity,
            )

            payload = try_advanced_football_continuity(message, ctx, brain=brain)
            if isinstance(payload, dict):
                tick_sport_anchor(ctx, used=True)
                ents = dict(payload.get("entities") or {})
                ents["sport_continuity_guard"] = True
                ents["sport_anchor_used"] = True
                ents.setdefault("turn_owner", "SPORT")
                ents.setdefault("response_owner", "advanced_football_continuity")
                ents["rewrite_locked"] = True
                payload["entities"] = ents
                payload["intent"] = "follow_up"
                return payload
        except Exception as exc:
            logger.warning("sport_continuity_guard: advanced skipped (%s)", exc)

        # No generic soft-hold (avoids USELESS_REPLY). Still mark GA/NC block for this turn.
        ctx["sport_continuity_block_ga"] = True
        ctx["sport_continuity_block_nc"] = True
        bump(ctx, "ga_blocked_by_sport")
        bump(ctx, "nc_blocked_by_sport")
        # Pronoun-like only: tiny SPORT continuity cue (not ownership_stability)
        folded = _fold(message)
        if folded.startswith("e ") or folded in {"outro", "o outro", "o outro?"}:
            hold = _minimal_sport_hold(message, ctx, anchor)
            tick_sport_anchor(ctx, used=True)
            return hold
        return None
    except Exception as exc:
        logger.warning("try_sport_continuity_claim fail-open: %s", exc)
        return None


def note_sport_anchor_after_response(
    ctx: dict[str, Any] | None,
    message: str | None,
    payload: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Create/refresh anchor after real sport replies; tick otherwise."""
    if not isinstance(ctx, dict) or not isinstance(payload, dict):
        return payload
    try:
        ents = dict(payload.get("entities") or {})
        intent = str(payload.get("intent") or "")
        owner = str(ents.get("response_owner") or "")
        sport_reply = (
            intent in {"analyze_match", "match_opinion", "follow_up"}
            and (
                owner
                in {
                    "partial_analysis",
                    "conversation_continuity",
                    "pronoun_continuity",
                    "advanced_football_continuity",
                    "match_opinion_renderer",
                }
                or bool(ents.get("sport_continuity_guard"))
                or bool(ents.get("continuity_followup"))
                or bool(ents.get("_partial"))
                or payload.get("_partial")
            )
        )
        # Extract fixture/teams from payload/ctx
        fx = (
            ents.get("followup_resolved_fixture")
            or ents.get("pronoun_fixture")
            or ctx.get("last_match")
        )
        home = ents.get("home")
        away = ents.get("away")
        if isinstance(fx, str) and " x " in fx.lower() and not home:
            parts = re.split(r"\s+x\s+", fx, maxsplit=1, flags=re.I)
            if len(parts) == 2:
                home, away = parts[0].strip(), parts[1].strip()

        team_only = ents.get("team") or ents.get("followup_resolved_team")
        if not team_only:
            sm = ctx.get("short_conversation_memory")
            if isinstance(sm, dict):
                team_only = sm.get("last_team")
        if intent == "analyze_match" or (
            sport_reply and fx and not sport_anchor_active(ctx)
        ):
            create_sport_context_anchor(
                ctx,
                fixture=str(fx) if fx else None,
                home=str(home) if home else None,
                away=str(away) if away else None,
                competition=ents.get("league") or ents.get("competition"),
                market_context=payload.get("best_markets") or ents.get("markets"),
                reason="post_sport_reply",
            )
        elif (
            not sport_anchor_active(ctx)
            and isinstance(team_only, str)
            and team_only.strip()
            and not is_non_sport_message(message)
        ):
            # Weak team anchor (TTL 3) for team-only → short FU chains
            create_sport_context_anchor(
                ctx,
                teams=[team_only.strip()],
                ttl_turns=3,
                reason="team_context",
            )
        elif sport_reply and sport_anchor_active(ctx):
            tick_sport_anchor(ctx, used=True)
        elif is_non_sport_message(message):
            # Digression: decrement TTL, do not force sport
            tick_sport_anchor(ctx, used=False)
        elif not ents.get("sport_continuity_guard"):
            # Neutral turn — soft decrement if anchor exists
            if sport_anchor_active(ctx) and not is_sport_short_followup(message):
                tick_sport_anchor(ctx, used=False)

        ents["sport_guard_counters"] = get_guard_counters(ctx)
        anchor = get_sport_anchor(ctx)
        if anchor:
            ents["sport_anchor_active"] = True
            ents["sport_anchor_ttl"] = anchor.get("turns_left")
            ents["sport_anchor_fixture"] = anchor.get("fixture")
        else:
            ents["sport_anchor_active"] = False
        payload["entities"] = ents
        return payload
    except Exception as exc:
        logger.warning("note_sport_anchor_after_response fail-open: %s", exc)
        return payload
