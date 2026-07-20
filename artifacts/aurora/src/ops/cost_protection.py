"""
Emergency Cost Protection Mode (ECPM).

Preserves provider quota until renewal:
- per-user daily consultation budget (default 12, range 10–15)
- prefer cache / stale for simple analyses
- force_refresh only on explicit premium refresh requests
- metrics: cache_hit_rate, provider_calls_per_user, daily_budget_remaining

Does not modify engines / DRS / NMB formulas.
Activate per request via begin_request(); inactive contexts stay unrestricted
(certs / internal tools).
"""

from __future__ import annotations

import os
import threading
import time
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from datetime import date
from typing import Any


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, *, lo: int, hi: int) -> int:
    raw = os.environ.get(name)
    try:
        val = int(raw) if raw is not None else default
    except (TypeError, ValueError):
        val = default
    return max(lo, min(hi, val))


@dataclass
class CostProtectionConfig:
    enabled: bool = field(
        default_factory=lambda: _env_bool("EMERGENCY_COST_PROTECTION", True)
    )
    daily_limit_per_user: int = field(
        default_factory=lambda: _env_int(
            "COST_PROTECTION_DAILY_LIMIT", 12, lo=10, hi=15
        )
    )
    prefer_cache: bool = True
    allow_stale: bool = True
    analyze_cache_ttl_sec: float = 600.0  # duplicate suppression window


@dataclass
class UserDayStats:
    day: str
    queries: int = 0
    provider_calls: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    analyze_cache_hits: int = 0
    blocked_queries: int = 0
    force_refresh_queries: int = 0


_CONFIG = CostProtectionConfig()
_LOCK = threading.Lock()
_USERS: dict[str, UserDayStats] = {}

# Request-scoped
_active: ContextVar[bool] = ContextVar("ecpm_active", default=False)
_user_id: ContextVar[str] = ContextVar("ecpm_user", default="")
_force_refresh: ContextVar[bool] = ContextVar("ecpm_force_refresh", default=False)

# In-process analyze response cache + singleflight
_ANALYZE_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_ANALYZE_INFLIGHT: dict[str, Any] = {}


def get_config() -> CostProtectionConfig:
    return _CONFIG


def configure(**kwargs: Any) -> CostProtectionConfig:
    """Test/helper override."""
    for k, v in kwargs.items():
        if hasattr(_CONFIG, k):
            setattr(_CONFIG, k, v)
    return _CONFIG


def reset_cost_protection_for_tests() -> None:
    global _USERS, _ANALYZE_CACHE, _ANALYZE_INFLIGHT
    with _LOCK:
        _USERS = {}
        _ANALYZE_CACHE = {}
        _ANALYZE_INFLIGHT = {}
    configure(
        enabled=_env_bool("EMERGENCY_COST_PROTECTION", True),
        daily_limit_per_user=_env_int("COST_PROTECTION_DAILY_LIMIT", 12, lo=10, hi=15),
    )


def _today() -> str:
    return date.today().isoformat()


def _user_stats_unlocked(user_id: str) -> UserDayStats:
    uid = (user_id or "anonymous").strip() or "anonymous"
    day = _today()
    st = _USERS.get(uid)
    if st is None or st.day != day:
        st = UserDayStats(day=day)
        _USERS[uid] = st
    return st


def _user_stats(user_id: str) -> UserDayStats:
    with _LOCK:
        return _user_stats_unlocked(user_id)


def begin_request(
    user_id: str,
    *,
    force_refresh: bool = False,
) -> tuple[Token, Token, Token]:
    """Enter ECPM request scope (copilot / analyze HTTP)."""
    return (
        _active.set(True),
        _user_id.set((user_id or "anonymous").strip() or "anonymous"),
        _force_refresh.set(bool(force_refresh) and bool(_CONFIG.enabled)),
    )


def end_request(tokens: tuple[Token, Token, Token] | list[Token] | None) -> None:
    if not tokens:
        return
    ta, tu, tf = tokens[0], tokens[1], tokens[2]
    try:
        _force_refresh.reset(tf)
        _user_id.reset(tu)
        _active.reset(ta)
    except Exception:
        pass


def is_request_active() -> bool:
    return bool(_active.get())


def current_user_id() -> str:
    return _user_id.get() or "anonymous"


def is_force_refresh() -> bool:
    return bool(_force_refresh.get())


def is_enabled() -> bool:
    return bool(_CONFIG.enabled)


def network_allowed() -> bool:
    """
    Outside ECPM request scope: unrestricted (certs / internal).
    Inside scope: network allowed for cold misses; prefer_stale_cache()
    avoids refresh unless force_refresh (premium).
    """
    if not _CONFIG.enabled:
        return True
    if not is_request_active():
        return True
    return True


def prefer_stale_cache() -> bool:
    """Simple analyses: prefer stale over provider refresh."""
    if not _CONFIG.enabled or not is_request_active():
        return False
    if is_force_refresh():
        return False
    return bool(_CONFIG.prefer_cache and _CONFIG.allow_stale)


