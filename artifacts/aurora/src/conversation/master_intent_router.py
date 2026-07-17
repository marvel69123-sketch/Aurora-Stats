"""
Master Intent Router — classify BEFORE any sports pipeline.

Only SPORT_QUERY and LIVE_MATCH may touch entity resolver / markets / sport planner.
Fail-open to GENERAL_CHAT. Additive.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import asdict, dataclass
from typing import Any, Literal

logger = logging.getLogger(__name__)

MasterIntent = Literal[
    "SMALL_TALK",
    "GENERAL_CHAT",
    "SPORT_QUERY",
    "LIVE_MATCH",
    "MEMORY_QUERY",
    "MATH_QUERY",
    "SYSTEM_QUERY",
]

SPORT_INTENTS = frozenset({"SPORT_QUERY", "LIVE_MATCH"})

CTX_KEY = "master_intent"


@dataclass
class MasterIntentResult:
    intent: MasterIntent
    confidence: float
    reason: str
    allow_sport_pipeline: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


_MATH = re.compile(
    r"("
    r"quanto\s+(?:e|eh|é)\s+\d|"
    r"\d+\s*[\+\-\*\/x×÷]\s*\d+|"
    r"quanto\s+(?:e|eh|é)\s+\d+\s*[\+\-\*\/x×÷]\s*\d+|"
    r"resolva\s+\d|"
    r"calcule\s+\d|"
    r"^\d+\s*[\+\-\*\/x×÷]\s*\d+\s*\??$"
    r")",
    re.I,
)

_SMALL = re.compile(
    r"("
    r"^(?:oi|ola|hey|hello|hi)(?:\s+\w+){0,4}[\s!?.]*$|"
    r"^(?:bom\s+dia|boa\s+tarde|boa\s+noite)(?:\s+\w+){0,3}[\s!?.]*$|"
    r"tudo\s+bem|td\s+bem|beleza|blz|e\s+ai|eae|"
    r"como\s+(?:voce\s+)?(?:esta|vai)|"
    r"obrigad|valeu|thanks|tmj|"
    r"boa\s+sorte|até\s+logo|ate\s+logo|tchau|flw"
    r")",
    re.I,
)

_SYSTEM = re.compile(
    r"("
    r"qual\s+(?:(?:e|eh|é)\s+)?(?:o\s+)?seu\s+nome|"
    r"como\s+(?:voce\s+)?se\s+chama|"
    r"quem\s+(?:e|eh|é)\s+(?:voce|a\s+aurora)|"
    r"quem\s+(?:te\s+)?criou|"
    r"o\s+que\s+(?:voce\s+)?(?:faz|e)\b|"
    r"quais\s+(?:suas\s+)?(?:funcoes|capacidades)|"
    r"no\s+que\s+(?:voce\s+)?pode\s+ajudar|"
    r"o\s+que\s+(?:voce\s+)?(?:consegue|pode)\s+fazer|"
    r"ajuda(?:\s+me)?$|"
    r"^help$"
    r")",
    re.I,
)

_MEMORY = re.compile(
    r"("
    r"voce\s+lembra|"
    r"se\s+lembra|"
    r"esquece(?:\s+isso)?|"
    r"meu\s+nome\s+e|"
    r"qual\s+(?:e|eh|é)\s+meu\s+nome|"
    r"meu\s+time\s+(?:e|eh|é)|"
    r"sobre\s+mim"
    r")",
    re.I,
)

_LIVE = re.compile(
    r"\b(ao\s+vivo|live|placar\s+ao\s+vivo|minuto\s+\d+)\b",
    re.I,
)

_SPORT = re.compile(
    r"("
    r"\b(analisar|analise|analyze|avaliar)\b|"
    r"\b\w+\s+[xX]\s+\w+\b|"
    r"\bvs\.?\b|"
    r"\b(jogo|partida|confronto|fixture|mercado|odds|"
    r"brasileirao|libertadores|champions|premier|"
    r"como\s+esta\s+(?:o|a)\s+\w+|o\s+que\s+acha\s+d[oe]|"
    r"joga\s+(?:hoje|amanha)|que\s+horas|horario|"
    r"tem\s+jogo|proximo\s+jogo|escalacao)\b"
    r")",
    re.I,
)

# Known clubs / sport tokens that force sport even without x
_KNOWN_CLUB = re.compile(
    r"\b(flamengo|botafogo|santos|corinthians|palmeiras|sao\s+paulo|"
    r"fluminense|gremio|internacional|vasco|bahia|mirassol|"
    r"arsenal|chelsea|liverpool|juventus|londrina|"
    r"sao\s+bernardo|ivai)\b",
    re.I,
)


def classify_master_intent(message: str) -> MasterIntentResult:
    folded = _fold(message)
    if not folded:
        return MasterIntentResult("GENERAL_CHAT", 0.4, "empty", False)

    if _MATH.search(folded) or _MATH.search(message or ""):
        return MasterIntentResult("MATH_QUERY", 0.97, "math_expression", False)

    if _SYSTEM.search(folded):
        return MasterIntentResult("SYSTEM_QUERY", 0.95, "identity_or_capabilities", False)

    if _MEMORY.search(folded):
        return MasterIntentResult("MEMORY_QUERY", 0.9, "memory_or_profile", False)

    # Sport BEFORE small talk — "como está o Botafogo?" is SPORT, not greeting
    if _LIVE.search(folded) and (
        _SPORT.search(folded) or _KNOWN_CLUB.search(folded) or re.search(r"\bx\b", folded)
    ):
        return MasterIntentResult("LIVE_MATCH", 0.93, "live_sport", True)

    if _SPORT.search(folded) or _KNOWN_CLUB.search(folded):
        kind: MasterIntent = "LIVE_MATCH" if _LIVE.search(folded) else "SPORT_QUERY"
        return MasterIntentResult(kind, 0.9, "sport_signal", True)

    if _SMALL.search(folded):
        return MasterIntentResult("SMALL_TALK", 0.96, "greeting_or_social", False)

    # Short non-sport → general (never invent teams)
    if len(folded.split()) <= 6 and not re.search(r"\bx\b", folded):
        return MasterIntentResult("GENERAL_CHAT", 0.75, "short_general", False)

    return MasterIntentResult("GENERAL_CHAT", 0.55, "default_general", False)


def is_sport_intent(intent: MasterIntent | str) -> bool:
    return str(intent) in SPORT_INTENTS


def hard_clear_sport_context(ctx: dict[str, Any] | None, *, reason: str = "non_sport") -> None:
    """
    Block sport pipeline for THIS turn without wiping session sport memory.
    Non-sport turns must not READ focus/thinking; later SPORT_QUERY may resume.
    """
    if not isinstance(ctx, dict):
        return
    try:
        from src.conversation.conversation_focus import clear_focus_on_boundary

        clear_focus_on_boundary(ctx)
    except Exception:
        ctx.pop("conversation_focus", None)

    for key in (
        "deep_thinking",
        "human_inference",
        "context_recovery",
        "reference_resolution",
        "pending_clarification",
        "response_plan",
        "web_thinking",
        "web_context",
        "user_expectation",
        "knowledge_pack",
        "next_games_hints",
        "ci_pending",
    ):
        ctx.pop(key, None)

    ctx["sport_pipeline_blocked"] = True
    ctx["block_hydrate_legacy"] = True
    ctx["master_intent_clear_reason"] = reason
    logger.warning("[AUDIT] MasterIntent: HARD BLOCK sport pipeline reason=%s", reason)


def sport_pipeline_allowed(ctx: dict[str, Any] | None) -> bool:
    if not isinstance(ctx, dict):
        return True
    if ctx.get("sport_pipeline_blocked"):
        return False
    mi = ctx.get(CTX_KEY) or {}
    if isinstance(mi, dict) and mi.get("allow_sport_pipeline") is False:
        return False
    return True


def apply_master_intent(
    message: str,
    ctx: dict[str, Any] | None,
) -> MasterIntentResult:
    result = classify_master_intent(message)
    if ctx is not None:
        ctx[CTX_KEY] = result.to_dict()
        if not result.allow_sport_pipeline:
            hard_clear_sport_context(ctx, reason=result.intent.lower())
        else:
            # Sport turn: lift prior non-sport hard block
            ctx.pop("sport_pipeline_blocked", None)
            ctx.pop("block_hydrate_legacy", None)
            ctx.pop("master_intent_clear_reason", None)
    logger.warning(
        "[AUDIT] MasterIntent: intent=%s conf=%.2f sport=%s reason=%s",
        result.intent,
        result.confidence,
        result.allow_sport_pipeline,
        result.reason,
    )
    return result
