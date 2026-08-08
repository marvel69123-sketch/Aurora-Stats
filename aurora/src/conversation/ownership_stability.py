"""
8.4-A.15 / 8.4-A.16 — Conversation Ownership Stability + Release.

Status: FROZEN (AEP P0 stabilization closed — do not patch without P1 redesign).

Owner lock + short-followup guard + steal confidence + loop guard
+ release conditions / claim cooldown / anti-reclaim / transition decay.
Conversation-layer only. Never invents match facts/odds.
Fail-open.
"""

from __future__ import annotations

import logging
import re
import time
import unicodedata
from typing import Any

logger = logging.getLogger(__name__)

CTX_LOCK = "ownership_stability"
OWNER_LOCK_TTL_SEC = 75.0  # 8.4-A.16 — shorter wall-clock TTL
OWNER_LOCK_MAX_TURNS = 5  # turn-based TTL (anti sticky)
MAX_CONSECUTIVE_CLAIMS = 4  # then must release unless strong sport FU
CLAIM_COOLDOWN_TURNS = 2
STEAL_CONFIDENCE_MIN = 0.92  # only allow GA steal above this when contested
TRANSITION_DECAY_PER_CLAIM = 0.12  # score penalty per consecutive reclaim

# Short continuity candidates that must prefer prior SPORT owner
_CONTINUITY_FU = re.compile(
    r"^(?:"
    r"(?:e\s+)?(?:a\s+|o\s+|as\s+|os\s+)?"
    r"(?:pressao|pressão|xg|kelly|edge|stake|value|momentum|odds?|odd|"
    r"estatisticas?|estatísticas?|mercados?|placar|favorito|pesquisa|"
    r"calendario|calendário|agenda|probabilidade|confianca|confiança|"
    r"criterio\s+de\s+kelly|critério\s+de\s+kelly)"
    r"|"
    r"e\s+(?:dele|dela|do\s+outro|da\s+outra|esse|essa|desse|dessa|ele|ela|agora|ai|aí)"
    r"|"
    r"(?:e\s+)?(?:o\s+)?outro"
    r"|"
    r"(?:mais\s+detalhes|todos\s+os\s+mercados|explica\s+melhor|e\s+agora)"
    r"|"
    r"(?:markets?|pressure|score|stats?|xg)"
    r")"
    r"(?:\s+\w+){0,3}"
    r"\s*[?!]*$",
    re.I,
)

# Messages that MUST release sport ownership (no overclaim)
_RELEASE_MSG = re.compile(
    r"^(?:"
    r"(?:oi|ola|olá|e\s*ai|e\s*aí|boa\s*(?:noite|tarde|dia)|fala|hey|hi|hello)"
    r"|"
    r"(?:voce|você)\s+e\s+a\s+aurora"
    r"|"
    r"(?:seu\s+nome|qual\s+(?:e|é)\s+(?:o\s+)?seu\s+nome)"
    r"|"
    r"(?:o\s+que\s+(?:voce|você)\s+faz|o\s+que\s+sabe\s+fazer|suas?\s+funcionalidades|"
    r"me\s+explica\s+o\s+que\s+(?:voce|você)\s+(?:e|é))"
    r"|"
    r"(?:ah\s+ta(?:[,\s]+genial)?|genial|claro\s+ne(?:\s+kkkk*)?|kkkk+|aff+|"
    r"isso\s+foi\s+inutil|pensa\s+um\s+pouco|isso\s+esta\s+errado|"
    r"preste\s+atencao|manda\s+a\s+real)"
    r"|"
    r"(?:goku\s*x\s*naruto|harry\s+potter\s*x\s*voldemort)"
    r")"
    r"[\s?!.,]*$",
    re.I,
)
_RELEASE_FRAGMENTS = (
    "ah ta",
    "ah tá",
    "claro ne",
    "claro né",
    "kkkk",
    "goku x naruto",
    "harry potter x voldemort",
    "voce e a aurora",
    "você é a aurora",
    "seu nome",
    "suas funcionalidades",
    "o que voce faz",
    "o que você faz",
    "o que sabe fazer",
)

_OBS_KEYS = (
    "owner_lock_activated",
    "owner_lock_preserved",
    "owner_steal_attempted",
    "owner_steal_blocked",
    "owner_transition_denied",
    "continuity_guard_triggered",
    "loop_guard_triggered",
    "owner_lock_ttl_expired",
    "dangerous_transition_detected",
    # 8.4-A.15b reinforcement
    "orphan_state_detected",
    "owner_claim_forced",
    "ga_block_without_claim",
    "owner_claimed_after_block",
    "dangerous_transition_after_block",
    "ownerless_transition",
    "advanced_continuity_hits",
    # 8.4-A.16 release stabilization
    "owner_reclaimed",
    "owner_lock_duration",
    "claim_repetition_count",
    "owner_release_triggered",
    "sticky_owner_detected",
)


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


def _obs(ctx: dict[str, Any]) -> dict[str, Any]:
    blob = ctx.get(CTX_LOCK)
    if not isinstance(blob, dict):
        blob = {"counters": {}, "history": []}
        ctx[CTX_LOCK] = blob
    counters = blob.get("counters")
    if not isinstance(counters, dict):
        counters = {}
        blob["counters"] = counters
    for k in _OBS_KEYS:
        counters.setdefault(k, 0)
    if not isinstance(blob.get("history"), list):
        blob["history"] = []
    return blob


def bump(ctx: dict[str, Any] | None, key: str, *, n: int = 1) -> None:
    if not isinstance(ctx, dict) or key not in _OBS_KEYS:
        return
    try:
        obs = _obs(ctx)
        obs["counters"][key] = int(obs["counters"].get(key) or 0) + n
    except Exception:
        pass


def get_stability_counters(ctx: dict[str, Any] | None) -> dict[str, int]:
    if not isinstance(ctx, dict):
        return {k: 0 for k in _OBS_KEYS}
    return dict(_obs(ctx).get("counters") or {})


def _turn_index(ctx: dict[str, Any]) -> int:
    obs = _obs(ctx)
    return int(obs.get("turn_index") or 0)


