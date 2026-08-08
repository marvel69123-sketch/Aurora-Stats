"""
8.4-A.20 — Ambiguous Context Priming Guard.

Status: FROZEN (AEP P0 stabilization closed — do not patch without P1 redesign).

Detects ambiguous openers, asks for clarification instead of assuming,
blocks continuity/sport_anchor/context-lock bootstrap while ambiguous,
drops continuity on context jumps, and blocks sticky GA templates.

Fail-open. No sticky ownership soft-hold. Does not invent match data.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any

logger = logging.getLogger(__name__)

CTX_KEY = "ambiguous_context_guard"

_OBS_KEYS = (
    "ambiguous_detected",
    "clarification_triggered",
    "bootstrap_blocked",
    "context_jump_detected",
    "continuity_dropped",
    "sticky_template_blocked",
)

# Bare / underspecified openers that prime wrong sport/GA context
_AMBIGUOUS_EXACT = frozenset(
    {
        "argentina",
        "barcelona",
        "real madrid",
        "flamengo",
        "palmeiras",
        "corinthians",
        "santos",
        "botafogo",
        "brasil",
        "espanha",
        "portugal",
        "franca",
        "frança",
        "alemanha",
        "italia",
        "itália",
        "mercados",
        "mercados?",
        "mercado",
        "pressao",
        "pressão",
        "pressao?",
        "pressão?",
        "xg",
        "xg?",
        "o outro",
        "o outro?",
        "e o outro",
        "e o outro?",
        "o de ontem",
        "o de ontem?",
        "kkkkk",
        "kkkk",
        "kkk",
        "ah ta genial",
        "ah tá genial",
        "ah ta, genial",
        "ah tá, genial",
        "aff",
    }
)

_AMBIGUOUS_PAT = re.compile(
    r"^(?:"
    r"(?:o\s+de\s+ontem|e\s+o\s+outro|o\s+outro)"
    r"|"
    r"(?:mercados?|pressao|pressão|xg|kelly|edge|stake|value)"
    r"\??"
    r"|"
    r"pesquisa\s+(?:o|a|os|as)?\s*\w+"
    r"|"
    r"me\s+fala\s+(?:do|da|de)\s+\w+"
    r"|"
    r"k{3,}"
    r")"
    r"[\s?!.,]*$",
    re.I,
)

# Clear sport fixture — not ambiguous
_CLEAR_FIXTURE = re.compile(
    r"\b[\wÀ-ÿ.''-]{2,}\s+(?:x|vs\.?|versus)\s+[\wÀ-ÿ.''-]{2,}\b",
    re.I,
)

_FICTION = re.compile(
    r"(?:"
    r"goku\s*x\s*naruto|"
    r"harry\s+potter\s*x\s*voldemort|"
    r"batman\s*x\s*superman|"
    r"pikachu\s*x\s*"
    r")",
    re.I,
)

_IDENTITY_JUMP = re.compile(
    r"^(?:"
    r"(?:qual\s+(?:e|é)\s+(?:o\s+)?seu\s+nome|seu\s+nome\??|"
    r"(?:voce|você)\s+(?:e|é)\s+a\s+aurora|"
    r"o\s+que\s+(?:voce|você)\s+faz|"
    r"o\s+que\s+sabe\s+fazer|"
    r"suas?\s+funcionalidades)"
    r")"
    r"[\s?!.,]*$",
    re.I,
)

_GREETING_JUMP = re.compile(
    r"^(?:oi|ola|olá|e\s*ai|e\s*aí|boa\s*(?:noite|tarde|dia)|"
    r"bom\s+dia|fala|hey|hi|hello)[\s?!.,]*$",
    re.I,
)

_STICKY_PREFIX = "Entendi. Posso te ajudar"

_NATIONAL_TEAMS = frozenset(
    {
        "argentina",
        "brasil",
        "brazil",
        "espanha",
        "spain",
        "portugal",
        "franca",
        "frança",
        "france",
        "alemanha",
        "germany",
        "italia",
        "itália",
        "italy",
        "inglaterra",
        "england",
        "holanda",
        "netherlands",
        "uruguai",
        "uruguay",
        "chile",
        "colombia",
        "colômbia",
        "mexico",
        "méxico",
        "eua",
        "usa",
    }
)

_CLUB_HINTS = frozenset(
    {
        "barcelona",
        "real madrid",
        "flamengo",
        "palmeiras",
        "corinthians",
        "santos",
        "botafogo",
        "juventus",
        "chelsea",
        "liverpool",
        "arsenal",
        "milan",
        "inter",
        "psg",
    }
)


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


def _blob(ctx: dict[str, Any]) -> dict[str, Any]:
    b = ctx.get(CTX_KEY)
    if not isinstance(b, dict):
        b = {
            "counters": {},
            "pending_clarify": False,
            "last_token": None,
            "bootstrap_blocked": False,
        }
        ctx[CTX_KEY] = b
    if not isinstance(b.get("counters"), dict):
        b["counters"] = {}
    for k in _OBS_KEYS:
        b["counters"].setdefault(k, 0)
    return b


def bump(ctx: dict[str, Any] | None, key: str, *, n: int = 1) -> None:
    if not isinstance(ctx, dict) or key not in _OBS_KEYS:
        return
    try:
        _blob(ctx)["counters"][key] = int(_blob(ctx)["counters"].get(key) or 0) + n
    except Exception:
        pass


def get_guard_counters(ctx: dict[str, Any] | None) -> dict[str, int]:
    if not isinstance(ctx, dict):
        return {k: 0 for k in _OBS_KEYS}
    return dict(_blob(ctx).get("counters") or {})


def _has_sport_anchor(ctx: dict[str, Any] | None) -> bool:
    try:
        from src.conversation.sport_continuity_guard import sport_anchor_active

        return bool(sport_anchor_active(ctx))
    except Exception:
        return False


def _has_continuity(ctx: dict[str, Any] | None) -> bool:
    if not isinstance(ctx, dict):
        return False
    cont = ctx.get("conversation_continuity")
    return isinstance(cont, dict) and bool(cont.get("active"))


def _has_sport_context(ctx: dict[str, Any] | None) -> bool:
    """Any recoverable sport frame (anchor, continuity, last_match, short memory)."""
    if not isinstance(ctx, dict):
        return False
    if _has_sport_anchor(ctx) or _has_continuity(ctx):
        return True
    lm = ctx.get("last_match")
    if isinstance(lm, str) and lm.strip():
        return True
    sm = ctx.get("short_conversation_memory")
    if isinstance(sm, dict) and (
        sm.get("last_fixture") or sm.get("last_team") or sm.get("last_match")
    ):
        return True
    try:
        from src.conversation.ownership_stability import owner_lock_active

        if owner_lock_active(ctx):
            return True
    except Exception:
        pass
    return False


def _is_short_sport_fu_token(folded: str) -> bool:
    """Bare market/FU tokens that need a prior fixture — not team openers."""
    t = (folded or "").rstrip("?!.,")
    if t in {
        "mercados",
        "mercado",
        "pressao",
        "pressão",
        "xg",
        "kelly",
        "edge",
        "stake",
        "value",
        "o outro",
        "e o outro",
        "estatisticas",
        "estatísticas",
        "placar",
        "odds",
        "odd",
    }:
        return True
    try:
        from src.conversation.sport_continuity_guard import is_sport_short_followup

        if is_sport_short_followup(folded):
            return True
    except Exception:
        pass
    return False


def _looks_like_team_token(folded: str) -> bool:
    if not folded or " " in folded:
        # allow two-word clubs
        if folded in _AMBIGUOUS_EXACT or folded in _CLUB_HINTS:
            return True
        if folded in _NATIONAL_TEAMS:
            return True
        return False
    if not folded.isalpha() or len(folded) < 3:
        return False
    if folded in _AMBIGUOUS_EXACT or folded in _NATIONAL_TEAMS or folded in _CLUB_HINTS:
        return True
    try:
        from src.core.team_aliases import TEAM_ALIASES

        if folded in TEAM_ALIASES:
            return True
    except Exception:
        pass
    return False


def is_clear_fixture(message: str | None) -> bool:
    folded = _fold(message or "")
    if not folded:
        return False
    if _FICTION.search(folded):
        return False
    return bool(_CLEAR_FIXTURE.search(folded))


def is_fiction_fixture(message: str | None) -> bool:
    return bool(_FICTION.search(_fold(message or "")))


def is_ambiguous_opener(message: str | None, ctx: dict[str, Any] | None = None) -> bool:
    """
    Ambiguous opener detector.

    Short sport FUs with ANY recoverable sport context are NOT ambiguous
    (A.18 / continuity / last_match own them — do not steal with clarify).
    Clear real fixtures are NOT ambiguous.
    """
    folded = _fold(message or "")
    if not folded:
        return False
    if is_clear_fixture(message) and not is_fiction_fixture(message):
        return False
    if _IDENTITY_JUMP.match(folded) or _GREETING_JUMP.match(folded):
        return False

    # Any sport frame + short FU → never clarify (let continuity/SCG/OS claim)
    if ctx is not None and _has_sport_context(ctx) and _is_short_sport_fu_token(folded):
        return False
    if ctx is not None and _has_sport_context(ctx):
        try:
            from src.conversation.sport_continuity_guard import is_sport_short_followup

            if is_sport_short_followup(message):
                return False
        except Exception:
            pass

    # Bare short FU without sport frame → clarify (do not assume)
    if _is_short_sport_fu_token(folded) or _AMBIGUOUS_PAT.match(folded):
        # Exclude team-name exact matches handled below
        if not _looks_like_team_token(folded.rstrip("?!.,")):
            return True

    if folded in _AMBIGUOUS_EXACT:
        # Team tokens in EXACT set still ambiguous as openers
        return True
    # Single / short team-like token without fixture
    tokens = folded.split()
    if len(tokens) == 1 and _looks_like_team_token(folded):
        return True
    if len(tokens) == 2 and folded in _CLUB_HINTS:
        return True
    if folded.startswith("pesquisa ") or folded.startswith("me fala d"):
        return True
    if re.fullmatch(r"k{3,}", folded):
        return True
    if "genial" in folded and len(tokens) <= 4:
        return True
    return False


def is_context_jump(message: str | None, ctx: dict[str, Any] | None = None) -> bool:
    """
    Context jump: prior sport/continuity exists, new message leaves that frame.
    Example: Flamengo x Palmeiras → seu nome? → Goku x Naruto
    """
    if not isinstance(ctx, dict):
        return False
    had_sport = (
        _has_sport_anchor(ctx)
        or _has_continuity(ctx)
        or bool(ctx.get("last_match"))
        or bool(
            isinstance(ctx.get("short_conversation_memory"), dict)
            and (
                ctx["short_conversation_memory"].get("last_fixture")
                or ctx["short_conversation_memory"].get("last_team")
            )
        )
    )
    if not had_sport:
        # Fiction still jumps even from empty (drops any residual priming)
        return is_fiction_fixture(message)

    folded = _fold(message or "")
    if not folded:
        return False
    if is_fiction_fixture(message):
        return True
    if _IDENTITY_JUMP.match(folded) or _GREETING_JUMP.match(folded):
        return True
    # Fiction already handled. New *real* fixture replaces topic in-place
    # (sport engines re-arm) — do not treat as jump/drop that blanks last_match.
    return False


def drop_continuity(
    ctx: dict[str, Any] | None,
    *,
    reason: str = "context_jump",
) -> None:
    """Remove continuity / sport_anchor / soft owner lock on context jump."""
    if not isinstance(ctx, dict):
        return
    dropped = False
    try:
        cont = ctx.get("conversation_continuity")
        if isinstance(cont, dict) and cont.get("active"):
            cont["active"] = False
            cont["turns_left"] = 0
            cont["mode"] = f"dropped:{reason}"
            ctx["conversation_continuity"] = cont
            dropped = True
    except Exception:
        pass
    try:
        from src.conversation.sport_continuity_guard import expire_sport_anchor

        if _has_sport_anchor(ctx):
            expire_sport_anchor(ctx, reason=reason)
            dropped = True
    except Exception:
        pass
    try:
        from src.conversation.ownership_stability import (
            owner_lock_active,
            release_owner_lock,
        )

        if owner_lock_active(ctx):
            release_owner_lock(ctx, reason=f"context_jump:{reason}")
            dropped = True
    except Exception:
        pass
    # Clear sticky session match priming that feeds wrong bootstrap
    try:
        if reason.startswith("context_jump") or reason == "fiction":
            ctx.pop("last_match", None)
    except Exception:
        pass
    blob = _blob(ctx)
    blob["pending_clarify"] = False
    blob["bootstrap_blocked"] = False
    if dropped or reason:
        bump(ctx, "continuity_dropped")
    logger.warning("[AUDIT] AmbiguousContext: CONTINUITY_DROPPED reason=%s", reason)


def bootstrap_blocked(
    ctx: dict[str, Any] | None,
    *,
    message: str | None = None,
    reason: str | None = None,
) -> bool:
    """
    Bootstrap guard: do not create continuity / sport_anchor / context lock
    while context is ambiguous or clarification is pending.
    """
    if not isinstance(ctx, dict):
        return False
    blob = _blob(ctx)
    if blob.get("pending_clarify") or blob.get("bootstrap_blocked"):
        bump(ctx, "bootstrap_blocked")
        return True
    msg = message
    if msg is None:
        msg = (
            ctx.get("raw_user_message")
            if isinstance(ctx.get("raw_user_message"), str)
            else None
        )
    if msg and is_ambiguous_opener(msg, ctx):
        bump(ctx, "bootstrap_blocked")
        return True
    # Weak team_context anchors are the priming vector — never bootstrap from them
    # while clarification is the right response for bare team tokens.
    if reason in {"team_context", "session_memory"} and msg and is_ambiguous_opener(msg, None):
        bump(ctx, "bootstrap_blocked")
        return True
    return False


def should_block_sticky_template(
    message: str | None,
    ctx: dict[str, Any] | None = None,
    *,
    text: str | None = None,
) -> bool:
    """Block sticky 'Entendi. Posso te ajudar...' for ambiguous messages."""
    sticky = False
    if isinstance(text, str) and text.strip().startswith(_STICKY_PREFIX):
        sticky = True
    if is_ambiguous_opener(message, ctx) or (
        isinstance(ctx, dict) and _blob(ctx).get("pending_clarify")
    ):
        if sticky or text is None:
            if isinstance(ctx, dict):
                bump(ctx, "sticky_template_blocked")
            return True
    return False


def build_clarification_text(message: str | None) -> str:
    folded = _fold(message or "")
    token = folded.rstrip("?!.,")

    if token in _NATIONAL_TEAMS or token == "argentina":
        label = token.title().replace("Brasil", "Brasil")
        if token == "argentina":
            label = "Argentina"
        return (
            "Você está falando de:\n"
            f"- Seleção {label}?\n"
            "- Jogo específico?\n"
            "- Notícias?"
        )
    if token in _CLUB_HINTS or _looks_like_team_token(token):
        nice = " ".join(w.capitalize() for w in token.split())
        return (
            "Você está falando de:\n"
            f"- O clube {nice}?\n"
            "- Um jogo específico?\n"
            "- Notícias / momento do time?"
        )
    if token in {"o de ontem", "o de ontem?"}:
        return (
            "Você está falando de:\n"
            "- Um jogo de ontem?\n"
            "- Um time específico?\n"
            "- Notícias?"
        )
    if token in {
        "mercados",
        "mercados?",
        "mercado",
        "pressao",
        "pressão",
        "pressao?",
        "pressão?",
        "xg",
        "xg?",
        "o outro",
        "o outro?",
        "e o outro",
        "e o outro?",
    }:
        return (
            "Você está falando de:\n"
            "- Um jogo específico (ex.: Time A x Time B)?\n"
            "- Continuação de uma análise anterior?\n"
            "- Outro assunto?"
        )
    if re.fullmatch(r"k{3,}", token) or "genial" in token or token == "aff":
        return (
            "Não peguei o contexto ainda.\n\n"
            "Você está falando de:\n"
            "- Um jogo / time?\n"
            "- Outra coisa?"
        )
    if token.startswith("pesquisa ") or token.startswith("me fala"):
        return (
            "Você está falando de:\n"
            "- Análise esportiva de um time/jogo?\n"
            "- Notícias?\n"
            "- Outro assunto?"
        )
    return (
        "Você está falando de:\n"
        "- Seleção / time?\n"
        "- Jogo específico?\n"
        "- Notícias?"
    )


def build_clarification_payload(
    message: str,
    ctx: dict[str, Any] | None = None,
) -> dict[str, Any]:
    text = build_clarification_text(message)
    if isinstance(ctx, dict):
        blob = _blob(ctx)
        blob["pending_clarify"] = True
        blob["bootstrap_blocked"] = True
        blob["last_token"] = _fold(message)
        bump(ctx, "clarification_triggered")
    try:
        from src.brain import get_brain_meta

        brain = get_brain_meta()
    except Exception:
        brain = {}
    return {
        "intent": "clarification",
        "answer": text,
        "text": text,
        "response": text,
        "match": None,
        "status": None,
        "is_live": False,
        "minute": None,
        "executive_summary": text,
        "best_markets": [],
        "confidence": {
            "score": 0.0,
            "label": "insufficient",
            "explanation": "Clarificação de contexto ambíguo (sem análise esportiva).",
            "data_sources": ["AmbiguousContextGuard"],
        },
        "risk": {"level": "Unknown", "flags": [], "invalidation_conditions": []},
        "bankroll_recommendation": {
            "recommended_stake_pct": 0.0,
            "method": "quarter-Kelly",
            "examples": {},
            "no_bet": True,
            "reasoning": "",
        },
        "positive_factors": [],
        "negative_factors": [],
        "historical_references": [],
        "knowledge_notes": [],
        "final_recommendation": text,
        "aurora_version": "Copilot v1.0",
        "brain": brain,
        "response_metadata": {
            "mode": "clarification",
            "source": "ambiguous_context_guard",
        },
        "entities": {
            "ambiguous_context_guard": True,
            "clarification_mode": True,
            "ambiguous_opener": True,
            "bootstrap_blocked": True,
            "has_analysis": False,
            "show_header": False,
            "skip_llm": True,
            "response_owner": "ambiguous_context_guard",
            "turn_owner": "CLARIFY",
            "rewrite_locked": True,
            "ambiguous_guard_counters": get_guard_counters(ctx)
            if isinstance(ctx, dict)
            else {},
        },
    }


def process_turn_start(
    message: str,
    ctx: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """
    Early turn hook (before continuity / OS / GA):
    1) detect context_jump → drop continuity
    2) detect ambiguous opener → clarification claim
    """
    if not isinstance(ctx, dict):
        return None
    try:
        # Reset per-turn bootstrap flag (pending_clarify may persist one turn)
        blob = _blob(ctx)
        blob["bootstrap_blocked"] = False

        if is_context_jump(message, ctx):
            bump(ctx, "context_jump_detected")
            drop_continuity(ctx, reason="context_jump")
            logger.warning(
                "[AUDIT] AmbiguousContext: CONTEXT_JUMP msg=%r",
                (message or "")[:80],
            )

        if is_ambiguous_opener(message, ctx):
            bump(ctx, "ambiguous_detected")
            blob["bootstrap_blocked"] = True
            # Fiction fixtures are jumps, not clarify-as-sport
            if is_fiction_fixture(message):
                return None
            # P3: frustration / menus disabled / short+goal → never sport menu
            try:
                from src.conversation.perception_conversation_state import (
                    current_goal_text,
                    is_frustration,
                    is_short_message,
                    menus_disabled,
                    note_user_message,
                )

                note_user_message(ctx, message)
                if (
                    menus_disabled(ctx)
                    or is_frustration(message)
                    or (is_short_message(message) and current_goal_text(ctx))
                ):
                    return None
            except Exception:
                pass
            # Identity/greeting already excluded in detector
            payload = build_clarification_payload(message, ctx)
            logger.warning(
                "[AUDIT] AmbiguousContext: CLARIFY opener=%r",
                (message or "")[:80],
            )
            return payload

        # Resolved clear fixture → clear pending clarify
        if is_clear_fixture(message) and not is_fiction_fixture(message):
            blob["pending_clarify"] = False
            blob["bootstrap_blocked"] = False
        return None
    except Exception as exc:
        logger.warning("ambiguous_context process_turn_start fail-open: %s", exc)
        return None


def try_ambiguous_clarification_claim(
    message: str,
    ctx: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Public early-claim entry used by the router."""
    return process_turn_start(message, ctx)


