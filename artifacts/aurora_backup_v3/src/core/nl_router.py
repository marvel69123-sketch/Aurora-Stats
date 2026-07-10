"""
Aurora Natural Language Router — Phase 1.

Classifies free-form messages into intents with a confidence score.
Uses text normalisation (lowercase, accent removal, punctuation stripping)
and weighted keyword / pattern matching so that approximate phrases are
accepted without requiring exact spelling.

Public API
----------
  route(message: str) -> RouteResult

  RouteResult.intent      — detected intent name (or "unknown" when confidence < 0.25)
  RouteResult.entities    — extracted entities dict (home/away teams, query text, …)
  RouteResult.confidence  — routing confidence 0.0–1.0

Intents
-------
  greeting          — hi, olá, bom dia …
  identity          — quem é você, o que é aurora, se apresente …
  capabilities      — o que você faz, como funciona, quais recursos …
  bankroll_review   — como está minha banca, roi, performance …
  learning_recap    — o que você aprendeu, histórico, aprendizados …
  live_opportunities— jogos ao vivo, tem jogo agora …
  knowledge_search  — explique BTTS, o que você sabe sobre escanteios …
  analyze_match     — Arsenal x Chelsea, Analisar PSG contra Bayern …
  unknown           — confidence < 0.25; do not forward to any pipeline

Routing priority when two classifiers score the same:
  analyze_match > knowledge_search > greeting > identity > capabilities
  > live_opportunities > bankroll_review > learning_recap
"""
from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class RouteResult:
    intent: str
    entities: dict
    confidence: float


# ---------------------------------------------------------------------------
# Text normalisation
# ---------------------------------------------------------------------------

_PUNCTUATION_RE = re.compile(r"[^\w\s-]")  # keep hyphens (team names like "Atlético-MG")
_WHITESPACE_RE  = re.compile(r"\s+")


def normalize(text: str) -> str:
    """
    Normalise a message for pattern matching.

    Steps:
      1. Lowercase
      2. Remove accents (NFKD decomposition → drop combining chars)
      3. Replace punctuation with spaces (hyphens preserved)
      4. Collapse whitespace / strip
    """
    text = text.lower().strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = _PUNCTUATION_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text


# ---------------------------------------------------------------------------
# Keyword scorer
# ---------------------------------------------------------------------------

def _kw_score(norm: str, phrases: list[tuple[str, float]]) -> float:
    """
    Return the highest weight among all phrases that match inside *norm*.

    Each phrase must appear as a whole-word sequence (word-boundary anchored).
    Shorter single-word phrases match as individual tokens.
    """
    best = 0.0
    for phrase, weight in phrases:
        # Escape and anchor with word boundaries
        pattern = r"(?<!\w)" + re.escape(phrase) + r"(?!\w)"
        if re.search(pattern, norm):
            logger.debug("      kw_score hit  %r → %.2f", phrase, weight)
            best = max(best, weight)
    return best


# ---------------------------------------------------------------------------
# Team separator & command-prefix patterns (on normalised text)
# ---------------------------------------------------------------------------

# Separators accepted in match analysis
_SEP_RE = re.compile(r"\b(x|vs|contra|versus)\b")

