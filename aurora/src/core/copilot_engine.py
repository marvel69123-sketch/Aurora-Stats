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

# Separator: "vs", "versus", "v", "x", "contra", "×"
_SEP = r"(?:vs\.?|versus|v\.?(?!\w)|\bx\b|\bcontra\b|\×)"

# ---------------------------------------------------------------------------
# Team alias map — normalise common aliases before sending to API-Football
# ---------------------------------------------------------------------------
_TEAM_ALIASES: dict[str, str] = {
    # European clubs
    "psg": "Paris Saint-Germain",
    "paris sg": "Paris Saint-Germain",
    "paris saint germain": "Paris Saint-Germain",
    "man united": "Manchester United",
    "man utd": "Manchester United",
    "manchester utd": "Manchester United",
    "man u": "Manchester United",
    "man city": "Manchester City",
    "atletico madrid": "Atletico Madrid",
    "atm": "Atletico Madrid",
    "atletico": "Atletico Madrid",
    "real": "Real Madrid",
    "barca": "Barcelona",
    "barca": "Barcelona",
    "fcb": "Barcelona",
    "spurs": "Tottenham",
    "tottenham hotspur": "Tottenham",
    "dortmund": "Borussia Dortmund",
    "bvb": "Borussia Dortmund",
    "bayern": "Bayern Munich",
    "juve": "Juventus",
    "juventus fc": "Juventus",
    "milan": "AC Milan",
    "ac milan": "AC Milan",
    "inter milan": "Inter Milan",
    "internazionale": "Inter Milan",
    "galatasaray": "Galatasaray",
    "besiktas": "Besiktas",
    "fenerbahce": "Fenerbahce",
    "ajax": "Ajax",
    "psv": "PSV",
    "porto fc": "Porto",
    "sporting cp": "Sporting CP",
    "sporting": "Sporting CP",
    "benfica": "Benfica",
    # Brazilian clubs
    "fla": "Flamengo",
    "flamengo": "Flamengo",
    "palmeiras": "Palmeiras",
    "sao paulo": "Sao Paulo",
    "são paulo": "Sao Paulo",
    "corinthians": "Corinthians",
    "timao": "Corinthians",
    "fluminense": "Fluminense",
    "flu": "Fluminense",
    "vasco": "Vasco",
    # Botafogo RJ (default bare name) vs Botafogo-PB — more specific keys first via exact match
    "botafogo": "Botafogo",
    "botafogo rj": "Botafogo",
    "botafogo fr": "Botafogo",
    "botafogo pb": "Botafogo PB",
    "botafogo-pb": "Botafogo PB",
    "botafogo paraiba": "Botafogo PB",
    "botafogo da paraiba": "Botafogo PB",
    "botafogo-paraiba": "Botafogo PB",
    "belo": "Botafogo PB",
    "confianca": "Confianca",
    "confiança": "Confianca",
    "ad confianca": "Confianca",
    "ad confiança": "Confianca",
    "associacao desportiva confianca": "Confianca",
    "sao bernardo": "Sao Bernardo",
    "são bernardo": "Sao Bernardo",
    "cuiaba": "Cuiaba",
    "cuiabá": "Cuiaba",
    "atletico-mg": "Atletico Mineiro",
    "atlético-mg": "Atletico Mineiro",
    "atletico mineiro": "Atletico Mineiro",
    "atlético mineiro": "Atletico Mineiro",
    "galo": "Atletico Mineiro",
    "cruzeiro": "Cruzeiro",
    "gremio": "Gremio",
    "grêmio": "Gremio",
    "internacional": "Internacional",
    "inter de porto alegre": "Internacional",
    "bragantino": "Bragantino",
    "fortaleza": "Fortaleza",
    "bahia": "Bahia",
    "sport": "Sport Recife",
    "ceara": "Ceara",
    "ceará": "Ceara",
    # National teams (PT → EN)
    "brasil": "Brazil",
    "selecao": "Brazil",
    "seleção": "Brazil",
    "franca": "France",
    "frança": "France",
    "alemanha": "Germany",
    "espanha": "Spain",
    "italia": "Italy",
    "itália": "Italy",
    "holanda": "Netherlands",
    "belgica": "Belgium",
    "bélgica": "Belgium",
    "croacia": "Croatia",
    "croácia": "Croatia",
    "polonia": "Poland",
    "polônia": "Poland",
    "suica": "Switzerland",
    "suíça": "Switzerland",
    "dinamarca": "Denmark",
    "suecia": "Sweden",
    "suécia": "Sweden",
    "noruega": "Norway",
    "marrocos": "Morocco",
    "nigeria": "Nigeria",
    "nigéria": "Nigeria",
    "egito": "Egypt",
    "arabia saudita": "Saudi Arabia",
    "arabia saudita": "Saudi Arabia",
    "japao": "Japan",
    "japão": "Japan",
    "coreia do sul": "South Korea",
    "coreia": "South Korea",
    "australia": "Australia",
    "austrália": "Australia",
    "estados unidos": "USA",
    "eua": "USA",
    "argentina": "Argentina",
    "uruguai": "Uruguay",
    "chile": "Chile",
    "colombia": "Colombia",
    "colômbia": "Colombia",
    "mexico": "Mexico",
    "méxico": "Mexico",
    "senegal": "Senegal",
    "ghana": "Ghana",
    "gana": "Ghana",
    "egito": "Egypt",
    "russia": "Russia",
    "rússia": "Russia",
    "turquia": "Turkey",
    "ucrania": "Ukraine",
    "ucrânia": "Ukraine",
    "austria": "Austria",
    "áustria": "Austria",
    "hungria": "Hungary",
    "escocia": "Scotland",
    "escócia": "Scotland",
    "wales": "Wales",
    "pais de gales": "Wales",
    "país de gales": "Wales",
    "irlanda": "Ireland",
    "republica tcheca": "Czech Republic",
    "republica checa": "Czech Republic",
    "eslováquia": "Slovakia",
    "eslovaquia": "Slovakia",
    "eslovenia": "Slovenia",
    "eslovênia": "Slovenia",
    "romenia": "Romania",
    "romênia": "Romania",
    "servia": "Serbia",
    "sérvia": "Serbia",
    # Missing European national teams
    "inglaterra": "England",
    "gales": "Wales",
    "grecia": "Greece",
    "grécia": "Greece",
    "finlandia": "Finland",
    "finlândia": "Finland",
    "islandia": "Iceland",
    "islândia": "Iceland",
    "albania": "Albania",
    "albânia": "Albania",
    "georgia": "Georgia",
    "geórgia": "Georgia",
    "azerbaijao": "Azerbaijan",
    "azerbaijão": "Azerbaijan",
    "armenia": "Armenia",
    "armênia": "Armenia",
    "bielorrussia": "Belarus",
    "bielorrussia": "Belarus",
    "irlanda do norte": "Northern Ireland",
    "luxemburgo": "Luxembourg",
    "macedonia": "North Macedonia",
    "macedônia": "North Macedonia",
    "norte da macedonia": "North Macedonia",
    "canada": "Canada",
    # South American / CONMEBOL
    "equador": "Ecuador",
    "equadór": "Ecuador",
    "paraguai": "Paraguay",
    "peru": "Peru",
    "venezuela": "Venezuela",
    "bolivia": "Bolivia",
    "bolívia": "Bolivia",
    # Asian / Others
    "coreia do norte": "Korea DPR",
    "corea do norte": "Korea DPR",
    "china": "China",
    "india": "India",
    "índia": "India",
    "africa do sul": "South Africa",
    "áfrica do sul": "South Africa",
    "costa rica": "Costa Rica",
    "nova zelandia": "New Zealand",
    "nova zelândia": "New Zealand",
    # Chilean clubs (API often uses Ñublense / O'Higgins)
    "nublense": "Nublense",
    "ñublense": "Nublense",
    "cd nublense": "Nublense",
    "ohiggins": "O'Higgins",
    "o higgins": "O'Higgins",
    "o'higgins": "O'Higgins",
    "cd ohiggins": "O'Higgins",
    "club deportivo ohiggins": "O'Higgins",
}


