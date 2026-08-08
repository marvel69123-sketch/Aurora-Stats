"""
Meta Question Handler — data source / confidence / why questions.
Does not invent stats. Speaks about origin of Aurora's reading.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


_META = re.compile(
    r"("
    r"de\s+onde\s+(?:estao|estão|vem|vêm|vem|vieram|vindo)|"
    r"qual\s+(?:e|eh|é)\s+a\s+fonte|"
    r"fonte\s+d(?:esses|esses|os)\s+dados|"
    r"(?:esses|os)\s+dados|"
    r"por\s+que\s+voce\s+acha|"
    r"porque\s+voce\s+acha|"
    r"como\s+voce\s+(?:sabe|chegou|calcul)|"
    r"qual\s+sua\s+confianca|"
    r"isso\s+e\s+da\s+api|"
    r"voce\s+esta\s+inventando|"
    r"baseado\s+em\s+que"
    r")",
    re.I,
)


def is_meta_question(message: str) -> bool:
    return bool(_META.search(_fold(message)))


def reply_meta_question(
    message: str,
    state: dict[str, Any] | None = None,
    ctx: dict[str, Any] | None = None,
) -> str:
    folded = _fold(message)
    entity = (state or {}).get("last_entity")
    live = bool((state or {}).get("is_live"))
    has_analysis = bool(
        (ctx or {}).get("last_analysis") or (ctx or {}).get("last_match")
    )

    if re.search(r"por\s+que\s+voce\s+acha|porque\s+voce\s+acha|baseado\s+em\s+que", folded):
        base = (
            "Eu não “acho” no vazio. Quando tem análise aberta, a leitura vem de "
            "estatísticas da partida, forma recente e sinais de mercado — "
            "sempre com o nível de confiança explícito."
        )
        if entity:
            base += f" No recorte atual, o fio era **{entity}**."
        base += " Se a confiança estiver baixa, eu digo isso em vez de forçar um veredito."
        return base

    if re.search(r"confianca", folded):
        return (
            "A confiança é um score da própria análise: combina qualidade dos dados, "
            "estabilidade do sinal e se o jogo está ao vivo ou pré-jogo. "
            "Não é garantia — é transparência do quanto a leitura está amparada."
        )

    # Default: data provenance
    parts = [
        "Esses dados vêm de fontes esportivas via API (fixtures, placar, estatísticas) "
        "e, quando aplicável, de cache recente da sessão — não invento placar nem odds."
    ]
    if live:
        parts.append("Em modo ao vivo, priorizo o estado atual da partida (minuto/placar) sobre agenda.")
    if has_analysis:
        parts.append("A última análise desta conversa fica na memória curta da sessão para follow-ups.")
    if entity:
        parts.append(f"O assunto que eu estava acompanhando era **{entity}**.")
    parts.append("Se algo estiver sem dado suficiente, eu falo isso em vez de completar com chute.")
    return " ".join(parts)
