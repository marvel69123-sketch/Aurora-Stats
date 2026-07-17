"""
Conversation Expectation — what the user likely wants next (conservative).
Annotates HCE state; does not replace sport engines.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


_LIVE = re.compile(r"\b(ao\s+vivo|live|placar|minuto)\b", re.I)
_MARKET = re.compile(r"\b(mercado|odd|odds|aposta|stake)\b", re.I)
_ANALYZE = re.compile(r"\b(analisar|analise|avaliar)\b", re.I)


def infer_turn_expectation(message: str) -> dict[str, Any]:
    folded = _fold(message)
    live = bool(_LIVE.search(folded))
    markets = bool(_MARKET.search(folded))
    analyze = bool(_ANALYZE.search(folded))

    hints: list[str] = []
    if live:
        hints = ["placar", "minuto", "estatisticas", "pressao", "mercados"]
    elif markets:
        hints = ["mercados", "risco", "confianca"]
    elif analyze:
        hints = ["leitura", "fatores", "mercados", "confianca"]
    else:
        hints = ["continuidade", "proximo_passo"]

    return {
        "live": live,
        "wants_markets": markets,
        "wants_analyze": analyze,
        "hints": hints,
    }


def soft_followup_reply(
    message: str,
    state: dict[str, Any],
) -> str | None:
    """Handle e agora? / qual mercado? when sport thread exists."""
    folded = _fold(message)
    entity = state.get("last_entity")
    hints = list(state.get("expectation_hints") or [])
    if not entity and state.get("last_topic") != "sport":
        return None

    if re.search(r"\bqual\s+mercado|melhor\s+mercado|que\s+mercado\b", folded):
        subj = entity or "esse jogo"
        return (
            f"Sobre mercados em **{subj}**: eu só indico com a análise aberta. "
            "Se já analisamos, peça *melhor mercado* ou *algo mais conservador*. "
            "Se ainda não, me manda o confronto que eu puxo a leitura."
        )

    if re.search(r"\be\s+agora\??$|\bagora\??$|\be\s+ai\??$", folded):
        if state.get("is_live") or "placar" in hints:
            subj = entity or "o jogo"
            return (
                f"Agora no fio de **{subj}**, o útil é: placar/minuto, pressão e se ainda há valor. "
                "Quer o placar, os mercados, ou uma leitura rápida?"
            )
        subj = entity or "o assunto"
        return (
            f"Agora, no fio de **{subj}**, posso aprofundar a leitura, olhar mercados "
            "ou trocar de jogo. O que você prefere?"
        )

    return None
