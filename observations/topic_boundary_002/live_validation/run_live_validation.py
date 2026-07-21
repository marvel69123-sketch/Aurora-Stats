"""TOPIC-BOUNDARY-002 live validation — full copilot/unified router (TestClient).

ENABLE_TOPIC_BOUNDARY_V2=1 for this session only. Does not change code defaults.
"""
from __future__ import annotations

import json
import os
import re
import sys
import uuid
from pathlib import Path

OUT = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[3]
AURORA = REPO / "artifacts" / "aurora"
sys.path.insert(0, str(AURORA))

BASE_FLAGS = {
    "ENABLE_RESPONSE_SELECTOR": "1",
    "ENABLE_SPORT_INTENTS": "1",
    "ENABLE_CSL": "1",
    "ENABLE_SPORTS_LANGUAGE_LAYER": "1",
    "ENABLE_SPORT_NLG": "0",
    "ENABLE_ENTITY_EDGE": "0",
    "ENABLE_TOPIC_BOUNDARY_V2": "1",
}


def _apply_flags() -> dict[str, str]:
    for k, v in BASE_FLAGS.items():
        os.environ[k] = v
    return dict(BASE_FLAGS)


def _summary(data: dict) -> str:
    if not isinstance(data, dict):
        return str(data)[:1200]
    for key in ("executive_summary", "response", "final_recommendation"):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val
    return ""


def _ents(data: dict) -> dict:
    e = data.get("entities") if isinstance(data, dict) else None
    return e if isinstance(e, dict) else {}


def _csl(ents: dict) -> dict:
    c = ents.get("csl")
    return c if isinstance(c, dict) else {}


def _blob(data: dict) -> str:
    """Full user-visible + entity text for contamination checks."""
    parts = [_summary(data)]
    ents = _ents(data)
    for k in ("home", "away", "match", "fixture"):
        v = ents.get(k)
        if isinstance(v, str):
            parts.append(v)
    csl = _csl(ents)
    for k in ("fixture", "topic"):
        v = csl.get(k)
        if isinstance(v, str):
            parts.append(v)
    teams = csl.get("teams")
    if isinstance(teams, list):
        parts.extend(str(t) for t in teams)
    try:
        parts.append(json.dumps(ents, ensure_ascii=False, default=str))
    except Exception:
        pass
    return " ".join(parts).lower()


