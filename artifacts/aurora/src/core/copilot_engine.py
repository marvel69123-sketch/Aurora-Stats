"""
Aurora Copilot Engine — intent detection, dispatch, and response formatting.

Intents
-------
  analyze_match        "Analyze Palmeiras vs Flamengo"
  live_opportunities   "Best live opportunities"
  bankroll_review      "Review bankroll"
  learning_recap       "What did Aurora learn today?"
  knowledge_search     "What do you know about BTTS?"
  explain_last         "Explain the recommendation"
  help                 "What can you do?"
  greeting             "Hi / Hello"
  unknown              fallback

Public API
----------
  detect_intent(message: str) -> tuple[str, dict]
  async dispatch(intent, entities, session_ctx, session_id) -> str
"""
from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Intent detection — regex patterns, priority ordered
# ---------------------------------------------------------------------------

_SEP = r"(?:vs\.?|versus|v\.?(?!\w)|\bx\b)"

_GREETING_RE = re.compile(
    r"^(?:hi|hello|hey|oi|olá|good\s+(?:morning|afternoon|evening|day)|howdy|yo)(?:\s+aurora)?\W*$",
    re.IGNORECASE,
)
_HELP_RE = re.compile(
    r"(?:^help$|what\s+can\s+(?:you|aurora)\s+do|commands|options|capabilities|^menu$)",
    re.IGNORECASE,
)
_LIVE_RE = re.compile(
    r"(?:best\s+)?live\s+(?:opportunities|matches|games|bets|now)|"
    r"what(?:'s|\s+is)\s+(?:currently\s+)?live|"
    r"live\s+right\s+now|"
    r"^live\??$|"
    r"any(?:thing)?\s+live",
    re.IGNORECASE,
)
_BANKROLL_RE = re.compile(
    r"(?:review|check|show|how\s+(?:is|am)\s+(?:my|i))\s+(?:my\s+)?bankroll|"
    r"bankroll\s+(?:status|review|health|summary|check)|"
    r"how\s+am\s+i\s+doing|"
    r"my\s+performance|"
    r"roi|"
    r"profit|"
    r"results\s+(?:so\s+far|today)?",
    re.IGNORECASE,
)
_LEARNING_RE = re.compile(
    r"what\s+did\s+(?:aurora\s+)?learn(?:ed)?(?:\s+today)?|"
    r"learning\s+(?:recap|summary|today|history)|"
    r"aurora(?:'s)?\s+(?:performance|track\s+record)|"
    r"accuracy\s+(?:today|summary)|"
    r"what\s+did\s+you\s+learn",
    re.IGNORECASE,
)
_EXPLAIN_RE = re.compile(
    r"explain\s+(?:the\s+)?(?:last\s+)?(?:recommendation|call|pick)|"
    r"why\s+(?:did\s+you|aurora)\s+(?:recommend|suggest|pick)|"
    r"explain\s+(?:the\s+)?confidence|"
    r"tell\s+me\s+(?:more|why)|"
    r"more\s+details?",
    re.IGNORECASE,
)
_KNOWLEDGE_RE = re.compile(
    r"what\s+(?:do\s+you|does\s+aurora)\s+know\s+about\s+(.+)|"
    r"(?:explain|tell\s+me\s+about)\s+(.+?)\s+(?:market|rule|strategy|knowledge|system)|"
    r"(?:how\s+does|what\s+is|what\s+are)\s+(.+?)(?:\s+work(?:s)?|\s+mean(?:s)?|\?)?$|"
    r"knowledge\s+(?:about|on)\s+(.+)|"
    r"aurora(?:'s)?\s+rule\s+(?:on|for|about)\s+(.+)",
    re.IGNORECASE,
)
_MATCH_PATTERNS = [
    re.compile(rf"analyz(?:e|ing|e\s+me)\s+(.+?)\s+{_SEP}\s+(.+)", re.IGNORECASE),
    re.compile(
        rf"(?:intelligence|report|assess(?:ment)?|predict(?:ion)?|check|forecast|score)\s+(.+?)\s+{_SEP}\s+(.+)",
        re.IGNORECASE,
    ),
    re.compile(
        rf"(?:what\s+about|show\s+me|give\s+me|run)\s+(.+?)\s+{_SEP}\s+(.+)",
        re.IGNORECASE,
    ),
    re.compile(
        rf"(.+?)\s+{_SEP}\s+(.+?)\s+(?:analysis|analyze|intelligence|prediction|forecast|report)\W*$",
        re.IGNORECASE,
    ),
    re.compile(rf"^(.+?)\s+{_SEP}\s+(.+)$", re.IGNORECASE),
]


