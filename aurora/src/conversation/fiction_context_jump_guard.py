"""
8.4-A.22 — Fiction & Hard Context Jump Guard.

Status: FROZEN (AEP P0 stabilization closed — do not patch without P1 redesign).
Note: A.22 gain was <1 pp; kept as defensive scrub only — not an approved lift patch.

Surgical residual-cluster patch:
- detect fiction topics
- detect hard context jumps (SPORT → identity/fiction/general)
- hard context reset (drop residual sport continuity / locks / priming)

Does NOT modify ownership architecture, Sport Continuity Guard logic,
Ambiguous Context Guard detector, continuity TTL, or routing tables.
Fail-open. Never invents match data.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any

logger = logging.getLogger(__name__)

CTX_KEY = "fiction_context_jump_guard"

_OBS_KEYS = (
    "fiction_detected",
    "hard_context_jump",
    "hard_context_reset",
    "residual_context_released",
    "wrong_context_prevented",
)

# Fiction characters / universes / hypothetical matchups
_FICTION_RE = re.compile(
    r"(?:"
    r"\bgoku\b|\bnaruto\b|\bvoldemort\b|\bbatman\b|\bsuperman\b|"
    r"\bpikachu\b|\bsonic\b|\bluffy\b|\bzoro\b|\bsaitama\b|"
    r"\bvegeta\b|\bicaro\b|\bthanos\b|\bspider[-\s]?man\b|"
    r"\biron\s*man\b|\bwonder\s*woman\b|\bdeadpool\b|"
    r"harry\s+potter|\bpotter\b|"
    r"goku\s*[xvs]+\s*naruto|"
    r"harry\s+potter\s*[xvs]+\s*voldemort|"
    r"batman\s*[xvs]+\s*superman|"
    r"pikachu\s*[xvs]+|"
    r"anime|mang[aá]|universo\s+fict|"
    r"personagem\s+fict|"
    r"vs\.?\s*(?:goku|naruto|batman|superman|voldemort|pikachu)"
    r")",
    re.I,
)

_FICTION_FIXTURE = re.compile(
    r"\b[\wÀ-ÿ.''-]{2,}\s+(?:x|vs\.?|versus)\s+[\wÀ-ÿ.''-]{2,}\b",
    re.I,
)

_IDENTITY = re.compile(
    r"^(?:"
    r"(?:qual\s+(?:e|é)\s+(?:o\s+)?seu\s+nome|seu\s+nome\??|"
    r"(?:voce|você)\s+(?:e|é)\s+a\s+aurora|"
    r"o\s+que\s+(?:voce|você)\s+faz|"
    r"o\s+que\s+sabe\s+fazer|"
    r"suas?\s+funcionalidades|"
    r"me\s+explica\s+o\s+que\s+(?:voce|você)\s+(?:e|é))"
    r")"
    r"[\s?!.,]*$",
    re.I,
)

_GENERAL_HARD = re.compile(
    r"^(?:"
    r"(?:oi|ola|olá|e\s*ai|e\s*aí|boa\s*(?:noite|tarde|dia)|bom\s+dia|"
    r"fala|hey|hi|hello)|"
    r"k{3,}|"
    r"(?:ah\s+ta|ah\s+tá)(?:[,\s]+genial)?|"
    r"aff+|tanto\s+faz"
    r")"
    r"[\s?!.,]*$",
    re.I,
)

_REAL_TEAM_HINTS = frozenset(
    {
        "flamengo",
        "palmeiras",
        "corinthians",
        "santos",
        "botafogo",
        "fluminense",
        "sao paulo",
        "grêmio",
        "gremio",
        "internacional",
        "atletico",
        "atlético",
        "barcelona",
        "real madrid",
        "liverpool",
        "chelsea",
        "arsenal",
        "bayern",
        "juventus",
        "milan",
        "inter",
        "psg",
        "argentina",
        "brasil",
        "brazil",
        "espanha",
        "portugal",
        "franca",
        "frança",
        "alemanha",
        "italia",
        "itália",
        "england",
        "inglaterra",
    }
)


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


def _blob(ctx: dict[str, Any]) -> dict[str, Any]:
    b = ctx.get(CTX_KEY)
    if not isinstance(b, dict):
        b = {"counters": {}, "last_reset_reason": None, "reset_this_turn": False}
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


def _looks_real_sport_fixture(folded: str) -> bool:
    if not _FICTION_FIXTURE.search(folded):
        return False
    if _FICTION_RE.search(folded):
        return False
    # at least one side looks like a known team token
    parts = re.split(r"\s+(?:x|vs\.?|versus)\s+", folded, maxsplit=1)
    if len(parts) != 2:
        return False
    a, b = parts[0].strip(), parts[1].strip()
    return a in _REAL_TEAM_HINTS or b in _REAL_TEAM_HINTS or any(
        t in a or t in b for t in _REAL_TEAM_HINTS if " " not in t
    )


def is_fiction_topic(message: str | None) -> bool:
    """Detect fiction topics / fictional matchups / anime-character priming."""
    folded = _fold(message or "")
    if not folded:
        return False
    if _FICTION_RE.search(folded):
        return True
    # Bare fictional names used as openers
    bare = folded.rstrip("?!.,")
    if bare in {
        "naruto",
        "goku",
        "batman",
        "superman",
        "voldemort",
        "pikachu",
        "luffy",
        "saitama",
        "thanos",
    }:
        return True
    return False


def is_identity_hard_jump(message: str | None) -> bool:
    return bool(_IDENTITY.match(_fold(message or "")))


def is_general_hard_jump(message: str | None) -> bool:
    folded = _fold(message or "")
    if not folded:
        return False
    if _GENERAL_HARD.match(folded):
        return True
    if re.fullmatch(r"k{3,}", folded):
        return True
    return False


def _has_residual_sport_context(ctx: dict[str, Any] | None) -> bool:
    if not isinstance(ctx, dict):
        return False
    if isinstance(ctx.get("last_match"), str) and ctx["last_match"].strip():
        return True
    cont = ctx.get("conversation_continuity")
    if isinstance(cont, dict) and cont.get("active"):
        return True
    try:
        from src.conversation.sport_continuity_guard import sport_anchor_active

        if sport_anchor_active(ctx):
            return True
    except Exception:
        pass
    try:
        from src.conversation.ownership_stability import owner_lock_active

        if owner_lock_active(ctx):
            return True
    except Exception:
        pass
    sm = ctx.get("short_conversation_memory")
    if isinstance(sm, dict) and (sm.get("last_fixture") or sm.get("last_team")):
        return True
    return False


def _is_protected_sport_fu(message: str | None, ctx: dict[str, Any] | None) -> bool:
    """Never hard-reset short sport FUs while a valid sport frame exists."""
    if not _has_residual_sport_context(ctx):
        return False
    if is_fiction_topic(message) or is_identity_hard_jump(message):
        return False
    try:
        from src.conversation.sport_continuity_guard import is_sport_short_followup

        if is_sport_short_followup(message):
            return True
    except Exception:
        pass
    folded = _fold(message or "")
    if _looks_real_sport_fixture(folded):
        # Real fixture replace — engines re-arm; do not wipe as "hard jump"
        return True
    return False


def is_hard_context_jump(message: str | None, ctx: dict[str, Any] | None) -> bool:
    """
    Hard jump into fiction (full reset) or identity after sport residue
    (partial reset — keeps sport_anchor TTL for A.18 digress return).
    Greetings / kkkk alone are NOT hard jumps (A.18 soft digress).
    """
    if _is_protected_sport_fu(message, ctx):
        return False
    if is_fiction_topic(message):
        return True
    if not _has_residual_sport_context(ctx):
        return False
    if is_identity_hard_jump(message):
        return True
    return False


def hard_context_reset(
    ctx: dict[str, Any] | None,
    *,
    reason: str = "hard_context_jump",
    expire_sport_anchor: bool = True,
) -> bool:
    """
    Residual release. Fiction → full wipe including sport_anchor.
    Identity digress → continuity/lock/last_match wipe, keep sport_anchor
    so A.18 short-FU return after soft digress still works.
    """
    if not isinstance(ctx, dict):
        return False
    released = False

    try:
        cont = ctx.get("conversation_continuity")
        if isinstance(cont, dict) and (
            cont.get("active") or cont.get("last_fixture") or cont.get("last_team")
        ):
            cont["active"] = False
            cont["turns_left"] = 0
            cont["mode"] = f"hard_reset:{reason}"
            cont["last_fixture"] = None
            cont["last_team"] = None
            ctx["conversation_continuity"] = cont
            released = True
    except Exception:
        pass

    if expire_sport_anchor:
        try:
            from src.conversation.sport_continuity_guard import (
                expire_sport_anchor as _expire,
                sport_anchor_active,
            )

            if sport_anchor_active(ctx):
                _expire(ctx, reason=f"a22:{reason}")
                released = True
            else:
                blob = ctx.get("sport_continuity_guard")
                if isinstance(blob, dict) and isinstance(blob.get("anchor"), dict):
                    blob["anchor"]["active"] = False
                    blob["anchor"]["turns_left"] = 0
                    blob["anchor"]["fixture"] = None
                    blob["anchor"]["teams"] = []
        except Exception:
            pass

    try:
        from src.conversation.ownership_stability import (
            owner_lock_active,
            release_owner_lock,
        )

        if owner_lock_active(ctx):
            release_owner_lock(ctx, reason=f"a22_hard_reset:{reason}")
            released = True
    except Exception:
        pass

    try:
        if ctx.get("last_match"):
            ctx.pop("last_match", None)
            released = True
        ctx.pop("last_intent", None)
    except Exception:
        pass

    try:
        sm = ctx.get("short_conversation_memory")
        if isinstance(sm, dict) and (
            sm.get("last_fixture") or sm.get("last_team") or sm.get("last_match")
        ):
            sm["last_fixture"] = None
            sm["last_team"] = None
            sm.pop("last_match", None)
            ctx["short_conversation_memory"] = sm
            released = True
    except Exception:
        pass

    # Clear A.20 pending priming without changing its detector
    try:
        acg = ctx.get("ambiguous_context_guard")
        if isinstance(acg, dict) and (
            acg.get("pending_clarify") or acg.get("bootstrap_blocked")
        ):
            # Fiction wipe pending; identity digress keeps clarify state alone
            if expire_sport_anchor:
                acg["pending_clarify"] = False
                acg["bootstrap_blocked"] = False
                released = True
    except Exception:
        pass

    try:
        # Only skip sport re-bootstrap on FULL fiction resets
        if expire_sport_anchor:
            ctx["fiction_context_hard_reset"] = True
        ctx["sport_continuity_block_ga"] = False
        ctx["ownership_stability_block_ga"] = False
    except Exception:
        pass

    blob = _blob(ctx)
    blob["reset_this_turn"] = bool(expire_sport_anchor)
    blob["last_reset_reason"] = reason
    bump(ctx, "hard_context_reset")
    if released:
        bump(ctx, "residual_context_released")
        bump(ctx, "wrong_context_prevented")
    logger.warning(
        "[AUDIT] FictionJumpGuard: HARD_RESET reason=%s full=%s released=%s",
        reason,
        expire_sport_anchor,
        released,
    )
    return released


def process_turn_start(
    message: str,
    ctx: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """
    Early turn hook (before A.20 / continuity / OS).
    Performs hard reset on fiction / hard jumps. Does not claim the turn.
    """
    if not isinstance(ctx, dict):
        return None
    try:
        blob = _blob(ctx)
        blob["reset_this_turn"] = False
        ctx.pop("fiction_context_hard_reset", None)

        if _is_protected_sport_fu(message, ctx):
            return None

        fiction = is_fiction_topic(message)
        hard = is_hard_context_jump(message, ctx)
        if not fiction and not hard:
            return None

        had_residual = _has_residual_sport_context(ctx)
        if fiction:
            bump(ctx, "fiction_detected")
            bump(ctx, "hard_context_jump")
            hard_context_reset(ctx, reason="fiction", expire_sport_anchor=True)
            return None

        if hard and is_identity_hard_jump(message):
            # Partial: release sticky continuity/lock, keep sport_anchor for A.18
            bump(ctx, "hard_context_jump")
            hard_context_reset(
                ctx, reason="identity_hard_jump", expire_sport_anchor=False
            )
        return None
    except Exception as exc:
        logger.warning("fiction_context_jump process_turn_start fail-open: %s", exc)
        return None


def should_skip_sport_bootstrap(ctx: dict[str, Any] | None) -> bool:
    """Router helper: after hard reset, do not re-arm sport notes this turn."""
    if not isinstance(ctx, dict):
        return False
    if ctx.get("fiction_context_hard_reset"):
        return True
    blob = ctx.get(CTX_KEY)
    return isinstance(blob, dict) and bool(blob.get("reset_this_turn"))


def stamp_payload_observability(
    payload: dict[str, Any] | None,
    ctx: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(payload, dict) or not isinstance(ctx, dict):
        return payload
    try:
        ents = dict(payload.get("entities") or {})
        ents["fiction_jump_guard_counters"] = get_guard_counters(ctx)
        ents["fiction_hard_reset"] = bool(ctx.get("fiction_context_hard_reset"))
        if is_fiction_topic(str(ctx.get("raw_user_message") or "")):
            ents["fiction_topic"] = True
        payload["entities"] = ents
    except Exception:
        pass
    return payload


def note_after_response(
    ctx: dict[str, Any] | None,
    message: str,
    payload: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """
    If this turn was fiction, scrub any sport priming the pipeline may have
    written (without changing A.18/A.20 internals).
    """
    if not isinstance(ctx, dict):
        return payload
    try:
        if is_fiction_topic(message) or ctx.get("fiction_context_hard_reset"):
            # Post-response scrub so next turn cannot inherit fiction-as-fixture
            if ctx.get("last_match") and is_fiction_topic(str(ctx.get("last_match"))):
                ctx.pop("last_match", None)
            if is_fiction_topic(message):
                ctx.pop("last_match", None)
                sm = ctx.get("short_conversation_memory")
                if isinstance(sm, dict):
                    sm["last_fixture"] = None
                    sm["last_team"] = None
                cont = ctx.get("conversation_continuity")
                if isinstance(cont, dict):
                    cont["active"] = False
                    cont["turns_left"] = 0
                    cont["last_fixture"] = None
            payload = stamp_payload_observability(payload, ctx)
    except Exception as exc:
        logger.warning("fiction_context_jump note_after fail-open: %s", exc)
    return payload
