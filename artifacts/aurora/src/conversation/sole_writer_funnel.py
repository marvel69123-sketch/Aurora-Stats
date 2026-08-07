"""
Mission 016 Phase 4+5 — Sole-Writer Funnel + PGR-01 gated activation.

Progressive activation percentages (constants): 0 → 1 → 5 → 10 → 25 → 50 → 100.
Default in repo: 0% (OFF). Authorized live stage without PO unlock = 1% only
(STAGE1_BOUNDARY_1PCT), and Phase 5 REGRA 25 requires independent PGR-01 arming
(`AURORA_PGR_01_ENABLE`) before that 1% path is live. Higher % / PGR-02+ remain
locked. No auto-advance. ENABLE_LANGGRAPH_STATE stays OFF (full prod write / Phase 6
not started).

Writes that the funnel owns go through C17 Minimal Commit Orchestrator only
(dual-write forbidden). Legacy writers remain present when OFF / not selected.
Shadow (Phase 3) is untouched.
"""

from __future__ import annotations

import hashlib
import logging
import os
import threading
from dataclasses import dataclass, field
from typing import Any, Literal

from src.conversation.migration_flag_controller import (
    get_migration_stage,
    production_write_active,
    sts_funnel_analyze_enabled,
    sts_funnel_boundary_enabled,
    sts_sole_writer_enabled,
)
from src.conversation.minimal_commit_orchestrator import (
    invoke_minimal_commit_orchestrator,
)
from src.conversation.sport_topic_state import SportTopicState, langgraph_state_enabled

logger = logging.getLogger(__name__)

# REGRA 24 stage ladder — higher stages exist as constants only.
FUNNEL_STAGE_PERCENTAGES: tuple[int, ...] = (0, 1, 5, 10, 25, 50, 100)

# Phase 4 PO cadence: only first progressive step authorized without unlock.
PHASE4_AUTHORIZED_MAX_PCT = 1

_ENV_PCT = "AURORA_SOLE_WRITER_FUNNEL_PCT"
_ENV_PO_UNLOCK = "AURORA_FUNNEL_PO_STAGE_UNLOCK"  # required to set pct > 1
_CTX_STS_KEY = "_sts_funnel_snapshot"
_CTX_FUNNEL_META = "_sts_funnel_meta"
_CSL_SUBJECT_GUARD = "csl_subject_guard"

FunnelOwner = Literal["boundary", "analyze", "note_subject", "none"]

_metrics_lock = threading.Lock()
_METRICS: dict[str, int] = {
    "funnel_commits": 0,
    "funnel_skipped_off": 0,
    "funnel_skipped_bucket": 0,
    "funnel_skipped_path": 0,
    "funnel_rollback_to_zero": 0,
    "funnel_blocked_high_stage": 0,
    "funnel_dual_write_blocked": 0,
}


def reset_funnel_metrics() -> None:
    with _metrics_lock:
        for k in _METRICS:
            _METRICS[k] = 0


def funnel_metrics_snapshot() -> dict[str, int]:
    with _metrics_lock:
        return dict(_METRICS)


def _bump(metric: str) -> None:
    with _metrics_lock:
        _METRICS[metric] = int(_METRICS.get(metric, 0)) + 1


def _flag_truthy(env_name: str) -> bool:
    raw = (os.environ.get(env_name) or "0").strip().lower()
    return raw in {"1", "true", "on", "yes"}


def po_stage_unlock_enabled() -> bool:
    """Explicit PO approval gate for pct > PHASE4_AUTHORIZED_MAX_PCT."""
    return _flag_truthy(_ENV_PO_UNLOCK)


def parse_funnel_pct(raw: str | None) -> int:
    """Parse pct; invalid → 0 (fail-closed)."""
    if raw is None or not str(raw).strip():
        return 0
    try:
        val = int(str(raw).strip())
    except (TypeError, ValueError):
        return 0
    if val not in FUNNEL_STAGE_PERCENTAGES:
        return 0
    return val


def get_configured_funnel_pct() -> int:
    """Raw configured pct before Phase-4 cap (observability)."""
    return parse_funnel_pct(os.environ.get(_ENV_PCT))


