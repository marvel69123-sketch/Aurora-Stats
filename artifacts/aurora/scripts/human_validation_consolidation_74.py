"""
FASE 7 — Suite Humana de Consolidação (Turn Ownership)
Conversas reais. Sem asserts. Sem mocks. Sem engines novas.
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
run_case = _p1.run_case


def main() -> None:
    print("AURORA — SUITE HUMANA DE CONSOLIDACAO (Fase 7.4)")
    print("ONE TURN = ONE OWNER | pergunta: parece mais humano?")
    print()

    run_case(
        "CENARIO 1 - Continuidade",
        [
            "Fluminense ao vivo",
            "e agora?",
            "por quê?",
            "qual mercado?",
            "continua",
            "sim",
        ],
    )

    run_case(
        "CENARIO 2 - Social",
        [
            "oi",
            "tudo bem?",
            "kkk",
            "ok",
            "valeu",
            "tchau",
        ],
    )

    run_case(
        "CENARIO 3 - Mistura",
        [
            "oi",
            "Fluminense ao vivo",
            "ok",
            "qual mercado?",
            "valeu",
        ],
    )

    print()
    print("=" * 64)
    print("Fim. Criterio: o comportamento parece mais humano?")
    print("=" * 64)


if __name__ == "__main__":
    main()
