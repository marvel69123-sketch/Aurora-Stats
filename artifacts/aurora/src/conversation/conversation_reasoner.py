"""
Aurora v4.0 Sprint 1 — Conversation Reasoner Foundation.

Interprets what the user *really* wants given message + conversation state.
Does NOT respond, call APIs, invent markets, or mutate engines.

Pipeline position (additive, fail-open):
  Message → Conversation State → Conversation Reasoner → CI → FollowUp → Router → Engines

Sacred rules:
  - NEVER invent fixtures / opponents / live stats
  - Read-only over conversation_state (does not edit that module's schema writers)
  - Output is an internal plan (`ReasoningResult`), not a user-facing reply
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

logger = logging.getLogger(__name__)

ReasoningType = Literal[
    "FOLLOWUP_MARKET",
    "FOLLOWUP_FIXTURE",
    "COMPARISON",
    "MARKET_REJECTION",
    "PREFERENCE_SIGNAL",
    "EXPLANATION",
    "AMBIGUOUS",
    "CLARIFY",
    "SMALL_TALK",
]

NextAction = Literal[
    "PASS_MARKET_FOLLOWUP",
    "USE_ACTIVE_CONTEXT",
    "COMPARE_HISTORY",
    "SEEK_ALTERNATIVE",
    "PREFER_CONSERVATIVE",
    "PREFER_AGGRESSIVE",
    "PREFER_BETTER",
    "EXPLAIN_LAST",
    "ASK_OPPONENT",
    "ASK_FIXTURE",
    "SMALL_TALK",
    "CONTINUE_PIPELINE",
]

REASONER_CTX_KEY = "last_reasoning"


def _fold(text: str) -> str:
    t = unicodedata.normalize("NFKD", (text or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^\w\sx/-]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


@dataclass
class ReasoningResult:
    """Internal thought — never shown as a final product reply by this module."""

    user_goal: str = ""
    reasoning_type: ReasoningType | str = "AMBIGUOUS"
    topic: str = ""
    comparison_target: str = ""
    requires_context: bool = False
    missing_information: list[str] = field(default_factory=list)
    confidence: float = 0.0
    next_action: NextAction | str = "CONTINUE_PIPELINE"
    # Internal narration for audit / tests ("pensamento")
    thought: str = ""
    signals: list[str] = field(default_factory=list)
    active_fixture: str | None = None
    active_market: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── Pattern banks (interpret only) ─────────────────────────────────────────

_MARKET_FOLLOW = re.compile(
    r"^(?:e\s+)?(?:pra\s+|para\s+|esse\s+)?"
    r"(gols?|escanteios?|corners?|cantos?|cart[oõ]es?|cart[aã]o|cards?|btts|"
    r"ambos\s+marcam|over|under)\s*\??$",
    re.I,
)

_DEIXIS_MARKET = re.compile(
    r"^(?:e\s+esse\??|esse\??|e\s+ai\??|e\s+aí\??)\s*$",
    re.I,
)

_COMPARISON = re.compile(
    r"\b(qual\s+parece\s+melhor|qual\s+dos\s+dois|compare(?:\s+os\s+dois)?|"
    r"comparar|comparado\s+ao|esse\s+ta\s+melhor|melhor\s+q(?:ue)?\s+o\s+outro|"
    r"o\s+anterior)\b",
    re.I,
)

_REJECTION = re.compile(
    r"\b(nao\s+gostei|esse\s+parece\s+ruim|nao\s+me\s+convenceu|"
    r"nao\s+curti|descarta(?:r)?\s+(?:esse|isso))\b",
    re.I,
)

_PREF_CONSERVATIVE = re.compile(
    r"\b(mais\s+conservador|mais\s+seguro|menor\s+risco|algo\s+mais\s+conservador)\b",
    re.I,
)
_PREF_AGGRESSIVE = re.compile(
    r"\b(mais\s+agressivo|algo\s+mais\s+agressivo|maior\s+risco)\b",
    re.I,
)
_PREF_BETTER = re.compile(
    r"\b(tem\s+algo\s+melhor|algo\s+melhor|outra\s+opcao|outra\s+opção|"
    r"vale\s+a\s+pena)\b",
    re.I,
)

_EXPLANATION = re.compile(
    r"\b(por\s+que|porque|porquê|explique|explica|me\s+explica|"
    r"oq\s+acha|o\s+que\s+acha|o\s+q\s+acha)\b",
    re.I,
)

_OPINION = re.compile(
    r"^(?:oq\s+acha|o\s+que\s+acha|o\s+q\s+acha|acha\s+q(?:ue)?)(?:\s+d(?:esse|isso|este)"
    r"(?:\s+jogo)?)?\s*\??$",
    re.I,
)

_SMALL_TALK = re.compile(
    r"^(?:oi|ola|hey|hello|hi|bom\s+dia|boa\s+tarde|boa\s+noite|"
    r"tudo\s+bem|td\s+bem|beleza|blz|"
    r"quem\s+(?:e|eh)\s+(?:voce|a\s+aurora))\s*[!?.]*$",
    re.I,
)

_SINGLE_TEAM = re.compile(
    r"(?:fala\s+d[oe]|analis[ae]\s+(?:o|a)?|o\s+que\s+acha\s+d[oe])\s+"
    r"([A-Za-zÀ-ÿ0-9][A-Za-zÀ-ÿ0-9.\s-]{1,40}?)(?:\s+hoje)?\s*$",
    re.I,
)

_EXPLICIT_FIXTURE = re.compile(
    r"\b([A-Za-zÀ-ÿ0-9][A-Za-zÀ-ÿ0-9.\s-]{1,40}?)\s+(?:x|vs|versus)\s+"
    r"([A-Za-zÀ-ÿ0-9][A-Za-zÀ-ÿ0-9.\s-]{1,40})\b",
    re.I,
)


def _snapshot_state(ctx: dict[str, Any] | None) -> dict[str, Any]:
    """Read-only view of conversation state + legacy keys. Never mutates writers."""
    try:
        from src.conversation.conversation_state import get_state, hydrate_from_legacy

        if ctx is not None:
            # hydrate is additive fill when empty — safe and helps reasoner
            hydrate_from_legacy(ctx)
        state = get_state(ctx)
    except Exception:
        state = {}
        if ctx:
            state = {
                "active_fixture": ctx.get("last_match") or ctx.get("last_fixture"),
                "active_market": None,
                "last_recommendation": ctx.get("last_recommendation"),
                "last_risk_level": None,
                "active_team": None,
                "pending_question": bool(ctx.get("ci_pending")),
                "market_history": [],
                "fixture_history": [],
            }
    return state


def _has_sports_context(state: dict[str, Any], ctx: dict[str, Any] | None) -> bool:
    if state.get("active_fixture") or state.get("active_market"):
        return True
    if state.get("active_team") or state.get("pending_question"):
        return True
    if ctx and (ctx.get("last_match") or ctx.get("last_fixture") or ctx.get("last_home")):
        return True
    return False


def _comparison_target(state: dict[str, Any], ctx: dict[str, Any] | None) -> str:
    f_hist = state.get("fixture_history") or []
    if f_hist and isinstance(f_hist[0], dict) and f_hist[0].get("fixture"):
        return str(f_hist[0]["fixture"])
    if ctx:
        ph, pa = (ctx.get("prev_home") or "").strip(), (ctx.get("prev_away") or "").strip()
        if ph and pa:
            return f"{ph} x {pa}"
        prev = (ctx.get("prev_match") or ctx.get("prev_fixture") or "").strip()
        if prev:
            return prev
    m_hist = state.get("market_history") or []
    if len(m_hist) >= 2 and isinstance(m_hist[1], dict) and m_hist[1].get("market"):
        return str(m_hist[1]["market"])
    return ""


def reason(
    message: str,
    ctx: dict[str, Any] | None = None,
) -> ReasoningResult:
    """
    Infer user goal from message + state. Fail-open: returns AMBIGUOUS on error.
    Does not produce user-facing text as a product reply.
    """
    try:
        return _reason_impl(message, ctx)
    except Exception as exc:
        logger.warning("conversation_reasoner fail-open: %s", exc)
        return ReasoningResult(
            user_goal="unknown",
            reasoning_type="AMBIGUOUS",
            confidence=0.0,
            next_action="CONTINUE_PIPELINE",
            thought=f"Fail-open: reasoner error ({exc}). Pipeline continues unchanged.",
            signals=["fail_open"],
        )


def _reason_impl(message: str, ctx: dict[str, Any] | None) -> ReasoningResult:
    original = (message or "").strip()
    folded = _fold(original)
    state = _snapshot_state(ctx)
    active_fx = state.get("active_fixture")
    active_mkt = state.get("active_market")
    active_team = state.get("active_team")
    pending = bool(state.get("pending_question") or (ctx or {}).get("ci_pending"))
    has_ctx = _has_sports_context(state, ctx)
    rec = state.get("last_recommendation")
    risk = state.get("last_risk_level")
    signals: list[str] = []

    base_kwargs = dict(
        active_fixture=str(active_fx) if active_fx else None,
        active_market=str(active_mkt) if active_mkt else None,
    )

    # 0) Small talk
    if _SMALL_TALK.match(folded):
        return ReasoningResult(
            user_goal="social_greeting_or_identity",
            reasoning_type="SMALL_TALK",
            topic="social",
            requires_context=False,
            confidence=0.95,
            next_action="SMALL_TALK",
            thought=(
                "Mensagem social pura. Não há pedido esportivo implícito. "
                "Próxima ação: small talk (sem tocar engines)."
            ),
            signals=["small_talk_pattern"],
            **base_kwargs,
        )

    # 1) Explicit new fixture A x B → followup fixture / analyze plan
    if _EXPLICIT_FIXTURE.search(folded):
        m = _EXPLICIT_FIXTURE.search(folded)
        assert m is not None
        label = f"{m.group(1).strip()} x {m.group(2).strip()}"
        signals.append("explicit_fixture")
        return ReasoningResult(
            user_goal="analyze_or_switch_fixture",
            reasoning_type="FOLLOWUP_FIXTURE",
            topic="fixture",
            comparison_target=str(active_fx) if active_fx and str(active_fx).lower() != label.lower() else "",
            requires_context=False,
            confidence=0.9,
            next_action="CONTINUE_PIPELINE",
            thought=(
                f"Usuário nomeou um confronto explícito ({label}). "
                + (
                    f"Isso substitui o fixture ativo ({active_fx}). "
                    if active_fx and str(active_fx).lower() != label.lower()
                    else "Sem fixture prévio ou mesmo jogo. "
                )
                + "Próxima ação: seguir pipeline de análise (Resolver/engines)."
            ),
            signals=signals,
            **base_kwargs,
        )

    # 2) Market follow-up ("e gols?", "e escanteios?")
    if _MARKET_FOLLOW.match(folded):
        signals.append("market_follow_pattern")
        if has_ctx and active_fx:
            return ReasoningResult(
                user_goal="switch_or_ask_market_on_active_fixture",
                reasoning_type="FOLLOWUP_MARKET",
                topic="markets",
                requires_context=True,
                confidence=0.92,
                next_action="PASS_MARKET_FOLLOWUP",
                thought=(
                    f"Usuário continua no fixture ativo ({active_fx}). "
                    f"Objetivo: trocar/consultar mercado ({folded}). "
                    + (f"Mercado atual em memória: {active_mkt}. " if active_mkt else "")
                    + "Confiança alta. Próxima ação: pass-through FollowUp com contexto."
                ),
                signals=signals + ["has_active_fixture"],
                **base_kwargs,
            )
        return ReasoningResult(
            user_goal="ask_market_without_fixture",
            reasoning_type="CLARIFY",
            topic="markets",
            requires_context=True,
            missing_information=["active_fixture"],
            confidence=0.75,
            next_action="ASK_FIXTURE",
            thought=(
                f"Pedido de mercado ({folded}) sem fixture ativo. "
                "Falta confronto. Próxima ação: clarify fixture."
            ),
            signals=signals + ["missing_fixture"],
            **base_kwargs,
        )

    # 3) "e esse?" deixis toward active market/fixture
    if _DEIXIS_MARKET.match(folded):
        signals.append("deixis_esse")
        if has_ctx:
            return ReasoningResult(
                user_goal="refer_to_active_item",
                reasoning_type="FOLLOWUP_FIXTURE" if active_fx else "FOLLOWUP_MARKET",
                topic=str(state.get("active_topic") or "fixture"),
                requires_context=True,
                confidence=0.8,
                next_action="USE_ACTIVE_CONTEXT",
                thought=(
                    "Usuário aponta ('e esse?') para o item ativo. "
                    f"Fixture={active_fx!r}, mercado={active_mkt!r}, rec={str(rec)[:80]!r}. "
                    "Próxima ação: reutilizar contexto ativo."
                ),
                signals=signals,
                **base_kwargs,
            )
        return ReasoningResult(
            user_goal="deixis_without_context",
            reasoning_type="CLARIFY",
            topic="",
            requires_context=True,
            missing_information=["active_fixture"],
            confidence=0.7,
            next_action="ASK_FIXTURE",
            thought="Deixis sem contexto. Precisa perguntar qual jogo/mercado.",
            signals=signals + ["missing_context"],
            **base_kwargs,
        )

    # 4) Comparison
    if _COMPARISON.search(folded):
        signals.append("comparison_pattern")
        target = _comparison_target(state, ctx)
        missing: list[str] = []
        if not has_ctx:
            missing.append("active_fixture")
        if not target:
            missing.append("comparison_target")
        conf = 0.88 if (has_ctx and target) else (0.7 if has_ctx else 0.55)
        return ReasoningResult(
            user_goal="compare_options_or_fixtures",
            reasoning_type="COMPARISON",
            topic="comparison",
            comparison_target=target,
            requires_context=True,
            missing_information=missing,
            confidence=conf,
            next_action="COMPARE_HISTORY" if (has_ctx and target) else "ASK_FIXTURE",
            thought=(
                "Usuário está comparando ('qual parece melhor?' / similar). "
                f"Usar fixture_history / market_history / last_recommendation. "
                f"Ativo={active_fx!r}, alvo_comparacao={target!r}, "
                f"rec={str(rec)[:80]!r}, risco={risk!r}. "
                + (
                    "Há material para comparar."
                    if target
                    else "Só um lado claro — pode faltar segundo confronto."
                )
            ),
            signals=signals,
            **base_kwargs,
        )

    # 5) Market rejection
    if _REJECTION.search(folded):
        signals.append("rejection_pattern")
        if has_ctx or active_mkt or rec:
            return ReasoningResult(
                user_goal="reject_previous_recommendation",
                reasoning_type="MARKET_REJECTION",
                topic="markets",
                requires_context=True,
                confidence=0.9,
                next_action="SEEK_ALTERNATIVE",
                thought=(
                    "Usuário rejeitou a recomendação/mercado anterior "
                    f"({active_mkt or rec or 'último item'}). "
                    f"Fixture ativo: {active_fx!r}. "
                    "Próxima ação: buscar alternativa (conservador/agressivo/outro)."
                ),
                signals=signals,
                **base_kwargs,
            )
        return ReasoningResult(
            user_goal="reject_without_context",
            reasoning_type="CLARIFY",
            topic="markets",
            requires_context=True,
            missing_information=["active_market", "last_recommendation"],
            confidence=0.65,
            next_action="ASK_FIXTURE",
            thought="Rejeição sem mercado/fixture em memória. Clarify o que foi rejeitado.",
            signals=signals + ["missing_context"],
            **base_kwargs,
        )

    # 6) Preference signals
    if _PREF_CONSERVATIVE.search(folded):
        return ReasoningResult(
            user_goal="prefer_lower_risk_alternative",
            reasoning_type="PREFERENCE_SIGNAL",
            topic="markets",
            requires_context=True,
            missing_information=[] if has_ctx else ["active_fixture"],
            confidence=0.88 if has_ctx else 0.6,
            next_action="PREFER_CONSERVATIVE",
            thought=(
                "Sinal de preferência: perfil mais conservador. "
                f"Ancorar em active_market={active_mkt!r}, risk={risk!r}, fixture={active_fx!r}."
            ),
            signals=["preference_conservative"],
            **base_kwargs,
        )
    if _PREF_AGGRESSIVE.search(folded):
        return ReasoningResult(
            user_goal="prefer_higher_risk_alternative",
            reasoning_type="PREFERENCE_SIGNAL",
            topic="markets",
            requires_context=True,
            missing_information=[] if has_ctx else ["active_fixture"],
            confidence=0.88 if has_ctx else 0.6,
            next_action="PREFER_AGGRESSIVE",
            thought=(
                "Sinal de preferência: perfil mais agressivo. "
                f"Ancorar em active_market={active_mkt!r}, risk={risk!r}."
            ),
            signals=["preference_aggressive"],
            **base_kwargs,
        )
    if _PREF_BETTER.search(folded):
        # "vale a pena?" is evaluative preference / better-option signal
        return ReasoningResult(
            user_goal="evaluate_or_seek_better_option",
            reasoning_type="PREFERENCE_SIGNAL",
            topic="markets",
            requires_context=True,
            missing_information=[] if has_ctx else ["active_fixture", "active_market"],
            confidence=0.85 if has_ctx else 0.55,
            next_action="PREFER_BETTER" if has_ctx else "ASK_FIXTURE",
            thought=(
                "Usuário pergunta se vale a pena / se há algo melhor. "
                f"Avaliar last_recommendation={str(rec)[:100]!r} no fixture {active_fx!r}. "
                + ("Usar contexto ativo." if has_ctx else "Sem contexto → clarify.")
            ),
            signals=["preference_better_or_worth_it"],
            **base_kwargs,
        )

    # 7) Single-team / pending Flamengo-style clarify chain
    sm = _SINGLE_TEAM.search(folded)
    if sm and not _EXPLICIT_FIXTURE.search(folded):
        team = sm.group(1).strip()
        signals.append("single_team")
        return ReasoningResult(
            user_goal="discuss_team_needs_opponent",
            reasoning_type="CLARIFY",
            topic="fixture",
            requires_context=False,
            missing_information=["opponent"],
            confidence=0.8,
            next_action="ASK_OPPONENT",
            thought=(
                f"Usuário fala de um time ({team}) sem adversário. "
                "Nunca inventar confronto. Próxima ação: pedir oponente."
            ),
            signals=signals,
            active_fixture=str(active_fx) if active_fx else None,
            active_market=str(active_mkt) if active_mkt else None,
        )

    # Pending team + vague opinion ("oq acha desse jogo?")
    if pending and active_team and _EXPLANATION.search(folded):
        return ReasoningResult(
            user_goal="continue_pending_team_thread",
            reasoning_type="CLARIFY",
            topic="fixture",
            requires_context=True,
            missing_information=["opponent"],
            confidence=0.86,
            next_action="ASK_OPPONENT",
            thought=(
                f"Usuário ainda fala do time pendente ({active_team}). "
                "Falta adversário. Manter clarify — não inventar jogo."
            ),
            signals=["pending_team", "opinion_on_incomplete_fixture"],
            **base_kwargs,
        )

    # 8) Explanation / opinion ("oq acha?", "por que?")
    if _OPINION.match(folded) or (
        _EXPLANATION.search(folded) and len(folded.split()) <= 4
    ):
        signals.append("opinion_or_explanation")
        if has_ctx:
            rtype: ReasoningType = (
                "EXPLANATION" if re.search(r"\b(por\s+que|porque|explique)", folded) else "FOLLOWUP_FIXTURE"
            )
            return ReasoningResult(
                user_goal="opinion_or_explanation_on_active_context",
                reasoning_type=rtype,
                topic=str(state.get("active_topic") or "fixture"),
                requires_context=True,
                confidence=0.84,
                next_action="EXPLAIN_LAST" if rtype == "EXPLANATION" else "USE_ACTIVE_CONTEXT",
                thought=(
                    "Pedido aberto de opinião/explicação. Existe contexto ativo: "
                    f"fixture={active_fx!r}, market={active_mkt!r}, rec={str(rec)[:80]!r}. "
                    "Usar contexto — não pedir tudo de novo."
                ),
                signals=signals + ["has_context"],
                **base_kwargs,
            )
        return ReasoningResult(
            user_goal="opinion_without_context",
            reasoning_type="CLARIFY",
            topic="",
            requires_context=True,
            missing_information=["active_fixture"],
            confidence=0.7,
            next_action="ASK_FIXTURE",
            thought=(
                "Pedido de opinião ('oq acha?') sem contexto ativo. "
                "Próxima ação: clarify qual jogo."
            ),
            signals=signals + ["missing_context"],
            **base_kwargs,
        )

    if _EXPLANATION.search(folded):
        return ReasoningResult(
            user_goal="explain_previous_output",
            reasoning_type="EXPLANATION",
            topic=str(state.get("active_topic") or "markets"),
            requires_context=True,
            missing_information=[] if has_ctx else ["active_fixture"],
            confidence=0.82 if has_ctx else 0.55,
            next_action="EXPLAIN_LAST" if has_ctx else "ASK_FIXTURE",
            thought=(
                "Usuário quer explicação ('por que?'). "
                + (
                    f"Explicar com base em {active_mkt or rec or active_fx}."
                    if has_ctx
                    else "Sem contexto — pedir referência."
                )
            ),
            signals=["explanation_pattern"],
            **base_kwargs,
        )

    # 9) Fallback ambiguous
    return ReasoningResult(
        user_goal="unclear",
        reasoning_type="AMBIGUOUS",
        topic=str(state.get("active_topic") or ""),
        requires_context=has_ctx,
        confidence=0.35,
        next_action="USE_ACTIVE_CONTEXT" if has_ctx else "CONTINUE_PIPELINE",
        thought=(
            "Não classifiquei com alta confiança. "
            + (
                f"Há contexto ({active_fx}) — pipeline pode reutilizar."
                if has_ctx
                else "Sem contexto forte — seguir pipeline padrão."
            )
        ),
        signals=["ambiguous_fallback"],
        **base_kwargs,
    )


def attach_reasoning(ctx: dict[str, Any], result: ReasoningResult) -> None:
    """Store last reasoning on session ctx (outside conversation_state blob)."""
    try:
        ctx[REASONER_CTX_KEY] = result.to_dict()
    except Exception as exc:
        logger.warning("attach_reasoning skipped: %s", exc)
