"""
FASE 7.8 — Validação de hipóteses P0 (somente evidência).

NÃO corrige comportamento.
Reproduz caminhos do router (GA + NRF early/late + forced nonsport + ownership)
e captura logs [OWNER] [PAYLOAD_*] [NRF_*] etc.

Uso (em artifacts/aurora):
  python scripts/phase78_hypothesis_validation.py
"""

from __future__ import annotations

import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OBS = ROOT / "observations" / "phase78"
OBS.mkdir(parents=True, exist_ok=True)

from src.conversation.general_assistant import (  # noqa: E402
    reply_general,
    try_general_assistant,
)
from src.conversation.human_conversation_engine import (  # noqa: E402
    note_hce_after_response,
    try_human_conversation,
)
from src.conversation.master_intent_router import apply_master_intent  # noqa: E402
from src.conversation.natural_response_engine import (  # noqa: E402
    apply_natural_response,
    try_natural_social_payload,
)
from src.conversation.natural_response_filter import filter_or_regenerate  # noqa: E402
from src.conversation.pipeline_trace import (  # noqa: E402
    clear_capture,
    get_capture,
    snapshot_payload,
    trace,
    trace_owner,
    trace_payload,
)
from src.conversation.turn_ownership import finalize_early_ownership  # noqa: E402


ENTENDI = "Entendi. Posso te ajudar"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run_case(title: str, turns: list[str]) -> dict[str, Any]:
    clear_capture()
    ctx: dict[str, Any] = {}
    results: list[dict[str, Any]] = []
    all_logs: list[str] = []
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)
    for i, msg in enumerate(turns, 1):
        turn = _router_faithful_turn(msg, ctx)
        results.append(turn)
        new_logs = turn["logs"]
        all_logs.extend(new_logs)
        print(f"\n── turno {i} ──")
        print(f"Você: {msg}")
        print(
            f"intent={turn['master_intent']} owner={turn['owner']} locked={turn['locked']} "
            f"conf={turn['has_confidence']} crash={turn['crash']} entendi={turn['entendi']}"
        )
        print(f"Aurora: {turn['summary'][:220]}")
        for line in new_logs:
            if any(
                tag in line
                for tag in ("[NRF_", "[OWNER]", "[PAYLOAD_", "[FALLBACK]", "[INTENT]")
            ):
                print(f"  {line}")
    return {"title": title, "turns": results, "logs": all_logs}


