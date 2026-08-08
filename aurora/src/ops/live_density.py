"""
P3-A — Live density / operational metrics collector.

Observability only. Does not modify Gateway, Cache, NMB, DRS, or P0 guards.
Consumes analyze payloads + optional provider probe records.
"""

from __future__ import annotations

import threading
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


@dataclass
class ProviderCall:
    path: str
    ok: bool
    latency_ms: float
    error: str | None = None
    status_hint: str | None = None
    ts: float = field(default_factory=time.time)


@dataclass
class AnalyzeSample:
    home: str
    away: str
    league_hint: str | None
    league_name: str | None
    league_id: int | None
    fixture_id: int
    resolved: bool
    soft_miss: bool
    partial: bool
    drs: int
    tier: str
    premium_analysis: bool
    narrative_present: bool
    calendar_empty: bool
    rate_limited: bool
    missing_signals: list[str]
    confirmed_signals: list[str]
    xg_coverage: float
    odds_coverage: float
    lineup_coverage: float
    event_coverage: float
    provenance: dict[str, Any]
    elapsed_ms: float
    ts: float = field(default_factory=time.time)


class LiveDensityCollector:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.samples: list[AnalyzeSample] = []
        self.provider_calls: list[ProviderCall] = []

    def record_sample(self, sample: AnalyzeSample) -> None:
        with self._lock:
            self.samples.append(sample)

    def record_provider(self, call: ProviderCall) -> None:
        with self._lock:
            self.provider_calls.append(call)

    def clear(self) -> None:
        with self._lock:
            self.samples.clear()
            self.provider_calls.clear()

    def summarize(self) -> dict[str, Any]:
        with self._lock:
            samples = list(self.samples)
            calls = list(self.provider_calls)

        n = len(samples)
        if n == 0:
            return {
                "sample_count": 0,
                "resolve_rate": None,
                "note": "no_samples",
            }

        resolved = sum(1 for s in samples if s.resolved)
        soft_miss = sum(1 for s in samples if s.soft_miss)
        t3t4 = sum(1 for s in samples if s.tier in {"T3", "T4"})
        drs_ge_60 = sum(1 for s in samples if s.drs >= 60)
        premium = sum(1 for s in samples if s.premium_analysis)
        narrative = sum(1 for s in samples if s.narrative_present)
        cal_empty = sum(1 for s in samples if s.calendar_empty)

        tiers = Counter(s.tier for s in samples)
        league_stats: dict[str, dict[str, Any]] = {}
        for s in samples:
            key = s.league_name or s.league_hint or "Unknown"
            bucket = league_stats.setdefault(
                key,
                {
                    "n": 0,
                    "resolved": 0,
                    "t3_t4": 0,
                    "drs_ge_60": 0,
                    "soft_miss": 0,
                    "drs_sum": 0,
                },
            )
            bucket["n"] += 1
            bucket["resolved"] += int(s.resolved)
            bucket["t3_t4"] += int(s.tier in {"T3", "T4"})
            bucket["drs_ge_60"] += int(s.drs >= 60)
            bucket["soft_miss"] += int(s.soft_miss)
            bucket["drs_sum"] += s.drs

        for key, b in league_stats.items():
            nn = max(1, b["n"])
            b["resolve_rate"] = round(b["resolved"] / nn, 4)
            b["t3_t4_rate"] = round(b["t3_t4"] / nn, 4)
            b["drs_ge_60_rate"] = round(b["drs_ge_60"] / nn, 4)
            b["soft_miss_rate"] = round(b["soft_miss"] / nn, 4)
            b["mean_drs"] = round(b["drs_sum"] / nn, 2)
            del b["drs_sum"]

        # Signal gaps limiting T3/T4 among non-premium resolved
        miss_counter: Counter[str] = Counter()
        for s in samples:
            if s.resolved and s.tier not in {"T3", "T4"}:
                for m in s.missing_signals:
                    miss_counter[m] += 1

        return {
            "sample_count": n,
            "resolve_rate": round(resolved / n, 4),
            "soft_miss_rate": round(soft_miss / n, 4),
            "drs_live_distribution": dict(tiers),
            "t3_t4_live_rate": round(t3t4 / n, 4),
            "pct_drs_ge_60": round(drs_ge_60 / n, 4),
            "premium_fixture_rate": round(premium / n, 4),
            "narrative_usage_rate": round(narrative / n, 4),
            "calendar_empty_rate": round(cal_empty / n, 4),
            "mean_drs": round(sum(s.drs for s in samples) / n, 2),
            "mean_analyze_latency_ms": round(
                sum(s.elapsed_ms for s in samples) / n, 2
            ),
            "by_league": league_stats,
            "signals_limiting_t3_t4": dict(miss_counter.most_common(20)),
            "coverage_means": {
                "xg": round(sum(s.xg_coverage for s in samples) / n, 4),
                "odds": round(sum(s.odds_coverage for s in samples) / n, 4),
                "lineup": round(sum(s.lineup_coverage for s in samples) / n, 4),
                "events": round(sum(s.event_coverage for s in samples) / n, 4),
            },
            "provider": summarize_provider_calls(calls),
        }


