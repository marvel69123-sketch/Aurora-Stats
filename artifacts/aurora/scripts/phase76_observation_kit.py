"""
FASE 7.6 — Governança de validação em produção.

Status: APROVADO E CONGELADO
Modo: OBSERVAR > IMPLEMENTAR (disciplina operacional)

Até o 1º relatório consolidado (n >= 5):
  PROIBIDO — engines, features, expansões arquiteturais, alterações estruturais
  PERMITIDO — transcripts, classificação, métricas, ajustes cirúrgicos com evidência

Decisões só com evidência agregada (mín. 5, ideal 5–10 transcripts reais).
Pergunta oficial: "O que os usuários estão realmente vivenciando?"

Uso:
  uv run python scripts/phase76_observation_kit.py new
  uv run python scripts/phase76_observation_kit.py report

Sessions: artifacts/aurora/observations/phase76/
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OBS_DIR = ROOT / "observations" / "phase76"

MIN_SAMPLES_FOR_DECISION = 5
RECOMMENDED_SAMPLES = 10

# Official KPI targets (Phase 7.6 governance)
KPI = {
    "ownership": 0.90,  # >90%
    "continuity": 0.85,  # >85%
    "user_corrections": 0.15,  # <15%
    "repetition": 0.20,  # <20%
    "humanity": 0.70,  # >70%
    "perceived_intelligence": 0.70,  # >70% (yes + half of partial)
    "friction_avg": 2.5,  # média < 2.5
    "recovery": 0.70,  # quando errou, recuperou? >70% dos casos com erro
}

CHECKLIST = [
    ("ownership_ok", "Ownership correto"),
    ("continuity_ok", "Continuidade correta"),
    ("social_ok", "Social correto"),
    ("excessive_repetition", "Repetição excessiva"),
    ("user_corrected_aurora", "Usuário corrigiu Aurora (nao entendeu / nao foi isso)"),
    ("felt_human", 'Parece uma conversa melhor? (humanidade)'),
]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def _ask_yn(label: str) -> bool:
    while True:
        raw = input(f"  {label}? [s/n]: ").strip().lower()
        if raw in {"s", "sim", "y", "yes"}:
            return True
        if raw in {"n", "nao", "não", "no"}:
            return False
        print("    digite s ou n")


def _ask_int(label: str, lo: int, hi: int) -> int:
    while True:
        raw = input(f"  {label} [{lo}-{hi}]: ").strip()
        try:
            v = int(raw)
            if lo <= v <= hi:
                return v
        except Exception:
            pass
        print(f"    digite um inteiro entre {lo} e {hi}")


def _ask_sev() -> str:
    while True:
        raw = input("  Severidade do pior incidente [P0/P1/P2/none]: ").strip().upper()
        if raw in {"P0", "P1", "P2", "NONE", ""}:
            return "none" if raw in {"", "NONE"} else raw
        print("    use P0, P1, P2 ou none")


def _ask_tri(label: str) -> str:
    while True:
        raw = input(f"  {label} [s/n/parcial]: ").strip().lower()
        if raw in {"s", "sim", "y", "yes"}:
            return "yes"
        if raw in {"n", "nao", "não", "no"}:
            return "no"
        if raw in {"p", "parcial", "partial"}:
            return "partial"
        print("    digite s, n ou parcial")


def new_session() -> Path:
    OBS_DIR.mkdir(parents=True, exist_ok=True)
    print()
    print("=== NOVA OBSERVACAO HUMANA (Fase 7.6 — Governanca) ===")
    print("Diretriz: OBSERVAR > IMPLEMENTAR")
    print("Cole o transcript (linha vazia + Enter para terminar):")
    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == "" and lines and lines[-1].strip() == "":
            break
        lines.append(line)
    while lines and not lines[-1].strip():
        lines.pop()

    source = input("  Fonte [production/internal/friend]: ").strip() or "internal"

    print()
    print("--- Checklist oficial ---")
    flags: dict[str, bool] = {}
    for key, label in CHECKLIST:
        flags[key] = _ask_yn(label)

    print()
    print("--- Metricas aprovadas ---")
    smarter = _ask_tri('KPI6: "A Aurora parece mais inteligente?"')
    friction = _ask_int("Friction Score (1=natural, 5=lutando contra a IA)", 1, 5)
    rephrases = _ask_int("User Rephrases (quantas vezes reformulou a intencao)", 0, 20)

    # Recovery Rate — só relevante se houve erro/correcao
    had_error = flags.get("user_corrected_aurora", False) or rephrases > 0
    recovery: str | bool = "n/a"
    if had_error:
        recovery = _ask_yn(
            "Recovery: apos o erro/correcao, a Aurora recuperou o contexto rapidamente"
        )

    notes = input("  Notas livres (opcional): ").strip()
    severity = _ask_sev()
    incident = ""
    if severity != "none":
        incident = input("  Descreva o incidente: ").strip()

    session: dict[str, Any] = {
        "phase": "7.6",
        "governance": "production_validation",
        "created_at": _now(),
        "source": source,
        "transcript": "\n".join(lines),
        "checklist": flags,
        "metrics": {
            "ownership_ok": flags.get("ownership_ok", False),
            "continuity_ok": flags.get("continuity_ok", False),
            "user_corrected": flags.get("user_corrected_aurora", False),
            "excessive_repetition": flags.get("excessive_repetition", False),
            "felt_human": flags.get("felt_human", False),
            "felt_smarter": smarter,
            "friction_score": friction,
            "user_rephrases": rephrases,
            "had_error_or_rephrase": had_error,
            "recovered_after_error": recovery,
        },
        "worst_severity": severity,
        "incident_notes": incident,
        "notes": notes,
    }

    path = OBS_DIR / f"session_{_now()}.json"
    path.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")
    print()
    print(f"Salvo: {path}")
    return path


def load_sessions() -> list[dict[str, Any]]:
    if not OBS_DIR.exists():
        return []
    out: list[dict[str, Any]] = []
    for p in sorted(OBS_DIR.glob("session_*.json")):
        if "TEMPLATE" in p.name:
            continue
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception as exc:
            print(f"aviso: falha ao ler {p.name}: {exc}")
    return out


def _rate(ok: int, n: int) -> float:
    return (ok / n) if n else 0.0


def _smarter_score(sessions: list[dict[str, Any]]) -> float:
    """yes=1, partial=0.5, no=0 — KPI perceived intelligence."""
    if not sessions:
        return 0.0
    total = 0.0
    for s in sessions:
        v = (s.get("metrics") or {}).get("felt_smarter")
        if v == "yes":
            total += 1.0
        elif v == "partial":
            total += 0.5
    return total / len(sessions)


def decide_scenario(
    *,
    n: int,
    ownership: float,
    continuity: float,
    corrections: float,
    repetition: float,
    humanity: float,
    intelligence: float,
    p0: int,
    p1: int,
    avg_friction: float,
    avg_rephrases: float,
    recovery: float | None,
) -> tuple[str, str]:
    """
    Returns (scenario, reason). No structural decision if n < MIN_SAMPLES.
    """
    if n < MIN_SAMPLES_FOR_DECISION:
        return (
            "HOLD",
            f"Amostra insuficiente ({n}/{MIN_SAMPLES_FOR_DECISION} min, "
            f"recomendado {RECOMMENDED_SAMPLES}). Proibido concluir sucesso, "
            "abrir features ou reabrir arquitetura.",
        )

    # Scenario C — structural
    if p0 > 0 or ownership < 0.70 or corrections > 0.35 or avg_friction >= 4.0:
        return (
            "C",
            "Ownership instavel / P0 / alta correcao ou friccao — reabrir auditoria se confirmar.",
        )

    recovery_ok = recovery is None or recovery >= KPI["recovery"]

    # Scenario A — close Phase 7
    if (
        p0 == 0
        and ownership >= KPI["ownership"]
        and continuity >= KPI["continuity"]
        and corrections <= KPI["user_corrections"]
        and repetition <= KPI["repetition"]
        and humanity >= KPI["humanity"]
        and intelligence >= KPI["perceived_intelligence"]
        and avg_friction < KPI["friction_avg"]
        and avg_rephrases <= 1.5
        and recovery_ok
    ):
        return (
            "A",
            "KPIs oficiais atingidos — candidato a ENCERRAR Fase 7 (revisao humana final).",
        )

    # Scenario B — surgical
    return (
        "B",
        "P1 localizados / KPIs parciais — ajustes CIRURGICOS apenas (P2 nao vira engine).",
    )


def report() -> None:
    sessions = load_sessions()
    print()
    print("=== RELATORIO FASE 7.6 — GOVERNANCA ===")
    print("Diretriz: OBSERVAR > IMPLEMENTAR | decisoes por evidencia agregada")
    print()
    if not sessions:
        print(f"Nenhuma session em {OBS_DIR}")
        print("Rode: uv run python scripts/phase76_observation_kit.py new")
        return

    n = len(sessions)
    own = sum(1 for s in sessions if (s.get("checklist") or {}).get("ownership_ok"))
    cont = sum(1 for s in sessions if (s.get("checklist") or {}).get("continuity_ok"))
    corr = sum(1 for s in sessions if (s.get("checklist") or {}).get("user_corrected_aurora"))
    rep = sum(1 for s in sessions if (s.get("checklist") or {}).get("excessive_repetition"))
    human = sum(1 for s in sessions if (s.get("checklist") or {}).get("felt_human"))
    social = sum(1 for s in sessions if (s.get("checklist") or {}).get("social_ok"))

    ownership_r = _rate(own, n)
    continuity_r = _rate(cont, n)
    corrections_r = _rate(corr, n)
    repetition_r = _rate(rep, n)
    humanity_r = _rate(human, n)
    intelligence_r = _smarter_score(sessions)

    frictions = [
        int((s.get("metrics") or {}).get("friction_score") or 0)
        for s in sessions
        if (s.get("metrics") or {}).get("friction_score")
    ]
    rephrases = [
        int((s.get("metrics") or {}).get("user_rephrases") or 0) for s in sessions
    ]
    avg_friction = sum(frictions) / len(frictions) if frictions else 0.0
    avg_rephrases = sum(rephrases) / len(rephrases) if rephrases else 0.0

    recovery_cases = [
        s
        for s in sessions
        if (s.get("metrics") or {}).get("had_error_or_rephrase")
        or (s.get("metrics") or {}).get("recovered_after_error") not in (None, "n/a")
    ]
    recovery_ok_n = sum(
        1
        for s in recovery_cases
        if (s.get("metrics") or {}).get("recovered_after_error") is True
    )
    recovery_r: float | None
    if recovery_cases:
        recovery_r = recovery_ok_n / len(recovery_cases)
    else:
        recovery_r = None

    p0 = sum(1 for s in sessions if s.get("worst_severity") == "P0")
    p1 = sum(1 for s in sessions if s.get("worst_severity") == "P1")
    p2 = sum(1 for s in sessions if s.get("worst_severity") == "P2")

    def mark(ok: bool) -> str:
        return "OK" if ok else "ABAIXO"

    print(f"Sessions reais: {n}  (min decisao={MIN_SAMPLES_FOR_DECISION}, ideal={RECOMMENDED_SAMPLES})")
    if n < MIN_SAMPLES_FOR_DECISION:
        print("  >>> HOLD: amostra insuficiente — so observar <<<")
    print()
    print("KPIs oficiais:")
    print(
        f"  1 Ownership              {ownership_r:.0%}  meta >{KPI['ownership']:.0%}  [{mark(ownership_r > KPI['ownership'])}]"
    )
    print(
        f"  2 Continuidade           {continuity_r:.0%}  meta >{KPI['continuity']:.0%}  [{mark(continuity_r > KPI['continuity'])}]"
    )
    print(
        f"  3 Correcoes do usuario   {corrections_r:.0%}  meta <{KPI['user_corrections']:.0%}  [{mark(corrections_r < KPI['user_corrections'])}]"
    )
    print(
        f"  4 Repeticao percebida    {repetition_r:.0%}  meta <{KPI['repetition']:.0%}  [{mark(repetition_r < KPI['repetition'])}]"
    )
    print(
        f"  5 Humanidade percebida   {humanity_r:.0%}  meta >{KPI['humanity']:.0%}  [{mark(humanity_r > KPI['humanity'])}]"
    )
    print(
        f"  6 Inteligencia percebida {intelligence_r:.0%}  meta >{KPI['perceived_intelligence']:.0%}  [{mark(intelligence_r > KPI['perceived_intelligence'])}]"
    )
    print()
    print("Metricas adicionais:")
    print(
        f"  Friction Score medio:  {avg_friction:.2f}  meta <{KPI['friction_avg']}  "
        f"[{mark(avg_friction < KPI['friction_avg'] if frictions else False)}]"
    )
    print(f"  User Rephrases medio:  {avg_rephrases:.2f}")
    if recovery_r is None:
        print("  Recovery Rate:          n/a  (nenhum erro/rephrase na amostra)")
    else:
        print(
            f"  Recovery Rate:          {recovery_r:.0%}  "
            f"({recovery_ok_n}/{len(recovery_cases)} com recuperacao)  "
            f"meta >{KPI['recovery']:.0%}  [{mark(recovery_r > KPI['recovery'])}]"
        )
    print(f"  Social correto:        {_rate(social, n):.0%}")
    print()
    print(f"Incidentes: P0={p0}  P1={p1}  P2={p2}")
    print()

    scenario, reason = decide_scenario(
        n=n,
        ownership=ownership_r,
        continuity=continuity_r,
        corrections=corrections_r,
        repetition=repetition_r,
        humanity=humanity_r,
        intelligence=intelligence_r,
        p0=p0,
        p1=p1,
        avg_friction=avg_friction,
        avg_rephrases=avg_rephrases,
        recovery=recovery_r,
    )
    print("Matriz de decisao (oficial):")
    print(f"  Cenario: {scenario}")
    print(f"  Motivo:  {reason}")
    if scenario == "A":
        print("  Acao:    Encerrar Fase 7 (apos revisao humana final).")
    elif scenario == "B":
        print("  Acao:    Ajuste cirurgico pontual — sem engine nova.")
    elif scenario == "C":
        print("  Acao:    Reabrir auditoria de ownership/ordem.")
    else:
        print("  Acao:    Continuar coletando transcripts reais.")
    print()
    print('Pergunta oficial: "O que os usuarios estao realmente vivenciando?"')
    print(f"Fonte: {OBS_DIR}")


def main() -> None:
    cmd = (sys.argv[1] if len(sys.argv) > 1 else "help").lower()
    if cmd == "new":
        new_session()
        report()
    elif cmd == "report":
        report()
    else:
        print("Fase 7.6 — Governanca de validacao")
        print()
        print("  new     registrar transcript + KPIs humanos")
        print("  report  agregar evidencia (decisao so com 5–10 samples)")
        print()
        print("Regra de ouro: pouca implementacao, muita observacao.")


if __name__ == "__main__":
    main()
