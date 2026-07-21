"""PARALLEL-HUMAN-AUDIT-001 — validation-only TestClient + entity probes.

Does not modify product code. Writes raw_*.json under this directory.
"""
from __future__ import annotations

import json
import os
import re
import sys
import uuid
from pathlib import Path

OUT = Path(__file__).resolve().parent
AURORA = Path(__file__).resolve().parents[2] / "artifacts" / "aurora"
sys.path.insert(0, str(AURORA))

# Realistic stack defaults (document in REPORT)
BASE_FLAGS = {
    "ENABLE_RESPONSE_SELECTOR": "1",
    "ENABLE_SPORT_INTENTS": "1",
    "ENABLE_CSL": "1",
    "ENABLE_SPORTS_LANGUAGE_LAYER": "1",
}


def _apply_flags(**overrides: str) -> dict[str, str]:
    matrix = dict(BASE_FLAGS)
    matrix.update(
        {
            "ENABLE_SPORT_NLG": "0",
            "ENABLE_TOPIC_BOUNDARY_V2": "0",
            "ENABLE_ENTITY_EDGE": "0",
        }
    )
    matrix.update(overrides)
    for k, v in matrix.items():
        os.environ[k] = v
    return matrix


def _summary(data: dict) -> str:
    if not isinstance(data, dict):
        return str(data)[:1200]
    for key in ("executive_summary", "response", "final_recommendation"):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val
    return ""


def _prefix(text: str, n: int = 280) -> str:
    t = " | ".join(line.strip() for line in (text or "").splitlines() if line.strip())
    return t[:n]


def _ents(data: dict) -> dict:
    e = data.get("entities") if isinstance(data, dict) else None
    return e if isinstance(e, dict) else {}


def _csl(ents: dict) -> dict:
    c = ents.get("csl")
    return c if isinstance(c, dict) else {}


def _extract_turn(mode: str, session: str, turn: int, user: str, data: dict, http: int) -> dict:
    ents = _ents(data)
    csl = _csl(ents)
    summary = _summary(data)
    low = summary.lower()
    return {
        "mode": mode,
        "session": session,
        "turn": turn,
        "user": user,
        "http": http,
        "intent_nl": data.get("intent") if isinstance(data, dict) else None,
        "sport_intent": ents.get("sport_intent"),
        "sport_skill": ents.get("sport_skill") or ents.get("sport_intent_skill"),
        "response_owner": ents.get("response_owner") or ents.get("turn_owner"),
        "response_selector": ents.get("response_selector"),
        "sport_intent_authored": ents.get("sport_intent_authored"),
        "sport_nlg": ents.get("sport_nlg"),
        "sport_nlg_intent": ents.get("sport_nlg_intent"),
        "episode_id": csl.get("episode_id"),
        "csl_fixture": csl.get("fixture"),
        "csl_teams": csl.get("teams"),
        "csl_topic": csl.get("topic"),
        "csl_phase": csl.get("phase"),
        "home": ents.get("home"),
        "away": ents.get("away"),
        "summary": summary[:2500],
        "summary_prefix": _prefix(summary),
        "has_mantendo_foco": "mantendo foco" in low,
        "has_nobet_shell": bool(re.search(r"no-bet\s*:\s*sinais insuficientes", low)),
        "has_fase_recente": "fase recente" in low,
        "has_viabilidade": "viabilidade" in low,
        "has_mando": "mando" in low,
        "mentions_flamengo": "flamengo" in low,
        "mentions_palmeiras": "palmeiras" in low,
        "mentions_liverpool": "liverpool" in low,
        "mentions_chelsea": "chelsea" in low,
        "invented_odds_like": bool(
            re.search(r"\b\d{1,2}[,.]\d{1,2}%\b|\bodds?\s+\d|@\s*\d[,.]\d", low)
        ),
        "has_numeric_pct": bool(re.search(r"\b\d{1,3}\s*%\b", low)),
    }