def _bump_turn(ctx: dict[str, Any]) -> int:
    obs = _obs(ctx)
    n = int(obs.get("turn_index") or 0) + 1
    obs["turn_index"] = n
    return n


def _sport_anchor(ctx: dict[str, Any] | None) -> tuple[str | None, str | None]:
    """Return (team, fixture) from session memory — never invents."""
    if not isinstance(ctx, dict):
        return None, None
    team = None
    fixture = None
    try:
        from src.conversation.conversation_continuity import (
            _fixture_from_ctx,
            _team_from_ctx,
        )

        team = _team_from_ctx(ctx)
        fixture = _fixture_from_ctx(ctx) or ctx.get("last_match")
    except Exception:
        fixture = ctx.get("last_match") if isinstance(ctx.get("last_match"), str) else None
    if isinstance(team, str) and not team.strip():
        team = None
    if isinstance(fixture, str) and not fixture.strip():
        fixture = None
    return (
        team if isinstance(team, str) else None,
        fixture if isinstance(fixture, str) else None,
    )


def is_release_message(message: str | None) -> bool:
    folded = _fold(message or "")
    if not folded:
        return False
    if _RELEASE_MSG.match(folded):
        return True
    if folded in {"aff", "kkk", "kkkk", "ok", "blz", "tanto faz"}:
        return True
    # Phrase fragments (sarcasm / identity / fiction) anywhere in short messages
    if len(folded.split()) <= 8 and any(f in folded for f in _RELEASE_FRAGMENTS):
        return True
    return False


def strong_sport_followup(message: str | None, ctx: dict[str, Any] | None) -> bool:
    """True continuity FU with a real sport anchor — safe to (re)claim."""
    if not is_continuity_followup_candidate(message):
        return False
    team, fixture = _sport_anchor(ctx)
    if not team and not fixture:
        return False
    cont = ctx.get("conversation_continuity") if isinstance(ctx, dict) else None
    if isinstance(cont, dict) and cont.get("active") and int(cont.get("turns_left") or 0) > 0:
        return True
    return bool(team or fixture)


def release_owner_lock(
    ctx: dict[str, Any] | None,
    *,
    reason: str = "release_conditions",
) -> None:
    if not isinstance(ctx, dict):
        return
    obs = _obs(ctx)
    locked_at = obs.get("locked_at")
    turns_held = int(obs.get("lock_turns_held") or 0)
    if obs.get("locked_owner") or turns_held > 0:
        bump(ctx, "owner_release_triggered")
        if turns_held > 0:
            bump(ctx, "owner_lock_duration", n=turns_held)
        elif locked_at is not None:
            try:
                dur = max(1, int(time.time() - float(locked_at)))
                bump(ctx, "owner_lock_duration", n=dur)
            except (TypeError, ValueError):
                pass
    obs["locked_owner"] = None
    obs["expires_at"] = 0
    obs["lock_reason"] = f"released:{reason}"
    obs["lock_turns_held"] = 0
    obs["consecutive_claims"] = 0
    obs["cooldown_until_turn"] = _turn_index(ctx) + CLAIM_COOLDOWN_TURNS
    obs["decay_penalty"] = 0.0
    logger.warning("[AUDIT] OwnerLock: RELEASED reason=%s", reason)


def claim_cooldown_active(ctx: dict[str, Any] | None) -> bool:
    if not isinstance(ctx, dict):
        return False
    obs = _obs(ctx)
    until = int(obs.get("cooldown_until_turn") or 0)
    return _turn_index(ctx) < until


def repeated_claim_detector(ctx: dict[str, Any] | None, *, record: bool = True) -> bool:
    """True when ownership_stability has reclaimed too many turns in a row."""
    if not isinstance(ctx, dict):
        return False
    obs = _obs(ctx)
    n = int(obs.get("consecutive_claims") or 0)
    if n >= MAX_CONSECUTIVE_CLAIMS:
        if record:
            bump(ctx, "claim_repetition_count")
            bump(ctx, "sticky_owner_detected")
        return True
    return False


def apply_transition_decay(ctx: dict[str, Any] | None) -> float:
    if not isinstance(ctx, dict):
        return 0.0
    obs = _obs(ctx)
    consec = int(obs.get("consecutive_claims") or 0)
    penalty = min(0.75, consec * TRANSITION_DECAY_PER_CLAIM)
    obs["decay_penalty"] = penalty
    return penalty


def anti_reclaim_guard(
    ctx: dict[str, Any] | None,
    message: str | None,
) -> bool:
    """
    True → block reclaim this turn.
    Allows reclaim only for strong sport follow-ups with anchor.
    """
    if not isinstance(ctx, dict):
        return False
    if strong_sport_followup(message, ctx):
        return False
    if claim_cooldown_active(ctx):
        return True
    if repeated_claim_detector(ctx, record=False):
        return True
    obs = _obs(ctx)
    if int(obs.get("lock_turns_held") or 0) >= OWNER_LOCK_MAX_TURNS:
        return True
    return False


def owner_release_conditions(
    ctx: dict[str, Any] | None,
    message: str | None,
) -> str | None:
    """
    Return release reason if ownership should drop; else None.
    """
    if not isinstance(ctx, dict):
        return None
    if is_release_message(message):
        return "non_sport_message"
    if strong_sport_followup(message, ctx):
        return None
    if repeated_claim_detector(ctx, record=False):
        return "repeated_claim"
    if claim_cooldown_active(ctx):
        return "claim_cooldown"
    if int(_obs(ctx).get("lock_turns_held") or 0) >= OWNER_LOCK_MAX_TURNS:
        return "max_lock_turns"
    team, fixture = _sport_anchor(ctx)
    if not team and not fixture and owner_lock_active(ctx):
        if not is_continuity_followup_candidate(message):
            return "no_sport_anchor"
    return None


