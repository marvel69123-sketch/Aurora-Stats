"""
P3-A.4 — Resolve / Unknown coverage diagnosis (READ-ONLY observations).

Does NOT change engines, Gateway, Cache, NMB, DRS, guards, or throttle logic.
Re-runs analyze under existing throttle to classify why fixtures land as Unknown.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import re
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


def _classify(
    *,
    home: str,
    away: str,
    league_hint: str | None,
    bucket: str | None,
    phase: str | None,
    fixture_id_hint: int | None,
    resolved: bool,
    detail: str | None,
    soft_miss: bool,
) -> str:
    if resolved:
        return "resolved_ok"
    d = (detail or "").lower()
    if bucket == "control" or home.lower() in {"goku"} or away.lower() in {"naruto"}:
        return "sampling_control_fiction"
    if "no team found matching" in d or "tried variants" in d:
        return "alias_team_resolve"
    if "no fixture found between" in d:
        # Discovered via league/date API but name re-resolve failed, or no H2H window
        if fixture_id_hint:
            # A+C should have bound id; if still here, bind failed/empty then name miss
            return "fixture_id_bind_miss_then_name_miss"
        if phase == "seed":
            return "sampling_seed_no_fixture"
        return "fixture_discovery_miss"
    if "429" in d or "rate limit" in d or "quota" in d:
        return "api_rate_limit"
    if "not configured" in d or "500" in d or "timeout" in d:
        return "api_gap_or_error"
    if fixture_id_hint and not resolved:
        return "fixture_id_present_still_unresolved"
    if phase == "seed":
        return "sampling_seed_unresolved"
    if soft_miss and not detail:
        return "soft_unresolved_no_detail"
    return "other_unresolved"


def _inference_reason(payload: dict) -> str | None:
    inf = payload.get("_inference") or {}
    fails = inf.get("failures") or inf.get("falhas") or []
    if isinstance(fails, list) and fails:
        first = fails[0]
        if isinstance(first, dict):
            return str(first.get("detail") or first.get("reason") or first.get("message") or "")
        return str(first)
    for key in ("reason", "detail", "mensagem", "message"):
        if inf.get(key):
            return str(inf.get(key))
    # honesty / partial stamps
    for block in (payload.get("_honesty"), payload.get("_partial_meta")):
        if isinstance(block, dict) and block.get("reason"):
            return str(block.get("reason"))
    return None


async def run_diagnosis(min_n: int = 100) -> dict:
    from src.ops.adaptive_throttle import full_throttle_defaults
    from src.ops.live_density import get_collector, reset_collector_for_tests
    from src.routers.analyze import analyze_fixture

    if not _p3a1._load_key_from_dotenv():
        return {"status": "BLOCKED_NO_API_KEY"}

    reset_collector_for_tests()
    throttle = full_throttle_defaults()
    await _p3a1._install_provider_probe(throttle)

    print("P3-A.4 diagnosing corpus…")
    corpus = await _p3a1._discover_corpus(min_n=min_n, lite=False)
    live = [p for p in corpus if p.get("phase") == "live"]
    pre = [p for p in corpus if p.get("phase") != "live"]
    ordered = live + pre
    if len(ordered) >= min_n:
        ordered = ordered[: max(min_n, min(160, len(ordered)))]
    print(f"Diagnosing {len(ordered)} fixtures…")

    rows: list[dict] = []
    for i, p in enumerate(ordered, 1):
        if throttle.budget.remaining < 6:
            print("budget reserve hit — stopping diagnosis early")
            break
        home, away = p["home"], p["away"]
        detail = None
        err = None
        try:
            _kwargs: dict = {
                "home": home,
                "away": away,
                "prefer_live": (p.get("phase") == "live"),
                "soft": True,
            }
            _fid = p.get("fixture_id_hint")
            if _fid is not None:
                try:
                    _fid_i = int(_fid)
                    if _fid_i > 0:
                        _kwargs["fixture_id"] = _fid_i
                except (TypeError, ValueError):
                    pass
            payload = await analyze_fixture(**_kwargs)
        except Exception as exc:
            payload = {
                "_partial": True,
                "fixture": {"id": 0},
                "league": {"name": "Unknown"},
                "teams": {"home": {"name": home}, "away": {"name": away}},
                "_drs": {"drs": 0, "tier": "T0"},
            }
            err = str(exc)[:300]
            detail = err

        sample = get_collector().samples[-1] if get_collector().samples else None
        resolved = bool(sample.resolved) if sample else False
        soft_miss = bool(sample.soft_miss) if sample else True
        fid = int(sample.fixture_id) if sample and sample.fixture_id else 0
        league_name = (sample.league_name if sample else None) or (
            (payload.get("league") or {}).get("name")
        )
        detail = detail or _inference_reason(payload) or err
        # Pull 404 text from nested inference if present
        if not detail and payload.get("_partial"):
            raw = json.dumps(payload.get("_inference") or {}, ensure_ascii=False)
            m = re.search(r"No (?:team|fixture) found[^\"\\]{0,200}", raw)
            if m:
                detail = m.group(0)

        cls = _classify(
            home=home,
            away=away,
            league_hint=p.get("league_hint"),
            bucket=p.get("bucket"),
            phase=p.get("phase"),
            fixture_id_hint=p.get("fixture_id_hint"),
            resolved=resolved,
            detail=detail,
            soft_miss=soft_miss,
        )
        rows.append(
            {
                "home": home,
                "away": away,
                "league_hint": p.get("league_hint"),
                "league_name_returned": league_name,
                "bucket": p.get("bucket"),
                "phase": p.get("phase"),
                "status_short_hint": p.get("status_short"),
                "fixture_id_hint": p.get("fixture_id_hint"),
                "fixture_id": fid or None,
                "resolved": resolved,
                "soft_miss": soft_miss,
                "drs": sample.drs if sample else None,
                "tier": sample.tier if sample else None,
                "premium_analysis": bool(sample.premium_analysis) if sample else False,
                "failure_class": cls,
                "detail": (detail or "")[:280] or None,
                "unknown_league_label": (
                    str(league_name or "") in {"", "Unknown"} and not resolved
                ),
            }
        )
        if i % 10 == 0:
            print(
                f"  …{i}/{len(ordered)} "
                f"unresolved={sum(1 for r in rows if not r['resolved'])} "
                f"budget={throttle.budget.used}/{throttle.budget.max_requests}"
            )

    return {
        "status": "DIAGNOSIS_RUN",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "sample_count": len(rows),
        "throttle": throttle.as_dict(),
        "rows": rows,
    }


def _build_reports(raw: dict) -> None:
    out = ROOT / "roadmap"
    out.mkdir(exist_ok=True)
    rows = raw.get("rows") or []
    n = max(1, len(rows))
    resolved_n = sum(1 for r in rows if r.get("resolved"))
    premium_n = sum(1 for r in rows if r.get("premium_analysis"))
    unknown_rows = [r for r in rows if r.get("unknown_league_label") or not r.get("resolved")]
    # Prefer unresolved as Unknown set (matches P3-A.3 bucket)
    unresolved = [r for r in rows if not r.get("resolved")]

    by_class = Counter(r.get("failure_class") for r in unresolved)
    by_league_hint = Counter(
        (r.get("league_hint") or "_(empty_hint)") for r in unresolved
    )
    by_phase = Counter(r.get("phase") or "?" for r in unresolved)
    by_bucket = Counter(r.get("bucket") or "?" for r in unresolved)

    # Leagues with most resolve failures (by hint — true sampling origin)
    league_fail = []
    hint_groups: dict[str, list] = defaultdict(list)
    for r in rows:
        hint_groups[r.get("league_hint") or "_(empty_hint)"].append(r)
    for hint, group in hint_groups.items():
        nn = len(group)
        fail = sum(1 for r in group if not r.get("resolved"))
        league_fail.append(
            {
                "league_hint": hint,
                "n": nn,
                "resolve_failures": fail,
                "resolve_rate": round((nn - fail) / max(1, nn), 4),
                "failure_rate": round(fail / max(1, nn), 4),
                "top_classes": dict(
                    Counter(
                        r.get("failure_class")
                        for r in group
                        if not r.get("resolved")
                    ).most_common(5)
                ),
            }
        )
    league_fail.sort(key=lambda x: (-x["resolve_failures"], -x["failure_rate"], x["league_hint"]))

    # Cause mix among unresolved
    cause_axes = {
        "aliases": sum(
            1 for r in unresolved if r.get("failure_class") == "alias_team_resolve"
        ),
        "fixture_discovery": sum(
            1
            for r in unresolved
            if r.get("failure_class")
            in {
                "fixture_discovery_miss",
                "fixture_id_bind_miss_then_name_miss",
                "fixture_id_present_still_unresolved",
                "discovery_id_not_used_then_name_miss",
                "discovery_id_not_used_unknown_detail",
            }
        ),
        "api_gaps": sum(
            1
            for r in unresolved
            if r.get("failure_class") in {"api_rate_limit", "api_gap_or_error"}
        ),
        "sampling": sum(
            1
            for r in unresolved
            if str(r.get("failure_class") or "").startswith("sampling_")
        ),
    }
    # discovery_id specifically
    discovery_id_wasted = sum(
        1
        for r in unresolved
        if r.get("fixture_id_hint")
        and not r.get("resolved")
    )

    resolve_rate = resolved_n / n
    premium_rate = premium_n / n
    cond_premium = premium_n / max(1, resolved_n)

    def _proj(target_resolve: float) -> dict:
        """Assume newly resolved inherit conditional premium of current resolved set."""
        need = max(0.0, target_resolve - resolve_rate)
        added = need * n
        prem_added = added * cond_premium
        new_prem_rate = (premium_n + prem_added) / n
        return {
            "target_resolve_rate": target_resolve,
            "resolve_delta_pp": round(need * 100, 2),
            "fixtures_to_recover": round(added, 1),
            "expected_premium_rate": round(new_prem_rate, 4),
            "premium_delta_pp": round((new_prem_rate - premium_rate) * 100, 2),
            "assumption": (
                "newly resolved fixtures inherit current "
                f"P(premium|resolved)={round(cond_premium, 4)}"
            ),
            "thin_premium_gate_50": new_prem_rate >= 0.50,
            "resolve_gate_85": target_resolve >= 0.85,
        }

    projections = {
        "baseline": {
            "resolve_rate": round(resolve_rate, 4),
            "premium_fixture_rate": round(premium_rate, 4),
            "p_premium_given_resolved": round(cond_premium, 4),
            "n": n,
            "resolved": resolved_n,
            "premium": premium_n,
            "unresolved": len(unresolved),
        },
        "if_resolve_70": _proj(0.70),
        "if_resolve_80": _proj(0.80),
        "if_resolve_85": _proj(0.85),
        "upper_bound_note": (
            "Premium uplift from resolve alone is capped by signal density; "
            "Thin Premium still needs premium≥50% and DRS≥60≥50%."
        ),
        "pessimistic_premium_if_new_resolves_like_mls_softmiss": {
            "note": "If recovered Unknowns get 0% premium (like MLS soft-miss block)",
            "premium_stays_near": round(premium_rate, 4),
        },
    }

    unknown_report = {
        "generated_at": raw.get("generated_at"),
        "status": raw.get("status"),
        "definition": (
            "Unknown in P3-A.3 league_coverage = unresolved soft partials whose "
            "payload stamps league.name='Unknown' (build_partial_analyze_data). "
            "That label shadows corpus league_hint in by_league aggregation."
        ),
        "unresolved_count": len(unresolved),
        "unknown_label_count": sum(1 for r in rows if r.get("unknown_league_label")),
        "failure_class_counts": dict(by_class),
        "by_phase": dict(by_phase),
        "by_bucket": dict(by_bucket),
        "by_league_hint": dict(by_league_hint.most_common()),
        "discovery_id_hint_present_but_unresolved": discovery_id_wasted,
        "cause_axes": cause_axes,
        "fixtures": [
            {
                "home": r["home"],
                "away": r["away"],
                "league_hint": r.get("league_hint"),
                "phase": r.get("phase"),
                "bucket": r.get("bucket"),
                "fixture_id_hint": r.get("fixture_id_hint"),
                "failure_class": r.get("failure_class"),
                "detail": r.get("detail"),
            }
            for r in unresolved
        ],
        "throttle": raw.get("throttle"),
    }

    league_failure_report = {
        "generated_at": raw.get("generated_at"),
        "ranked_by_resolve_failures": league_fail,
        "note": (
            "Ranked by corpus league_hint (sampling origin), not payload "
            "league.name='Unknown'."
        ),
    }

    resolve_roi = {
        "generated_at": raw.get("generated_at"),
        "projections": projections,
        "root_causes_ranked": [
            {"cause": k, "count": v, "share_of_unresolved": round(v / max(1, len(unresolved)), 4)}
            for k, v in sorted(cause_axes.items(), key=lambda kv: -kv[1])
        ],
        "top_failure_classes": dict(by_class.most_common()),
    }

    (out / "unknown_fixture_report.json").write_text(
        json.dumps(unknown_report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (out / "league_failure_report.json").write_text(
        json.dumps(league_failure_report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (out / "resolve_roi_report.json").write_text(
        json.dumps(resolve_roi, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    top_leagues = league_fail[:8]
    top_unknown = unresolved[:25]
    md = f"""# P3-A.4 — Coverage & Resolve Hardening (Diagnosis)

