"""
P3-B — Match-state / premium gap diagnosis (READ-ONLY).

Does NOT change engines, DRS formulas, NMB, Gateway, or aliases.
Collects missing signals among resolved non-premium and projects DRS uplift.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_SCRIPT = Path(__file__).resolve().parent / "run_p3a1_live_certification.py"
_spec = importlib.util.spec_from_file_location("run_p3a1_live_certification", _SCRIPT)
assert _spec and _spec.loader
_p3a1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_p3a1)

# Max DRS points if signal goes missing → confirmed (from drs.py, diagnosis model only)
SIGNAL_DRS_UPLIFT = {
    "statistics": 12,  # core
    "xg": 12,
    "standings": 10,
    "events": 8,
    "lineups": 8 + 3,  # context 8 + wave3 up to +3 (XI)
    "score": 4,
    "referee": 4,
    "live_momentum": 6,  # context when h2h empty
    "odds": 6 + 4 + 4,  # market 6(+4 live) + wave3 +4 (conservative use 10)
    "injuries": 2,
    "calendar": 4 + 3,  # context + wave3
}


def _simulate_fill(drs: int, missing: list[str], fill: set[str]) -> int:
    """Naive additive uplift; respects rough component caps via min(100)."""
    gain = 0
    for sig in fill:
        if sig in missing:
            gain += SIGNAL_DRS_UPLIFT.get(sig, 0)
    # Synergy bonuses if combo filled
    if {"xg", "events", "live_momentum"} & fill and (
        "xg" in missing or "events" in missing or "live_momentum" in missing
    ):
        if "xg" in fill and "events" in fill and "live_momentum" in fill:
            if "xg" in missing or "events" in missing or "live_momentum" in missing:
                gain += 4
        elif "xg" in fill and "events" in fill:
            if "xg" in missing or "events" in missing:
                gain += 2
    if {"odds", "lineups", "calendar"} <= fill:
        if any(s in missing for s in ("odds", "lineups", "calendar")):
            gain += 2
    return max(0, min(100, int(drs) + gain))


async def run() -> dict:
    from src.ops.adaptive_throttle import full_throttle_defaults
    from src.ops.live_density import get_collector, reset_collector_for_tests
    from src.routers.analyze import analyze_fixture

    if not _p3a1._load_key_from_dotenv():
        return {"status": "BLOCKED_NO_API_KEY"}

    reset_collector_for_tests()
    throttle = full_throttle_defaults()
    await _p3a1._install_provider_probe(throttle)

    corpus = await _p3a1._discover_corpus(min_n=100, lite=False)
    live = [p for p in corpus if p.get("phase") == "live"]
    pre = [p for p in corpus if p.get("phase") != "live"]
    ordered = (live + pre)[: max(100, min(160, len(live + pre)))]
    print(f"P3-B diagnosing premium gaps on {len(ordered)} fixtures…")

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
                "fixture": {"id": 0},
                "league": {"name": "Unknown"},
                "_drs": {"drs": 0, "tier": "T0", "missing": ["fixture"], "premium_analysis": False},
                "_error": str(exc)[:200],
            }

        sample = get_collector().samples[-1] if get_collector().samples else None
        drs_block = payload.get("_drs") or {}
        missing = list(drs_block.get("missing") or (sample.missing_signals if sample else []) or [])
        tier = str(
            (sample.tier if sample else None)
            or drs_block.get("tier")
            or "T0"
        )
        drs = int(
            (sample.drs if sample else None)
            or drs_block.get("drs")
            or 0
        )
        resolved = bool(sample.resolved) if sample else (
            int((payload.get("fixture") or {}).get("id") or 0) > 0
        )
        premium = bool(
            (sample.premium_analysis if sample else False)
            or drs_block.get("premium_analysis")
            or tier in {"T3", "T4"}
        )
        comps = drs_block.get("components") or {}
        rows.append(
            {
                "home": home,
                "away": away,
                "league_hint": p.get("league_hint"),
                "phase": p.get("phase"),
                "bucket": p.get("bucket"),
                "status_short": p.get("status_short")
                or str(((payload.get("fixture") or {}).get("status") or {}).get("short") or ""),
                "resolved": resolved,
                "premium": premium,
                "tier": tier,
                "drs": drs,
                "missing": missing,
                "components": comps,
                "gap_to_60": max(0, 60 - drs) if resolved and not premium else 0,
            }
        )
        if i % 10 == 0:
            print(f"  …{i}/{len(ordered)}")

    n = max(1, len(rows))
    resolved_rows = [r for r in rows if r["resolved"]]
    premium_rows = [r for r in rows if r["premium"]]
    gap_rows = [r for r in resolved_rows if not r["premium"]]  # the ~75%

    miss_counter: Counter[str] = Counter()
    co_miss: Counter[tuple] = Counter()
    for r in gap_rows:
        miss = sorted(set(r["missing"]))
        for m in miss:
            miss_counter[m] += 1
        # pairs among key match-state signals
        key = [s for s in miss if s in SIGNAL_DRS_UPLIFT]
        for a in key:
            for b in key:
                if a < b:
                    co_miss[(a, b)] += 1

    baseline_premium_rate = len(premium_rows) / n
    baseline_resolve = len(resolved_rows) / n

    def project_fill(fill_signals: list[str]) -> dict:
        fill = set(fill_signals)
        newly = 0
        still = 0
        for r in gap_rows:
            new_drs = _simulate_fill(r["drs"], r["missing"], fill)
            if new_drs >= 60:
                newly += 1
            else:
                still += 1
        # already premium unchanged
        total_prem = len(premium_rows) + newly
        rate = total_prem / n
        return {
            "fill": fill_signals,
            "newly_premium": newly,
            "still_gap": still,
            "premium_rate": round(rate, 4),
            "premium_delta_pp": round((rate - baseline_premium_rate) * 100, 2),
            "unlocks_50": rate >= 0.50,
        }

    singles = {
        sig: project_fill([sig])
        for sig in ("statistics", "lineups", "events", "live_momentum", "odds", "xg", "score")
    }
    combos = {
        "stats_only": project_fill(["statistics"]),
        "stats_lineups": project_fill(["statistics", "lineups"]),
        "stats_events": project_fill(["statistics", "events"]),
        "stats_events_lineups": project_fill(["statistics", "events", "lineups"]),
        "match_state_pack": project_fill(
            ["statistics", "events", "lineups", "live_momentum", "score"]
        ),
        "match_state_plus_odds": project_fill(
            ["statistics", "events", "lineups", "live_momentum", "score", "odds"]
        ),
        "stats_events_momentum": project_fill(
            ["statistics", "events", "live_momentum"]
        ),
        "lineups_odds_calendar": project_fill(["lineups", "odds", "calendar"]),
        "full_core_wave2": project_fill(
            ["statistics", "xg", "events", "live_momentum", "lineups"]
        ),
    }

    # Minimal combo search (greedy by ROI then small brute on top signals)
    top_sigs = [s for s, _ in miss_counter.most_common(8)]
    minimal = None
    from itertools import combinations

    for k in range(1, 5):
        for combo in combinations(top_sigs, k):
            proj = project_fill(list(combo))
            if proj["unlocks_50"]:
                minimal = proj
                break
        if minimal:
            break

    # Phase split of gap
    by_phase = Counter(r["phase"] for r in gap_rows)
    mean_drs_gap = (
        round(sum(r["drs"] for r in gap_rows) / max(1, len(gap_rows)), 2)
        if gap_rows
        else 0
    )
    mean_gap_to_60 = (
        round(sum(r["gap_to_60"] for r in gap_rows) / max(1, len(gap_rows)), 2)
        if gap_rows
        else 0
    )

    out = {
        "status": "PREMIUM_GAP_DIAGNOSIS",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "n": n,
        "resolved": len(resolved_rows),
        "premium": len(premium_rows),
        "gap_resolved_non_premium": len(gap_rows),
        "resolve_rate": round(baseline_resolve, 4),
        "premium_rate": round(baseline_premium_rate, 4),
        "p_premium_given_resolved": round(
            len(premium_rows) / max(1, len(resolved_rows)), 4
        ),
        "mean_drs_gap": mean_drs_gap,
        "mean_points_short_of_60": mean_gap_to_60,
        "gap_by_phase": dict(by_phase),
        "missing_among_gap": dict(miss_counter.most_common()),
        "co_missing_top": [
            {"pair": list(k), "count": v} for k, v in co_miss.most_common(15)
        ],
        "single_signal_projections": singles,
        "combo_projections": combos,
        "minimal_combo_for_50": minimal,
        "throttle": throttle.as_dict(),
        "sample_gaps": [
            {
                "home": r["home"],
                "away": r["away"],
                "phase": r["phase"],
                "tier": r["tier"],
                "drs": r["drs"],
                "gap_to_60": r["gap_to_60"],
                "missing": r["missing"][:12],
            }
            for r in sorted(gap_rows, key=lambda x: -x["gap_to_60"])[:40]
        ],
    }
    return out


def write_reports(raw: dict) -> None:
    out = ROOT / "roadmap"
    out.mkdir(exist_ok=True)
    if raw.get("status") == "BLOCKED_NO_API_KEY":
        (out / "signal_roi_projection.json").write_text(
            json.dumps(raw, indent=2), encoding="utf-8"
        )
        return

    singles = raw.get("single_signal_projections") or {}
    combos = raw.get("combo_projections") or {}
    miss = raw.get("missing_among_gap") or {}

    signal_roi = {
        "generated_at": raw.get("generated_at"),
        "baseline": {
            "n": raw["n"],
            "resolve_rate": raw["resolve_rate"],
            "premium_rate": raw["premium_rate"],
            "gap_resolved_non_premium": raw["gap_resolved_non_premium"],
            "mean_drs_gap": raw["mean_drs_gap"],
            "mean_points_short_of_60": raw["mean_points_short_of_60"],
        },
        "missing_among_gap": miss,
        "single_fill_if_100pct_coverage_on_gap": {
            k: {
                "premium_rate": v["premium_rate"],
                "delta_pp": v["premium_delta_pp"],
                "newly_premium": v["newly_premium"],
                "unlocks_50": v["unlocks_50"],
                "roi_rank_key": v["premium_delta_pp"],
            }
            for k, v in singles.items()
        },
        "roi_ranking": sorted(
            (
                {
                    "signal": k,
                    "delta_pp": v["premium_delta_pp"],
                    "premium_rate": v["premium_rate"],
                    "newly_premium": v["newly_premium"],
                }
                for k, v in singles.items()
            ),
            key=lambda x: -x["delta_pp"],
        ),
        "model_note": (
            "Uplift is a diagnosis simulation using DRS point tables from drs.py; "
            "component caps / real API availability may reduce realized gains. "
            "Does not modify DRS."
        ),
    }

    unlock = {
        "generated_at": raw.get("generated_at"),
        "baseline_premium_rate": raw["premium_rate"],
        "target": 0.50,
        "combos": combos,
        "minimal_combo_for_50": raw.get("minimal_combo_for_50"),
        "dependencies": {
            "co_missing_top": raw.get("co_missing_top"),
            "notes": [
                "statistics/events/score/lineups/referee/live_momentum often co-miss on prematch (API empty until live/post)",
                "live_momentum DRS credit depends on h2h absence (up to 6 vs +2)",
                "wave2 synergy requires xg+events(+momentum)",
                "wave3 cluster bonuses: calendar+lineups; odds+lineups+calendar",
                "live_or_finished core +8 requires non-NS status — prematch ceiling is structural",
            ],
        },
    }

    (out / "signal_roi_projection.json").write_text(
        json.dumps(signal_roi, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (out / "premium_unlock_projection.json").write_text(
        json.dumps(unlock, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    roi_lines = "\n".join(
        f"| {r['signal']} | {r['delta_pp']} | {r['premium_rate']:.1%} | {r['newly_premium']} |"
        for r in signal_roi["roi_ranking"]
    )
    miss_lines = "\n".join(f"| {k} | {v} |" for k, v in list(miss.items())[:12])
    minimal = raw.get("minimal_combo_for_50")
    minimal_txt = (
        f"`{' + '.join(minimal['fill'])}` → premium **{minimal['premium_rate']:.1%}**"
        if minimal
        else "_No combination of ≤4 top-missing signals unlocks 50% under this model — need larger match-state pack or live density._"
    )

    md = f"""# P3-B — Premium Gap Report (Match-State Diagnosis)

