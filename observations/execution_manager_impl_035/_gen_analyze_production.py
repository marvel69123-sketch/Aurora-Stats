"""One-shot generator: extract analyze parity body from Router into EM module."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
router = ROOT / "artifacts" / "aurora" / "src" / "routers" / "copilot_unified_router.py"
out = (
    ROOT
    / "artifacts"
    / "aurora"
    / "src"
    / "execution_manager"
    / "pipelines"
    / "analyze_production.py"
)

lines = router.read_text(encoding="utf-8").splitlines()
helpers_src = "\n".join(lines[402:549])  # _conf_label .. _compose_final
# After fetch: ictx = scan_analyze_data ... through end of result dict (before match_card try)
core = lines[599:1091]

header = '''"""
Analyze production assembly — Phase 4 Stage 3 (E3).

Parity body for EM `run_analyze` after A1 soft fetch. Consume-only Frozen engines.
No attach_match_card. No CM writes. No begin_request.
Generated from SoT `_run_analyze` (helpers + post-fetch body); match-card stripped.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


'''

fn_head = '''
def build_analyze_payload_from_data(
    data: dict[str, Any],
    home: str,
    away: str,
    *,
    prefer_live: bool = False,
) -> dict[str, Any]:
    """
    SoT-equivalent of `_run_analyze` after soft fetch, without match-card attach.

    Includes defense-in-depth early integrity HARD-ABORT (same as SoT). EM A2
    normally gates first; this keeps parity if called with raw fetch data.
    """
    from src.brain import get_brain_meta, get_config, get_methodology_config
    from src.core import (
        confidence_engine,
        learning_engine,
        market_engine,
        methodology_engine,
        methodology_v1,
    )
    from src.core.decision_center import run as _dc_run
    from src.core.fixture_status import fixture_is_live
    from src.core.inference_context import scan_analyze_data
    from src.core.intelligence_engine import generate as _intel
    from src.core.knowledge_engine import consult as _kc
    from src.learning_db import get_learning_stats
    from src.memory_db import recall_context as _mem_recall

'''

# Router body already uses 4-space indent (inside `_run_analyze`) — reuse as-is.
core_text = "\n".join(core)
content = header + helpers_src + "\n\n" + fn_head + core_text + "\n    return result\n"
out.write_text(content, encoding="utf-8")
compile(content, str(out), "exec")
print("wrote", out.relative_to(ROOT), "bytes", out.stat().st_size)
