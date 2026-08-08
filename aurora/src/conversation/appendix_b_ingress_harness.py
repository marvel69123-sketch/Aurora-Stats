"""
Mission 016 Phase 3 — Appendix B Path B ingress-order harness (Spec T21 / V4).

Runs named suite IO-S1…IO-S5 against ingress_order_shadow_compare.
Observe-only: never enables production write, Sole Writer, or funnel.

REGRA 23: harness does not mutate production ctx / responses.
"""

from __future__ import annotations

import copy
from typing import Any

from src.conversation.langgraph_state_adapter import ingress_order_shadow_compare
from src.conversation.sport_topic_state import (
    langgraph_state_enabled,
    langgraph_state_shadow_enabled,
)

SUITE_NAME = "appendix_b_path_b_mission016_phase3"
MIN_N = 30
LOCUS2_MAX_RATE = 0.05

# Switch pairs used to expand N≥30 while preserving golden sticky semantics.
_SWITCH_PAIRS: list[tuple[str, str, str, list[str]]] = [
    ("Flamengo", "Palmeiras", "Flamengo x Palmeiras", ["Flamengo", "Palmeiras"]),
    ("Liverpool", "Chelsea", "Liverpool x Chelsea", ["Liverpool", "Chelsea"]),
    ("Arsenal", "Tottenham", "Arsenal x Tottenham", ["Arsenal", "Tottenham"]),
    ("Barcelona", "Real Madrid", "Barcelona x Real Madrid", ["Barcelona", "Real Madrid"]),
    ("Bayern", "Dortmund", "Bayern x Dortmund", ["Bayern", "Dortmund"]),
    ("Milan", "Juventus", "Milan x Juventus", ["Milan", "Juventus"]),
    ("PSG", "Lyon", "PSG x Lyon", ["PSG", "Lyon"]),
    ("Benfica", "Porto", "Benfica x Porto", ["Benfica", "Porto"]),
    ("Ajax", "Feyenoord", "Ajax x Feyenoord", ["Ajax", "Feyenoord"]),
    ("City", "United", "City x United", ["City", "United"]),
]


def _ctx_for(home: str, away: str, fixture: str, episode: str) -> dict[str, Any]:
    return {
        "last_home": home,
        "last_away": away,
        "last_match": fixture,
        "episode_id": episode,
        "last_intent": "fixture_compare",
        "subject_generation": 1,
        "csl": {
            "episode_id": episode,
            "teams": [home, away],
            "fixture": fixture,
            "topic": "comparison",
            "last_intent": "fixture_compare",
        },
        "sport_referent_frame": {
            "fixture_label": fixture,
            "home": home,
            "away": away,
        },
    }


def _build_suite_turns() -> list[dict[str, Any]]:
    """
    Named Path B turns: §9.3 sticky + CONTAMINATION_NOTES switches + Inter partial
    + expansions to satisfy IO-S1 N≥30.
    """
    turns: list[dict[str, Any]] = []

    # --- Golden sticky §9.3 (Flamengo → Liverpool lag → soft FU clean) ---
    turns.append(
        {
            "label": "golden_t1_seed",
            "message": "Flamengo x Palmeiras",
            "ctx": {},
            "sll_clubs": ["Flamengo", "Palmeiras"],
            "expected_teams": ["Flamengo", "Palmeiras"],
            "kind": "switch",
        }
    )
    turns.append(
        {
            "label": "golden_t2_switch_lagging_old",
            "message": "Liverpool x Chelsea",
            "ctx": _ctx_for("Flamengo", "Palmeiras", "Flamengo x Palmeiras", "ep-flamengo"),
            "sll_clubs": ["Liverpool", "Chelsea"],
            "expected_teams": ["Liverpool", "Chelsea"],
            "kind": "switch",
        }
    )
    turns.append(
        {
            "label": "golden_t3_soft_fu_clean",
            "message": "Quem está melhor?",
            "ctx": _ctx_for("Liverpool", "Chelsea", "Liverpool x Chelsea", "ep-liverpool"),
            "sll_clubs": [],
            "expected_teams": [],  # soft FU: no ingress expected switch
            "kind": "soft_fu",
        }
    )

    # --- CONTAMINATION_NOTES style golden switch turns (lagging OLD) ---
    for i, (h, a, fx, clubs) in enumerate(_SWITCH_PAIRS[1:6]):
        prior = _SWITCH_PAIRS[i]
        turns.append(
            {
                "label": f"contam_switch_{h.lower()}",
                "message": fx,
                "ctx": _ctx_for(prior[0], prior[1], prior[2], f"ep-prior-{i}"),
                "sll_clubs": clubs,
                "expected_teams": clubs,
                "kind": "switch",
            }
        )

    # --- Inter partial (Plan critical pack) ---
    turns.append(
        {
            "label": "inter_partial",
            "message": "Inter joga hoje?",
            "ctx": _ctx_for("Flamengo", "Palmeiras", "Flamengo x Palmeiras", "ep-flamengo-inter"),
            "sll_clubs": ["Inter"],
            "expected_teams": ["Inter"],
            "kind": "switch",
        }
    )

    # --- Soft FU clean after each switch pair (no contaminated prior) ---
    for h, a, fx, _clubs in _SWITCH_PAIRS:
        turns.append(
            {
                "label": f"soft_fu_clean_{h.lower()}",
                "message": "Quem está melhor?",
                "ctx": _ctx_for(h, a, fx, f"ep-soft-{h.lower()}"),
                "sll_clubs": [],
                "expected_teams": [],
                "kind": "soft_fu",
            }
        )

    # --- Expand seeds / switches until N ≥ 30 ---
    idx = 0
    while len(turns) < MIN_N:
        prior = _SWITCH_PAIRS[idx % len(_SWITCH_PAIRS)]
        nxt = _SWITCH_PAIRS[(idx + 1) % len(_SWITCH_PAIRS)]
        turns.append(
            {
                "label": f"expand_switch_{idx}",
                "message": nxt[2],
                "ctx": _ctx_for(prior[0], prior[1], prior[2], f"ep-exp-{idx}"),
                "sll_clubs": nxt[3],
                "expected_teams": nxt[3],
                "kind": "switch",
            }
        )
        idx += 1

    return turns


