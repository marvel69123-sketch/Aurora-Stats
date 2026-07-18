"""
Phase 8.3-B — Conversation continuity (short sport follow-ups).

Arms a 1–3 turn window after repair / match-opinion / short_sport_continue
so "sim", "leitura rápida", "placar", "e mercados?" do not fall into GA.

Fail-open. Does not modify repair / short_memory / ownership / renderer modules.
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
    r"^(?:placar|o\s+placar|resultado|o\s+resultado)\s*[!?.]*$",
    re.I,
)
_MERCADOS = re.compile(
    r"^(?:e\s+)?(?:os\s+)?mercados?\s*\??$|"
    r"^e\s+mercados?\s*\??$|"
    r"^mercado\s*\??$",
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
    return None


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
    if _SHORT_SPORT.match(folded):
        return "continue"
    return None


def apply_continuity_resolve(
    message: str,
    ctx: dict[str, Any] | None,
) -> str:
    """
    Rewrite short sport follow-ups while continuity window is active.
    Must run BEFORE MasterIntent (after short-memory pronouns).
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

        if kind == "affirm":
            if last_q and re.search(
                r"\b(achou|jogo|partida|atuacao|ontem|ultimo)\b", _fold(last_q)
            ):
                rewrite = last_q
            else:
                rewrite = f"o que você achou do jogo do {team} ontem?"
        elif kind == "leitura":
            rewrite = f"me faz uma leitura rápida do último jogo do {team}"
        elif kind == "placar":
            rewrite = f"qual foi o placar do último jogo do {team}?"
        elif kind == "mercados":
            rewrite = f"e os mercados do jogo do {team}?"
        else:
            rewrite = f"continua sobre o {team}"

        ctx[RESOLVE_KEY] = {
            "original": message,
            "rewrite": rewrite,
            "kind": kind,
            "mode": mode,
            "team": team,
        }
        logger.warning(
            "[AUDIT] Continuity: %r → %r kind=%s team=%r turns_left=%s",
            message,
            rewrite,
            kind,
            team,
            cont.get("turns_left"),
        )
        try:
            from src.conversation.pipeline_trace import trace as _ptrace

            _ptrace(
                "CONTINUITY",
                action="resolve",
                kind=kind,
                team=team,
                rewrite=rewrite[:80],
            )
        except Exception:
            pass
        return rewrite
    except Exception as exc:
        logger.warning("apply_continuity_resolve fail-open: %s", exc)
        return message


def _arm(
    ctx: dict[str, Any],
    *,
    mode: str,
    team: str | None,
    question: str | None = None,
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
        }
    )
    ctx[CTX_KEY] = mem
    logger.warning(
        "[AUDIT] Continuity: ARMED mode=%s team=%r turns=%s",
        mode,
        mem.get("last_team"),
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
        ) or _team_from_ctx(ctx)
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
            _arm(ctx, mode="repair_confirm", team=team, question=q, turns=MAX_TURNS)
            ctx.pop(RESOLVE_KEY, None)
            return

        # Arm after match-opinion render
        if (
            ents.get("match_opinion_renderer")
            or ents.get("response_type") == "match_opinion"
            or ents.get("recent_match")
        ):
            _arm(
                ctx,
                mode="opinion",
                team=team,
                question=user_q or _last_question(ctx),
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
                turns=MAX_TURNS,
            )
            ctx.pop(RESOLVE_KEY, None)
            return

        cont = get_continuity(ctx)
        if not cont.get("active"):
            ctx.pop(RESOLVE_KEY, None)
            return

        # Consumed a continuity resolve this turn → refresh window slightly
        if resolve.get("rewrite"):
            cont["turns_left"] = max(int(cont.get("turns_left") or 1), 2)
            if team:
                cont["last_team"] = team
            if user_q and not _is_short_followup(user_q):
                cont["last_user_question"] = user_q[:240]
            # After affirm, mode becomes opinion continue
            if resolve.get("kind") == "affirm":
                cont["mode"] = "opinion"
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
