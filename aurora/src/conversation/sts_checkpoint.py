"""
Mission 016 Phase 2 — STS Checkpoint store scaffolding (C10).

Dev backend: InMemory (default) + optional SQLite path.
Payload includes STS fields, subject_generation, projection plan, checksum,
schema version (Spec §13 / FINDING-003 / FINDING-023).

Corrupt / unexpected-shape hydrate → refuse → AUDIT → cold empty STS
(SUBJECT_RECOVERY_CLARIFY). Does not enable production write.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from src.conversation.sport_topic_state import SportTopicState
from src.conversation.thread_identity import CHECKPOINT_NS

logger = logging.getLogger(__name__)

CHECKPOINT_SCHEMA_VERSION = 1
UX_RECOVERY_CLARIFY = "SUBJECT_RECOVERY_CLARIFY"


@dataclass
class CheckpointRecord:
    thread_id: str
    schema_version: int
    subject_generation: int
    sts: dict[str, Any]
    projection_plan: dict[str, Any] = field(default_factory=dict)
    checksum: str = ""
    checkpoint_ns: str = CHECKPOINT_NS
    host_channels: dict[str, Any] = field(default_factory=dict)
    corrupt: bool = False
    unexpected_shape: bool = False
    recovery_ux: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _canonical_payload(data: dict[str, Any]) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8"
    )


def compute_checksum(
    *,
    sts: dict[str, Any],
    subject_generation: int,
    projection_plan: dict[str, Any],
    schema_version: int = CHECKPOINT_SCHEMA_VERSION,
) -> str:
    body = {
        "schema_version": schema_version,
        "subject_generation": subject_generation,
        "sts": sts,
        "projection_plan": projection_plan,
    }
    return hashlib.sha256(_canonical_payload(body)).hexdigest()


def build_checkpoint(
    thread_id: str,
    sts: SportTopicState | dict[str, Any],
    *,
    projection_plan: dict[str, Any] | None = None,
    host_channels: dict[str, Any] | None = None,
) -> CheckpointRecord:
    if isinstance(sts, SportTopicState):
        sts_dict = sts.to_dict()
        gen = int(getattr(sts, "subject_generation", 0) or 0)
    else:
        sts_dict = dict(sts or {})
        gen = int(sts_dict.get("subject_generation") or 0)
    plan = dict(projection_plan or {})
    checksum = compute_checksum(
        sts=sts_dict,
        subject_generation=gen,
        projection_plan=plan,
    )
    return CheckpointRecord(
        thread_id=thread_id,
        schema_version=CHECKPOINT_SCHEMA_VERSION,
        subject_generation=gen,
        sts=sts_dict,
        projection_plan=plan,
        checksum=checksum,
        host_channels=dict(host_channels or {}),
    )


def validate_checkpoint(record: CheckpointRecord | dict[str, Any]) -> CheckpointRecord:
    """
    Distinguish corruption (checksum fail) vs unexpected shape (schema/fields).
    On either: mark refuse flags; caller must cold-empty STS (single branch).
    """
    if isinstance(record, dict):
        rec = CheckpointRecord(
            thread_id=str(record.get("thread_id") or ""),
            schema_version=int(record.get("schema_version") or 0),
            subject_generation=int(record.get("subject_generation") or 0),
            sts=dict(record.get("sts") or {}),
            projection_plan=dict(record.get("projection_plan") or {}),
            checksum=str(record.get("checksum") or ""),
            checkpoint_ns=str(record.get("checkpoint_ns") or CHECKPOINT_NS),
            host_channels=dict(record.get("host_channels") or {}),
        )
    else:
        rec = record

    if rec.schema_version != CHECKPOINT_SCHEMA_VERSION:
        rec.unexpected_shape = True
        rec.recovery_ux = UX_RECOVERY_CLARIFY
        return rec
    if not isinstance(rec.sts, dict) or "episode_id" not in rec.sts:
        # lean STS always has episode_id after from_dict; missing = unexpected
        if not isinstance(rec.sts, dict):
            rec.unexpected_shape = True
            rec.recovery_ux = UX_RECOVERY_CLARIFY
            return rec

    expected = compute_checksum(
        sts=rec.sts,
        subject_generation=rec.subject_generation,
        projection_plan=rec.projection_plan,
        schema_version=rec.schema_version,
    )
    if expected != rec.checksum:
        rec.corrupt = True
        rec.recovery_ux = UX_RECOVERY_CLARIFY
    return rec


def refuse_contaminated_hydrate(
    record: CheckpointRecord,
) -> tuple[SportTopicState, dict[str, Any]]:
    """
    Single normative recovery branch (FINDING-023):
    refuse contaminated hydrate → AUDIT → cold empty STS → UX clarify.
    """
    reason = "checksum_corrupt" if record.corrupt else "unexpected_shape"
    audit = {
        "event": "STS_CHECKPOINT_REFUSE",
        "thread_id": record.thread_id,
        "reason": reason,
        "recovery_ux": UX_RECOVERY_CLARIFY,
        "schema_version": record.schema_version,
    }
    logger.warning(
        "[AUDIT] STS_CHECKPOINT_REFUSE thread_id=%s reason=%s ux=%s",
        record.thread_id,
        reason,
        UX_RECOVERY_CLARIFY,
    )
    return SportTopicState(), audit


class InMemoryCheckpointStore:
    """Dev/POC checkpointer keyed by thread_id."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: dict[str, dict[str, Any]] = {}

    def save(self, record: CheckpointRecord) -> CheckpointRecord:
        built = build_checkpoint(
            record.thread_id,
            record.sts,
            projection_plan=record.projection_plan,
            host_channels=record.host_channels,
        )
        with self._lock:
            self._data[built.thread_id] = built.to_dict()
        return built

    def load(self, thread_id: str) -> CheckpointRecord | None:
        with self._lock:
            raw = self._data.get(thread_id)
        if raw is None:
            return None
        return validate_checkpoint(raw)

    def delete(self, thread_id: str) -> None:
        with self._lock:
            self._data.pop(thread_id, None)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


