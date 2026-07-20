"""
P3-A.1 / P3-A.2 — Live density certification.

P3-A.1: 100+ fixture certification.
P3-A.2: adaptive throttling, backoff, request budget, --lite mode.

Does NOT modify Gateway/Cache/NMB/DRS internals/engines/guards.
Uses existing analyze_fixture + ops collector; wraps gateway fetcher for latency + pacing.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Awaitable, Callable

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Active throttle for discovery + analyze (set by _install_provider_probe).
_ACTIVE_THROTTLE = None
_THROTTLED_GET: Callable[[str, dict | None], Awaitable[dict]] | None = None

# API-Football league ids
TOP_LEAGUES = {
    39: "EPL",
    140: "La Liga",
    135: "Serie A",
    78: "Bundesliga",
    61: "Ligue 1",
    71: "BR Serie A",
    2: "UCL",
    3: "UEL",
}
MID_LEAGUES = {
    94: "Primeira Liga",
    88: "Eredivisie",
    144: "Belgian Pro League",
    203: "Super Lig",
    128: "Argentina Liga",
    262: "Liga MX",
    253: "MLS",
    179: "Scottish Prem",
    40: "Championship",
    79: "2. Bundesliga",
}
LOW_LEAGUES = {
    98: "J1 League",
    292: "K League 1",
    307: "Saudi Pro League",
    113: "Allsvenskan",
    119: "Superliga DK",
    218: "Austrian Bundesliga",
    207: "Swiss Super League",
    345: "Czech Fortuna",
    106: "Ekstraklasa",
    197: "Super League Greece",
}

NAMED_SEED: list[tuple[str, str, str, str]] = [
    # (home, away, league_hint, bucket)
    ("Flamengo", "Palmeiras", "BR Serie A", "top"),
    ("Corinthians", "Sao Paulo", "BR Serie A", "top"),
    ("Fluminense", "Botafogo", "BR Serie A", "top"),
    ("Atletico Mineiro", "Cruzeiro", "BR Serie A", "top"),
    ("Manchester City", "Arsenal", "EPL", "top"),
    ("Liverpool", "Chelsea", "EPL", "top"),
    ("Manchester United", "Tottenham", "EPL", "top"),
    ("Newcastle", "Aston Villa", "EPL", "top"),
    ("Barcelona", "Real Madrid", "La Liga", "top"),
    ("Atletico Madrid", "Sevilla", "La Liga", "top"),
    ("Inter", "AC Milan", "Serie A", "top"),
    ("Juventus", "Napoli", "Serie A", "top"),
    ("Bayern Munich", "Borussia Dortmund", "Bundesliga", "top"),
    ("PSG", "Marseille", "Ligue 1", "top"),
    ("Benfica", "Porto", "Primeira Liga", "mid"),
    ("Ajax", "Plymouth", "Cross / weak", "low"),
    ("Brazil", "Argentina", "International", "mid"),
    ("Goku", "Naruto", "Fiction", "control"),
]


def _load_key_from_dotenv() -> bool:
    if os.environ.get("API_FOOTBALL_KEY"):
        return True
    for rel in (".env", "../.env", "../../.env"):
        path = ROOT / rel
        if not path.is_file():
            continue
        try:
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.strip().startswith("API_FOOTBALL_KEY="):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if val:
                        os.environ["API_FOOTBALL_KEY"] = val
                        return True
        except Exception:
            continue
    return bool(os.environ.get("API_FOOTBALL_KEY"))


async def _install_provider_probe(throttle=None):
    """Install latency probe + P3-A.2 adaptive throttle/budget around provider GETs."""
    global _ACTIVE_THROTTLE, _THROTTLED_GET

    from src.client import api_football_get
    from src.data.gateway import get_gateway
    from src.ops.adaptive_throttle import (
        AdaptiveThrottle,
        full_throttle_defaults,
        wrap_fetcher,
    )
    from src.ops.live_density import ProviderCall, get_collector

    if throttle is None:
        throttle = full_throttle_defaults()
    assert isinstance(throttle, AdaptiveThrottle)

    async def probed(path: str, params: dict | None = None) -> dict:
        t0 = time.perf_counter()
        try:
            data = await api_football_get(path, params or {})
            ms = (time.perf_counter() - t0) * 1000.0
            get_collector().record_provider(
                ProviderCall(path=path, ok=True, latency_ms=ms)
            )
            return data
        except Exception as exc:
            ms = (time.perf_counter() - t0) * 1000.0
            detail = str(exc)
            hint = "429" if "429" in detail else None
            get_collector().record_provider(
                ProviderCall(
                    path=path,
                    ok=False,
                    latency_ms=ms,
                    error=detail[:200],
                    status_hint=hint,
                )
            )
            raise

    throttled = wrap_fetcher(probed, throttle)
    _ACTIVE_THROTTLE = throttle
    _THROTTLED_GET = throttled
    get_gateway().set_fetcher(throttled)
    return throttle


async def _api_get(path: str, params: dict | None = None) -> dict:
    """Prefer throttled GET so discovery counts against the same request budget."""
    if _THROTTLED_GET is not None:
        return await _THROTTLED_GET(path, params)
    from src.client import api_football_get

    return await api_football_get(path, params or {})


def _pair_from_fixture(row: dict, bucket: str, phase: str) -> dict | None:
    try:
        home = ((row.get("teams") or {}).get("home") or {}).get("name")
        away = ((row.get("teams") or {}).get("away") or {}).get("name")
        league = ((row.get("league") or {}).get("name")) or "Unknown"
        lid = ((row.get("league") or {}).get("id"))
        fid = ((row.get("fixture") or {}).get("id"))
        status = str(
            ((row.get("fixture") or {}).get("status") or {}).get("short") or ""
        ).upper()
        if not home or not away:
            return None
        return {
            "home": str(home),
            "away": str(away),
            "league_hint": str(league),
            "league_id": int(lid) if lid is not None else None,
            "fixture_id_hint": int(fid) if fid is not None else None,
            "bucket": bucket,
            "phase": phase,
            "status_short": status,
        }
    except Exception:
        return None


async def _discover_corpus(
    min_n: int = 100,
    *,
    lite: bool = False,
) -> list[dict]:
    """Pull live + date-window fixtures from API; pad with named seeds."""
    pairs: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def _add(p: dict | None) -> None:
        if not p:
            return
        key = (p["home"].lower(), p["away"].lower())
        if key in seen:
            return
        seen.add(key)
        pairs.append(p)

    # Named seeds first (controls + known derbies)
    seeds = NAMED_SEED[:10] if lite else NAMED_SEED
    for home, away, hint, bucket in seeds:
        _add(
            {
                "home": home,
                "away": away,
                "league_hint": hint,
                "league_id": None,
                "fixture_id_hint": None,
                "bucket": bucket,
                "phase": "seed",
                "status_short": "",
            }
        )

    # Live sweep
    try:
        live = await _api_get("/fixtures", {"live": "all"})
        for row in live.get("response") or []:
            lid = ((row.get("league") or {}).get("id"))
            if lid in TOP_LEAGUES:
                bucket = "top"
            elif lid in MID_LEAGUES:
                bucket = "mid"
            else:
                bucket = "low"
            if lite and bucket == "low":
                continue
            _add(_pair_from_fixture(row, bucket=bucket, phase="live"))
    except Exception as exc:
        print("live sweep failed:", str(exc)[:160])
        if "request_budget_exhausted" in str(exc):
            return pairs

    # Pre-match / recent by date for league sets
    day_offsets = (0, 1) if lite else (-1, 0, 1, 2, 3)
    days = [
        datetime.now(timezone.utc).date() + timedelta(days=d) for d in day_offsets
    ]
    if lite:
        league_map = {**TOP_LEAGUES, **dict(list(MID_LEAGUES.items())[:4])}
    else:
        league_map = {**TOP_LEAGUES, **MID_LEAGUES, **LOW_LEAGUES}

    for lid, lname in league_map.items():
        bucket = (
            "top"
            if lid in TOP_LEAGUES
            else ("mid" if lid in MID_LEAGUES else "low")
        )
        for day in days:
            if len(pairs) >= min_n + (8 if lite else 40):
                break
            try:
                data = await _api_get(
                    "/fixtures",
                    {"league": lid, "season": day.year, "date": day.isoformat()},
                )
                rows = data.get("response") or []
                if not rows and day.month < 7:
                    data = await _api_get(
                        "/fixtures",
                        {
                            "league": lid,
                            "season": day.year - 1,
                            "date": day.isoformat(),
                        },
                    )
                    rows = data.get("response") or []
                for row in rows:
                    st = str(
                        ((row.get("fixture") or {}).get("status") or {}).get("short")
                        or ""
                    ).upper()
                    phase = (
                        "live"
                        if st in {"1H", "2H", "HT", "ET", "P", "LIVE"}
                        else "prematch"
                    )
                    _add(_pair_from_fixture(row, bucket=bucket, phase=phase))
                if not lite:
                    await asyncio.sleep(0.05)
            except Exception as exc:
                print(f"league {lid} date {day} failed:", str(exc)[:120])
                if "request_budget_exhausted" in str(exc):
                    return pairs
                if not lite:
                    await asyncio.sleep(0.1)

    # Next fixtures per top/mid league if still short
    if len(pairs) < min_n:
        next_map = {**TOP_LEAGUES, **MID_LEAGUES} if not lite else {**TOP_LEAGUES}
        for lid, lname in next_map.items():
            if len(pairs) >= min_n:
                break
            bucket = "top" if lid in TOP_LEAGUES else "mid"
            for season in (datetime.now(timezone.utc).year, datetime.now(timezone.utc).year - 1):
                try:
                    data = await _api_get(
                        "/fixtures",
                        {"league": lid, "season": season, "next": 8 if lite else 15},
                    )
                    for row in data.get("response") or []:
                        _add(
                            _pair_from_fixture(row, bucket=bucket, phase="prematch")
                        )
                    if data.get("response"):
                        break
                except Exception as exc:
                    if "request_budget_exhausted" in str(exc):
                        return pairs

    return pairs


async def run_certification(
    min_n: int = 100,
    *,
    mode: str = "full",
    budget: int | None = None,
) -> dict:
    from src.ops.adaptive_throttle import (
        RequestBudget,
        full_throttle_defaults,
        lite_throttle_defaults,
    )
    from src.ops.live_density import get_collector, reset_collector_for_tests
    from src.routers.analyze import analyze_fixture

    lite = mode == "lite"
    if lite and min_n >= 100:
        min_n = 24

    key_ok = _load_key_from_dotenv()
    if not key_ok:
        return {
            "status": "BLOCKED_NO_API_KEY",
            "api_key_configured": False,
            "sample_count": 0,
            "go_thin_premium": False,
            "verdict": "HOLD",
            "mode": mode,
            "note": (
                "Set API_FOOTBALL_KEY and re-run "
                + (
                    "run_p3a2_lite_certification.py"
                    if lite
                    else "run_p3a1_live_certification.py"
                )
            ),
        }

    reset_collector_for_tests()
    throttle = lite_throttle_defaults() if lite else full_throttle_defaults()
    if budget is not None:
        throttle.budget = RequestBudget(max_requests=int(budget))
    await _install_provider_probe(throttle)

    print(
        f"Discovering corpus from API… mode={mode} "
        f"budget={throttle.budget.max_requests} delay={throttle.current_delay_sec}s"
    )
    budget_hit = False
    try:
        corpus = await _discover_corpus(min_n=min_n, lite=lite)
    except Exception as exc:
        if "request_budget_exhausted" in str(exc):
            corpus = []
            budget_hit = True
            print("Discovery stopped: request budget exhausted")
        else:
            raise

    # Prefer diversity: keep all live, then fill
    live = [p for p in corpus if p.get("phase") == "live"]
    pre = [p for p in corpus if p.get("phase") != "live"]
    ordered = live + pre
    cap = min(40, len(ordered)) if lite else min(160, len(ordered))
    if len(ordered) < min_n:
        print(f"WARNING: only {len(ordered)} unique pairs discovered (<{min_n})")
    else:
        ordered = ordered[: max(min_n, cap)]

    print(f"Running analyze on {len(ordered)} fixtures…")
    rows: list[dict] = []
    for i, p in enumerate(ordered, 1):
        # Leave a small reserve so mid-analyze fan-out can finish one fixture
        if throttle.budget.remaining < 8:
            budget_hit = True
            print(
                f"Stopping early at {i - 1}/{len(ordered)}: "
                f"budget remaining={throttle.budget.remaining}"
            )
            break
        home, away = p["home"], p["away"]
        t0 = time.perf_counter()
        err = None
        try:
            # P3-A.6: reuse discovery fixture_id_hint; skip name re-resolve when set.
            _fid = p.get("fixture_id_hint")
            _analyze_kwargs: dict = {
                "home": home,
                "away": away,
                "prefer_live": (p.get("phase") == "live"),
                "soft": True,
            }
            if _fid is not None:
                try:
                    _fid_i = int(_fid)
                    if _fid_i > 0:
                        _analyze_kwargs["fixture_id"] = _fid_i
                except (TypeError, ValueError):
                    pass
            payload = await analyze_fixture(**_analyze_kwargs)
        except Exception as exc:
            detail = str(exc)
            if "request_budget_exhausted" in detail:
                budget_hit = True
                print(f"Budget exhausted during analyze at {i}/{len(ordered)}")
                break
            payload = {
                "_partial": True,
                "fixture": {"id": 0},
                "teams": {"home": {"name": home}, "away": {"name": away}},
                "league": {"name": p.get("league_hint")},
                "_drs": {"drs": 0, "tier": "T0", "missing": ["fixture"], "confirmed": []},
            }
            err = detail[:200]
        elapsed = (time.perf_counter() - t0) * 1000.0
        col = get_collector()
        sample = col.samples[-1] if col.samples else None
        if sample is None:
            from src.ops.live_density import record_analyze_sample

            sample = record_analyze_sample(
                payload,
                home=home,
                away=away,
                league_hint=p.get("league_hint"),
                elapsed_ms=elapsed,
            )
        sample.league_hint = p.get("league_hint")
        sample.elapsed_ms = elapsed
        rows.append(
            {
                "home": home,
                "away": away,
                "league_hint": p.get("league_hint"),
                "bucket": p.get("bucket"),
                "phase": p.get("phase"),
                "status_short_hint": p.get("status_short"),
                "resolved": sample.resolved,
                "fixture_id": sample.fixture_id,
                "league_name": sample.league_name,
                "drs": sample.drs,
                "tier": sample.tier,
                "premium_analysis": sample.premium_analysis,
                "soft_miss": sample.soft_miss,
                "elapsed_ms": round(elapsed, 1),
                "error": err,
                "missing": sample.missing_signals[:10],
            }
        )
        if i % 10 == 0:
            print(
                f"  …{i}/{len(ordered)} "
                f"budget={throttle.budget.used}/{throttle.budget.max_requests} "
                f"delay={throttle.current_delay_sec:.2f}s"
            )

    summary = get_collector().summarize()
    summary["api_key_configured"] = True
    summary["mode"] = mode
    summary["status"] = "BUDGET_EXHAUSTED" if budget_hit else "CERTIFIED_RUN"
    summary["corpus_planned"] = len(ordered)
    summary["rows"] = rows
    summary["throttle"] = throttle.as_dict()
    summary["bucket_mix"] = {
        "top": sum(1 for r in rows if r.get("bucket") == "top"),
        "mid": sum(1 for r in rows if r.get("bucket") == "mid"),
        "low": sum(1 for r in rows if r.get("bucket") == "low"),
        "control": sum(1 for r in rows if r.get("bucket") == "control"),
        "live_phase": sum(1 for r in rows if r.get("phase") == "live"),
        "prematch_phase": sum(1 for r in rows if r.get("phase") == "prematch"),
        "seed_phase": sum(1 for r in rows if r.get("phase") == "seed"),
    }

    # GO criteria (exclude pure fiction control from denominators optionally)
    real_rows = [r for r in rows if r.get("bucket") != "control"]
    n_real = max(1, len(real_rows))
    resolve_real = sum(1 for r in real_rows if r.get("resolved")) / n_real
    t3t4_real = sum(1 for r in real_rows if r.get("tier") in {"T3", "T4"}) / n_real
    drs60_real = sum(1 for r in real_rows if (r.get("drs") or 0) >= 60) / n_real
    premium_real = sum(1 for r in real_rows if r.get("premium_analysis")) / n_real

    prov = summary.get("provider") or {}
    health = prov.get("health") or "unknown"
    health_ok = health in {"healthy", "degraded"}  # degraded still acceptable if fail <70%

    # Lite mode: informational gates (same thresholds, labeled lite)
    go = (
        len(real_rows) >= (12 if lite else 50)
        and resolve_real >= 0.85
        and drs60_real >= 0.50
        and premium_real >= 0.50
        and health_ok
    )
    summary["certification"] = {
        "mode": mode,
        "resolve_rate_real": round(resolve_real, 4),
        "t3_t4_live_rate_real": round(t3t4_real, 4),
        "pct_drs_ge_60_real": round(drs60_real, 4),
        "premium_fixture_rate_real": round(premium_real, 4),
        "provider_health": health,
        "provider_failure_rate": prov.get("provider_failure_rate"),
        "provider_latency_ms": prov.get("provider_latency_ms"),
        "gates": {
            "resolve_ge_85": resolve_real >= 0.85,
            "drs60_ge_50": drs60_real >= 0.50,
            "premium_ge_50": premium_real >= 0.50,
            "provider_health_ok": health_ok,
            "sample_floor": len(real_rows) >= (12 if lite else 50),
        },
        "verdict": "GO" if go else "HOLD",
        "go_thin_premium": go and not lite,  # full cert only unlocks Thin Premium
        "lite_signal_only": lite,
    }
    # also expose headline rates on real subset
    summary["resolve_rate"] = round(resolve_real, 4)
    summary["t3_t4_live_rate"] = round(t3t4_real, 4)
    summary["pct_drs_ge_60"] = round(drs60_real, 4)
    summary["premium_fixture_rate"] = round(premium_real, 4)
    return summary


def _write_reports(summary: dict, mode: str = "full") -> None:
    out = ROOT / "roadmap"
    out.mkdir(exist_ok=True)
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")
    lite = mode == "lite" or summary.get("mode") == "lite"
    cert_md = "p3a2_lite_certification.md" if lite else "p3a_live_certification.md"
    cert_json = (
        "live_density_lite_certified.json" if lite else "live_density_certified.json"
    )
    how_script = (
        "python roadmap/scripts/run_p3a2_lite_certification.py"
        if lite
        else "python roadmap/scripts/run_p3a1_live_certification.py"
    )
    slo_name = "provider_slo_lite_report.json" if lite else "provider_slo_report.json"

    if summary.get("status") == "BLOCKED_NO_API_KEY":
        blocked = {
            "generated_at": ts,
            "status": "BLOCKED_NO_API_KEY",
            "verdict": "HOLD",
            "go_thin_premium": False,
            "api_key_configured": False,
            "sample_count": 0,
            "mode": mode,
            "note": summary.get("note"),
            "how_to_run": f"Set API_FOOTBALL_KEY then: {how_script}",
            "throttle": None,
        }
        (out / cert_json).write_text(
            json.dumps(blocked, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (out / slo_name).write_text(
            json.dumps(
                {
                    "generated_at": ts,
                    "provider": "api-football",
                    "provider_health": "not_configured",
                    "limiting_factor": "API_FOOTBALL_KEY",
                    "api_key_configured": False,
                    "mode": mode,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        if not lite:
            (out / "league_coverage_report.json").write_text(
                json.dumps(
                    {
                        "generated_at": ts,
                        "status": "BLOCKED_NO_API_KEY",
                        "degrading_leagues": [],
                        "all_leagues": [],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        title = (
            "P3-A.2 — Lite Certification"
            if lite
            else "P3-A.1 — Live Density Certification"
        )
        (out / cert_md).write_text(
            f"""# {title}

