"""
Response Templates 2.0 + dynamic section selection (anti-template feel).
Never invents fixtures. Assistant-tone gaps via confidence rewriter.
"""

from __future__ import annotations

import hashlib
import random
from typing import Any

from src.conversation.knowledge_synthesizer import KnowledgePack
from src.conversation.response_planner import ResponsePlan

# Section id → (emoji, title variants)
_SECTION_LIB: dict[str, list[tuple[str, str]]] = {
    "moment": [
        ("📊", "Momento"),
        ("📊", "Fase atual"),
        ("📡", "Como chega"),
    ],
    "pressure": [
        ("🔥", "Pressão"),
        ("⚠", "O que pesa agora"),
    ],
    "phase": [
        ("📈", "Fase"),
        ("📊", "Leitura da fase"),
    ],
    "market": [
        ("📰", "Mercado"),
        ("🗞️", "O que circula"),
        ("📰", "Notícias e sinais"),
    ],
    "recent": [
        ("📰", "Último sinal"),
        ("🧾", "Recorte recente"),
    ],
    "next": [
        ("📅", "Próximos jogos"),
        ("⏭", "Próximo desafio"),
        ("📅", "Agenda à frente"),
    ],
    "perspective": [
        ("🎯", "Perspectiva"),
        ("🧭", "Para onde olho"),
        ("🎯", "Leitura útil"),
    ],
    "strengths": [
        ("✅", "Pontos positivos"),
        ("📈", "O que aparece bem"),
    ],
    "issues": [
        ("⚠", "Pontos de atenção"),
        ("📉", "Onde trava"),
    ],
    "expect": [
        ("🔮", "Expectativa"),
        ("🎯", "Cenário que acompanho"),
    ],
    "context": [
        ("⚔", "Contexto"),
        ("🎟", "Quadro do jogo"),
    ],
    "tactics": [
        ("🧠", "Tática / duelo"),
        ("📈", "Choque de estilos"),
    ],
    "match_expect": [
        ("🎯", "Expectativa"),
        ("🔮", "Cenário provável"),
    ],
}


def dynamic_section_selection(
    answer_type: str,
    *,
    team: str | None = None,
    home: str | None = None,
    away: str | None = None,
    variant: int | None = None,
) -> list[str]:
    """
    Pick section keys dynamically — not always Momento/Recente/Próximos/Perspectiva.
    """
    seed_src = f"{answer_type}|{team or ''}|{home or ''}|{away or ''}|{variant if variant is not None else ''}"
    if variant is None:
        seed = int(hashlib.md5(seed_src.encode()).hexdigest()[:8], 16)
        variant = seed % 3
    else:
        variant = int(variant) % 3

    if answer_type == "team_moment":
        layouts = [
            ["phase", "strengths", "issues", "expect"],
            ["pressure", "phase", "perspective"],
            ["moment", "issues", "expect"],
        ]
        return layouts[variant]

    if answer_type == "match_analysis":
        layouts = [
            ["context", "tactics", "match_expect"],
            ["context", "strengths", "issues", "match_expect"],
            ["tactics", "context", "match_expect"],
        ]
        return layouts[variant]

    # team_summary / team_talk
    layouts = [
        ["moment", "market", "next"],
        ["recent", "moment", "next", "perspective"],
        ["moment", "next", "perspective"],
        ["market", "next", "perspective"],
    ]
    return layouts[variant % len(layouts)]


def _pick_header(section_id: str, variant: int) -> tuple[str, str]:
    opts = _SECTION_LIB.get(section_id) or [("•", section_id)]
    return opts[variant % len(opts)]


