"""
P3-A — Run real fixture corpus through analyze_fixture (soft) and emit ops reports.

Observability only. Does not modify Gateway/Cache/NMB/DRS modules.
Uses live API-Football when API_FOOTBALL_KEY is configured.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Real named pairs across major competitions (user utterances → analyze).
# Fiction control included to measure non-resolve honesty.
REAL_CORPUS: list[tuple[str, str, str]] = [
    # Brazil
    ("Flamengo", "Palmeiras", "BR Serie A"),
    ("Corinthians", "Sao Paulo", "BR Serie A"),
    ("Atletico-MG", "Cruzeiro", "BR Serie A"),
    ("Fluminense", "Botafogo", "BR Serie A"),
    ("Internacional", "Gremio", "BR Serie A"),
    # England
    ("Manchester City", "Arsenal", "EPL"),
    ("Liverpool", "Chelsea", "EPL"),
    ("Manchester United", "Tottenham", "EPL"),
    ("Newcastle", "Aston Villa", "EPL"),
    # Spain
    ("Barcelona", "Real Madrid", "La Liga"),
    ("Atletico Madrid", "Sevilla", "La Liga"),
    ("Real Sociedad", "Athletic Club", "La Liga"),
    # Italy
    ("Inter", "AC Milan", "Serie A"),
    ("Juventus", "Napoli", "Serie A"),
    ("Roma", "Lazio", "Serie A"),
    # Germany
    ("Bayern Munich", "Borussia Dortmund", "Bundesliga"),
    ("RB Leipzig", "Bayer Leverkusen", "Bundesliga"),
    # France
    ("PSG", "Marseille", "Ligue 1"),
    ("Lyon", "Monaco", "Ligue 1"),
    # Internationals / cups style
    ("Brazil", "Argentina", "International"),
    ("Portugal", "Spain", "International"),
    ("France", "Germany", "International"),
    # Ambiguous / lower coverage probes
    ("Benfica", "Porto", "Primeira Liga"),
    ("Ajax", "Plymouth", "Cross / weak"),  # likely miss or odd
    ("MLS All Stars", "Unknown FC", "Fiction-like"),
    # Replay-seeded real asks
    ("Argentina", "Brazil", "International"),
    ("Barcelona", "Real Madrid", "La Liga"),
    ("Flamengo", "Palmeiras", "BR Serie A"),
    ("Liverpool", "Chelsea", "EPL"),
    ("Goku", "Naruto", "Fiction"),
]


async def _install_provider_probe() -> None:
    """Wrap gateway fetcher to record latency/failures without editing gateway.py."""
    from src.client import api_football_get
    from src.data.gateway import get_gateway
    from src.ops.live_density import ProviderCall, get_collector

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
            hint = None
            if "429" in detail:
                hint = "429"
            elif "401" in detail or "403" in detail:
                hint = "auth"
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

    get_gateway().set_fetcher(probed)


async def run_corpus() -> dict:
    from src.ops.live_density import get_collector, record_analyze_sample, reset_collector_for_tests
    from src.routers.analyze import analyze_fixture

    reset_collector_for_tests()
    key_present = bool(os.environ.get("API_FOOTBALL_KEY"))
    await _install_provider_probe()

    rows: list[dict] = []
    for home, away, league_hint in REAL_CORPUS:
        t0 = time.perf_counter()
        try:
            payload = await analyze_fixture(
                home=home, away=away, prefer_live=False, soft=True
            )
            err = None
        except Exception as exc:
            payload = {
                "_partial": True,
                "fixture": {"id": 0},
                "teams": {
                    "home": {"name": home},
                    "away": {"name": away},
                },
                "league": {"name": league_hint},
                "_drs": {"drs": 0, "tier": "T0", "missing": ["fixture"], "confirmed": []},
                "_data_plane": {"drs": 0, "tier": "T0"},
            }
            err = str(exc)[:200]
        elapsed = (time.perf_counter() - t0) * 1000.0
        # analyze_fixture already stamps ops collector (avoid double-count)
        col = get_collector()
        sample = col.samples[-1] if col.samples else record_analyze_sample(
            payload,
            home=home,
            away=away,
            league_hint=league_hint,
            elapsed_ms=elapsed,
        )
        # overlay league_hint + latency for reporting
        sample.league_hint = league_hint
        sample.elapsed_ms = elapsed
        rows.append(
            {
                "home": home,
                "away": away,
                "league_hint": league_hint,
                "resolved": sample.resolved,
                "fixture_id": sample.fixture_id,
                "league_name": sample.league_name,
                "drs": sample.drs,
                "tier": sample.tier,
                "premium_analysis": sample.premium_analysis,
                "soft_miss": sample.soft_miss,
                "narrative_present": sample.narrative_present,
                "calendar_empty": sample.calendar_empty,
                "elapsed_ms": round(elapsed, 1),
                "error": err,
                "missing": sample.missing_signals[:12],
            }
        )
        # gentle pacing for rate limits
        await asyncio.sleep(0.35)

    summary = get_collector().summarize()
    summary["api_key_configured"] = key_present
    summary["corpus_size"] = len(REAL_CORPUS)
    summary["mode"] = "live_api" if key_present else "soft_no_key"
    summary["rows"] = rows
    return summary


def _write_reports(summary: dict) -> None:
    out = ROOT / "roadmap"
    out.mkdir(exist_ok=True)
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")

    live_density = {
        "generated_at": ts,
        "wave": "p3a_operational",
        "api_key_configured": summary.get("api_key_configured"),
        "mode": summary.get("mode"),
        "sample_count": summary.get("sample_count"),
        "resolve_rate": summary.get("resolve_rate"),
        "soft_miss_rate": summary.get("soft_miss_rate"),
        "drs_live_distribution": summary.get("drs_live_distribution"),
        "t3_t4_live_rate": summary.get("t3_t4_live_rate"),
        "pct_drs_ge_60": summary.get("pct_drs_ge_60"),
        "premium_fixture_rate": summary.get("premium_fixture_rate"),
        "narrative_usage_rate": summary.get("narrative_usage_rate"),
        "calendar_empty_rate": summary.get("calendar_empty_rate"),
        "mean_drs": summary.get("mean_drs"),
        "mean_analyze_latency_ms": summary.get("mean_analyze_latency_ms"),
        "coverage_means": summary.get("coverage_means"),
        "by_league": summary.get("by_league"),
        "signals_limiting_t3_t4": summary.get("signals_limiting_t3_t4"),
    }
    (out / "live_density_metrics.json").write_text(
        json.dumps(live_density, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    provider = dict(summary.get("provider") or {})
    if not summary.get("api_key_configured"):
        provider["health"] = "not_configured"
        provider["limiting_factor"] = "API_FOOTBALL_KEY"
        provider["limiting_paths"] = ["*"]
    provider_report = {
        "generated_at": ts,
        "provider": "api-football",
        "health": provider.get("health"),
        "provider_failure_rate": provider.get("provider_failure_rate"),
        "provider_latency_ms": provider.get("provider_latency_ms"),
        "calls": provider.get("calls"),
        "by_path": provider.get("by_path"),
        "limiting_paths": provider.get("limiting_paths"),
        "limiting_factor": provider.get("limiting_factor"),
        "api_key_configured": summary.get("api_key_configured"),
        "notes": [],
    }
    if not summary.get("api_key_configured"):
        provider_report["notes"].append(
            "API_FOOTBALL_KEY missing — gateway fetcher never reached network; "
            "resolve_rate/soft_miss reflect auth/config block, not league coverage."
        )
        provider_report["notes"].append(
            "Re-run: set API_FOOTBALL_KEY then "
            "`python roadmap/scripts/run_p3a_operational_corpus.py`"
        )
    (out / "provider_health_report.json").write_text(
        json.dumps(provider_report, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    rows = summary.get("rows") or []
    premium_rows = [r for r in rows if r.get("premium_analysis")]
    premium_report = {
        "generated_at": ts,
        "premium_fixture_rate": summary.get("premium_fixture_rate"),
        "t3_t4_live_rate": summary.get("t3_t4_live_rate"),
        "pct_drs_ge_60": summary.get("pct_drs_ge_60"),
        "premium_count": len(premium_rows),
        "sample_count": summary.get("sample_count"),
        "premium_fixtures": premium_rows,
        "non_premium_resolved": [
            r for r in rows if r.get("resolved") and not r.get("premium_analysis")
        ],
        "unresolved": [r for r in rows if not r.get("resolved")],
    }
    (out / "premium_fixture_report.json").write_text(
        json.dumps(premium_report, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Operational answers
    resolve = summary.get("resolve_rate")
    t3t4 = summary.get("t3_t4_live_rate")
    drs60 = summary.get("pct_drs_ge_60")
    prem = summary.get("premium_fixture_rate")
    soft = summary.get("soft_miss_rate")
    health = provider.get("health")
    limiting = provider.get("limiting_paths") or []
    by_league = summary.get("by_league") or {}
    low_leagues = sorted(
        (
            (name, info)
            for name, info in by_league.items()
            if info.get("n", 0) >= 1
        ),
        key=lambda kv: (kv[1].get("t3_t4_rate", 0), kv[1].get("resolve_rate", 0)),
    )[:8]
    signal_limit = summary.get("signals_limiting_t3_t4") or {}

    thin_ok = bool(
        summary.get("api_key_configured")
        and (resolve or 0) >= 0.5
        and (drs60 or 0) >= 0.35
    )
    thin_verdict = (
        "YES — enough density for Thin Premium pilot"
        if thin_ok
        else "NO / CONDITIONAL — density below Thin Premium bar (need live resolve + DRS≥60)"
    )
    if not summary.get("api_key_configured"):
        thin_verdict = (
            "NO — cannot certify live density without API_FOOTBALL_KEY; "
            "re-run with key for GO/NO-GO"
        )

    report = f"""# P3-A — Operational Intelligence Report