def _clean_team(name: str) -> str:
    return re.sub(r"[?.!,]+$", "", name).strip()


def _extract_knowledge_query(message: str) -> str:
    m = _KNOWLEDGE_RE.search(message)
    if m:
        for g in m.groups():
            if g:
                return _clean_team(g)
    # fallback: strip common prefixes
    cleaned = re.sub(r"^(?:what|how|tell|explain|knowledge)\s+\w+\s+", "", message, flags=re.IGNORECASE)
    return cleaned.strip() or message.strip()


def detect_intent(message: str) -> tuple[str, dict]:
    """
    Parse a natural-language message and return (intent_name, entities_dict).

    Priority: greeting → help → explain_last → live → bankroll → learning
              → knowledge → match_patterns → unknown
    """
    msg = message.strip()

    if _GREETING_RE.match(msg):
        return "greeting", {}

    if _HELP_RE.search(msg):
        return "help", {}

    if _EXPLAIN_RE.search(msg):
        return "explain_last", {}

    if _LIVE_RE.search(msg):
        return "live_opportunities", {}

    if _BANKROLL_RE.search(msg):
        return "bankroll_review", {}

    if _LEARNING_RE.search(msg):
        return "learning_recap", {}

    if _KNOWLEDGE_RE.search(msg):
        return "knowledge_search", {"query": _extract_knowledge_query(msg)}

    for pat in _MATCH_PATTERNS:
        m = pat.search(msg)
        if m:
            home = _clean_team(m.group(1))
            away = _clean_team(m.group(2))
            if home and away and home.lower() != away.lower():
                return "analyze_match", {"home": home, "away": away}

    return "unknown", {}


# ---------------------------------------------------------------------------
# Response formatters — pure functions, no side-effects
# ---------------------------------------------------------------------------


def _fmt_match(
    report: Any, hn: str, an: str, league: str | None, session_id: str
) -> str:
    """Format IntelligenceReport as a conversational copilot response."""
    league_str = f" — {league}" if league else ""
    status_str = report.status
    if report.minute:
        status_str += f" (minute {report.minute})"

    lines: list[str] = []

    # Header
    lines += [
        f"**{report.match}**{league_str}",
        f"*{status_str}*",
        "",
    ]

    # Executive summary
    lines += [report.executive_summary, ""]

    # Recommendation box
    if report.primary_recommendation != "No actionable market":
        lines += [
            f"**Primary recommendation:** {report.primary_recommendation}",
            f"**Confidence:** {report.overall_confidence}/10 · **Risk:** {report.risk_level}",
            "",
        ]

    # Top factors
    lines.append("**Key factors:**")
    for f in report.main_factors[:3]:
        lines.append(f"  {f}")
    lines.append("")

    # Positive signals (condensed)
    pos = [p for p in report.positive_factors if not p.startswith("• No category")]
    if pos:
        lines.append("**Supporting signals:**")
        for p in pos[:2]:
            lines.append(f"  {p}")
        lines.append("")

    # Risk flags (condensed)
    risks = [r for r in report.risk_factors if not r.startswith("• No critical")]
    if risks:
        lines.append("**Risks to note:**")
        for r in risks[:2]:
            lines.append(f"  {r}")
        lines.append("")

    # Stake (first line only)
    stake_first = report.recommended_stake.split("\n")[0]
    stake_examples = ""
    for ln in report.recommended_stake.split("\n"):
        if "£1,000" in ln or "£1k" in ln:
            stake_examples = ln.strip()
            break
    lines += [
        "**Recommended stake:**",
        f"  {stake_first}",
    ]
    if stake_examples:
        lines.append(f"  {stake_examples}")
    lines.append("")

    # Alternatives (condensed)
    alts = [a for a in report.alternative_markets if not a.startswith("No alternative")]
    if alts:
        lines.append("**Alternative markets:**")
        for a in alts[:2]:
            lines.append(f"  • {a[:180]}")
        lines.append("")

    # Invalidation teaser
    if report.invalidation_conditions:
        lines += [
            "**What could change this call:**",
            f"  {report.invalidation_conditions[0][:220]}",
            "",
        ]

    # Footer
    lines += [
        "---",
        f"*Session `{session_id}` · Ask: \"explain confidence\", \"what are the risks?\", or analyze another match.*",
    ]

    return "\n".join(lines)


