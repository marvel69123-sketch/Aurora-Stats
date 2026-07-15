"""
Inference Layer V2 — soft failures become confidence reductions.

Hard aborts (404 / null / empty fallback) in the analyze path are replaced by
an InferenceContext that records what was found, missing, or inferred, then
continues the pipeline with a lower confidence score.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


# Canonical signal keys used across analyze → engines → copilot
SIGNAL_KEYS: tuple[str, ...] = (
    "fixture",
    "teams",
    "score",
    "statistics",
    "xg",
    "events",
    "lineups",
    "standings",
    "referee",
)

# How much each missing signal subtracts from the 0–10 confidence scale
_PENALTY_WEIGHTS: dict[str, float] = {
    "fixture": 3.0,
    "teams": 2.0,
    "statistics": 1.0,
    "xg": 1.2,
    "standings": 1.0,
    "lineups": 0.8,
    "events": 0.5,
    "score": 0.4,
    "referee": 0.4,
}

_INFER_RECOVERY = 0.25  # fraction of weight recovered when a signal is inferred
_MAX_PENALTY = 8.0


@dataclass
class InferenceContext:
    """Tracks data availability and confidence penalties for one request."""

    available_signals: list[str] = field(default_factory=list)
    missing_signals: list[str] = field(default_factory=list)
    inferred_signals: list[str] = field(default_factory=list)
    confidence_penalties: list[dict[str, Any]] = field(default_factory=list)
    data_completeness: float = 0.0
    notes: list[str] = field(default_factory=list)
    soft_mode: bool = True

    # ── mutators ───────────────────────────────────────────────────────────

    def mark_available(self, signal: str, note: str | None = None) -> None:
        if signal not in self.available_signals:
            self.available_signals.append(signal)
        if signal in self.missing_signals:
            self.missing_signals.remove(signal)
        if note:
            self.notes.append(note)

    def mark_missing(self, signal: str, reason: str | None = None) -> None:
        if signal not in self.missing_signals and signal not in self.available_signals:
            self.missing_signals.append(signal)
        detail = reason or f"Sinal ausente: {signal}"
        self.confidence_penalties.append(
            {
                "signal": signal,
                "reason": detail,
                "penalty": round(_PENALTY_WEIGHTS.get(signal, 0.5), 2),
            }
        )
        self.notes.append(detail)

    def mark_inferred(self, signal: str, how: str) -> None:
        if signal not in self.inferred_signals:
            self.inferred_signals.append(signal)
        # Inferred counts as "available enough to continue", not fully missing
        if signal in self.missing_signals:
            self.missing_signals.remove(signal)
        if signal not in self.available_signals:
            self.available_signals.append(signal)
        self.notes.append(f"Inferido ({signal}): {how}")
        self.confidence_penalties.append(
            {
                "signal": signal,
                "reason": f"Inferência: {how}",
                "penalty": round(_PENALTY_WEIGHTS.get(signal, 0.5) * (1.0 - _INFER_RECOVERY), 2),
            }
        )

    def register_failure(self, stage: str, detail: str, *, signal: str | None = None) -> None:
        """Audit a would-be abort: log as penalty and keep going."""
        sig = signal or stage
        self.confidence_penalties.append(
            {
                "signal": sig,
                "reason": f"[{stage}] {detail}",
                "penalty": round(_PENALTY_WEIGHTS.get(sig, 0.75), 2),
            }
        )
        self.notes.append(f"Falha registrada ({stage}): {detail}")
        if sig not in self.missing_signals and sig not in self.available_signals:
            self.missing_signals.append(sig)

    def finalize(self) -> "InferenceContext":
        self.data_completeness = calculate_data_completeness(
            self.available_signals,
            self.missing_signals,
        )
        return self

    # ── exports ────────────────────────────────────────────────────────────

    def total_penalty(self) -> float:
        return calculate_confidence_penalty(
            self.missing_signals,
            self.inferred_signals,
            extra_penalties=self.confidence_penalties,
        )

    def apply_to_score(self, score: float) -> float:
        """Reduce a 0–10 confidence score; never returns negative."""
        adjusted = float(score) - self.total_penalty()
        return round(max(0.0, min(10.0, adjusted)), 2)

    def explainability(self) -> dict[str, Any]:
        """Structured explainability block for brain / API consumers."""
        self.finalize()
        return {
            "dados_encontrados": list(self.available_signals),
            "dados_faltantes": list(self.missing_signals),
            "inferencias_realizadas": list(self.inferred_signals),
            "data_completeness": self.data_completeness,
            "confidence_penalty": self.total_penalty(),
            "penalties": list(self.confidence_penalties),
            "notes": list(self.notes),
        }

    def knowledge_notes_pt(self) -> list[str]:
        """Human-readable PT bullets for knowledge_notes (no frontend change)."""
        self.finalize()
        notes: list[str] = []
        if self.available_signals:
            notes.append(
                "Dados encontrados: " + ", ".join(self.available_signals)
            )
        if self.missing_signals:
            notes.append(
                "Dados faltantes: " + ", ".join(self.missing_signals)
            )
        if self.inferred_signals:
            notes.append(
                "Inferências realizadas: " + ", ".join(self.inferred_signals)
            )
        notes.append(
            f"Completude dos dados: {self.data_completeness * 100:.0f}% "
            f"(penalidade de confiança −{self.total_penalty():.1f})"
        )
        return notes

    def to_dict(self) -> dict[str, Any]:
        self.finalize()
        return {
            "available_signals": list(self.available_signals),
            "missing_signals": list(self.missing_signals),
            "inferred_signals": list(self.inferred_signals),
            "confidence_penalties": list(self.confidence_penalties),
            "data_completeness": self.data_completeness,
            "explainability": self.explainability(),
        }


def calculate_data_completeness(
    available_signals: Iterable[str],
    missing_signals: Iterable[str],
) -> float:
    """
    Fraction of known signal slots that are available (0.0–1.0).

    Uses the union of available + missing; empty → 0.0.
    """
    avail = {s for s in available_signals if s}
    miss = {s for s in missing_signals if s}
    total = avail | miss
    if not total:
        return 0.0
    return round(len(avail) / len(total), 3)


def calculate_confidence_penalty(
    missing_signals: Iterable[str],
    inferred_signals: Iterable[str] | None = None,
    extra_penalties: Iterable[dict[str, Any]] | None = None,
) -> float:
    """
    Penalty to subtract from a 0–10 confidence score.

    Missing signals apply full weight; inferred signals apply reduced weight.
    Caps at _MAX_PENALTY so the pipeline can still produce a non-zero score
    when some signals remain.
    """
    penalty = 0.0
    inferred = set(inferred_signals or [])
    seen: set[str] = set()

    for sig in missing_signals:
        if not sig or sig in seen:
            continue
        seen.add(sig)
        penalty += _PENALTY_WEIGHTS.get(sig, 0.5)

    for sig in inferred:
        if not sig or sig in seen:
            # already counted as missing — replace with reduced weight
            if sig in seen:
                full = _PENALTY_WEIGHTS.get(sig, 0.5)
                penalty -= full
                penalty += full * (1.0 - _INFER_RECOVERY)
            continue
        seen.add(sig)
        penalty += _PENALTY_WEIGHTS.get(sig, 0.5) * (1.0 - _INFER_RECOVERY)

    if extra_penalties:
        # Avoid double-counting signals already in missing/inferred lists
        for item in extra_penalties:
            sig = str(item.get("signal") or "")
            if sig in seen:
                continue
            try:
                penalty += float(item.get("penalty") or 0.0)
            except (TypeError, ValueError):
                penalty += 0.5
            if sig:
                seen.add(sig)

    return round(min(_MAX_PENALTY, max(0.0, penalty)), 2)


def scan_analyze_data(data: dict[str, Any]) -> InferenceContext:
    """Build InferenceContext by inspecting an analyze_fixture() payload."""
    ctx = InferenceContext(soft_mode=True)

    fixture = data.get("fixture") or {}
    teams = data.get("teams") or {}
    score = data.get("score") or {}
    stats = data.get("statistics") or {}
    events = data.get("events") or []
    lineups = data.get("lineups") or {}
    standings = data.get("standings") or {}

    fid = fixture.get("id")
    if fid and int(fid) != 0:
        ctx.mark_available("fixture")
    else:
        ctx.mark_missing("fixture", "Fixture oficial não resolvida na API")

    home = (teams.get("home") or {}).get("name")
    away = (teams.get("away") or {}).get("name")
    if home and away:
        ctx.mark_available("teams")
    else:
        ctx.mark_missing("teams", "Nomes dos times incompletos")

    cur = score.get("current") or {}
    if cur.get("home") is not None or cur.get("away") is not None:
        ctx.mark_available("score")
    else:
        ctx.mark_missing("score", "Placar indisponível")

    home_stats = stats.get("home") or {}
    away_stats = stats.get("away") or {}
    has_any_stat = any(
        home_stats.get(k) is not None or away_stats.get(k) is not None
        for k in ("shots_total", "possession", "corners", "fouls", "passes_total")
    )
    if has_any_stat:
        ctx.mark_available("statistics")
    else:
        ctx.mark_missing("statistics", "Estatísticas da partida ausentes")

    has_xg = home_stats.get("xg") is not None or away_stats.get("xg") is not None
    if has_xg:
        ctx.mark_available("xg")
    else:
        ctx.mark_missing("xg", "xG indisponível — engines usam GPG/standings")

    if events:
        ctx.mark_available("events")
    else:
        ctx.mark_missing("events", "Eventos da partida ausentes")

    if lineups.get("home") or lineups.get("away"):
        ctx.mark_available("lineups")
    else:
        ctx.mark_missing("lineups", "Escalações não confirmadas")

    if standings.get("home") or standings.get("away"):
        ctx.mark_available("standings")
    else:
        ctx.mark_missing("standings", "Classificação não disponível")

    if fixture.get("referee"):
        ctx.mark_available("referee")
    else:
        ctx.mark_missing("referee", "Árbitro não informado")

    # Carry forward any pre-attached inference markers from soft analyze
    prior = data.get("_inference") or {}
    for sig in prior.get("inferred_signals") or []:
        if sig not in ctx.inferred_signals:
            ctx.inferred_signals.append(sig)
    for note in prior.get("notes") or []:
        if note not in ctx.notes:
            ctx.notes.append(note)
    for pen in prior.get("confidence_penalties") or []:
        ctx.confidence_penalties.append(pen)

    return ctx.finalize()


def build_partial_analyze_data(
    home: str,
    away: str,
    *,
    reason: str,
    ctx: InferenceContext | None = None,
) -> dict[str, Any]:
    """
    Synthetic analyze payload when fixture resolution fails.

    Engines already degrade on missing standings/xg/stats — this keeps the
    pipeline alive instead of HTTP 404.
    """
    ictx = ctx or InferenceContext(soft_mode=True)
    ictx.register_failure("fixture_resolve", reason, signal="fixture")
    ictx.mark_inferred(
        "teams",
        f"Nomes fornecidos pelo usuário: {home} x {away}",
    )
    ictx.mark_inferred(
        "fixture",
        "Contexto sintético pré-jogo — fixture oficial não localizada",
    )
    ictx.mark_missing("statistics", "Sem fixture real — estatísticas indisponíveis")
    ictx.mark_missing("xg", "Sem fixture real — xG indisponível")
    ictx.mark_missing("events", "Sem fixture real — eventos indisponíveis")
    ictx.mark_missing("lineups", "Sem fixture real — escalações indisponíveis")
    ictx.mark_missing("standings", "Sem fixture real — classificação indisponível")
    ictx.mark_missing("referee", "Sem fixture real — árbitro indisponível")
    ictx.mark_missing("score", "Sem fixture real — placar indisponível")
    ictx.finalize()

    empty_stats = {
        "possession": None,
        "shots_total": None,
        "shots_on_target": None,
        "shots_off_target": None,
        "blocked_shots": None,
        "corners": None,
        "fouls": None,
        "offsides": None,
        "saves": None,
        "passes_total": None,
        "passes_accurate": None,
        "pass_accuracy": None,
        "xg": None,
        "yellow_cards": 0,
        "red_cards": 0,
    }

    payload = {
        "fixture": {
            "id": 0,
            "date": None,
            "timestamp": 0,
            "referee": None,
            "venue": {"name": None, "city": None},
            "status": {
                "short": "NS",
                "long": "Not Started",
                "minute": None,
                "extra": None,
            },
        },
        "league": {
            "id": 0,
            "name": "Unknown",
            "country": None,
            "logo": None,
            "flag": None,
            "season": 0,
            "round": None,
        },
        "teams": {
            "home": {
                "id": 0,
                "name": home or "Home",
                "logo": None,
                "winner": None,
            },
            "away": {
                "id": 0,
                "name": away or "Away",
                "logo": None,
                "winner": None,
            },
        },
        "score": {
            "current": {"home": None, "away": None},
            "halftime": {"home": None, "away": None},
            "fulltime": {"home": None, "away": None},
            "extratime": {"home": None, "away": None},
            "penalty": {"home": None, "away": None},
        },
        "statistics": {"home": dict(empty_stats), "away": dict(empty_stats)},
        "events": [],
        "lineups": {"home": None, "away": None},
        "standings": {"home": None, "away": None},
        "_inference": ictx.to_dict(),
        "_partial": True,
        "_partial_reason": reason,
    }
    try:
        from src.core.team_branding import enrich_analyze_teams

        payload = enrich_analyze_teams(payload, home=home, away=away)
    except Exception:
        pass
    return payload
