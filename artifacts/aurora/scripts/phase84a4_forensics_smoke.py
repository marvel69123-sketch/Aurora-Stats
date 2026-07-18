#!/usr/bin/env python3
"""Phase 8.4-A.4 — runtime forensics smoke (instrumentation only)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

MSG = "o que você achou do jogo do fluminense ontem?"
KEYS = [
    "team_opinion_path",
    "match_opinion_import_ok",
    "match_opinion_import_error",
    "match_opinion_renderer",
    "renderer_stage",
    "response_type",
    "response_type_before_finalize",
    "response_type_after_finalize",
    "response_type_before_overwrite",
    "response_type_after_overwrite",
    "overwrite_by",
    "fallback_kind",
    "natural_kind",
    "opinion_time",
    "recent_match",
    "final_summary_prefix",
]


def main() -> int:
    client = TestClient(app)
    r = client.post(
        "/aurora/copilot",
        json={"message": MSG, "debug": True},
    )
    data = r.json()
    ents = data.get("entities") or {}
    summary = str(data.get("executive_summary") or "")
    out = {
        "http": r.status_code,
        "backend_commit": data.get("backend_commit"),
        "intent": data.get("intent"),
        "response_type": ents.get("response_type"),
        "forensics": {k: ents.get(k) for k in KEYS},
        "summary_prefix": summary[:200],
        "has_panorama": "panorama" in summary.lower(),
        "has_leitura_rapida": "leitura rápida" in summary.lower()
        or "leitura rapida" in summary.lower(),
        "all_entity_keys": sorted(ents.keys()),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    dest = ROOT / "observations" / "phase84a4" / "capture.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