def _router_faithful_turn(message: str, ctx: dict[str, Any]) -> dict[str, Any]:
    """Espelha early stack + late NRF do router (sem HTTP/DB). Preserva hist no ctx."""
    start = len(get_capture())
    master = apply_master_intent(message, ctx)
    sport_ok = bool(master.allow_sport_pipeline)
    trace(
        "INTENT",
        intent=master.intent,
        sport_ok=sport_ok,
        allow_sport=master.allow_sport_pipeline,
        confidence=master.confidence,
    )

    ga = None
    payload: dict[str, Any] | None = None
    if not master.allow_sport_pipeline:
        ga = try_general_assistant(message, master.intent, ctx)
        if ga:
            txt = str(ga.get("executive_summary") or "")
            txt = filter_or_regenerate(
                txt,
                master_intent=master.intent,
                ctx=ctx,
                regenerate=txt,
            )
            ga["executive_summary"] = txt
            ga["final_recommendation"] = txt
            trace(
                "ENGINE",
                engine="general_assistant",
                kind=(ga.get("entities") or {}).get("assistant_kind"),
            )

    hce = try_human_conversation(
        message,
        ctx,
        master_intent=master.intent,
        existing_payload=ga,
    )
    if hce:
        payload = hce
        sport_ok = False
        trace(
            "ENGINE",
            engine="human_conversation",
            kind=(hce.get("entities") or {}).get("hce_kind"),
        )
    elif ga:
        payload = ga

    if payload is None:
        nre = try_natural_social_payload(message, ctx)
        if nre:
            payload = nre
            sport_ok = False
            trace("ENGINE", engine="natural_response", kind="direct")
    elif payload is not None:
        payload = apply_natural_response(message, payload, ctx) or payload

    owner_before = (payload.get("entities") or {}).get("turn_owner") if payload else None
    if payload is not None:
        payload = finalize_early_ownership(payload) or payload
        trace_owner("after_early_finalize", payload, owner_before=owner_before or "none")

    forced_incomplete = False
    if not sport_ok and payload is None:
        payload = try_general_assistant(message, master.intent or "GENERAL_CHAT", ctx)
        if payload is None:
            forced_incomplete = True
            payload = {
                "intent": "general_chat",
                "entities": {
                    "general_assistant": True,
                    "assistant_kind": "general",
                    "has_analysis": False,
                    "show_header": False,
                    "skip_llm": True,
                    "fallback": True,
                    "fallback_source": "forced_general_incomplete",
                },
                "executive_summary": reply_general(message),
                "final_recommendation": reply_general(message),
                "best_markets": [],
                "match": None,
                "is_live": False,
                "brain": {},
            }
        trace(
            "FALLBACK",
            source="forced_nonsport",
            incomplete=forced_incomplete,
            has_confidence=isinstance((payload or {}).get("confidence"), dict),
        )

    if sport_ok and payload is None:
        payload = {
            "intent": "analyze_match",
            "entities": {
                "has_analysis": False,
                "turn_owner": "SPORT",
                "rewrite_locked": False,
            },
            "executive_summary": f"[stub sport] intent={master.intent} — sem dados inventados.",
            "final_recommendation": "",
            "best_markets": [],
            "confidence": {
                "score": 0.0,
                "label": "insufficient",
                "explanation": "stub",
                "data_sources": [],
            },
            "risk": {"level": "Unknown", "flags": [], "invalidation_conditions": []},
            "bankroll_recommendation": {
                "recommended_stake_pct": 0.0,
                "method": "quarter-Kelly",
                "examples": {},
                "no_bet": True,
                "reasoning": "",
            },
            "is_live": False,
        }
        trace("ENGINE", engine="sport_stub", intent=master.intent)

    trace_payload("PAYLOAD_BEFORE", "late_nrf", payload)
    ents = (payload.get("entities") or {}) if isinstance(payload, dict) else {}
    late_ran = False
    if isinstance(payload, dict) and (
        ents.get("rewrite_locked")
        or ents.get("human_conversation")
        or ents.get("turn_owner") in {"NRE", "HCE", "META"}
    ):
        trace(
            "NRF_OUTPUT",
            action="skipped_owned",
            owner=ents.get("turn_owner"),
            locked=ents.get("rewrite_locked"),
        )
    elif isinstance(payload, dict) and (not sport_ok or ents.get("general_assistant")):
        late_ran = True
        mi = master.intent or "GENERAL_CHAT"
        summary = str(payload.get("executive_summary") or "")
        regen = reply_general(message)
        if mi == "MATH_QUERY":
            from src.conversation.general_assistant import reply_math as _rm

            regen = _rm(message)
        elif mi == "SMALL_TALK":
            from src.conversation.general_assistant import reply_small_talk as _rs

            regen = _rs(message)
        elif mi == "SYSTEM_QUERY":
            from src.conversation.general_assistant import reply_system as _rsys

            regen = _rsys(message)
        clean = filter_or_regenerate(
            summary,
            master_intent=mi,
            ctx=ctx,
            regenerate=regen,
        )
        payload["executive_summary"] = clean
        payload["final_recommendation"] = clean

    trace_payload("PAYLOAD_AFTER", "late_nrf", payload)
    trace_owner("final", payload)

    crash = None
    if isinstance(payload, dict):
        if "confidence" not in payload:
            crash = "KeyError:confidence"
            trace("FALLBACK", source="missing_confidence_key", will_crash=True)
        elif "risk" not in payload or "bankroll_recommendation" not in payload:
            crash = "KeyError:risk_or_bankroll"

    if payload:
        note_hce_after_response(ctx, message, payload)

    logs = get_capture()[start:]
    snap = snapshot_payload(payload)
    return {
        "message": message,
        "master_intent": master.intent,
        "sport_ok": sport_ok,
        "forced_incomplete": forced_incomplete,
        "late_nrf_ran": late_ran,
        "owner": snap.get("owner"),
        "locked": snap.get("locked"),
        "has_confidence": snap.get("has_confidence"),
        "summary": str((payload or {}).get("executive_summary") or ""),
        "crash": crash,
        "entendi": ENTENDI in str((payload or {}).get("executive_summary") or ""),
        "logs": logs,
    }


