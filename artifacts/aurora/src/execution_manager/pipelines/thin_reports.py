"""
Thin report pipelines — Phase 4 Progressive Extraction Stage 1 (E1).

Extracted equivalents of mega-router `_run_bankroll` / `_run_learning` /
`_run_knowledge`. Data via DbReadPort only (no CM writes, no Tool Registry).
"""

from __future__ import annotations

from typing import Any

from src.execution_manager.contracts import (
    THIN_BANKROLL_STEPS,
    THIN_KNOWLEDGE_STEPS,
    THIN_LEARNING_STEPS,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
    StepStatus,
    StepTrace,
)
from src.execution_manager.observability import emit
from src.execution_manager.ports import PortBundle


def _conf_label(score: float) -> str:
    if score >= 8:
        return "strong"
    if score >= 6:
        return "moderate"
    if score >= 4:
        return "adequate"
    if score >= 2:
        return "weak"
    return "insufficient"


def _brain_meta() -> dict[str, Any]:
    try:
        from src.brain import get_brain_meta

        return get_brain_meta()
    except Exception:
        return {"brain_version": "unknown"}


def _assemble_bankroll_payload(stats: dict[str, Any]) -> dict[str, Any]:
    """Parity with mega-router `_run_bankroll` (legacy body retained for OFF path)."""
    s = stats or {}
    total = s.get("total_predictions", 0)
    wins = s.get("wins", 0)
    losses = s.get("losses", 0)
    pending = s.get("pending", 0)
    acc = s.get("current_accuracy")
    roi = s.get("roi_pct")
    best_m = s.get("best_market", "N/A")
    best_l = s.get("best_league", "N/A")
    breakdown = s.get("market_breakdown", []) or []
    league_br = s.get("league_breakdown", []) or []

    acc_str = f"{acc:.1f}%" if acc is not None else "not computed"
    roi_str = f"{roi:+.1f}%" if roi is not None else "not computed"

    pos: list[str] = []
    neg: list[str] = []
    for row in breakdown:
        rule = str(row.get("rule", "")).replace("_", " ").title()
        a = row.get("accuracy", 0)
        w, l = row.get("wins", 0), row.get("losses", 0)
        entry = f"{rule}: {a:.1f}% ({w}W/{l}L)"
        (pos if w >= l else neg).append(entry)

    hist: list[str] = []
    for lg in league_br[:5]:
        hist.append(
            f"{lg.get('league', '?')}: {lg.get('accuracy', 0):.1f}% "
            f"({lg.get('wins', 0)}W/{lg.get('losses', 0)}L)"
        )

    summary = (
        f"A Aurora monitorou {total} previsões: {wins}V / {losses}D / {pending} pendentes. "
        f"Precisão: {acc_str}. ROI: {roi_str}. "
        f"Melhor mercado: {best_m}. Melhor liga: {best_l}."
    )
    final = (
        f"Desempenho {'acima' if (acc or 0) >= 55 else 'abaixo'} da meta de precisão. "
        f"{'Mantenha a disciplina.' if (acc or 0) >= 55 else 'Considere reduzir as stakes até que a precisão se recupere.'}"
    )

    return {
        "intent": "bankroll_review",
        "entities": {
            "total_predictions": total,
            "wins": wins,
            "losses": losses,
            "pending": pending,
            "accuracy_pct": acc,
            "roi_pct": roi,
        },
        "match": None,
        "status": None,
        "is_live": False,
        "minute": None,
        "executive_summary": summary,
        "best_markets": [],
        "confidence": {
            "score": min(10.0, round((total / 20) * 10, 1)) if total else 0.0,
            "label": _conf_label(min(10.0, (total / 20) * 10) if total else 0),
            "explanation": (
                f"Baseado em {total} previsões monitoradas. "
                "Mais previsões aumentam a confiança estatística."
            ),
            "data_sources": ["Base de dados de aprendizado"],
        },
        "risk": {
            "level": "Low" if (acc or 0) >= 55 else "High",
            "flags": neg[:3],
            "invalidation_conditions": [],
        },
        "bankroll_recommendation": {
            "recommended_stake_pct": 0.0,
            "method": "quarter-Kelly",
            "examples": {},
            "reasoning": (
                "Apenas revisão de banca — nenhuma aposta específica recomendada. "
                "Analise uma partida para obter uma recomendação de stake."
            ),
            "no_bet": True,
        },
        "positive_factors": pos[:5],
        "negative_factors": neg[:5],
        "historical_references": hist,
        "knowledge_notes": [],
        "final_recommendation": final,
        "aurora_version": "Copilot v1.0",
        "brain": _brain_meta(),
    }


