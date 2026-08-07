"""
live_team_analyze composite — Phase 4 Progressive Extraction Stage 4 (E4).

T0 search_live_for_team (Tool Use live list via FetchLiveFeed) +
T1 delegate_analyze with prefer_live=True (same Step Runner analyze path).

No CM writes. No attach_match_card. Match-card / post-integrity / CM eligibility
remain Router / Orchestration (§4.6–§4.7).
"""

from __future__ import annotations

from typing import Any

from src.execution_manager.contracts import (
    LIVE_TEAM_STEP_ORDER,
    ExecutionMode,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStatus,
    StepStatus,
    StepTrace,
)
from src.execution_manager.observability import emit
from src.execution_manager.pipelines.analyze import run_analyze
from src.execution_manager.ports import PortBundle


def _fixtures_from_feed(feed: Any) -> list[dict[str, Any]]:
    if isinstance(feed, list):
        return list(feed)
    if not isinstance(feed, dict):
        return []
    matches = feed.get("matches")
    if isinstance(matches, list):
        return list(matches)
    fixtures = feed.get("fixtures")
    if isinstance(fixtures, list):
        return list(fixtures)
    return []


def match_team_in_live_feed(
    team: str, feed: Any
) -> tuple[str, str]:
    """
    T0 helper — find home/away names for `team` in a live feed payload.

    Uses EntityResolver fold / name_match (SoT live_team bridge parity).
    Returns ("", "") when not found.
    """
    team = (team or "").strip()
    if not team:
        return "", ""
    try:
        from src.core.entity_resolver import match_team_in_fixture_names
    except Exception:
        return "", ""
    for fx in _fixtures_from_feed(feed):
        home = ((fx.get("home") or {}).get("name") or "")
        away = ((fx.get("away") or {}).get("name") or "")
        if match_team_in_fixture_names(team, home, away):
            return str(home), str(away)
    return "", ""


def _not_found_payload(team: str) -> dict[str, Any]:
    """SoT-shaped NotFound when team is absent from the live feed (no CM write)."""
    try:
        from src.brain import get_brain_meta
        from src.core.inference_context import InferenceContext

        ictx = InferenceContext(soft_mode=True)
        ictx.register_failure(
            "live_team_lookup",
            f"{team} não está no feed ao vivo",
            signal="fixture",
        )
        ictx.finalize()
        brain = {**get_brain_meta(), "inference": ictx.explainability()}
        conf_score = ictx.apply_to_score(2.0)
        penalty = ictx.total_penalty()
        missing = list(ictx.missing_signals)
        notes = ictx.knowledge_notes_pt()
    except Exception:
        brain = {}
        conf_score = 2.0
        penalty = 0.0
        missing = []
        notes = []

    return {
        "intent": "live_team_analysis",
        "match": None,
        "is_live": False,
        "status": "NotFound",
        "minute": None,
        "executive_summary": (
            f"**{team}** não está jogando ao vivo agora.\n\n"
            f"A Aurora registrou a falha (Inference V2) e manteve a conversa "
            f"com confiança reduzida.\n\n"
            f"Se souber o adversário, diga:\n"
            f"\"Analisar {team} x [adversário]\""
        ),
        "best_markets": [],
        "confidence": {
            "score": conf_score,
            "label": "insufficient",
            "explanation": (
                f"Inference V2: time ausente ao vivo — "
                f"penalidade −{penalty:.1f}"
            ),
            "data_sources": ["Feed ao vivo API-Football", "Inference Layer V2"],
        },
        "risk": {
            "level": "Unknown",
            "flags": missing,
            "invalidation_conditions": [],
        },
        "bankroll_recommendation": {
            "recommended_stake_pct": 0.0,
            "method": "quarter-Kelly",
            "examples": {},
            "no_bet": True,
            "reasoning": "Sem partida ao vivo identificada.",
        },
        "positive_factors": [],
        "negative_factors": [],
        "historical_references": [],
        "knowledge_notes": notes,
        "final_recommendation": (
            f"Não encontrei {team} ao vivo. "
            f"Tente: \"Analisar {team} x [adversário]\""
        ),
        "aurora_version": "Copilot v1.0",
        "brain": brain,
    }


