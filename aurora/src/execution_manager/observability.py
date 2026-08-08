"""EM observability hooks — no-op sinks in Phase 2 (Spec §10 / Plan §13)."""

from __future__ import annotations

from typing import Any, Callable

EventSink = Callable[[str, dict[str, Any]], None]


def _noop_sink(event: str, payload: dict[str, Any]) -> None:
    return None


_sink: EventSink = _noop_sink


def set_event_sink(sink: EventSink | None) -> None:
    global _sink
    _sink = sink or _noop_sink


def emit(event: str, **payload: Any) -> None:
    _sink(event, dict(payload))