**Date:** {time.strftime('%Y-%m-%d')}  
**Status:** `BLOCKED_NO_API_KEY`  
**Verdict:** **HOLD**

## Blocker

`API_FOOTBALL_KEY` is not configured in this environment.  
Corpus discovery and analyze certification **did not run**.

## P3-A.2 controls (ready)

- Adaptive throttling
- Exponential backoff on 429/errors
- Request budget
- Lite certification mode

## How to certify

```powershell
$env:API_FOOTBALL_KEY = "<your key>"
$env:PYTHONPATH = "."
.\\venv\\Scripts\\python.exe roadmap\\scripts\\{'run_p3a2_lite_certification.py' if lite else 'run_p3a1_live_certification.py'}
```
""",
            encoding="utf-8",
        )
        print(json.dumps(blocked, indent=2))
        return

    cert = summary.get("certification") or {}
    prov = summary.get("provider") or {}
    by_league = summary.get("by_league") or {}
    throttle = summary.get("throttle") or {}

    live_cert = {
        "generated_at": ts,
        "status": summary.get("status"),
        "mode": summary.get("mode") or mode,
        "api_key_configured": summary.get("api_key_configured"),
        "sample_count": summary.get("sample_count"),
        "corpus_planned": summary.get("corpus_planned"),
        "bucket_mix": summary.get("bucket_mix"),
        "resolve_rate": summary.get("resolve_rate"),
        "t3_t4_live_rate": summary.get("t3_t4_live_rate"),
        "pct_drs_ge_60": summary.get("pct_drs_ge_60"),
        "premium_fixture_rate": summary.get("premium_fixture_rate"),
        "soft_miss_rate": summary.get("soft_miss_rate"),
        "drs_live_distribution": summary.get("drs_live_distribution"),
        "mean_drs": summary.get("mean_drs"),
        "mean_analyze_latency_ms": summary.get("mean_analyze_latency_ms"),
        "coverage_means": summary.get("coverage_means"),
        "signals_limiting_t3_t4": summary.get("signals_limiting_t3_t4"),
        "certification": cert,
        "gates": cert.get("gates"),
        "verdict": cert.get("verdict") or summary.get("verdict") or "HOLD",
        "throttle": throttle,
    }
    (out / cert_json).write_text(
        json.dumps(live_cert, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    slo = {
        "generated_at": ts,
        "provider": "api-football",
        "mode": summary.get("mode") or mode,
        "provider_health": prov.get("health") or cert.get("provider_health"),
        "provider_failure_rate": prov.get("provider_failure_rate"),
        "provider_latency_ms": prov.get("provider_latency_ms"),
        "calls": prov.get("calls"),
        "by_path": prov.get("by_path"),
        "limiting_paths": prov.get("limiting_paths"),
        "throttle": throttle,
        "slo": {
            "health_acceptable": (prov.get("health") in {"healthy", "degraded"}),
            "failure_rate_lt_35": (
                (prov.get("provider_failure_rate") or 1) < 0.35
                if prov.get("provider_failure_rate") is not None
                else False
            ),
            "p95_latency_lt_5000ms": (
                ((prov.get("provider_latency_ms") or {}).get("p95") or 99999) < 5000
            ),
        },
    }
    (out / slo_name).write_text(
        json.dumps(slo, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    degrading: list[dict] = []
    if not lite:
        league_rows = []
        for name, info in by_league.items():
            league_rows.append(
                {
                    "league": name,
                    **info,
                    "degrades_product": (
                        info.get("resolve_rate", 0) < 0.7
                        or info.get("t3_t4_rate", 0) < 0.35
                        or info.get("soft_miss_rate", 1) > 0.5
                    ),
                }
            )
        league_rows.sort(
            key=lambda r: (
                r.get("t3_t4_rate", 0),
                r.get("resolve_rate", 0),
                -r.get("soft_miss_rate", 0),
            )
        )
        league_report = {
            "generated_at": ts,
            "league_count": len(league_rows),
            "degrading_leagues": [r for r in league_rows if r.get("degrades_product")],
            "all_leagues": league_rows,
        }
        (out / "league_coverage_report.json").write_text(
            json.dumps(league_report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        degrading = league_report["degrading_leagues"][:12]

    verdict = cert.get("verdict") or summary.get("verdict") or "HOLD"
    gates = cert.get("gates") or {}
    title = (
        "P3-A.2 — Lite Certification"
        if lite
        else "P3-A.1 — Live Density Certification"
    )
    budget = (throttle.get("budget") or {}) if isinstance(throttle, dict) else {}

    md = f"""# {title}

