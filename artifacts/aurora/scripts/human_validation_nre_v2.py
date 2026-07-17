"""
HUMAN VALIDATION — Natural Response Engine V2
Conversas reais. Sem asserts. Sem mocks.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.disable(logging.WARNING)

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "human_validation_p1", ROOT / "scripts" / "human_validation_p1.py"
)
_p1 = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_p1)
run_case = _p1.run_case


def main() -> None:
    print("AURORA — HUMAN VALIDATION NRE V2")
    print("Expressao natural. Sem asserts. Sem mocks.")

    run_case(
        "FLUXO 1 - ACKs",
        ["ok", "show", "perfeito", "beleza"],
    )
    run_case(
        "FLUXO 2 - thanks / laugh",
        ["obrigado", "valeu", "kkk"],
    )
    run_case(
        "FLUXO 3 - despedidas",
        ["tchau", "até logo", "boa noite"],
    )
    run_case(
        "FLUXO 4 - 30 sociais",
        [
            "oi",
            "tudo bem?",
            "ok",
            "show",
            "perfeito",
            "beleza",
            "obrigado",
            "valeu",
            "kkk",
            "bom dia",
            "blz",
            "qual seu nome?",
            "quanto é 2+2?",
            "ok",
            "show",
            "boa tarde",
            "entendi",
            "combinado",
            "valeu demais",
            "hey",
            "td bem",
            "perfeito",
            "show",
            "ok",
            "beleza",
            "obrigado",
            "falou",
            "tchau",
            "oi",
            "até logo",
        ],
    )
    run_case(
        "FLUXO 5 - futebol > social > tchau > retorno",
        [
            "Fluminense ao vivo",
            "e agora?",
            "ok",
            "show",
            "boa noite",
            "tchau",
            "oi",
            "Santos x Corinthians",
            "qual mercado?",
            "valeu",
        ],
    )
    print()
    print("Fim — leia se parece pessoa ou sistema.")


if __name__ == "__main__":
    main()