def is_continuity_followup_candidate(message: str | None) -> bool:
    """Short follow-up / pronoun / advanced / research-ish continuity ask."""
    raw = str(message or "").strip()
    if not raw:
        return False
    folded = _fold(raw)
    if len(folded.split()) > 8:
        return False
    try:
        from src.conversation.pronoun_continuity import is_pronoun_followup

        if is_pronoun_followup(raw):
            return True
    except Exception:
        pass
    try:
        from src.conversation.advanced_football_continuity import (
            is_advanced_football_followup,
        )

        if is_advanced_football_followup(raw):
            return True
    except Exception:
        pass
    try:
        from src.conversation.conversation_continuity import _is_short_followup

        if _is_short_followup(raw):
            return True
    except Exception:
        pass
    return bool(_CONTINUITY_FU.match(folded))


def has_active_sport_context(ctx: dict[str, Any] | None) -> bool:
    if not isinstance(ctx, dict):
        return False
    # Explicit owner lock
    lock = _obs(ctx)
    if lock.get("locked_owner") == "SPORT" and _lock_ttl_ok(lock):
        return True
    # Continuity window
    cont = ctx.get("conversation_continuity")
    if isinstance(cont, dict) and cont.get("active") and int(cont.get("turns_left") or 0) > 0:
        return True
    # Session sport memory
    if isinstance(ctx.get("last_match"), str) and ctx["last_match"].strip():
        return True
    if isinstance(ctx.get("last_analysis"), dict) and ctx["last_analysis"]:
        return True
    pm = ctx.get("pronoun_continuity")
    if isinstance(pm, dict) and (
        pm.get("last_fixture") or pm.get("last_team") or pm.get("focus_team")
    ):
        return True
    sm = ctx.get("short_conversation_memory")
    if isinstance(sm, dict) and (sm.get("last_fixture") or sm.get("last_team")):
        return True
    cs = ctx.get("conversation_state")
    if isinstance(cs, dict) and cs.get("active_fixture"):
        return True
    return False


def _lock_ttl_ok(lock: dict[str, Any]) -> bool:
    exp = lock.get("expires_at")
    if exp is None:
        return bool(lock.get("locked_owner"))
    try:
        return float(exp) > time.time()
    except (TypeError, ValueError):
        return False


def activate_owner_lock(
    ctx: dict[str, Any] | None,
    *,
    owner: str = "SPORT",
    ttl_sec: float = OWNER_LOCK_TTL_SEC,
    reason: str = "sport_session",
    refresh_ttl: bool = True,
) -> None:
    if not isinstance(ctx, dict):
        return
    # 8.4-A.20 — no context lock while ambiguous / clarification pending
    try:
        from src.conversation.ambiguous_context_guard import bootstrap_blocked

        if bootstrap_blocked(ctx, reason=reason):
            logger.warning(
                "[AUDIT] OwnerLock: BLOCKED bootstrap reason=%s", reason
            )
            return
    except Exception:
        pass
    obs = _obs(ctx)
    now = time.time()
    was = obs.get("locked_owner")
    def _inc_lock_turns() -> int:
        # Increment at most once per conversation turn
        turn = int(obs.get("turn_index") or 0)
        if obs.get("last_lock_inc_turn") == turn and turn > 0:
            return int(obs.get("lock_turns_held") or 0)
        held = int(obs.get("lock_turns_held") or 0) + 1
        obs["lock_turns_held"] = held
        obs["last_lock_inc_turn"] = turn
        return held

    # 8.4-A.16 — do not extend sticky locks forever on soft holds
    if was == owner and reason in {"owner_lock_hold", "continuity_guard", "forced_after_ga_block"}:
        held = _inc_lock_turns()
        if held > OWNER_LOCK_MAX_TURNS:
            bump(ctx, "sticky_owner_detected")
            release_owner_lock(ctx, reason="sticky_max_turns")
            return
        if not refresh_ttl:
            bump(ctx, "owner_lock_preserved")
            return
        # Soft refresh: only top up a fraction of TTL
        try:
            cur_exp = float(obs.get("expires_at") or 0)
            obs["expires_at"] = max(cur_exp, now + max(5.0, float(ttl_sec) * 0.35))
        except (TypeError, ValueError):
            obs["expires_at"] = now + max(5.0, float(ttl_sec) * 0.35)
        bump(ctx, "owner_lock_preserved")
        return

    obs["locked_owner"] = owner
    obs["locked_at"] = now
    obs["expires_at"] = now + max(5.0, float(ttl_sec))
    obs["lock_reason"] = reason
    if was and was != owner:
        bump(ctx, "owner_reclaimed")
    if was != owner:
        bump(ctx, "owner_lock_activated")
        obs["lock_turns_held"] = 1
        obs["last_lock_inc_turn"] = int(obs.get("turn_index") or 0)
    else:
        _inc_lock_turns()
        bump(ctx, "owner_lock_preserved")
    logger.warning(
        "[AUDIT] OwnerLock: ACTIVE owner=%s ttl=%ss reason=%s turns=%s",
        owner,
        ttl_sec,
        reason,
        obs.get("lock_turns_held"),
    )


def refresh_owner_lock(ctx: dict[str, Any] | None, *, ttl_sec: float = OWNER_LOCK_TTL_SEC) -> None:
    if not isinstance(ctx, dict):
        return
    obs = _obs(ctx)
    if obs.get("locked_owner") == "SPORT":
        if int(obs.get("lock_turns_held") or 0) >= OWNER_LOCK_MAX_TURNS:
            release_owner_lock(ctx, reason="refresh_blocked_max_turns")
            return
        obs["expires_at"] = time.time() + max(5.0, float(ttl_sec) * 0.5)
        bump(ctx, "owner_lock_preserved")


def owner_lock_active(ctx: dict[str, Any] | None) -> bool:
    if not isinstance(ctx, dict):
        return False
    obs = _obs(ctx)
    if obs.get("locked_owner") != "SPORT":
        return False
    if int(obs.get("lock_turns_held") or 0) > OWNER_LOCK_MAX_TURNS:
        bump(ctx, "sticky_owner_detected")
        bump(ctx, "owner_lock_ttl_expired")
        release_owner_lock(ctx, reason="turn_ttl_expired")
        return False
    if _lock_ttl_ok(obs):
        return True
    bump(ctx, "owner_lock_ttl_expired")
    release_owner_lock(ctx, reason="wall_ttl_expired")
    return False