**Date:** {time.strftime('%Y-%m-%d')}  
**Status:** `{raw.get('status')}`  
**Samples diagnosed:** {n}  
**Unresolved / Unknown-label:** {len(unresolved)} / {sum(1 for r in rows if r.get('unknown_league_label'))}  
**Resolve rate (this run):** {resolve_rate:.2%}  
**Premium rate (this run):** {premium_rate:.2%}  
**Freeze:** diagnosis only — **no** engine / Gateway / Cache / NMB / DRS / guard / throttle changes

---

## 1. Which fixtures became Unknown?

Unresolved soft partials stamp `league.name = "Unknown"` via `build_partial_analyze_data`.  
In P3-A.3 this produced the **Unknown** league bucket (n≈57) even when the corpus had a real `league_hint`.

### Failure classes (unresolved)

| Class | Count |
|-------|------:|
"""
    for cls, c in by_class.most_common():
        md += f"| `{cls}` | {c} |\n"

    md += f"""
### Discovery ID discarded

Corpus often carries `fixture_id_hint` from league/date discovery, but `analyze_fixture` resolves **only by team names**.  
Hints present yet unresolved: **{discovery_id_wasted}**

### Sample of Unknown / unresolved pairs

| Home | Away | league_hint | phase | class |
|------|------|-------------|-------|-------|
"""
    for r in top_unknown:
        md += (
            f"| {r['home']} | {r['away']} | {r.get('league_hint')} | "
            f"{r.get('phase')} | `{r.get('failure_class')}` |\n"
        )
    if len(unresolved) > 25:
        md += f"\n_(+{len(unresolved) - 25} more in `unknown_fixture_report.json`)_\n"

    md += """
