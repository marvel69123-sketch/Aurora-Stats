"""
AURORA-TOPIC-BOUNDARY-001/002 — Episode boundary detection (V2).

Additive façade. Detects when sport continuity should start a *new episode*
(Athena / Episodic-style subject change) so sticky prior context does not bleed.

Rule:
  If entity overlap is low OR a completely new fixture appears → new episode.

TOPIC-BOUNDARY-002 (sticky bleed fix):
  - Router must call apply_topic_boundary_v2 AFTER SLL and BEFORE CSL /
    sport-intent rewrite / follow-up reuse (raw user message).
  - On new episode: clear orphan sport referents (SRF, entity bind, short
    sport memory, follow-up refs) and fully replace CSL subject.
  - note_csl must not re-write the prior fixture after reset (subject guard).

Feature flag: ENABLE_TOPIC_BOUNDARY_V2 (default OFF).
Fail-open. Never invents fixtures/odds. Does not edit FROZEN engines or
ownership_stability / sport_continuity_guard internals — only calls public
release/expire APIs and clears sport-episode session keys via helpers.
"""

from __future__ import annotations

import logging
import os
import re
import unicodedata
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

_FLAG_ENV = "ENABLE_TOPIC_BOUNDARY_V2"
CTX_KEY = "topic_boundary_v2"
# Jaccard below this ⇒ low overlap (disjoint pairs ≈ 0.0)
_LOW_OVERLAP = 0.34

_FIXTURE_PHRASE = re.compile(
    r"(?<!\w)([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9._''-]{1,40})"
    r"\s+(?:x|×|vs\.?|versus)\s+"
    r"([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9._''-]{1,40})(?!\w)",
    re.I,
)
_COMPARE_PHRASE = re.compile(
    r"(?<!\w)([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9._''-]{1,40})"
    r"\s+(?:ou|contra)\s+"
    r"([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9._''-]{1,40})(?!\w)",
    re.I,
)
_SOFT_FOLLOWUP = re.compile(
    r"(?:"
    r"quem\s+est[aá]\s+(?:melhor|em\s+melhor)|"
    r"quem\s+(?:e|é)\s+melhor|"
    r"e\s+(?:os\s+)?(?:gols?|escanteios?|cart[oõ]es?|mercados?)|"
    r"e\s+(?:o\s+)?(?:placar|horario|horário|mando)|"
    r"e\s+agora\??|"
    r"como\s+(?:ele|ela|eles)\b|"
    r"e\s+dele\??|"
    r"qual\s+(?:dos\s+dois|melhor)"
    r")",
    re.I,
)
# Single-club calendar / schedule asks ("Inter joga hoje?")
_SINGLE_TEAM_ASK = re.compile(
    r"(?<!\w)([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9._''-]{2,40})\s+"
    r"(?:joga|jogam|enfrenta|enfrentam|venceu|perdeu|empata)\b",
    re.I,
)
# Ctx stamp: protect CSL subject from note_csl re-bleed after episode reset
CSL_SUBJECT_GUARD_KEY = "csl_subject_guard"


def topic_boundary_v2_enabled() -> bool:
    raw = (os.environ.get(_FLAG_ENV) or "0").strip().lower()
    return raw in {"1", "true", "on", "yes"}


def fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


@dataclass
class EpisodeBoundaryDecision:
    is_boundary: bool = False
    reason: str = "keep"
    overlap: float | None = None
    prior_entities: list[str] = field(default_factory=list)
    current_entities: list[str] = field(default_factory=list)
    new_fixture: str | None = None
    prior_fixture: str | None = None
    episode_id: str | None = None
    skipped_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_boundary": self.is_boundary,
            "reason": self.reason,
            "overlap": self.overlap,
            "prior_entities": list(self.prior_entities),
            "current_entities": list(self.current_entities),
            "new_fixture": self.new_fixture,
            "prior_fixture": self.prior_fixture,
            "episode_id": self.episode_id,
            "skipped_reason": self.skipped_reason,
        }