def _fmt_live(live_data: dict, session_id: str) -> str:
    fixtures = live_data.get("live_matches", [])
    if not fixtures:
        return (
            "**No matches are currently live.**\n\n"
            "Check back later, or ask me to analyze an upcoming fixture:\n"
            "*\"Analyze [Home Team] vs [Away Team]\"*"
        )

    count = len(fixtures)
    lines = [f"**Live now — {count} match{'es' if count != 1 else ''}**", ""]

    for fx in fixtures[:5]:
        hn = (fx.get("teams", {}).get("home", {}) or {}).get("name", "Home")
        an = (fx.get("teams", {}).get("away", {}) or {}).get("name", "Away")
        minute = (fx.get("status") or {}).get("minute", "?")
        score_h = (fx.get("score", {}).get("current") or {}).get("home", 0)
        score_a = (fx.get("score", {}).get("current") or {}).get("away", 0)
        league = (fx.get("league") or {}).get("name", "")
        league_str = f" ({league})" if league else ""

        lines.append(f"**{hn} {score_h}–{score_a} {an}**{league_str} · Minute {minute}")

        # Pull best stat hint
        hs = (fx.get("stats") or {}).get("home") or {}
        corners = hs.get("corners") or 0
        if corners:
            lines.append(f"  Corners: {corners} | ")

        lines.append("")

    if count > 5:
        lines.append(f"*+{count - 5} more live matches.*")
        lines.append("")

    lines += [
        "**Want a full analysis?** Ask:",
        "*\"Analyze [Home Team] vs [Away Team]\"*",
        "",
        "---",
        f"*Session `{session_id}`*",
    ]
    return "\n".join(lines)


