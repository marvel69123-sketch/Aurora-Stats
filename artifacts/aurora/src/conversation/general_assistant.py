"""
General Assistant Mode — non-sport replies (small talk, math, system, general).
Never touches markets / entity resolver / sport planner.
"""

from __future__ import annotations

import ast
import logging
import operator
import re
import unicodedata
from typing import Any

logger = logging.getLogger(__name__)

_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


def _safe_eval_math(expr: str) -> float | int | None:
    try:
        tree = ast.parse(expr, mode="eval")
    except Exception:
        return None

    def _eval(node: ast.AST) -> float | int:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](_eval(node.operand))  # type: ignore[operator]
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](_eval(node.left), _eval(node.right))  # type: ignore[operator]
        raise ValueError("unsupported")

    try:
        val = _eval(tree)
        if isinstance(val, float) and val.is_integer():
            return int(val)
        return val
    except Exception:
        return None


def _extract_math_expr(message: str) -> str | None:
    m = re.search(
        r"(\d+(?:[.,]\d+)?\s*[\+\-\*\/x×÷]\s*\d+(?:[.,]\d+)?(?:\s*[\+\-\*\/x×÷]\s*\d+(?:[.,]\d+)?)*)",
        message or "",
    )
    if not m:
        return None
    expr = m.group(1)
    expr = expr.replace("×", "*").replace("÷", "/").replace("x", "*").replace(",", ".")
    expr = re.sub(r"\s+", "", expr)
    return expr


def _payload(text: str, *, intent: str, kind: str) -> dict[str, Any]:
    try:
        from src.brain import get_brain_meta

        brain = get_brain_meta()
    except Exception:
        brain = {}
    return {
        "intent": intent,
        "entities": {
            "general_assistant": True,
            "assistant_kind": kind,
            "has_analysis": False,
            "show_header": False,
            "skip_llm": True,
        },
        "match": None,
        "status": None,
        "is_live": False,
        "minute": None,
        "executive_summary": text,
        "best_markets": [],
        "confidence": {
            "score": 0.0,
            "label": "insufficient",
            "explanation": "Resposta conversacional (fora do pipeline esportivo).",
            "data_sources": ["GeneralAssistant"],
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
            "mode": "general_assistant",
            "source": kind,
            "show_header": False,
        },
    }


def reply_small_talk(message: str) -> str:
    folded = _fold(message)
    if re.search(r"bom\s+dia", folded):
        return "Bom dia! Tudo certo por aqui. Como posso te ajudar?"
    if re.search(r"boa\s+tarde", folded):
        return "Boa tarde! Em que posso ajudar?"
    if re.search(r"boa\s+noite", folded):
        return "Boa noite! Se quiser conversar ou olhar um jogo, estou aqui."
    if re.search(r"tudo\s+bem|td\s+bem|como\s+(?:voce\s+)?(?:esta|vai)", folded):
        return (
            "Tudo bem, obrigada por perguntar! 🙂\n\n"
            "E você, tudo certo? Se quiser, a gente conversa ou olha um jogo juntos."
        )
    if re.search(r"obrigad|valeu|thanks", folded):
        return "Por nada! Quando precisar, é só chamar."
    # Default greeting
    return (
        "Oi! Eu sou a Aurora. 🙂\n\n"
        "Tudo bem por aqui. Pode falar comigo normalmente — "
        "seja um oi, uma dúvida rápida ou um jogo pra analisar."
    )


def reply_system(message: str) -> str:
    folded = _fold(message)
    if re.search(r"seu\s+nome|se\s+chama", folded):
        return (
            "Meu nome é **Aurora**.\n\n"
            "Sou uma assistente focada em futebol e conversa — "
            "posso analisar jogos, falar do momento de um time ou só bater um papo."
        )
    if re.search(r"quem\s+(?:te\s+)?criou", folded):
        return (
            "Fui criada como a Aurora, do ecossistema Aurora Stats — "
            "uma assistente para leitura de jogos e conversa sobre futebol.\n\n"
            "Se quiser, me conta o que você quer fazer agora."
        )
    if re.search(r"quem\s+(?:e|eh|é)\s+(?:voce|a\s+aurora)", folded):
        return (
            "Eu sou a **Aurora** — assistente de futebol e conversa.\n\n"
            "Consigo analisar confrontos, falar do momento de times e "
            "responder perguntas do dia a dia sem enrolação."
        )
    if re.search(r"funcoes|capacidades|o\s+que\s+(?:voce\s+)?(?:faz|pode)|ajuda", folded):
        return (
            "Posso ajudar com:\n\n"
            "• Conversa normal (oi, dúvidas rápidas)\n"
            "• Análise de jogos (ex.: *Analisar Time A x Time B*)\n"
            "• Momento de um time (ex.: *Como está o time X?*)\n"
            "• Agenda/horário quando tiver o confronto\n\n"
            "O que você quer fazer agora?"
        )
    return "Eu sou a Aurora. Em que posso ajudar?"


def reply_math(message: str) -> str:
    expr = _extract_math_expr(message)
    if not expr:
        return "Me manda a conta no formato tipo `2+2` que eu resolvo."
    val = _safe_eval_math(expr)
    if val is None:
        return "Não consegui resolver essa expressão com segurança. Tenta algo como `2+2` ou `10/2`."
    return str(val)


def reply_general(message: str) -> str:
    return (
        "Entendi. Posso te ajudar com isso de forma direta.\n\n"
        "Se for sobre futebol, me diga o time ou o confronto. "
        "Se for outra coisa, pode perguntar normalmente."
    )


def try_general_assistant(
    message: str,
    master_intent: str,
    ctx: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """
    Short-circuit non-sport intents with human replies.
    """
    try:
        intent = (master_intent or "").upper()
        if intent == "SMALL_TALK":
            return _payload(reply_small_talk(message), intent="small_talk", kind="small_talk")
        if intent == "MATH_QUERY":
            return _payload(reply_math(message), intent="general_chat", kind="math")
        if intent == "SYSTEM_QUERY":
            return _payload(reply_system(message), intent="identity", kind="system")
        if intent == "MEMORY_QUERY":
            # Let profile memory handle if possible; soft general otherwise
            return None
        if intent == "GENERAL_CHAT":
            # Very short greetings missed by SMALL_TALK
            folded = _fold(message)
            if re.search(r"^(?:oi|ola|hey|hi)\b", folded):
                return _payload(
                    reply_small_talk(message), intent="small_talk", kind="small_talk"
                )
            return _payload(reply_general(message), intent="general_chat", kind="general")
        return None
    except Exception as exc:
        logger.warning("try_general_assistant fail-open: %s", exc)
        return None