def _post(client, sid: str, message: str) -> tuple[int, dict]:
    r = client.post(
        "/aurora/copilot",
        json={"message": message, "session_id": sid, "debug": True},
    )
    try:
        data = r.json()
    except Exception:
        data = {"_raw": r.text}
    return r.status_code, data if isinstance(data, dict) else {"_raw": data}


def run_sport_nlg(client) -> tuple[list, list, dict]:
    """Seed fixture then form/bet/home FUs — NLG OFF vs ON."""
    scenarios = [
        ("s1", "Flamengo x Palmeiras", "Quem esta melhor?"),
        ("s2", "Flamengo x Palmeiras", "Vale aposta?"),
        ("s3", "Flamengo x Palmeiras", "E fora de casa?"),
    ]
    off_rows: list = []
    on_rows: list = []

    matrix_off = _apply_flags(ENABLE_SPORT_NLG="0")
    for name, seed, fu in scenarios:
        sid = f"pha-nlg-off-{name}-{uuid.uuid4().hex[:8]}"
        st, d1 = _post(client, sid, seed)
        off_rows.append(_extract_turn("OFF", name, 1, seed, d1, st))
        st, d2 = _post(client, sid, fu)
        off_rows.append(_extract_turn("OFF", name, 2, fu, d2, st))

    matrix_on = _apply_flags(ENABLE_SPORT_NLG="1")
    for name, seed, fu in scenarios:
        sid = f"pha-nlg-on-{name}-{uuid.uuid4().hex[:8]}"
        st, d1 = _post(client, sid, seed)
        on_rows.append(_extract_turn("ON", name, 1, seed, d1, st))
        st, d2 = _post(client, sid, fu)
        on_rows.append(_extract_turn("ON", name, 2, fu, d2, st))

    return off_rows, on_rows, {"off": matrix_off, "on": matrix_on}


def run_topic_boundary(client) -> tuple[list, list, dict]:
    """S1 keep FU; S2 new fixture then FU (bleed check)."""
    off_rows: list = []
    on_rows: list = []

    # --- OFF ---
    matrix_off = _apply_flags(ENABLE_TOPIC_BOUNDARY_V2="0")
    # S1 keep
    sid = f"pha-tb-off-s1-{uuid.uuid4().hex[:8]}"
    st, d1 = _post(client, sid, "Flamengo x Palmeiras")
    off_rows.append(_extract_turn("OFF", "s1_keep", 1, "Flamengo x Palmeiras", d1, st))
    st, d2 = _post(client, sid, "Quem esta melhor?")
    off_rows.append(_extract_turn("OFF", "s1_keep", 2, "Quem esta melhor?", d2, st))

    # S2 switch + FU about continuity
    sid = f"pha-tb-off-s2-{uuid.uuid4().hex[:8]}"
    st, d1 = _post(client, sid, "Flamengo x Palmeiras")
    off_rows.append(_extract_turn("OFF", "s2_switch", 1, "Flamengo x Palmeiras", d1, st))
    st, d2 = _post(client, sid, "Liverpool x Chelsea")
    off_rows.append(_extract_turn("OFF", "s2_switch", 2, "Liverpool x Chelsea", d2, st))
    st, d3 = _post(client, sid, "Quem esta melhor?")
    off_rows.append(_extract_turn("OFF", "s2_switch", 3, "Quem esta melhor?", d3, st))
    st, d4 = _post(client, sid, "E o Flamengo x Palmeiras?")
    off_rows.append(_extract_turn("OFF", "s2_switch", 4, "E o Flamengo x Palmeiras?", d4, st))

    # --- ON ---
    matrix_on = _apply_flags(ENABLE_TOPIC_BOUNDARY_V2="1")
    sid = f"pha-tb-on-s1-{uuid.uuid4().hex[:8]}"
    st, d1 = _post(client, sid, "Flamengo x Palmeiras")
    on_rows.append(_extract_turn("ON", "s1_keep", 1, "Flamengo x Palmeiras", d1, st))
    st, d2 = _post(client, sid, "Quem esta melhor?")
    on_rows.append(_extract_turn("ON", "s1_keep", 2, "Quem esta melhor?", d2, st))

    sid = f"pha-tb-on-s2-{uuid.uuid4().hex[:8]}"
    st, d1 = _post(client, sid, "Flamengo x Palmeiras")
    on_rows.append(_extract_turn("ON", "s2_switch", 1, "Flamengo x Palmeiras", d1, st))
    st, d2 = _post(client, sid, "Liverpool x Chelsea")
    on_rows.append(_extract_turn("ON", "s2_switch", 2, "Liverpool x Chelsea", d2, st))
    st, d3 = _post(client, sid, "Quem esta melhor?")
    on_rows.append(_extract_turn("ON", "s2_switch", 3, "Quem esta melhor?", d3, st))
    st, d4 = _post(client, sid, "E o Flamengo x Palmeiras?")
    on_rows.append(_extract_turn("ON", "s2_switch", 4, "E o Flamengo x Palmeiras?", d4, st))

    return off_rows, on_rows, {"off": matrix_off, "on": matrix_on}