def run_live_team_analyze(
    request: ExecutionRequest, ports: PortBundle
) -> ExecutionResult:
    """
    T0–T1 live_team_analyze composite (Plan E4).

    T0: FetchLiveFeed + team search.
    T1: delegate to run_analyze with prefer_live=True when a match is found.
    """
    traces: list[StepTrace] = []
    emit("em.run.started", run_id=request.run_id, pipeline_id="live_team_analyze")
    ents = dict(request.entities or {})
    flags = dict(request.flags or {})
    team = str(ents.get("team") or flags.get("team") or "").strip()

    # T0 — search_live_for_team
    emit("em.step.started", step_id="search_live_for_team")
    feed = ports.fetch_live_feed.fetch(
        force_refresh=bool(flags.get("force_refresh"))
    )
    home, away = match_team_in_live_feed(team, feed)
    # Harness override: explicit home/away without requiring feed match.
    if not home and not away:
        home = str(ents.get("home") or flags.get("home") or "")
        away = str(ents.get("away") or flags.get("away") or "")
        if home and away and not team:
            # explicit pair counts as T0 hit for harness
            pass
        elif not (home and away):
            home, away = "", ""
        # If team was set and feed miss, do not accept unrelated home/away
        # unless flags force_delegate (harness).
        if team and not match_team_in_live_feed(team, feed):
            if flags.get("force_delegate"):
                home = str(ents.get("home") or flags.get("home") or home)
                away = str(ents.get("away") or flags.get("away") or away)
            else:
                home, away = "", ""

    traces.append(
        StepTrace(
            step_id="search_live_for_team",
            status=StepStatus.COMPLETED,
            reason="matched" if (home and away) else "not_found",
        )
    )
    emit(
        "em.step.completed",
        step_id="search_live_for_team",
        matched=bool(home and away),
    )

    if not (home and away):
        # T1 skipped — team absent from live feed
        emit("em.step.started", step_id="delegate_analyze")
        traces.append(
            StepTrace(
                step_id="delegate_analyze",
                status=StepStatus.SKIPPED,
                reason="live_team_not_found",
            )
        )
        emit("em.step.completed", step_id="delegate_analyze", skipped=True)
        assert [t.step_id for t in traces] == list(LIVE_TEAM_STEP_ORDER)
        result = ExecutionResult(
            run_id=request.run_id,
            pipeline_id="live_team_analyze",
            status=ExecutionStatus.COMPLETED,
            payload=_not_found_payload(team or "time"),
            step_traces=traces,
            diagnostics={
                "phase4_stage4": True,
                "live_team_analyze": True,
                "stub": False,
                "matched": False,
                "team": team,
            },
        )
        emit("em.run.completed", run_id=request.run_id, pipeline_id="live_team_analyze")
        return result

    # T1 — delegate_analyze (prefer_live=True)
    emit("em.step.started", step_id="delegate_analyze")
    child_flags = dict(flags)
    child_flags["prefer_live"] = True
    child_flags["home"] = home
    child_flags["away"] = away
    child_ents = dict(ents)
    child_ents["home"] = home
    child_ents["away"] = away
    child = ExecutionRequest(
        run_id=f"{request.run_id}:analyze",
        pipeline_id="analyze",
        session_id=request.session_id,
        mode=request.mode if isinstance(request.mode, ExecutionMode) else request.mode,
        entities=child_ents,
        flags=child_flags,
        budget_token=request.budget_token,
        read_projections=request.read_projections,
        timeout_ms=request.timeout_ms,
        trace_parent=request.trace_parent,
    )
    analyze_result = run_analyze(child, ports)
    traces.append(StepTrace(step_id="delegate_analyze", status=StepStatus.COMPLETED))
    emit("em.step.completed", step_id="delegate_analyze")

    assert [t.step_id for t in traces] == list(LIVE_TEAM_STEP_ORDER)

    payload = dict(analyze_result.payload) if isinstance(analyze_result.payload, dict) else {}
    # Surface live_team bridge markers for Router post-processing (not CM).
    payload.setdefault("entities", {})
    if isinstance(payload.get("entities"), dict):
        payload["entities"] = dict(payload["entities"])
        payload["entities"].setdefault("home", home)
        payload["entities"].setdefault("away", away)
        payload["entities"]["live_team"] = team

    diagnostics = {
        "phase4_stage4": True,
        "live_team_analyze": True,
        "stub": False,
        "matched": True,
        "team": team,
        "home": home,
        "away": away,
        "child_run_id": child.run_id,
        "child_diagnostics": dict(analyze_result.diagnostics or {}),
    }
    fx = (analyze_result.diagnostics or {}).get("analyze_fixture_data")
    if isinstance(fx, dict):
        diagnostics["analyze_fixture_data"] = fx

    result = ExecutionResult(
        run_id=request.run_id,
        pipeline_id="live_team_analyze",
        status=analyze_result.status,
        payload=payload,
        step_traces=traces + list(analyze_result.step_traces),
        abort_reason=analyze_result.abort_reason,
        fixture_quality=analyze_result.fixture_quality,
        diagnostics=diagnostics,
    )
    emit("em.run.completed", run_id=request.run_id, pipeline_id="live_team_analyze")
    return result


# Phase 2 registry name — real Stage 4 handler (stub alias retained).
run_live_team_analyze_stub = run_live_team_analyze