**Date:** {time.strftime('%Y-%m-%d')}  
**Status:** `{raw.get('status')}`  
**Mode:** Diagnosis only — **NOT IMPLEMENTED**  
**Freeze:** engines / DRS formulas / NMB / Gateway unchanged

## Baseline

| Metric | Value |
|--------|------:|
| n | {raw['n']} |
| resolve_rate | **{raw['resolve_rate']:.1%}** |
| premium_rate | **{raw['premium_rate']:.1%}** |
| resolved non-premium (gap) | **{raw['gap_resolved_non_premium']}** |
| mean DRS in gap | {raw['mean_drs_gap']} |
| mean points short of 60 | {raw['mean_points_short_of_60']} |
| gap by phase | `{raw.get('gap_by_phase')}` |

Resolve is largely solved; premium stays ~25% because **DRS&lt;60** on most resolved fixtures — match-state / prematch emptiness, not identity.

---

## 1. Signals missing in the non-premium ~75%

Among **resolved ∧ ¬premium**:

| Signal | Times missing |
|--------|--------------:|
{miss_lines}

---

## 2. Highest ROI signal (single fill → 100% on gap)

| Signal | Δ premium pp | Resulting premium | Newly premium |
|--------|-------------:|------------------:|--------------:|
{roi_lines}