def get_funnel_pct() -> int:
    """
    Effective progressive activation percentage.

    Default 0. Values > PHASE4_AUTHORIZED_MAX_PCT without PO unlock fail-closed to 0
    (do not auto-advance; do not silently run higher stages).

    Phase 5 / REGRA 25: configured 1% is effective only when PGR-01 is armed
    (`AURORA_PGR_01_ENABLE`). Without that independent gate, effective remains 0.
    """
    configured = get_configured_funnel_pct()
    if configured <= 0:
        return 0
    if configured > PHASE4_AUTHORIZED_MAX_PCT and not po_stage_unlock_enabled():
        _bump("funnel_blocked_high_stage")
        logger.warning(
            "[AUDIT] SOLE_WRITER_FUNNEL blocked_high_stage configured_pct=%s "
            "authorized_max=%s (set %s=1 only with PO approval)",
            configured,
            PHASE4_AUTHORIZED_MAX_PCT,
            _ENV_PO_UNLOCK,
        )
        return 0
    # PGR-01 independent gate for the authorized 1% stage.
    if configured == PHASE4_AUTHORIZED_MAX_PCT:
        try:
            from src.conversation.progressive_gate_review import (
                higher_pgr_gate_attempted,
                require_pgr01_for_stage1,
            )

            if higher_pgr_gate_attempted():
                _bump("funnel_blocked_high_stage")
                return 0
            if not require_pgr01_for_stage1(force=False):
                return 0
        except Exception as exc:
            logger.warning(
                "[AUDIT] SOLE_WRITER_FUNNEL pgr01_gate_check failed fail-closed (%s)",
                exc,
            )
            return 0
    return configured


def rollback_funnel_to_off() -> int:
    """Instant rollback helper: clear pct env to OFF (0%)."""
    os.environ.pop(_ENV_PCT, None)
    _bump("funnel_rollback_to_zero")
    logger.warning("[AUDIT] SOLE_WRITER_FUNNEL rollback_to_off pct=0")
    return 0


def funnel_stage_name(pct: int | None = None) -> str:
    p = get_funnel_pct() if pct is None else int(pct)
    if p <= 0:
        return "OFF_0"
    if p == 1:
        return "STAGE1_BOUNDARY_1PCT"
    if p == 5:
        return "STAGE2_ANALYZE_5PCT"
    if p == 10:
        return "STAGE3_NOTE_10PCT"
    if p == 25:
        return "STAGE4_25PCT"
    if p == 50:
        return "STAGE5_50PCT"
    if p >= 100:
        return "STAGE6_100PCT"
    return f"PCT_{p}"


def in_funnel_canary_bucket(
    session_key: str | None,
    *,
    force: bool = False,
    pct: int | None = None,
) -> bool:
    """
    Deterministic canary selection for progressive %.

    force=True: tests only — treat as selected (PGR arming may be absent in
    unit tests that still exercise C17 ownership via force).
    """
    if force:
        return True
    effective = get_funnel_pct() if pct is None else int(pct)
    if effective <= 0:
        return False
    if effective >= 100:
        return True
    key = (session_key or "").strip() or "anonymous"
    digest = hashlib.sha256(f"aurora-funnel:{key}".encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) % 100  # 0..99
    return bucket < effective


def boundary_funnel_enabled(*, force: bool = False) -> bool:
    """First Plan funnel stage: boundary write path (REGRA 24/25 stage 1% + PGR-01)."""
    if not sts_funnel_boundary_enabled():
        return False
    if force:
        # Tests may force stage-1 semantics when boundary flag is ON.
        return True
    try:
        from src.conversation.progressive_gate_review import require_pgr01_for_stage1

        if not require_pgr01_for_stage1(force=False):
            return False
    except Exception:
        return False
    return get_funnel_pct() >= 1