**Date:** {time.strftime('%Y-%m-%d')}  
**Status:** `{summary.get('status')}`  
**Mode:** `{summary.get('mode') or mode}`  
**Verdict:** **{verdict}**  
**Samples:** {summary.get('sample_count')} (planned {summary.get('corpus_planned')})  
**Throttle budget used:** {budget.get('used', '?')}/{budget.get('max_requests', '?')}  
**Freeze:** engines / Gateway core / NMB / DRS **not modified**

---

## GO criteria

| Gate | Threshold | Result | Pass |
|------|-----------|-------:|:----:|
| resolve_rate | ≥ 85% | {cert.get('resolve_rate_real', summary.get('resolve_rate'))} | {'✅' if gates.get('resolve_ge_85') else '❌'} |
| pct_drs_ge_60 | ≥ 50% | {cert.get('pct_drs_ge_60_real', summary.get('pct_drs_ge_60'))} | {'✅' if gates.get('drs60_ge_50') else '❌'} |
| premium_fixture_rate | ≥ 50% | {cert.get('premium_fixture_rate_real', summary.get('premium_fixture_rate'))} | {'✅' if gates.get('premium_ge_50') else '❌'} |
| provider_health | healthy/degraded | {cert.get('provider_health') or prov.get('health')} | {'✅' if gates.get('provider_health_ok') else '❌'} |