def _alias_keys(name: str) -> list[str]:
    """Build lookup keys: raw, spaced, ascii, compacted (no spaces/hyphens/apostrophes)."""
    import unicodedata
    key = name.lower().strip()
    key = re.sub(r"[''`´’]", "", key)                 # drop apostrophes
    key_spaced = re.sub(r"[-_]+", " ", key)
    key_spaced = re.sub(r"\s+", " ", key_spaced).strip()
    ascii_spaced = (
        unicodedata.normalize("NFKD", key_spaced)
        .encode("ascii", "ignore")
        .decode()
    )
    compact = re.sub(r"[\s\-_]+", "", ascii_spaced)
    out: list[str] = []
    for k in (key, key_spaced, ascii_spaced, compact, name.lower().strip()):
        if k and k not in out:
            out.append(k)
    return out


def normalize_team_name(name: str) -> str:
    """Resolve common aliases and accented variants to their API-Football canonical name."""
    import logging as _logging
    _log = _logging.getLogger(__name__)

    keys = _alias_keys(name)
    for candidate in keys:
        if candidate in _TEAM_ALIASES:
            _log.warning(
                "[AUDIT] normalize_team_name: %r → %r (alias key=%r)",
                name, _TEAM_ALIASES[candidate], candidate,
            )
            return _TEAM_ALIASES[candidate]

    # Title-case spaced form without apostrophes/hyphens noise
    spaced = keys[1] if len(keys) > 1 else (keys[0] if keys else name)
    display = " ".join(w.capitalize() for w in spaced.split()) if spaced else name
    _log.warning("[AUDIT] normalize_team_name: %r → NO ALIAS → %r", name, display)
    return display


