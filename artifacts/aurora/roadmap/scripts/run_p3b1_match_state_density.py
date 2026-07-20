"""
P3-B.1 — Match-State Density Diagnosis (READ-ONLY).

Does NOT modify engines, DRS, NMB, Gateway, Resolve, or Cost Protection.
Measures signal density + premium by PREMATCH / LIVE / FINISHED.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_SCRIPT = Path(__file__).resolve().parent / "run_p3a1_live_certification.py"
_spec = importlib.util.spec_from_file_location("run_p3a1_live_certification", _SCRIPT)
assert _spec and _spec.loader
_p3a1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_p3a1)

from src.core.fixture_status import FINISHED_STATUSES, LIVE_STATUSES  # noqa: E402

# Diagnosis-only DRS point table (mirrors drs.py; does not change it)
UPLIFT = {
    "statistics": 12,
    "xg": 12,
    "standings": 10,
    "events": 8,
    "lineups": 11,
    "score": 4,
    "referee": 4,
    "live_momentum": 6,
    "odds": 10,
    "injuries": 2,
    "calendar": 7,
}

# Structurally expected empty in pure prematch (API usually blank until live/FT)
PREMATCH_STRUCTURAL_GAP = frozenset(
    {"statistics", "events", "score", "live_momentum", "xg"}
)
# Often available prematch
PREMATCH_EXPECTED = frozenset(
    {"lineups", "odds", "injuries", "standings", "calendar", "referee"}
)
LIVE_EXPECTED = frozenset(
    {"statistics", "events", "score", "live_momentum", "odds", "lineups"}
)
FINISHED_EXPECTED = frozenset(
    {"statistics", "events", "score", "xg", "standings", "lineups", "odds"}
)


def _state_of(status_short: str) -> str:
    s = str(status_short or "").strip().upper()
    if s in LIVE_STATUSES:
        return "LIVE"
    if s in FINISHED_STATUSES:
        return "FINISHED"
    if s in {"NS", "TBD", "PST", "CANC", "ABD"} or not s:
        return "PREMATCH"
    # SUSP already in LIVE; default unknown shorts → prematch-ish
    return "PREMATCH"


def _signal_present(nmb_signals: dict, name: str) -> bool:
    slot = nmb_signals.get(name) or {}
    if isinstance(slot, dict):
        q = str(slot.get("quality") or "").lower()
        return q in {"confirmed", "stale"}
    return False


def _coverage_from_payload(payload: dict) -> dict[str, float]:
    plane = payload.get("_data_plane") or {}
    nmb = payload.get("_nmb") or {}
    signals = nmb.get("signals") or {}
    drs = payload.get("_drs") or {}
    missing = set(drs.get("missing") or [])

    def cov(name: str, plane_key: str | None = None) -> float:
        if plane_key and plane.get(plane_key) is not None:
            try:
                return float(plane.get(plane_key) or 0.0)
            except (TypeError, ValueError):
                pass
        if name in ("statistics", "standings", "injuries", "live_momentum", "referee", "score"):
            return 1.0 if _signal_present(signals, name) else (
                0.0 if name in missing else (1.0 if _signal_present(signals, name) else 0.0)
            )
        # prefer explicit present
        if _signal_present(signals, name):
            return 1.0
        if name in missing:
            return 0.0
        return 0.0

    return {
        "statistics": cov("statistics"),
        "lineups": float(plane.get("lineup_coverage") or 0.0)
        if plane.get("lineup_coverage") is not None
        else cov("lineups"),
        "events": float(plane.get("event_coverage") or 0.0)
        if plane.get("event_coverage") is not None
        else cov("events"),
        "injuries": float(plane.get("injury_coverage") or 0.0)
        if plane.get("injury_coverage") is not None
        else cov("injuries"),
        "odds": float(plane.get("odds_coverage") or 0.0)
        if plane.get("odds_coverage") is not None
        else cov("odds"),
        "standings": cov("standings"),
        "xg": float(plane.get("xg_coverage") or 0.0)
        if plane.get("xg_coverage") is not None
        else cov("xg"),
        "momentum": cov("live_momentum"),
    }


def _simulate(drs: int, missing: list[str], fill: set[str]) -> int:
    gain = sum(UPLIFT.get(s, 0) for s in fill if s in missing)
    return max(0, min(100, int(drs) + gain))


async def run_diagnosis(min_n: int = 100) -> dict[str, Any]:
    from src.ops.adaptive_throttle import full_throttle_defaults
    from src.ops.live_density import get_collector, reset_collector_for_tests
    from src.routers.analyze import analyze_fixture

    if not _p3a1._load_key_from_dotenv():
        return {"status": "BLOCKED_NO_API_KEY"}

    # Ensure cert-style unrestricted path (no ECPM request scope)
    reset_collector_for_tests()
    throttle = full_throttle_defaults()
    await _p3a1._install_provider_probe(throttle)

    corpus = await _p3a1._discover_corpus(min_n=min_n, lite=False)
    ordered = ([p for p in corpus if p.get("phase") == "live"]
               + [p for p in corpus if p.get("phase") != "live"])
    ordered = ordered[: max(min_n, min(160, len(ordered)))]
    print(f"P3-B.1 diagnosing {len(ordered)} fixtures by match state…")

    rows: list[dict] = []
    for i, p in enumerate(ordered, 1):
        if throttle.budget.remaining < 6:
            break
        home, away = p["home"], p["away"]
        kwargs: dict = {
            "home": home,
            "away": away,
            "prefer_live": p.get("phase") == "live",
            "soft": True,
        }
        fid = p.get("fixture_id_hint")
        if fid is not None:
            try:
                fi = int(fid)
                if fi > 0:
                    kwargs["fixture_id"] = fi
            except (TypeError, ValueError):
                pass
        try:
            payload = await analyze_fixture(**kwargs)
        except Exception as exc:
            payload = {
                "_partial": True,
                "fixture": {"id": 0, "status": {"short": ""}},
                "_drs": {"drs": 0, "tier": "T0", "missing": ["fixture"], "premium_analysis": False},
                "_error": str(exc)[:160],
            }

        sample = get_collector().samples[-1] if get_collector().samples else None
        status = str(
            ((payload.get("fixture") or {}).get("status") or {}).get("short")
            or p.get("status_short")
            or ""
        ).upper()
        state = _state_of(status)
        resolved = bool(sample.resolved) if sample else (
            int((payload.get("fixture") or {}).get("id") or 0) > 0
        )
        drs_block = payload.get("_drs") or {}
        tier = str((sample.tier if sample else None) or drs_block.get("tier") or "T0")
        drs = int((sample.drs if sample else None) or drs_block.get("drs") or 0)
        premium = bool(
            (sample.premium_analysis if sample else False)
            or drs_block.get("premium_analysis")
            or tier in {"T3", "T4"}
        )
        missing = list(drs_block.get("missing") or (sample.missing_signals if sample else []) or [])
        cov = _coverage_from_payload(payload)
        rows.append(
            {
                "home": home,
                "away": away,
                "league_hint": p.get("league_hint"),
                "phase_hint": p.get("phase"),
                "status_short": status,
                "state": state,
                "resolved": resolved,
                "premium": premium,
                "tier": tier,
                "drs": drs,
                "missing": missing,
                "coverage": cov,
            }
        )
        if i % 10 == 0:
            print(f"  …{i}/{len(ordered)}")

    return _aggregate(rows, throttle.as_dict())


def _aggregate(rows: list[dict], throttle: dict) -> dict[str, Any]:
    by_state: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_state[r["state"]].append(r)

    density: dict[str, Any] = {}
    unlock: dict[str, Any] = {}
    for state in ("PREMATCH", "LIVE", "FINISHED"):
        group = by_state.get(state) or []
        n = len(group)
        resolved = [r for r in group if r["resolved"]]
        nr = max(1, len(resolved))
        premium_n = sum(1 for r in resolved if r["premium"])
        cov_keys = [
            "statistics",
            "lineups",
            "events",
            "injuries",
            "odds",
            "standings",
            "xg",
            "momentum",
        ]
        cov_means = {}
        for k in cov_keys:
            if resolved:
                cov_means[k] = round(
                    sum(float((r["coverage"] or {}).get(k) or 0.0) for r in resolved) / nr,
                    4,
                )
            else:
                cov_means[k] = None

        miss_counts: dict[str, int] = defaultdict(int)
        for r in resolved:
            if r["premium"]:
                continue
            for m in r["missing"]:
                miss_counts[m] += 1

        # Single-signal ROI within this state (resolved non-premium only)
        gap = [r for r in resolved if not r["premium"]]
        base_prem_rate = premium_n / max(1, n) if n else 0.0
        # Use state-sized denominator = all rows in state (incl unresolved)
        singles = {}
        for sig in ("statistics", "lineups", "events", "live_momentum", "odds", "xg", "injuries", "standings"):
            newly = 0
            for r in gap:
                if _simulate(r["drs"], r["missing"], {sig}) >= 60:
                    newly += 1
            rate = (premium_n + newly) / max(1, n) if n else 0.0
            singles[sig] = {
                "newly_premium": newly,
                "premium_rate": round(rate, 4),
                "delta_pp": round((rate - base_prem_rate) * 100, 2),
            }

        # Contextual ceiling: fill only signals expected for the state
        expected = {
            "PREMATCH": PREMATCH_EXPECTED,
            "LIVE": LIVE_EXPECTED,
            "FINISHED": FINISHED_EXPECTED,
        }[state]
        newly_ctx = 0
        for r in gap:
            fill = set(expected) & set(r["missing"])
            # Also allow structural if somehow present in missing for live/ft
            if state != "PREMATCH":
                fill |= (PREMATCH_STRUCTURAL_GAP & set(r["missing"]))
            if _simulate(r["drs"], r["missing"], fill) >= 60:
                newly_ctx += 1
        ctx_rate = (premium_n + newly_ctx) / max(1, n) if n else 0.0

        # Blind fill all (unrealistic for prematch)
        newly_all = 0
        for r in gap:
            if _simulate(r["drs"], r["missing"], set(r["missing"])) >= 60:
                newly_all += 1
        all_rate = (premium_n + newly_all) / max(1, n) if n else 0.0

        density[state] = {
            "n": n,
            "resolved": len(resolved),
            "resolve_rate": round(len(resolved) / max(1, n), 4),
            "premium": premium_n,
            "premium_rate": round(premium_n / max(1, n), 4),
            "p_premium_given_resolved": round(premium_n / nr, 4) if resolved else None,
            "mean_drs": round(sum(r["drs"] for r in resolved) / nr, 2) if resolved else None,
            "coverage_means": cov_means,
            "missing_among_non_premium": dict(
                sorted(miss_counts.items(), key=lambda kv: -kv[1])
            ),
            "status_mix": dict(
                __import__("collections").Counter(r["status_short"] or "?" for r in group)
            ),
        }
        unlock[state] = {
            "baseline_premium_rate": round(base_prem_rate, 4),
            "single_signal_roi": dict(
                sorted(singles.items(), key=lambda kv: -kv[1]["delta_pp"])
            ),
            "contextual_expected_pack_fill": {
                "fill_set": sorted(expected),
                "premium_rate": round(ctx_rate, 4),
                "delta_pp": round((ctx_rate - base_prem_rate) * 100, 2),
                "operational_ceiling_estimate": round(ctx_rate, 4),
            },
            "unconstrained_fill_all_missing": {
                "premium_rate": round(all_rate, 4),
                "note": "Ignores structural prematch emptiness — upper fantasy bound",
            },
            "signals_that_move_premium": [
                k
                for k, v in sorted(singles.items(), key=lambda kv: -kv[1]["delta_pp"])
                if v["delta_pp"] > 0
            ],
        }

    # Contextual DRS model (design only)
    drs_model = {
        "principle": (
            "Do not penalize PREMATCH for absence of live-only signals. "
            "Score each state against an expected signal set; missing structural "
            "live signals in NS should be N/A, not DRS penalties."
        ),
        "state_expected_signals": {
            "PREMATCH": sorted(PREMATCH_EXPECTED),
            "LIVE": sorted(LIVE_EXPECTED),
            "FINISHED": sorted(FINISHED_EXPECTED),
        },
        "structural_impossible_in_prematch": sorted(PREMATCH_STRUCTURAL_GAP),
        "proposed_rules": [
            "If status in {NS,TBD}: exclude statistics/events/score/live_momentum/xg from missing penalties and from DRS denominator.",
            "Prematch premium path: weight lineups + odds + injuries + standings + calendar (+ referee).",
            "Live premium path: weight statistics + events + live_momentum + score (+ odds).",
            "Finished premium path: weight statistics + events + xg + score (+ standings).",
            "Optional: state-conditional tier thresholds (e.g. prematch T3 at calibrated lower bar) — product decision, not implemented here.",
        ],
        "not_implemented": True,
        "frozen": ["engines", "DRS", "NMB", "Gateway", "Resolve", "CostProtection"],
    }

    overall_n = max(1, len(rows))
    return {
        "status": "MATCH_STATE_DENSITY_DIAGNOSIS",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "n": len(rows),
        "resolve_rate": round(sum(1 for r in rows if r["resolved"]) / overall_n, 4),
        "premium_rate": round(sum(1 for r in rows if r["premium"]) / overall_n, 4),
        "state_counts": {k: len(v) for k, v in by_state.items()},
        "signal_density_by_state": density,
        "premium_unlock_by_state": unlock,
        "drs_state_projection": drs_model,
        "throttle": throttle,
        "sample_rows": [
            {
                "state": r["state"],
                "status": r["status_short"],
                "home": r["home"],
                "away": r["away"],
                "resolved": r["resolved"],
                "premium": r["premium"],
                "drs": r["drs"],
                "tier": r["tier"],
                "coverage": r["coverage"],
            }
            for r in rows[:60]
        ],
    }


def write_reports(raw: dict) -> None:
    out = ROOT / "roadmap"
    out.mkdir(exist_ok=True)
    if raw.get("status") == "BLOCKED_NO_API_KEY":
        for name in (
            "signal_density_by_state.json",
            "drs_state_projection.json",
            "premium_unlock_by_state.json",
        ):
            (out / name).write_text(json.dumps(raw, indent=2), encoding="utf-8")
        return

    density = raw["signal_density_by_state"]
    unlock = raw["premium_unlock_by_state"]
    model = raw["drs_state_projection"]

    (out / "signal_density_by_state.json").write_text(
        json.dumps(
            {
                "generated_at": raw["generated_at"],
                "n": raw["n"],
                "resolve_rate": raw["resolve_rate"],
                "premium_rate": raw["premium_rate"],
                "state_counts": raw["state_counts"],
                "by_state": density,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (out / "drs_state_projection.json").write_text(
        json.dumps(model, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (out / "premium_unlock_by_state.json").write_text(
        json.dumps(
            {
                "generated_at": raw["generated_at"],
                "by_state": unlock,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    def _cov_table(state: str) -> str:
        c = (density.get(state) or {}).get("coverage_means") or {}
        lines = []
        for k in (
            "statistics",
            "lineups",
            "events",
            "injuries",
            "odds",
            "standings",
            "xg",
            "momentum",
        ):
            v = c.get(k)
            lines.append(f"| {k} | {v if v is not None else 'n/a'} |")
        return "\n".join(lines)

    md = f"""# P3-B.1 — Premium by Match State (Diagnosis)