def _uniq_folded(names: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for n in names:
        if not isinstance(n, str):
            continue
        t = n.strip()
        if not t:
            continue
        k = fold(t)
        if k and k not in seen:
            seen.add(k)
            out.append(t)
    return out


def prior_episode_entities(ctx: dict[str, Any] | None) -> list[str]:
    """
    Teams belonging to the sticky prior sport episode (read-only).

    Prefer continuity sticky keys / sport_anchor / focus — NOT live CSL slots,
    because apply_csl_resolve may already have overwritten csl.teams with the
    current turn's compare before V2 runs.
    """
    if not isinstance(ctx, dict):
        return []
    names: list[str] = []
    for key in ("last_home", "last_away"):
        v = ctx.get(key)
        if isinstance(v, str) and v.strip():
            names.append(v.strip())
    for key in ("last_match", "last_fixture"):
        v = ctx.get(key)
        if isinstance(v, str) and v.strip():
            parts = re.split(r"\s+(?:x|×|vs\.?|versus)\s+", v, maxsplit=1, flags=re.I)
            if len(parts) == 2:
                names.extend(p.strip() for p in parts if p.strip())
    focus = ctx.get("conversation_focus")
    if isinstance(focus, dict):
        for t in focus.get("topic_teams") or []:
            if isinstance(t, str) and t.strip():
                names.append(t.strip())
        tt = focus.get("topic_team")
        if isinstance(tt, str) and tt.strip():
            names.append(tt.strip())
    cont = ctx.get("conversation_continuity")
    if isinstance(cont, dict):
        for key in ("home", "away", "team", "focus_team"):
            v = cont.get(key)
            if isinstance(v, str) and v.strip():
                names.append(v.strip())
        fx = cont.get("fixture") or cont.get("last_fixture")
        if isinstance(fx, str) and fx.strip():
            parts = re.split(r"\s+(?:x|×|vs\.?|versus)\s+", fx, maxsplit=1, flags=re.I)
            if len(parts) == 2:
                names.extend(p.strip() for p in parts if p.strip())
    try:
        from src.conversation.sport_continuity_guard import get_sport_anchor

        anchor = get_sport_anchor(ctx)
        if isinstance(anchor, dict):
            for t in anchor.get("teams") or []:
                if isinstance(t, str) and t.strip():
                    names.append(t.strip())
            for key in ("home", "away"):
                v = anchor.get(key)
                if isinstance(v, str) and v.strip():
                    names.append(v.strip())
    except Exception:
        pass
    # Fallback: CSL only when no sticky keys (first-turn / CSL-only sessions)
    if not names:
        csl = ctx.get("csl")
        if isinstance(csl, dict):
            for t in csl.get("teams") or []:
                if isinstance(t, str) and t.strip():
                    names.append(t.strip())
    return _uniq_folded(names)


def prior_episode_fixture(ctx: dict[str, Any] | None) -> str | None:
    if not isinstance(ctx, dict):
        return None
    for key in ("last_match", "last_fixture"):
        v = ctx.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    try:
        from src.conversation.sport_continuity_guard import get_sport_anchor

        anchor = get_sport_anchor(ctx)
        if isinstance(anchor, dict):
            fx = anchor.get("fixture")
            if isinstance(fx, str) and fx.strip():
                return fx.strip()
    except Exception:
        pass
    focus = ctx.get("conversation_focus")
    if isinstance(focus, dict):
        fx = focus.get("topic_fixture")
        if isinstance(fx, str) and fx.strip():
            return fx.strip()
    cont = ctx.get("conversation_continuity")
    if isinstance(cont, dict):
        fx = cont.get("fixture") or cont.get("last_fixture")
        if isinstance(fx, str) and fx.strip():
            return fx.strip()
    # CSL fixture only as last resort (may already be new-turn)
    csl = ctx.get("csl")
    if isinstance(csl, dict) and isinstance(csl.get("fixture"), str) and csl["fixture"].strip():
        sticky = bool(ctx.get("last_home") or ctx.get("last_away") or ctx.get("last_match"))
        if not sticky:
            return csl["fixture"].strip()
    return None


def current_message_entities(message: str, ctx: dict[str, Any] | None = None) -> list[str]:
    """Teams explicitly present on this turn (SLL / compare / fixture phrase)."""
    names: list[str] = []
    if isinstance(ctx, dict):
        sll = ctx.get("sll")
        if isinstance(sll, dict):
            for c in sll.get("clubs") or []:
                if isinstance(c, str) and c.strip():
                    names.append(c.strip())
    text = message or ""
    for rx in (_FIXTURE_PHRASE, _COMPARE_PHRASE):
        m = rx.search(text)
        if m:
            a, b = m.group(1).strip(" .,!?"), m.group(2).strip(" .,!?")
            if fold(a) != fold(b):
                names.extend([a, b])
            break
    if not names:
        m = _SINGLE_TEAM_ASK.search(text)
        if m:
            names.append(m.group(1).strip(" .,!?"))
    return _uniq_folded(names)


def extract_fixture_phrase(message: str) -> str | None:
    m = _FIXTURE_PHRASE.search(message or "")
    if not m:
        return None
    a, b = m.group(1).strip(" .,!?"), m.group(2).strip(" .,!?")
    if fold(a) == fold(b):
        return None
    return f"{a} x {b}"


def entity_overlap(prior: list[str], current: list[str]) -> float | None:
    """Jaccard overlap on folded names. None when either side empty."""
    a = {fold(x) for x in prior if fold(x)}
    b = {fold(x) for x in current if fold(x)}
    if not a or not b:
        return None
    inter = a & b
    union = a | b
    if not union:
        return None
    return len(inter) / len(union)


def _fixtures_equivalent(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    fa, fb = fold(a), fold(b)
    if fa == fb:
        return True
    # Order-insensitive: "A x B" == "B x A"
    pa = re.split(r"\s+(?:x|×|vs\.?|versus)\s+", fa)
    pb = re.split(r"\s+(?:x|×|vs\.?|versus)\s+", fb)
    if len(pa) == 2 and len(pb) == 2:
        return set(pa) == set(pb)
    return False


def has_prior_episode(ctx: dict[str, Any] | None) -> bool:
    if not isinstance(ctx, dict):
        return False
    if prior_episode_entities(ctx) or prior_episode_fixture(ctx):
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
    return bool(ctx.get("conversation_continuity") or ctx.get("ci_pending"))


def detect_episode_boundary(
    message: str,
    ctx: dict[str, Any] | None,
) -> EpisodeBoundaryDecision:
    """
    Pure detection (no mutation). Fail-open → is_boundary=False.
    """
    decision = EpisodeBoundaryDecision()
    try:
        if not topic_boundary_v2_enabled():
            decision.skipped_reason = "flag_disabled"
            return decision
        if not has_prior_episode(ctx):
            decision.reason = "no_prior_episode"
            return decision

        prior = prior_episode_entities(ctx)
        current = current_message_entities(message, ctx)
        prior_fx = prior_episode_fixture(ctx)
        new_fx = extract_fixture_phrase(message)
        decision.prior_entities = prior
        decision.current_entities = current
        decision.prior_fixture = prior_fx
        decision.new_fixture = new_fx

        # Soft FU with no new entities → keep episode
        if not current and not new_fx:
            if _SOFT_FOLLOWUP.search(message or "") or len((message or "").split()) <= 6:
                decision.reason = "soft_followup_same_episode"
                return decision
            decision.reason = "no_current_entities"
            return decision

        # Brand-new fixture phrase vs prior sticky fixture
        if new_fx and prior_fx and not _fixtures_equivalent(new_fx, prior_fx):
            decision.is_boundary = True
            decision.reason = "new_fixture"
            decision.overlap = entity_overlap(prior, current)
            return decision

        # Explicit new fixture when prior had teams but no named fixture string
        if new_fx and prior and not prior_fx:
            ov = entity_overlap(prior, current)
            decision.overlap = ov
            if ov is None or ov < _LOW_OVERLAP:
                decision.is_boundary = True
                decision.reason = "new_fixture_no_prior_label"
                return decision

        ov = entity_overlap(prior, current)
        decision.overlap = ov
        if ov is not None and ov < _LOW_OVERLAP:
            decision.is_boundary = True
            decision.reason = "low_entity_overlap"
            return decision

        # Same fixture restated — keep
        if new_fx and prior_fx and _fixtures_equivalent(new_fx, prior_fx):
            decision.reason = "same_fixture_restated"
            return decision

        decision.reason = "overlap_ok"
        return decision
    except Exception as exc:
        logger.warning("detect_episode_boundary fail-open: %s", exc)
        decision.skipped_reason = "error"
        decision.is_boundary = False
        return decision


def _bump_csl_episode(
    ctx: dict[str, Any],
    *,
    seed_teams: list[str],
    seed_fixture: str | None,
) -> str:
    """Rotate CSL episode_id + fully replace subject slots (no prior preserve)."""
    new_id = str(uuid.uuid4())
    teams = list(seed_teams)[:4]
    fixture = seed_fixture
    if not fixture and len(teams) >= 2:
        fixture = f"{teams[0]} x {teams[1]}"
    topic = "comparison" if len(teams) >= 2 else ("calendar" if teams else None)
    try:
        from src.conversation.conversation_state_layer import get_csl, set_csl

        state = get_csl(ctx)
        state.episode_id = new_id
        # Full subject replace — never keep prior fixture/teams/topic
        state.teams = teams
        state.fixture = fixture
        state.topic = topic
        state.last_intent = None
        state.phase = "OPEN" if not teams else ("COMPARE" if len(teams) >= 2 else "SLOT_READY")
        state.injected = False
        state.skipped_reason = None
        state.contextualized_text = None
        set_csl(ctx, state)
    except Exception as exc:
        logger.warning("topic_boundary_v2: CSL episode bump skipped (%s)", exc)
        blob = ctx.get("csl") if isinstance(ctx.get("csl"), dict) else {}
        blob = dict(blob)
        blob["episode_id"] = new_id
        blob["teams"] = teams
        blob["fixture"] = fixture
        blob["topic"] = topic
        blob["last_intent"] = None
        blob["phase"] = "OPEN" if not teams else ("COMPARE" if len(teams) >= 2 else "SLOT_READY")
        blob["injected"] = False
        ctx["csl"] = blob
    logger.warning(
        "[AUDIT] subject_replaced teams=%s fixture=%r topic=%s episode=%s",
        teams,
        fixture,
        topic,
        new_id[:8],
    )
    return new_id


def _clear_orphan_sport_state(ctx: dict[str, Any], *, reason: str) -> dict[str, bool]:
    """
    Clear sticky sport referents that survive last_* clears.

    Does NOT clear: global chat history, user preferences, about-you profile,
    or non-sport session memory.
    """
    flags = {
        "orphan_state_cleared": False,
        "srf_cleared": False,
        "entity_bind_cleared": False,
        "short_sport_memory_cleared": False,
        "followup_refs_cleared": False,
    }
    try:
        from src.conversation.sport_referent_frame import clear_srf

        clear_srf(ctx, reason=f"episode_boundary:{reason}")
        flags["srf_cleared"] = True
        logger.warning("[AUDIT] srf_cleared reason=%s", reason)
    except Exception as exc:
        logger.warning("topic_boundary_v2: clear_srf skipped (%s)", exc)

    if ctx.pop("entity_v2_last_bind", None) is not None:
        flags["entity_bind_cleared"] = True
    ctx.pop("entity_v2_bind", None)
    ctx.pop("entity_bind", None)
    if flags["entity_bind_cleared"]:
        logger.warning("[AUDIT] entity_bind_cleared reason=%s", reason)

    # Short sport memory only (pronoun / last fixture) — not global history
    sm = ctx.get("short_conversation_memory")
    if isinstance(sm, dict):
        for key in (
            "last_team",
            "last_fixture",
            "last_home",
            "last_away",
            "last_match",
            "last_entities",
            "last_focus_team",
            "resolved_team",
            "resolved_fixture",
        ):
            sm.pop(key, None)
        ctx["short_conversation_memory"] = sm
        flags["short_sport_memory_cleared"] = True
    ctx.pop("short_memory_resolve", None)

    # Follow-up / referent sticky keys (episode-scoped)
    for key in (
        "followup_resolved_fixture",
        "followup_resolved_team",
        "pending_followup",
        "ci_pending",
        "last_referent",
        "sport_referent",
        "recent_entities",
        "last_entities",
    ):
        if ctx.pop(key, None) is not None:
            flags["followup_refs_cleared"] = True

    flags["orphan_state_cleared"] = any(
        flags[k]
        for k in (
            "srf_cleared",
            "entity_bind_cleared",
            "short_sport_memory_cleared",
            "followup_refs_cleared",
        )
    )
    if flags["orphan_state_cleared"]:
        logger.warning(
            "[AUDIT] orphan_state_cleared srf=%s bind=%s short_mem=%s followup=%s",
            flags["srf_cleared"],
            flags["entity_bind_cleared"],
            flags["short_sport_memory_cleared"],
            flags["followup_refs_cleared"],
        )
    return flags


def apply_episode_boundary(
    ctx: dict[str, Any],
    decision: EpisodeBoundaryDecision,
) -> EpisodeBoundaryDecision:
    """
    Materialize a new episode: clear sticky sport memory + orphan referents,
    expire anchors, release owner lock (public APIs), replace CSL subject.
    """
    if not isinstance(ctx, dict) or not decision.is_boundary:
        return decision
    try:
        from src.conversation.message_intelligence import clear_fixture_context

        clear_fixture_context(ctx)
    except Exception as exc:
        logger.warning("topic_boundary_v2: clear_fixture_context skipped (%s)", exc)

    try:
        from src.conversation.conversation_focus import clear_focus_on_boundary

        clear_focus_on_boundary(ctx)
    except Exception:
        pass

    try:
        from src.conversation.sport_continuity_guard import expire_sport_anchor

        expire_sport_anchor(ctx, reason=f"episode_boundary:{decision.reason}")
    except Exception as exc:
        logger.warning("topic_boundary_v2: expire_sport_anchor skipped (%s)", exc)

    try:
        from src.conversation.ownership_stability import release_owner_lock

        release_owner_lock(ctx, reason=f"episode_boundary:{decision.reason}")
    except Exception as exc:
        logger.warning("topic_boundary_v2: release_owner_lock skipped (%s)", exc)

    # Drop continuity memory blobs (session keys — not FROZEN internals)
    for key in (
        "conversation_continuity",
        "pronoun_continuity",
        "advanced_football_continuity",
        "ci_pending",
        "last_turn_owner",
        "last_response_owner",
    ):
        ctx.pop(key, None)

    orphan_flags = _clear_orphan_sport_state(ctx, reason=decision.reason)

    episode_id = _bump_csl_episode(
        ctx,
        seed_teams=list(decision.current_entities),
        seed_fixture=decision.new_fixture,
    )
    decision.episode_id = episode_id

    # Protect new subject from note_csl writing the prior analyze fixture
    guard_teams = list(decision.current_entities)[:4]
    guard_fx = decision.new_fixture
    if not guard_fx and len(guard_teams) >= 2:
        guard_fx = f"{guard_teams[0]} x {guard_teams[1]}"
    ctx[CSL_SUBJECT_GUARD_KEY] = {
        "episode_id": episode_id,
        "teams": guard_teams,
        "fixture": guard_fx,
        "reason": decision.reason,
    }

    # Signals for wrappers / observability (fail-open consumers)
    ctx["brain_boundary_cleared"] = True
    ctx["block_hydrate_legacy"] = True
    ctx["topic_boundary_reason"] = decision.reason
    ctx["episode_boundary"] = True
    ctx["episode_id"] = episode_id
    ctx["boundary_detected"] = True
    ctx["boundary_reason"] = decision.reason
    ctx["subject_replaced"] = True
    for k, v in orphan_flags.items():
        ctx[k] = v
    ctx[CTX_KEY] = decision.to_dict()

    logger.warning(
        "[AUDIT] boundary_detected reason=%s overlap=%s "
        "prior=%s current=%s new_fx=%r episode=%s",
        decision.reason,
        decision.overlap,
        decision.prior_entities,
        decision.current_entities,
        decision.new_fixture,
        (episode_id or "")[:8],
    )
    logger.warning(
        "[AUDIT] TopicBoundaryV2: NEW_EPISODE reason=%s overlap=%s "
        "prior=%s current=%s new_fx=%r episode=%s",
        decision.reason,
        decision.overlap,
        decision.prior_entities,
        decision.current_entities,
        decision.new_fixture,
        (episode_id or "")[:8],
    )
    return decision


def apply_topic_boundary_v2(
    message: str,
    ctx: dict[str, Any] | None,
) -> EpisodeBoundaryDecision:
    """
    Turn-start entry. Detect + optionally apply. No-op when flag off.
    Fail-open. Never raises.
    """
    decision = EpisodeBoundaryDecision()
    try:
        if not topic_boundary_v2_enabled():
            decision.skipped_reason = "flag_disabled"
            if isinstance(ctx, dict):
                ctx.pop("episode_boundary", None)
                ctx[CTX_KEY] = decision.to_dict()
            return decision
        if not isinstance(ctx, dict):
            decision.skipped_reason = "no_ctx"
            return decision

        # Per-turn: clear previous turn's sticky boundary stamps
        for key in (
            "episode_boundary",
            "boundary_detected",
            "boundary_reason",
            "subject_replaced",
            "orphan_state_cleared",
            "srf_cleared",
            "entity_bind_cleared",
            "short_sport_memory_cleared",
            "followup_refs_cleared",
            "note_csl_blocked",
            CSL_SUBJECT_GUARD_KEY,
        ):
            ctx.pop(key, None)

        decision = detect_episode_boundary(message, ctx)
        if decision.is_boundary:
            decision = apply_episode_boundary(ctx, decision)
        else:
            ctx[CTX_KEY] = decision.to_dict()
        return decision
    except Exception as exc:
        logger.warning("apply_topic_boundary_v2 fail-open: %s", exc)
        decision.skipped_reason = "error"
        decision.is_boundary = False
        return decision


def is_topic_switch_v2(message: str, ctx: dict[str, Any] | None = None) -> bool:
    """
    Narrow replacement for message_intelligence.is_topic_switch when flag ON.
    Uses episode boundary detection; falls back to legacy A x B regex if needed.
    """
    try:
        if topic_boundary_v2_enabled() and isinstance(ctx, dict):
            d = detect_episode_boundary(message, ctx)
            if d.is_boundary:
                return True
            if d.reason in {"same_fixture_restated", "soft_followup_same_episode", "overlap_ok"}:
                return False
        # Legacy: explicit A x B phrase
        return bool(_FIXTURE_PHRASE.search(message or ""))
    except Exception:
        return bool(_FIXTURE_PHRASE.search(message or ""))
