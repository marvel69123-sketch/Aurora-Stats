"""
ConversationContext + ConversationManager (Phase 5B).

In-memory cache (TTL 30 min) with SQLite fallback via chat_db.
Singleton manager — never recreate per request.

---------------------------------------------------------------------------
ARCHITECTURAL LIMITATION (Replit Autoscale)
---------------------------------------------------------------------------
Production deploy has NO sticky session affinity between VMs.
SQLite (artifacts/aurora/aurora.db) is LOCAL to each instance — not shared.

Therefore conversation memory is BEST-EFFORT only:
  • In-process cache helps subsequent requests on the SAME worker.
  • SQLite fallback helps only when the request lands on the SAME instance
    that wrote the context.
  • Cross-node persistence is NOT guaranteed. Do not design features that
    require multi-VM shared conversation state without an external store
    (explicitly out of scope for 5B — no Redis / new services).

Follow-ups that hit the QuickFollowUpGate still avoid expensive pipelines
even when memory is warm on one node; cold nodes simply miss context and
fall through to normal NL routing.
---------------------------------------------------------------------------
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

TTL_SECONDS = 30 * 60  # 30 minutes


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _utcnow_iso() -> str:
    return _utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class ConversationContext:
    session_id: str
    last_fixture: str | None = None
    last_match: str | None = None  # alias compat with existing ctx
    last_home: str | None = None
    last_away: str | None = None
    last_analysis: dict | None = None
    last_market: dict | list | None = None
    last_entities: list = field(default_factory=list)
    last_is_live: bool = False
    last_minute: int | None = None
    last_confidence: float = 0.0
    last_intent: str | None = None
    last_response_metadata: dict = field(default_factory=dict)
    last_live_at: str | None = None  # ISO when live snapshot was captured
    conversation_turns: list = field(default_factory=list)
    user_profile: dict = field(default_factory=dict)
    updated_at: str = field(default_factory=_utcnow_iso)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if not d.get("last_match") and d.get("last_fixture"):
            d["last_match"] = d["last_fixture"]
        if not d.get("last_fixture") and d.get("last_match"):
            d["last_fixture"] = d["last_match"]
        return d

    @classmethod
    def from_dict(cls, session_id: str, data: dict | None) -> ConversationContext:
        data = dict(data or {})
        match = data.get("last_match") or data.get("last_fixture")
        la = data.get("last_analysis") if isinstance(data.get("last_analysis"), dict) else None
        conf = 0.0
        if la and isinstance(la.get("confidence"), dict):
            try:
                conf = float(la["confidence"].get("score") or 0.0)
            except (TypeError, ValueError):
                conf = 0.0
        return cls(
            session_id=session_id,
            last_fixture=match,
            last_match=match,
            last_home=data.get("last_home"),
            last_away=data.get("last_away"),
            last_analysis=la,
            last_market=data.get("last_market") or (la.get("best_markets") if la else None),
            last_entities=list(data.get("last_entities") or []),
            last_is_live=bool(
                data.get("last_is_live")
                if data.get("last_is_live") is not None
                else (la.get("is_live") if la else False)
            ),
            last_minute=(
                data.get("last_minute")
                if data.get("last_minute") is not None
                else (la.get("minute") if la else None)
            ),
            last_confidence=float(data.get("last_confidence") or conf or 0.0),
            last_intent=data.get("last_intent"),
            last_response_metadata=dict(data.get("last_response_metadata") or {}),
            last_live_at=data.get("last_live_at"),
            conversation_turns=list(data.get("conversation_turns") or []),
            user_profile=dict(data.get("user_profile") or {}),
            updated_at=data.get("updated_at") or _utcnow_iso(),
        )

    def has_fixture(self) -> bool:
        return bool(self.last_match or self.last_fixture)


class ConversationManager:
    """
    Process-local singleton cache + SQLite fallback.

    ERRADO: ConversationManager() por request
    CORRETO: from src.conversation import conversation_manager
    """

    def __init__(self, ttl_seconds: int = TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._lock = threading.RLock()
        self._cache: dict[str, tuple[dict[str, Any], float]] = {}

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def _expired(self, expires: float) -> bool:
        return time.monotonic() > expires

    def get(self, session_id: str) -> dict[str, Any]:
        """Memory first; SQLite fallback; empty dict if unknown."""
        with self._lock:
            hit = self._cache.get(session_id)
            if hit is not None:
                ctx, expires = hit
                if not self._expired(expires):
                    return dict(ctx)
                self._cache.pop(session_id, None)

        try:
            from src.chat_db import get_conversation_context
            raw = get_conversation_context(session_id) or {}
        except Exception as exc:
            logger.warning("ConversationManager.get sqlite failed: %s", exc)
            raw = {}

        if not raw:
            return {}

        ctx = ConversationContext.from_dict(session_id, raw).to_dict()
        self._put_memory(session_id, ctx)
        return dict(ctx)

    def save(self, session_id: str, ctx: dict[str, Any]) -> None:
        """Update memory + SQLite. Always stamps updated_at."""
        merged = dict(ctx)
        merged["updated_at"] = _utcnow_iso()
        if merged.get("last_match") and not merged.get("last_fixture"):
            merged["last_fixture"] = merged["last_match"]
        if merged.get("last_fixture") and not merged.get("last_match"):
            merged["last_match"] = merged["last_fixture"]

        self._put_memory(session_id, merged)

        try:
            from src.chat_db import save_conversation_context
            save_conversation_context(session_id, merged)
        except Exception as exc:
            logger.warning("ConversationManager.save sqlite failed: %s", exc)

    def _put_memory(self, session_id: str, ctx: dict[str, Any]) -> None:
        with self._lock:
            self._cache[session_id] = (dict(ctx), time.monotonic() + self._ttl)

    def touch_from_analysis(
        self,
        session_id: str,
        ctx: dict[str, Any],
        payload: dict[str, Any],
        home: str,
        away: str,
    ) -> dict[str, Any]:
        """Persist analysis fields into ctx (in-place) and save."""
        analysis = {
            k: v for k, v in payload.items() if k not in ("brain", "aurora_version")
        }
        match = payload.get("match") or f"{home} x {away}"
        is_live = bool(payload.get("is_live"))
        minute = payload.get("minute")
        conf = 0.0
        csec = analysis.get("confidence")
        if isinstance(csec, dict):
            try:
                conf = float(csec.get("score") or 0.0)
            except (TypeError, ValueError):
                conf = 0.0

        ctx["last_home"] = home
        ctx["last_away"] = away
        ctx["last_match"] = match
        ctx["last_fixture"] = match
        ctx["last_intent"] = "analyze_match"
        ctx["last_analysis"] = analysis
        ctx["last_market"] = analysis.get("best_markets")
        ctx["last_is_live"] = is_live
        ctx["last_minute"] = minute
        ctx["last_confidence"] = conf
        ctx["last_entities"] = [{"home": home, "away": away}]
        if is_live:
            ctx["last_live_at"] = _utcnow_iso()
        ctx["updated_at"] = _utcnow_iso()
        self.save(session_id, ctx)
        return ctx


# Module-level singleton — never recreate per request.
conversation_manager = ConversationManager()