# ---------------------------------------------------------------------------
# Command-prefix stripper — removes "Analisar / Veja / Quero ver" etc.
# from the beginning of a team-name capture group.
# ---------------------------------------------------------------------------
_CMD_PREFIX_RE = re.compile(
    r"^(?:"
    r"analis[ae]r?|analise|analisa|analyz[ei](?:ng|e\s+me)?|"
    r"veja|mostre?|mostra|avalie?|avalia|"
    r"preveja?|prever|previs[aã]o\s+(?:de\s+)?|"
    r"quero\s+(?:ver|analisar|analisa)|"
    r"me\s+(?:d[eê]|mostr[ae]|fale\s+(?:sobre\s+)?|analise)|"
    r"pode(?:ria)?\s+analisar|"
    r"what\s+about|show\s+me|give\s+me|run|check|forecast|predict|analyse?|"
    r"intelligence|report|assess(?:ment)?|"
    r"como\s+est[aá]\s+"
    r")\s*",
    re.IGNORECASE,
)


def _clean_team(name: str) -> str:
    """Strip trailing punctuation and leading command words."""
    name = re.sub(r"[?.!,;:]+$", "", name).strip()
    name = _CMD_PREFIX_RE.sub("", name).strip()
    name = re.sub(r"[?.!,;:]+$", "", name).strip()
    return name