**Verdict: {verdict}**  
{"Lite mode is signal-only; Thin Premium unlock still requires full P3-A.1 (≥100)." if lite else f"**Thin Premium: {verdict}**"}

---

## P3-A.2 pacing

| Control | Value |
|---------|------:|
| current_delay_sec | {throttle.get('current_delay_sec')} |
| rate_limit_hits | {throttle.get('rate_limit_hits')} |
| total_wait_sec | {throttle.get('total_wait_sec')} |
| budget_used | {budget.get('used')} |
| budget_max | {budget.get('max_requests')} |
| budget_rejected | {budget.get('rejected')} |

---

## Mandatory metrics

| Metric | Value |
|--------|------:|
| resolve_rate | **{summary.get('resolve_rate')}** |
| t3_t4_live_rate | **{summary.get('t3_t4_live_rate')}** |
| pct_drs_ge_60 | **{summary.get('pct_drs_ge_60')}** |
| premium_fixture_rate | **{summary.get('premium_fixture_rate')}** |
| soft_miss_rate | {summary.get('soft_miss_rate')} |
| provider_health | **{prov.get('health') or cert.get('provider_health')}** |
| mean_drs | {summary.get('mean_drs')} |
| mean_analyze_latency_ms | {summary.get('mean_analyze_latency_ms')} |

