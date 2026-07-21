"""Print compact summary of audit JSON for REPORT drafting."""
from __future__ import annotations

import json
from pathlib import Path

p = Path(__file__).resolve().parent


def ep(eid):
    return (eid or "")[:8]


for name in [
    "raw_sport_nlg_off.json",
    "raw_sport_nlg_on.json",
    "raw_topic_boundary_off.json",
    "raw_topic_boundary_on.json",
    "raw_entity_edge_off.json",
    "raw_entity_edge_on.json",
    "raw_before.json",
    "raw_after.json",
]:
    d = json.loads((p / name).read_text(encoding="utf-8"))
    print("====", name, "====")
    if "turns" in d:
        for t in d["turns"]:
            pref = (t.get("summary_prefix") or "")[:160]
            print(
                f"  [{t.get('mode')}] {t.get('session')} T{t.get('turn')} "
                f"user={t.get('user')!r}"
            )
            print(
                f"    owner={t.get('response_owner')} intent={t.get('sport_intent')} "
                f"nlg={t.get('sport_nlg')} ep={ep(t.get('episode_id'))} "
                f"fx={t.get('csl_fixture')}"
            )
            print(f"    prefix={pref!r}")
            print(
                "    flags: "
                f"mantendo={t.get('has_mantendo_foco')} "
                f"fase={t.get('has_fase_recente')} "
                f"viab={t.get('has_viabilidade')} "
                f"mando={t.get('has_mando')} "
                f"odds={t.get('invented_odds_like')} "
                f"fla={t.get('mentions_flamengo')} "
                f"liv={t.get('mentions_liverpool')} "
                f"chel={t.get('mentions_chelsea')}"
            )
    if "probes" in d:
        for pr in d["probes"]:
            print(
                f"  {pr['raw']!r} msg={pr.get('message')!r} "
                f"-> norm={pr.get('normalize')} "
                f"edge={pr.get('edge_canonical')}/{pr.get('edge_source')} "
                f"fuzzy={pr.get('fuzzy_hit')}"
            )
