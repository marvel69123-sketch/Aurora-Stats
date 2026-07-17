"""
Aurora v4.1 Sprint 2 — Conversational Response Layer (CRL).

Decides HOW to respond (response mode + short copy).
Does NOT recreate Reasoner logic — consumes ctx["last_reasoning"].

Does NOT:
  - call APIs / invent fixtures / regenerate full analysis engines
  - edit FollowUp, Resolver, payloads schemas, or frozen conversation modules

Pipeline:
  Reasoner → CRL → CI → FollowUp → NL → Engines
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

logger = logging.getLogger(__name__)

CRL_CTX_KEY = "last_response_plan"

ResponseMode = Literal[
    "FULL_ANALYSIS",
    "CONVERSATIONAL_REPLY",
    "EXPLANATION_REPLY",
    "COMPARISON_REPLY",
    "ALTERNATIVE_REPLY",
    "QUICK_REPLY",
]


def _fold(text: str) -> str:
    t = unicodedata.normalize("NFKD", (text or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^\w\sx/-]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


@dataclass
class ResponsePlan:
    mode: ResponseMode = "FULL_ANALYSIS"
    should_short_circuit: bool = False
    show_header: bool = True
    reply_text: str | None = None
    reason: str = ""
    used_reasoning_type: str = ""
    used_next_action: str = ""
    signals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_ANALYZE_ASK = re.compile(
    r"\b(analis[ae]r?|o\s+que\s+acha\s+de|como\s+(?:esta|está))\b",
    re.I,
)
_EXPLICIT_FX = re.compile(
    r"\b([A-Za-zÀ-ÿ0-9][A-Za-zÀ-ÿ0-9.\s-]{1,40}?)\s+(?:x|vs|versus)\s+"
    r"([A-Za-zÀ-ÿ0-9][A-Za-zÀ-ÿ0-9.\s-]{1,40})\b",
    re.I,
)


def _get_reasoning(ctx: dict[str, Any] | None) -> dict[str, Any]:
    if not ctx:
        return {}
    raw = ctx.get("last_reasoning")
    return dict(raw) if isinstance(raw, dict) else {}


def _state_view(ctx: dict[str, Any] | None) -> dict[str, Any]:
    try:
        from src.conversation.conversation_state import get_state

        return get_state(ctx)
    except Exception:
        return {}


def decide_response_mode(
    message: str,
    ctx: dict[str, Any] | None,
    reasoning: dict[str, Any] | None = None,
) -> ResponseMode:
    """Map Reasoner output → response mode. Fail-open → FULL_ANALYSIS."""
    reasoning = reasoning if reasoning is not None else _get_reasoning(ctx)
    rtype = str(reasoning.get("reasoning_type") or "")
    action = str(reasoning.get("next_action") or "")
    folded = _fold(message or "")

    # Explicit new analysis request with A x B → full report allowed
    if _EXPLICIT_FX.search(folded) and (
        action == "CONTINUE_PIPELINE"
        or rtype == "FOLLOWUP_FIXTURE"
        or _ANALYZE_ASK.search(folded)
    ):
        # Market-only phrases never full analysis
        if not re.match(
            r"^(?:e\s+)?(?:pra\s+|para\s+)?(gols?|escanteios?|cart)",
            folded,
        ):
            if _ANALYZE_ASK.search(folded) or action == "CONTINUE_PIPELINE":
                return "FULL_ANALYSIS"

    if action == "ASK_OPPONENT" or (
        rtype == "CLARIFY" and "opponent" in (reasoning.get("missing_information") or [])
    ):
        return "CONVERSATIONAL_REPLY"

    if action == "ASK_FIXTURE" or rtype == "CLARIFY":
        return "CONVERSATIONAL_REPLY"

    if action == "COMPARE_HISTORY" or rtype == "COMPARISON":
        return "COMPARISON_REPLY"

    if action == "EXPLAIN_LAST" or rtype == "EXPLANATION":
        return "EXPLANATION_REPLY"

    if action in {
        "SEEK_ALTERNATIVE",
        "PREFER_CONSERVATIVE",
        "PREFER_AGGRESSIVE",
        "PREFER_BETTER",
    } or rtype in {"MARKET_REJECTION", "PREFERENCE_SIGNAL"}:
        return "ALTERNATIVE_REPLY"

    if action in {"PASS_MARKET_FOLLOWUP", "USE_ACTIVE_CONTEXT"} or rtype in {
        "FOLLOWUP_MARKET",
        "FOLLOWUP_FIXTURE",
    }:
        # FOLLOWUP_FIXTURE with explicit analyze already handled above
        if rtype == "FOLLOWUP_FIXTURE" and _EXPLICIT_FX.search(folded) and _ANALYZE_ASK.search(folded):
            return "FULL_ANALYSIS"
        return "CONVERSATIONAL_REPLY"

    if action == "SMALL_TALK" or rtype == "SMALL_TALK":
        return "QUICK_REPLY"

    if rtype == "AMBIGUOUS" and reasoning.get("requires_context"):
        return "QUICK_REPLY"

    return "FULL_ANALYSIS"


def _market_focus_from_message(message: str) -> str | None:
    f = _fold(message)
    if re.search(r"escanteio|corner|canto", f):
        return "escanteios"
    if re.search(r"\bgols?\b|over|under|btts", f):
        return "gols"
    if re.search(r"cart", f):
        return "cartões"
    return None


def _build_conversational_copy(message: str, ctx: dict[str, Any] | None, reasoning: dict[str, Any]) -> str:
    state = _state_view(ctx)
    fx = reasoning.get("active_fixture") or state.get("active_fixture")
    mkt = reasoning.get("active_market") or state.get("active_market")
    rec = state.get("last_recommendation")
    focus = _market_focus_from_message(message) or "esse mercado"

    if str(reasoning.get("next_action")) == "ASK_OPPONENT" or (
        "opponent" in (reasoning.get("missing_information") or [])
    ):
        team = state.get("active_team") or "esse time"
        return (
            f"Na minha leitura, você está falando do {team}. "
            "Me diga o adversário (ex.: Time A x Time B) para eu analisar com segurança — "
            "não vou inventar o confronto."
        )

    if str(reasoning.get("next_action")) == "ASK_FIXTURE":
        return (
            "Me parece que falta o confronto. "
            "Qual jogo você quer que eu leia? (ex.: Botafogo x Santos)"
        )

    if focus == "escanteios":
        body = (
            f"Eu gosto mais de escanteios aqui"
            + (f" em {fx}" if fx else "")
            + ". "
            "Na minha leitura, o volume de pressão costuma abrir espaço para cantos — "
            "eu vejo valor nisso com cautela de linha."
        )
    elif focus == "gols":
        body = (
            f"Em gols"
            + (f" nesse {fx}" if fx else "")
            + ", eu teria uma leitura mais seletiva. "
            "Me parece um jogo em que o ritmo define se o over faz sentido — "
            "eu não forçaria sem olhar o contexto do confronto."
        )
    elif focus == "cartões":
        body = (
            "Em cartões, eu teria cautela. "
            "Na minha leitura, depende muito do estilo de arbitragem e do ritmo do jogo."
        )
    else:
        body = (
            "Na minha leitura, faz sentido continuar nesse confronto"
            + (f" ({fx})" if fx else "")
            + ". "
        )
        if mkt:
            body += f'O mercado em foco continua sendo "{mkt}". '
        if rec:
            body += f"Eu ainda lembro da recomendação: {str(rec)[:100]}."

    return body.strip()


def _build_explanation_copy(ctx: dict[str, Any] | None, reasoning: dict[str, Any]) -> str:
    state = _state_view(ctx)
    fx = reasoning.get("active_fixture") or state.get("active_fixture")
    mkt = reasoning.get("active_market") or state.get("active_market")
    risk = state.get("last_risk_level")
    rec = state.get("last_recommendation")
    bits = ["Porque, na minha leitura, o quadro ainda aponta nessa direção."]
    if mkt:
        bits.append(f'O mercado "{mkt}" me parece o mais coerente com o que vimos.')
    if risk:
        bits.append(f"Eu teria cautela: risco em foco {risk}.")
    if fx:
        bits.append(f"Contexto ativo: {fx}.")
    if rec:
        bits.append(f"Recomendação que estou ancorando: {str(rec)[:120]}.")
    bits.append("Se quiser, aprofunda um mercado vizinho sem eu reabrir o relatório inteiro.")
    return " ".join(bits)


def _build_comparison_copy(ctx: dict[str, Any] | None, reasoning: dict[str, Any]) -> str:
    state = _state_view(ctx)
    fx = reasoning.get("active_fixture") or state.get("active_fixture")
    target = reasoning.get("comparison_target") or ""
    if not target:
        f_hist = state.get("fixture_history") or []
        if f_hist and isinstance(f_hist[0], dict):
            target = str(f_hist[0].get("fixture") or "")
    mkt = reasoning.get("active_market") or state.get("active_market")
    rec = state.get("last_recommendation")

    if fx and target and str(target).lower() != str(fx).lower():
        return (
            f"Comparando o que temos na conversa — sem pedir tudo de novo:\n"
            f"• Agora: {fx}"
            + (f" (mercado: {mkt})" if mkt else "")
            + f"\n• Antes: {target}\n"
            f"Na minha leitura, eu ficaria com o que está mais claro no ativo"
            + (f" — {rec[:80]}" if rec else "")
            + ". Qual dos dois você quer aprofundar?"
        )
    return (
        f"No momento eu só tenho um confronto claro"
        + (f" ({fx})" if fx else "")
        + ". Analise outro jogo e eu comparo os dois com calma."
    )


def _build_alternative_copy(
    message: str,
    ctx: dict[str, Any] | None,
    reasoning: dict[str, Any],
) -> str:
    state = _state_view(ctx)
    fx = reasoning.get("active_fixture") or state.get("active_fixture")
    mkt = reasoning.get("active_market") or state.get("active_market")
    action = str(reasoning.get("next_action") or "")
    folded = _fold(message)

    bias = "better"
    if action == "PREFER_CONSERVATIVE" or "conservador" in folded or "seguro" in folded:
        bias = "conservative"
    elif action == "PREFER_AGGRESSIVE" or "agressivo" in folded:
        bias = "aggressive"
    elif action == "SEEK_ALTERNATIVE" or "nao gostei" in folded or "ruim" in folded:
        bias = "better"

    alts: list[str] = []
    try:
        from src.conversation.state_driven_resolution import suggest_alternatives

        alts = suggest_alternatives(
            bias=bias,
            active_market=str(mkt) if mkt else None,
            last_risk=str(state.get("last_risk_level") or "") or None,
            market_history=list(state.get("market_history") or []),
        )
    except Exception:
        alts = ["um mercado mais conservador", "uma linha diferente", "outro tipo de mercado"]

    lines = ["Entendi."]
    if mkt:
        lines.append(f'"{mkt}" não me convenceu para o seu perfil agora.')
    if fx:
        lines.append(f"Em {fx}, eu olharia outras frentes:")
    else:
        lines.append("Eu olharia outras frentes:")
    for a in alts[:3]:
        lines.append(f"• {a}")
    lines.append("Na minha leitura, isso evita repetir o mesmo relatório.")
    return "\n".join(lines)


def _build_quick_copy(ctx: dict[str, Any] | None, reasoning: dict[str, Any]) -> str:
    state = _state_view(ctx)
    fx = reasoning.get("active_fixture") or state.get("active_fixture")
    if fx:
        return (
            f"Pode ser — eu ainda estou com {fx} em mente. "
            "Quer que eu foque em gols, escanteios ou outra leitura?"
        )
    return "Pode me dizer o confronto ou o que você quer aprofundar?"


def build_reply_for_mode(
    mode: ResponseMode,
    message: str,
    ctx: dict[str, Any] | None,
    reasoning: dict[str, Any] | None = None,
) -> str | None:
    reasoning = reasoning if reasoning is not None else _get_reasoning(ctx)
    if mode == "FULL_ANALYSIS":
        return None
    if mode == "EXPLANATION_REPLY":
        return _build_explanation_copy(ctx, reasoning)
    if mode == "COMPARISON_REPLY":
        return _build_comparison_copy(ctx, reasoning)
    if mode == "ALTERNATIVE_REPLY":
        return _build_alternative_copy(message, ctx, reasoning)
    if mode == "QUICK_REPLY":
        return _build_quick_copy(ctx, reasoning)
    # CONVERSATIONAL_REPLY
    return _build_conversational_copy(message, ctx, reasoning)


def plan_response(
    message: str,
    ctx: dict[str, Any] | None = None,
) -> ResponsePlan:
    """
    Decide HOW to respond from last_reasoning.
    Fail-open: FULL_ANALYSIS pass-through on errors.
    """
    try:
        reasoning = _get_reasoning(ctx)
        mode = decide_response_mode(message, ctx, reasoning)
        show_header = mode == "FULL_ANALYSIS"
        short = mode != "FULL_ANALYSIS"
        reply = build_reply_for_mode(mode, message, ctx, reasoning) if short else None

        # Clarifies / conversational modes must short-circuit to avoid full report
        should_sc = bool(short and reply)

        plan = ResponsePlan(
            mode=mode,
            should_short_circuit=should_sc,
            show_header=show_header,
            reply_text=reply,
            reason=f"mapped_from_{reasoning.get('reasoning_type')}_{reasoning.get('next_action')}",
            used_reasoning_type=str(reasoning.get("reasoning_type") or ""),
            used_next_action=str(reasoning.get("next_action") or ""),
            signals=list(reasoning.get("signals") or []),
        )
        return plan
    except Exception as exc:
        logger.warning("conversation_response_layer fail-open: %s", exc)
        return ResponsePlan(
            mode="FULL_ANALYSIS",
            should_short_circuit=False,
            show_header=True,
            reason=f"fail_open:{exc}",
        )


def attach_response_plan(ctx: dict[str, Any], plan: ResponsePlan) -> None:
    try:
        ctx[CRL_CTX_KEY] = plan.to_dict()
    except Exception as exc:
        logger.warning("attach_response_plan skipped: %s", exc)


def apply_crl_payload(
    plan: ResponsePlan,
    brain: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Build soft conversational payload when CRL short-circuits."""
    if not plan.should_short_circuit or not plan.reply_text:
        return None
    try:
        from src.conversation.message_intelligence import build_conversational_payload

        payload = build_conversational_payload(plan.reply_text, brain)
        meta = dict(payload.get("response_metadata") or {})
        meta.update(
            {
                "mode": "conversational_response_layer",
                "crl_mode": plan.mode,
                "show_header": bool(plan.show_header),
                "source": "conversation.conversation_response_layer",
            }
        )
        payload["response_metadata"] = meta
        ents = dict(payload.get("entities") or {})
        ents.update(
            {
                "conversation_assist": True,
                "crl": True,
                "crl_mode": plan.mode,
                "show_header": bool(plan.show_header),
            }
        )
        payload["entities"] = ents
        return payload
    except Exception as exc:
        logger.warning("apply_crl_payload failed: %s", exc)
        return None