**Date:** {time.strftime('%Y-%m-%d')}  
**Status:** `{raw.get('status')}`  
**Freeze:** engines · DRS · NMB · Gateway · Resolve · Cost Protection **unchanged**  
**Mode:** Diagnosis only — **NOT IMPLEMENTED**

## Baseline

| Metric | Value |
|--------|------:|
| n | {raw['n']} |
| resolve_rate | **{raw['resolve_rate']:.1%}** |
| premium_rate | **{raw['premium_rate']:.1%}** |
| PREMATCH / LIVE / FINISHED | {raw['state_counts'].get('PREMATCH', 0)} / {raw['state_counts'].get('LIVE', 0)} / {raw['state_counts'].get('FINISHED', 0)} |

---

## 1–3. Density + premium by state

### PREMATCH
| Metric | Value |
|--------|------:|
| n | {(density.get('PREMATCH') or {}).get('n')} |
| resolve_rate | {(density.get('PREMATCH') or {}).get('resolve_rate')} |
| premium_rate | **{(density.get('PREMATCH') or {}).get('premium_rate')}** |
| mean_drs | {(density.get('PREMATCH') or {}).get('mean_drs')} |

| Signal | Coverage |
|--------|---------:|
{_cov_table('PREMATCH')}

### LIVE
| Metric | Value |
|--------|------:|
| n | {(density.get('LIVE') or {}).get('n')} |
| resolve_rate | {(density.get('LIVE') or {}).get('resolve_rate')} |
| premium_rate | **{(density.get('LIVE') or {}).get('premium_rate')}** |
| mean_drs | {(density.get('LIVE') or {}).get('mean_drs')} |

