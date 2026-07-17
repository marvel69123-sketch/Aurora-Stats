"""
Aurora v4.5.1 — Response Variation Layer.

Reduces repetitive openers/headers in deep / presence replies.
Additive. Fail-open. Does not edit CRL/CIL/State.
"""

from __future__ import annotations

import random
from typing import Any

VARIATION_RECENT_KEY = "response_variation_recent"

_BANNED_FRAGMENTS = (
    "mercado em foco",
    "na lógica atual",
    "na logica atual",
    "faz sentido continuar",
)

FAMILIES: dict[str, list[str]] = {
    "opener_cautious": [
        "Eu teria uma visão cautelosa.",
        "Se eu tivesse que escolher, seria cautelosa aqui.",
        "Minha inclinação hoje é de cautela.",
        "Talvez eu fosse mais cautelosa porque ainda falta margem.",
        "Não é um mercado que me passa muita segurança.",
        "Vejo valor, mas com algumas ressalvas.",
        "Eu entraria só com filtro — e bem consciente do risco.",
    ],
    "opener_lean_pos": [
        "Eu teria uma visão levemente positiva.",
        "Minha inclinação seria levemente positiva.",
        "Vejo um viés positivo — ainda com filtro.",
        "Vejo valor, mas com algumas ressalvas.",
        "Há um caminho interessante, sem euforia.",
        "Eu inclinaria a favor — com stake contida.",
    ],
    "opener_neutral": [
        "Eu ficaria no meio-termo por enquanto.",
        "Ainda não fecho posição forte.",
        "Prefiro esperar mais um sinal antes de cravar.",
    ],
    "opener_opinion_change": [
        "Eu mudaria minha visão caso:",
        "O que me faria mudar de ideia:",
        "Eu abandonaria essa leitura se:",
        "Esses pontos invalidariam minha análise atual:",
        "Eu revisaria tudo se acontecesse o seguinte:",
    ],
    "favor": [
        "O que me favorece:",
        "O ponto que mais pesa para mim:",
        "O que mais me chama atenção:",
        "Pontos a favor:",
        "O que sustenta minha leitura:",
        "O lado positivo que eu enxergo:",
    ],
    "worry": [
        "Meu principal receio seria...",
        "Meu principal receio:",
        "O que me preocupa:",
        "O ponto que mais me incomoda:",
        "O cenário que me deixaria desconfortável seria:",
        "Onde eu teria mais cautela:",
    ],
    "scenario": [
        "Se o jogo seguir por outro caminho:",
        "Cenários que eu acompanho:",
        "O cenário que mais me preocupa — e os vizinhos:",
        "Algo que pode mudar completamente esse jogo é:",
        "Caminhos alternativos do confronto:",
    ],
    "change": [
        "O que poderia mudar minha opinião:",
        "O que me faria mudar de ideia:",
        "O que invalidaria essa análise:",
        "Sinais que me fariam abandonar o mercado:",
    ],
    "alt_safe": [
        "Se eu quisesse reduzir risco:",
        "Se eu fosse mais conservadora:",
        "Caminho mais contido:",
        "Uma leitura mais defensiva seria:",
    ],
    "alt_agg": [
        "Se eu quisesse mais risco:",
        "Uma leitura mais agressiva seria:",
        "Se eu apertasse o acelerador:",
    ],
    "closing_change": [
        "Esses cenários alterariam significativamente minha leitura atual.",
        "Com qualquer um desses sinais, eu revisaria a posição sem apego.",
        "Nesses casos, eu reduziria confiança na hora.",
    ],
}


def pick_variant(family: str, ctx: dict[str, Any] | None = None) -> str:
    opts = list(FAMILIES.get(family) or FAMILIES["opener_neutral"])
    recent = list((ctx or {}).get(VARIATION_RECENT_KEY) or [])
    fresh = [o for o in opts if o not in recent]
    choice = random.choice(fresh or opts)
    if ctx is not None:
        ctx[VARIATION_RECENT_KEY] = ([choice] + recent)[:24]
    return choice


def scrub_banned(text: str) -> str:
    out = text or ""
    replacements = [
        ("mercado em foco", "caminho que estou olhando"),
        ("Mercado em foco", "Caminho que estou olhando"),
        ("na lógica atual", "do jeito que vejo agora"),
        ("na logica atual", "do jeito que vejo agora"),
        ("Na lógica atual", "Do jeito que vejo agora"),
        ("Na logica atual", "Do jeito que vejo agora"),
        ("faz sentido continuar", "ainda faz sentido seguir"),
        ("Faz sentido continuar", "Ainda faz sentido seguir"),
    ]
    for a, b in replacements:
        out = out.replace(a, b)
    return out