def _body_for(
    section_id: str,
    plan: ResponsePlan,
    pack: KnowledgePack,
) -> str:
    team = plan.team or "esse time"
    home = plan.home or "Time A"
    away = plan.away or "Time B"

    def first(*lists: list[str], fallback: str) -> str:
        for lst in lists:
            if lst:
                return lst[0]
        return fallback

    if section_id in {"moment", "phase"}:
        return first(
            pack.team_moment,
            pack.strengths,
            fallback=(
                f"Com o contexto atual do {team}, priorizo fase e ritmo — "
                f"sem cravar um veredito seco."
            ),
        )
    if section_id == "pressure":
        return first(
            pack.issues,
            pack.team_moment,
            fallback=(
                f"No {team}, a pressão costuma aparecer na regularidade e na "
                f"resposta do elenco quando o plano trava."
            ),
        )
    if section_id in {"market", "recent"}:
        return first(
            pack.recent_results,
            pack.market_news,
            fallback=(
                "Ainda sem um placar recente amarrado aqui; o útil é cruzar "
                "fase e próximo desafio."
            ),
        )
    if section_id == "next":
        return first(
            pack.next_games,
            fallback=(
                f"O próximo desafio do {team} depende do calendário oficial — "
                f"com o adversário na mesa, a leitura fica bem mais afiada."
            ),
        )
    if section_id == "perspective":
        return first(
            pack.perspective,
            fallback=(
                f"Leitura útil: acompanhar o {team} pelo próximo confronto e "
                f"pela estabilidade de 90 minutos."
            ),
        )
    if section_id == "strengths":
        return first(
            pack.strengths,
            fallback=(
                f"Quando o {team} encontra intensidade e ideia de jogo, "
                f"a fase melhora de verdade."
            ),
        )
    if section_id == "issues":
        return first(
            pack.issues,
            fallback=(
                "Atenção típica: oscilação, bolas nas costas e resposta sob pressão."
            ),
        )
    if section_id == "expect":
        return first(
            pack.perspective,
            fallback=(
                f"Expectativa: o {team} precisa de regularidade para mudar o tom. "
                f"Quer olhar o próximo jogo juntos?"
            ),
        )
    if section_id == "context":
        return first(
            pack.team_moment,
            pack.market_news,
            fallback=(
                f"Com o contexto atual de {home} x {away}, a leitura nasce do "
                f"momento de cada lado e do clima da rodada."
            ),
        )
    if section_id == "tactics":
        return first(
            pack.strengths,
            fallback=(
                f"{home}: criação e intensidade. {away}: transição e compactação — "
                f"o duelo costuma decidir quem impõe ritmo."
            ),
        )
    if section_id == "match_expect":
        return first(
            pack.perspective,
            fallback=(
                "Expectativa: os primeiros 20 minutos dizem muito. "
                "Com a fixture oficial, aprofunda-se o cenário de mercados."
            ),
        )
    return first(pack.perspective, fallback=f"Leitura aberta sobre {team}.")


def render_dynamic(plan: ResponsePlan, pack: KnowledgePack, *, variant: int | None = None) -> str:
    sections = dynamic_section_selection(
        plan.answer_type,
        team=plan.team,
        home=plan.home,
        away=plan.away,
        variant=variant,
    )
    if variant is None:
        seed = f"{plan.team}|{plan.answer_type}|{sections}"
        variant = int(hashlib.md5(seed.encode()).hexdigest()[:8], 16) % 3

    if plan.answer_type == "match_analysis":
        title = f"**{plan.home or 'Time A'} x {plan.away or 'Time B'}** — pré-leitura"
    elif plan.answer_type == "team_moment":
        title = f"**{plan.team or 'O time'}** — momento"
    else:
        title_opts = [
            f"**{plan.team or 'O time'}** — leitura rápida",
            f"**{plan.team or 'O time'}** — o que importa agora",
            f"**{plan.team or 'O time'}** — panorama",
        ]
        title = title_opts[variant % len(title_opts)]

    blocks: list[str] = [title, ""]
    for i, sid in enumerate(sections):
        emoji, label = _pick_header(sid, variant + i)
        body = _body_for(sid, plan, pack)
        blocks.append(f"{emoji} **{label}**\n{body}")
        blocks.append("")
    return "\n".join(blocks).strip()


def render_from_plan(plan: ResponsePlan, pack: KnowledgePack) -> str:
    return render_dynamic(plan, pack)


def render_forced_useful(plan: ResponsePlan, *, variant: int | None = None) -> str:
    """Last-resort structured answer — dynamic, never philosophy essay."""
    if variant is None:
        variant = random.randint(0, 2)
    return render_dynamic(plan, KnowledgePack(), variant=variant)