| Signal | Coverage |
|--------|---------:|
{_cov_table('LIVE')}

### FINISHED
| Metric | Value |
|--------|------:|
| n | {(density.get('FINISHED') or {}).get('n')} |
| resolve_rate | {(density.get('FINISHED') or {}).get('resolve_rate')} |
| premium_rate | **{(density.get('FINISHED') or {}).get('premium_rate')}** |
| mean_drs | {(density.get('FINISHED') or {}).get('mean_drs')} |

| Signal | Coverage |
|--------|---------:|
{_cov_table('FINISHED')}

---

## 4. Operational ceiling (contextual pack fill)

| State | Baseline premium | Contextual ceiling | Unconstrained fantasy |
|-------|-----------------:|-------------------:|----------------------:|
| PREMATCH | {(unlock.get('PREMATCH') or {}).get('baseline_premium_rate')} | {((unlock.get('PREMATCH') or {}).get('contextual_expected_pack_fill') or {}).get('operational_ceiling_estimate')} | {((unlock.get('PREMATCH') or {}).get('unconstrained_fill_all_missing') or {}).get('premium_rate')} |
| LIVE | {(unlock.get('LIVE') or {}).get('baseline_premium_rate')} | {((unlock.get('LIVE') or {}).get('contextual_expected_pack_fill') or {}).get('operational_ceiling_estimate')} | {((unlock.get('LIVE') or {}).get('unconstrained_fill_all_missing') or {}).get('premium_rate')} |
| FINISHED | {(unlock.get('FINISHED') or {}).get('baseline_premium_rate')} | {((unlock.get('FINISHED') or {}).get('contextual_expected_pack_fill') or {}).get('operational_ceiling_estimate')} | {((unlock.get('FINISHED') or {}).get('unconstrained_fill_all_missing') or {}).get('premium_rate')} |