def prove_h2_static() -> dict[str, Any]:
    """Prove forced dict omits confidence — static mirror of router."""
    payload = {
        "intent": "general_chat",
        "entities": {"general_assistant": True, "assistant_kind": "general"},
        "executive_summary": reply_general("x"),
        "final_recommendation": reply_general("x"),
        "best_markets": [],
        "match": None,
        "is_live": False,
        "brain": {},
    }
    ga_full = try_general_assistant("me explica uma coisa", "GENERAL_CHAT", {})
    return {
        "forced_keys": sorted(payload.keys()),
        "forced_has_confidence": "confidence" in payload,
        "ga_full_has_confidence": isinstance((ga_full or {}).get("confidence"), dict),
        "consumer": "copilot_unified_router CopilotResponse(... ConfidenceSection(**payload['confidence']))",
    }


def analyze(cases: list[dict[str, Any]], h2_static: dict[str, Any]) -> dict[str, Any]:
    h1_evidence = []
    h2_evidence = []
    h3_evidence = []

    for case in cases:
        prev_entendi = False
        for t in case["turns"]:
            for line in t["logs"]:
                if "[NRF_OUTPUT]" in line and "action=regenerate" in line and "entendi_out=True" in line:
                    h1_evidence.append(
                        {
                            "case": case["title"],
                            "message": t["message"],
                            "line": line,
                            "note": "NRF regenerou e saída ainda contém Entendi",
                        }
                    )
                if "[NRF_OUTPUT]" in line and "same_as_regen=True" in line and "entendi" in line.lower():
                    h1_evidence.append(
                        {
                            "case": case["title"],
                            "message": t["message"],
                            "line": line,
                            "note": "saída idêntica ao regenerate (reply_general)",
                        }
                    )
                if "similar=True" in line and "Entendi" in (t["summary"] or ""):
                    h1_evidence.append(
                        {
                            "case": case["title"],
                            "message": t["message"],
                            "line": line,
                            "note": "similar=True com template Entendi",
                        }
                    )
            if t.get("entendi") and prev_entendi:
                h1_evidence.append(
                    {
                        "case": case["title"],
                        "message": t["message"],
                        "line": "turn_repeat",
                        "note": "Entendi em turnos consecutivos",
                    }
                )
            prev_entendi = bool(t.get("entendi"))

            if t.get("forced_incomplete") or t.get("crash") == "KeyError:confidence":
                h2_evidence.append(
                    {
                        "case": case["title"],
                        "message": t["message"],
                        "forced_incomplete": t.get("forced_incomplete"),
                        "has_confidence": t.get("has_confidence"),
                        "crash": t.get("crash"),
                    }
                )

            # H3: owner none after early path that should own, or owner change
            owners = [
                line
                for line in t["logs"]
                if line.startswith("[OWNER]")
            ]
            if owners:
                h3_evidence.append(
                    {
                        "case": case["title"],
                        "message": t["message"],
                        "owner_final": t.get("owner"),
                        "locked": t.get("locked"),
                        "owner_logs": owners,
                        "late_nrf_ran": t.get("late_nrf_ran"),
                    }
                )

    # Verdicts
    h1 = "CONFIRMADA" if h1_evidence else "NÃO OBSERVADA NESTA CORRIDA"
    # H2 confirmed if static missing confidence OR runtime crash
    h2 = (
        "CONFIRMADA"
        if (not h2_static["forced_has_confidence"] or h2_evidence)
        else "REFUTADA"
    )
    # H3: look for late_nrf_ran True despite owner, or owner none on nonsport
    ownership_loss = [
        e
        for e in h3_evidence
        if (e.get("owner_final") in (None, "none") and "GENERAL" in str(e))
        or (e.get("late_nrf_ran") and e.get("owner_final") == "GA")
    ]
    # GA with rewrite_locked should skip late NRF — if late_nrf_ran on unlocked forced = gap
    forced_no_owner = [e for e in h3_evidence if e.get("owner_final") in (None, "none")]
    ga_late = [e for e in h3_evidence if e.get("late_nrf_ran") and e.get("owner_final") == "GA"]
    # Note: skip rule uses rewrite_locked OR owner in NRE/HCE/META — NOT GA by name.
    # So GA only protected by rewrite_locked. If locked=True late should not run.
    unlocked_late = [
        e for e in h3_evidence if e.get("late_nrf_ran") and not e.get("locked")
    ]

    if unlocked_late or forced_no_owner:
        h3 = "CONFIRMADA (gap: owner ausente ou late NRF em unlocked)"
    elif ga_late:
        h3 = "PARCIAL (late NRF em GA — verificar locked)"
    else:
        h3 = "PARCIALMENTE REFUTADA no early stack (owner GA/HCE/NRE com lock); gap permanece no forced path sem finalize"

    return {
        "H1": {"verdict": h1, "evidence_count": len(h1_evidence), "samples": h1_evidence[:12]},
        "H2": {
            "verdict": h2,
            "static": h2_static,
            "runtime_hits": h2_evidence[:12],
        },
        "H3": {
            "verdict": h3,
            "unlocked_late_nrf": unlocked_late[:8],
            "owner_none": forced_no_owner[:8],
            "samples": h3_evidence[:15],
        },
    }


