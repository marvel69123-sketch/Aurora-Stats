"""
Phase 8.3-B / 8.4-A.8 — Conversation continuity (short sport follow-ups).

Arms a 1–3 turn window after repair / match-opinion / partial_analysis /
team_summary / short_sport_continue so "sim", "leitura rápida", "placar?",
"mercados?", "estatísticas?", "favorito?", "escalações?" reuse prior context.

Fail-open. Does not modify Opinion Renderer, Calendar Authority core,
Small Talk core, or Repair Engine modules.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any

logger = logging.getLogger(__name__)

CTX_KEY = "conversation_continuity"
RESOLVE_KEY = "continuity_resolve"
MAX_TURNS = 3

# Short follow-up kinds that must never be stolen by calendar / intel fallback
SPORT_FOLLOWUP_KINDS = frozenset(
    {
        "affirm",
        "leitura",
        "placar",
        "mercados",
        "estatisticas",
        "favorito",
        "escalacoes",
        "continue",
    }
)

_AFFIRM = re.compile(
    r"^(?:sim|yes|isso|pode|quero|bora|vamos|ok|okay|claro|"
    r"com\s+certeza|pode\s+ser|isso\s+mesmo|exato)\s*[!?.]*$",
    re.I,
)
_LEITURA = re.compile(
    r"^(?:leitura\s+rapida|uma\s+leitura\s+rapida|resumo(?:\s+rapido)?|"
    r"leitura|me\s+da\s+uma\s+leitura)\s*[!?.]*$",
    re.I,
)
_PLACAR = re.compile(
    r"^(?:(?:e\s+)?(?:o\s+)?placar|(?:e\s+)?(?:o\s+)?resultado)\s*[!?.]*$",
    re.I,
)
_MERCADOS = re.compile(
    r"^(?:e\s+)?(?:os\s+)?mercados?\s*\??$|"
    r"^e\s+mercados?\s*\??$|"
    r"^mercado\s*\??$",
    re.I,
)
_ESTATS = re.compile(
    r"^(?:e\s+)?(?:as\s+)?estatisticas?\s*\??$|"
    r"^(?:e\s+)?(?:os\s+)?stats?\s*\??$",
    re.I,
)
_FAVORITO = re.compile(
    r"^(?:e\s+)?(?:o\s+)?favoritos?\s*\??$|"
    r"^quem\s+(?:e|eh|é)\s+(?:o\s+)?favorito\s*\??$",
    re.I,
)
_ESCALACOES = re.compile(
    r"^(?:e\s+)?(?:as\s+)?escalacoes?\s*\??$|"
    r"^(?:e\s+)?(?:o\s+)?lineup\s*\??$",
    re.I,
)
_SHORT_SPORT = re.compile(
    r"^(?:e\s+ai|e\s+agora|continua|segue|mais|detalha|aprofunda)\s*[!?.]*$",
    re.I,
)


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


def get_continuity(ctx: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(ctx, dict):
        return {}
    raw = ctx.get(CTX_KEY)
    return dict(raw) if isinstance(raw, dict) else {}


def _team_from_ctx(ctx: dict[str, Any]) -> str | None:
    cont = get_continuity(ctx)
    if isinstance(cont.get("last_team"), str) and cont["last_team"].strip():
        return cont["last_team"].strip()
    try:
        from src.conversation.short_conversation_memory import get_short_memory

        sm = get_short_memory(ctx)
        if isinstance(sm.get("last_team"), str) and sm["last_team"].strip():
            return sm["last_team"].strip()
    except Exception:
        pass
    try:
        from src.conversation.conversation_repair import get_repair_memory

        rm = get_repair_memory(ctx)
        if isinstance(rm.get("last_team"), str) and rm["last_team"].strip():
            return rm["last_team"].strip()
    except Exception:
        pass
    th = ctx.get("deep_thinking") if isinstance(ctx.get("deep_thinking"), dict) else {}
    if isinstance(th.get("topic_team"), str) and th["topic_team"].strip():
        return th["topic_team"].strip()
    # Partial / analyze session
    lm = ctx.get("last_match")
    if isinstance(lm, str) and " x " in lm.lower():
        return lm.split(" x ")[0].strip() or None
    if isinstance(lm, str) and " vs " in lm.lower():
        return lm.split(" vs ")[0].strip() or None
    return None


def _fixture_from_ctx(ctx: dict[str, Any]) -> str | None:
    cont = get_continuity(ctx)
    mode = str(cont.get("mode") or "")
    team = (
        cont.get("last_team")
        if isinstance(cont.get("last_team"), str)
        else None
    )
    # Continuity-owned fixture first
    val = cont.get("last_fixture")
    if isinstance(val, str) and val.strip():
        # If mode is opinion/summary, ignore stale analyze fixture from another match
        if mode in {"opinion", "team_summary", "sport_continue", "repair_confirm"} and team:
            low = val.lower()
            if team.lower() not in low and " x " in low:
                return f"contexto do {team}"
        return val.strip()
    # Opinion / summary window must not inherit analyze last_match of another pair
    if mode in {"opinion", "team_summary", "sport_continue", "repair_confirm"} and team:
        return f"contexto do {team}"
    for key in ("last_match", "last_fixture"):
        val = ctx.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    try:
        from src.conversation.short_conversation_memory import get_short_memory

        sm = get_short_memory(ctx)
        fx = sm.get("last_fixture") or sm.get("last_match")
        if isinstance(fx, str) and fx.strip():
            return fx.strip()
    except Exception:
        pass
    team = team or _team_from_ctx(ctx)
    return f"contexto do {team}" if team else None


def _last_question(ctx: dict[str, Any]) -> str | None:
    try:
        from src.conversation.conversation_repair import get_repair_memory

        q = get_repair_memory(ctx).get("last_user_question")
        if isinstance(q, str) and q.strip():
            return q.strip()
    except Exception:
        pass
    try:
        from src.conversation.short_conversation_memory import get_short_memory

        q = get_short_memory(ctx).get("last_user_question")
        if isinstance(q, str) and q.strip():
            return q.strip()
    except Exception:
        pass
    cont = get_continuity(ctx)
    q = cont.get("last_user_question")
    return q.strip() if isinstance(q, str) and q.strip() else None


def _is_short_followup(message: str) -> str | None:
    """Return follow-up kind or None."""
    folded = _fold(message)
    if not folded or len(folded.split()) > 6:
        return None
    if _AFFIRM.match(folded):
        return "affirm"
    if _LEITURA.match(folded):
        return "leitura"
    if _PLACAR.match(folded):
        return "placar"
    if _MERCADOS.match(folded):
        return "mercados"
    if _ESTATS.match(folded):
        return "estatisticas"
    if _FAVORITO.match(folded):
        return "favorito"
    if _ESCALACOES.match(folded):
        return "escalacoes"
    if _SHORT_SPORT.match(folded):
        return "continue"
    return None


def is_active_sport_followup(
    ctx: dict[str, Any] | None,
    message: str | None = None,
) -> bool:
    """True when continuity window is active and this turn is a short sport FU."""
    if not isinstance(ctx, dict):
        return False
    cont = get_continuity(ctx)
    if not cont.get("active") or int(cont.get("turns_left") or 0) <= 0:
        return False
    resolve = ctx.get(RESOLVE_KEY) if isinstance(ctx.get(RESOLVE_KEY), dict) else {}
    kind = resolve.get("kind")
    if kind in SPORT_FOLLOWUP_KINDS:
        return True
    raw = str(message or ctx.get("raw_user_message") or "")
    return _is_short_followup(raw) in SPORT_FOLLOWUP_KINDS


def apply_continuity_resolve(
    message: str,
    ctx: dict[str, Any] | None,
) -> str:
    """
    Rewrite short sport follow-ups while continuity window is active.
    Must run BEFORE MasterIntent (after short-memory pronouns).

    Rewrites MUST NOT contain "jogo do …" (calendar poison for HIE / Natural).
    """
    try:
        if not message or not isinstance(ctx, dict):
            return message

        try:
            from src.conversation.conversation_repair import is_repair_signal

            if is_repair_signal(message):
                return message
        except Exception:
            pass

        cont = get_continuity(ctx)
        if not cont.get("active") or int(cont.get("turns_left") or 0) <= 0:
            return message

        kind = _is_short_followup(message)
        if not kind:
            return message

        team = _team_from_ctx(ctx)
        if not team:
            logger.warning(
                "[AUDIT] Continuity: follow-up %r without team — skip", message[:40]
            )
            return message

        last_q = _last_question(ctx)
        mode = str(cont.get("mode") or "opinion")
        fixture = _fixture_from_ctx(ctx) or team

        # Safe rewrites — never use "jogo do" (calendar authority trigger)
        if kind == "affirm":
            if last_q and re.search(
                r"\b(achou|partida|atuacao|ontem|ultimo|analise|confronto)\b",
                _fold(last_q),
            ):
                rewrite = last_q
            else:
                rewrite = f"continua a leitura do {team}"
        elif kind == "leitura":
            rewrite = f"me faz uma leitura rápida do {team}"
        elif kind == "placar":
            rewrite = f"qual foi o placar do {team}?"
        elif kind == "mercados":
            rewrite = f"e os mercados do {team}?"
        elif kind == "estatisticas":
            rewrite = f"e as estatísticas do {team}?"
        elif kind == "favorito":
            rewrite = f"quem é o favorito no contexto do {team}?"
        elif kind == "escalacoes":
            rewrite = f"quais as escalações do {team}?"
        else:
            rewrite = f"continua sobre o {team}"

        ctx[RESOLVE_KEY] = {
            "original": message,
            "rewrite": rewrite,
            "kind": kind,
            "mode": mode,
            "team": team,
            "fixture": fixture,
            "followup_context_found": True,
            "followup_source": mode,
        }
        logger.warning(
            "[AUDIT] Continuity: %r → %r kind=%s team=%r fixture=%r turns_left=%s",
            message,
            rewrite,
            kind,
            team,
            fixture,
            cont.get("turns_left"),
        )
        try:
            from src.conversation.pipeline_trace import trace as _ptrace

            _ptrace(
                "CONTINUITY",
                action="resolve",
                kind=kind,
                team=team,
                fixture=str(fixture)[:60] if fixture else None,
                rewrite=rewrite[:80],
            )
        except Exception:
            pass
        return rewrite
    except Exception as exc:
        logger.warning("apply_continuity_resolve fail-open: %s", exc)
        return message


def stamp_followup_audit(
    payload: dict[str, Any] | None,
    ctx: dict[str, Any] | None,
    *,
    before_fallback: bool = True,
) -> dict[str, Any] | None:
    """Attach required follow-up audit fields to entities."""
    if not isinstance(payload, dict):
        return payload
    out = dict(payload)
    ents = dict(out.get("entities") or {})
    resolve = {}
    cont = {}
    if isinstance(ctx, dict):
        resolve = (
            ctx.get(RESOLVE_KEY) if isinstance(ctx.get(RESOLVE_KEY), dict) else {}
        )
        cont = get_continuity(ctx)
    team = (
        resolve.get("team")
        or cont.get("last_team")
        or ents.get("team")
        or _team_from_ctx(ctx or {})
    )
    fixture = (
        resolve.get("fixture")
        or cont.get("last_fixture")
        or _fixture_from_ctx(ctx or {})
    )
    ents["followup_context_found"] = bool(
        resolve.get("followup_context_found")
        or cont.get("active")
        or team
        or fixture
    )
    ents["followup_source"] = str(
        resolve.get("followup_source")
        or resolve.get("mode")
        or cont.get("mode")
        or ents.get("followup_source")
        or "continuity"
    )
    ents["followup_resolved_team"] = team
    ents["followup_resolved_fixture"] = fixture
    ents["followup_before_fallback"] = bool(before_fallback)
    if resolve.get("kind"):
        ents["continuity_kind"] = resolve.get("kind")
    out["entities"] = ents
    return out


def _markets_from_ctx(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    la = ctx.get("last_analysis") if isinstance(ctx.get("last_analysis"), dict) else {}
    markets = la.get("best_markets") or []
    if isinstance(markets, list) and markets:
        return [m for m in markets if isinstance(m, dict)]
    return []


def _build_contextual_reply(
    kind: str,
    team: str,
    fixture: str | None,
    ctx: dict[str, Any],
) -> str:
    label = fixture or team
    markets = _markets_from_ctx(ctx)
    mode = str(get_continuity(ctx).get("mode") or "opinion")

    if kind == "mercados":
        if markets:
            lines = [
                f"No contexto de **{label}**, estes foram os mercados em destaque:",
                "",
            ]
            for m in markets[:5]:
                name = m.get("market") or m.get("name") or "mercado"
                prob = m.get("probability")
                bit = f"• **{name}**"
                if prob is not None:
                    try:
                        bit += f" — {float(prob):.0f}%"
                    except (TypeError, ValueError):
                        pass
                lines.append(bit)
            lines.append("")
            lines.append("Quer que eu afunile gols, escanteios ou um mercado específico?")
            return "\n".join(lines)
        return (
            f"Sobre **{label}**: ainda não fechei uma lista numérica de mercados "
            f"nesta conversa.\n\n"
            f"Posso priorizar gols, ambas marcam ou over asiático se você quiser "
            f"uma leitura direcionada — sem inventar odds."
        )

    if kind == "placar":
        la = ctx.get("last_analysis") if isinstance(ctx.get("last_analysis"), dict) else {}
        score = None
        if isinstance(la.get("score"), dict):
            cur = la["score"].get("current") or {}
            if cur.get("home") is not None and cur.get("away") is not None:
                score = f"{cur.get('home')} x {cur.get('away')}"
        if not score and isinstance(la.get("match_card"), dict):
            sc = la["match_card"].get("score")
            if isinstance(sc, str) and sc.strip():
                score = sc.strip()
        if score:
            return f"No contexto de **{label}**, o placar registrado é **{score}**."
        return (
            f"Sobre **{label}**: o desenlace/placar oficial não está confirmado "
            f"nesta conversa.\n\n"
            f"Me passa o resultado (ou o adversário) que eu fecho a leitura "
            f"sem inventar número."
        )

    if kind == "estatisticas":
        return (
            f"Sobre **{label}**: estatísticas fechadas (posse, chutes, etc.) "
            f"não estão confirmadas neste turno.\n\n"
            f"Posso seguir com leitura qualitativa do {team} "
            f"ou você me passa o que já viu do jogo."
        )

    if kind == "favorito":
        if markets:
            top = markets[0]
            name = top.get("market") or top.get("name") or "o recorte principal"
            return (
                f"No contexto de **{label}**, o recorte que mais se destaca "
                f"na leitura anterior é **{name}** — "
                f"não como certeza, mas como favorito relativo dos sinais disponíveis."
            )
        return (
            f"Sobre **{label}**: sem cravar favorito sem placar/estatísticas.\n\n"
            f"Pelo perfil do {team}, a leitura fica em equilíbrio / leve vantagem "
            f"situacional — me diga o adversário se quiser afinar."
        )

    if kind == "escalacoes":
        return (
            f"Sobre **{label}**: escalações oficiais não estão confirmadas "
            f"nesta conversa.\n\n"
            f"Se tiver a escalação (ou o adversário), eu encaixo na leitura."
        )

    if kind == "leitura":
        return (
            f"Leitura rápida no contexto de **{label}** "
            f"(modo {mode}): mantenho a linha da conversa anterior — "
            f"forças relativas do {team}, sem inventar estatísticas ausentes.\n\n"
            f"Quer mercados, placar ou um ponto específico?"
        )

    if kind == "affirm":
        return (
            f"Perfeito — seguimos no contexto de **{label}**.\n\n"
            f"Posso detalhar mercados, placar, favorito ou a leitura do {team}."
        )

    return (
        f"Seguindo no contexto de **{label}**.\n\n"
        f"O que você quer afunilar: mercados, placar, estatísticas ou favorito?"
    )


def try_contextual_short_followup(
    message: str,
    ctx: dict[str, Any] | None,
    *,
    brain: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """
    Phase 8.4-A.8 — resolve short sport follow-ups BEFORE
    Natural / IntelligenceFallback / presence claims.

    Prefer FollowUp engine when last_analysis exists; otherwise continuity reply.
    """
    try:
        if not isinstance(ctx, dict):
            return None
        if not is_active_sport_followup(ctx, message):
            return None

        resolve = (
            ctx.get(RESOLVE_KEY) if isinstance(ctx.get(RESOLVE_KEY), dict) else {}
        )
        raw = str(ctx.get("raw_user_message") or message or "")
        kind = resolve.get("kind") or _is_short_followup(raw) or _is_short_followup(
            message
        )
        if kind not in SPORT_FOLLOWUP_KINDS:
            return None

        team = str(resolve.get("team") or _team_from_ctx(ctx) or "").strip()
        if not team:
            return None
        fixture = resolve.get("fixture") or _fixture_from_ctx(ctx)

        # Prefer engine reuse only when prior analysis has usable content.
        # After match_opinion there is often no last_analysis — use continuity prose.
        payload: dict[str, Any] | None = None
        markets = _markets_from_ctx(ctx)
        la = ctx.get("last_analysis") if isinstance(ctx.get("last_analysis"), dict) else {}
        mode = str(get_continuity(ctx).get("mode") or resolve.get("mode") or "")
        can_reuse_engine = bool(markets) or bool(la.get("executive_summary")) or bool(
            la.get("positive_factors")
        )
        if can_reuse_engine and (ctx.get("last_match") or la):
            try:
                from src.core.follow_up_engine import is_followup, resolve as fu_resolve

                engine_msg = {
                    "mercados": "todos os mercados",
                    "placar": "e o resultado",
                    "favorito": "qual o favorito",
                    "estatisticas": "mais detalhes",
                    "escalacoes": "mais detalhes",
                    "leitura": "resumo da analise",
                    "continue": "explique melhor",
                    "affirm": "resumo da analise",
                }.get(str(kind), message)
                if is_followup(engine_msg):
                    payload = fu_resolve(engine_msg, ctx, brain or {})
            except Exception as fu_exc:
                logger.warning(
                    "[AUDIT] Continuity: follow_up_engine bridge skipped (%s)", fu_exc
                )
                payload = None

        def _useless_summary(text: str | None) -> bool:
            t = (text or "").strip()
            if not t or t in {"?", "…", "...", ".", "!"}:
                return True
            if len(t) < 12:
                return True
            # Personality crumbs like "Interessante.?"
            if re.fullmatch(r"(?i)interessante\.?\s*\??", t):
                return True
            return False

        if isinstance(payload, dict) and _useless_summary(
            str(payload.get("executive_summary") or "")
        ):
            logger.warning(
                "[AUDIT] Continuity: engine reply useless — using contextual prose mode=%s",
                mode,
            )
            payload = None

        if not isinstance(payload, dict):
            text = _build_contextual_reply(str(kind), team, fixture, ctx)
            payload = {
                "intent": "follow_up",
                "entities": {
                    "followup": True,
                    "continuity_followup": True,
                    "has_analysis": True,
                    "team": team,
                    "show_header": False,
                },
                "executive_summary": text,
                "final_recommendation": text,
                "best_markets": markets[:5],
                "confidence": {
                    "score": 4.0 if markets else 3.0,
                    "label": "adequate" if markets else "weak",
                    "explanation": "Follow-up contextual (continuidade).",
                    "data_sources": ["Conversation Continuity"],
                },
                "risk": {"level": "Medium", "flags": [], "invalidation_conditions": []},
                "bankroll_recommendation": {
                    "recommended_stake_pct": 0.0,
                    "method": "quarter-Kelly",
                    "examples": {},
                    "no_bet": True,
                    "reasoning": "Follow-up — sem novo stake.",
                },
                "knowledge_notes": [
                    f"Continuidade: kind={kind} team={team} fixture={fixture}",
                ],
                "aurora_version": "Aurora v3.3.2-beta",
                "brain": brain or {},
            }

        payload = stamp_followup_audit(payload, ctx, before_fallback=True) or payload
        try:
            from src.conversation.turn_ownership import mark_owner

            payload = mark_owner(payload, "SPORT", rewrite_locked=True) or payload
        except Exception:
            ents = dict(payload.get("entities") or {})
            ents["rewrite_locked"] = True
            ents["turn_owner"] = "SPORT"
            payload["entities"] = ents

        ents = dict(payload.get("entities") or {})
        ents["continuity_followup"] = True
        ents["response_owner"] = ents.get("response_owner") or "conversation_continuity"
        ents["final_response"] = True
        # Preserve draft so late layers (credibility/formatter) cannot erase it
        draft = str(payload.get("executive_summary") or "").strip()
        if draft and draft not in {"?", "…", "..."}:
            ents["continuity_draft"] = draft[:2000]
        payload["entities"] = ents

        logger.warning(
            "[AUDIT] ContinuityFollowUp: BEFORE_FALLBACK kind=%s team=%r fixture=%r",
            kind,
            team,
            fixture,
        )
        try:
            from src.conversation.pipeline_trace import trace as _ptrace

            _ptrace(
                "CONTINUITY_FOLLOWUP",
                kind=kind,
                team=team,
                before_fallback=True,
                source=ents.get("followup_source"),
            )
        except Exception:
            pass
        return payload
    except Exception as exc:
        logger.warning("try_contextual_short_followup fail-open: %s", exc)
        return None


def restore_continuity_draft(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """Re-apply continuity draft if a late layer wiped the executive summary."""
    if not isinstance(payload, dict):
        return payload
    ents = dict(payload.get("entities") or {})
    if not ents.get("continuity_followup"):
        return payload
    draft = ents.get("continuity_draft")
    if not isinstance(draft, str) or not draft.strip():
        return payload
    cur = str(payload.get("executive_summary") or "").strip()
    if cur and cur not in {"?", "…", "...", ".", "!"} and len(cur) >= 20:
        if not re.fullmatch(r"(?i)interessante\.?\s*\??", cur):
            return payload
    out = dict(payload)
    out["executive_summary"] = draft
    out["final_recommendation"] = draft
    out["entities"] = ents
    logger.warning("[AUDIT] ContinuityFollowUp: restored draft after late wipe")
    return out


def _arm(
    ctx: dict[str, Any],
    *,
    mode: str,
    team: str | None,
    question: str | None = None,
    fixture: str | None = None,
    turns: int = MAX_TURNS,
) -> None:
    mem = get_continuity(ctx)
    mem.update(
        {
            "active": True,
            "turns_left": max(1, min(int(turns), MAX_TURNS)),
            "mode": mode,
            "last_team": team or mem.get("last_team"),
            "last_user_question": question or mem.get("last_user_question"),
            "last_fixture": fixture
            or mem.get("last_fixture")
            or ctx.get("last_match")
            or (f"contexto do {team}" if team else None),
        }
    )
    ctx[CTX_KEY] = mem
    logger.warning(
        "[AUDIT] Continuity: ARMED mode=%s team=%r fixture=%r turns=%s",
        mode,
        mem.get("last_team"),
        mem.get("last_fixture"),
        mem.get("turns_left"),
    )


def note_continuity(
    ctx: dict[str, Any] | None,
    message: str,
    payload: dict[str, Any] | None,
) -> None:
    """Arm / refresh / decay continuity window from the turn result."""
    if not isinstance(ctx, dict):
        return
    try:
        ents = dict(payload.get("entities") or {}) if isinstance(payload, dict) else {}
        team = (
            ents.get("team")
            if isinstance(ents.get("team"), str)
            else None
        ) or (
            ents.get("home")
            if isinstance(ents.get("home"), str)
            else None
        ) or _team_from_ctx(ctx)
        fixture = None
        if isinstance(payload, dict):
            match = payload.get("match")
            if isinstance(match, str) and match.strip():
                fixture = match.strip()
        fixture = fixture or _fixture_from_ctx(ctx)
        resolve = (
            ctx.get(RESOLVE_KEY) if isinstance(ctx.get(RESOLVE_KEY), dict) else {}
        )
        user_q = str(
            resolve.get("original")
            or ctx.get("raw_user_message")
            or message
            or ""
        ).strip()

        # Arm after repair (awaiting user confirm / continue)
        if ents.get("conversation_repair") or ents.get("repair_mode"):
            q = _last_question(ctx) or user_q
            _arm(
                ctx,
                mode="repair_confirm",
                team=team,
                question=q,
                fixture=fixture,
                turns=MAX_TURNS,
            )
            ctx.pop(RESOLVE_KEY, None)
            return

        # Arm after match-opinion render
        if (
            ents.get("match_opinion_renderer")
            or ents.get("response_type") == "match_opinion"
            or ents.get("recent_match")
        ):
            op_team = team or (
                ents.get("team") if isinstance(ents.get("team"), str) else None
            )
            _arm(
                ctx,
                mode="opinion",
                team=op_team,
                question=user_q or _last_question(ctx),
                # Force team-scoped fixture — do not keep prior analyze pair
                fixture=(
                    f"contexto do {op_team}"
                    if op_team
                    else (fixture or None)
                ),
                turns=MAX_TURNS,
            )
            ctx.pop(RESOLVE_KEY, None)
            return

        # Arm after partial analysis recovery
        if (
            ents.get("preliminary_analysis")
            or ents.get("response_owner") == "partial_analysis"
            or ents.get("allow_partial_analysis")
        ):
            home = ents.get("home")
            away = ents.get("away")
            if isinstance(home, str) and isinstance(away, str) and home and away:
                team = home
                fixture = f"{home} x {away}"
            _arm(
                ctx,
                mode="partial_analysis",
                team=team,
                question=user_q or _last_question(ctx),
                fixture=fixture,
                turns=MAX_TURNS,
            )
            ctx.pop(RESOLVE_KEY, None)
            return

        # Arm after team_summary
        if ents.get("response_type") == "team_summary" or ents.get("team_summary"):
            _arm(
                ctx,
                mode="team_summary",
                team=team or ents.get("entity"),
                question=user_q or _last_question(ctx),
                fixture=fixture,
                turns=MAX_TURNS,
            )
            ctx.pop(RESOLVE_KEY, None)
            return

        # Arm after HCE short sport continue
        if ents.get("hce_kind") in {"short_sport_continue", "soft_followup"}:
            _arm(
                ctx,
                mode="sport_continue",
                team=team or ents.get("entity"),
                question=_last_question(ctx),
                fixture=fixture,
                turns=MAX_TURNS,
            )
            ctx.pop(RESOLVE_KEY, None)
            return

        cont = get_continuity(ctx)
        if not cont.get("active"):
            ctx.pop(RESOLVE_KEY, None)
            return

        # Consumed a continuity resolve this turn → refresh window slightly
        if resolve.get("rewrite") or ents.get("continuity_followup"):
            cont["turns_left"] = max(int(cont.get("turns_left") or 1), 2)
            if team:
                cont["last_team"] = team
            if fixture:
                cont["last_fixture"] = fixture
            if user_q and not _is_short_followup(user_q):
                cont["last_user_question"] = user_q[:240]
            if resolve.get("kind") == "affirm":
                cont["mode"] = cont.get("mode") or "opinion"
            ctx[CTX_KEY] = cont
            ctx.pop(RESOLVE_KEY, None)
            return

        # Decay on other turns while active
        left = int(cont.get("turns_left") or 0) - 1
        if left <= 0:
            cont["active"] = False
            cont["turns_left"] = 0
            logger.warning("[AUDIT] Continuity: EXPIRED")
        else:
            cont["turns_left"] = left
        ctx[CTX_KEY] = cont
        ctx.pop(RESOLVE_KEY, None)
    except Exception as exc:
        logger.warning("note_continuity fail-open: %s", exc)