---

## 5. Signals that move Premium (by state)

- **PREMATCH movers:** `{(unlock.get('PREMATCH') or {}).get('signals_that_move_premium')}`
- **LIVE movers:** `{(unlock.get('LIVE') or {}).get('signals_that_move_premium')}`
- **FINISHED movers:** `{(unlock.get('FINISHED') or {}).get('signals_that_move_premium')}`

See `premium_unlock_by_state.json` for full single-signal ROI tables.

---

## 6. Structurally impossible in prematch

{', '.join(model.get('structural_impossible_in_prematch') or [])}

These should be **N/A**, not DRS penalties, while status is NS/TBD.

---

## 7. Contextual DRS model (design only)

{chr(10).join('- ' + r for r in (model.get('proposed_rules') or []))}

**Not implemented.** Frozen surfaces unchanged.

---

## Artifacts

- `roadmap/premium_by_state_report.md`
- `roadmap/signal_density_by_state.json`
- `roadmap/drs_state_projection.json`
- `roadmap/premium_unlock_by_state.json`
"""
    (out / "premium_by_state_report.md").write_text(md, encoding="utf-8")
    print(
        json.dumps(
            {
                "n": raw["n"],
                "resolve_rate": raw["resolve_rate"],
                "premium_rate": raw["premium_rate"],
                "state_counts": raw["state_counts"],
                "premium_by_state": {
                    s: (density.get(s) or {}).get("premium_rate")
                    for s in ("PREMATCH", "LIVE", "FINISHED")
                },
                "ceilings": {
                    s: ((unlock.get(s) or {}).get("contextual_expected_pack_fill") or {}).get(
                        "operational_ceiling_estimate"
                    )
                    for s in ("PREMATCH", "LIVE", "FINISHED")
                },
            },
            indent=2,
        )
    )


def main() -> None:
    raw = asyncio.run(run_diagnosis(min_n=100))
    write_reports(raw)
    if raw.get("status") == "BLOCKED_NO_API_KEY":
        sys.exit(2)


if __name__ == "__main__":
    main()