**Date:** {time.strftime('%Y-%m-%d')}  
**Mode:** `{summary.get('mode')}`  
**API key configured:** {summary.get('api_key_configured')}  
**Corpus:** {summary.get('corpus_size')} real named pairs (multi-league + fiction controls)  
**Freeze:** P0 · P1 · P2.5 · P2b (Gateway/Cache/NMB/DRS/Waves) **not modified**

---

## Mandatory metrics

| Metric | Value |
|--------|------:|
| resolve_rate | **{resolve}** |
| t3_t4_live_rate | **{t3t4}** |
| pct_drs_ge_60 / DRS≥60 | **{drs60}** |
| premium_fixture_rate | **{prem}** |
| soft_miss_rate | **{soft}** |
| narrative_usage_rate | {summary.get('narrative_usage_rate')} |
| calendar_empty_rate | {summary.get('calendar_empty_rate')} |
| mean_drs | {summary.get('mean_drs')} |
| mean_analyze_latency_ms | {summary.get('mean_analyze_latency_ms')} |
| provider_health | **{health}** |
| provider_failure_rate | {provider.get('provider_failure_rate')} |
| provider_latency p50/p95 ms | {(provider.get('provider_latency_ms') or {}).get('p50')} / {(provider.get('provider_latency_ms') or {}).get('p95')} |

