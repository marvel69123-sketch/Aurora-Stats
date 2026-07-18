"""
Phase 8.4-A.11 — Advanced Football Continuity.

Short advanced football terms (xG, pressão, Kelly, edge, …) after an active
fixture must reuse context BEFORE GeneralAssistant / fallback.

Fail-open. Does not modify Market Engine, Opinion Renderer, Calendar,
Partial Analysis, or Ownership modules.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any

logger = logging.getLogger(__name__)

RESOLVE_KEY = "advanced_football_resolve"

# Longer phrases first. Canonical term → audit `advanced_term`.
_TERM_SPECS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bexpected\s+goals\b", re.I), "xg"),
    (re.compile(r"\bcriterio\s+de\s+kelly\b", re.I), "kelly"),
    (re.compile(r"\bodd\s+justa\b", re.I), "odd_justa"),
    (re.compile(r"\bvalor\s+esperado\b", re.I), "value"),
    (re.compile(r"\bqual\s+(?:o\s+)?edge\b", re.I), "edge"),
    (re.compile(r"\bambas\s+marcam\b", re.I), "ambas_marcam"),
    (re.compile(r"\b(?:over|under)\s+\d+(?:[.,]\d+)?\b", re.I), "market_line"),
    (re.compile(r"\bx\s*\.?\s*g\s*\.?\b", re.I), "xg"),
    (re.compile(r"\bxg\b", re.I), "xg"),
    (re.compile(r"\bpressao\b", re.I), "pressao"),
    (re.compile(r"\bmomentum\b", re.I), "momentum"),
    (re.compile(r"\bkelly\b", re.I), "kelly"),
    (re.compile(r"\bprobabilidades?\b", re.I), "probabilidade"),
    (re.compile(r"\bvalue\b", re.I), "value"),
    (re.compile(r"\bedge\b", re.I), "edge"),
    (re.compile(r"\bstake\b", re.I), "stake"),
    (re.compile(r"\bconfianca\b", re.I), "confianca"),
]


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


def detect_advanced_term(message: str | None) -> str | None:
    """Return canonical advanced term or None."""
    folded = _fold(message or "")
    if not folded or len(folded.split()) > 8:
        return None
    # Avoid stealing full fixture asks
    if re.search(r"\b\w+\s+(?:x|vs)\s+\w+\b", folded):
        return None
    for pat, term in _TERM_SPECS:
        if pat.search(folded):
            return term
    return None


def _gather_fixture(ctx: dict[str, Any]) -> dict[str, Any]:
    """Reuse pronoun / continuity / last_match sources without inventing data."""
    try:
        from src.conversation.pronoun_continuity import _gather_context

        return _gather_context(ctx)
    except Exception:
        pass
    fixture = None
    for key in ("last_match", "last_fixture"):
        val = ctx.get(key)
        if isinstance(val, str) and val.strip():
            fixture = val.strip()
            break
    return {
        "fixture": fixture,
        "home": None,
        "away": None,
        "team": None,
        "entity_invalid": False,
        "fixture_quality": None,
    }


def _term_prose(term: str, label: str) -> str:
    """Conceptual continuity text — never invents numeric xG/odds/stake."""
    base = f"No contexto de **{label}**"
    if term == "xg":
        return (
            f"{base}, o recorte de **xG / expected goals** é o ângulo certo.\n\n"
            f"Se a leitura anterior já trouxe sinais de volume ofensivo, "
            f"uso isso como base — sem inventar um xG numérico ausente.\n\n"
            f"Quer que eu amarre isso a gols, BTTS ou um mercado específico?"
        )
    if term == "pressao":
        return (
            f"{base}, foco em **pressão / campo**.\n\n"
            f"Sigo a linha da análise anterior sobre quem empurra o jogo "
            f"— sem fabricar posse ou PPDA se não estiverem confirmados.\n\n"
            f"Prefere pressão ofensiva, defensiva ou o momento do confronto?"
        )
    if term == "momentum":
        return (
            f"{base}, falando de **momentum**.\n\n"
            f"Uso só o que já ficou na conversa (tendência / fase do jogo) "
            f"e não invento virada de placar.\n\n"
            f"Quer o recorte ofensivo ou o de controle de jogo?"
        )
    if term == "kelly":
        return (
            f"{base}, sobre **critério de Kelly**.\n\n"
            f"Kelly só faz sentido com edge e probabilidade estimada. "
            f"Se ainda não fechei esses números neste confronto, "
            f"não invento stake — posso explicar o critério e o que faltaria.\n\n"
            f"Quer a lógica do Kelly ou amarrar a um mercado da leitura anterior?"
        )
    if term == "odd_justa":
        return (
            f"{base}, recorte de **odd justa**.\n\n"
            f"Sem probabilidade fechada nesta conversa, não publico odd inventada. "
            f"Posso usar os mercados já rankeados (se houver) como referência.\n\n"
            f"Qual mercado você quer aferir?"
        )
    if term == "probabilidade":
        return (
            f"{base}, falando de **probabilidade**.\n\n"
            f"Reutilizo só probabilidades já presentes na análise anterior — "
            f"sem inventar %. Posso listar os mercados que já tinham número.\n\n"
            f"Quer gols, escanteios ou o top da leitura?"
        )
    if term in {"value", "edge"}:
        return (
            f"{base}, recorte de **{term}** (valor / edge).\n\n"
            f"Edge só aparece quando há probabilidade vs preço. "
            f"Se a leitura anterior já apontou VE/edge, sigo daí; "
            f"senão explico o critério sem inventar odd.\n\n"
            f"Quer o melhor mercado já listado ou um mercado específico?"
        )
    if term == "stake":
        return (
            f"{base}, sobre **stake**.\n\n"
            f"Sem edge fechado não recomendo % inventado. "
            f"Posso seguir a banca/Kelly só com o que já foi validado na análise.\n\n"
            f"Quer regra de stake ou amarrar a um mercado?"
        )
    if term == "confianca":
        return (
            f"{base}, sobre **confiança** da leitura.\n\n"
            f"Uso o nível de completeza/confiança já carimbado na análise — "
            f"sem inflar score. Em PARTIAL deixo claro o que falta.\n\n"
            f"Quer o que sustenta a confiança ou o que a limita?"
        )
    if term in {"ambas_marcam", "market_line"}:
        return (
            f"{base}, seguindo no ângulo de **mercado** que você pediu.\n\n"
            f"Se a análise anterior já rankeou mercados, priorizo esses sinais; "
            f"caso contrário peço o mercado exato — sem inventar odd.\n\n"
            f"Quer que eu foque nesse mercado ou compare com o top da leitura?"
        )
    return (
        f"{base}, mantenho a continuidade no termo **{term}**.\n\n"
        f"Diga o recorte (mercado, time ou métrica) que eu afunilo "
        f"sem inventar dados."
    )


def _stamp(
    payload: dict[str, Any],
    *,
    term: str,
    fixture: str | None,
    reused: bool,
) -> dict[str, Any]:
    out = dict(payload)
    ents = dict(out.get("entities") or {})
    ents["advanced_term_detected"] = True
    ents["advanced_term"] = term
    ents["advanced_fixture_reused"] = bool(reused and fixture)
    ents["advanced_before_fallback"] = True
    ents["advanced_football_continuity"] = True
    if reused and fixture:
        ents["followup_context_found"] = True
        ents["followup_resolved_fixture"] = fixture
        ents["followup_before_fallback"] = True
        ents["continuity_followup"] = True
    out["entities"] = ents
    return out


def try_advanced_football_continuity(
    message: str,
    ctx: dict[str, Any] | None,
    *,
    brain: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Claim advanced-term follow-ups BEFORE GA when a fixture is active."""
    try:
        if not isinstance(ctx, dict):
            return None
        raw = str(ctx.get("raw_user_message") or message or "")
        term = detect_advanced_term(raw) or detect_advanced_term(message)
        if not term:
            return None

        try:
            from src.conversation.conversation_repair import is_repair_signal

            if is_repair_signal(raw):
                return None
        except Exception:
            pass

        info = _gather_fixture(ctx)
        fixture = info.get("fixture")
        if not fixture and not info.get("home"):
            logger.warning(
                "[AUDIT] AdvancedFootball: term=%s without active fixture — skip",
                term,
            )
            return None

        if not fixture and info.get("home") and info.get("away"):
            fixture = f"{info['home']} x {info['away']}"

        # INVALID prior → refuse invention
        if info.get("entity_invalid") or info.get("fixture_quality") == "INVALID":
            text = (
                f"Não consigo aplicar **{term}** sobre **{fixture}** — "
                f"as entidades não são válidas para análise.\n\n"
                f"Me diga um confronto real e eu sigo sem inventar dados."
            )
            payload: dict[str, Any] = {
                "intent": "analyze_match",
                "fixture_quality": "INVALID",
                "entities": {
                    "entity_invalid": True,
                    "fixture_quality": "INVALID",
                    "has_analysis": False,
                    "show_header": False,
                    "response_owner": "advanced_football_continuity",
                    "final_response": True,
                    "rewrite_locked": True,
                },
                "executive_summary": text,
                "final_recommendation": text,
                "best_markets": [],
                "confidence": {
                    "score": 0.0,
                    "label": "invalid",
                    "explanation": "Advanced term on INVALID fixture.",
                    "data_sources": ["Advanced Football Continuity"],
                },
                "risk": {
                    "level": "High",
                    "flags": ["invalid_entities"],
                    "invalidation_conditions": [],
                },
                "bankroll_recommendation": {
                    "recommended_stake_pct": 0.0,
                    "method": "quarter-Kelly",
                    "examples": {},
                    "no_bet": True,
                    "reasoning": "INVALID — sem stake.",
                },
                "knowledge_notes": [f"AdvancedFootball: INVALID term={term}"],
                "aurora_version": "Aurora v3.3.2-beta",
                "brain": brain or {},
            }
            payload = _stamp(payload, term=term, fixture=fixture, reused=True)
            ctx[RESOLVE_KEY] = {
                "term": term,
                "fixture": fixture,
                "invalid": True,
            }
            return payload

        label = str(fixture)
        text = _term_prose(term, label)

        # Prefer engine reuse when prior analysis has content (no new invention)
        payload = None
        la = ctx.get("last_analysis") if isinstance(ctx.get("last_analysis"), dict) else {}
        if la and (la.get("best_markets") or la.get("executive_summary")):
            try:
                from src.core.follow_up_engine import is_followup, resolve as fu_resolve

                engine_msg = {
                    "xg": "mais detalhes",
                    "pressao": "mais detalhes",
                    "probabilidade": "todos os mercados",
                    "value": "todos os mercados",
                    "edge": "todos os mercados",
                    "kelly": "resumo da analise",
                    "stake": "resumo da analise",
                    "ambas_marcam": "todos os mercados",
                    "market_line": "todos os mercados",
                }.get(term, "mais detalhes")
                if is_followup(engine_msg):
                    payload = fu_resolve(engine_msg, ctx, brain or {})
            except Exception as fu_exc:
                logger.warning(
                    "[AUDIT] AdvancedFootball: follow_up_engine skip (%s)", fu_exc
                )
                payload = None

        if isinstance(payload, dict):
            summary = str(payload.get("executive_summary") or "").strip()
            if not summary or len(summary) < 12 or summary in {"?", "…", "..."}:
                payload = None
            else:
                # Prefix with term framing without wiping useful engine content
                framed = (
                    f"No contexto de **{label}** (ângulo **{term}**):\n\n{summary}"
                )
                payload = dict(payload)
                payload["executive_summary"] = framed
                payload["final_recommendation"] = framed
                payload["intent"] = payload.get("intent") or "follow_up"

        if not isinstance(payload, dict):
            markets = []
            if isinstance(la.get("best_markets"), list):
                markets = [m for m in la["best_markets"] if isinstance(m, dict)][:5]
            payload = {
                "intent": "follow_up",
                "entities": {
                    "followup": True,
                    "has_analysis": True,
                    "show_header": False,
                    "response_owner": "advanced_football_continuity",
                    "final_response": True,
                    "home": info.get("home"),
                    "away": info.get("away"),
                    "team": info.get("team") or info.get("home"),
                },
                "executive_summary": text,
                "final_recommendation": text,
                "best_markets": markets,
                "confidence": {
                    "score": 4.0 if markets else 3.0,
                    "label": "adequate" if markets else "weak",
                    "explanation": "Advanced football continuity (fixture reuse).",
                    "data_sources": ["Advanced Football Continuity"],
                },
                "risk": {"level": "Medium", "flags": [], "invalidation_conditions": []},
                "bankroll_recommendation": {
                    "recommended_stake_pct": 0.0,
                    "method": "quarter-Kelly",
                    "examples": {},
                    "no_bet": True,
                    "reasoning": "Advanced continuity — sem novo stake inventado.",
                },
                "knowledge_notes": [
                    f"AdvancedFootball: term={term} fixture={fixture}"
                ],
                "aurora_version": "Aurora v3.3.2-beta",
                "brain": brain or {},
                "match": fixture,
            }

        payload = _stamp(payload, term=term, fixture=fixture, reused=True)
        ents = dict(payload.get("entities") or {})
        ents["rewrite_locked"] = True
        ents["turn_owner"] = ents.get("turn_owner") or "SPORT"
        ents["continuity_draft"] = str(payload.get("executive_summary") or "")[:2000]
        payload["entities"] = ents
        try:
            from src.conversation.turn_ownership import mark_owner

            payload = mark_owner(payload, "SPORT", rewrite_locked=True) or payload
        except Exception:
            pass

        ctx[RESOLVE_KEY] = {"term": term, "fixture": fixture, "reused": True}
        logger.warning(
            "[AUDIT] AdvancedFootball: BEFORE_FALLBACK term=%s fixture=%r reused=True",
            term,
            fixture,
        )
        try:
            from src.conversation.pipeline_trace import trace as _ptrace

            _ptrace(
                "ADVANCED_FOOTBALL",
                term=term,
                fixture=str(fixture)[:60] if fixture else None,
                before_fallback=True,
            )
        except Exception:
            pass
        return payload
    except Exception as exc:
        logger.warning("try_advanced_football_continuity fail-open: %s", exc)
        return None


def is_advanced_football_followup(message: str | None) -> bool:
    return detect_advanced_term(message) is not None