def stamp_payload_observability(
    payload: dict[str, Any] | None,
    ctx: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(payload, dict) or not isinstance(ctx, dict):
        return payload
    try:
        ents = dict(payload.get("entities") or {})
        ents["ambiguous_guard_counters"] = get_guard_counters(ctx)
        blob = _blob(ctx)
        ents["ambiguous_pending_clarify"] = bool(blob.get("pending_clarify"))
        payload["entities"] = ents
    except Exception:
        pass
    return payload


def note_after_clarification(
    ctx: dict[str, Any] | None,
    message: str,
    payload: dict[str, Any] | None,
) -> None:
    """Keep bootstrap blocked after clarification replies; clear on clear sport."""
    if not isinstance(ctx, dict):
        return
    try:
        ents = dict(payload.get("entities") or {}) if isinstance(payload, dict) else {}
        blob = _blob(ctx)
        if ents.get("clarification_mode") or ents.get("ambiguous_context_guard"):
            blob["pending_clarify"] = True
            blob["bootstrap_blocked"] = True
            return
        if is_clear_fixture(message) and not is_fiction_fixture(message):
            blob["pending_clarify"] = False
            blob["bootstrap_blocked"] = False
            return
        # Successful sport reply clears pending
        intent = str(payload.get("intent") or "") if isinstance(payload, dict) else ""
        if intent in {"analyze_match", "follow_up", "match_opinion"} and not ents.get(
            "clarification_mode"
        ):
            if ents.get("turn_owner") == "SPORT" or ents.get("response_owner") in {
                "partial_analysis",
                "conversation_continuity",
                "pronoun_continuity",
                "advanced_football_continuity",
                "match_opinion_renderer",
            }:
                blob["pending_clarify"] = False
                blob["bootstrap_blocked"] = False
    except Exception as exc:
        logger.warning("note_after_clarification fail-open: %s", exc)