def analyze_funnel_enabled(*, force: bool = False) -> bool:
    """Second Plan funnel stage — scaffolding only in Phase 4 (needs pct>=5 + unlock)."""
    if not sts_funnel_analyze_enabled():
        return False
    if force and get_configured_funnel_pct() >= 5 and po_stage_unlock_enabled():
        return get_funnel_pct() >= 5
    return get_funnel_pct() >= 5


def note_subject_funnel_enabled(*, force: bool = False) -> bool:
    """note_* subject funnel — scaffolding; needs pct>=10 + unlock (not Phase 4 live)."""
    if not _flag_truthy("ENABLE_STS_NOTE_SUBJECT_GUARDS"):
        return False
    return get_funnel_pct() >= 10


def funnel_owns_path(
    owner: FunnelOwner,
    *,
    session_key: str | None = None,
    force: bool = False,
) -> bool:
    """
    True when funnel owns this write path for this turn (no dual-write with legacy).
    """
    if owner == "none":
        return False
    if langgraph_state_enabled() or production_write_active():
        # Phase 5 host owns production write — C17 funnel must not dual-commit.
        return False
    if owner == "boundary":
        if not boundary_funnel_enabled(force=force):
            return False
    elif owner == "analyze":
        if not analyze_funnel_enabled(force=force):
            return False
    elif owner == "note_subject":
        if not note_subject_funnel_enabled(force=force):
            return False
    else:
        return False

    if not in_funnel_canary_bucket(session_key, force=force):
        _bump("funnel_skipped_bucket")
        return False
    return True


@dataclass
class FunnelCommitResult:
    owned: bool
    committed: bool
    skipped: bool
    skipped_reason: str | None = None
    owner: FunnelOwner = "none"
    pct: int = 0
    stage_name: str = "OFF_0"
    sts: SportTopicState | None = None
    orchestrator: dict[str, Any] = field(default_factory=dict)
    dual_write_forbidden: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "owned": self.owned,
            "committed": self.committed,
            "skipped": self.skipped,
            "skipped_reason": self.skipped_reason,
            "owner": self.owner,
            "pct": self.pct,
            "stage_name": self.stage_name,
            "sts": self.sts.to_dict() if self.sts else None,
            "orchestrator": dict(self.orchestrator),
            "dual_write_forbidden": self.dual_write_forbidden,
            "metrics": funnel_metrics_snapshot(),
            "migration_stage": get_migration_stage().value,
            "sole_writer_flag": sts_sole_writer_enabled(),
            "production_write": production_write_active(),
        }


def _project_sts_to_ctx_boundary(
    ctx: dict[str, Any], sts: SportTopicState, *, reason: str
) -> None:
    """Write-through projection from committed STS (epoch-tagged). Not a second author."""
    teams = list(sts.teams or [])[:4]
    home = teams[0] if teams else None
    away = teams[1] if len(teams) > 1 else None
    fx = sts.fixture
    gen = int(sts.subject_generation or 0)

    if home:
        ctx["last_home"] = home
    else:
        ctx.pop("last_home", None)
    if away:
        ctx["last_away"] = away
    else:
        ctx.pop("last_away", None)
    if fx:
        ctx["last_match"] = fx
        ctx["last_fixture"] = fx
    else:
        ctx.pop("last_match", None)
        ctx.pop("last_fixture", None)

    ctx["episode_id"] = sts.episode_id
    ctx["subject_generation"] = gen
    ctx["boundary_reason"] = sts.boundary_reason or reason
    ctx["topic_boundary_reason"] = sts.boundary_reason or reason
    ctx["episode_boundary"] = True
    ctx["boundary_detected"] = True
    ctx["subject_replaced"] = True
    ctx["brain_boundary_cleared"] = True
    ctx["block_hydrate_legacy"] = True

    csl = dict(ctx.get("csl") or {}) if isinstance(ctx.get("csl"), dict) else {}
    csl["episode_id"] = sts.episode_id
    csl["teams"] = teams
    csl["fixture"] = fx
    if sts.topic:
        csl["topic"] = sts.topic
    ctx["csl"] = csl

    ctx[_CSL_SUBJECT_GUARD] = {
        "episode_id": sts.episode_id,
        "teams": teams,
        "fixture": fx,
        "reason": sts.boundary_reason or reason,
        "subject_generation": gen,
    }
    ctx[_CTX_STS_KEY] = sts.to_dict()