def summarize_provider_calls(calls: list[ProviderCall]) -> dict[str, Any]:
    if not calls:
        return {
            "calls": 0,
            "provider_failure_rate": None,
            "provider_latency_ms": {},
            "by_path": {},
            "health": "unknown",
        }

    by_path: dict[str, dict[str, Any]] = {}
    for c in calls:
        b = by_path.setdefault(
            c.path,
            {"n": 0, "ok": 0, "fail": 0, "latencies": [], "errors": Counter()},
        )
        b["n"] += 1
        if c.ok:
            b["ok"] += 1
        else:
            b["fail"] += 1
            if c.error:
                b["errors"][str(c.error)[:120]] += 1
        b["latencies"].append(c.latency_ms)

    path_out: dict[str, Any] = {}
    all_lat: list[float] = []
    fails = 0
    for path, b in by_path.items():
        lats = b["latencies"]
        all_lat.extend(lats)
        fails += b["fail"]
        path_out[path] = {
            "n": b["n"],
            "ok_rate": round(b["ok"] / max(1, b["n"]), 4),
            "failure_rate": round(b["fail"] / max(1, b["n"]), 4),
            "latency_ms": {
                "p50": _percentile(lats, 50),
                "p95": _percentile(lats, 95),
                "mean": round(sum(lats) / len(lats), 2) if lats else None,
            },
            "top_errors": dict(b["errors"].most_common(5)),
        }

    fail_rate = round(fails / len(calls), 4)
    health = "healthy"
    if fail_rate >= 0.35:
        health = "degraded"
    if fail_rate >= 0.7:
        health = "critical"
    if not any(c.ok for c in calls):
        health = "down"

    return {
        "calls": len(calls),
        "provider_failure_rate": fail_rate,
        "provider_latency_ms": {
            "p50": _percentile(all_lat, 50),
            "p95": _percentile(all_lat, 95),
            "mean": round(sum(all_lat) / len(all_lat), 2) if all_lat else None,
        },
        "by_path": path_out,
        "health": health,
        "limiting_paths": [
            p
            for p, info in sorted(
                path_out.items(), key=lambda kv: kv[1]["failure_rate"], reverse=True
            )
            if info["failure_rate"] > 0
        ][:8],
    }


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    arr = sorted(values)
    if len(arr) == 1:
        return round(arr[0], 2)
    k = (len(arr) - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, len(arr) - 1)
    if f == c:
        return round(arr[f], 2)
    return round(arr[f] + (arr[c] - arr[f]) * (k - f), 2)


