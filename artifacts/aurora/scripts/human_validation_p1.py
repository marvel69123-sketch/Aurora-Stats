"""
HUMAN VALIDATION P1 — conversas humanas reais.

Sem asserts. Sem mocks.
Usa Master Intent + General Assistant + HCE reais.
Imprime o diálogo como o usuário leria.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Conversas humanas: silenciar audit noise
logging.disable(logging.WARNING)

from src.conversation.general_assistant import try_general_assistant
from src.conversation.human_conversation_engine import (
    note_hce_after_response,
    try_human_conversation,
)
from src.conversation.human_conversation_state import get_hce_state
from src.conversation.master_intent_router import apply_master_intent
from src.conversation.natural_response_engine import (
    apply_natural_response,
    try_natural_social_payload,
)
from src.conversation.perceived_intelligence_engine import apply_perceived_intelligence


def aurora_reply(message: str, ctx: dict[str, Any]) -> tuple[str, str]:
    """Uma volta real do stack conversacional (sem HTTP / sem mocks)."""
    master = apply_master_intent(message, ctx)
    ga = None
    if not master.allow_sport_pipeline:
        ga = try_general_assistant(message, master.intent, ctx)

    hce = try_human_conversation(
        message,
        ctx,
        master_intent=master.intent,
        existing_payload=ga,
    )

    payload = hce or ga
    src = "none"
    if hce:
        src = f"HCE:{((hce.get('entities') or {}).get('hce_kind') or 'ok')}"
    elif ga:
        src = f"GA:{((ga.get('entities') or {}).get('assistant_kind') or 'ok')}"

    if payload is None:
        nre = try_natural_social_payload(message, ctx)
        if nre:
            payload = nre
            src = f"NRE:{((nre.get('entities') or {}).get('natural_response_v2') or 'social')}"
    elif payload is not None:
        before = str(payload.get("executive_summary") or "")
        payload = apply_natural_response(message, payload, ctx) or payload
        after = str(payload.get("executive_summary") or "")
        nre_tag = (payload.get("entities") or {}).get("natural_response_v2")
        if nre_tag and after != before:
            src = f"{src}+NRE:{nre_tag}"

    # Sport pipeline stub (validation without inventing live numbers)
    if payload is None and master.allow_sport_pipeline:
        st = get_hce_state(ctx)
        entity = st.get("last_entity")
        payload = {
            "intent": "analyze_match",
            "executive_summary": (
                f"Leitura de **{entity}** ao vivo."
                if entity and st.get("is_live")
                else f"Leitura de **{entity}**."
                if entity
                else f"Intent esportivo ({master.intent})."
            ),
            "final_recommendation": "",
            "entities": {"has_analysis": False},
            "match": {"home": entity} if entity else {},
            "is_live": bool(st.get("is_live")),
            "best_markets": [],
            "positive_factors": [],
            "negative_factors": [],
            "confidence": {"label": "insufficient", "score": 0.0},
        }
        src = f"SPORT:{master.intent}"

    if payload:
        before = str(payload.get("executive_summary") or "")
        payload = apply_perceived_intelligence(message, payload, ctx) or payload
        after = str(payload.get("executive_summary") or "")
        if (payload.get("entities") or {}).get("perceived_intelligence") and after != before:
            src = f"{src}+PIE:{(payload.get('entities') or {}).get('pie_ask')}"
        note_hce_after_response(ctx, message, payload)
        text = after.strip() or before.strip()
        return text, src

    text = "Pode falar comigo normalmente — em que posso ajudar?"
    return text, "FALLBACK"


def run_case(title: str, turns: list[str]) -> None:
    print()
    print("=" * 64)
    print(title)
    print("=" * 64)
    ctx: dict[str, Any] = {}
    for i, user in enumerate(turns, 1):
        reply, src = aurora_reply(user, ctx)
        st = get_hce_state(ctx)
        exp = st.get("last_expected_action") or "—"
        ent = st.get("last_entity") or "—"
        print()
        print(f"── turno {i} ──")
        print(f"Você:  {user}")
        print(f"Aurora ({src}):")
        print(reply)
        print(f"  · expected={exp}  entity={ent}")


def main() -> None:
    print("AURORA — HUMAN VALIDATION P1")
    print("Conversas reais. Sem asserts. Sem mocks.")

    run_case(
        "CASO 1 - analisar > sim > mercado > meta",
        [
            "oi",
            "boa noite",
            "perfeito quero analisar um jogo",
            "sim",
            "qual mercado?",
            "de onde vêm os dados?",
        ],
    )

    run_case(
        "CASO 2 - banca > salve > stake",
        [
            "minha banca é 100",
            "salve",
            "quanto arrisco?",
        ],
    )

    run_case(
        "CASO 3 - live > social > e agora?",
        [
            "Fluminense ao vivo",
            "boa noite",
            "e agora?",
        ],
    )

    social = [
        "oi",
        "tudo bem?",
        "bom dia",
        "beleza",
        "e ai",
        "como voce esta?",
        "qual seu nome?",
        "quem te criou?",
        "o que voce faz?",
        "quanto é 2+2?",
        "obrigado",
        "valeu",
        "boa tarde",
        "hey aurora",
        "blz",
        "td bem",
        "ajuda",
        "como voce se chama?",
        "quais suas funcoes?",
        "10/2",
        "boa noite",
        "tchau",
        "oi de novo",
        "tudo certo?",
        "valeu demais",
        "ok",
        "perfeito",
        "show",
        "falou",
        "até logo",
    ]
    run_case("CASO 4 - 30 mensagens sociais", social)

    run_case(
        "CASO 5 - muitas trocas de assunto",
        [
            "oi",
            "Flamengo",
            "quanto é 3+3?",
            "qual seu nome?",
            "perfeito quero analisar um jogo",
            "sim",
            "Fluminense ao vivo",
            "e agora?",
            "minha banca é 200",
            "salve isso",
            "quanto arrisco?",
            "de onde vêm esses dados?",
            "boa noite",
            "continua",
            "Santos x Corinthians",
            "qual mercado?",
            "obrigado",
            "tchau",
            "oi",
            "quero analisar um jogo",
            "não",
            "tudo bem?",
        ],
    )

    print()
    print("=" * 64)
    print("Fim da validação humana P1 — leia os diálogos acima.")
    print("=" * 64)


if __name__ == "__main__":
    main()