def _assemble_learning_payload(stats: dict[str, Any]) -> dict[str, Any]:
    """Parity with mega-router `_run_learning`."""
    s = stats or {}
    total = s.get("total_predictions", 0)
    wins = s.get("wins", 0)
    losses = s.get("losses", 0)
    acc = s.get("current_accuracy")
    breakdown = s.get("market_breakdown", []) or []
    league_br = s.get("league_breakdown", []) or []

    working = [r for r in breakdown if r.get("wins", 0) >= r.get("losses", 0)]
    struggling = [r for r in breakdown if r.get("losses", 0) > r.get("wins", 0)]

    hist: list[str] = []
    for lg in league_br[:6]:
        hist.append(
            f"{lg.get('league', '?')}: {lg.get('accuracy', 0):.1f}% accuracy "
            f"({lg.get('wins', 0)}W/{lg.get('losses', 0)}L)"
        )
    for r in working[:3]:
        hist.append(
            f"Market '{str(r.get('rule', '?')).replace('_', ' ').title()}' — "
            f"{r.get('accuracy', 0):.1f}% accuracy"
        )

    pos = [
        f"{str(r.get('rule', '?')).replace('_', ' ').title()}: "
        f"{r.get('accuracy', 0):.1f}% ({r.get('wins', 0)}W/{r.get('losses', 0)}L)"
        for r in working[:5]
    ]
    neg = [
        f"{str(r.get('rule', '?')).replace('_', ' ').title()}: "
        f"{r.get('accuracy', 0):.1f}% ({r.get('wins', 0)}W/{r.get('losses', 0)}L)"
        for r in struggling[:5]
    ]

    summary = (
        f"A Aurora resolveu {total} previsões: {wins}V / {losses}D. "
        f"Precisão atual: {f'{acc:.1f}%' if acc is not None else 'não calculada ainda'}. "
        f"A Aurora aprende continuamente — mudanças de peso requerem 20+ observações consistentes."
    )
    final = (
        "Motor de aprendizado ativo. "
        f"{'Mercados sólidos para continuar: ' + ', '.join(str(r.get('rule', '')).replace('_', ' ').title() for r in working[:2]) + '.' if working else ''}"
        f"{'Mercados para atenção: ' + ', '.join(str(r.get('rule', '')).replace('_', ' ').title() for r in struggling[:2]) + '.' if struggling else ''}"
    ).strip()

    return {
        "intent": "learning_recap",
        "entities": {
            "total_predictions": total,
            "wins": wins,
            "losses": losses,
            "accuracy_pct": acc,
        },
        "match": None,
        "status": None,
        "is_live": False,
        "minute": None,
        "executive_summary": summary,
        "best_markets": [],
        "confidence": {
            "score": min(10.0, round((total / 20) * 10, 1)) if total else 0.0,
            "label": _conf_label(min(10.0, (total / 20) * 10) if total else 0),
            "explanation": (
                f"A confiança estatística cresce com mais previsões resolvidas. "
                f"Atualmente {total} resolvidas."
            ),
            "data_sources": ["Base de dados de aprendizado", "Motor de evolução"],
        },
        "risk": {
            "level": "Low" if (acc or 0) >= 55 else "High",
            "flags": neg[:3],
            "invalidation_conditions": [],
        },
        "bankroll_recommendation": {
            "recommended_stake_pct": 0.0,
            "method": "quarter-Kelly",
            "examples": {},
            "no_bet": True,
            "reasoning": "Apenas revisão de aprendizado.",
        },
        "positive_factors": pos,
        "negative_factors": neg,
        "historical_references": hist,
        "knowledge_notes": [],
        "final_recommendation": final,
        "aurora_version": "Copilot v1.0",
        "brain": _brain_meta(),
    }