def grade_appendix_b(
    results: list[dict[str, Any]],
    *,
    suite_name: str = SUITE_NAME,
) -> dict[str, Any]:
    """
    Grade IO-S1…IO-S5 from Path B result list.

    IO-S5 is a reporting rule (do not use locus-1 as sole exit) — always Pass
    when IO-S1…IO-S4 are cited as primary criteria.
    """
    n = len(results)
    locus2 = sum(1 for r in results if r.get("contamination_locus") == "inside_state_layer")
    locus2_rate = (locus2 / n) if n else 1.0

    switch_mismatch = 0
    soft_contam = 0
    for r in results:
        classes = list(r.get("divergence_classes") or [])
        if r.get("is_switch_turn") and "subject_teams_mismatch" in classes:
            switch_mismatch += 1
        if "soft_fu_on_contaminated_prior" in classes:
            soft_contam += 1

    io_s1 = n >= MIN_N and suite_name == SUITE_NAME
    io_s2 = locus2_rate <= LOCUS2_MAX_RATE
    io_s3 = switch_mismatch == 0
    io_s4 = soft_contam == 0
    io_s5 = True  # graded via IO-S1…IO-S4 citation; locus-1 not used as exit

    criteria = {
        "IO-S1": {"pass": io_s1, "n": n, "min_n": MIN_N, "suite": suite_name},
        "IO-S2": {
            "pass": io_s2,
            "locus2_count": locus2,
            "locus2_rate": round(locus2_rate, 4),
            "max_rate": LOCUS2_MAX_RATE,
        },
        "IO-S3": {"pass": io_s3, "subject_teams_mismatch_on_switch": switch_mismatch},
        "IO-S4": {"pass": io_s4, "soft_fu_on_contaminated_prior": soft_contam},
        "IO-S5": {
            "pass": io_s5,
            "note": "P2 exit cites IO-S1…IO-S4; locus-1 legacy-lag is monitoring only",
        },
    }
    overall = all(c["pass"] for c in criteria.values())
    return {
        "suite_name": suite_name,
        "n": n,
        "overall_pass": overall,
        "criteria": criteria,
        "production_write_enabled": langgraph_state_enabled(),
        "shadow_enabled": langgraph_state_shadow_enabled(),
        "locus1_monitoring_only": True,
    }


def run_appendix_b_harness(*, force: bool = True) -> dict[str, Any]:
    """
    Execute Path B suite and grade Appendix B.

    force=True allows in-process grading without env shadow flag (tests).
    Live observe path still requires ENABLE_LANGGRAPH_STATE_SHADOW.
    Never enables ENABLE_LANGGRAPH_STATE.
    """
    assert not langgraph_state_enabled(), "REGRA 23 / Spec: production write must stay OFF"

    turns = _build_suite_turns()
    results: list[dict[str, Any]] = []
    raw_turns: list[dict[str, Any]] = []

    for spec in turns:
        ctx_before = copy.deepcopy(spec["ctx"])
        result = ingress_order_shadow_compare(
            spec["message"],
            spec["ctx"],
            sll_clubs=spec.get("sll_clubs"),
            expected_teams=spec.get("expected_teams"),
            force=force,
        )
        # Zero user impact: ctx unchanged
        assert spec["ctx"] == ctx_before, "Path B mutated live ctx — REGRA 23 violation"
        assert result is not None, f"Path B returned None for {spec['label']}"
        assert result.get("shadow_only") is True
        assert result.get("production_write_enabled") is False
        assert result.get("appendix_b_ready") is True
        results.append(result)
        raw_turns.append({"spec": {k: v for k, v in spec.items() if k != "ctx"}, "result": result})

    grade = grade_appendix_b(results)
    return {
        "harness": SUITE_NAME,
        "mission": "016",
        "phase": "3_shadow",
        "turns": raw_turns,
        "grade": grade,
        "flags": {
            "ENABLE_LANGGRAPH_STATE": langgraph_state_enabled(),
            "ENABLE_LANGGRAPH_STATE_SHADOW": langgraph_state_shadow_enabled(),
        },
    }