Bucket mix: `{summary.get('bucket_mix')}`

---
"""
    if not lite:
        md += "### Degrading leagues\n\n"
        md += "| League | n | resolve | t3_t4 | soft_miss | mean_drs |\n"
        md += "|--------|--:|--------:|------:|----------:|---------:|\n"
        for r in degrading:
            md += (
                f"| {r.get('league')} | {r.get('n')} | {r.get('resolve_rate')} | "
                f"{r.get('t3_t4_rate')} | {r.get('soft_miss_rate')} | {r.get('mean_drs')} |\n"
            )
        if not degrading:
            md += "| _(none flagged)_ | | | | | |\n"
        md += "\n---\n"

    md += f"""
## Artifacts

- `roadmap/{cert_json}`
- `roadmap/{slo_name}`
- `roadmap/{cert_md}`
"""
    (out / cert_md).write_text(md, encoding="utf-8")
    print(
        json.dumps(
            {
                "status": summary.get("status"),
                "mode": summary.get("mode") or mode,
                "verdict": verdict,
                "sample_count": summary.get("sample_count"),
                "resolve_rate": summary.get("resolve_rate"),
                "t3_t4_live_rate": summary.get("t3_t4_live_rate"),
                "pct_drs_ge_60": summary.get("pct_drs_ge_60"),
                "premium_fixture_rate": summary.get("premium_fixture_rate"),
                "provider_health": prov.get("health") or cert.get("provider_health"),
                "throttle": {
                    "budget_used": budget.get("used"),
                    "budget_max": budget.get("max_requests"),
                    "current_delay_sec": throttle.get("current_delay_sec"),
                    "rate_limit_hits": throttle.get("rate_limit_hits"),
                },
                "gates": gates,
            },
            indent=2,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="P3-A live density certification")
    parser.add_argument(
        "--lite",
        action="store_true",
        help="P3-A.2 lite mode: smaller corpus + tighter request budget",
    )
    parser.add_argument("--min-n", type=int, default=None, help="Minimum fixture count")
    parser.add_argument(
        "--budget",
        type=int,
        default=None,
        help="Max provider requests (overrides mode default)",
    )
    args = parser.parse_args()
    mode = "lite" if args.lite else "full"
    min_n = args.min_n if args.min_n is not None else (24 if args.lite else 100)
    summary = asyncio.run(
        run_certification(min_n=min_n, mode=mode, budget=args.budget)
    )
    _write_reports(summary, mode=mode)
    if summary.get("status") == "BLOCKED_NO_API_KEY":
        sys.exit(2)
    if (summary.get("certification") or {}).get("verdict") != "GO":
        sys.exit(1)


if __name__ == "__main__":
    main()
