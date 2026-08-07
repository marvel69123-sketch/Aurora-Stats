"""
EM outbound ports (Spec §4.5) — protocols + inert stub adapters.

Phase 2: stubs do NOT call production Tool Use / engines / cost_protection
begin_request. Phase 4 Stage 1/2: production read/feed/engine adapters behind
DEFAULT OFF pipeline flags. Never CM write. Never begin_request.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class FetchFixturePort(Protocol):
    def fetch(
        self,
        *,
        home: str | None = None,
        away: str | None = None,
        force_refresh: bool = False,
        soft: bool = True,
    ) -> dict[str, Any]: ...


@runtime_checkable
class FetchLiveFeedPort(Protocol):
    def fetch(self, *, force_refresh: bool = False) -> dict[str, Any]: ...


@runtime_checkable
class BudgetGatePort(Protocol):
    def may_run(self, step: str, budget_token: Any | None = None) -> bool: ...


@runtime_checkable
class EnginePort(Protocol):
    def run(self, name: str, scratch: dict[str, Any]) -> dict[str, Any]: ...


@runtime_checkable
class DbReadPort(Protocol):
    def learning_stats(self) -> dict[str, Any]: ...

    def knowledge_search(self, query: str = "") -> list[dict[str, Any]]: ...

    def memory_recall(self, session_id: str = "") -> dict[str, Any]: ...


@dataclass
class InertFetchFixture:
    """Stub FetchFixture — returns empty / not-found by default."""

    response: dict[str, Any] = field(
        default_factory=lambda: {"fixture_id": 0, "found": False}
    )

    def fetch(
        self,
        *,
        home: str | None = None,
        away: str | None = None,
        force_refresh: bool = False,
        soft: bool = True,
    ) -> dict[str, Any]:
        out = dict(self.response)
        out.setdefault("home", home)
        out.setdefault("away", away)
        out.setdefault("force_refresh", force_refresh)
        out.setdefault("soft", soft)
        return out


@dataclass
class InertFetchLiveFeed:
    response: dict[str, Any] = field(default_factory=lambda: {"items": []})

    def fetch(self, *, force_refresh: bool = False) -> dict[str, Any]:
        out = dict(self.response)
        out["force_refresh"] = force_refresh
        return out


@dataclass
class InertBudgetGate:
    """Consult-only stub — never calls begin_request / end_request."""

    allow: bool = True

    def may_run(self, step: str, budget_token: Any | None = None) -> bool:
        return bool(self.allow)


@dataclass
class InertEnginePort:
    """Consume-only engine stub — no Frozen module imports."""

    results: dict[str, dict[str, Any]] = field(default_factory=dict)

    def run(self, name: str, scratch: dict[str, Any]) -> dict[str, Any]:
        return dict(self.results.get(name) or {"engine": name, "stub": True})


@dataclass
class InertDbReadPort:
    """Read-adapter stub — not Tool Registry; not CM write."""

    stats: dict[str, Any] = field(default_factory=dict)
    knowledge: list[dict[str, Any]] = field(default_factory=list)
    memory: dict[str, Any] = field(default_factory=dict)

    def learning_stats(self) -> dict[str, Any]:
        return dict(self.stats)

    def knowledge_search(self, query: str = "") -> list[dict[str, Any]]:
        return list(self.knowledge)

    def memory_recall(self, session_id: str = "") -> dict[str, Any]:
        out = dict(self.memory)
        out.setdefault("session_id", session_id)
        return out


@dataclass
class ProductionDbReadPort:
    """
    Phase 4 Stage 1 — thin-report Db read adapter.

    Calls learning_db / knowledge_db read APIs only. Never CM write.
    Never Tool Registry. Used when EM thin pipelines are flag-armed.
    """

    def learning_stats(self) -> dict[str, Any]:
        from src.learning_db import get_learning_stats

        return get_learning_stats()

    def knowledge_search(self, query: str = "") -> list[dict[str, Any]]:
        from src.knowledge_db import search_knowledge_items

        return search_knowledge_items(query, limit=6)

    def memory_recall(self, session_id: str = "") -> dict[str, Any]:
        return {"session_id": session_id}


@dataclass
class PrefetchedLiveFeed:
    """
    Phase 4 Stage 2 — inject an already-fetched live feed (async shim prefetch).

    Preferred under a running event loop; avoids nested asyncio.run.
    """

    response: dict[str, Any] = field(default_factory=lambda: {"matches": []})

    def fetch(self, *, force_refresh: bool = False) -> dict[str, Any]:
        out = dict(self.response)
        out.setdefault("force_refresh", force_refresh)
        return out


@dataclass
class ProductionFetchLiveFeedPort:
    """
    Phase 4 Stage 2 — FetchLiveFeed adapter (Tool Use live list port).

    Sync bridge to `routers.live._build_live_response`. When already inside a
    running event loop, callers must use PrefetchedLiveFeed instead.
    """

    def fetch(self, *, force_refresh: bool = False) -> dict[str, Any]:
        from src.routers.live import _build_live_response

        coro = _build_live_response()
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            out = asyncio.run(coro)
            if isinstance(out, dict):
                out = dict(out)
                out["force_refresh"] = force_refresh
                return out
            return {"matches": [], "force_refresh": force_refresh}
        raise RuntimeError(
            "ProductionFetchLiveFeedPort.fetch cannot block under a running "
            "event loop — use PrefetchedLiveFeed from the async Router shim"
        )


@dataclass
class ProductionLiveEnginePort:
    """
    Phase 4 Stage 2 — consume-only Frozen live intelligence adapter.

    Invokes `build_live_payload` only. Never attach_match_card. Never CM write.
    """

    def run(self, name: str, scratch: dict[str, Any]) -> dict[str, Any]:
        if name != "live_intelligence":
            return {"engine": name, "error": "unknown_engine"}
        from src.brain import get_brain_meta
        from src.core.live_intelligence_engine import build_live_payload

        feed = scratch.get("feed") or {}
        if isinstance(feed, list):
            fixtures = list(feed)
        elif isinstance(feed, dict):
            fixtures = list(feed.get("matches") or feed.get("fixtures") or [])
        else:
            fixtures = []
        return build_live_payload(fixtures, get_brain_meta())


@dataclass
class PortBundle:
    """Injectable port bundle for Step Runner / pipeline stubs."""

    fetch_fixture: FetchFixturePort = field(default_factory=InertFetchFixture)
    fetch_live_feed: FetchLiveFeedPort = field(default_factory=InertFetchLiveFeed)
    budget_gate: BudgetGatePort = field(default_factory=InertBudgetGate)
    engine: EnginePort = field(default_factory=InertEnginePort)
    db: DbReadPort = field(default_factory=InertDbReadPort)