def _run_keep_side_effects(ctx: dict[str, Any], reason: str) -> None:
    """KEEP module public APIs (orphan clear / OS / SCG) — not subject invent."""
    try:
        from src.conversation.message_intelligence import clear_fixture_context

        clear_fixture_context(ctx)
    except Exception as exc:
        logger.warning("funnel: clear_fixture_context skipped (%s)", exc)
    try:
        from src.conversation.conversation_focus import clear_focus_on_boundary

        clear_focus_on_boundary(ctx)
    except Exception:
        pass
    try:
        from src.conversation.sport_continuity_guard import expire_sport_anchor

        expire_sport_anchor(ctx, reason=f"funnel_boundary:{reason}")
    except Exception as exc:
        logger.warning("funnel: expire_sport_anchor skipped (%s)", exc)
    try:
        from src.conversation.ownership_stability import release_owner_lock

        release_owner_lock(ctx, reason=f"funnel_boundary:{reason}")
    except Exception as exc:
        logger.warning("funnel: release_owner_lock skipped (%s)", exc)
    for key in (
        "conversation_continuity",
        "pronoun_continuity",
        "advanced_football_continuity",
        "ci_pending",
        "last_turn_owner",
        "last_response_owner",
    ):
        ctx.pop(key, None)
    try:
        from src.conversation.topic_boundary_v2 import _clear_orphan_sport_state

        orphan_flags = _clear_orphan_sport_state(ctx, reason=reason)
        for k, v in orphan_flags.items():
            ctx[k] = v
    except Exception as exc:
        logger.warning("funnel: orphan clear skipped (%s)", exc)


def commit_via_c17_funnel(
    message: str,
    ctx: dict[str, Any] | None,
    *,
    owner: FunnelOwner,
    session_key: str | None = None,
    force: bool = False,
    prior_sts: SportTopicState | dict[str, Any] | None = None,
) -> FunnelCommitResult:
    """
    Sole commit entry for funnel-owned paths. Dual-write forbidden when owned=True.

    When not owned: skipped — caller MUST use legacy writer (legacy remains present).
    """
    pct = get_funnel_pct()
    if force and pct <= 0 and get_configured_funnel_pct() >= 1:
        # Tests: force with configured stage-1 pct even if mis-capped mid-call.
        pct = PHASE4_AUTHORIZED_MAX_PCT if get_configured_funnel_pct() >= 1 else 0
    if force and pct <= 0 and boundary_funnel_enabled(force=True):
        pct = PHASE4_AUTHORIZED_MAX_PCT
    stage = funnel_stage_name(pct)
    sk = session_key
    if sk is None and isinstance(ctx, dict):
        sk = str(ctx.get("session_id") or ctx.get("thread_id") or "") or None

    if not funnel_owns_path(owner, session_key=sk, force=force):
        reason = "funnel_off_or_not_selected"
        if get_funnel_pct() <= 0 and not (force and sts_funnel_boundary_enabled()):
            _bump("funnel_skipped_off")
            reason = "funnel_pct_off"
        elif owner == "boundary" and not sts_funnel_boundary_enabled():
            _bump("funnel_skipped_path")
            reason = "boundary_flag_off"
        elif owner == "analyze" and not analyze_funnel_enabled(force=force):
            _bump("funnel_skipped_path")
            reason = "analyze_stage_not_live"
        elif owner == "note_subject" and not note_subject_funnel_enabled(force=force):
            _bump("funnel_skipped_path")
            reason = "note_stage_not_live"
        logger.info(
            "[AUDIT] SOLE_WRITER_FUNNEL skipped owner=%s reason=%s pct=%s stage=%s",
            owner,
            reason,
            pct,
            stage,
        )
        return FunnelCommitResult(
            owned=False,
            committed=False,
            skipped=True,
            skipped_reason=reason,
            owner=owner,
            pct=pct,
            stage_name=stage,
        )

    orch = invoke_minimal_commit_orchestrator(
        message or "",
        prior_sts,
        session_id=sk,
        force=True,  # stage gate already applied; C17 still skips if P4 write ON
        persist_checkpoint=False,
        hydrate_from_checkpoint=False,
    )
    if orch.skipped:
        _bump("funnel_skipped_path")
        logger.warning(
            "[AUDIT] SOLE_WRITER_FUNNEL c17_skipped owner=%s reason=%s",
            owner,
            orch.skipped_reason,
        )
        return FunnelCommitResult(
            owned=True,
            committed=False,
            skipped=True,
            skipped_reason=orch.skipped_reason or "c17_skipped",
            owner=owner,
            pct=pct,
            stage_name=stage,
            sts=orch.sts,
            orchestrator=orch.to_dict(),
        )

    if isinstance(ctx, dict) and owner == "boundary":
        reason = (orch.decision.reason if orch.decision else None) or "funnel_boundary"
        _run_keep_side_effects(ctx, reason)
        _project_sts_to_ctx_boundary(ctx, orch.sts, reason=reason)
        ctx[_CTX_FUNNEL_META] = {
            "owner": owner,
            "pct": pct,
            "stage_name": stage,
            "apply_node": orch.apply_node,
            "subject_generation": int(orch.sts.subject_generation or 0),
            "dual_write_forbidden": True,
        }

    _bump("funnel_commits")
    logger.warning(
        "[AUDIT] SOLE_WRITER_FUNNEL commit owner=%s pct=%s stage=%s node=%s gen=%s",
        owner,
        pct,
        stage,
        orch.apply_node,
        getattr(orch.sts, "subject_generation", None),
    )
    return FunnelCommitResult(
        owned=True,
        committed=True,
        skipped=False,
        owner=owner,
        pct=pct,
        stage_name=stage,
        sts=orch.sts,
        orchestrator=orch.to_dict(),
    )


