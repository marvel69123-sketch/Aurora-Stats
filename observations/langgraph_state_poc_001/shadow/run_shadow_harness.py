"""
LANGGRAPH-STATE-POC-001 Phase 2 — runnable shadow harness (no FastAPI).

Runs the critical 3-turn dialogue against maybe_shadow_compare with a
simulated multi-writer ctx, writes shadow_compare.json + contamination notes.

Usage (from repo root):
  .\\.tools\\python312\\python.exe observations\\langgraph_state_poc_001\\shadow\\run_shadow_harness.py

Does NOT set ENABLE_LANGGRAPH_STATE. Enables SHADOW only for the process.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Repo root → artifacts/aurora on sys.path
_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[2]
_AURORA = _REPO / "artifacts" / "aurora"
if str(_AURORA) not in sys.path:
    sys.path.insert(0, str(_AURORA))

os.environ.pop("ENABLE_LANGGRAPH_STATE", None)
os.environ["ENABLE_LANGGRAPH_STATE_SHADOW"] = "1"

from src.conversation.langgraph_state_adapter import (  # noqa: E402
    langgraph_state_enabled,
    langgraph_state_shadow_enabled,
    maybe_shadow_compare,
)


def _ctx_flamengo(episode: str = "ep-flamengo") -> dict:
    return {
        "last_home": "Flamengo",
        "last_away": "Palmeiras",
        "last_match": "Flamengo x Palmeiras",
        "episode_id": episode,
        "last_intent": "fixture_compare",
        "csl": {
            "episode_id": episode,
            "teams": ["Flamengo", "Palmeiras"],
            "fixture": "Flamengo x Palmeiras",
            "topic": "comparison",
            "last_intent": "fixture_compare",
        },
        "sport_referent_frame": {
            "fixture_label": "Flamengo x Palmeiras",
            "home": "Flamengo",
            "away": "Palmeiras",
        },
    }


def _apply_new_to_ctx(ctx: dict, new: dict) -> dict:
    """Simulate a clean writer adopting NEW_STATE (harness only — not production)."""
    fx = new.get("fixture")
    teams = list(new.get("teams") or [])
    ep = new.get("episode") or ctx.get("episode_id")
    out = dict(ctx)
    out["episode_id"] = ep
    out["last_match"] = fx
    out["last_intent"] = new.get("intent") or out.get("last_intent")
    if len(teams) >= 2:
        out["last_home"], out["last_away"] = teams[0], teams[1]
    elif len(teams) == 1:
        out["last_home"] = teams[0]
        out["last_away"] = None
    out["csl"] = {
        "episode_id": ep,
        "teams": teams,
        "fixture": fx,
        "topic": "comparison" if len(teams) >= 2 else "calendar",
        "last_intent": new.get("intent") or "fixture_compare",
    }
    out["sport_referent_frame"] = {
        "fixture_label": fx,
        "home": teams[0] if teams else None,
        "away": teams[1] if len(teams) > 1 else None,
    }
    return out


def main() -> int:
    assert langgraph_state_enabled() is False, "production write flag must stay OFF"
    assert langgraph_state_shadow_enabled() is True

    turns: list[dict] = []
    notes: list[str] = []

    # --- Path A: lagging multi-writer (T2 OLD still Flamengo) ---
    ctx = _ctx_flamengo()
    dialogue = [
        ("Flamengo x Palmeiras", "seed"),
        ("Liverpool x Chelsea", "switch_with_lagging_old"),
        ("Quem está melhor?", "soft_fu_after_clean_adopt"),
    ]

    for i, (msg, label) in enumerate(dialogue, start=1):
        if i == 2:
            # Keep Flamengo in ctx to simulate sticky / lagging writers at T2
            ctx = _ctx_flamengo()
        elif i == 3:
            # After T2 shadow NEW was Liverpool — adopt for clean soft-FU input
            # (what sole-writer would have written; multi-writer may fail this)
            ctx = _apply_new_to_ctx(ctx, turns[-1]["result"]["new"])

        result = maybe_shadow_compare(msg, ctx)
        assert result is not None, f"shadow returned None on turn {i}"
        turns.append({"turn": i, "label": label, "message": msg, "result": result})
        notes.append(
            f"T{i} [{label}] msg={msg!r} old.fx={result['old']['fixture']!r} "
            f"new.fx={result['new']['fixture']!r} locus={result['contamination_locus']!r}"
        )

    # --- Path B: contaminated soft-FU (OLD never left Flamengo) ---
    sticky = maybe_shadow_compare("Quem está melhor?", _ctx_flamengo())
    notes.append(
        "Contaminated soft-FU (OLD still Flamengo after intended Liverpool switch never "
        f"landed in ctx): new.fx={sticky['new']['fixture']!r} locus={sticky['contamination_locus']!r}. "
        "Soft keep preserves contaminated OLD → healing requires correct prior (locus on "
        "switch turn = before_langgraph)."
    )

    t2 = turns[1]["result"]
    t3 = turns[2]["result"]
    primary_locus = t2.get("contamination_locus")
    finding = {
        "critical_scenario": "Flamengo×Palmeiras → Liverpool×Chelsea → Quem está melhor?",
        "primary_contamination_locus": primary_locus,
        "locus_code": {
            "before_langgraph": 1,
            "inside_state_layer": 2,
            "after_state_commit": 3,
        }.get(primary_locus or "", None),
        "explanation": (
            "On T2 (Liverpool×Chelsea) with lagging multi-writer ctx still holding "
            "Flamengo×Palmeiras, OLD is wrong vs the user message while NEW (isolated "
            "LangGraph STS) correctly becomes Liverpool×Chelsea. Contamination locus "
            "is therefore (1) before_langgraph — legacy subject lag / sticky bleed "
            "entering the turn. Inside state layer (2) does not mis-classify this "
            "turn. After state commit (3) is N/A for Phase 2 live ctx (shadow never "
            "writes back). T3 soft FU with correct prior keeps Liverpool."
        ),
        "t2_new_fixture": t2["new"]["fixture"],
        "t3_new_fixture": t3["new"]["fixture"],
        "t3_ok": t3["new"]["fixture"] == "Liverpool x Chelsea"
        and "Flamengo" not in (t3["new"]["teams"] or []),
        "production_write_enabled": langgraph_state_enabled(),
        "shadow_enabled": langgraph_state_shadow_enabled(),
    }

    out = {
        "poc": "LANGGRAPH-STATE-POC-001",
        "phase": 2,
        "mode": "shadow",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "flags": {
            "ENABLE_LANGGRAPH_STATE": "0 (forced unset)",
            "ENABLE_LANGGRAPH_STATE_SHADOW": "1 (harness only)",
        },
        "turns": turns,
        "sticky_soft_fu": sticky,
        "contamination_finding": finding,
        "notes": notes,
    }

    out_path = _HERE / "shadow_compare.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    notes_path = _HERE / "CONTAMINATION_NOTES.md"
    notes_path.write_text(
        "\n".join(
            [
                "# Phase 2 Shadow — Contamination Notes",
                "",
                f"Generated: {out['generated_at']}",
                "",
                "## Critical scenario",
                finding["critical_scenario"],
                "",
                f"**Primary locus:** `{primary_locus}` "
                f"(code {finding['locus_code']} = before LangGraph)",
                "",
                finding["explanation"],
                "",
                "## Turn log",
                *[f"- {n}" for n in notes],
                "",
                "## Flags",
                "- `ENABLE_LANGGRAPH_STATE` default / harness: **OFF**",
                "- `ENABLE_LANGGRAPH_STATE_SHADOW` harness: **ON** (log-only)",
                "",
                f"Artifact: `{out_path.name}`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps({"wrote": str(out_path), "finding": finding}, indent=2))
    return 0 if finding["t3_ok"] and finding["locus_code"] == 1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