DRS distribution: `{summary.get('drs_live_distribution')}`

---

## Criteria answers

### 1. Aurora já possui densidade suficiente para Thin Premium?

**{thin_verdict}**

Bar used: resolve_rate ≥ 0.50 and pct_drs_ge_60 ≥ 0.35 with live API key.

### 2. Quais ligas possuem baixa cobertura?

Lowest T3/T4 / resolve in this corpus:

| League | n | resolve | t3_t4 | soft_miss | mean_drs |
|--------|--:|--------:|------:|----------:|---------:|
"""
    for name, info in low_leagues:
        report += (
            f"| {name} | {info.get('n')} | {info.get('resolve_rate')} | "
            f"{info.get('t3_t4_rate')} | {info.get('soft_miss_rate')} | "
            f"{info.get('mean_drs')} |\n"
        )

    report += f"""

### 3. Qual é o novo teto operacional?

```text
operational_ceiling ≈ min(resolve_rate, provider_health, signal_density)
```

Current binding constraint: **{"provider/API access" if not summary.get("api_key_configured") else ("provider failures on " + ", ".join(limiting[:4]) if limiting else "fixture resolve + sparse secondary signals (xG/odds/XI)")}**.

Architecture (P2b) is no longer the ceiling — **live resolve × provider path health × secondary signal fill** is.

### 4. Quais sinais estão limitando T3/T4?

Among resolved-but-not-T3/T4 samples, missing signal frequencies:

`{json.dumps(signal_limit, ensure_ascii=False)}`

Coverage means: `{json.dumps(summary.get("coverage_means") or {}, ensure_ascii=False)}`

Provider limiting paths: `{limiting}`

---

## Recommendations

1. Re-run this script with `API_FOOTBALL_KEY` in a healthy window if mode was soft_no_key.  
2. Prioritize leagues with lowest `resolve_rate` / `t3_t4_rate` in `by_league`.  
3. If odds/lineups/xG dominate `signals_limiting_t3_t4`, keep Thin Premium gated on confirmed signals only.  
4. Instrument production analyze path via `src.ops.record_analyze_sample` (hook already available).  
5. Thin Premium GO only when live `pct_drs_ge_60 ≥ 0.50` on covered leagues (charter bar).

---

## Artifacts

- `roadmap/live_density_metrics.json`
- `roadmap/provider_health_report.json`
- `roadmap/premium_fixture_report.json`
- `roadmap/p3_operational_report.md`
"""
    (out / "p3_operational_report.md").write_text(report, encoding="utf-8")
    print(json.dumps({k: summary.get(k) for k in (
        "mode", "api_key_configured", "sample_count", "resolve_rate",
        "t3_t4_live_rate", "pct_drs_ge_60", "premium_fixture_rate",
        "soft_miss_rate", "provider",
    )}, indent=2, default=str))


def main() -> None:
    summary = asyncio.run(run_corpus())
    _write_reports(summary)


if __name__ == "__main__":
    main()