def sample_from_analyze_payload(
    data: dict[str, Any] | None,
    *,
    home: str,
    away: str,
    league_hint: str | None = None,
    elapsed_ms: float = 0.0,
) -> AnalyzeSample:
    data = data if isinstance(data, dict) else {}
    fx = data.get("fixture") or {}
    league = data.get("league") or {}
    fid = _safe_int(fx.get("id"), 0)
    partial = bool(data.get("_partial")) or fid <= 0
    resolved = (not partial) and fid > 0

    drs_block = data.get("_drs") if isinstance(data.get("_drs"), dict) else {}
    plane = data.get("_data_plane") if isinstance(data.get("_data_plane"), dict) else {}
    nmb = data.get("_nmb") if isinstance(data.get("_nmb"), dict) else {}
    deg = data.get("_degradation") if isinstance(data.get("_degradation"), dict) else {}
    inference = data.get("_inference") if isinstance(data.get("_inference"), dict) else {}

    drs = _safe_int(drs_block.get("drs") or plane.get("drs"), 0)
    tier = str(drs_block.get("tier") or plane.get("tier") or "T0")
    premium = bool(
        drs_block.get("premium_analysis")
        or plane.get("premium_analysis")
        or tier in {"T3", "T4"}
    )

    signals = nmb.get("signals") if isinstance(nmb.get("signals"), dict) else {}
    narr = signals.get("narrative") if isinstance(signals.get("narrative"), dict) else {}
    narrative_present = str(narr.get("quality") or "") == "confirmed"

    cal = signals.get("calendar") if isinstance(signals.get("calendar"), dict) else {}
    cal_quality = str(cal.get("quality") or "")
    cal_val = cal.get("value") if isinstance(cal.get("value"), dict) else {}
    calendar_empty = (not resolved) or (
        cal_quality in {"missing", "empty", "rate_limited"}
        and not (cal_val.get("match_date") or cal_val.get("kickoff"))
    )

    # Soft miss: secondary fetch failures / rate limit / empty stats after resolve
    prov = data.get("_signal_provenance") if isinstance(data.get("_signal_provenance"), dict) else {}
    soft_miss = False
    if resolved:
        for name in ("statistics", "events", "standings", "odds", "lineups"):
            info = prov.get(name) or {}
            q = str(info.get("quality") or "")
            src = str(info.get("source") or "")
            if q in {"missing", "rate_limited", "error"} or src in {"error"}:
                soft_miss = True
                break
        if not soft_miss:
            stats = data.get("statistics") or {}
            home_s = stats.get("home") if isinstance(stats, dict) else None
            if not isinstance(home_s, dict) or all(
                home_s.get(k) in (None, "", 0, "0")
                for k in ("shots_total", "possession", "xg", "corners")
            ):
                # resolved but hollow stats
                if str((signals.get("statistics") or {}).get("quality") or "") in {
                    "missing",
                    "rate_limited",
                    "empty",
                }:
                    soft_miss = True
    else:
        soft_miss = True

    rate_limited = bool(
        plane.get("rate_limited")
        or nmb.get("rate_limited")
        or any(
            "rate" in str(x).lower()
            for x in (inference.get("notes") or [])
        )
    )

    missing = list(drs_block.get("missing") or deg.get("missing_signals") or [])
    confirmed = list(drs_block.get("confirmed") or deg.get("confirmed_signals") or [])

    return AnalyzeSample(
        home=home,
        away=away,
        league_hint=league_hint,
        league_name=str(league.get("name") or "") or None,
        league_id=_safe_int(league.get("id"), 0) or None,
        fixture_id=fid,
        resolved=resolved,
        soft_miss=soft_miss,
        partial=partial,
        drs=drs,
        tier=tier,
        premium_analysis=premium,
        narrative_present=narrative_present,
        calendar_empty=calendar_empty,
        rate_limited=rate_limited,
        missing_signals=[str(m) for m in missing],
        confirmed_signals=[str(c) for c in confirmed],
        xg_coverage=float(plane.get("xg_coverage") or nmb.get("xg_coverage") or 0.0),
        odds_coverage=float(plane.get("odds_coverage") or nmb.get("odds_coverage") or 0.0),
        lineup_coverage=float(
            plane.get("lineup_coverage") or nmb.get("lineup_coverage") or 0.0
        ),
        event_coverage=float(
            plane.get("event_coverage") or nmb.get("event_coverage") or 0.0
        ),
        provenance=dict(prov),
        elapsed_ms=float(elapsed_ms),
    )


_COLLECTOR: LiveDensityCollector | None = None


def get_collector() -> LiveDensityCollector:
    global _COLLECTOR
    if _COLLECTOR is None:
        _COLLECTOR = LiveDensityCollector()
    return _COLLECTOR


def reset_collector_for_tests() -> LiveDensityCollector:
    global _COLLECTOR
    _COLLECTOR = LiveDensityCollector()
    return _COLLECTOR


def record_analyze_sample(
    data: dict[str, Any] | None,
    *,
    home: str,
    away: str,
    league_hint: str | None = None,
    elapsed_ms: float = 0.0,
) -> AnalyzeSample:
    sample = sample_from_analyze_payload(
        data,
        home=home,
        away=away,
        league_hint=league_hint,
        elapsed_ms=elapsed_ms,
    )
    get_collector().record_sample(sample)
    return sample
