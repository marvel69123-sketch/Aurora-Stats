"""Fase 7.5 — Suite humana de naturalidade (variação sem novas engines)."""

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
    print("AURORA — SUITE 7.5 NATURALIDADE")
    print("Mesmo significado, forma diferente. Ownership intacto.")
    run_case(
        "SUITE 7.5 - continuidade com variacao",
        [
            "Fluminense ao vivo",
            "e agora?",
            "continua",
            "sim",
            "por quê?",
        ],
    )
    print()
    print("Pergunta: a resposta parece menos robotica?")


if __name__ == "__main__":
    main()