def note_transition(
    ctx: dict[str, Any] | None,
    *,
    from_bucket: str,
    to_bucket: str,
) -> bool:
    """
    Record transition; return True if transition should be DENIED (loop guard).
    """
    if not isinstance(ctx, dict):
        return False
    obs = _obs(ctx)
    hist: list = obs["history"]
    edge = f"{from_bucket}->{to_bucket}"
    hist.append(edge)
    if len(hist) > 12:
        del hist[:-12]

    dangerous = {
        "SPORT->GA",
        "SPORT->LOOP",
        "GA->LOOP",
        "LOOP->GA",
        "HCE->LOOP",
    }
    if edge in dangerous:
        bump(ctx, "dangerous_transition_detected")

    # Detect short cycles SPORT->LOOP->SPORT, SPORT->GA->LOOP, GA->LOOP->GA
    if len(hist) >= 2:
        a, b = hist[-2], hist[-1]
        cycle_pairs = {
            ("SPORT->LOOP", "LOOP->SPORT"),
            ("SPORT->GA", "GA->LOOP"),
            ("GA->LOOP", "LOOP->GA"),
            ("LOOP->SPORT", "SPORT->LOOP"),
            ("SPORT->LOOP", "LOOP->GA"),
        }
        if (a, b) in cycle_pairs:
            bump(ctx, "loop_guard_triggered")
            return True
    if len(hist) >= 3:
        tri = tuple(hist[-3:])
        if tri in {
            ("SPORT->GA", "GA->LOOP", "LOOP->SPORT"),
            ("SPORT->LOOP", "LOOP->SPORT", "SPORT->LOOP"),
            ("GA->LOOP", "LOOP->GA", "GA->LOOP"),
        }:
            bump(ctx, "loop_guard_triggered")
            return True
    return False


def owner_steal_allowed(
    *,
    proposed_owner: str,
    current_locked: bool,
    master_confidence: float | None,
    continuity_candidate: bool,
) -> bool:
    """
    Steal to GA only when confidence is very high AND not a continuity candidate
    AND no active sport owner lock.
    """
    if proposed_owner not in {"GA", "general", "general_chat"}:
        return True
    if continuity_candidate:
        return False
    if current_locked:
        return False
    conf = float(master_confidence or 0.0)
    return conf >= STEAL_CONFIDENCE_MIN


def _ensure_continuity_armed(ctx: dict[str, Any]) -> bool:
    """Arm continuity from session sport memory so short FU resolvers can claim."""
    try:
        from src.conversation.conversation_continuity import (
            _arm,
            _fixture_from_ctx,
            _team_from_ctx,
            get_continuity,
        )

        cont = get_continuity(ctx)
        if cont.get("active") and int(cont.get("turns_left") or 0) > 0:
            return True
        team = _team_from_ctx(ctx)
        fixture = _fixture_from_ctx(ctx) or ctx.get("last_match")
        if not team and not fixture:
            return False
        if isinstance(fixture, str) and " x " in fixture.lower() and not team:
            team = fixture.split(" x ")[0].strip()
        _arm(
            ctx,
            mode="owner_lock_sport",
            team=team if isinstance(team, str) else None,
            fixture=fixture if isinstance(fixture, str) else None,
            turns=4,
        )
        return True
    except Exception as exc:
        logger.warning("ownership_stability: arm continuity fail-open (%s)", exc)
        return False


def compute_continuity_stamp(
    ctx: dict[str, Any] | None,
    message: str | None = None,
) -> dict[str, Any]:
    """
    8.4-A.15b — explicit continuity score + signals for ownership decisions.
    Never invents fixture facts; only reads session memory.
    """
    signals: dict[str, Any] = {
        "last_owner": None,
        "fixture_id": None,
        "resolved_fixture": None,
        "resolved_team": None,
        "pronouns": False,
        "short_followups": False,
        "recent_entities": False,
        "continuity_ttl": 0,
        "advanced_continuity_hits": 0,
        "owner_lock_active": False,
        "sport_context": False,
    }
    score = 0.0
    if not isinstance(ctx, dict):
        return {"continuity_score": 0.0, "continuity_signals": signals}

    last_owner = ctx.get("last_turn_owner") or ctx.get("last_response_owner")
    if isinstance(last_owner, str) and last_owner.strip():
        signals["last_owner"] = last_owner.strip()
        if last_owner.upper() in {"SPORT", "SPORT"} or last_owner in {
            "conversation_continuity",
            "pronoun_continuity",
            "advanced_football_continuity",
            "ownership_stability",
            "partial_analysis",
        }:
            score += 0.18

    lock = _obs(ctx)
    if owner_lock_active(ctx):
        signals["owner_lock_active"] = True
        score += 0.2
        try:
            ttl = max(0.0, float(lock.get("expires_at") or 0) - time.time())
            signals["continuity_ttl"] = int(ttl)
            if ttl > 0:
                score += 0.08
        except (TypeError, ValueError):
            pass

    cont = ctx.get("conversation_continuity")
    if isinstance(cont, dict) and cont.get("active"):
        left = int(cont.get("turns_left") or 0)
        signals["continuity_ttl"] = max(int(signals["continuity_ttl"] or 0), left)
        if left > 0:
            score += 0.15

    team = None
    fixture = None
    try:
        from src.conversation.conversation_continuity import (
            _fixture_from_ctx,
            _team_from_ctx,
        )

        team = _team_from_ctx(ctx)
        fixture = _fixture_from_ctx(ctx) or ctx.get("last_match")
    except Exception:
        fixture = ctx.get("last_match") if isinstance(ctx.get("last_match"), str) else None

    if isinstance(fixture, str) and fixture.strip():
        signals["resolved_fixture"] = fixture.strip()
        signals["fixture_id"] = fixture.strip().lower()[:120]
        score += 0.18
    if isinstance(team, str) and team.strip():
        signals["resolved_team"] = team.strip()
        score += 0.12

    pm = ctx.get("pronoun_continuity")
    if isinstance(pm, dict) and (
        pm.get("last_fixture") or pm.get("last_team") or pm.get("focus_team")
    ):
        signals["recent_entities"] = True
        score += 0.08
    sm = ctx.get("short_conversation_memory")
    if isinstance(sm, dict) and (sm.get("last_fixture") or sm.get("last_team")):
        signals["recent_entities"] = True
        score += 0.05

    if is_continuity_followup_candidate(message):
        signals["short_followups"] = True
        score += 0.12
    try:
        from src.conversation.pronoun_continuity import is_pronoun_followup

        if is_pronoun_followup(message):
            signals["pronouns"] = True
            score += 0.1
    except Exception:
        pass
    try:
        from src.conversation.advanced_football_continuity import (
            is_advanced_football_followup,
        )

        if is_advanced_football_followup(message):
            hits = int(lock.get("advanced_hits") or 0) + 1
            lock["advanced_hits"] = hits
            signals["advanced_continuity_hits"] = hits
            bump(ctx, "advanced_continuity_hits")
            score += 0.12
    except Exception:
        pass

    signals["sport_context"] = has_active_sport_context(ctx)
    if signals["sport_context"]:
        score += 0.1

    # 8.4-A.16 — transition decay on sticky reclaim streaks
    penalty = apply_transition_decay(ctx)
    if penalty:
        score = max(0.0, score - penalty)
        signals["transition_decay"] = penalty

    score = round(min(1.0, max(0.0, score)), 3)
    return {"continuity_score": score, "continuity_signals": signals}