def _assemble_knowledge_payload(query: str, results: list[dict[str, Any]]) -> dict[str, Any]:
    """Parity with mega-router `_run_knowledge`."""
    notes: list[str] = []
    for item in results or []:
        cat = str(item.get("category", "")).replace("_", " ").title()
        title = item.get("title", "")
        desc = item.get("description", "")
        conf = item.get("confidence", 0)
        notes.append(f"[{cat} · {conf:.0%}] {title}: {desc}")

    summary = (
        f"Encontrei {len(results)} item(ns) de conhecimento para \"{query}\"."
        if results
        else f"Nenhum item de conhecimento encontrado para \"{query}\"."
    )
    final = (
        f"A base de conhecimento tem {len(results)} regra(s) relevante(s) para \"{query}\". "
        "Estas são aplicadas antes de cada previsão da Aurora."
    )

    return {
        "intent": "knowledge_search",
        "entities": {"query": query},
        "match": None,
        "status": None,
        "is_live": False,
        "minute": None,
        "executive_summary": summary,
        "best_markets": [],
        "confidence": {
            "score": 0.0,
            "label": "insufficient",
            "explanation": "Apenas busca de conhecimento — nenhuma análise de partida realizada.",
            "data_sources": ["Base de conhecimento"],
        },
        "risk": {
            "level": "Unknown",
            "flags": [],
            "invalidation_conditions": [],
        },
        "bankroll_recommendation": {
            "recommended_stake_pct": 0.0,
            "method": "quarter-Kelly",
            "examples": {},
            "no_bet": True,
            "reasoning": "Nenhuma aposta recomendada apenas com base em busca de conhecimento.",
        },
        "positive_factors": [],
        "negative_factors": [],
        "historical_references": [],
        "knowledge_notes": notes,
        "final_recommendation": final,
        "aurora_version": "Copilot v1.0",
        "brain": _brain_meta(),
    }


def _run_thin(
    request: ExecutionRequest,
    ports: PortBundle,
    *,
    pipeline_id: str,
    steps: tuple[str, ...],
) -> ExecutionResult:
    traces: list[StepTrace] = []
    emit("em.run.started", run_id=request.run_id, pipeline_id=pipeline_id)
    scratch: dict[str, Any] = {}
    payload: dict[str, Any] = {}

    for step_id in steps:
        emit("em.step.started", step_id=step_id)
        try:
            if step_id == "load_learning_stats":
                scratch["stats"] = ports.db.learning_stats()
            elif step_id == "search_knowledge_items":
                q = str((request.entities or {}).get("query") or "")
                scratch["query"] = q
                scratch["items"] = ports.db.knowledge_search(q)
            elif step_id == "assemble_bankroll_payload":
                payload = _assemble_bankroll_payload(scratch.get("stats") or {})
            elif step_id == "assemble_learning_payload":
                payload = _assemble_learning_payload(scratch.get("stats") or {})
            elif step_id == "assemble_knowledge_payload":
                payload = _assemble_knowledge_payload(
                    str(scratch.get("query") or ""),
                    list(scratch.get("items") or []),
                )
            traces.append(StepTrace(step_id=step_id, status=StepStatus.COMPLETED))
            emit("em.step.completed", step_id=step_id)
        except Exception as exc:
            traces.append(
                StepTrace(
                    step_id=step_id,
                    status=StepStatus.FAILED,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
            emit("em.step.failed", step_id=step_id, error=str(exc))
            emit("em.run.failed", run_id=request.run_id, pipeline_id=pipeline_id)
            return ExecutionResult(
                run_id=request.run_id,
                pipeline_id=pipeline_id,
                status=ExecutionStatus.FAILED,
                payload={"error": str(exc), "intent": pipeline_id},
                step_traces=traces,
                diagnostics={"phase4_stage1": True, "thin": True},
            )

    result = ExecutionResult(
        run_id=request.run_id,
        pipeline_id=pipeline_id,
        status=ExecutionStatus.COMPLETED,
        payload=payload,
        step_traces=traces,
        diagnostics={"phase4_stage1": True, "thin": True, "stub": False},
    )
    emit("em.run.completed", run_id=request.run_id, pipeline_id=pipeline_id)
    return result


def run_bankroll(request: ExecutionRequest, ports: PortBundle) -> ExecutionResult:
    return _run_thin(
        request,
        ports,
        pipeline_id="bankroll",
        steps=THIN_BANKROLL_STEPS,
    )


def run_learning(request: ExecutionRequest, ports: PortBundle) -> ExecutionResult:
    return _run_thin(
        request,
        ports,
        pipeline_id="learning",
        steps=THIN_LEARNING_STEPS,
    )


def run_knowledge(request: ExecutionRequest, ports: PortBundle) -> ExecutionResult:
    return _run_thin(
        request,
        ports,
        pipeline_id="knowledge",
        steps=THIN_KNOWLEDGE_STEPS,
    )


# Phase 2 registry aliases (names retained for harness compatibility).
run_bankroll_stub = run_bankroll
run_learning_stub = run_learning
run_knowledge_stub = run_knowledge