def _fmt_bankroll(stats: dict, session_id: str) -> str:
    total   = stats.get("total_predictions", 0)
    wins    = stats.get("wins", 0)
    losses  = stats.get("losses", 0)
    pending = stats.get("pending", 0)
    acc     = stats.get("current_accuracy")
    roi     = stats.get("roi_pct")
    best_m  = stats.get("best_market")
    worst_m = stats.get("worst_market")
    best_l  = stats.get("best_league")

    acc_str = f"{acc:.1f}%" if acc is not None else "not yet computed (no resolved bets)"
    roi_str = f"{roi:+.1f}%" if roi is not None else "not yet computed"

    lines = ["**Bankroll & Performance Review**", ""]

    if total == 0:
        lines += [
            "Aurora hasn't logged any predictions yet in this session.",
            "Every prediction is automatically tracked — start by analyzing a match.",
            "",
            f"*Session `{session_id}`*",
        ]
        return "\n".join(lines)

    decided = wins + losses
    lines += [
        f"**{total} predictions tracked** — {wins}W / {losses}L / {pending} pending",
        f"**Accuracy:** {acc_str}",
        f"**ROI:** {roi_str}",
        "",
    ]

    if best_m:
        lines.append(f"**Best-performing market:** {best_m.replace('_', ' ').title()}")
    if worst_m and worst_m != best_m:
        lines.append(f"**Weakest market:** {worst_m.replace('_', ' ').title()} — approach with extra caution")
    if best_l:
        lines.append(f"**Strongest league:** {best_l}")
    lines.append("")

    # Qualitative assessment
    if acc is not None:
        if acc >= 60:
            verdict = (
                f"Aurora is performing well at {acc:.1f}% accuracy. "
                f"Maintain discipline — stick to the quarter-Kelly staking plan."
            )
        elif acc >= 45:
            verdict = (
                f"Performance at {acc:.1f}% is marginally below the target of 55%+. "
                f"Review which markets are losing and consider reducing exposure there."
            )
        else:
            verdict = (
                f"Accuracy of {acc:.1f}% is below expectations. "
                f"Aurora recommends entering protection mode: halve all stakes "
                f"and only bet on markets with confidence ≥ 7.0 until the streak improves."
            )
        lines += [verdict, ""]

    # Market breakdown
    breakdown = stats.get("market_breakdown", [])
    if breakdown:
        lines.append("**Market breakdown (top 3 by accuracy):**")
        for r in breakdown[:3]:
            rule = r.get("rule", "").replace("_", " ").title()
            mkt_acc = r.get("accuracy", 0)
            mkt_w = r.get("wins", 0)
            mkt_l = r.get("losses", 0)
            lines.append(f"  • {rule}: {mkt_acc:.1f}% ({mkt_w}W/{mkt_l}L)")
        lines.append("")

    lines += [
        "---",
        f"*Session `{session_id}` · Ask: \"What did Aurora learn?\" or analyze a match.*",
    ]
    return "\n".join(lines)


def _fmt_learning(stats: dict, session_id: str) -> str:
    total   = stats.get("total_predictions", 0)
    wins    = stats.get("wins", 0)
    losses  = stats.get("losses", 0)
    pending = stats.get("pending", 0)
    acc     = stats.get("current_accuracy")
    best_m  = stats.get("best_market")
    worst_m = stats.get("worst_market")
    breakdown = stats.get("market_breakdown", [])
    league_br = stats.get("league_breakdown", [])

    lines = ["**Aurora Learning Recap**", ""]

    if total == 0:
        lines += [
            "No predictions have been resolved yet.",
            "Aurora begins learning automatically once match results come in.",
            "Every prediction is tracked — the learning engine updates in real time.",
            "",
            f"*Session `{session_id}`*",
        ]
        return "\n".join(lines)

    decided = wins + losses
    acc_str = f"{acc:.1f}%" if acc is not None else "pending"
    lines += [
        f"**Prediction track record:** {total} total — {wins}W / {losses}L / {pending} pending",
        f"**Current accuracy:** {acc_str}",
        "",
    ]

    if breakdown:
        lines.append("**What's working:**")
        for r in [x for x in breakdown if x.get("wins", 0) > 0][:3]:
            rule = r.get("rule", "").replace("_", " ").title()
            lines.append(f"  ✓ {rule} — {r.get('accuracy', 0):.1f}% accuracy ({r.get('wins', 0)}W/{r.get('losses', 0)}L)")
        lines.append("")

        losing = [x for x in breakdown if x.get("losses", 0) > x.get("wins", 0)]
        if losing:
            lines.append("**What's struggling:**")
            for r in losing[:2]:
                rule = r.get("rule", "").replace("_", " ").title()
                lines.append(f"  ✗ {rule} — {r.get('accuracy', 0):.1f}% accuracy ({r.get('wins', 0)}W/{r.get('losses', 0)}L)")
            lines.append("")

    if league_br:
        lines.append("**League performance:**")
        for lg in league_br[:3]:
            lines.append(
                f"  • {lg.get('league', 'Unknown')}: "
                f"{lg.get('accuracy', 0):.1f}% ({lg.get('wins', 0)}W/{lg.get('losses', 0)}L)"
            )
        lines.append("")

    lines += [
        "Aurora learns continuously — every resolved match updates the accuracy model.",
        "Weight changes to the methodology engine require 20+ consistent observations.",
        "",
        "---",
        f"*Session `{session_id}` · Ask: \"Review bankroll\" or analyze a match to add more data.*",
    ]
    return "\n".join(lines)