---

## 2. Leagues with most resolve failures

Ranked by **corpus `league_hint`** (not the Unknown label):

| league_hint | n | failures | failure_rate |
|-------------|--:|---------:|-------------:|
"""
    for L in top_leagues:
        md += (
            f"| {L['league_hint']} | {L['n']} | {L['resolve_failures']} | "
            f"{L['failure_rate']} |\n"
        )

    md += f"""
---

## 3. Failure taxonomy

| Axis | Count | Share of unresolved |
|------|------:|--------------------:|
| aliases (team name) | {cause_axes['aliases']} | {cause_axes['aliases']/max(1,len(unresolved)):.0%} |
| fixture discovery / name re-resolve | {cause_axes['fixture_discovery']} | {cause_axes['fixture_discovery']/max(1,len(unresolved)):.0%} |
| API gaps / rate limit | {cause_axes['api_gaps']} | {cause_axes['api_gaps']/max(1,len(unresolved)):.0%} |
| sampling (seeds/control) | {cause_axes['sampling']} | {cause_axes['sampling']/max(1,len(unresolved)):.0%} |

**Interpretation**
- **Aliases:** `No team found matching …`
- **Fixture discovery:** teams OK but no H2H/recent/next match; often after discarding `fixture_id_hint`
- **API gaps:** 429 / 5xx / key issues (should be rare under throttle)
- **Sampling:** fiction control + named seeds without a current fixture window

