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
    ctx: dict[str, Any] | None = None,
) -> str | None:
    """Handle e agora? / qual mercado? when sport thread exists. Form varies (7.5)."""
    folded = _fold(message)
    entity = state.get("last_entity")
    hints = list(state.get("expectation_hints") or [])
    if not entity and state.get("last_topic") != "sport":
        return None

    try:
        from src.conversation.phrase_variation import pick_variant
    except Exception:
        pick_variant = None  # type: ignore[assignment]

    if re.search(r"\bqual\s+mercado|melhor\s+mercado|que\s+mercado\b", folded):
        subj = entity or "esse jogo"
        variants = [
            (
                f"Sobre mercados em **{subj}**: eu só indico com a análise aberta. "
                "Se já analisamos, peça *melhor mercado* ou *algo mais conservador*. "
                "Se ainda não, me manda o confronto que eu puxo a leitura."
            ),
            (
                f"Para falar de mercado no **{subj}**, preciso da análise aberta — "
                "sem isso eu não cravo seleção. Quer que a gente abra o confronto "
                "ou prefere uma opção mais conservadora depois da leitura?"
            ),
            (
                f"Mercado no fio do **{subj}** só com lastro. "
                "Com a análise na mesa eu priorizo; sem ela, evito chute. "
                "Me passa o confronto se quiser seguir."
            ),
        ]
        if pick_variant:
            return pick_variant(ctx, "soft_market", variants)
        return variants[0]

    # Continuity: "por quê?" after a sport thread — stay with HCE, don't restart
    if re.search(
        r"^(?:por\s+que|porque|porquê|por\s+quê)\s*\??$|"
        r"^(?:por\s+que|porque)\s+(?:isso|dessa|dessa\s+leitura|voce\s+acha)",
        folded,
    ):
        subj = entity or "esse fio"
        variants = [
            (
                f"Sobre **{subj}**: eu priorizei o estado atual (placar/minuto e ritmo) "
                "porque, sem a análise aberta com sinais concretos, qualquer mercado seria chute. "
                "Se quiser o *porquê* de uma leitura específica, abre o confronto ou a análise ao vivo."
            ),
            (
                f"A leitura do **{subj}** ficou no estado do jogo porque é o que temos "
                "de concreto agora. Sem fatores da análise, eu não forcejo uma conclusão de mercado."
            ),
            (
                f"Porque no **{subj}** o que ainda sustenta a conversa é o momento da partida — "
                "não um veredito de odds. Com sinais da análise, eu amarro o motivo com mais firmeza."
            ),
        ]
        if pick_variant:
            return pick_variant(ctx, "soft_why", variants)
        return variants[0]

    if re.search(r"\be\s+agora\??$|\bagora\??$|\be\s+ai\??$", folded):
        if state.get("is_live") or "placar" in hints:
            subj = entity or "o jogo"
            variants = [
                (
                    f"O cenário do **{subj}** mudou pouco desde a última fala — "
                    "eu seguiria em placar/minuto e se a pressão se sustenta. "
                    "Quer o placar, os mercados, ou uma leitura rápida?"
                ),
                (
                    f"Neste momento o **{subj}** segue no mesmo recorte: estado atual da partida. "
                    "Prefere placar, mercados ou um resumo curto?"
                ),
                (
                    f"Até aqui, no **{subj}**, o útil continua sendo o ritmo do jogo "
                    "(placar/minuto). Quer que eu foque nisso ou nos mercados?"
                ),
                (
                    f"Por enquanto ainda observamos o **{subj}** pelo que a partida mostra agora. "
                    "Placar, mercados ou leitura rápida — o que você quer?"
                ),
            ]
            if pick_variant:
                return pick_variant(ctx, "soft_now_live", variants)
            return variants[0]
        subj = entity or "o assunto"
        variants = [
            (
                f"Agora, no fio de **{subj}**, posso aprofundar a leitura, olhar mercados "
                "ou trocar de jogo. O que você prefere?"
            ),
            (
                f"Seguindo em **{subj}**: quer que eu aprofunde, fale de mercados "
                "ou a gente mude de assunto?"
            ),
        ]
        if pick_variant:
            return pick_variant(ctx, "soft_now", variants)
        return variants[0]

    return None