def _fmt_knowledge(results: list, query: str, session_id: str) -> str:
    if not results:
        return (
            f"**No knowledge found for \"{query}\"**\n\n"
            f"Aurora's knowledge base covers: methodology, betting rules, bankroll management, "
            f"market rules, live rules, pre-match rules, referee tendencies, league profiles, "
            f"team patterns, psychology, risk management, red flags, and golden rules.\n\n"
            f"Try: *\"What do you know about BTTS?\"* or *\"Explain Kelly Criterion\"*\n\n"
            f"---\n*Session `{session_id}`*"
        )

    lines = [f"**Aurora Knowledge — \"{query}\"**", f"*{len(results)} relevant item(s) found*", ""]

    for item in results[:4]:
        cat = item.get("category", "").replace("_", " ").title()
        title = item.get("title", "")
        desc = item.get("description", "")
        conf = item.get("confidence", 0)
        examples_raw = item.get("examples", [])

        lines += [
            f"**{title}** · *{cat}* · Confidence {conf:.0%}",
            desc,
        ]
        if examples_raw and isinstance(examples_raw, list):
            lines.append(f"*Example: {examples_raw[0][:150]}*")
        lines.append("")

    lines += [
        "---",
        f"*Session `{session_id}` · These rules are applied before every Aurora recommendation.*",
    ]
    return "\n".join(lines)


def _fmt_explain(report: Any, session_id: str) -> str:
    """Focused explanation using the confidence + main factors sections."""
    lines = [
        f"**Explaining: {report.match}**",
        f"*Recommendation: {report.primary_recommendation} | {report.overall_confidence}/10 confidence*",
        "",
    ]

    lines += [report.confidence_explanation, ""]

    lines.append("**Top factors:**")
    for f in report.main_factors[:5]:
        lines.append(f"  {f}")
    lines.append("")

    lines.append("**What could change this:**")
    for c in report.invalidation_conditions[:3]:
        lines.append(f"  • {c[:200]}")
    lines.append("")

    lines += [
        "---",
        f"*Session `{session_id}` · Ask: \"what are the risks?\" or analyze another match.*",
    ]
    return "\n".join(lines)


def _fmt_greeting(session_id: str) -> str:
    return (
        "Hello! I'm **Aurora**, your football intelligence assistant.\n\n"
        "I combine live match data, expected goals, historical patterns, "
        "and 39 foundational betting rules to give you professional-grade analysis.\n\n"
        "**What you can ask:**\n"
        "  • *\"Analyze Arsenal vs Chelsea\"* — full intelligence report\n"
        "  • *\"Best live opportunities\"* — current live match opportunities\n"
        "  • *\"Review bankroll\"* — your prediction performance\n"
        "  • *\"What did Aurora learn today?\"* — learning & accuracy recap\n"
        "  • *\"What do you know about BTTS?\"* — search knowledge base\n"
        "  • *\"Explain recommendation\"* — deep dive into the last call\n\n"
        "**Where to start?** Try: *\"Analyze [Home Team] vs [Away Team]\"*\n\n"
        "---\n"
        f"*Session `{session_id}` started.*"
    )


def _fmt_help(session_id: str) -> str:
    return (
        "**Aurora Copilot — Available Commands**\n\n"
        "| Command | Example |\n"
        "|---|---|\n"
        "| Analyze a match | *\"Analyze Palmeiras vs Flamengo\"* |\n"
        "| Live opportunities | *\"Best live opportunities\"* |\n"
        "| Bankroll review | *\"Review bankroll\"* |\n"
        "| Learning recap | *\"What did Aurora learn today?\"* |\n"
        "| Knowledge search | *\"What do you know about corners?\"* |\n"
        "| Explain last call | *\"Explain the recommendation\"* |\n\n"
        "**Natural language works:** You don't need exact commands. "
        "Try *\"Man City x Arsenal\"*, *\"how are my results?\"*, or *\"why did you pick that market?\"*\n\n"
        "**Every analysis includes:**\n"
        "  • Primary recommendation with probability and expected value\n"
        "  • 7 factors ranked by contribution\n"
        "  • Quarter-Kelly stake recommendation with bankroll examples\n"
        "  • Alternative markets\n"
        "  • Risk flags and invalidation conditions\n\n"
        "---\n"
        f"*Session `{session_id}`*"
    )