---

## 4–5. Resolve ROI & premium uplift (model)

Baseline: resolve **{resolve_rate:.2%}**, premium **{premium_rate:.2%}**,  
P(premium|resolved) **{cond_premium:.2%}**

| If resolve → | Fixtures to recover | Expected premium | Δ premium pp | Hits premium≥50%? |
|--------------|--------------------:|-----------------:|-------------:|:-----------------:|
| 70% | {projections['if_resolve_70']['fixtures_to_recover']} | {projections['if_resolve_70']['expected_premium_rate']:.2%} | {projections['if_resolve_70']['premium_delta_pp']} | {'yes' if projections['if_resolve_70']['thin_premium_gate_50'] else 'no'} |
| 80% | {projections['if_resolve_80']['fixtures_to_recover']} | {projections['if_resolve_80']['expected_premium_rate']:.2%} | {projections['if_resolve_80']['premium_delta_pp']} | {'yes' if projections['if_resolve_80']['thin_premium_gate_50'] else 'no'} |
| 85% | {projections['if_resolve_85']['fixtures_to_recover']} | {projections['if_resolve_85']['expected_premium_rate']:.2%} | {projections['if_resolve_85']['premium_delta_pp']} | {'yes' if projections['if_resolve_85']['thin_premium_gate_50'] else 'no'} |

Resolve hardening alone **does not** unlock Thin Premium (still need signal density).

---

## Artifacts

- `roadmap/coverage_gap_report.md` (this file)
- `roadmap/unknown_fixture_report.json`
- `roadmap/resolve_roi_report.json`
- `roadmap/league_failure_report.json`
"""
    (out / "coverage_gap_report.md").write_text(md, encoding="utf-8")
    print(json.dumps({"unresolved": len(unresolved), "classes": dict(by_class), "roi": projections}, indent=2))


def main() -> None:
    raw = asyncio.run(run_diagnosis(min_n=100))
    if raw.get("status") == "BLOCKED_NO_API_KEY":
        print(json.dumps(raw, indent=2))
        sys.exit(2)
    _build_reports(raw)


if __name__ == "__main__":
    main()
