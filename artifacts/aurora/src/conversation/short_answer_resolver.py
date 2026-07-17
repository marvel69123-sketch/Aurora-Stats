"""
Short Answer Resolver — map sim/não/ok/perfeito/esse/continua to pending expectation.
Conservative. Fail-open.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


_AFFIRM = re.compile(
    r"^(?:sim+|s+|yes|yep|ok|okay|perfeito|certo|isso|pode|pode\s+ser|"
    r"claro|bora|vamos|show|beleza|blz|combinado|fechou|uhum|ahm)\s*[!?.]*$",
    re.I,
)
_NEGATE = re.compile(
    r"^(?:nao|não|nope|negativo|deixa|deixa\s+pra\s+la|agora\s+nao)\s*[!?.]*$",
    re.I,
)
_CONTINUE = re.compile(
    r"^(?:continua|continue|segue|pode\s+continuar|e\s+agora\??|agora\??|"
    r"e\s+ai\??|proximo|próximo|manda)\s*[!?.]*$",
    re.I,
)
_THAT = re.compile(
    r"^(?:esse|essa|esse\s+jogo|aquela|aquele|aquele\s+jogo|essa\s+ai)\s*[!?.]*$",
    re.I,
)


def is_short_answer(message: str) -> bool:
    folded = _fold(message)
    if not folded or len(folded.split()) > 5:
        return False
    return bool(
        _AFFIRM.match(folded)
        or _NEGATE.match(folded)
        or _CONTINUE.match(folded)
        or _THAT.match(folded)
    )


def classify_short(message: str) -> str | None:
    folded = _fold(message)
    if not folded:
        return None
    if _AFFIRM.match(folded):
        return "affirm"
    if _NEGATE.match(folded):
        return "negate"
    if _CONTINUE.match(folded):
        return "continue"
    if _THAT.match(folded):
        return "that"
    if len(folded.split()) <= 2 and folded in {"sim", "nao", "ok", "perfeito"}:
        return "affirm" if folded != "nao" else "negate"
    return None


def resolve_short_answer(
    message: str,
    state: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Returns {text, expected_action, kind} or None if cannot resolve safely.
    """
    kind = classify_short(message)
    if not kind:
        return None

    expected = str(state.get("last_expected_action") or "")
    pending = str(state.get("pending_question") or state.get("last_question") or "")
    entity = str(state.get("last_entity") or "")
    topic = str(state.get("last_topic") or "")
    hints = list(state.get("expectation_hints") or [])

    # No pending thread → do not invent; let other layers handle
    if not expected and not pending and kind != "continue":
        return None

    # Strict: only when we are actually waiting for a fixture (not leftover "analisar" copy)
    if expected == "awaiting_fixture":
        if kind in {"affirm", "continue", "that"}:
            return {
                "text": (
                    "Perfeito. Me diga o confronto no formato "
                    "*Time A x Time B* (pode ser ao vivo também) que eu analiso."
                ),
                "expected_action": "awaiting_fixture",
                "kind": "short_await_fixture",
                "topic": "analyze_match",
            }
        if kind == "negate":
            return {
                "text": "Tudo bem. Quando quiser analisar, é só mandar o jogo.",
                "expected_action": None,
                "kind": "short_cancel",
                "topic": "social",
                "clear_pending": True,
            }

    if expected == "awaiting_bankroll_confirm":
        if kind in {"affirm", "that"}:
            return {
                "text": "Combinado — confirmo a banca. Se quiser, diga *salve isso* para eu guardar.",
                "expected_action": "awaiting_memory_save",
                "kind": "short_bankroll",
                "topic": "bankroll",
            }
        if kind == "negate":
            return {
                "text": "Ok, não vou guardar a banca. Se mudar de ideia, me fala o valor de novo.",
                "expected_action": None,
                "kind": "short_cancel",
                "topic": "bankroll",
            }

    if expected == "sport_followup" and entity:
        if kind in {"continue", "affirm", "that"}:
            focus = hints[0] if hints else "o que está acontecendo"
            return {
                "text": (
                    f"Seguindo no {entity}: o mais útil agora é {focus}. "
                    f"Quer placar, mercados ou uma leitura rápida?"
                ),
                "expected_action": "sport_followup",
                "kind": "short_sport_continue",
                "topic": "sport",
                "entity": entity,
            }
        if kind == "negate":
            return {
                "text": "Ok — a gente para por aqui nesse jogo. Quer olhar outro?",
                "expected_action": None,
                "kind": "short_cancel",
                "topic": "social",
            }

    if expected == "awaiting_choice" and pending:
        if kind in {"affirm", "that", "continue"}:
            return {
                "text": (
                    "Certo. " + (
                        "Me confirma o que você escolheu em uma frase curta?"
                        if "ou" in pending.lower()
                        else "Pode seguir — me diga o próximo passo."
                    )
                ),
                "expected_action": "awaiting_choice",
                "kind": "short_choice",
                "topic": topic or "general",
            }
        if kind == "negate":
            return {
                "text": "Beleza, cancelado. O que você prefere fazer então?",
                "expected_action": None,
                "kind": "short_cancel",
                "topic": "social",
            }

    # Generic continue with any pending question
    if kind == "continue" and (entity or pending):
        subj = entity or "o que a gente estava falando"
        return {
            "text": f"Continuando sobre {subj} — o que você quer aprofundar?",
            "expected_action": expected or "sport_followup",
            "kind": "short_generic_continue",
            "topic": topic or "general",
            "entity": entity or None,
        }

    if kind == "affirm" and pending:
        return {
            "text": (
                "Perfeito. "
                + (
                    "Me diga o confronto (Time A x Time B)."
                    if expected == "awaiting_fixture"
                    else "Pode seguir — estou acompanhando."
                )
            ),
            "expected_action": expected or "awaiting_user",
            "kind": "short_affirm_pending",
            "topic": topic or "general",
        }

    return None