# Prefixes to strip from the LEFT side of the separator to expose the home team.
# Also strips knowledge-query prefixes so "Explique Arsenal x Chelsea" works.
_CMD_STRIP_RE = re.compile(
    r"^(?:"
    # Portuguese match commands
    r"quero\s+(?:analisar|ver|analise|analisa|que\s+voce\s+analise)\s*|"
    r"quero\s+|"
    r"analis[ae]r?\s+|"
    r"analise\s+|"
    r"analisa\s+|"
    r"estudar?\s+|"
    r"prever?\s+|"
    r"previsao\s+(?:de\s+)?|"
    r"pode(?:ria)?\s+(?:analisar\s+)?|"
    # Knowledge/explain verbs that precede team names
    r"me\s+expliq(?:ue|a)\s+|"
    r"expliq(?:ue|a)\s+|"
    r"me\s+fale\s+sobre\s+|"
    r"fale\s+sobre\s+|"
    r"me\s+conte\s+sobre\s+|"
    r"conte\s+sobre\s+|"
    r"me\s+mostre?\s+|"
    r"mostre?\s+|"
    r"me\s+(?:analise|de)\s+|"
    # English commands
    r"show\s+me\s+|"
    r"what\s+about\s+|"
    r"give\s+me\s+|"
    r"predict\s+|"
    r"forecast\s+|"
    r"analys[ei]\s+|"
    r"check\s+|"
    r"run\s+"
    r")",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Team alias resolution — thin wrapper around copilot_engine helpers
# ---------------------------------------------------------------------------

def _resolve_team(name: str) -> str:
    """
    Look up the extracted (normalised-lowercase) team name against the alias
    table, returning the canonical API-Football name.  Falls back to
    title-casing if no alias is found.
    """
    # Import lazily to avoid circular dependency issues at module load time
    from src.core.copilot_engine import normalize_team_name
    resolved = normalize_team_name(name.strip())
    if resolved.lower() == name.strip().lower():
        # No alias found — title-case each word
        return " ".join(w.capitalize() for w in name.strip().split())
    return resolved


def _has_alias(name: str) -> bool:
    """Return True when the normalised name maps to a known alias."""
    from src.core.copilot_engine import _TEAM_ALIASES
    key = name.strip().lower()
    # Direct key check
    if key in _TEAM_ALIASES:
        return True
    # ASCII fallback (strip any residual accents)
    ascii_key = (
        unicodedata.normalize("NFKD", key)
        .encode("ascii", "ignore")
        .decode()
    )
    return ascii_key in _TEAM_ALIASES


# ---------------------------------------------------------------------------
# Per-intent classifiers
# Each returns (confidence: float, entities: dict)
# ---------------------------------------------------------------------------

# ── Greeting ────────────────────────────────────────────────────────────────

_GREETING_PHRASES: list[tuple[str, float]] = [
    ("ola", 0.97), ("oi", 0.97), ("hi", 0.97), ("hello", 0.97),
    ("hey", 0.93), ("howdy", 0.92), ("yo", 0.88), ("e ai", 0.90),
    ("bom dia", 0.96), ("boa tarde", 0.96), ("boa noite", 0.96),
    ("good morning", 0.96), ("good afternoon", 0.96), ("good evening", 0.96),
    ("good day", 0.93),
]


def _clf_greeting(norm: str) -> tuple[float, dict]:
    # Greetings are short — penalise long messages
    if len(norm.split()) > 8:
        return 0.0, {}
    score = _kw_score(norm, _GREETING_PHRASES)
    return score, {}


# ── Identity ────────────────────────────────────────────────────────────────

_IDENTITY_PHRASES: list[tuple[str, float]] = [
    ("quem e voce", 0.98),
    ("quem e aurora", 0.98),
    ("o que e aurora", 0.97),
    ("o que e voce", 0.90),
    ("se apresente", 0.96),
    ("se identifique", 0.95),
    ("fale sobre voce", 0.92),
    ("fale sobre a aurora", 0.95),
    ("me fale sobre voce", 0.92),
    ("me fale sobre aurora", 0.95),
    ("quem sou", 0.72),
    ("quem eh voce", 0.98),
    ("who are you", 0.97),
    ("what is aurora", 0.97),
    ("introduce yourself", 0.96),
    ("tell me about yourself", 0.92),
    ("tell me about aurora", 0.95),
]


def _clf_identity(norm: str) -> tuple[float, dict]:
    return _kw_score(norm, _IDENTITY_PHRASES), {}


# ── Capabilities ─────────────────────────────────────────────────────────────

_CAPABILITIES_PHRASES: list[tuple[str, float]] = [
    ("o que voce faz", 0.96),
    ("o que voce pode fazer", 0.96),
    ("como voce funciona", 0.92),
    ("quais recursos voce possui", 0.98),
    ("quais recursos", 0.90),
    ("no que pode ajudar", 0.96),
    ("no que voce pode ajudar", 0.98),
    ("o que pode fazer", 0.92),
    ("o que sabe fazer", 0.90),
    ("como posso usar", 0.87),
    ("como usar aurora", 0.88),
    ("what can you do", 0.97),
    ("what do you do", 0.94),
    ("capabilities", 0.93),
    ("comandos", 0.82),
    ("opcoes", 0.80),
    ("ajuda", 0.72),
    ("help", 0.72),
    ("menu", 0.72),
]


def _clf_capabilities(norm: str) -> tuple[float, dict]:
    score = _kw_score(norm, _CAPABILITIES_PHRASES)
    # "como funciona" with no trailing topic → treat as a capabilities question
    if score == 0.0 and re.fullmatch(r"como\s+funciona(?:\s+(?:a|o)?\s*aurora)?\s*", norm):
        logger.debug("      _clf_capabilities: 'como funciona' bare match → 0.82")
        score = 0.82
    return score, {}


# ── Bankroll review ──────────────────────────────────────────────────────────

_BANKROLL_PHRASES: list[tuple[str, float]] = [
    ("como esta minha banca", 0.98),
    ("como esta a banca", 0.97),
    ("revisar banca", 0.96),
    ("revisar minha banca", 0.97),
    ("ver banca", 0.90),
    ("ver minha banca", 0.92),
    ("mostrar desempenho", 0.92),
    ("ver desempenho", 0.90),
    ("minha banca", 0.88),
    ("banca atual", 0.92),
    ("resumo da banca", 0.95),
    ("status da banca", 0.95),
    ("roi atual", 0.96),
    ("roi", 0.84),
    ("performance", 0.82),
    ("desempenho", 0.80),
    ("resultados atuais", 0.90),
    ("meus resultados", 0.87),
    ("bankroll", 0.93),
    ("como estou indo", 0.87),
    ("como estou me saindo", 0.88),
    ("quanto tenho na banca", 0.95),
    ("my bankroll", 0.94),
    ("bankroll status", 0.96),
    ("bankroll review", 0.97),
    ("bankroll health", 0.96),
    ("review bankroll", 0.96),
    ("check bankroll", 0.93),
    ("show bankroll", 0.93),
    ("how am i doing", 0.87),
    ("my performance", 0.82),
    ("profit", 0.79),
]


def _clf_bankroll(norm: str) -> tuple[float, dict]:
    return _kw_score(norm, _BANKROLL_PHRASES), {}


# ── Learning recap ───────────────────────────────────────────────────────────

_LEARNING_PHRASES: list[tuple[str, float]] = [
    ("mostrar historico", 0.93),
    ("ver historico", 0.91),
    ("historico de previsoes", 0.95),
    ("mostrar aprendizados", 0.96),
    ("ver aprendizados", 0.93),
    ("o que voce aprendeu", 0.97),
    ("o que aprendeu", 0.93),
    ("o que aurora aprendeu", 0.98),
    ("o que a aurora aprendeu", 0.98),
    ("o que a aurora aprendeu hoje", 0.99),
    ("o que voce aprendeu hoje", 0.98),
    ("aprendizados", 0.86),
    ("aprendizado", 0.82),
    ("desempenho anterior", 0.91),
    ("historico", 0.78),
    ("acertos anteriores", 0.88),
    ("resumo de aprendizado", 0.95),
    ("what did you learn", 0.97),
    ("learning recap", 0.97),
    ("learning summary", 0.95),
    ("learning history", 0.93),
    ("track record", 0.86),
    ("accuracy summary", 0.93),
    ("aurora performance", 0.90),
    ("aurora aprendeu", 0.92),
    ("a aurora aprendeu", 0.93),
]


def _clf_learning(norm: str) -> tuple[float, dict]:
    return _kw_score(norm, _LEARNING_PHRASES), {}


# ── Live opportunities ───────────────────────────────────────────────────────

_LIVE_PHRASES: list[tuple[str, float]] = [
    ("jogos ao vivo", 0.98),
    ("partidas ao vivo", 0.98),
    ("oportunidades ao vivo", 0.98),
    ("melhores oportunidades ao vivo", 0.99),
    ("melhores oportunidades", 0.91),
    ("ao vivo", 0.88),
    ("tem jogo agora", 0.96),
    ("tem jogo", 0.82),
    ("o que esta rolando", 0.90),
    ("o que tem ao vivo", 0.92),
    ("jogos agora", 0.92),
    ("partidas agora", 0.92),
    ("tem algo ao vivo", 0.96),
    ("o que esta acontecendo", 0.82),
    ("best live", 0.93),
    ("live matches", 0.96),
    ("live opportunities", 0.98),
    ("live right now", 0.97),
    ("anything live", 0.93),
    ("live", 0.80),
]


def _clf_live(norm: str) -> tuple[float, dict]:
    return _kw_score(norm, _LIVE_PHRASES), {}


# ── Knowledge search ─────────────────────────────────────────────────────────

_KNOWLEDGE_PHRASES: list[tuple[str, float]] = [
    ("o que voce sabe sobre", 0.96),
    ("o que sabe sobre", 0.94),
    ("me fale sobre", 0.88),
    ("fale sobre", 0.82),
    ("me conte sobre", 0.88),
    ("conte sobre", 0.82),
    ("conhecimento sobre", 0.92),
    ("regra sobre", 0.90),
    ("what do you know about", 0.96),
    ("knowledge about", 0.94),
    ("knowledge on", 0.93),
    ("tell me about", 0.86),
    ("aurora rule on", 0.93),
    ("aurora rule for", 0.93),
]

# Lower-weight single-word / prefix triggers that still push toward knowledge
_KNOWLEDGE_WEAK_PHRASES: list[tuple[str, float]] = [
    ("explique", 0.78),
    ("explica", 0.76),
    ("como funciona", 0.75),
    ("o que e o", 0.72),
    ("o que e a", 0.72),
    ("o que sao", 0.72),
    ("explain", 0.74),
    ("how does", 0.70),
    ("what is", 0.66),
]

# Regex to extract the topic after known knowledge prefixes
_KNOWLEDGE_TOPIC_RE = re.compile(
    r"(?:sobre|about|de|on|regarding)\s+(.+?)(?:\s*\??\s*$)"
    r"|(?:expliq(?:ue|a)|explain|conte|tell\s+me\s+about)\s+(.+?)(?:\s*\??\s*$)",
    re.IGNORECASE,
)


def _clf_knowledge(norm: str, original: str) -> tuple[float, dict]:
    # Strong keyword match
    score = _kw_score(norm, _KNOWLEDGE_PHRASES)
    if score == 0.0:
        # Try weaker single-word triggers
        score = _kw_score(norm, _KNOWLEDGE_WEAK_PHRASES)
        # "como funciona" with NO topic following → not a knowledge query (it's a capabilities query)
        if score > 0 and re.fullmatch(r"como\s+funciona(?:\s+(?:a|o)\s+aurora)?\s*", norm):
            logger.debug("      _clf_knowledge: 'como funciona' alone → skip (no topic)")
            score = 0.0

    if score == 0.0:
        return 0.0, {}

    # Extract the topic string
    query = ""
    m = _KNOWLEDGE_TOPIC_RE.search(norm)
    if m:
        for g in m.groups():
            if g:
                query = g.strip().rstrip("?").strip()
                break

    if not query:
        # Strip common interrogative prefix to isolate topic
        query = re.sub(
            r"^(?:o\s+que\s+voce\s+sabe\s+sobre|o\s+que\s+sabe\s+sobre|"
            r"me\s+fale\s+sobre|fale\s+sobre|me\s+conte\s+sobre|conte\s+sobre|"
            r"expliq(?:ue|a)|como\s+funciona|o\s+que\s+e|o\s+que\s+sao|"
            r"what\s+do\s+you\s+know\s+about|tell\s+me\s+about|explain|"
            r"knowledge\s+(?:about|on))\s+",
            "", norm, count=1, flags=re.IGNORECASE,
        ).strip().rstrip("?").strip()

    return score, {"query": query or norm.rstrip("?").strip()}


# ── Match analysis ───────────────────────────────────────────────────────────

def _clf_match(norm: str) -> tuple[float, dict]:
    """
    Detect a match-analysis request.

    Algorithm:
      1. Search for a separator token (x, vs, contra, versus).
      2. Split into left (home) and right (away) parts.
      3. Strip any command/knowledge prefix from the left side.
      4. Validate that both parts look like team names (length / word count).
      5. Resolve aliases → canonical names.
      6. Score based on: separator present, command prefix used, alias hit.
    """
    sep_m = _SEP_RE.search(norm)
    if not sep_m:
        logger.debug("      _clf_match: no separator in %r", norm)
        return 0.0, {}

    sep_start, sep_end = sep_m.span()
    left_raw  = norm[:sep_start].strip()
    right_raw = norm[sep_end:].strip()

    logger.debug("      _clf_match: sep=%r left=%r right=%r", sep_m.group(), left_raw, right_raw)

    # Strip command/knowledge prefix from the left side
    stripped_left = _CMD_STRIP_RE.sub("", left_raw, count=1).strip()
    had_prefix = stripped_left != left_raw
    if had_prefix:
        logger.debug("      _clf_match: stripped prefix → left=%r", stripped_left)
    left = stripped_left

    # Validation
    if not left or not right_raw:
        logger.debug("      _clf_match: empty side after strip (left=%r right=%r)", left, right_raw)
        return 0.0, {}

    if len(left) < 2 or len(right_raw) < 2:
        logger.debug("      _clf_match: side too short")
        return 0.0, {}

    left_words  = left.split()
    right_words = right_raw.split()

    if len(left_words) > 6:
        # Too many words for a team name — likely a sentence fragment
        logger.debug("      _clf_match: left too many words (%d)", len(left_words))
        return 0.35, {}

    if len(right_words) > 6:
        logger.debug("      _clf_match: right too many words (%d)", len(right_words))
        return 0.35, {}

    # Resolve to canonical names
    home = _resolve_team(left)
    away = _resolve_team(right_raw)

    if home.lower() == away.lower():
        logger.debug("      _clf_match: home == away after alias resolution (%r)", home)
        return 0.0, {}

    # Confidence scoring
    #   - bare separator alone:           0.84
    #   - with command prefix:            0.92
    #   - each known-alias hit:          +0.03 each (max +0.06)
    base = 0.92 if had_prefix else 0.84
    alias_boost = 0.0
    if _has_alias(left):
        alias_boost += 0.03
        logger.debug("      _clf_match: home alias hit → +0.03")
    if _has_alias(right_raw):
        alias_boost += 0.03
        logger.debug("      _clf_match: away alias hit → +0.03")

    conf = min(1.0, base + alias_boost)

    logger.debug(
        "      _clf_match: home=%r away=%r conf=%.3f (base=%.2f alias_boost=%.2f had_prefix=%s)",
        home, away, conf, base, alias_boost, had_prefix,
    )

    return conf, {"home": home, "away": away}


# ---------------------------------------------------------------------------
# Priority tie-breaker order when confidences are equal
# ---------------------------------------------------------------------------

_PRIORITY: dict[str, int] = {
    "analyze_match":    100,
    "knowledge_search": 90,
    "greeting":         80,
    "identity":         75,
    "capabilities":     70,
    "live_opportunities": 65,
    "bankroll_review":  60,
    "learning_recap":   55,
}


# ---------------------------------------------------------------------------
# Main route function
# ---------------------------------------------------------------------------

def route(message: str) -> RouteResult:
    """
    Route a natural-language message to an intent.

    Returns a RouteResult with intent, entities, and confidence (0–1).
    Returns intent="unknown" only when the best confidence < 0.25.

    Logs:
      INFO  — final routing decision
      DEBUG — per-classifier scores and intermediate steps
    """
    original = message.strip()
    norm     = normalize(original)

    logger.info("NLRouter.route ← %r", original)
    logger.debug("NLRouter.route   normalised=%r", norm)

    if not norm:
        logger.warning("NLRouter.route: empty input → unknown")
        return RouteResult("unknown", {}, 0.0)

    # ── Run all classifiers ──────────────────────────────────────────────────
    raw_classifiers: list[tuple[str, tuple[float, dict]]] = [
        ("greeting",            _clf_greeting(norm)),
        ("identity",            _clf_identity(norm)),
        ("capabilities",        _clf_capabilities(norm)),
        ("bankroll_review",     _clf_bankroll(norm)),
        ("learning_recap",      _clf_learning(norm)),
        ("live_opportunities",  _clf_live(norm)),
        ("knowledge_search",    _clf_knowledge(norm, original)),
        ("analyze_match",       _clf_match(norm)),
    ]

    candidates: list[tuple[float, int, str, dict]] = []
    for intent, (conf, entities) in raw_classifiers:
        logger.debug("  [%-20s] conf=%.3f  entities=%s", intent, conf, entities)
        if conf > 0.0:
            priority = _PRIORITY.get(intent, 0)
            candidates.append((conf, priority, intent, entities))

    if not candidates:
        logger.info("NLRouter.route → unknown (no classifiers fired, conf=0.0)")
        return RouteResult("unknown", {}, 0.0)

    # Sort: primary key = confidence (desc), secondary = priority (desc)
    candidates.sort(key=lambda t: (t[0], t[1]), reverse=True)

    top_conf, top_priority, top_intent, top_entities = candidates[0]

    # Build a readable log of all candidates for easy debugging
    _cand_log = ", ".join(
        f"{i}={c:.2f}" for c, _, i, _ in candidates
    )
    logger.info(
        "NLRouter.route → intent=%s  conf=%.3f  entities=%s | all=[%s]",
        top_intent, top_conf, top_entities, _cand_log,
    )

    if top_conf < 0.25:
        logger.info(
            "NLRouter.route: best conf %.3f < 0.25 → unknown", top_conf
        )
        return RouteResult("unknown", top_entities, top_conf)

    return RouteResult(top_intent, top_entities, top_conf)
