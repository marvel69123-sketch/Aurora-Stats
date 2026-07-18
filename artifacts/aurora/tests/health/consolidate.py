"""
Consolidate AEP / Simulator / Frustration / LLM Judge into one health report.

Observability only — never invents match data, never changes engines.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def classify_health(score: float) -> str:
    if score >= 95:
        return "Excelente"
    if score >= 85:
        return "Muito Boa"
    if score >= 70:
        return "Boa"
    if score >= 50:
        return "Atenção"
    return "Crítica"


def _num(val: Any, default: float | None = None) -> float | None:
    if val is None:
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def extract_metrics(
    aep: dict[str, Any] | None,
    sim: dict[str, Any] | None,
    frust: dict[str, Any] | None,
    judge: dict[str, Any] | None,
) -> dict[str, Any]:
    aep_s = (aep or {}).get("summary") if isinstance(aep, dict) else {}
    if not isinstance(aep_s, dict):
        aep_s = {}
    sim_m = (sim or {}).get("metrics") if isinstance(sim, dict) else {}
    if not isinstance(sim_m, dict):
        sim_m = {}

    conversation_success = _num(
        sim_m.get("conversation_success_rate"),
        _num((sim or {}).get("success_rate"), _num(aep_s.get("success_rate"), 0.0)),
    )
    aep_success = _num(aep_s.get("success_rate"), conversation_success)

    # Loop rate: prefer simulator metrics; else loops/total
    loop_rate = _num(sim_m.get("loop_rate"))
    if loop_rate is None and isinstance(sim, dict):
        total = _num(sim.get("total_runs"), 0) or 0
        loops = _num(sim.get("loops"), 0) or 0
        loop_rate = round((loops / total) * 100.0, 2) if total else 0.0
    if loop_rate is None:
        loop_rate = 0.0

    context_preservation = _num(sim_m.get("context_preservation"), 100.0)

    # Organic frustration from simulator; recovery from frustration suite
    sim_frust = (sim or {}).get("frustration_analytics") if isinstance(sim, dict) else None
    if isinstance(sim_frust, dict) and sim_frust.get("frustration_rate") is not None:
        frustration_rate = _num(sim_frust.get("frustration_rate"), 0.0) or 0.0
    else:
        # flags count / runs as soft organic rate
        total = _num((sim or {}).get("total_runs"), 0) or 0
        fr_flags = _num((sim or {}).get("frustration_detected"), 0) or 0
        frustration_rate = round((fr_flags / total) * 100.0, 2) if total else 0.0

    recovery_rate = _num((frust or {}).get("recovery_rate"), None)
    if recovery_rate is None and isinstance(sim_frust, dict):
        recovery_rate = _num(sim_frust.get("recovery_rate"), 100.0)
    if recovery_rate is None:
        recovery_rate = 100.0

    llm_overall = _num((judge or {}).get("overall"))
    if llm_overall is None and isinstance(sim, dict):
        llm_overall = _num(((sim.get("llm_judge") or {}) if isinstance(sim.get("llm_judge"), dict) else {}).get("overall"))
    if llm_overall is None and isinstance(frust, dict):
        llm_overall = _num(((frust.get("llm_judge") or {}) if isinstance(frust.get("llm_judge"), dict) else {}).get("overall"))
    if llm_overall is None:
        llm_overall = 0.0

    naturalness = _num((judge or {}).get("naturalness"), llm_overall)
    credibility = _num((judge or {}).get("credibility"), llm_overall)

    return {
        "aep_success_rate": round(aep_success or 0.0, 1),
        "conversation_success": round(conversation_success or 0.0, 1),
        "loop_rate": round(loop_rate or 0.0, 2),
        "context_preservation": round(context_preservation or 0.0, 1),
        "frustration_rate": round(frustration_rate or 0.0, 2),
        "recovery_rate": round(recovery_rate or 0.0, 1),
        "llm_overall": round(llm_overall or 0.0, 1),
        "naturalness": round(naturalness or 0.0, 1),
        "credibility": round(credibility or 0.0, 1),
        "sources_present": {
            "aep": aep is not None,
            "simulator": sim is not None,
            "frustration": frust is not None,
            "llm_judge": judge is not None,
        },
    }


def compute_health_score(m: dict[str, Any]) -> float:
    """
    Weighted 0–100 health score.

    Higher is better for success / preservation / recovery / llm.
    Lower is better for loop_rate / frustration_rate (inverted).
    """
    aep = float(m.get("aep_success_rate") or 0)
    conv = float(m.get("conversation_success") or 0)
    ctx = float(m.get("context_preservation") or 0)
    rec = float(m.get("recovery_rate") or 0)
    llm10 = float(m.get("llm_overall") or 0)
    nat10 = float(m.get("naturalness") or llm10)
    cred10 = float(m.get("credibility") or llm10)
    loop = float(m.get("loop_rate") or 0)
    frust = float(m.get("frustration_rate") or 0)

    loop_health = max(0.0, 100.0 - loop * 8.0)  # 0% loops → 100; 5% → 60
    frust_health = max(0.0, 100.0 - frust * 5.0)  # 0% → 100; 2% → 90
    llm_health = (llm10 / 10.0) * 100.0
    nat_health = (nat10 / 10.0) * 100.0
    cred_health = (cred10 / 10.0) * 100.0

    score = (
        aep * 0.22
        + conv * 0.18
        + ctx * 0.10
        + rec * 0.10
        + loop_health * 0.12
        + frust_health * 0.08
        + llm_health * 0.10
        + nat_health * 0.05
        + cred_health * 0.05
    )
    return round(max(0.0, min(100.0, score)), 1)


def compute_trend(
    current_score: float,
    history_path: Path,
) -> tuple[str, list[dict[str, Any]]]:
    """Compare with last stored report. Returns (trend, history_tail)."""
    hist: list[dict[str, Any]] = []
    if history_path.is_file():
        try:
            raw = json.loads(history_path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                hist = [x for x in raw if isinstance(x, dict)]
        except Exception:
            hist = []

    trend = "flat"
    if hist:
        prev = _num(hist[-1].get("health_score"))
        if prev is not None:
            if current_score > prev + 0.3:
                trend = "up"
            elif current_score < prev - 0.3:
                trend = "down"
            else:
                trend = "flat"
    return trend, hist[-20:]


def build_health_report(
    *,
    root: Path,
    version: str | None = None,
) -> dict[str, Any]:
    paths = {
        "aep": root / "observations" / "aep_v1" / "last_run.json",
        "simulator": root / "tests" / "simulator" / "results" / "last_simulation.json",
        "frustration": root / "tests" / "frustration" / "results" / "last_frustration.json",
        "llm_judge": root / "tests" / "judge" / "results" / "last_judge.json",
    }
    aep = _load_json(paths["aep"])
    sim = _load_json(paths["simulator"])
    frust = _load_json(paths["frustration"])
    judge = _load_json(paths["llm_judge"])

    metrics = extract_metrics(aep, sim, frust, judge)
    health_score = compute_health_score(metrics)
    status = classify_health(health_score)

    health_dir = root / "observations" / "health"
    history_path = health_dir / "history.json"
    trend, prev_hist = compute_trend(health_score, history_path)

    if not version:
        try:
            from src.core.deploy_identity import get_backend_commit

            version = get_backend_commit() or "unknown"
        except Exception:
            version = "unknown"

    report = {
        "platform": "AEP",
        "component": "aurora_health_center",
        "version": "5.0.0",
        "backend_commit": version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "health_score": health_score,
        "status": status,
        "loop_rate": metrics["loop_rate"],
        "frustration_rate": metrics["frustration_rate"],
        "llm_overall": metrics["llm_overall"],
        "trend": trend,
        "metrics": {
            "overall_health_score": health_score,
            "conversation_success": metrics["conversation_success"],
            "aep_success_rate": metrics["aep_success_rate"],
            "loop_rate": metrics["loop_rate"],
            "context_preservation": metrics["context_preservation"],
            "frustration_rate": metrics["frustration_rate"],
            "recovery_rate": metrics["recovery_rate"],
            "llm_overall_score": metrics["llm_overall"],
            "naturalness": metrics["naturalness"],
            "credibility": metrics["credibility"],
        },
        "sources": metrics["sources_present"],
        "source_paths": {k: str(v) for k, v in paths.items()},
        "trend_by_version": prev_hist
        + [
            {
                "backend_commit": version,
                "health_score": health_score,
                "status": status,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
        ],
        "components": {
            "aep": {
                "success_rate": metrics["aep_success_rate"],
                "total": ((aep or {}).get("summary") or {}).get("total") if aep else None,
            },
            "simulator": {
                "success_rate": metrics["conversation_success"],
                "loop_rate": metrics["loop_rate"],
                "context_preservation": metrics["context_preservation"],
            },
            "frustration": {
                "organic_frustration_rate": metrics["frustration_rate"],
                "recovery_rate": metrics["recovery_rate"],
                "suite_frustration_rate": (frust or {}).get("frustration_rate"),
                "top_causes": (frust or {}).get("top_causes"),
            },
            "llm_judge": {
                "overall": metrics["llm_overall"],
                "naturalness": metrics["naturalness"],
                "credibility": metrics["credibility"],
                "band": (judge or {}).get("band"),
            },
        },
    }
    return report


def persist_report(report: dict[str, Any], root: Path) -> Path:
    health_dir = root / "observations" / "health"
    health_dir.mkdir(parents=True, exist_ok=True)
    out = health_dir / "health_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # Append history (dedupe last identical commit+score)
    history_path = health_dir / "history.json"
    hist: list[dict[str, Any]] = []
    if history_path.is_file():
        try:
            raw = json.loads(history_path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                hist = [x for x in raw if isinstance(x, dict)]
        except Exception:
            hist = []
    entry = {
        "backend_commit": report.get("backend_commit"),
        "health_score": report.get("health_score"),
        "status": report.get("status"),
        "loop_rate": report.get("loop_rate"),
        "frustration_rate": report.get("frustration_rate"),
        "llm_overall": report.get("llm_overall"),
        "generated_at": report.get("generated_at"),
    }
    if not hist or hist[-1].get("generated_at") != entry.get("generated_at"):
        hist.append(entry)
    hist = hist[-50:]
    history_path.write_text(json.dumps(hist, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