def _extract(scenario: str, turn: int, user: str, data: dict, http: int) -> dict:
    ents = _ents(data)
    csl = _csl(ents)
    summary = _summary(data)
    blob = _blob(data)
    tb = ents.get("topic_boundary_v2") if isinstance(ents.get("topic_boundary_v2"), dict) else {}
    return {
        "scenario": scenario,
        "turn": turn,
        "user": user,
        "http": http,
        "intent": data.get("intent") if isinstance(data, dict) else None,
        "sport_intent": ents.get("sport_intent"),
        "episode_id": csl.get("episode_id"),
        "csl_fixture": csl.get("fixture"),
        "csl_teams": csl.get("teams"),
        "csl_topic": csl.get("topic"),
        "csl_phase": csl.get("phase"),
        "home": ents.get("home"),
        "away": ents.get("away"),
        "topic_boundary_v2": tb,
        "episode_boundary": ents.get("episode_boundary") or tb.get("is_boundary"),
        "summary": summary[:3000],
        "summary_prefix": summary[:280].replace("\n", " | "),
        "has_mantendo_foco_flamengo": "mantendo foco" in blob and "flamengo" in blob,
        "mentions_flamengo": "flamengo" in blob,
        "mentions_palmeiras": "palmeiras" in blob,
        "mentions_liverpool": "liverpool" in blob,
        "mentions_chelsea": "chelsea" in blob,
        "mentions_inter": bool(re.search(r"\binter\b", blob)),
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


def judge_s1(turns: list[dict]) -> dict:
    t1, t2 = turns[0], turns[1]
    ep_rot = bool(t1.get("episode_id") and t2.get("episode_id") and t1["episode_id"] != t2["episode_id"])
    fx2 = (t2.get("csl_fixture") or "").lower()
    teams2 = " ".join(str(x) for x in (t2.get("csl_teams") or [])).lower()
    subject_ok = ("liverpool" in fx2 or "liverpool" in teams2) and ("chelsea" in fx2 or "chelsea" in teams2)
    no_flam = not t2.get("mentions_flamengo") and not t2.get("mentions_palmeiras")
    no_mantendo = not t2.get("has_mantendo_foco_flamengo")
    old_fx = "flamengo" not in fx2 and "palmeiras" not in fx2
    passed = ep_rot and subject_ok and no_flam and no_mantendo and old_fx
    return {
        "pass": passed,
        "episode_rotated": ep_rot,
        "subject_liverpool_chelsea": subject_ok,
        "no_flamengo_contamination": no_flam,
        "no_mantendo_foco_flamengo": no_mantendo,
        "csl_fixture_clean": old_fx,
        "evidence": {
            "ep1": t1.get("episode_id"),
            "ep2": t2.get("episode_id"),
            "csl_fixture_t2": t2.get("csl_fixture"),
            "csl_teams_t2": t2.get("csl_teams"),
            "flamengo_t2": t2.get("mentions_flamengo"),
            "prefix_t2": t2.get("summary_prefix"),
        },
    }


def judge_s2(turns: list[dict]) -> dict:
    t1, t2, t3 = turns[0], turns[1], turns[2]
    ep_rot = bool(t1.get("episode_id") and t2.get("episode_id") and t1["episode_id"] != t2["episode_id"])
    same_ep = t2.get("episode_id") and t3.get("episode_id") and t2["episode_id"] == t3["episode_id"]
    fx3 = (t3.get("csl_fixture") or "").lower()
    teams3 = " ".join(str(x) for x in (t3.get("csl_teams") or [])).lower()
    subject_ok = ("liverpool" in fx3 or "liverpool" in teams3 or t3.get("mentions_liverpool")) and (
        "chelsea" in fx3 or "chelsea" in teams3 or t3.get("mentions_chelsea")
    )
    no_flam_t3 = not t3.get("mentions_flamengo") and not t3.get("mentions_palmeiras")
    no_mantendo = not t3.get("has_mantendo_foco_flamengo") and not t2.get("has_mantendo_foco_flamengo")
    passed = ep_rot and same_ep and subject_ok and no_flam_t3 and no_mantendo
    return {
        "pass": passed,
        "episode_rotated_t1_t2": ep_rot,
        "t3_same_liverpool_episode": same_ep,
        "t3_about_liverpool_chelsea": subject_ok,
        "no_flamengo_on_t3": no_flam_t3,
        "no_mantendo_foco": no_mantendo,
        "evidence": {
            "ep1": t1.get("episode_id"),
            "ep2": t2.get("episode_id"),
            "ep3": t3.get("episode_id"),
            "csl_fixture_t3": t3.get("csl_fixture"),
            "csl_teams_t3": t3.get("csl_teams"),
            "flamengo_t3": t3.get("mentions_flamengo"),
            "prefix_t3": t3.get("summary_prefix"),
        },
    }


def judge_s3(turns: list[dict]) -> dict:
    t1, t2 = turns[0], turns[1]
    ep_changed = bool(t1.get("episode_id") and t2.get("episode_id") and t1["episode_id"] != t2["episode_id"])
    fx2 = (t2.get("csl_fixture") or "").lower()
    teams2 = " ".join(str(x) for x in (t2.get("csl_teams") or [])).lower()
    inter_subject = "inter" in fx2 or "inter" in teams2 or bool(t2.get("mentions_inter"))
    no_flam_reuse = "flamengo" not in fx2 and "palmeiras" not in fx2
    no_mantendo = not t2.get("has_mantendo_foco_flamengo")
    passed = inter_subject and no_flam_reuse and no_mantendo
    return {
        "pass": passed,
        "episode_rotated_or_partial": ep_changed,
        "inter_subject": inter_subject,
        "no_flamengo_fixture_reuse": no_flam_reuse,
        "no_mantendo_foco_flamengo": no_mantendo,
        "evidence": {
            "ep1": t1.get("episode_id"),
            "ep2": t2.get("episode_id"),
            "csl_fixture_t2": t2.get("csl_fixture"),
            "csl_teams_t2": t2.get("csl_teams"),
            "flamengo_t2": t2.get("mentions_flamengo"),
            "boundary_t2": t2.get("topic_boundary_v2"),
            "prefix_t2": t2.get("summary_prefix"),
        },
    }


def main() -> None:
    os.chdir(AURORA)
    matrix = _apply_flags()
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    results = {"flag_matrix": matrix, "scenarios": {}}

    sid = f"tb002-live-s1-{uuid.uuid4().hex[:8]}"
    turns = []
    for i, msg in enumerate(["Flamengo x Palmeiras", "Liverpool x Chelsea"], 1):
        st, data = _post(client, sid, msg)
        turns.append(_extract("s1_switch", i, msg, data, st))
        (OUT / f"raw_s1_t{i}.json").write_text(
            json.dumps({"http": st, "session": sid, "user": msg, "response": data}, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
    j1 = judge_s1(turns)
    results["scenarios"]["s1"] = {"turns": turns, "judgment": j1}

    sid = f"tb002-live-s2-{uuid.uuid4().hex[:8]}"
    turns = []
    for i, msg in enumerate(["Flamengo x Palmeiras", "Liverpool x Chelsea", "Quem está melhor?"], 1):
        st, data = _post(client, sid, msg)
        turns.append(_extract("s2_switch_fu", i, msg, data, st))
        (OUT / f"raw_s2_t{i}.json").write_text(
            json.dumps({"http": st, "session": sid, "user": msg, "response": data}, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
    j2 = judge_s2(turns)
    results["scenarios"]["s2"] = {"turns": turns, "judgment": j2}

    sid = f"tb002-live-s3-{uuid.uuid4().hex[:8]}"
    turns = []
    for i, msg in enumerate(["Flamengo x Palmeiras", "Inter joga hoje?"], 1):
        st, data = _post(client, sid, msg)
        turns.append(_extract("s3_partial", i, msg, data, st))
        (OUT / f"raw_s3_t{i}.json").write_text(
            json.dumps({"http": st, "session": sid, "user": msg, "response": data}, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
    j3 = judge_s3(turns)
    results["scenarios"]["s3"] = {"turns": turns, "judgment": j3}

    all_pass = all(results["scenarios"][k]["judgment"]["pass"] for k in ("s1", "s2", "s3"))
    results["all_pass"] = all_pass
    results["recommendation"] = (
        "ENABLE_TOPIC_BOUNDARY_V2=1" if all_pass else "KEEP ENABLE_TOPIC_BOUNDARY_V2=0"
    )

    (OUT / "live_results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    lines = [
        "# TOPIC-BOUNDARY-002 — Live router validation",
        "",
        f"**Flag session:** `ENABLE_TOPIC_BOUNDARY_V2=1` (code default unchanged / still off)",
        f"**All pass:** {all_pass}",
        f"**Recommendation:** {results['recommendation']}",
        "",
    ]
    for key, title in (
        ("s1", "Scenario 1 — Flamengo x Palmeiras → Liverpool x Chelsea"),
        ("s2", "Scenario 2 — … → Quem está melhor?"),
        ("s3", "Scenario 3 — Flamengo x Palmeiras → Inter joga hoje?"),
    ):
        sc = results["scenarios"][key]
        j = sc["judgment"]
        lines.append(f"## {title}")
        lines.append("")
        lines.append(f"**PASS:** {j['pass']}")
        lines.append("")
        for t in sc["turns"]:
            lines.append(f"### T{t['turn']}: {t['user']}")
            lines.append(f"- episode_id: `{t.get('episode_id')}`")
            lines.append(f"- csl_fixture: `{t.get('csl_fixture')}`")
            lines.append(f"- csl_teams: `{t.get('csl_teams')}`")
            lines.append(f"- home/away: `{t.get('home')}` / `{t.get('away')}`")
            lines.append(f"- flamengo={t.get('mentions_flamengo')} liverpool={t.get('mentions_liverpool')} inter={t.get('mentions_inter')}")
            lines.append(f"- mantendo_foco_flamengo={t.get('has_mantendo_foco_flamengo')}")
            lines.append(f"- summary: {t.get('summary_prefix')}")
            lines.append("")
        lines.append(f"Judgment detail: `{json.dumps(j, ensure_ascii=False)}`")
        lines.append("")

    (OUT / "TRANSCRIPT.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"all_pass": all_pass, "recommendation": results["recommendation"],
                      "s1": j1, "s2": j2, "s3": j3}, ensure_ascii=False, indent=2, default=str))
    print(f"WROTE {OUT}")


if __name__ == "__main__":
    main()
