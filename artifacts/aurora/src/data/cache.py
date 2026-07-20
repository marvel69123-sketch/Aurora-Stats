"""
P2b Wave 1 — Hot (memory) + Warm (SQLite) cache with per-signal TTL.
Only stores confirmed | empty | error — never inferred inventions.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger(__name__)

Quality = Literal["confirmed", "empty", "error"]

# TTL seconds per signal class (Wave 1 defaults)
TTL_SEC: dict[str, float] = {
    "team": 86400.0,
    "fixture": 600.0,
    "fixture_live": 30.0,
    "statistics": 45.0,
    "statistics_pre": 600.0,
    "standings": 3600.0,
    "events": 30.0,
    "events_pre": 600.0,
    "status": 30.0,
    "empty_resolve": 180.0,
    # Wave 3
    "odds": 300.0,
    "odds_live": 45.0,
    "lineups": 900.0,
    "injuries": 1800.0,
    "calendar": 900.0,
}


@dataclass
class CacheEntry:
    key: str
    signal: str
    payload: Any
    quality: Quality
    fetched_at: float
    ttl_sec: float

    def fresh(self, *, now: float | None = None, max_age: float | None = None) -> bool:
        ts = now if now is not None else time.time()
        age = ts - self.fetched_at
        limit = max_age if max_age is not None else self.ttl_sec
        return age <= limit

    def age_sec(self, *, now: float | None = None) -> float:
        return (now if now is not None else time.time()) - self.fetched_at


class HotCache:
    def __init__(self, max_items: int = 2048) -> None:
        self._max = max_items
        self._data: dict[str, CacheEntry] = {}
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def get(
        self,
        key: str,
        *,
        max_age: float | None = None,
        allow_stale: bool = False,
    ) -> CacheEntry | None:
        with self._lock:
            ent = self._data.get(key)
            if ent is None:
                self.misses += 1
                return None
            if ent.fresh(max_age=max_age) or allow_stale:
                self.hits += 1
                return ent
            self.misses += 1
            return None

    def set(
        self,
        key: str,
        signal: str,
        payload: Any,
        *,
        quality: Quality,
        ttl_sec: float | None = None,
    ) -> CacheEntry:
        ttl = float(ttl_sec if ttl_sec is not None else TTL_SEC.get(signal, 300.0))
        ent = CacheEntry(
            key=key,
            signal=signal,
            payload=payload,
            quality=quality,
            fetched_at=time.time(),
            ttl_sec=ttl,
        )
        with self._lock:
            if len(self._data) >= self._max and key not in self._data:
                # drop oldest
                oldest = min(self._data.values(), key=lambda e: e.fetched_at)
                self._data.pop(oldest.key, None)
            self._data[key] = ent
        return ent

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


class WarmCache:
    """SQLite warm store for cross-process reuse."""

    def __init__(self, path: Path | None = None) -> None:
        root = Path(__file__).resolve().parents[2]
        self.path = path or (root / "observations" / "p2b_cache" / "warm_cache.sqlite3")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        with self._lock:
            con = sqlite3.connect(str(self.path))
            try:
                con.execute(
                    """
                    CREATE TABLE IF NOT EXISTS cache_entries (
                        key TEXT PRIMARY KEY,
                        signal TEXT NOT NULL,
                        payload TEXT NOT NULL,
                        quality TEXT NOT NULL,
                        fetched_at REAL NOT NULL,
                        ttl_sec REAL NOT NULL
                    )
                    """
                )
                con.commit()
            finally:
                con.close()

    def get(
        self,
        key: str,
        *,
        max_age: float | None = None,
        allow_stale: bool = False,
    ) -> CacheEntry | None:
        with self._lock:
            con = sqlite3.connect(str(self.path))
            try:
                row = con.execute(
                    "SELECT key, signal, payload, quality, fetched_at, ttl_sec "
                    "FROM cache_entries WHERE key=?",
                    (key,),
                ).fetchone()
            finally:
                con.close()
        if not row:
            return None
        ent = CacheEntry(
            key=row[0],
            signal=row[1],
            payload=json.loads(row[2]),
            quality=row[3],  # type: ignore[arg-type]
            fetched_at=float(row[4]),
            ttl_sec=float(row[5]),
        )
        if ent.fresh(max_age=max_age) or allow_stale:
            return ent
        return None

    def set(
        self,
        key: str,
        signal: str,
        payload: Any,
        *,
        quality: Quality,
        ttl_sec: float | None = None,
    ) -> None:
        ttl = float(ttl_sec if ttl_sec is not None else TTL_SEC.get(signal, 300.0))
        blob = json.dumps(payload, ensure_ascii=False, default=str)
        with self._lock:
            con = sqlite3.connect(str(self.path))
            try:
                con.execute(
                    """
                    INSERT OR REPLACE INTO cache_entries
                    (key, signal, payload, quality, fetched_at, ttl_sec)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (key, signal, blob, quality, time.time(), ttl),
                )
                con.commit()
            finally:
                con.close()


class DataCache:
    """L1 hot + L2 warm facade."""

    def __init__(
        self,
        hot: HotCache | None = None,
        warm: WarmCache | None = None,
        *,
        enable_warm: bool = True,
    ) -> None:
        self.hot = hot or HotCache()
        self.warm = warm if warm is not None else (WarmCache() if enable_warm else None)

    def get(
        self,
        key: str,
        *,
        max_age: float | None = None,
        allow_stale: bool = False,
    ) -> CacheEntry | None:
        ent = self.hot.get(key, max_age=max_age, allow_stale=allow_stale)
        if ent is not None:
            return ent
        if self.warm is None:
            return None
        ent = self.warm.get(key, max_age=max_age, allow_stale=allow_stale)
        if ent is not None:
            # promote
            self.hot.set(
                key,
                ent.signal,
                ent.payload,
                quality=ent.quality,
                ttl_sec=ent.ttl_sec,
            )
            # preserve original fetched_at by overwriting
            with self.hot._lock:
                stored = self.hot._data.get(key)
                if stored:
                    stored.fetched_at = ent.fetched_at
            return ent
        return None

    def set(
        self,
        key: str,
        signal: str,
        payload: Any,
        *,
        quality: Quality,
        ttl_sec: float | None = None,
        warm: bool = True,
    ) -> CacheEntry:
        ent = self.hot.set(key, signal, payload, quality=quality, ttl_sec=ttl_sec)
        if warm and self.warm is not None and quality in {"confirmed", "empty"}:
            try:
                self.warm.set(key, signal, payload, quality=quality, ttl_sec=ttl_sec)
            except Exception as exc:
                logger.warning("warm cache write failed: %s", exc)
        return ent


_CACHE: DataCache | None = None


def get_cache() -> DataCache:
    global _CACHE
    if _CACHE is None:
        _CACHE = DataCache()
    return _CACHE


def reset_cache_for_tests(*, enable_warm: bool = False) -> DataCache:
    global _CACHE
    _CACHE = DataCache(enable_warm=enable_warm)
    return _CACHE


def cache_key(signal: str, *parts: Any) -> str:
    return "data:" + signal + ":" + ":".join(str(p) for p in parts)
