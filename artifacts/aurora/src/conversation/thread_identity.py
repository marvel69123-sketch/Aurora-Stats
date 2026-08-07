"""
Mission 016 Phase 2 — Session→thread_id mapper (C11).

Spec §13.1: thread_id = "sts:" || hex(SHA-256(UTF-8(session_id)))[0:32]
Empty / anon / whitespace-only → reject (fail-closed).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

CHECKPOINT_NS = "aurora.context_manager.sts"
_THREAD_PREFIX = "sts:"
_HEX_LEN = 32
_THREAD_ID_RE = re.compile(rf"^{re.escape(_THREAD_PREFIX)}[0-9a-f]{{{_HEX_LEN}}}$")


class SessionIdentityError(ValueError):
    """Empty/anon session_id rejected per Spec §13.1."""

    def __init__(self, reason: str = "empty_or_anon_session_id"):
        self.reason = reason
        self.http_status = 400
        super().__init__(reason)


@dataclass(frozen=True)
class ThreadIdentity:
    session_id: str
    thread_id: str
    checkpoint_ns: str = CHECKPOINT_NS

    @property
    def length(self) -> int:
        return len(self.thread_id)


def _is_empty_or_anon(session_id: str | None) -> bool:
    if session_id is None:
        return True
    s = str(session_id).strip()
    if not s:
        return True
    # Anonymous placeholders must not coalesce into a shared thread.
    if s.lower() in {"anon", "anonymous", "null", "none", "undefined"}:
        return True
    return False


def map_session_to_thread_id(session_id: str | None) -> str:
    """
    Deterministic Spec §13.1 mapping. Raises SessionIdentityError on empty/anon.
    """
    if _is_empty_or_anon(session_id):
        raise SessionIdentityError("empty_or_anon_session_id")
    digest = hashlib.sha256(str(session_id).encode("utf-8")).hexdigest()
    thread_id = f"{_THREAD_PREFIX}{digest[:_HEX_LEN]}"
    assert len(thread_id) == 4 + _HEX_LEN
    assert _THREAD_ID_RE.match(thread_id)
    return thread_id


def resolve_thread_identity(session_id: str | None) -> ThreadIdentity:
    tid = map_session_to_thread_id(session_id)
    return ThreadIdentity(
        session_id=str(session_id).strip(),
        thread_id=tid,
        checkpoint_ns=CHECKPOINT_NS,
    )


def is_valid_thread_id(thread_id: str | None) -> bool:
    if not thread_id or not isinstance(thread_id, str):
        return False
    return bool(_THREAD_ID_RE.match(thread_id))