def run_entity_edge() -> dict:
    """Unit probes for normalize/resolve OFF vs ON (no product edits)."""
    from src.core.entity_edge import resolve_edge_entity
    from src.core.entity_resolver import fuzzy_correct_team, normalize_team_name

    probes = [
        {"raw": "Barcelona", "message": None},
        {"raw": "Barcelona SC", "message": None},
        {"raw": "barcelona", "message": "barcelona na laliga contra o real madrid"},
        {"raw": "barcelona", "message": "jogo do barcelona no equador guayaquil liga pro"},
        {"raw": "Real Madrid", "message": None},
        {"raw": "Atletico Madrid", "message": None},
        {"raw": "atletico", "message": "atletico na laliga contra barcelona"},
        {"raw": "atletico", "message": "atletico ou bahia no brasileirao"},
        {"raw": "barca", "message": None},
        {"raw": "real", "message": None},
        {"raw": "atm", "message": None},
        {"raw": "barcelna", "message": None},
        {"raw": "real madrd", "message": None},
        {"raw": "chance", "message": None},
    ]

    def _one(flag: str) -> list:
        os.environ["ENABLE_ENTITY_EDGE"] = flag
        rows = []
        for p in probes:
            raw = p["raw"]
            msg = p["message"]
            edge = resolve_edge_entity(raw, message=msg)
            if msg:
                norm = normalize_team_name(raw, message=msg)
            else:
                norm = normalize_team_name(raw)
            fuzzy_hit, fuzzy_score = fuzzy_correct_team(raw)
            rows.append(
                {
                    "flag": flag,
                    "raw": raw,
                    "message": msg,
                    "normalize": norm,
                    "edge_canonical": edge.canonical,
                    "edge_source": edge.source,
                    "fuzzy_hit": fuzzy_hit,
                    "fuzzy_score": fuzzy_score,
                }
            )
        return rows

    _apply_flags()  # base stack env still set
    off = _one("0")
    on = _one("1")
    return {
        "flag_matrix": {
            "off": {**BASE_FLAGS, "ENABLE_ENTITY_EDGE": "0"},
            "on": {**BASE_FLAGS, "ENABLE_ENTITY_EDGE": "1"},
        },
        "off": off,
        "on": on,
    }