def force_owner_claim_after_ga_block(
    message: str,
    ctx: dict[str, Any] | None,
    *,
    brain: dict[str, Any] | None = None,
    existing_payload: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """
    8.4-A.15b/16 — AFTER GA block, claim only when sport continuity is real.
    Priority: current_owner → previous_owner → continuity_owner → hold with anchor.
    8.4-A.16: never invent a SPORT hold without fixture/team (prevents sticky overclaim).
    Returns None when release conditions say ownership must drop.
    """
    release_reason = owner_release_conditions(ctx, message)
    if release_reason:
        release_owner_lock(ctx, reason=f"force_block:{release_reason}")
        return None
    _team, _fixture = _sport_anchor(ctx)
    if not strong_sport_followup(message, ctx) and not _team and not _fixture:
        release_owner_lock(ctx, reason="force_block:no_anchor")
        return None

    if isinstance(existing_payload, dict):
        ents = existing_payload.get("entities") or {}
        if ents.get("turn_owner") and ents.get("response_owner"):
            # Do not re-stamp non-sport owners into ownership_stability
            if str(ents.get("response_owner")) != "ownership_stability" and not ents.get(
                "continuity_followup"
            ):
                return existing_payload
            stamped = _stamp_stability(
                existing_payload,
                guard=str(ents.get("ownership_stability_guard") or "preserved"),
                ctx=ctx,
                claim_source="current_owner",
            )
            bump(ctx, "owner_claimed_after_block")
            return stamped

    # Try normal claim path first
    claimed = try_ownership_stability_claim(message, ctx, brain=brain)
    if isinstance(claimed, dict):
        bump(ctx, "owner_claim_forced")
        bump(ctx, "owner_claimed_after_block")
        return _stamp_stability(
            claimed,
            guard="forced_after_ga_block",
            ctx=ctx,
            claim_source="continuity_owner",
        )

    # previous_owner preference — only with real sport anchor
    prev = None
    if isinstance(ctx, dict):
        prev = ctx.get("last_turn_owner") or ctx.get("last_response_owner")
    hold = _build_hold_payload(message, ctx if isinstance(ctx, dict) else {})
    if hold is None:
        # 8.4-A.16 — no anchor ⇒ release (do not emit infinite soft hold)
        bump(ctx, "orphan_state_detected")
        release_owner_lock(ctx, reason="force_block:hold_without_anchor")
        return None

    source = "previous_owner" if prev else "continuity_owner"
    bump(ctx, "owner_claim_forced")
    bump(ctx, "owner_claimed_after_block")
    return _stamp_stability(
        hold,
        guard="forced_after_ga_block",
        ctx=ctx,
        claim_source=source,
    )


def try_nonsticky_release_handoff(
    message: str,
    ctx: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """
    8.4-A.16 — for sarcasm/fiction release turns, answer once without SPORT lock
    and without the sticky GA loop template. Identity/capabilities return None
    so HCE/MasterIntent can own the turn.
    """
    if not isinstance(ctx, dict) or not is_release_message(message):
        return None
    release_owner_lock(ctx, reason="nonsticky_handoff")
    folded = _fold(message)
    # Identity / capabilities / greetings → do not intercept
    if any(
        k in folded
        for k in (
            "aurora",
            "seu nome",
            "funcionalidade",
            "o que voce faz",
            "o que sabe fazer",
            "boa noite",
            "boa tarde",
            "boa dia",
            "e ai",
            "ola",
            "oi",
        )
    ):
        return None
    # Sarcasm / fiction / pure frustration — one-shot non-sport ack
    text = (
        "Beleza — pra eu analisar de verdade, me passa um jogo ou time real "
        "(ex.: Argentina x Brasil, Flamengo, Liverpool x Chelsea)."
    )
    return {
        "intent": "small_talk",
        "entities": {
            "turn_owner": "GA",
            "response_owner": "natural_conversation",
            "ownership_stability": False,
            "owner_lock": False,
            "rewrite_locked": False,
            "owner_release_triggered": True,
            "nonsticky_handoff": True,
        },
        "executive_summary": text,
        "final_recommendation": text,
        "aurora_version": "Aurora v3.3.2-beta",
    }


def try_ownership_stability_claim(
    message: str,
    ctx: dict[str, Any] | None,
    *,
    brain: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """
    Before MasterIntent/GA: if sport context + continuity FU, claim SPORT
    via existing continuity layers (priority: continuity → pronoun → advanced).
    8.4-A.16 — release / cooldown / anti-reclaim before claiming.
    """
    if not isinstance(ctx, dict):
        return None
    try:
        # PATCH-001 R3 — no ownership lock before entity validation on
        # comparison / long fresh sport questions
        try:
            from src.conversation.entity_safety import (
                looks_like_comparison,
                ownership_lock_permitted,
            )

            if looks_like_comparison(message) or not ownership_lock_permitted(
                message, ctx
            ):
                if looks_like_comparison(message) and not is_continuity_followup_candidate(
                    message
                ):
                    logger.warning(
                        "[AUDIT] OwnerLock: BLOCKED pending entity validation "
                        "msg_prefix=%r",
                        (message or "")[:48],
                    )
                    return None
        except Exception:
            pass
        # 8.4-A.18 — never OS-claim digressions / identity / research openers
        try:
            from src.conversation.sport_continuity_guard import is_non_sport_message

            if is_non_sport_message(message):
                release_owner_lock(ctx, reason="non_sport_message")
                return None
        except Exception:
            pass
        # Never claim brand-new fixture openers (let analyze_match own them)
        folded_msg = _fold(message)
        if " x " in folded_msg and len(folded_msg.split()) <= 8:
            if not is_continuity_followup_candidate(message):
                return None
        # Also block "A ou B" openers from early ownership steal
        if re.search(r"\bou\b", folded_msg) and len(folded_msg.split()) <= 10:
            if not is_continuity_followup_candidate(message):
                return None
        if folded_msg.startswith("pesquisa ") or folded_msg.startswith("me fala do "):
            release_owner_lock(ctx, reason="research_opener")
            return None
        # Release non-sport / sticky reclaim — never SPORT-overclaim these
        if is_release_message(message):
            release_owner_lock(ctx, reason="non_sport_message")
            return None
        if anti_reclaim_guard(ctx, message) and not strong_sport_followup(message, ctx):
            release_owner_lock(ctx, reason="anti_reclaim_guard")
            return None
        if repeated_claim_detector(ctx, record=False) and not strong_sport_followup(
            message, ctx
        ):
            release_owner_lock(ctx, reason="repeated_claim")
            return None

        stamp = compute_continuity_stamp(ctx, message)
        ctx["_continuity_stamp"] = stamp
        candidate = is_continuity_followup_candidate(message)
        strong = strong_sport_followup(message, ctx)
        team, fixture = _sport_anchor(ctx)
        score = float(stamp.get("continuity_score") or 0)

        # Need continuity FU + real sport anchor (no score-only overclaim)
        if not (candidate and (team or fixture)):
            return None
        if score < 0.25 and not strong:
            return None

        bump(ctx, "continuity_guard_triggered")
        if int(_obs(ctx).get("consecutive_claims") or 0) > 0:
            bump(ctx, "owner_reclaimed")

        activate_owner_lock(
            ctx,
            owner="SPORT",
            reason="continuity_guard",
            refresh_ttl=bool(strong),
        )
        _ensure_continuity_armed(ctx)

        # Priority 1 — conversation continuity short FU
        try:
            from src.conversation.conversation_continuity import (
                apply_continuity_resolve,
                try_contextual_short_followup,
            )

            apply_continuity_resolve(message, ctx)
            payload = try_contextual_short_followup(message, ctx, brain=brain)
            if isinstance(payload, dict):
                return _stamp_stability(
                    payload, guard="continuity", ctx=ctx, claim_source="continuity_owner"
                )
        except Exception as exc:
            logger.warning("ownership_stability: continuity retry skipped (%s)", exc)

        # Priority 2 — pronoun
        try:
            from src.conversation.pronoun_continuity import try_pronoun_continuity

            payload = try_pronoun_continuity(message, ctx, brain=brain)
            if isinstance(payload, dict):
                return _stamp_stability(
                    payload, guard="pronoun", ctx=ctx, claim_source="continuity_owner"
                )
        except Exception as exc:
            logger.warning("ownership_stability: pronoun retry skipped (%s)", exc)

        # Priority 3 — advanced football
        try:
            from src.conversation.advanced_football_continuity import (
                try_advanced_football_continuity,
            )

            payload = try_advanced_football_continuity(message, ctx, brain=brain)
            if isinstance(payload, dict):
                return _stamp_stability(
                    payload, guard="advanced", ctx=ctx, claim_source="continuity_owner"
                )
        except Exception as exc:
            logger.warning("ownership_stability: advanced retry skipped (%s)", exc)

        # Soft hold only for pronoun-like FUs — avoid generic hold on kelly/xg/etc.
        folded = _fold(message)
        if folded.startswith("e ") or "outro" in folded.split():
            hold = _build_hold_payload(message, ctx)
            if hold:
                return _stamp_stability(
                    hold,
                    guard="owner_lock_hold",
                    ctx=ctx,
                    claim_source="continuity_owner",
                )
        return None
    except Exception as exc:
        logger.warning("try_ownership_stability_claim fail-open: %s", exc)
        return None


def _stamp_stability(
    payload: dict[str, Any],
    *,
    guard: str,
    ctx: dict[str, Any] | None = None,
    claim_source: str | None = None,
) -> dict[str, Any]:
    out = dict(payload)
    ents = dict(out.get("entities") or {})
    stamp = {}
    if isinstance(ctx, dict):
        stamp = ctx.get("_continuity_stamp") or compute_continuity_stamp(ctx)
    elif not stamp:
        stamp = compute_continuity_stamp(ctx)
    signals = dict(stamp.get("continuity_signals") or {})

    ents["owner_lock"] = True
    ents["ownership_stability"] = True
    ents["ownership_stability_guard"] = guard
    ents["turn_owner"] = "SPORT"
    ents["rewrite_locked"] = True
    # Keep AEP detectors from flagging context_lost / GA steal on locked turns
    ents["followup_context_found"] = True
    ents["followup_before_fallback"] = True
    ents["continuity_followup"] = True
    ents.setdefault("continuity_kind", f"owner_lock_{guard}")
    # 8.4-A.15b reinforced stamp signals
    ents["continuity_score"] = stamp.get("continuity_score")
    ents["continuity_signals"] = signals
    prev_owner = signals.get("last_owner")
    if not prev_owner and isinstance(ctx, dict):
        prev_owner = ctx.get("last_turn_owner") or ctx.get("last_response_owner")
    ents["last_owner"] = prev_owner
    ents["fixture_id"] = signals.get("fixture_id")
    ents["resolved_fixture"] = (
        ents.get("followup_resolved_fixture")
        or ents.get("pronoun_fixture")
        or signals.get("resolved_fixture")
    )
    ents["resolved_team"] = (
        ents.get("followup_resolved_team")
        or ents.get("team")
        or signals.get("resolved_team")
    )
    ents["followup_resolved_fixture"] = ents.get("resolved_fixture")
    ents["followup_resolved_team"] = ents.get("resolved_team")
    if ents.get("resolved_team") and not ents.get("team"):
        ents["team"] = ents["resolved_team"]
    ents["continuity_ttl"] = signals.get("continuity_ttl")
    ents["short_followups"] = bool(signals.get("short_followups"))
    ents["recent_entities"] = bool(signals.get("recent_entities"))
    ents["advanced_continuity_hits"] = signals.get("advanced_continuity_hits") or 0
    if claim_source:
        ents["owner_claim_source"] = claim_source
        ents["owner_claimed_after_block"] = claim_source.startswith("forced") or guard.startswith(
            "forced"
        )

    if guard == "pronoun" or signals.get("pronouns"):
        ents.setdefault("pronoun_resolved", True)
        ents.setdefault("pronoun_continuity", True)
    if guard == "advanced" or int(signals.get("advanced_continuity_hits") or 0) > 0:
        ents.setdefault("advanced_fixture_reused", True)
        ents.setdefault("advanced_football_continuity", True)
    # 8.4-A.16 — preserve resolver owner; ownership_stability is the guard flag.
    # Soft holds keep response_owner=ownership_stability; resolvers keep theirs.
    _guard_owners = {
        "continuity": "conversation_continuity",
        "pronoun": "pronoun_continuity",
        "advanced": "advanced_football_continuity",
    }
    existing_owner = str(ents.get("response_owner") or "")
    if guard in _guard_owners:
        if not existing_owner or existing_owner == "ownership_stability":
            ents["response_owner"] = _guard_owners[guard]
    elif not existing_owner:
        ents["response_owner"] = "ownership_stability"
    ents["turn_owner"] = "SPORT"
    # Drop GA/loop-looking intents on continuity holds only
    if guard in {"owner_lock_hold", "forced_after_ga_block", "continuity", "pronoun", "advanced"}:
        out["intent"] = "follow_up"
    # Prevent loop-marker summaries from sticky GA templates
    summary = str(out.get("executive_summary") or "")
    low = _fold(summary)
    if any(
        m in low
        for m in (
            "entendi. posso te ajudar",
            "diz o objetivo em uma frase",
            "pode falar comigo normalmente",
            "pode reformular em uma frase",
        )
    ) or len(summary.strip()) < 12:
        team = ents.get("resolved_team") or ents.get("team") or "o jogo"
        fx = ents.get("resolved_fixture") or team
        text = (
            f"Mantendo o contexto de **{fx}**. "
            f"Pode seguir com mercados, placar, estatísticas, pressão/xG ou 'e dele?'."
        )
        out["executive_summary"] = text
        out["final_recommendation"] = text
    # Draft for late-layer restore (same mechanism as continuity)
    ents["continuity_draft"] = str(out.get("executive_summary") or "")[:2000]
    out["entities"] = ents
    return out


def _build_hold_payload(message: str, ctx: dict[str, Any]) -> dict[str, Any] | None:
    """Minimal SPORT hold — reuses ctx labels only; never invents odds."""
    try:
        from src.conversation.conversation_continuity import (
            _fixture_from_ctx,
            _team_from_ctx,
        )

        team = _team_from_ctx(ctx)
        fixture = _fixture_from_ctx(ctx) or ctx.get("last_match")
        if not team and not fixture:
            return None
        label = fixture or team
        text = (
            f"Continuando sobre **{label}**. "
            f"Pode pedir mercados, placar, estatísticas, pressão/xG ou 'e dele?' — "
            f"mantenho o contexto do jogo."
        )
        return {
            "intent": "follow_up",
            "entities": {
                "followup": True,
                "continuity_followup": True,
                "followup_before_fallback": True,
                "owner_lock": True,
                "ownership_stability": True,
                "ownership_stability_guard": "owner_lock_hold",
                "team": team,
                "followup_resolved_team": team,
                "followup_resolved_fixture": fixture,
                "turn_owner": "SPORT",
                "rewrite_locked": True,
                "response_owner": "ownership_stability",
                "show_header": False,
            },
            "executive_summary": text,
            "final_recommendation": text,
            "knowledge_notes": [
                f"8.4-A.15 owner lock hold msg={message[:80]!r} fixture={fixture!r}"
            ],
            "aurora_version": "Aurora v3.3.2-beta",
        }
    except Exception:
        return None


def should_block_ga(
    ctx: dict[str, Any] | None,
    message: str | None,
    *,
    master_confidence: float | None = None,
) -> bool:
    """True → skip GA/repair steal for this turn."""
    if not isinstance(ctx, dict):
        return False
    # 8.4-A.16 — never block (trap) on explicit non-sport / release messages
    if is_release_message(message):
        release_owner_lock(ctx, reason="ga_block_skip:non_sport_message")
        return False

    candidate = is_continuity_followup_candidate(message)
    team, fixture = _sport_anchor(ctx)
    has_anchor = bool(team or fixture)
    locked = owner_lock_active(ctx) or (has_anchor and has_active_sport_context(ctx))

    # Sticky reclaim without strong FU → release and do not block (let proper owner answer)
    if not strong_sport_followup(message, ctx):
        if repeated_claim_detector(ctx, record=False) or claim_cooldown_active(ctx):
            release_owner_lock(ctx, reason="ga_block_skip:sticky_reclaim")
            return False
        if int(_obs(ctx).get("lock_turns_held") or 0) > OWNER_LOCK_MAX_TURNS:
            release_owner_lock(ctx, reason="ga_block_skip:max_lock_turns")
            return False

    # Block GA steal on real short FU when sport anchor exists
    if candidate and has_anchor and locked:
        bump(ctx, "owner_steal_attempted")
        bump(ctx, "owner_steal_blocked")
        bump(ctx, "owner_transition_denied")
        note_transition(ctx, from_bucket="SPORT", to_bucket="GA")
        return True
    if locked and has_anchor and not owner_steal_allowed(
        proposed_owner="GA",
        current_locked=True,
        master_confidence=master_confidence,
        continuity_candidate=candidate,
    ):
        bump(ctx, "owner_steal_attempted")
        bump(ctx, "owner_steal_blocked")
        return True
    return False


def note_owner_after_response(
    ctx: dict[str, Any] | None,
    payload: dict[str, Any] | None,
) -> None:
    """Persist last owner + refresh SPORT lock after sport replies."""
    if not isinstance(ctx, dict) or not isinstance(payload, dict):
        return
    try:
        _bump_turn(ctx)
        ents = payload.get("entities") or {}
        owner = ents.get("turn_owner") or ents.get("response_owner")
        intent = str(payload.get("intent") or "")
        resp_owner = str(ents.get("response_owner") or "")
        obs = _obs(ctx)

        # Track consecutive ownership_stability claims (anti sticky)
        if resp_owner == "ownership_stability":
            obs["consecutive_claims"] = int(obs.get("consecutive_claims") or 0) + 1
            if int(obs["consecutive_claims"]) >= MAX_CONSECUTIVE_CLAIMS:
                bump(ctx, "sticky_owner_detected")
                bump(ctx, "claim_repetition_count")
        else:
            obs["consecutive_claims"] = 0

        if not owner:
            bump(ctx, "orphan_state_detected")
            bump(ctx, "ownerless_transition")
            # Self-heal only when a real sport anchor exists
            team, fixture = _sport_anchor(ctx)
            if team or fixture:
                healed = force_owner_claim_after_ga_block(
                    str(ctx.get("raw_user_message") or ""),
                    ctx,
                    existing_payload=payload,
                )
                if isinstance(healed, dict):
                    payload.clear()
                    payload.update(healed)
                    ents = payload.get("entities") or {}
                    owner = ents.get("turn_owner") or "SPORT"
            else:
                ents = dict(ents)
                ents["turn_owner"] = "GA"
                ents["response_owner"] = ents.get("response_owner") or "natural_conversation"
                payload["entities"] = ents
                owner = ents["turn_owner"]
                release_owner_lock(ctx, reason="orphan_no_anchor")

        ctx["last_turn_owner"] = owner
        ctx["last_response_owner"] = ents.get("response_owner")
        if ctx.get("ownership_stability_block_ga"):
            note_transition(ctx, from_bucket="SPORT", to_bucket="BLOCKED_GA")
            if not ents.get("owner_claimed_after_block") and not ents.get(
                "ownership_stability"
            ):
                bump(ctx, "ga_block_without_claim")
                bump(ctx, "dangerous_transition_after_block")

        # 8.4-A.16 — refresh lock only on real sport analysis / resolver hits
        real_sport = intent in {"analyze_match", "match_opinion"} or bool(
            ents.get("pronoun_continuity")
            or ents.get("advanced_football_continuity")
            or (
                ents.get("continuity_followup")
                and ents.get("ownership_stability_guard")
                in {"continuity", "pronoun", "advanced"}
            )
        )
        soft_hold = bool(ents.get("ownership_stability")) and not real_sport
        if real_sport:
            activate_owner_lock(ctx, owner="SPORT", reason="post_sport_reply")
            _ensure_continuity_armed(ctx)
        elif soft_hold:
            # Count toward turn TTL without full wall-clock refresh
            activate_owner_lock(
                ctx,
                owner="SPORT",
                reason="owner_lock_hold",
                refresh_ttl=False,
            )
        elif resp_owner and resp_owner != "ownership_stability":
            # Non-sport owner answered — release sticky lock
            if owner_lock_active(ctx) and intent not in {
                "follow_up",
                "analyze_match",
                "match_opinion",
            }:
                release_owner_lock(ctx, reason="non_sport_owner_reply")

        obs = _obs(ctx)
        # Snapshot counters onto payload entities for AEP detectors
        ents = dict(payload.get("entities") or {})
        ents["owner_stability_counters"] = dict(obs.get("counters") or {})
        ents["owner_lock_duration"] = int(obs.get("lock_turns_held") or 0)
        ents["claim_repetition_count"] = int(obs.get("consecutive_claims") or 0)
        ents["owner_release_triggered"] = bool(
            str(obs.get("lock_reason") or "").startswith("released:")
        )
        stamp = ctx.get("_continuity_stamp") or compute_continuity_stamp(ctx)
        ents["continuity_score"] = stamp.get("continuity_score")
        ents["continuity_signals"] = stamp.get("continuity_signals")
        payload["entities"] = ents
    except Exception as exc:
        logger.warning("note_owner_after_response fail-open: %s", exc)


def stamp_payload_observability(
    payload: dict[str, Any] | None,
    ctx: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(payload, dict) or not isinstance(ctx, dict):
        return payload
    try:
        out = dict(payload)
        ents = dict(out.get("entities") or {})
        ents["owner_stability_counters"] = get_stability_counters(ctx)
        if owner_lock_active(ctx):
            ents["owner_lock_active"] = True
        stamp = ctx.get("_continuity_stamp") or compute_continuity_stamp(ctx)
        ents.setdefault("continuity_score", stamp.get("continuity_score"))
        ents.setdefault("continuity_signals", stamp.get("continuity_signals"))
        # Final orphan guard — never relabel unrelated answers as ownership_stability
        if not ents.get("turn_owner") or not ents.get("response_owner"):
            bump(ctx, "orphan_state_detected")
            team, fixture = _sport_anchor(ctx)
            if (team or fixture) and (
                ents.get("ownership_stability")
                or ents.get("continuity_followup")
                or ents.get("owner_lock")
            ):
                ents["turn_owner"] = ents.get("turn_owner") or "SPORT"
                ents["response_owner"] = ents.get("response_owner") or "ownership_stability"
                ents["owner_claim_forced"] = True
                ents["rewrite_locked"] = True
            else:
                ents["turn_owner"] = ents.get("turn_owner") or "GA"
                ents["response_owner"] = ents.get("response_owner") or "natural_conversation"
        out["entities"] = ents
        return out
    except Exception:
        return payload