_GREETING_RE = re.compile(
    r"^(?:hi|hello|hey|oi|ol[aá]|bom\s+(?:dia|tarde|noite)|good\s+(?:morning|afternoon|evening|day)|howdy|yo|e\s+a[íi])(?:\s+aurora)?\W*$",
    re.IGNORECASE,
)
_HELP_RE = re.compile(
    r"(?:^help$|what\s+can\s+(?:you|aurora)\s+do|commands|options|capabilities|^menu$|"
    r"^ajuda$|o\s+que\s+voc[eê]\s+(?:faz|pode)|como\s+(?:funciona|usar)\s+a?\s*aurora|^comandos?$)",
    re.IGNORECASE,
)
_LIVE_RE = re.compile(
    r"(?:best\s+)?live\s+(?:opportunities|matches|games|bets|now)|"
    r"what(?:'s|\s+is)\s+(?:currently\s+)?live|"
    r"live\s+right\s+now|"
    r"^live\??$|"
    r"any(?:thing)?\s+live|"
    r"tem\s+(?:algo|alguma\s+coisa|oportunidades?)\s+ao\s+vivo|"
    r"(?:melhores\s+)?oportunidades?\s+ao\s+vivo|"
    r"partidas?\s+ao\s+vivo|"
    r"jogos?\s+ao\s+vivo|"
    r"o\s+que\s+(?:est[aá]|tem)\s+(?:rolando\s+)?ao\s+vivo|"
    r"^ao\s+vivo\??$",
    re.IGNORECASE,
)
_BANKROLL_RE = re.compile(
    r"(?:review|check|show|how\s+(?:is|am)\s+(?:my|i))\s+(?:my\s+)?bankroll|"
    r"bankroll\s+(?:status|review|health|summary|check)|"
    r"how\s+am\s+i\s+doing|"
    r"my\s+performance|"
    r"\broi\b|"
    r"\bprofit\b|"
    r"results\s+(?:so\s+far|today)?|"
    r"(?:revisar?|ver|checar|como\s+est[aá])\s+(?:minha\s+)?banca|"
    r"(?:minha\s+)?banca\s+(?:atual|hoje|status|resumo)|"
    r"como\s+estou\s+(?:indo|me\s+saindo)?|"
    r"meu\s+desempenho|"
    r"meus\s+resultados",
    re.IGNORECASE,
)
_LEARNING_RE = re.compile(
    r"what\s+did\s+(?:aurora\s+)?learn(?:ed)?(?:\s+today)?|"
    r"learning\s+(?:recap|summary|today|history)|"
    r"aurora(?:'s)?\s+(?:performance|track\s+record)|"
    r"accuracy\s+(?:today|summary)|"
    r"what\s+did\s+you\s+learn|"
    r"o\s+que\s+a?\s*aurora\s+aprendeu|"
    r"resumo\s+de\s+aprendizado|"
    r"aprendizado\s+(?:de\s+hoje|resumo)?|"
    r"o\s+que\s+voc[eê]\s+aprendeu",
    re.IGNORECASE,
)
_EXPLAIN_RE = re.compile(
    r"explain\s+(?:the\s+)?(?:last\s+)?(?:recommendation|call|pick)|"
    r"why\s+(?:did\s+you|aurora)\s+(?:recommend|suggest|pick)|"
    r"explain\s+(?:the\s+)?confidence|"
    r"tell\s+me\s+(?:more|why)|"
    r"more\s+details?|"
    r"explique\s+(?:a\s+)?(?:recomenda[cç][aã]o|an[aá]lise|confian[cç]a)|"
    r"por\s+que\s+(?:voc[eê]\s+)?recomendou|"
    r"me\s+explique\s+(?:mais|isso|a\s+recomenda[cç][aã]o)|"
    r"mais\s+detalhes",
    re.IGNORECASE,
)
_KNOWLEDGE_RE = re.compile(
    r"what\s+(?:do\s+you|does\s+aurora)\s+know\s+about\s+(.+)|"
    r"(?:explain|tell\s+me\s+about)\s+(.+?)\s+(?:market|rule|strategy|knowledge|system)|"
    r"(?:how\s+does|what\s+is|what\s+are)\s+(.+?)(?:\s+work(?:s)?|\s+mean(?:s)?|\?)?$|"
    r"knowledge\s+(?:about|on)\s+(.+)|"
    r"aurora(?:'s)?\s+rule\s+(?:on|for|about)\s+(.+)|"
    r"o\s+que\s+voc[eê]\s+sabe\s+sobre\s+(.+)|"
    r"me\s+(?:fale|conte)\s+(?:sobre\s+)?(.+?)\s*\??$|"
    r"explique\s+(?:o\s+que\s+[eé]\s+|o\s+)?(.+?)\s*\??$|"
    r"como\s+funciona\s+(?:o\s+|a\s+)?(.+?)\s*\??$",
    re.IGNORECASE,
)

# Match patterns — ordered from most specific to least specific.
# Groups 1 and 2 must always be home and away team names.
# _clean_team will strip any leaked command prefix words.
_MATCH_PATTERNS = [
    # PT command verbs: Analise/Analisar + TeamA SEP TeamB
    re.compile(rf"analis[ae]r?\s+(.+?)\s+{_SEP}\s+(.+)", re.IGNORECASE),
    # EN command verbs: Analyze/Analyse + TeamA SEP TeamB
    re.compile(rf"analyz[ei](?:ng|e\s+me)?\s+(.+?)\s+{_SEP}\s+(.+)", re.IGNORECASE),
    # PT/EN veja / show me / what about + TeamA SEP TeamB
    re.compile(
        rf"(?:veja|mostre?|mostra|avalie?|avalia|preveja?|prever|"
        rf"what\s+about|show\s+me|give\s+me)\s+(.+?)\s+{_SEP}\s+(.+)",
        re.IGNORECASE,
    ),
    # EN intelligence/report/assess/predict etc.
    re.compile(
        rf"(?:intelligence|report|assess(?:ment)?|predict(?:ion)?|check|forecast|score)\s+(.+?)\s+{_SEP}\s+(.+)",
        re.IGNORECASE,
    ),
    # TeamA SEP TeamB + trailing keyword (PT + EN)
    re.compile(
        rf"(.+?)\s+{_SEP}\s+(.+?)\s+(?:an[aá]lise|analis[ae]|analysis|analyz[ei]|"
        rf"intelligence|prediction|previs[aã]o|forecast|report)\W*$",
        re.IGNORECASE,
    ),
    # Bare "TeamA x/vs/contra TeamB" — must come last; _clean_team strips stray prefixes
    re.compile(rf"^(.+?)\s+{_SEP}\s+(.+)$", re.IGNORECASE),
]


