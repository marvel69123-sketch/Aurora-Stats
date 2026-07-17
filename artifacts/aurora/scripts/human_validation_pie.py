"""
HUMAN VALIDATION — Perceived Intelligence Engine
Conversas reais. Sem asserts. Sem mocks.
"""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.disable(logging.WARNING)

_spec = importlib.util.spec_from_file_location(
    "human_validation_p1", ROOT / "scripts" / "human_validation_p1.py"
)
_p1 = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_p1)
aurora_reply = _p1.aurora_reply
run_case = _p1.run_case


def case_with_seeded_analysis() -> None:
    """Caso com fatos reais em sessão (sem inventar ao vivo)."""
    print()
    print("=" * 64)
    print("CASO 2b - mercado conservador COM analise na sessao")
    print("=" * 64)
    ctx: dict = {
        "human_conversation_state": {
            "last_entity": "Fluminense x Bragantino",
            "is_live": True,
            "last_expected_action": "sport_followup",
            "updated_at": __import__("time").time(),
        },
        "last_analysis": {
            "is_live": True,
            "match": {"home": "Fluminense", "away": "Bragantino"},
            "positive_factors": [
                "Pressao ofensiva do Fluminense aumentou nos ultimos 15 minutos",
                "Bragantino cedendo mais finalizacoes de dentro da area",
            ],
            "negative_factors": [
                "Placar ainda aberto — um contra-ataque invalida a leitura",
            ],
            "best_markets": [
                {
                    "market": "Over 1.5 gols",
                    "odds": 1.45,
                    "risk_level": "conservative",
                    "reasoning": "partida ja tem ritmo e ambos chegam com frequencia na area",
                },
                {
                    "market": "Ambas marcam",
                    "odds": 2.10,
                    "risk_level": "medium",
                },
                {
                    "market": "Over 3.5 gols",
                    "odds": 3.80,
                    "risk_level": "aggressive",
                },
            ],
            "confidence": {"label": "moderate", "score": 0.62},
        },
    }
    for i, user in enumerate(
        ["qual mercado mais conservador?", "por que voce acha isso?"],
        1,
    ):
        # Bypass master sport for these follow-ups: feed soft payload then PIE via aurora_reply path
        reply, src = aurora_reply(user, ctx)
        print()
        print(f"-- turno {i} --")
        print(f"Voce:  {user}")
        print(f"Aurora ({src}):")
        print(reply)


def main() -> None:
    print("AURORA — HUMAN VALIDATION PIE")
    print("Inteligencia percebida. Sem inventar dados. Sem mocks de API.")

    run_case(
        "CASO 1 - Fluminense ao vivo (poucos dados)",
        ["Fluminense ao vivo"],
    )
    run_case(
        "CASO 2 - mercado conservador (sem analise previa)",
        [
            "Fluminense ao vivo",
            "qual mercado mais conservador?",
        ],
    )
    case_with_seeded_analysis()
    run_case(
        "CASO 3 - por que voce acha isso? (meta/why)",
        [
            "Fluminense ao vivo",
            "por que voce acha isso?",
        ],
    )
    run_case(
        "CASO 4 - conversa longa (inteligência sustentada)",
        [
            "oi",
            "Fluminense ao vivo",
            "e agora?",
            "ok",
            "qual mercado?",
            "de onde vem os dados?",
            "valeu",
            "continua",
        ],
    )
    run_case(
        "CASO 5 - poucos dados / incerteza",
        [
            "Mirassol ao vivo",
            "qual mercado mais conservador?",
            "por que voce acha isso?",
        ],
    )
    print()
    print("Pergunta final: parece que ela pensou, ou so respondeu?")


if __name__ == "__main__":
    main()
