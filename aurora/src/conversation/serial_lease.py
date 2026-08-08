"""
Mission 016 Phase 2 — Process-local serial lease (C16 scaffolding).

Spec FINDING-007 / CDR2-F5: queue FIFO per thread_id; wait bound 5000 ms →
HTTP 429; refuse merge. Multi-instance shared lease is NOT claimed here
(single-node / process-local only while multi-instance write unclaimed).

Production write path remains OFF — lease is scaffolding for later phases.
"""

from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Generator, Iterator

DEFAULT_LEASE_WAIT_MS = 5000


class LeaseTimeoutError(TimeoutError):
    """Serial lease wait exceeded — maps to HTTP 429."""

    def __init__(self, thread_id: str, wait_ms: int = DEFAULT_LEASE_WAIT_MS):
        self.thread_id = thread_id
        self.wait_ms = wait_ms
        self.http_status = 429
        super().__init__(
            f"serial lease timeout thread_id={thread_id} wait_ms={wait_ms}"
        )


@dataclass
class LeaseHandle:
    thread_id: str
    acquired_at: float
    token: str


class SerialLeaseStore:
    """
    Process-local mutex map keyed by thread_id.

    Not a shared multi-instance store (DEFER-017 remains open; P4 NO-GO if
    multi-instance write claimed without shared lease).
    """

    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._locks: dict[str, threading.Lock] = {}
        self._holders: dict[str, str] = {}

    def _lock_for(self, thread_id: str) -> threading.Lock:
        with self._guard:
            if thread_id not in self._locks:
                self._locks[thread_id] = threading.Lock()
            return self._locks[thread_id]

    def acquire(
        self,
        thread_id: str,
        *,
        wait_ms: int = DEFAULT_LEASE_WAIT_MS,
        token: str | None = None,
    ) -> LeaseHandle:
        if not thread_id or not isinstance(thread_id, str):
            raise ValueError("thread_id required")
        wait_s = max(0.0, float(wait_ms) / 1000.0)
        lock = self._lock_for(thread_id)
        ok = lock.acquire(timeout=wait_s)
        if not ok:
            raise LeaseTimeoutError(thread_id, wait_ms=wait_ms)
        tok = token or f"lease-{threading.get_ident()}-{time.time_ns()}"
        self._holders[thread_id] = tok
        return LeaseHandle(thread_id=thread_id, acquired_at=time.time(), token=tok)

    def release(self, handle: LeaseHandle | str) -> None:
        thread_id = handle.thread_id if isinstance(handle, LeaseHandle) else handle
        with self._guard:
            lock = self._locks.get(thread_id)
            self._holders.pop(thread_id, None)
        if lock is not None and lock.locked():
            try:
                lock.release()
            except RuntimeError:
                pass

    def is_held(self, thread_id: str) -> bool:
        return thread_id in self._holders

    @contextmanager
    def hold(
        self,
        thread_id: str,
        *,
        wait_ms: int = DEFAULT_LEASE_WAIT_MS,
    ) -> Generator[LeaseHandle, None, None]:
        handle = self.acquire(thread_id, wait_ms=wait_ms)
        try:
            yield handle
        finally:
            self.release(handle)


# Process-global default store (single-node scaffolding).
_DEFAULT_STORE = SerialLeaseStore()


def get_serial_lease_store() -> SerialLeaseStore:
    return _DEFAULT_STORE


def acquire_serial_lease(
    thread_id: str,
    *,
    wait_ms: int = DEFAULT_LEASE_WAIT_MS,
) -> LeaseHandle:
    return _DEFAULT_STORE.acquire(thread_id, wait_ms=wait_ms)


def release_serial_lease(handle: LeaseHandle | str) -> None:
    _DEFAULT_STORE.release(handle)


@contextmanager
def serial_lease(
    thread_id: str,
    *,
    wait_ms: int = DEFAULT_LEASE_WAIT_MS,
) -> Iterator[LeaseHandle]:
    with _DEFAULT_STORE.hold(thread_id, wait_ms=wait_ms) as handle:
        yield handle