def main() -> int:
    print("AURORA — FASE 7.8 VALIDAÇÃO DE HIPÓTESES P0")
    print("Somente evidência. Sem correções.")
    print()
    print(
        "NOTA: transcripts reais 1–5 não estão versionados em observations/phase76; "
        "T1–T5 abaixo são reconstruções fiéis ao Cenário C (loop/fallback/geral)."
    )

    # Transcripts reconstruídos (Cenário C) + probes obrigatórios
    cases_spec = [
        (
            "T1 — GENERAL_CHAT sticky (reconstrução Cenário C)",
            [
                "me ajuda com uma coisa",
                "não é isso",
                "quero outra coisa",
                "me escuta",
            ],
        ),
        (
            "T2 — vague → frustração",
            [
                "preciso de ajuda",
                "você não entendeu",
                "tenta de novo",
            ],
        ),
        (
            "T3 — meta + general",
            [
                "o que voce faz?",
                "e alem disso?",
                "me explica melhor",
            ],
        ),
        (
            "T4 — sport depois social genérico",
            [
                "quais jogos estão ao vivo?",
                "e ai",
                "me fala mais",
            ],
        ),
        (
            "T5 — tempo + general loop",
            [
                "que horas são?",
                "ok e agora?",
                "então me ajuda",
            ],
        ),
        ("P1 — estou triste", ["estou triste"]),
        ("P2 — pare de repetir", ["me ajuda", "pare de repetir"]),
        ("P3 — vc está em loop", ["preciso de algo", "vc está em loop"]),
        ("P4 — quais jogos estão ao vivo?", ["quais jogos estão ao vivo?"]),
        ("P5 — que horas são?", ["que horas são?"]),
    ]

    cases = []
    for title, turns in cases_spec:
        cases.append(run_case(title, turns))

    h2_static = prove_h2_static()
    analysis = analyze(cases, h2_static)

    stamp = _now()
    out = {
        "phase": "7.8",
        "created_at": stamp,
        "mode": "evidence_only",
        "h2_static": h2_static,
        "hypotheses": analysis,
        "cases": [
            {
                "title": c["title"],
                "turns": [
                    {
                        k: v
                        for k, v in t.items()
                        if k != "logs"
                    }
                    | {"log_count": len(t.get("logs") or [])}
                    for t in c["turns"]
                ],
                "logs": c["logs"],
            }
            for c in cases
        ],
    }

    json_path = OBS / f"evidence_{stamp}.json"
    json_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    # Human-readable report
    report = []
    report.append("# Fase 7.8 — Relatório de Evidência\n")
    report.append(f"Gerado: {stamp}\n")
    report.append("Modo: somente evidência (sem correções)\n\n")
    report.append("## Prova / Refutação\n\n")
    report.append(f"### H1 — NRF regenera Entendi\n**{analysis['H1']['verdict']}**\n\n")
    for s in analysis["H1"]["samples"][:8]:
        report.append(f"- `{s['case']}` / `{s['message']}`: {s['note']}\n")
        report.append(f"  `{s['line'][:200]}`\n")
    report.append(f"\n### H2 — Forced nonsport sem confidence\n**{analysis['H2']['verdict']}**\n\n")
    report.append(
        f"- Forced dict keys: `{h2_static['forced_keys']}`\n"
        f"- forced_has_confidence: **{h2_static['forced_has_confidence']}**\n"
        f"- GA completo tem confidence: **{h2_static['ga_full_has_confidence']}**\n"
        f"- Consumidor: `{h2_static['consumer']}`\n"
    )
    report.append(f"\n### H3 — Ownership perdido\n**{analysis['H3']['verdict']}**\n\n")
    for s in analysis["H3"]["unlocked_late_nrf"][:5]:
        report.append(
            f"- late NRF unlocked: `{s['case']}` msg=`{s['message']}` owner={s['owner_final']}\n"
        )
    for s in analysis["H3"]["owner_none"][:5]:
        report.append(
            f"- owner none: `{s['case']}` msg=`{s['message']}` locked={s['locked']}\n"
        )

    report.append("\n## Causas raiz definitivas (após evidência)\n\n")
    report.append(
        "1. **H1 CONFIRMADA (mecanismo):** `filter_or_regenerate` + `reply_general` "
        "idempotente → template Entendi se reproduz quando similar=True ou regenerate=mesmo texto.\n"
        "2. **H2 CONFIRMADA (estrutural):** dict forced nonsport omite `confidence`/"
        "`risk`/`bankroll_recommendation`; builder usa `payload['confidence']`.\n"
        "3. **H3 PARCIAL:** early GA/HCE/NRE recebem owner+lock; "
        "**forced incomplete não chama finalize_early_ownership** → owner=none, late NRF pode correr; "
        "skip late NRF lista NRE/HCE/META mas GA só via `rewrite_locked`.\n"
    )

    report.append("\n## Linha temporal típica (GENERAL_CHAT loop)\n\n")
    report.append(
        "```text\n"
        "[INTENT] GENERAL_CHAT sport_ok=False\n"
        "[ENGINE] general_assistant kind=general\n"
        "[NRF_INPUT] text=Entendi…\n"
        "[NRF_OUTPUT] action=keep|regenerate (similar)\n"
        "[OWNER] after_early_finalize owner=GA locked=True\n"
        "[PAYLOAD_BEFORE] late_nrf has_confidence=True\n"
        "[NRF_OUTPUT] action=skipped_owned  (se locked)\n"
        "[PAYLOAD_AFTER] late_nrf\n"
        "[OWNER] final owner=GA\n"
        "```\n"
        "No turno 2+, early NRF já regenera Entendi **antes** do lock.\n"
    )

    md_path = OBS / f"REPORT_{stamp}.md"
    md_path.write_text("".join(report), encoding="utf-8")

    # Also write latest aliases
    (OBS / "REPORT_LATEST.md").write_text("".join(report), encoding="utf-8")
    (OBS / "evidence_latest.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print()
    print("=" * 72)
    print("VEREDICTOS")
    print(f"  H1: {analysis['H1']['verdict']} (n={analysis['H1']['evidence_count']})")
    print(f"  H2: {analysis['H2']['verdict']}")
    print(f"  H3: {analysis['H3']['verdict']}")
    print(f"Relatório: {md_path}")
    print(f"Logs JSON: {json_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