def _fmt_unknown(message: str, session_id: str) -> str:
    return (
        f"I didn't quite understand: *\"{message[:120]}\"*\n\n"
        "**Try one of these:**\n"
        "  • *\"Analyze [Home] vs [Away]\"* — match analysis\n"
        "  • *\"Best live opportunities\"* — live matches\n"
        "  • *\"Review bankroll\"* — performance\n"
        "  • *\"Help\"* — full command list\n\n"
        "---\n"
        f"*Session `{session_id}`*"
    )


# ---------------------------------------------------------------------------
# Dispatcher — async, calls engines, returns formatted response
# ---------------------------------------------------------------------------


async def dispatch(
    intent:      str,
    entities:    dict,
    session_ctx: dict,
    session_id:  str,
) -> str:
    """
    Route an intent to the appropriate Aurora pipeline and return a formatted response.
    All engine imports are lazy to avoid circular dependencies at module load.
    """
    try:
        if intent == "greeting":
            return _fmt_greeting(session_id)

        if intent == "help":
            return _fmt_help(session_id)

        if intent == "analyze_match":
            return await _handle_analyze(entities, session_id)

        if intent == "explain_last":
            return await _handle_explain(session_ctx, session_id)

        if intent == "live_opportunities":
            return await _handle_live(session_id)

        if intent == "bankroll_review":
            return _handle_bankroll(session_id)

        if intent == "learning_recap":
            return _handle_learning(session_id)

        if intent == "knowledge_search":
            return _handle_knowledge(entities.get("query", ""), session_id)

        return _fmt_unknown(entities.get("_raw", ""), session_id)

    except Exception as exc:
        logger.error("Copilot dispatch error [%s]: %s", intent, exc, exc_info=True)
        return (
            f"Aurora encountered an error processing your request: {exc}\n\n"
            "Please try again. If the error persists, check the fixture name spelling or try a different query.\n\n"
            f"---\n*Session `{session_id}`*"
        )


async def _handle_analyze(entities: dict, session_id: str) -> str:
    home = entities.get("home", "")
    away = entities.get("away", "")
    if not home or not away:
        return (
            "Please specify both teams: *\"Analyze [Home Team] vs [Away Team]\"*\n\n"
            f"---\n*Session `{session_id}`*"
        )

    # Import engines lazily
    from src.brain import get_config, get_methodology_config
    from src.core import confidence_engine, learning_engine, market_engine, methodology_engine, methodology_v1
    from src.core.decision_center import run as _dc_run
    from src.core.intelligence_engine import generate as _intel
    from src.core.knowledge_engine import consult as _kc
    from src.learning_db import get_learning_stats
    from src.memory_db import recall_context as _mem_recall
    from src.routers.analyze import analyze_fixture

    data    = await analyze_fixture(home=home, away=away)
    league  = (data.get("league") or {}).get("name")
    fx      = data["fixture"]
    teams   = data["teams"]
    hn      = teams["home"]["name"]
    an      = teams["away"]["name"]

    cfg  = get_config()
    mcfg = get_methodology_config()
    meth = methodology_engine.run(data, cfg)
    lrn  = learning_engine.run(league=league)
    conf = confidence_engine.run(meth, cfg)
    mkts = market_engine.run(hn, an, data, meth, conf, cfg)
    mv1  = methodology_v1.run(
        data=data, hn=hn, an=an,
        meth=meth, conf=conf, market=mkts,
        learning=lrn, mcfg=mcfg, brain_cfg=cfg,
    )
    dc = _dc_run(
        data=data, hn=hn, an=an, fixture_id=fx["id"],
        meth=meth, conf=conf, mv1=mv1, learning=lrn, cfg=cfg,
    )
    mem_ctx   = _mem_recall(hn=hn, an=an, league=league) or {}
    knowledge = _kc(
        hn=hn, an=an, league=league,
        is_live=bool(fx.get("status", {}).get("elapsed")),
        has_xg=meth.has_xg,
        has_referee=bool(fx.get("referee")),
        meth_score=mv1.overall_score,
    )
    lstats = get_learning_stats()

    report = _intel(
        hn=hn, an=an, league=league, data=data,
        mv1=mv1, dc=dc, meth=meth,
        knowledge=knowledge, learning_stats=lstats, mem_ctx=mem_ctx,
    )
    return _fmt_match(report, hn, an, league, session_id)