def _extract_knowledge_query(message: str) -> str:
    m = _KNOWLEDGE_RE.search(message)
    if m:
        for g in m.groups():
            if g:
                return _clean_team(g).strip("?")
    # fallback: strip common prefixes
    cleaned = re.sub(
        r"^(?:what|how|tell|explain|me\s+(?:fale|conte|explique)|o\s+que|como)\s+\w+\s+",
        "", message, flags=re.IGNORECASE,
    )
    return cleaned.strip("?").strip() or message.strip()


def detect_intent(message: str) -> tuple[str, dict]:
    """
    Parse a natural-language message and return (intent_name, entities_dict).

    Priority: greeting → help → explain_last → live → bankroll → learning
              → match_patterns → knowledge → unknown

    NOTE: match_patterns now runs BEFORE knowledge so that
    "Explique Arsenal x Chelsea" is treated as a match query, not a knowledge query.
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

    # Match patterns run BEFORE knowledge so "explique Arsenal x Chelsea" is a match,
    # not a knowledge query.
    for pat in _MATCH_PATTERNS:
        m = pat.search(msg)
        if m:
            home = normalize_team_name(_clean_team(m.group(1)))
            away = normalize_team_name(_clean_team(m.group(2)))
            # Sanity check: both extracted, non-empty, and different
            if home and away and home.lower() != away.lower() and len(home) >= 2 and len(away) >= 2:
                return "analyze_match", {"home": home, "away": away}

    if _KNOWLEDGE_RE.search(msg):
        return "knowledge_search", {"query": _extract_knowledge_query(msg)}

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
            f"**Recomendação principal:** {report.primary_recommendation}",
            f"**Confiança:** {report.overall_confidence}/10 · **Risco:** {report.risk_level}",
            "",
        ]

    # Top factors
    lines.append("**Principais fatores:**")
    for f in report.main_factors[:3]:
        lines.append(f"  {f}")
    lines.append("")

    # Positive signals (condensed)
    pos = [p for p in report.positive_factors if not p.startswith("• No category")]
    if pos:
        lines.append("**Sinais favoráveis:**")
        for p in pos[:2]:
            lines.append(f"  {p}")
        lines.append("")

    # Risk flags (condensed)
    risks = [r for r in report.risk_factors if not r.startswith("• No critical")]
    if risks:
        lines.append("**Riscos a considerar:**")
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
        "**Stake recomendada:**",
        f"  {stake_first}",
    ]
    if stake_examples:
        lines.append(f"  {stake_examples}")
    lines.append("")

    # Alternatives (condensed)
    alts = [a for a in report.alternative_markets if not a.startswith("No alternative")]
    if alts:
        lines.append("**Mercados alternativos:**")
        for a in alts[:2]:
            lines.append(f"  • {a[:180]}")
        lines.append("")

    # Invalidation teaser
    if report.invalidation_conditions:
        lines += [
            "**O que poderia mudar esta análise:**",
            f"  {report.invalidation_conditions[0][:220]}",
            "",
        ]

    # Footer
    lines += [
        "---",
        f"*Sessão `{session_id}` · Pergunte: \"explicar confiança\", \"quais são os riscos?\", ou analise outra partida.*",
    ]

    return "\n".join(lines)


def _fmt_live(live_data: dict, session_id: str) -> str:
    fixtures = live_data.get("live_matches", [])
    if not fixtures:
        return (
            "**Nenhuma partida ao vivo no momento.**\n\n"
            "Volte em breve, ou peça para analisar uma partida:\n"
            "*\"Analisar [Time da Casa] x [Time Visitante]\"*"
        )

    count = len(fixtures)
    lines = [f"**Ao vivo agora — {count} partida{'s' if count != 1 else ''}**", ""]

    for fx in fixtures[:5]:
        hn = (fx.get("teams", {}).get("home", {}) or {}).get("name", "Casa")
        an = (fx.get("teams", {}).get("away", {}) or {}).get("name", "Fora")
        minute = (fx.get("status") or {}).get("minute", "?")
        score_h = (fx.get("score", {}).get("current") or {}).get("home", 0)
        score_a = (fx.get("score", {}).get("current") or {}).get("away", 0)
        league = (fx.get("league") or {}).get("name", "")
        league_str = f" ({league})" if league else ""

        lines.append(f"**{hn} {score_h}–{score_a} {an}**{league_str} · Minuto {minute}")

        # Pull best stat hint
        hs = (fx.get("stats") or {}).get("home") or {}
        corners = hs.get("corners") or 0
        if corners:
            lines.append(f"  Corners: {corners} | ")

        lines.append("")

    if count > 5:
        lines.append(f"*+{count - 5} partidas ao vivo adicionais.*")
        lines.append("")

    lines += [
        "**Quer uma análise completa?** Pergunte:",
        "*\"Analisar [Time da Casa] x [Time Visitante]\"*",
        "",
        "---",
        f"*Sessão `{session_id}`*",
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

    lines = ["**Revisão de Banca e Desempenho**", ""]

    if total == 0:
        lines += [
            "A Aurora ainda não registrou nenhuma previsão nesta sessão.",
            "Cada previsão é rastreada automaticamente — comece analisando uma partida.",
            "",
            f"*Sessão `{session_id}`*",
        ]
        return "\n".join(lines)

    decided = wins + losses
    lines += [
        f"**{total} previsões monitoradas** — {wins}V / {losses}D / {pending} pendentes",
        f"**Precisão:** {acc_str}",
        f"**ROI:** {roi_str}",
        "",
    ]

    if best_m:
        lines.append(f"**Melhor mercado:** {best_m.replace('_', ' ').title()}")
    if worst_m and worst_m != best_m:
        lines.append(f"**Mercado mais fraco:** {worst_m.replace('_', ' ').title()} — aborde com cautela extra")
    if best_l:
        lines.append(f"**Liga mais forte:** {best_l}")
    lines.append("")

    # Avaliação qualitativa
    if acc is not None:
        if acc >= 60:
            verdict = (
                f"A Aurora está performando bem com {acc:.1f}% de precisão. "
                f"Mantenha a disciplina — siga o plano de stake pelo Critério de Kelly."
            )
        elif acc >= 45:
            verdict = (
                f"Desempenho de {acc:.1f}% está levemente abaixo da meta de 55%+. "
                f"Revise quais mercados estão perdendo e considere reduzir exposição."
            )
        else:
            verdict = (
                f"Precisão de {acc:.1f}% está abaixo do esperado. "
                f"A Aurora recomenda modo de proteção: reduza todas as stakes pela metade "
                f"e aposte apenas em mercados com confiança ≥ 7,0 até a sequência melhorar."
            )
        lines += [verdict, ""]

    # Breakdown de mercados
    breakdown = stats.get("market_breakdown", [])
    if breakdown:
        lines.append("**Breakdown de mercados (top 3 por precisão):**")
        for r in breakdown[:3]:
            rule = r.get("rule", "").replace("_", " ").title()
            mkt_acc = r.get("accuracy", 0)
            mkt_w = r.get("wins", 0)
            mkt_l = r.get("losses", 0)
            lines.append(f"  • {rule}: {mkt_acc:.1f}% ({mkt_w}V/{mkt_l}D)")
        lines.append("")

    lines += [
        "---",
        f"*Sessão `{session_id}` · Pergunte: \"O que a Aurora aprendeu?\" ou analise uma partida.*",
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

    lines = ["**Resumo de Aprendizado da Aurora**", ""]

    if total == 0:
        lines += [
            "Nenhuma previsão foi resolvida ainda.",
            "A Aurora começa a aprender automaticamente assim que os resultados das partidas chegam.",
            "Cada previsão é rastreada — o motor de aprendizado atualiza em tempo real.",
            "",
            f"*Sessão `{session_id}`*",
        ]
        return "\n".join(lines)

    decided = wins + losses
    acc_str = f"{acc:.1f}%" if acc is not None else "pendente"
    lines += [
        f"**Histórico de previsões:** {total} total — {wins}V / {losses}D / {pending} pendentes",
        f"**Precisão atual:** {acc_str}",
        "",
    ]

    if breakdown:
        lines.append("**O que está funcionando:**")
        for r in [x for x in breakdown if x.get("wins", 0) > 0][:3]:
            rule = r.get("rule", "").replace("_", " ").title()
            lines.append(f"  ✓ {rule} — {r.get('accuracy', 0):.1f}% precisão ({r.get('wins', 0)}V/{r.get('losses', 0)}D)")
        lines.append("")

        losing = [x for x in breakdown if x.get("losses", 0) > x.get("wins", 0)]
        if losing:
            lines.append("**O que precisa de atenção:**")
            for r in losing[:2]:
                rule = r.get("rule", "").replace("_", " ").title()
                lines.append(f"  ✗ {rule} — {r.get('accuracy', 0):.1f}% precisão ({r.get('wins', 0)}V/{r.get('losses', 0)}D)")
            lines.append("")

    if league_br:
        lines.append("**Desempenho por liga:**")
        for lg in league_br[:3]:
            lines.append(
                f"  • {lg.get('league', 'Desconhecida')}: "
                f"{lg.get('accuracy', 0):.1f}% ({lg.get('wins', 0)}V/{lg.get('losses', 0)}D)"
            )
        lines.append("")

    lines += [
        "A Aurora aprende continuamente — cada partida resolvida atualiza o modelo de precisão.",
        "Mudanças de peso no motor de metodologia requerem 20+ observações consistentes.",
        "",
        "---",
        f"*Sessão `{session_id}` · Pergunte: \"Revisar banca\" ou analise uma partida para adicionar mais dados.*",
    ]
    return "\n".join(lines)


def _fmt_knowledge(results: list, query: str, session_id: str) -> str:
    if not results:
        return (
            f"**Nenhum conhecimento encontrado para \"{query}\"**\n\n"
            f"A base de conhecimento da Aurora cobre: metodologia, regras de apostas, gestão de banca, "
            f"regras de mercado, regras ao vivo, regras pré-jogo, tendências de árbitros, perfis de ligas, "
            f"padrões de equipes, psicologia, gestão de risco, alertas vermelhos e regras de ouro.\n\n"
            f"Tente: *\"O que você sabe sobre BTTS?\"* ou *\"Explique o Critério de Kelly\"*\n\n"
            f"---\n*Sessão `{session_id}`*"
        )

    lines = [f"**Conhecimento Aurora — \"{query}\"**", f"*{len(results)} item(ns) relevante(s) encontrado(s)*", ""]

    for item in results[:4]:
        cat = item.get("category", "").replace("_", " ").title()
        title = item.get("title", "")
        desc = item.get("description", "")
        conf = item.get("confidence", 0)
        examples_raw = item.get("examples", [])

        lines += [
            f"**{title}** · *{cat}* · Confiança {conf:.0%}",
            desc,
        ]
        if examples_raw and isinstance(examples_raw, list):
            lines.append(f"*Exemplo: {examples_raw[0][:150]}*")
        lines.append("")

    lines += [
        "---",
        f"*Sessão `{session_id}` · Estas regras são aplicadas antes de cada recomendação da Aurora.*",
    ]
    return "\n".join(lines)


def _fmt_explain(report: Any, session_id: str) -> str:
    """Focused explanation using the confidence + main factors sections."""
    lines = [
        f"**Explicando: {report.match}**",
        f"*Recomendação: {report.primary_recommendation} | Confiança {report.overall_confidence}/10*",
        "",
    ]

    lines += [report.confidence_explanation, ""]

    lines.append("**Principais fatores:**")
    for f in report.main_factors[:5]:
        lines.append(f"  {f}")
    lines.append("")

    lines.append("**O que poderia mudar esta análise:**")
    for c in report.invalidation_conditions[:3]:
        lines.append(f"  • {c[:200]}")
    lines.append("")

    lines += [
        "---",
        f"*Sessão `{session_id}` · Pergunte: \"quais são os riscos?\" ou analise outra partida.*",
    ]
    return "\n".join(lines)


def _fmt_greeting(session_id: str) -> str:
    return (
        "Olá! Sou a **Aurora**, sua assistente de inteligência esportiva.\n\n"
        "Combino dados ao vivo, gols esperados (xG), padrões históricos "
        "e 39 regras metodológicas de apostas para oferecer análises de nível profissional.\n\n"
        "**O que você pode me perguntar:**\n"
        "  • *\"Analisar Arsenal x Chelsea\"* — relatório completo de inteligência\n"
        "  • *\"Melhores oportunidades ao vivo\"* — oportunidades em partidas ao vivo\n"
        "  • *\"Revisar banca\"* — desempenho das suas previsões\n"
        "  • *\"O que a Aurora aprendeu hoje?\"* — resumo de aprendizado e precisão\n"
        "  • *\"O que você sabe sobre BTTS?\"* — buscar na base de conhecimento\n"
        "  • *\"Explique a recomendação\"* — análise aprofundada da última chamada\n\n"
        "**Por onde começar?** Tente: *\"Analisar [Time da Casa] x [Time Visitante]\"*\n\n"
        "---\n"
        f"*Sessão `{session_id}` iniciada.*"
    )


def _fmt_help(session_id: str) -> str:
    return (
        "**Aurora — Comandos Disponíveis**\n\n"
        "| Comando | Exemplo |\n"
        "|---|---|\n"
        "| Analisar partida | *\"Analisar Palmeiras x Flamengo\"* |\n"
        "| Oportunidades ao vivo | *\"Melhores oportunidades ao vivo\"* |\n"
        "| Revisão de banca | *\"Revisar banca\"* |\n"
        "| Resumo de aprendizado | *\"O que a Aurora aprendeu hoje?\"* |\n"
        "| Busca de conhecimento | *\"O que você sabe sobre escanteios?\"* |\n"
        "| Explicar última análise | *\"Explique a recomendação\"* |\n\n"
        "**Linguagem natural funciona:** Não é preciso usar comandos exatos. "
        "Tente *\"Man City x Arsenal\"*, *\"como estão meus resultados?\"*, ou *\"por que você escolheu esse mercado?\"*\n\n"
        "**Cada análise inclui:**\n"
        "  • Recomendação principal com probabilidade e valor esperado\n"
        "  • 7 fatores classificados por contribuição\n"
        "  • Recomendação de stake pelo Critério de Kelly\n"
        "  • Mercados alternativos\n"
        "  • Alertas de risco e condições de invalidação\n\n"
        "---\n"
        f"*Sessão `{session_id}`*"
    )


def _fmt_unknown(message: str, session_id: str) -> str:
    return (
        f"Não entendi bem: *\"{message[:120]}\"*\n\n"
        "**Tente uma dessas opções:**\n"
        "  • *\"Analisar [Casa] x [Fora]\"* — análise de partida\n"
        "  • *\"Melhores oportunidades ao vivo\"* — partidas ao vivo\n"
        "  • *\"Revisar banca\"* — desempenho\n"
        "  • *\"Ajuda\"* — lista completa de comandos\n\n"
        "---\n"
        f"*Sessão `{session_id}`*"
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
            f"A Aurora encontrou um erro ao processar sua solicitação: {exc}\n\n"
            "Por favor, tente novamente. Se o erro persistir, verifique o nome da partida ou tente uma consulta diferente.\n\n"
            f"---\n*Sessão `{session_id}`*"
        )


async def _handle_analyze(entities: dict, session_id: str) -> str:
    home = entities.get("home", "")
    away = entities.get("away", "")
    if not home or not away:
        return (
            "Por favor, especifique os dois times: *\"Analisar [Time da Casa] x [Time Visitante]\"*\n\n"
            f"---\n*Sessão `{session_id}`*"
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
            "Nenhuma partida recente para explicar. Primeiro analise uma partida:\n"
            "*\"Analisar [Time da Casa] x [Time Visitante]\"*\n\n"
            f"---\n*Sessão `{session_id}`*"
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
            "Por favor, especifique sobre o que você quer saber:\n"
            "*\"O que você sabe sobre [tópico]?\"*\n\n"
            f"---\n*Sessão `{session_id}`*"
        )
    from src.knowledge_db import search_knowledge_items
    results = search_knowledge_items(query, limit=4)
    return _fmt_knowledge(results, query, session_id)
