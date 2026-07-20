#!/usr/bin/env python3
"""
P3-D.3 — Response Pattern Analysis (post Commitment Recovery).

Analysis only. Does not modify Aurora product code.
Clusters Aurora reply shapes that dominate remaining loops.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


def _tokens(t: str) -> set[str]:
    return {x for x in re.findall(r"[a-z0-9à-ú]{3,}", _fold(t))}


def jaccard(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def fingerprint(aurora: str) -> str:
    """Stabilize reply into a pattern key (strip quotes / numbers / names)."""
    f = _fold(aurora)
    f = re.sub(r"[“”\"'].*?[“”\"']", "<Q>", f)
    f = re.sub(r"\b\d+(?:[.,]\d+)?%?\b", "<N>", f)
    f = re.sub(r"\b(flamengo|palmeiras|bahia|corinthians|santos|sao paulo|botafogo|vasco|gremio|internacional)\b", "<TEAM>", f)
    f = re.sub(r"\s+", " ", f).strip()
    # keep first ~110 chars as signature
    return f[:110]


def classify_family(aurora: str) -> str:
    f = _fold(aurora)
    if any(
        x in f
        for x in (
            "minha inclinacao",
            "minha inclinação",
            "vejo valor",
            "seria cautelosa",
            "ha contexto suficiente",
            "há contexto suficiente",
            "caminho interessante, sem euforia",
            "vies positivo",
            "viés positivo",
            "o que me favorece",
            "o que sustenta minha leitura",
        )
    ):
        return "sport_analysis_boilerplate"
    if any(
        x in f
        for x in (
            "sem hipotese ativa",
            "sem hipótese ativa",
            "compromisso zerado",
            "modo aberto",
            "sem compromisso ativo",
            "sem nova ainda",
            "nao vou te perguntar de novo",
            "não vou te perguntar de novo",
            "sem repetir pergunta",
        )
    ):
        return "uncommitted_explicit"
    if any(
        x in f
        for x in (
            "soltei aquela leitura",
            "abandonei o fio",
            "reset limpo",
            "hipotese antiga fora",
            "hipótese antiga fora",
            "nao retomo o chute",
            "não retomo o chute",
            "manda o pedido atual",
            "assunto novo",
            "recomece do zero",
        )
    ):
        return "abandon_escape_ask"
    if any(
        x in f
        for x in (
            "vou assumir o fio",
            "seguindo do ponto",
            "retomo o ponto",
            "ok, vou responder sem repetir",
            "entendi que o pedido era",
            "seguindo com o que parece",
            "avancando no assunto",
            "avançando no assunto",
            "mantendo continuidade",
            "assunto:",
            "trato ",
        )
    ):
        return "soft_assume_goal"
    if any(
        x in f
        for x in (
            "voce esta falando de",
            "você está falando de",
            "selecao / time",
            "seleção / time",
            "jogo especifico",
            "jogo específico",
        )
    ):
        return "legacy_clarify_triage"
    if any(
        x in f
        for x in (
            "ficcao / hipotetico",
            "ficção / hipotético",
            "nao trato como partida real",
            "não trato como partida real",
        )
    ):
        return "fiction_refusal"
    if any(
        x in f
        for x in (
            "sem inventar placar",
            "sem inventar numero",
            "sem inventar número",
            "opiniao de torcida",
            "opinião de torcida",
            "modo conversa esportiva",
        )
    ):
        return "sport_chat_soft"
    if any(x in f for x in ("eu sou a aurora", "oi!", "tudo bem por aqui")):
        return "greeting_identity"
    if f.count("?") >= 2:
        return "multi_question"
    if len(f) < 12:
        return "too_short"
    return "other_content"


def is_loop(t: dict[str, Any]) -> bool:
    reasons = t.get("failure_reasons") or []
    if "loop" in reasons:
        return True
    return bool((t.get("scores") or {}).get("loop_hit"))


def main() -> None:
    full = json.loads(
        (ROOT / "human_stress_sessions_full.json").read_text(encoding="utf-8")
    )
    sessions = full.get("sessions") or []
    pm = json.loads((ROOT / "perception_metrics.json").read_text(encoding="utf-8"))

    family_all: Counter[str] = Counter()
    family_loop: Counter[str] = Counter()
    family_by_profile: dict[str, Counter[str]] = defaultdict(Counter)
    family_by_length: dict[str, Counter[str]] = defaultdict(Counter)
    fp_loop: Counter[str] = Counter()
    fp_all: Counter[str] = Counter()
    fp_examples: dict[str, str] = {}
    family_examples: dict[str, list[dict[str, Any]]] = defaultdict(list)

    # consecutive same-family streaks on loops
    family_streak_ge3 = Counter()
    intent_x_family: dict[str, Counter[str]] = defaultdict(Counter)

    # speech-act shape
    ask_rate_loop = 0
    ask_rate_all = 0
    n_loop = 0
    n_all = 0

    for s in sessions:
        profile = str(s.get("profile") or "?")
        length = str(s.get("length") or "?")
        prev_fam = None
        streak = 0
        for t in s.get("turns") or []:
            aurora = str(t.get("aurora_prefix") or "")
            if not aurora.strip():
                continue
            n_all += 1
            fam = classify_family(aurora)
            fp = fingerprint(aurora)
            family_all[fam] += 1
            fp_all[fp] += 1
            if fp not in fp_examples:
                fp_examples[fp] = aurora[:200]
            intent = str(t.get("intent") or "")
            if intent:
                intent_x_family[fam][intent] += 1
            if "?" in aurora:
                ask_rate_all += 1

            loop = is_loop(t)
            if loop:
                n_loop += 1
                family_loop[fam] += 1
                family_by_profile[profile][fam] += 1
                family_by_length[length][fam] += 1
                fp_loop[fp] += 1
                if "?" in aurora:
                    ask_rate_loop += 1
                if prev_fam == fam:
                    streak += 1
                    if streak == 3:
                        family_streak_ge3[fam] += 1
                else:
                    streak = 1
                    prev_fam = fam
                if len(family_examples[fam]) < 6:
                    family_examples[fam].append(
                        {
                            "run_id": s.get("run_id"),
                            "profile": profile,
                            "length": length,
                            "turn": t.get("turn"),
                            "user": str(t.get("user") or "")[:120],
                            "aurora": aurora[:220],
                            "intent": intent,
                        }
                    )
            else:
                streak = 0
                prev_fam = None

    loop_total = sum(family_loop.values()) or 1
    all_total = sum(family_all.values()) or 1

    family_ranked = [
        {
            "rank": i + 1,
            "family": fam,
            "loop_count": cnt,
            "loop_share": round(cnt / loop_total, 4),
            "all_count": family_all.get(fam, 0),
            "all_share": round(family_all.get(fam, 0) / all_total, 4),
            "loop_density": round(
                cnt / max(1, family_all.get(fam, 0)), 4
            ),  # P(loop|family)
            "top_intents": dict(intent_x_family[fam].most_common(5)),
            "streak_ge3_events": family_streak_ge3.get(fam, 0),
        }
        for i, (fam, cnt) in enumerate(family_loop.most_common())
    ]

    top_fps = [
        {
            "rank": i + 1,
            "fingerprint": fp,
            "loop_count": c,
            "loop_share": round(c / loop_total, 4),
            "all_count": fp_all.get(fp, 0),
            "example": fp_examples.get(fp, "")[:180],
            "family": classify_family(fp_examples.get(fp, "")),
        }
        for i, (fp, c) in enumerate(fp_loop.most_common(40))
    ]

    profile_rank = []
    for p, c in family_by_profile.items():
        top = c.most_common(3)
        profile_rank.append(
            {
                "profile": p,
                "loop_events": sum(c.values()),
                "top_families": [
                    {"family": k, "count": v, "share": round(v / max(1, sum(c.values())), 4)}
                    for k, v in top
                ],
            }
        )
    profile_rank.sort(key=lambda r: -r["loop_events"])

    length_rank = []
    for L, c in sorted(
        family_by_length.items(),
        key=lambda x: int(x[0]) if str(x[0]).isdigit() else 0,
    ):
        top = c.most_common(3)
        length_rank.append(
            {
                "length": L,
                "loop_events": sum(c.values()),
                "top_families": [
                    {"family": k, "count": v, "share": round(v / max(1, sum(c.values())), 4)}
                    for k, v in top
                ],
            }
        )

    # Concentration: how much of loops is top-K fingerprints
    cum = 0
    concentration = []
    for k, (_fp, c) in enumerate(fp_loop.most_common(20), start=1):
        cum += c
        concentration.append({"top_k": k, "share": round(cum / loop_total, 4)})

    answers = {
        "1_dominant_loop_family": family_ranked[0]["family"] if family_ranked else None,
        "2_top3_families": [r["family"] for r in family_ranked[:3]],
        "3_escape_still_dominant": bool(
            family_loop.get("abandon_escape_ask", 0) / loop_total >= 0.25
        ),
        "4_uncommitted_share_of_loops": round(
            family_loop.get("uncommitted_explicit", 0) / loop_total, 4
        ),
        "5_sport_boilerplate_share": round(
            family_loop.get("sport_analysis_boilerplate", 0) / loop_total, 4
        ),
        "6_soft_assume_share": round(
            family_loop.get("soft_assume_goal", 0) / loop_total, 4
        ),
        "7_ask_rate_on_loops": round(ask_rate_loop / max(1, n_loop), 4),
        "8_top10_fingerprint_concentration": concentration[9]["share"]
        if len(concentration) >= 10
        else None,
        "9_commitment_recovery_effect": (
            "abandon_escape_ask + uncommitted_explicit together are "
            f"{100 * (family_loop.get('abandon_escape_ask', 0) + family_loop.get('uncommitted_explicit', 0)) / loop_total:.1f}% of loops; "
            "sport_analysis_boilerplate remains the largest single sticky family if ranked #1, "
            "or second — see ranked table."
        ),
    }

    report = {
        "version": "P3-D.3",
        "generated_at": _utc(),
        "mode": "analysis_only",
        "corpus": {
            "sessions": len(sessions),
            "total_replies": n_all,
            "loop_replies": n_loop,
            "loop_rate_global": (pm.get("metrics") or {}).get("Loop_Rate"),
            "context": "post_commitment_recovery_mvp destroy",
        },
        "family_ranked_by_loop": family_ranked,
        "top_loop_fingerprints": top_fps,
        "fingerprint_concentration": concentration,
        "by_profile": profile_rank,
        "by_length": length_rank,
        "ask_rates": {
            "all_replies": round(ask_rate_all / max(1, n_all), 4),
            "loop_replies": round(ask_rate_loop / max(1, n_loop), 4),
        },
        "family_streak_ge3": dict(family_streak_ge3.most_common()),
        "answers": answers,
        "examples": {k: v for k, v in family_examples.items()},
        "definitions": {
            "sport_analysis_boilerplate": "Frozen sports engine prose (cautela/vejo valor/contexto suficiente).",
            "uncommitted_explicit": "P3-D.2 no-commitment non-ask lines.",
            "abandon_escape_ask": "Post-abandon open ask (escape budget).",
            "soft_assume_goal": "Goal soft-assume / rebuild continue templates.",
            "legacy_clarify_triage": "Old seleção/time/jogo triage.",
            "fiction_refusal": "Fiction/hypothetical refusal.",
            "sport_chat_soft": "Conversational sport chat without analysis boilerplate.",
        },
    }

    out_json = ROOT / "response_pattern_analysis.json"
    out_json.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    lines = [
        "# P3-D.3 — Response Pattern Analysis",
        "",
        "**Mode:** ANALYSIS ONLY (no implementation)",
        f"**Generated:** {report['generated_at']}",
        f"**Corpus:** post–Commitment Recovery destroy — {len(sessions)} sessions / {n_all} replies / {n_loop} loop replies",
        f"**Global loop rate:** {(pm.get('metrics') or {}).get('Loop_Rate')}",
        "",
        "---",
        "",
        "## Verdict",
        "",
        f"- Dominant loop family: **`{answers['1_dominant_loop_family']}`** "
        f"({100 * (family_ranked[0]['loop_share'] if family_ranked else 0):.1f}% of loop replies).",
        f"- Top 3: {', '.join(f'`{x}`' for x in answers['2_top3_families'])}.",
        f"- Escape still dominant? **{answers['3_escape_still_dominant']}** "
        f"(abandon_escape share "
        f"{100 * family_loop.get('abandon_escape_ask', 0) / loop_total:.1f}%).",
        f"- Uncommitted explicit share of loops: "
        f"**{100 * answers['4_uncommitted_share_of_loops']:.1f}%**.",
        f"- Ask-rate on loop replies: **{100 * answers['7_ask_rate_on_loops']:.1f}%** "
        f"(all replies {100 * ask_rate_all / max(1, n_all):.1f}%).",
        f"- Top-10 fingerprints cover **{100 * (answers['8_top10_fingerprint_concentration'] or 0):.1f}%** of loop replies.",
        "",
        "## Loop families (ranked)",
        "",
        "| Rank | Family | Loop # | Loop % | P(loop\\|family) | Streak≥3 |",
        "|-----:|--------|-------:|-------:|----------------:|---------:|",
    ]
    for r in family_ranked:
        lines.append(
            f"| {r['rank']} | `{r['family']}` | {r['loop_count']} | "
            f"{100 * r['loop_share']:.1f}% | {r['loop_density']:.2f} | "
            f"{r['streak_ge3_events']} |"
        )

    lines += [
        "",
        "## Top loop fingerprints (concrete templates)",
        "",
        "| Rank | Family | Loop # | Example |",
        "|-----:|--------|-------:|---------|",
    ]
    for r in top_fps[:15]:
        ex = (r["example"] or "").replace("|", "/").replace("\n", " ")[:90]
        lines.append(
            f"| {r['rank']} | `{r['family']}` | {r['loop_count']} | {ex} |"
        )

    lines += [
        "",
        "## By persona (loop families)",
        "",
        "| Persona | Loop events | #1 family | #2 |",
        "|---------|------------:|-----------|----|",
    ]
    for r in profile_rank:
        tops = r["top_families"]
        t1 = f"`{tops[0]['family']}` ({100 * tops[0]['share']:.0f}%)" if tops else "—"
        t2 = f"`{tops[1]['family']}` ({100 * tops[1]['share']:.0f}%)" if len(tops) > 1 else "—"
        lines.append(f"| {r['profile']} | {r['loop_events']} | {t1} | {t2} |")

    lines += [
        "",
        "## By length",
        "",
        "| L | Loop events | #1 family |",
        "|--|------------:|-----------|",
    ]
    for r in length_rank:
        tops = r["top_families"]
        t1 = f"`{tops[0]['family']}` ({100 * tops[0]['share']:.0f}%)" if tops else "—"
        lines.append(f"| {r['length']} | {r['loop_events']} | {t1} |")

    lines += [
        "",
        "## What this means (no fix here)",
        "",
        "1. **Belief + commitment recovery** changed the *shape* of hollow replies "
        "(escape → uncommitted), but did not remove the largest sticky **content** family "
        "if sport analysis boilerplate still leads.",
        "2. **Soft-assume** remains a mid-tier loop family — paraphrased goal continues can "
        "still Jaccard-collide on long sessions.",
        "3. Pattern concentration: a small set of fingerprints explains a large share of loops "
        "→ remaining collapse is **template-driven**, not diffuse randomness.",
        "",
        "## Answers",
        "",
    ]
    for k, v in answers.items():
        lines.append(f"**{k}:** {v}")
        lines.append("")

    lines += [
        "---",
        "",
        "Artifacts: `response_pattern_analysis.json`, `response_pattern_analysis.md`",
        "",
    ]

    (ROOT / "response_pattern_analysis.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "wrote": [
                    str(out_json.name),
                    "response_pattern_analysis.md",
                ],
                "dominant": answers["1_dominant_loop_family"],
                "top3": answers["2_top3_families"],
                "sport_share": answers["5_sport_boilerplate_share"],
                "escape_share": round(
                    family_loop.get("abandon_escape_ask", 0) / loop_total, 4
                ),
                "uncommitted_share": answers["4_uncommitted_share_of_loops"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
