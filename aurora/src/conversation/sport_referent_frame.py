"""
P2.5 — Sport Referent Frame (SRF).

Single consumer-facing sport memory for Entity Resolver v2.
Projects from existing ctx fields; does not write into frozen AEP blobs.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Literal

logger = logging.getLogger(__name__)

CTX_KEY = "sport_referent_frame"

FocusKind = Literal["FIXTURE", "TEAM", "COMPETITION", "NONE"]
BindQuality = Literal["FULL", "PARTIAL", "TEAM_ONLY", "AMBIGUOUS", "NONE"]

_EMPTY = {
    "focus_kind": "NONE",
    "home": None,
    "away": None,
    "fixture_label": None,
    "fixture_id": None,
    "focus_team": None,
    "focus_side": "UNKNOWN",
    "competition_label": None,
    "binding_quality": "NONE",
    "ambiguity_score": 0.0,
    "assumptions": [],
    "sources": [],
    "ttl_turns": 0,
    "updated_turn": 0,
    "counters": {
        "projected": 0,
        "assumed": 0,
        "clarified": 0,
        "switched": 0,
        "ttl_expired": 0,
    },
}


def _blank() -> dict[str, Any]:
    import copy

    return copy.deepcopy(_EMPTY)


def get_srf(ctx: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(ctx, dict):
        return _blank()
    raw = ctx.get(CTX_KEY)
    if not isinstance(raw, dict):
        return _blank()
    out = _blank()
    out.update(raw)
    if not isinstance(out.get("counters"), dict):
        out["counters"] = dict(_EMPTY["counters"])
    if not isinstance(out.get("assumptions"), list):
        out["assumptions"] = []
    if not isinstance(out.get("sources"), list):
        out["sources"] = []
    return out


def save_srf(ctx: dict[str, Any] | None, srf: dict[str, Any]) -> None:
    if not isinstance(ctx, dict):
        return
    ctx[CTX_KEY] = srf


def bump(ctx: dict[str, Any] | None, key: str) -> None:
    srf = get_srf(ctx)
    c = srf.setdefault("counters", {})
    c[key] = int(c.get(key) or 0) + 1
    save_srf(ctx, srf)


def tick_ttl(ctx: dict[str, Any] | None) -> dict[str, Any]:
    srf = get_srf(ctx)
    if str(srf.get("focus_kind") or "NONE") == "NONE":
        return srf
    ttl = int(srf.get("ttl_turns") or 0) - 1
    srf["ttl_turns"] = ttl
    if ttl <= 0:
        bump(ctx, "ttl_expired")
        srf = _blank()
        srf["counters"] = get_srf(ctx).get("counters") or dict(_EMPTY["counters"])
    save_srf(ctx, srf)
    return srf


def clear_srf(ctx: dict[str, Any] | None, *, reason: str = "clear") -> None:
    if not isinstance(ctx, dict):
        return
    prev = get_srf(ctx)
    counters = dict(prev.get("counters") or {})
    srf = _blank()
    srf["counters"] = counters
    srf["last_clear_reason"] = reason
    save_srf(ctx, srf)


def set_fixture(
    ctx: dict[str, Any] | None,
    home: str,
    away: str,
    *,
    fixture_id: int | None = None,
    quality: BindQuality = "PARTIAL",
    source: str = "user",
    assumptions: list[str] | None = None,
) -> dict[str, Any]:
    srf = get_srf(ctx)
    srf["focus_kind"] = "FIXTURE"
    srf["home"] = home.strip()
    srf["away"] = away.strip()
    srf["fixture_label"] = f"{srf['home']} x {srf['away']}"
    srf["fixture_id"] = fixture_id
    srf["focus_team"] = None
    srf["focus_side"] = "UNKNOWN"
    srf["binding_quality"] = quality
    srf["ambiguity_score"] = 0.05 if quality != "AMBIGUOUS" else 0.6
    srf["assumptions"] = list(assumptions or [])
    src = list(srf.get("sources") or [])
    if source and source not in src:
        src.append(source)
    srf["sources"] = src[-8:]
    srf["ttl_turns"] = 8
    save_srf(ctx, srf)
    return srf


def set_team(
    ctx: dict[str, Any] | None,
    team: str,
    *,
    ambiguous: bool = False,
    source: str = "user",
    assumptions: list[str] | None = None,
    clear_fixture: bool = True,
) -> dict[str, Any]:
    srf = get_srf(ctx)
    if clear_fixture:
        srf["home"] = None
        srf["away"] = None
        srf["fixture_label"] = None
        srf["fixture_id"] = None
    srf["focus_kind"] = "TEAM"
    srf["focus_team"] = team.strip()
    srf["focus_side"] = "UNKNOWN"
    srf["binding_quality"] = "AMBIGUOUS" if ambiguous else "TEAM_ONLY"
    srf["ambiguity_score"] = 0.65 if ambiguous else 0.15
    srf["assumptions"] = list(assumptions or [])
    src = list(srf.get("sources") or [])
    if source and source not in src:
        src.append(source)
    srf["sources"] = src[-8:]
    srf["ttl_turns"] = 6
    save_srf(ctx, srf)
    bump(ctx, "switched")
    return get_srf(ctx)


def set_focus_team(
    ctx: dict[str, Any] | None,
    team: str,
    *,
    side: str = "UNKNOWN",
) -> dict[str, Any]:
    srf = get_srf(ctx)
    srf["focus_team"] = team.strip()
    srf["focus_side"] = side
    save_srf(ctx, srf)
    return srf


def project_from_ctx(ctx: dict[str, Any] | None) -> dict[str, Any]:
    """
    Fill SRF from existing memory if SRF empty.
    Read-only w.r.t. frozen AEP modules.
    """
    if not isinstance(ctx, dict):
        return _blank()
    srf = get_srf(ctx)
    if str(srf.get("focus_kind") or "NONE") != "NONE":
        return srf

    home = away = fixture = team = None
    quality: BindQuality = "PARTIAL"

    lm = ctx.get("last_match")
    if isinstance(lm, str) and lm.strip():
        fixture = lm.strip()

    try:
        from src.conversation.conversation_continuity import get_continuity

        cont = get_continuity(ctx)
        if isinstance(cont.get("last_fixture"), str) and cont["last_fixture"].strip():
            fixture = fixture or cont["last_fixture"].strip()
        if isinstance(cont.get("last_team"), str) and cont["last_team"].strip():
            team = cont["last_team"].strip()
    except Exception:
        pass

    sm = ctx.get("short_conversation_memory")
    if isinstance(sm, dict):
        fixture = fixture or sm.get("last_fixture") or sm.get("last_match")
        team = team or sm.get("last_team")

    try:
        from src.conversation.sport_continuity_guard import get_sport_anchor

        anchor = get_sport_anchor(ctx)
        if isinstance(anchor, dict) and anchor.get("active"):
            fixture = fixture or anchor.get("fixture")
            teams = anchor.get("teams") or []
            if isinstance(teams, (list, tuple)) and len(teams) >= 2:
                home = str(teams[0])
                away = str(teams[1])
    except Exception:
        pass

    if isinstance(fixture, str) and fixture.strip():
        parts = re.split(r"\s+(?:vs\.?|x|versus)\s+", fixture.strip(), maxsplit=1, flags=re.I)
        if len(parts) == 2 and parts[0].strip() and parts[1].strip():
            home = home or parts[0].strip()
            away = away or parts[1].strip()
            set_fixture(ctx, home, away, quality=quality, source="project")
            bump(ctx, "projected")
            if team:
                set_focus_team(ctx, str(team))
            return get_srf(ctx)

    if isinstance(team, str) and team.strip():
        set_team(ctx, team.strip(), source="project")
        bump(ctx, "projected")
        return get_srf(ctx)

    return srf


def note_from_payload(ctx: dict[str, Any] | None, payload: dict[str, Any] | None) -> None:
    """Update SRF after a sport reply."""
    if not isinstance(ctx, dict) or not isinstance(payload, dict):
        return
    ents = payload.get("entities") or {}
    if not isinstance(ents, dict):
        return
    if ents.get("entity_invalid") or str(ents.get("fixture_quality") or "").upper() in {
        "INVALID",
        "FICTIONAL",
    }:
        return
    home = ents.get("home")
    away = ents.get("away")
    if isinstance(home, str) and isinstance(away, str) and home.strip() and away.strip():
        q = str(ents.get("fixture_quality") or "PARTIAL").upper()
        quality: BindQuality = "FULL" if q == "VALID" else "PARTIAL"
        fid = payload.get("fixture_id") or ents.get("fixture_id")
        try:
            fid_i = int(fid) if fid else None
        except (TypeError, ValueError):
            fid_i = None
        set_fixture(
            ctx,
            home.strip(),
            away.strip(),
            fixture_id=fid_i,
            quality=quality,
            source="payload",
        )
        return
    team = ents.get("resolved_team") or ents.get("followup_resolved_team") or ents.get("team")
    if isinstance(team, str) and team.strip():
        set_team(ctx, team.strip(), source="payload", clear_fixture=False)
        if get_srf(ctx).get("focus_kind") == "FIXTURE":
            set_focus_team(ctx, team.strip())