def set_force_refresh(value: bool) -> None:
    """Upgrade current request to premium refresh (no-op if inactive)."""
    if is_request_active():
        _force_refresh.set(bool(value) and bool(_CONFIG.enabled))


@dataclass
class BudgetDecision:
    allowed: bool
    remaining: int
    used: int
    limit: int
    reason: str | None = None
    served_from_cache: bool = False


def check_budget(user_id: str | None = None) -> BudgetDecision:
    uid = user_id or current_user_id()
    limit = int(_CONFIG.daily_limit_per_user)
    st = _user_stats(uid)
    used = st.queries
    remaining = max(0, limit - used)
    if not _CONFIG.enabled or not is_request_active():
        return BudgetDecision(True, remaining, used, limit)
    if used >= limit:
        return BudgetDecision(
            False, 0, used, limit, reason="daily_budget_exhausted"
        )
    return BudgetDecision(True, remaining, used, limit)


def consume_query(
    user_id: str | None = None,
    *,
    force_refresh: bool = False,
    from_analyze_cache: bool = False,
) -> BudgetDecision:
    """
    Count a user consultation.
    Cache-only duplicate serves still count as 1 consultation (product use),
    but callers may skip consume when purely internal.
    """
    uid = user_id or current_user_id()
    limit = int(_CONFIG.daily_limit_per_user)
    if not _CONFIG.enabled or not is_request_active():
        st = _user_stats(uid)
        return BudgetDecision(True, max(0, limit - st.queries), st.queries, limit)

    with _LOCK:
        st = _user_stats_unlocked(uid)
        if st.queries >= limit:
            st.blocked_queries += 1
            return BudgetDecision(
                False, 0, st.queries, limit, reason="daily_budget_exhausted"
            )
        st.queries += 1
        if force_refresh:
            st.force_refresh_queries += 1
        if from_analyze_cache:
            st.analyze_cache_hits += 1
        remaining = max(0, limit - st.queries)
        return BudgetDecision(
            True,
            remaining,
            st.queries,
            limit,
            served_from_cache=from_analyze_cache,
        )


def record_cache_hit(user_id: str | None = None) -> None:
    with _LOCK:
        st = _user_stats_unlocked(user_id or current_user_id())
        st.cache_hits += 1


def record_cache_miss(user_id: str | None = None) -> None:
    with _LOCK:
        st = _user_stats_unlocked(user_id or current_user_id())
        st.cache_misses += 1


def record_provider_call(user_id: str | None = None, n: int = 1) -> None:
    with _LOCK:
        st = _user_stats_unlocked(user_id or current_user_id())
        st.provider_calls += n


def analyze_cache_key(home: str, away: str, fixture_id: int | None = None) -> str:
    h = (home or "").strip().lower()
    a = (away or "").strip().lower()
    fid = int(fixture_id or 0)
    return f"analyze:{h}:{a}:{fid}"


def get_cached_analyze(key: str) -> dict[str, Any] | None:
    now = time.time()
    with _LOCK:
        ent = _ANALYZE_CACHE.get(key)
        if not ent:
            return None
        ts, payload = ent
        if now - ts > _CONFIG.analyze_cache_ttl_sec:
            _ANALYZE_CACHE.pop(key, None)
            return None
        return payload


def set_cached_analyze(key: str, payload: dict[str, Any]) -> None:
    with _LOCK:
        _ANALYZE_CACHE[key] = (time.time(), payload)


def metrics(user_id: str | None = None) -> dict[str, Any]:
    """Expose required ECPM metrics (+ helpers)."""
    uid = user_id or (current_user_id() if is_request_active() else None)
    limit = int(_CONFIG.daily_limit_per_user)
    global_hits = 0
    global_misses = 0
    global_provider = 0
    per_user: dict[str, Any] = {}
    with _LOCK:
        for u, st in _USERS.items():
            if st.day != _today():
                continue
            hits = st.cache_hits + st.analyze_cache_hits
            misses = st.cache_misses
            global_hits += hits
            global_misses += misses
            global_provider += st.provider_calls
            total = hits + misses
            per_user[u] = {
                "queries": st.queries,
                "provider_calls": st.provider_calls,
                "daily_budget_remaining": max(0, limit - st.queries),
                "cache_hit_rate": round(hits / total, 4) if total else None,
                "blocked_queries": st.blocked_queries,
                "force_refresh_queries": st.force_refresh_queries,
            }
    total_c = global_hits + global_misses
    out: dict[str, Any] = {
        "emergency_cost_protection": bool(_CONFIG.enabled),
        "daily_limit_per_user": limit,
        "cache_hit_rate": round(global_hits / total_c, 4) if total_c else None,
        "provider_calls_per_user": {
            u: v["provider_calls"] for u, v in per_user.items()
        },
        "daily_budget_remaining": {
            u: v["daily_budget_remaining"] for u, v in per_user.items()
        },
        "users": per_user,
        "prefer_cache": _CONFIG.prefer_cache,
        "allow_stale": _CONFIG.allow_stale,
    }
    if uid and uid in per_user:
        out["current_user"] = uid
        out["current"] = per_user[uid]
    return out