async def _handle_explain(session_ctx: dict, session_id: str) -> str:
    home = session_ctx.get("last_home")
    away = session_ctx.get("last_away")
    if not home or not away:
        return (
            "No recent match to explain. First analyze a fixture:\n"
            "*\"Analyze [Home Team] vs [Away Team]\"*\n\n"
            f"---\n*Session `{session_id}`*"
        )

    from src.brain import get_config, get_methodology_config
    from src.core import confidence_engine, learning_engine, market_engine, methodology_engine, methodology_v1
    from src.core.decision_center import run as _dc_run
    from src.core.intelligence_engine import generate as _intel
    from src.core.knowledge_engine import consult as _kc
    from src.learning_db import get_learning_stats
    from src.memory_db import recall_context as _mem_recall
    from src.routers.analyze import analyze_fixture

    data   = await analyze_fixture(home=home, away=away)
    league = (data.get("league") or {}).get("name")
    fx     = data["fixture"]
    teams  = data["teams"]
    hn     = teams["home"]["name"]
    an     = teams["away"]["name"]

    cfg  = get_config()
    mcfg = get_methodology_config()
    meth = methodology_engine.run(data, cfg)
    lrn  = learning_engine.run(league=league)
    conf = confidence_engine.run(meth, cfg)
    mkts = market_engine.run(hn, an, data, meth, conf, cfg)
    mv1  = methodology_v1.run(
        data=data, hn=hn, an=an,
        meth=meth, conf=conf, market=mkts,
        learning=lrn, mcfg=mcfg, brain_cfg=cfg,
    )
    dc = _dc_run(
        data=data, hn=hn, an=an, fixture_id=fx["id"],
        meth=meth, conf=conf, mv1=mv1, learning=lrn, cfg=cfg,
    )
    knowledge = _kc(hn=hn, an=an, league=league, has_xg=meth.has_xg,
                    has_referee=bool(fx.get("referee")), meth_score=mv1.overall_score)
    lstats = get_learning_stats()
    mem_ctx = _mem_recall(hn=hn, an=an, league=league) or {}

    report = _intel(
        hn=hn, an=an, league=league, data=data,
        mv1=mv1, dc=dc, meth=meth,
        knowledge=knowledge, learning_stats=lstats, mem_ctx=mem_ctx,
    )
    return _fmt_explain(report, session_id)


async def _handle_live(session_id: str) -> str:
    from src.routers.live import _build_live_response
    live_data = await _build_live_response()
    return _fmt_live(live_data, session_id)


def _handle_bankroll(session_id: str) -> str:
    from src.learning_db import get_learning_stats
    stats = get_learning_stats()
    return _fmt_bankroll(stats, session_id)


def _handle_learning(session_id: str) -> str:
    from src.learning_db import get_learning_stats
    stats = get_learning_stats()
    return _fmt_learning(stats, session_id)


def _handle_knowledge(query: str, session_id: str) -> str:
    if not query or len(query) < 2:
        return (
            "Please specify what you'd like to know about:\n"
            "*\"What do you know about [topic]?\"*\n\n"
            f"---\n*Session `{session_id}`*"
        )
    from src.knowledge_db import search_knowledge_items
    results = search_knowledge_items(query, limit=4)
    return _fmt_knowledge(results, query, session_id)