def mark_dual_write_blocked(owner: FunnelOwner) -> None:
    """Observability when a legacy writer was suppressed because funnel owns path."""
    _bump("funnel_dual_write_blocked")
    logger.info(
        "[AUDIT] SOLE_WRITER_FUNNEL dual_write_blocked owner=%s",
        owner,
    )


def funnel_flag_snapshot() -> dict[str, Any]:
    """Read-only posture for reports / Validation Contract."""
    configured = get_configured_funnel_pct()
    effective = get_funnel_pct()
    pgr_snap: dict[str, Any] = {}
    try:
        from src.conversation.progressive_gate_review import (
            pgr01_enable_flag,
            pgr_flag_snapshot,
        )

        pgr_snap = pgr_flag_snapshot()
        pgr01_on = pgr01_enable_flag()
    except Exception:
        pgr01_on = False
    return {
        "configured_pct": configured,
        "effective_pct": effective,
        "stage_name": funnel_stage_name(effective),
        "phase4_authorized_max_pct": PHASE4_AUTHORIZED_MAX_PCT,
        "po_unlock": po_stage_unlock_enabled(),
        "boundary_flag": sts_funnel_boundary_enabled(),
        "analyze_flag": sts_funnel_analyze_enabled(),
        "sole_writer_flag": sts_sole_writer_enabled(),
        "boundary_funnel_live": boundary_funnel_enabled(),
        "analyze_funnel_live": analyze_funnel_enabled(),
        "note_funnel_live": note_subject_funnel_enabled(),
        "ladder": list(FUNNEL_STAGE_PERCENTAGES),
        "metrics": funnel_metrics_snapshot(),
        "legacy_writers_present": True,
        "shadow_untouched": True,
        # Phase 5 PGR-01 may be armed; full LangGraph production write still OFF.
        "phase5_pgr01_started": bool(pgr01_on or effective >= 1),
        "phase5_langgraph_write_not_started": not langgraph_state_enabled(),
        "phase6_not_started": True,
        "pgr02_not_started": True,
        "phase5_not_started": not langgraph_state_enabled(),  # compat: write path
        "auto_advance": False,
        "pgr": pgr_snap,
    }
