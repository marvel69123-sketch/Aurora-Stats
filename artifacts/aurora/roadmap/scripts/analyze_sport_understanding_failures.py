#!/usr/bin/env python3
"""
Sport understanding failure analysis — post perception / diversification destroy.

ANALYSIS ONLY. Does not modify Aurora product code.
Uses human_stress_sessions_full.json + conversation_failures.json.
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

SPORT_USER = re.compile(
    r"\b("
    r"flamengo|palmeiras|corinthians|santos|vasco|botafogo|gremio|grêmio|"
    r"internacional|sao\s*paulo|são\s*paulo|bahia|cruzeiro|atletico|atlético|"
    r"barcelona|real\s*madrid|manchester|liverpool|chelsea|arsenal|"
    r"jogo|partida|placar|odd|odds|mercado|aposta|over|under|"
    r"times?|sele[cç][aã]o|campeonato|brasileir[aã]o|libertadores|"
    r"classico|clássico|rival|escanteio|cart[aã]o|gol|gols|"
    r"vale\s+a\s+pena|quem\s+ganha|como\s+est[aá]|forma\s+do|"
    r"x\s+\w+|vs\.?"
    r")\b",
    re.I,
)

PRONOUN_SPORT = re.compile(
    r"\b(e\s+dele|e\s+deles|e\s+o\s+outro|como\s+ele|eles\s+est|desse\s+time|"
    r"desse\s+jogo|e\s+agora|nesse\s+jogo|nesse\s+confronto)\b",
    re.I,
)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


def is_sport_user(user: str) -> bool:
    u = user or ""
    if SPORT_USER.search(u):
        return True
    if PRONOUN_SPORT.search(u) and len(u.split()) <= 8:
        return True
    return False


def classify_reply_failure(user: str, aurora: str, scores: dict[str, Any] | None) -> list[str]:
    """Return zero+ failure tags for a sport-ish user turn."""
    f = _fold(aurora)
    u = _fold(user)
    tags: list[str] = []
    sc = scores or {}

    if "ficcao" in f or "ficção" in f or "hipotetico" in f or "hipotético" in f:
        if not any(x in u for x in ("dragao", "dragão", "unicornio", "unicórnio", "marte", "harry")):
            tags.append("fiction_false_positive")

    if (
        "voce esta falando de" in f
        or "você está falando de" in f
        or ("selecao" in f and "jogo especifico" in f)
        or ("seleção" in f and "jogo específico" in f)
    ):
        tags.append("legacy_triage_menu")

    if any(
        x in f
        for x in (
            "contexto suficiente",
            "minha inclinacao",
            "minha inclinação",
            "pontos a favor",
            "o que me favorece",
            "vejo valor, mas",
        )
    ):
        if any(
            x in u
            for x in (
                "quem ganha",
                "placar",
                "odd",
                "ao vivo",
                "agora",
                "e dele",
                "e o outro",
                "como ele",
                "vale a pena",
            )
        ) or len(u.split()) <= 6:
            tags.append("boilerplate_misses_question")

    if any(
        x in f
        for x in (
            "sou a aurora",
            "assistente",
            "posso te ajudar com",
            "nao sou humana",
            "não sou humana",
        )
    ) and is_sport_user(user):
        tags.append("identity_deflection")

    if any(
        x in f
        for x in (
            "sem hipotese ativa",
            "sem hipótese ativa",
            "compromisso zerado",
            "modo aberto",
            "zerei o enquadro",
            "sem compromisso",
            "mudando o formato: sem status",
        )
    ):
        tags.append("hollow_uncommitted_instead_of_sport")

    if any(x in f for x in ("ancorando no que voce", "ancorando no que você", "pegando o fio de", "voltando ao")):
        if not any(x in f for x in ("mercado", "risco", "forma", "placar", "odd", "leitura")):
            tags.append("anchor_without_sport_answer")

    qmarks = (aurora or "").count("?")
    if qmarks >= 2 and len(f) < 280:
        tags.append("over_ask_instead_of_bind")

    if any(x in f for x in ("leitura curta", "resumo direto", "versao enxuta", "versão enxuta")):
        if any(x in u for x in ("quem ganha", "placar", "ao vivo", "e dele", "odd")):
            tags.append("short_sport_still_generic")

    try:
        uc = float(sc.get("understanding_confidence") or 10)
        if uc <= 4.0:
            tags.append("low_understanding_confidence")
    except Exception:
        pass

    if sc.get("invention_hit"):
        tags.append("invention_flag")
    if sc.get("robotic_hit"):
        tags.append("robotic_flag")
    if sc.get("loop_hit"):
        tags.append("loop_flag")

    if any(
        x in f
        for x in (
            "vou assumir o fio",
            "seguindo do ponto",
            "entendi que o pedido era",
            "avancando no assunto",
            "avançando no assunto",
        )
    ):
        tags.append("soft_assume_template")

    if any(x in f for x in ("nao entendi", "não entendi", "pode reformular", "fora do esporte")):
        tags.append("explicit_non_understand")

    return tags


def sport_question_shape(user: str) -> str:
    u = _fold(user)
    if re.search(r"\bx\b|\bvs\b", u):
        return "fixture_pair"
    if any(x in u for x in ("e dele", "e o outro", "como ele", "eles ", "desse time", "nesse jogo")):
        return "pronoun_followup"
    if any(x in u for x in ("odd", "mercado", "aposta", "over", "under", "vale a pena")):
        return "market_ask"
    if any(x in u for x in ("placar", "ao vivo", "agora", "tempo real")):
        return "live_or_score"
    if any(x in u for x in ("quem ganha", "palpite", "tendencia", "tendência")):
        return "prediction"
    if any(x in u for x in ("forma", "elenco", "tecnico", "técnico", "lesao", "lesão")):
        return "team_context"
    if len(u.split()) <= 3:
        return "ultra_short_sport"
    return "sport_chat_other"


def main() -> None:
    sessions = json.loads(
        (ROOT / "human_stress_sessions_full.json").read_text(encoding="utf-8")
    )["sessions"]
    failures_doc = json.loads(
        (ROOT / "conversation_failures.json").read_text(encoding="utf-8")
    )
    tax = json.loads((ROOT / "destroy_loop_taxonomy.json").read_text(encoding="utf-8"))
    danger = json.loads((ROOT / "destroy_danger_rankings.json").read_text(encoding="utf-8"))

    tag_counts: Counter[str] = Counter()
    shape_counts: Counter[str] = Counter()
    shape_fail: dict[str, Counter[str]] = defaultdict(Counter)
    profile_fail: dict[str, Counter[str]] = defaultdict(Counter)
    intent_on_sport: Counter[str] = Counter()
    dialog_on_sport: Counter[str] = Counter()
    examples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    sport_turns = 0
    sport_turns_with_fail = 0
    low_uc_sport = 0
    uc_sum = 0.0
    uc_n = 0

    esportivo_sessions = []

    for s in sessions:
        prof = s.get("profile")
        if prof == "esportivo":
            esportivo_sessions.append(
                {
                    "run_id": s.get("run_id"),
                    "length": s.get("length"),
                    "loop_rate": (s.get("hard") or {}).get("loop_rate"),
                    "break_turn": (s.get("hard") or {}).get("break_turn"),
                    "failure_count": s.get("failure_count"),
                    "understanding_mean": round(
                        sum(
                            float((t.get("scores") or {}).get("understanding_confidence") or 0)
                            for t in (s.get("turns") or [])
                        )
                        / max(1, len(s.get("turns") or [])),
                        3,
                    ),
                }
            )

        for t in s.get("turns") or []:
            user = str(t.get("user") or "")
            if prof != "esportivo" and not is_sport_user(user):
                continue

            sport_turns += 1
            aurora = str(t.get("aurora_prefix") or "")
            scores = t.get("scores") or {}
            shape = sport_question_shape(user)
            shape_counts[shape] += 1
            intent_on_sport[str(t.get("intent") or "?")] += 1
            dialog_on_sport[str(t.get("dialog_mode") or "?")] += 1

            try:
                uc = float(scores.get("understanding_confidence") or 0)
                uc_sum += uc
                uc_n += 1
                if uc <= 4.0:
                    low_uc_sport += 1
            except Exception:
                pass

            tags = classify_reply_failure(user, aurora, scores)
            for r in t.get("failure_reasons") or []:
                tags.append(f"harness:{r}")

            if tags:
                sport_turns_with_fail += 1
            for tag in tags:
                tag_counts[tag] += 1
                shape_fail[shape][tag] += 1
                profile_fail[str(prof)][tag] += 1
                if len(examples[tag]) < 6:
                    examples[tag].append(
                        {
                            "run_id": s.get("run_id"),
                            "profile": prof,
                            "length": s.get("length"),
                            "turn": t.get("turn"),
                            "shape": shape,
                            "intent": t.get("intent"),
                            "dialog_mode": t.get("dialog_mode"),
                            "user": user[:160],
                            "aurora": aurora[:220],
                            "understanding_confidence": scores.get("understanding_confidence"),
                            "failure_reasons": t.get("failure_reasons"),
                        }
                    )

    cf_sport = []
    cf_reason = Counter()
    for f in failures_doc.get("failures") or []:
        user = str(f.get("user") or "")
        if f.get("profile") == "esportivo" or is_sport_user(user):
            cf_sport.append(f)
            for r in f.get("reasons") or []:
                cf_reason[r] += 1

    sport_danger: list[Any] = []

    def _walk(obj: Any) -> None:
        if isinstance(obj, dict):
            if obj.get("persona") == "esportivo" or obj.get("category") in {
                "sport_continuity",
                "sport_light",
                "sport",
            }:
                sport_danger.append(
                    {k: obj[k] for k in list(obj)[:12] if not isinstance(obj[k], (list, dict))}
                    | {
                        k: obj[k]
                        for k in ("persona", "category", "prompt", "user", "score", "loop_rate")
                        if k in obj and not isinstance(obj.get(k), (list, dict))
                    }
                )
            for v in obj.values():
                _walk(v)
        elif isinstance(obj, list):
            for v in obj[:80]:
                _walk(v)

    _walk(danger)

    top_tags = tag_counts.most_common(20)
    principal = top_tags[0][0] if top_tags else "unknown"

    report = {
        "version": "sport_understanding_failure_analysis",
        "generated_at": _utc(),
        "mode": "ANALYSIS_ONLY",
        "corpus": {
            "sessions": len(sessions),
            "sport_turns_analyzed": sport_turns,
            "sport_turns_with_any_fail_tag": sport_turns_with_fail,
            "fail_tag_rate": round(sport_turns_with_fail / max(1, sport_turns), 4),
            "mean_understanding_confidence_sport": round(uc_sum / max(1, uc_n), 3),
            "low_uc_rate_le4": round(low_uc_sport / max(1, sport_turns), 4),
            "destroy_loop_taxonomy": tax.get("loop_taxonomy"),
            "conversation_failures_sportish": len(cf_sport),
            "conversation_failure_reasons_sportish": dict(cf_reason.most_common()),
        },
        "principal_failure_tag": principal,
        "failure_tags_ranked": [
            {
                "tag": t,
                "count": c,
                "share_of_tagged_events": round(c / max(1, sum(tag_counts.values())), 4),
            }
            for t, c in top_tags
        ],
        "question_shapes": dict(shape_counts),
        "failures_by_shape": {k: dict(v.most_common(8)) for k, v in shape_fail.items()},
        "failures_by_profile": {k: dict(v.most_common(8)) for k, v in profile_fail.items()},
        "intent_on_sport_turns": dict(intent_on_sport.most_common(25)),
        "dialog_mode_on_sport_turns": dict(dialog_on_sport.most_common(25)),
        "esportivo_sessions": sorted(
            esportivo_sessions,
            key=lambda x: (-(x.get("loop_rate") or 0), x.get("length") or 0),
        ),
        "examples": {k: examples[k] for k, _ in top_tags[:12]},
        "danger_snippets_sport": sport_danger[:20],
        "causal_verdict": {
            "summary": (
                "Perception/diversification reduced hollow loops, but sport understanding "
                "still fails when binding/intent/domain gates misfire — especially fiction FP, "
                "triage menus, and generic analysis that does not answer the user question."
            ),
            "layers": [
                {
                    "layer": "domain_gate",
                    "issue": "fiction_false_positive / identity deflection",
                    "effect": "Real sport asks rejected or redirected before binding",
                },
                {
                    "layer": "referent_binding",
                    "issue": "legacy_triage_menu / over_ask_instead_of_bind",
                    "effect": "Fixture/team not bound; user re-asked instead of answered",
                },
                {
                    "layer": "intent_answer_fit",
                    "issue": "boilerplate_misses_question / short_sport_still_generic",
                    "effect": "Deep/short sport templates ignore question shape",
                },
                {
                    "layer": "commitment_recovery_side_effect",
                    "issue": "hollow_uncommitted_instead_of_sport / soft_assume_template",
                    "effect": "After abandon/diversify, sport thread replaced by hollow status",
                },
                {
                    "layer": "harness_perception",
                    "issue": "context_confusion dominates loop taxonomy",
                    "effect": "Talks sport-shaped without proving understanding",
                },
            ],
        },
    }

    (ROOT / "sport_understanding_failure_analysis.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    lines = [
        "# Sport Understanding Failure Analysis",
        "",
        "**Mode:** ANALYSIS ONLY (no implementation)",
        f"**Generated:** {report['generated_at']}",
        f"**Corpus:** destroy sessions ({len(sessions)}) — sport/esportivo turns mined",
        "",
        "---",
        "",
        "## Verdict",
        "",
        report["causal_verdict"]["summary"],
        "",
        f"- Sport turns analyzed: **{sport_turns}**",
        f"- Turns with ≥1 failure tag: **{sport_turns_with_fail}** ({report['corpus']['fail_tag_rate']:.1%})",
        f"- Mean understanding confidence (sport): **{report['corpus']['mean_understanding_confidence_sport']}**",
        f"- Low UC (≤4) rate: **{report['corpus']['low_uc_rate_le4']:.1%}**",
        f"- Principal failure tag: **`{principal}`**",
        "",
        "## Why perception MVPs were not enough",
        "",
        "Belief revision / commitment recovery / response diversification attack "
        "**sticky reply banks** and hollow commitment. They do **not** fix:",
        "",
        "1. **Referent binding** (which team/fixture is in scope)",
        "2. **Question-shape answering** (pronoun / live / odds / prediction)",
        "3. **Domain gates** (fiction/identity firing on real sport talk)",
        "",
        "Destroy loop taxonomy is still dominated by **context_confusion** "
        f"({(tax.get('loop_taxonomy') or {}).get('share', {}).get('context_confusion')} share) — "
        "a binding/understanding failure class, not a template-cooldown class.",
        "",
        "## Failure tags (ranked)",
        "",
        "| Tag | Count | Share |",
        "|-----|------:|------:|",
    ]
    for row in report["failure_tags_ranked"][:18]:
        lines.append(
            f"| `{row['tag']}` | {row['count']} | {row['share_of_tagged_events']:.1%} |"
        )

    lines += [
        "",
        "## By question shape",
        "",
        "| Shape | Turns | Top failure |",
        "|-------|------:|-------------|",
    ]
    for shape, n in shape_counts.most_common():
        top = shape_fail[shape].most_common(1)
        top_s = f"{top[0][0]} ({top[0][1]})" if top else "—"
        lines.append(f"| `{shape}` | {n} | {top_s} |")

    lines += [
        "",
        "## Causal stack (where understanding breaks)",
        "",
    ]
    for i, layer in enumerate(report["causal_verdict"]["layers"], 1):
        lines.append(
            f"{i}. **{layer['layer']}** — `{layer['issue']}` → {layer['effect']}"
        )

    lines += [
        "",
        "## Intent / dialog_mode on sport turns",
        "",
        "Top intents:",
    ]
    for k, v in intent_on_sport.most_common(12):
        lines.append(f"- `{k}`: {v}")
    lines.append("")
    lines.append("Top dialog modes:")
    for k, v in dialog_on_sport.most_common(12):
        lines.append(f"- `{k}`: {v}")

    lines += [
        "",
        "## Esportivo sessions (hard)",
        "",
        "| Run | L | Loop | Break | Failures | UC mean |",
        "|-----|--:|-----:|------:|---------:|--------:|",
    ]
    for row in report["esportivo_sessions"]:
        lines.append(
            f"| `{row['run_id']}` | {row['length']} | {row['loop_rate']} | "
            f"{row['break_turn']} | {row['failure_count']} | {row['understanding_mean']} |"
        )

    lines += [
        "",
        "## Conversation failures (sportish)",
        "",
        f"Events: **{len(cf_sport)}**",
        "",
        "Reasons:",
    ]
    for k, v in cf_reason.most_common():
        lines.append(f"- `{k}`: {v}")

    lines += ["", "## Concrete examples (from destroy dumps)", ""]
    for tag, _ in top_tags[:8]:
        lines.append(f"### `{tag}`")
        for ex in examples.get(tag, [])[:3]:
            lines.append(
                f"- **{ex['profile']} L{ex['length']} t{ex['turn']}** "
                f"({ex['shape']}, intent=`{ex['intent']}`)"
            )
            lines.append(f"  - User: {ex['user']}")
            lines.append(f"  - Aurora: {ex['aurora']}")
            lines.append(
                f"  - UC={ex['understanding_confidence']} reasons={ex['failure_reasons']}"
            )
        lines.append("")

    lines += [
        "## What this is NOT",
        "",
        "- Not a sports-engine stats/odds bug report (engines frozen; no invented numbers expected).",
        "- Not asking for a new diversification bank.",
        "- Next work (when requested) should target **binding + question-shape routing**, "
        "not more hollow-reply cooldowns.",
        "",
        "Artifacts: `sport_understanding_failure_analysis.json`, "
        "`sport_understanding_failure_analysis.md`",
        "",
    ]

    (ROOT / "sport_understanding_failure_analysis.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "wrote": [
                    "sport_understanding_failure_analysis.json",
                    "sport_understanding_failure_analysis.md",
                ],
                "sport_turns": sport_turns,
                "fail_rate": report["corpus"]["fail_tag_rate"],
                "principal": principal,
                "top5": [t for t, _ in top_tags[:5]],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