---

## 3. If each signal were 100% (on current gap)

See `signal_roi_projection.json` → `single_fill_if_100pct_coverage_on_gap`.

---

## 4. Minimal combo for premium ≥50%

{minimal_txt}

Broader packs in `premium_unlock_projection.json`.

---

## 5. Signal dependencies

- **Prematch structure:** statistics / events / score / live_momentum often empty together until live or FT.
- **DRS caps:** core ≤50, context ≤20, market ≤10, wave3 bonus ≤12.
- **Synergy:** xG+events(+momentum); odds+lineups+calendar cluster.
- **live_or_finished (+8):** blocked while status is NS — hard ceiling for pure prematch.

---

## Artifacts

- `roadmap/premium_gap_report.md`
- `roadmap/signal_roi_projection.json`
- `roadmap/premium_unlock_projection.json`
"""
    (out / "premium_gap_report.md").write_text(md, encoding="utf-8")
    print(
        json.dumps(
            {
                "resolve_rate": raw["resolve_rate"],
                "premium_rate": raw["premium_rate"],
                "gap": raw["gap_resolved_non_premium"],
                "top_missing": list(miss.items())[:6],
                "roi_top": signal_roi["roi_ranking"][:3],
                "minimal_50": minimal,
            },
            indent=2,
        )
    )


def main() -> None:
    raw = asyncio.run(run())
    write_reports(raw)
    if raw.get("status") == "BLOCKED_NO_API_KEY":
        sys.exit(2)


if __name__ == "__main__":
    main()