class SqliteCheckpointStore:
    """Optional local SQLite durable backend (single-node staging scaffolding)."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=5.0)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sts_checkpoints (
                thread_id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        conn.commit()
        return conn

    def _init_db(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.close()
            finally:
                pass

    def save(self, record: CheckpointRecord) -> CheckpointRecord:
        import time

        built = build_checkpoint(
            record.thread_id,
            record.sts,
            projection_plan=record.projection_plan,
            host_channels=record.host_channels,
        )
        payload = json.dumps(built.to_dict(), default=str)
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO sts_checkpoints(thread_id, payload, updated_at)
                    VALUES(?, ?, ?)
                    ON CONFLICT(thread_id) DO UPDATE SET
                      payload=excluded.payload,
                      updated_at=excluded.updated_at
                    """,
                    (built.thread_id, payload, time.time()),
                )
                conn.commit()
            finally:
                conn.close()
        return built

    def load(self, thread_id: str) -> CheckpointRecord | None:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT payload FROM sts_checkpoints WHERE thread_id = ?",
                    (thread_id,),
                ).fetchone()
            finally:
                conn.close()
        if not row:
            return None
        raw = json.loads(row[0])
        return validate_checkpoint(raw)


_DEFAULT_STORE = InMemoryCheckpointStore()


def get_checkpoint_store() -> InMemoryCheckpointStore:
    return _DEFAULT_STORE


def hydrate_sts_from_checkpoint(
    thread_id: str,
    store: InMemoryCheckpointStore | SqliteCheckpointStore | None = None,
) -> tuple[SportTopicState, dict[str, Any]]:
    """
    Load + validate. On miss → cold empty. On corrupt/shape → refuse branch.
    """
    store = store or _DEFAULT_STORE
    rec = store.load(thread_id)
    meta: dict[str, Any] = {"thread_id": thread_id, "hit": rec is not None}
    if rec is None:
        meta["cold"] = True
        return SportTopicState(), meta
    if rec.corrupt or rec.unexpected_shape:
        sts, audit = refuse_contaminated_hydrate(rec)
        meta.update(audit)
        meta["refused"] = True
        return sts, meta
    sts = SportTopicState.from_dict(rec.sts)
    meta["subject_generation"] = rec.subject_generation
    meta["checksum_ok"] = True
    return sts, meta
