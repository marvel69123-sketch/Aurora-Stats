"""
Memory Intent — salve / lembre / guarde / anote (bankroll & short facts).
Uses existing session ctx user_profile. Does not invent odds.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any

logger = logging.getLogger(__name__)


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


_SAVE = re.compile(
    r"\b(salva|salve|salvar|guarda|guarde|guardar|lembra|lembre|lembrar|"
    r"anota|anote|anotar|grava|grave)\b",
    re.I,
)
_BANKROLL = re.compile(
    r"("
    r"(?:minha\s+)?banca(?:\s+(?:atual|e|eh|é))?\s*(?:de|:)?\s*r?\$?\s*(\d+(?:[.,]\d+)?)"
    r"|"
    r"(\d+(?:[.,]\d+)?)\s*(?:reais|r\$)\b"
    r")",
    re.I,
)
_STAKE_ASK = re.compile(
    r"("
    r"quanto\s+(?:devo|posso)\s+(?:arriscar|apostar)|"
    r"quanto\s+arrisco|"
    r"quanto\s+aposto|"
    r"qual\s+stake|"
    r"quanto\s+coloco|"
    r"gestao\s+de\s+banca"
    r")",
    re.I,
)


def is_memory_intent(message: str) -> bool:
    return bool(_SAVE.search(_fold(message)))


def is_bankroll_declare(message: str) -> bool:
    return bool(_BANKROLL.search(message or ""))


def is_stake_question(message: str) -> bool:
    return bool(_STAKE_ASK.search(_fold(message)))


def _parse_bankroll(message: str) -> float | None:
    m = _BANKROLL.search(message or "")
    if not m:
        return None
    raw = m.group(2) or m.group(3)
    if not raw:
        return None
    try:
        return float(raw.replace(",", "."))
    except Exception:
        return None


def _ensure_profile(ctx: dict[str, Any]) -> dict[str, Any]:
    prof = ctx.get("user_profile")
    if not isinstance(prof, dict):
        prof = {}
        ctx["user_profile"] = prof
    return prof


def handle_memory_or_bankroll(
    message: str,
    ctx: dict[str, Any] | None,
    state: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """
    Returns {text, bankroll, expected_action, kind} or None.
    """
    if ctx is None:
        ctx = {}
    folded = _fold(message)
    state = state or {}

    # Declare bankroll (with or without save verb)
    amount = _parse_bankroll(message)
    if amount is not None and (
        is_bankroll_declare(message) or is_memory_intent(message)
    ):
        prof = _ensure_profile(ctx)
        pending = float(amount)
        if is_memory_intent(message) or re.search(r"\bsalv", folded):
            prof["bankroll"] = pending
            prof["bankroll_currency"] = "BRL"
            ctx["user_profile"] = prof
            return {
                "text": (
                    f"Pronto — guardei sua banca atual em **R$ {pending:.0f}**. "
                    "Quando quiser, pergunte quanto arriscar que eu uso esse valor."
                ),
                "bankroll": pending,
                "expected_action": "bankroll_ready",
                "kind": "memory_bankroll_saved",
            }
        # Declare without explicit save — remember in HCE + soft confirm
        return {
            "text": (
                f"Entendi: banca de **R$ {pending:.0f}**. "
                "Quer que eu salve isso na sessão? (pode responder *sim* ou *salve isso*)"
            ),
            "bankroll": pending,
            "expected_action": "awaiting_bankroll_confirm",
            "kind": "memory_bankroll_pending",
            "pending_bankroll": pending,
        }

    # "salve isso" referring to pending bankroll / last entity
    if is_memory_intent(message):
        pending = state.get("pending_bankroll") or state.get("last_bankroll")
        if pending is None and isinstance(ctx.get("user_profile"), dict):
            # already saved?
            pass
        if pending is not None:
            try:
                val = float(pending)
            except Exception:
                val = None
            if val is not None:
                prof = _ensure_profile(ctx)
                prof["bankroll"] = val
                prof["bankroll_currency"] = "BRL"
                ctx["user_profile"] = prof
                return {
                    "text": f"Salvei: banca **R$ {val:.0f}** nesta sessão.",
                    "bankroll": val,
                    "expected_action": "bankroll_ready",
                    "kind": "memory_bankroll_saved",
                }
        # Generic save without clear referent
        entity = state.get("last_entity")
        if entity:
            return {
                "text": (
                    f"Anotei o fio atual (**{entity}**) na memória curta da conversa. "
                    "Para banca, me diga o valor (ex.: *salve minha banca de 100 reais*)."
                ),
                "expected_action": state.get("last_expected_action"),
                "kind": "memory_topic_noted",
            }
        return {
            "text": (
                "Pode ser — o que exatamente quer que eu salve? "
                "Ex.: *salve minha banca de 100 reais*."
            ),
            "expected_action": "awaiting_memory_save",
            "kind": "memory_clarify",
        }

    # Stake question using saved bankroll
    if is_stake_question(message):
        prof = ctx.get("user_profile") if isinstance(ctx.get("user_profile"), dict) else {}
        bank = prof.get("bankroll") or state.get("last_bankroll")
        if bank:
            try:
                b = float(bank)
            except Exception:
                b = None
            if b and b > 0:
                # Conservative guidance — no invented market edge
                low = max(1.0, round(b * 0.01, 2))
                mid = max(1.0, round(b * 0.02, 2))
                high = max(1.0, round(b * 0.05, 2))
                return {
                    "text": (
                        f"Com banca de **R$ {b:.0f}**, eu trabalharia assim "
                        "(sem forçar um mercado específico):\n\n"
                        f"• Conservador: cerca de **R$ {low:.0f}** (~1%)\n"
                        f"• Padrão: cerca de **R$ {mid:.0f}** (~2%)\n"
                        f"• Teto duro: **R$ {high:.0f}** (5% — não passar disso)\n\n"
                        "Se quiser stake no jogo atual, me diga o confronto que eu amarro na análise."
                    ),
                    "bankroll": b,
                    "expected_action": "bankroll_ready",
                    "kind": "memory_stake_guidance",
                }
        return {
            "text": (
                "Para te dizer quanto arriscar, preciso da sua banca. "
                "Ex.: *minha banca é 100 reais* (depois *salve isso*)."
            ),
            "expected_action": "awaiting_bankroll_confirm",
            "kind": "memory_need_bankroll",
        }

    return None
