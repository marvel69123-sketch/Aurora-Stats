"""
Aurora Human Understanding — Intent Inference (not classical NLP).

Rule 1: What did a human mean? — BEFORE any engine.
Fail-open. Additive. Never invents fixtures/stats.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

CTX_KEY = "human_inference"

# Strong verbs — never ignore
_ANALYZE = re.compile(
    r"\b(analisar|analise|analiz|analyze|analys[e]?|avaliar|avalia|"
    r"leitura\s+(?:d[oe]|sobre)|breakdown)\b",
    re.I,
)
_OPINION = re.compile(
    r"\b(opiniao|acha|achas|achou|achando|pensa|penso|gosta|"
    r"fale\s+sobre|fala\s+sobre|me\s+fala|conta\s+(?:sobre|d[oe]))\b",
    re.I,
)
_MOMENT = re.compile(
    r"\b(como\s+(?:esta|vai)|momento(?:\s+atual)?|atualmente|agora|agr)\b",
    re.I,
)
_KICKOFF = re.compile(
    r"\b(horario|que\s+horas|joga\s+que\s+horas|kickoff|que\s+hora)\b",
    re.I,
)
_CALENDAR = re.compile(
    r"\b(tem\s+jogo|jogo\s+d[oe]|jogos?\s+(?:de\s+)?(?:hoje|amanha)|"
    r"proximo\s+jogo|agenda|quando\s+joga|joga\s+hoje|joga\s+amanha)\b",
    re.I,
)
_TEMPORAL = re.compile(r"\b(hoje|amanha|agora|agr|atualmente)\b", re.I)
_PAIR = re.compile(
    r"([A-Za-zÀ-ÿ][\wÀ-ÿ.'-]{1,28})\s+(?:x|X|vs\.?|versus)\s+"
    r"([A-Za-zÀ-ÿ][\wÀ-ÿ.'-]{1,28})",
    re.I,
)
_BARE_TEAM = re.compile(r"^[A-Za-zÀ-ÿ][\wÀ-ÿ.'\s-]{2,40}\??$", re.I)

_ENCYCLOPEDIA = re.compile(
    r"("
    r"é uma agremia[cç][aã]o|"
    r"é um clube de futebol|"
    r"Clube de Regatas do|"
    r"Football Club is |"
    r"is an? (?:Italian|English|Brazilian|Spanish) (?:football|soccer) club|"
    r"com sede na (?:cidade|cidade do)|"
    r"fundado em \d{4}"
    r")",
    re.I,
)


@dataclass
class HumanInference:
    literal: str
    what_user_said: str
    what_user_meant: str
    what_user_expects: list[str] = field(default_factory=list)
    human_goal: str = ""
    intent: str = "unknown"
    priority: str = "normal"
    home: str | None = None
    away: str | None = None
    team: str | None = None
    teams: list[str] = field(default_factory=list)
    confidence: float = 0.0
    rewrite: str | None = None
    strong_verb: str | None = None
    topic_kind: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


def _title(raw: str) -> str:
    t = (raw or "").strip(" ?!.,;:")
    if not t:
        return t
    # Keep known multi-word casing lightly
    return " ".join(w[:1].upper() + w[1:] for w in t.split())


def _resolve_team(raw: str) -> str | None:
    t = (raw or "").strip(" ?!.,;:")
    if len(t) < 2:
        return None
    try:
        from src.conversation.context_recovery import fuzzy_resolve_team

        hit = fuzzy_resolve_team(t)
        if hit:
            return hit
    except Exception:
        pass
    try:
        from src.conversation.conversational_understanding import (
            _TEAM_NAMES,
            _extract_teams,
        )

        found = _extract_teams(_fold(t))
        if found:
            return found[0]
        key = _fold(t)
        if key in _TEAM_NAMES:
            return _TEAM_NAMES[key]
    except Exception:
        pass
    # Accept unknown club names (Arsenal, Chelsea…) as titled tokens
    if re.match(r"^[A-Za-zÀ-ÿ][\wÀ-ÿ.'-]{1,28}$", t):
        return _title(t)
    return None


def _extract_pair(message: str) -> tuple[str, str] | None:
    m = _PAIR.search(message or "")
    if not m:
        return None
    home = _resolve_team(m.group(1))
    away = _resolve_team(m.group(2))
    if home and away and _fold(home) != _fold(away):
        return home, away
    return None


def _extract_single_team(message: str, folded: str) -> str | None:
    try:
        from src.conversation.conversational_understanding import _extract_teams

        teams = _extract_teams(folded)
        if len(teams) == 1:
            return teams[0]
    except Exception:
        pass
    # Bare token / short phrase
    cleaned = (message or "").strip(" ?!.,;:")
    if _BARE_TEAM.match(cleaned) and not _PAIR.search(cleaned):
        return _resolve_team(cleaned)
    return None


def infer_human_intent(
    message: str,
    ctx: dict[str, Any] | None = None,
) -> HumanInference:
    """
    Interpret what a human meant — strong verbs dominate.
    Prefers raw_user_message when recovery rewrote away strong verbs.
    """
    raw = ""
    if isinstance(ctx, dict):
        raw = str(ctx.get("raw_user_message") or "").strip()
    # Prefer raw when it still carries strong verbs that recovery stripped
    literal = (message or "").strip()
    if raw and raw != literal:
        raw_f = _fold(raw)
        msg_f = _fold(literal)
        if (
            (_MOMENT.search(raw_f) and not _MOMENT.search(msg_f))
            or (_ANALYZE.search(raw_f) and not _ANALYZE.search(msg_f))
            or (_OPINION.search(raw_f) and not _OPINION.search(msg_f))
            or (_KICKOFF.search(raw_f) and not _KICKOFF.search(msg_f))
        ):
            literal = raw
    folded = _fold(literal)
    pair = _extract_pair(literal)
    team = None if pair else _extract_single_team(literal, folded)
    recovery = (ctx or {}).get("context_recovery") or {}
    if not team and recovery.get("teams"):
        teams_r = list(recovery["teams"])
        if len(teams_r) == 1 and not pair:
            team = teams_r[0]
        elif len(teams_r) >= 2 and not pair:
            pair = (str(teams_r[0]), str(teams_r[1]))

    base = HumanInference(
        literal=literal,
        what_user_said=literal,
        what_user_meant=literal,
        confidence=0.4,
    )

    # ── Strong: ANALISAR (+ pair or recoverable teams) ───────────────────
    if _ANALYZE.search(folded):
        if pair:
            h, a = pair
            return HumanInference(
                literal=literal,
                what_user_said=literal,
                what_user_meant=f"analisar o confronto {h} x {a}",
                what_user_expects=[
                    "match_analysis",
                    "markets_or_reading",
                    "comparative_perspective",
                ],
                human_goal="analisar confronto",
                intent="match_analysis",
                priority="very_high",
                home=h,
                away=a,
                teams=[h, a],
                confidence=0.97,
                rewrite=f"analisar {h} x {a}",
                strong_verb="analisar",
                topic_kind="match_analysis",
            )
        if team:
            return HumanInference(
                literal=literal,
                what_user_said=literal,
                what_user_meant=f"análise aprofundada sobre {team}",
                what_user_expects=["team_analysis", "perspective", "recent_form"],
                human_goal=f"analisar {team}",
                intent="team_analysis",
                priority="very_high",
                team=team,
                teams=[team],
                confidence=0.9,
                rewrite=f"análise detalhada do {team}",
                strong_verb="analisar",
                topic_kind="moment",
            )

    # ── Strong: KICKOFF / HORÁRIO ────────────────────────────────────────
    if _KICKOFF.search(folded):
        subj = f"{pair[0]} x {pair[1]}" if pair else (team or "o jogo")
        return HumanInference(
            literal=literal,
            what_user_said=literal,
            what_user_meant=f"saber o horário de {subj}",
            what_user_expects=["kickoff_time", "fixture_confirmation"],
            human_goal="horário do jogo",
            intent="kickoff_lookup",
            priority="high",
            home=pair[0] if pair else None,
            away=pair[1] if pair else None,
            team=team,
            teams=list(pair) if pair else ([team] if team else []),
            confidence=0.9,
            strong_verb="horário",
            topic_kind="kickoff",
        )

    # ── Strong: CALENDAR cues ────────────────────────────────────────────
    if _CALENDAR.search(folded) or (
        pair and _TEMPORAL.search(folded) and not _ANALYZE.search(folded)
    ):
        if pair:
            h, a = pair
            when = "amanhã" if "amanha" in folded else "hoje" if "hoje" in folded else ""
            return HumanInference(
                literal=literal,
                what_user_said=literal,
                what_user_meant=f"ver se/quando joga {h} x {a} {when}".strip(),
                what_user_expects=["fixture_lookup", "kickoff_if_available"],
                human_goal="agenda/confronto",
                intent="calendar_or_fixture",
                priority="high",
                home=h,
                away=a,
                teams=[h, a],
                confidence=0.88,
                strong_verb="agenda",
                topic_kind="fixture",
            )
        if team:
            return HumanInference(
                literal=literal,
                what_user_said=literal,
                what_user_meant=f"ver agenda/jogo do {team}",
                what_user_expects=["team_calendar", "next_fixture"],
                human_goal=f"agenda do {team}",
                intent="calendar_or_fixture",
                priority="high",
                team=team,
                teams=[team],
                confidence=0.86,
                strong_verb="agenda",
                topic_kind="calendar",
            )

    # ── Strong: MOMENT / COMO ESTÁ ───────────────────────────────────────
    if _MOMENT.search(folded) and (team or pair):
        t = team or (pair[0] if pair else None)
        return HumanInference(
            literal=literal,
            what_user_said=literal,
            what_user_meant=f"entender o momento atual do {t}",
            what_user_expects=[
                "recent_form",
                "moment",
                "analysis",
                "perspective",
            ],
            human_goal=f"momento do {t}",
            intent="team_moment",
            priority="high",
            team=t,
            teams=[t] if t else [],
            confidence=0.92,
            rewrite=f"como está o {t} atualmente?",
            strong_verb="como está",
            topic_kind="moment",
        )

    # ── Strong: OPINION ──────────────────────────────────────────────────
    if _OPINION.search(folded) and (team or pair):
        t = team or (pair[0] if pair else None)
        return HumanInference(
            literal=literal,
            what_user_said=literal,
            what_user_meant=f"opinião / conversa sobre {t}",
            what_user_expects=["perspective", "opinion", "context"],
            human_goal=f"falar sobre {t}",
            intent="general_team_talk",
            priority="high",
            team=t,
            teams=[t] if t else [],
            confidence=0.9,
            rewrite=f"o que acha do {t}?",
            strong_verb="opinião",
            topic_kind="opinion",
        )

    # ── Implicit: bare A x B → match analysis (human default) ────────────
    if pair and not _CALENDAR.search(folded) and not _KICKOFF.search(folded):
        h, a = pair
        return HumanInference(
            literal=literal,
            what_user_said=literal,
            what_user_meant=f"analisar o confronto {h} x {a}",
            what_user_expects=[
                "match_analysis",
                "markets_or_reading",
                "comparative_perspective",
            ],
            human_goal="analisar confronto",
            intent="match_analysis",
            priority="high",
            home=h,
            away=a,
            teams=[h, a],
            confidence=0.9,
            rewrite=f"analisar {h} x {a}",
            strong_verb=None,
            topic_kind="match_analysis",
        )

    # ── Implicit: bare team entity → general talk (NEVER "?") ────────────
    cleaned = literal.strip(" ?!.,;:")
    if team and (
        _BARE_TEAM.match(cleaned)
        or len(folded.split()) <= 3
        and not re.search(r"\b(como|oque|o\s+que|quando|onde|porque)\b", folded)
    ):
        # Avoid treating "e o Botafogo" as bare — that's a pivot (recovery handles)
        if re.search(r"^\s*e\s+(?:o|a|do|da)\s+", folded):
            return HumanInference(
                literal=literal,
                what_user_said=literal,
                what_user_meant=f"continuar a conversa sobre {team}",
                what_user_expects=["perspective", "opinion", "keep_intent"],
                human_goal=f"falar sobre {team}",
                intent="general_team_talk",
                priority="high",
                team=team,
                teams=[team],
                confidence=0.88,
                rewrite=f"o que acha do {team}?",
                topic_kind="opinion",
            )
        return HumanInference(
            literal=literal,
            what_user_said=literal,
            what_user_meant=f"falar sobre o {team}",
            what_user_expects=["general_overview", "perspective", "moment_hint"],
            human_goal=f"falar sobre o {team}",
            intent="general_team_talk",
            priority="high",
            team=team,
            teams=[team],
            confidence=0.9,
            rewrite=f"me fala sobre o {team}",
            topic_kind="opinion",
        )

    # Soft keep from prior focus
    focus = (ctx or {}).get("conversation_focus") or {}
    if focus.get("topic_team") and len(folded) < 24:
        t = str(focus["topic_team"])
        base.what_user_meant = f"continuidade sobre {t}"
        base.human_goal = f"continuar sobre {t}"
        base.intent = "follow_up"
        base.team = t
        base.confidence = 0.45
        base.topic_kind = focus.get("topic_kind") or "opinion"
        return base

    base.what_user_meant = "pedido ambíguo — tentar inferir antes de desistir"
    base.human_goal = "inferir intenção"
    base.intent = "unknown"
    return base


def apply_human_inference(
    message: str,
    ctx: dict[str, Any] | None,
) -> tuple[str, HumanInference]:
    """
    Persist inference on ctx and align DeepThinking / recovery.
    Returns (possibly rewritten message, inference).
    """
    inf = infer_human_intent(message, ctx)
    if ctx is None:
        return message, inf

    ctx[CTX_KEY] = inf.to_dict()

    # Align recovery teams
    recovery = dict(ctx.get("context_recovery") or {})
    if inf.teams:
        recovery["teams"] = list(inf.teams)
    if inf.intent == "match_analysis":
        recovery["inferred_goal"] = "match_analysis"
        recovery["topic_kind_hint"] = "match_analysis"
        recovery["confidence"] = max(float(recovery.get("confidence") or 0), inf.confidence)
    elif inf.intent in {"general_team_talk", "team_moment", "team_analysis"}:
        recovery["inferred_goal"] = "team_opinion"
        recovery["confidence"] = max(float(recovery.get("confidence") or 0), inf.confidence)
    elif inf.intent == "kickoff_lookup":
        recovery["inferred_goal"] = "kickoff_lookup"
    elif inf.intent == "calendar_or_fixture":
        recovery["inferred_goal"] = "calendar_or_fixture"
        recovery["topic_kind_hint"] = inf.topic_kind or "calendar"
    ctx["context_recovery"] = recovery

    # Align DeepThinking — match_analysis must NOT be calendar/fixture block
    thinking = dict(ctx.get("deep_thinking") or {})
    if inf.topic_kind:
        thinking["topic_kind"] = inf.topic_kind
    if inf.team:
        thinking["topic_team"] = inf.team
    if inf.teams:
        thinking["topic_teams"] = list(inf.teams)
    if inf.human_goal:
        thinking["user_real_want"] = inf.what_user_meant
        thinking["human_goal"] = inf.human_goal
    if inf.intent == "match_analysis":
        thinking["topic_kind"] = "match_analysis"
        thinking["web_need"] = "none"
        thinking["needs_web"] = False
        thinking["web_mode"] = "none"
        thinking["needs_inference"] = True
        thinking["surface_risk"] = 0.08
    elif inf.intent in {"general_team_talk", "team_moment", "team_analysis"}:
        thinking["web_need"] = thinking.get("web_need") or "optional"
        thinking["needs_web"] = True
        thinking["needs_inference"] = True
        thinking["surface_risk"] = min(float(thinking.get("surface_risk") or 0.5), 0.2)
    thinking["human_intent"] = inf.intent
    thinking["human_priority"] = inf.priority
    ctx["deep_thinking"] = thinking

    out = inf.rewrite or message
    logger.warning(
        "[AUDIT] HumanInference: intent=%s priority=%s goal=%r meant=%r "
        "home=%r away=%r team=%r conf=%.2f rewrite=%r",
        inf.intent,
        inf.priority,
        inf.human_goal,
        inf.what_user_meant,
        inf.home,
        inf.away,
        inf.team,
        inf.confidence,
        out if out != message else None,
    )
    return out, inf


def is_match_analysis(ctx: dict[str, Any] | None) -> bool:
    h = (ctx or {}).get(CTX_KEY) or {}
    return h.get("intent") == "match_analysis" or (
        ((ctx or {}).get("deep_thinking") or {}).get("topic_kind") == "match_analysis"
    )


def is_general_team_talk(ctx: dict[str, Any] | None) -> bool:
    h = (ctx or {}).get(CTX_KEY) or {}
    return h.get("intent") in {
        "general_team_talk",
        "team_moment",
        "team_analysis",
    }


def looks_like_encyclopedia_dump(text: str) -> bool:
    """Thinking Delay — institutional wiki blurbs are not intelligent answers."""
    t = (text or "").strip()
    if not t:
        return False
    if _ENCYCLOPEDIA.search(t):
        return True
    # Long first sentence that defines the institution
    first = t.split("\n")[0]
    if len(first) > 160 and re.search(
        r"\b(agremia[cç][aã]o|sede na|fundado|poliesportiv)\b", first, re.I
    ):
        return True
    return False


def thinking_delay_ok(text: str, ctx: dict[str, Any] | None = None) -> bool:
    """
    BEFORE answering: does this look like an intelligent reply?
    False → caller must regenerate / fall back.
    """
    t = (text or "").strip()
    if not t or t in {"?", ".", "-", "…", "..."}:
        return False
    if looks_like_encyclopedia_dump(t):
        logger.warning("[AUDIT] ThinkingDelay: FAIL encyclopedia_dump")
        return False
    # Never ship pure "?"
    if re.match(r"^\?\s*$", t):
        return False
    return True


def repair_unintelligent_reply(
    text: str,
    ctx: dict[str, Any] | None = None,
) -> str:
    """Replace encyclopedia / empty with human team talk."""
    if thinking_delay_ok(text, ctx):
        return text
    thinking = (ctx or {}).get("deep_thinking") or {}
    h = (ctx or {}).get(CTX_KEY) or {}
    team = (
        h.get("team")
        or thinking.get("topic_team")
        or (h.get("teams") or [None])[0]
        or "esse time"
    )
    moment = (h.get("intent") == "team_moment") or (
        thinking.get("topic_kind") == "moment"
    )
    try:
        from src.conversation.brain_authority import opinion_local_reasoning

        return opinion_local_reasoning(str(team), moment=bool(moment))
    except Exception:
        return (
            f"Sobre o {team}: eu olharia momento, ideia de jogo e o próximo "
            f"adversário — sem cravar um veredito engessado. "
            f"Quer aprofundar um confronto específico?"
        )