def run_combined_before_after(client) -> tuple[list, list, dict]:
    """Same critical FUs with all three layers OFF vs all ON."""
    scenarios = [
        ("s1", "Flamengo x Palmeiras", "Quem esta melhor?"),
        ("s2", "Flamengo x Palmeiras", "Vale aposta?"),
        ("s3", "Flamengo x Palmeiras", "E fora de casa?"),
        ("s4_switch", "Flamengo x Palmeiras", "Liverpool x Chelsea"),
    ]
    before: list = []
    after: list = []

    matrix_before = _apply_flags(
        ENABLE_SPORT_NLG="0",
        ENABLE_TOPIC_BOUNDARY_V2="0",
        ENABLE_ENTITY_EDGE="0",
    )
    for name, seed, fu in scenarios:
        sid = f"pha-before-{name}-{uuid.uuid4().hex[:8]}"
        st, d1 = _post(client, sid, seed)
        before.append(_extract_turn("BEFORE", name, 1, seed, d1, st))
        st, d2 = _post(client, sid, fu)
        before.append(_extract_turn("BEFORE", name, 2, fu, d2, st))
        if name == "s4_switch":
            st, d3 = _post(client, sid, "Quem esta melhor?")
            before.append(_extract_turn("BEFORE", name, 3, "Quem esta melhor?", d3, st))

    matrix_after = _apply_flags(
        ENABLE_SPORT_NLG="1",
        ENABLE_TOPIC_BOUNDARY_V2="1",
        ENABLE_ENTITY_EDGE="1",
    )
    for name, seed, fu in scenarios:
        sid = f"pha-after-{name}-{uuid.uuid4().hex[:8]}"
        st, d1 = _post(client, sid, seed)
        after.append(_extract_turn("AFTER", name, 1, seed, d1, st))
        st, d2 = _post(client, sid, fu)
        after.append(_extract_turn("AFTER", name, 2, fu, d2, st))
        if name == "s4_switch":
            st, d3 = _post(client, sid, "Quem esta melhor?")
            after.append(_extract_turn("AFTER", name, 3, "Quem esta melhor?", d3, st))

    return before, after, {"before": matrix_before, "after": matrix_after}


def _write(name: str, obj) -> None:
    path = OUT / name
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"WROTE {path}")


def main() -> None:
    os.chdir(AURORA)
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)

    print("=== SPORT-NLG track ===")
    nlg_off, nlg_on, nlg_matrix = run_sport_nlg(client)
    _write("raw_sport_nlg_off.json", {"flag_matrix": nlg_matrix, "turns": nlg_off})
    _write("raw_sport_nlg_on.json", {"flag_matrix": nlg_matrix, "turns": nlg_on})

    print("=== TOPIC-BOUNDARY track ===")
    tb_off, tb_on, tb_matrix = run_topic_boundary(client)
    _write("raw_topic_boundary_off.json", {"flag_matrix": tb_matrix, "turns": tb_off})
    _write("raw_topic_boundary_on.json", {"flag_matrix": tb_matrix, "turns": tb_on})

    print("=== ENTITY-EDGE track ===")
    edge = run_entity_edge()
    _write("raw_entity_edge_off.json", {"flag_matrix": edge["flag_matrix"], "probes": edge["off"]})
    _write("raw_entity_edge_on.json", {"flag_matrix": edge["flag_matrix"], "probes": edge["on"]})

    print("=== COMBINED before/after ===")
    before, after, comb_matrix = run_combined_before_after(client)
    _write("raw_before.json", {"flag_matrix": comb_matrix, "turns": before})
    _write("raw_after.json", {"flag_matrix": comb_matrix, "turns": after})

    meta = {
        "base_flags": BASE_FLAGS,
        "toggled_layers": [
            "ENABLE_SPORT_NLG",
            "ENABLE_TOPIC_BOUNDARY_V2",
            "ENABLE_ENTITY_EDGE",
        ],
        "runtime": "local TestClient · partial data / no API-Football key expected",
        "branch_hint": "feat/aurora-response-selector-001",
    }
    _write("run_meta.json", meta)
    print(f"WROTE observations/parallel_human_audit_001 ({OUT})")


if __name__ == "__main__":
    main()
