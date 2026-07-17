"""
Aurora v4.3 — Conversational Understanding Engine (CUE).

Turns raw text into a structured ConversationIntent:
  explicit_goal, implicit_goal, entities, temporal_context, emotional_tone, confidence

Additive. Fail-open. Does NOT edit State / CRL / Reasoner / FollowUp / Resolver.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

logger = logging.getLogger(__name__)

CUE_CTX_KEY = "conversation_intent"

SocialIntent = Literal[
    "GREETING",
    "WELL_BEING_CHECK",
    "THANKS",
    "FAREWELL",
    "CASUAL_CHAT",
    "NONE",
]

ExplicitGoal = Literal[
    "ASK_FUTURE_ANALYSIS",
    "ASK_ANALYSIS",
    "ASK_OPINION",
    "ASK_EXPLANATION",
    "ASK_RISK_EVAL",
    "ASK_BETTER_OPTION",
    "COMPARE",
    "REJECT",
    "SOCIAL",
    "UNKNOWN",
]


def _fold(text: str) -> str:
    t = unicodedata.normalize("NFKD", (text or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^\w\sx/-]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


@dataclass
class ConversationIntent:
    explicit_goal: ExplicitGoal | str = "UNKNOWN"
    implicit_goal: str = ""
    entities: dict[str, Any] = field(default_factory=dict)
    temporal_context: str | None = None  # today | tomorrow | weekend | next | round | None
    emotional_tone: str = "neutral"
    confidence: float = 0.0
    social_intents: list[str] = field(default_factory=list)
    understood_intent: str = ""
    implicit_meaning: str = ""
    rewrite_for_pipeline: str | None = None
    signals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_TEMPORAL = [
    (re.compile(r"\bamanha\b", re.I), "tomorrow"),
    (re.compile(r"\bhoje\b", re.I), "today"),
    (re.compile(r"\bfim\s+de\s+semana\b|\bfinal\s+de\s+semana\b|\bfinde\b", re.I), "weekend"),
    (re.compile(r"\bproxima?\s+rodada\b|\bessa\s+rodada\b|\bnesta\s+rodada\b", re.I), "round"),
    (re.compile(r"\bproximo\s+jogo\b|\bna\s+proxima\b", re.I), "next"),
]

_TEAM_NAMES: dict[str, str] = {
    "bahia": "Bahia",
    "chapecoense": "Chapecoense",
    "chape": "Chapecoense",
    "flamengo": "Flamengo",
    "fla": "Flamengo",
    "botafogo": "Botafogo",
    "fogao": "Botafogo",
    "santos": "Santos",
    "peixe": "Santos",
    "vasco": "Vasco",
    "vascao": "Vasco",
    "palmeiras": "Palmeiras",
    "corinthians": "Corinthians",
    "sao paulo": "Sao Paulo",
    "fluminense": "Fluminense",
    "gremio": "Gremio",
    "internacional": "Internacional",
    "atletico mineiro": "Atletico Mineiro",
    "cruzeiro": "Cruzeiro",
    "fortaleza": "Fortaleza",
    "vitoria": "Vitoria",
}


def _extract_temporal(folded: str) -> str | None:
    for pat, label in _TEMPORAL:
        if pat.search(folded):
            return label
    return None


def _extract_teams(folded: str) -> list[str]:
    """Extract up to 2 teams in left-to-right appearance order."""
    hits: list[tuple[int, str]] = []
    seen: set[str] = set()

    def _add(pos: int, name: str) -> None:
        if name in seen:
            return
        seen.add(name)
        hits.append((pos, name))

    for key in sorted(_TEAM_NAMES.keys(), key=len, reverse=True):
        for m in re.finditer(rf"(?<!\w){re.escape(key)}(?!\w)", folded):
            _add(m.start(), _TEAM_NAMES[key])
    try:
        from src.conversation.state_driven_resolution import SPORTS_ALIASES

        for key, canon in sorted(SPORTS_ALIASES.items(), key=lambda kv: -len(kv[0])):
            fk = _fold(key)
            for m in re.finditer(rf"(?<!\w){re.escape(fk)}(?!\w)", folded):
                _add(m.start(), canon)
    except Exception:
        pass

    hits.sort(key=lambda x: x[0])
    ordered: list[str] = []
    for _, name in hits:
        if name not in ordered:
            ordered.append(name)
        if len(ordered) >= 2:
            break
    return ordered


def _social_intents(folded: str) -> list[str]:
    intents: list[str] = []
    if re.search(
        r"\b(oi|ola|hey|hello|hi|bom\s+dia|boa\s+tarde|boa\s+noite)\b",
        folded,
    ):
        intents.append("GREETING")
    if re.search(
        r"\b(tudo\s+bem|td\s+bem|como\s+(?:voce\s+)?(?:esta|vai)|e\s+ai|e\s+ai)\b",
        folded,
    ):
        intents.append("WELL_BEING_CHECK")
    if re.search(r"\b(obrigad[oa]|valeu|thanks|brigado)\b", folded):
        intents.append("THANKS")
    if re.search(r"\b(tchau|ate\s+mais|ate\s+logo|flw|falou)\b", folded):
        intents.append("FAREWELL")
    # Pure casual short chat without sports markers
    if (
        intents
        and not re.search(r"\b(gol|escanteio|analis|aposta|mercado|x|vs)\b", folded)
        and len(folded.split()) <= 10
    ):
        if "CASUAL_CHAT" not in intents and "GREETING" in intents:
            intents.append("CASUAL_CHAT")
    return intents


def _emotional_tone(folded: str) -> str:
    if re.search(r"\b(nao\s+gostei|ruim|odio|absurdo)\b", folded):
        return "negative"
    if re.search(r"\b(obrigad|valeu|otimo|bora|legal)\b", folded):
        return "positive"
    if re.search(r"\b(duvida|sera|talvez|nao\s+sei)\b", folded):
        return "uncertain"
    if re.search(r"\b(tudo\s+bem|oi|ola|boa\s+noite)\b", folded):
        return "friendly"
    return "neutral"


def understand(message: str, ctx: dict[str, Any] | None = None) -> ConversationIntent:
    """
    Main CUE entry. Fail-open → UNKNOWN intent with low confidence.
    """
    try:
        original = (message or "").strip()
        folded = _fold(original)
        social = _social_intents(folded)
        temporal = _extract_temporal(folded)
        teams = _extract_teams(folded)
        tone = _emotional_tone(folded)
        signals: list[str] = []

        intent = ConversationIntent(
            social_intents=social,
            temporal_context=temporal,
            emotional_tone=tone,
            entities={},
        )

        # Social-first for short well-being / greetings
        if social and not teams and not re.search(
            r"\b(analis|escanteio|gol|mercado|aposta|fale\s+sobre|comente)\b",
            folded,
        ):
            intent.explicit_goal = "SOCIAL"
            intent.implicit_goal = "+".join(social).lower()
            intent.understood_intent = "+".join(social)
            intent.implicit_meaning = (
                "Usuário cumprimenta e/ou pergunta como a Aurora está — "
                "espera reciprocidade humana, não apresentação de produto."
            )
            intent.confidence = 0.92 if "WELL_BEING_CHECK" in social else 0.88
            intent.signals = social + ["cue_social"]
            if ctx is not None:
                ctx[CUE_CTX_KEY] = intent.to_dict()
            return intent

        # Semantic: speak/comment/analyze about a match
        talkish = bool(
            re.search(
                r"\b(fale\s+sobre|fala\s+sobre|fala\s+d[oe]|fale\s+d[oe]|comente|"
                r"comenta|analis[ae]r?|me\s+fala|me\s+diz|oq\s+acha|o\s+que\s+acha|"
                r"me\s+explica|explique)\b",
                folded,
            )
        )

        # "bahia e chapecoense" / "bahia x chapecoense"
        pair = re.search(
            r"\b([a-z0-9][a-z0-9.\s-]{1,30}?)\s+(?:e|x|vs|versus)\s+"
            r"([a-z0-9][a-z0-9.\s-]{1,30})\b",
            folded,
        )
        if pair and len(teams) < 2:
            # Re-resolve pair sides through team map
            left, right = pair.group(1).strip(), pair.group(2).strip()
            for raw in (left, right):
                # strip leading "jogo da/do"
                raw2 = re.sub(r"^(?:jogo\s+d[aoe]\s+|partida\s+d[aoe]\s+)", "", raw).strip()
                t2 = _extract_teams(raw2)
                for t in t2:
                    if t not in teams:
                        teams.append(t)
            if len(teams) < 2:
                # direct lookup
                for raw, fallback in ((left, left), (right, right)):
                    raw2 = re.sub(r"^(?:jogo\s+d[aoe]\s+)", "", raw).strip()
                    canon = _TEAM_NAMES.get(raw2) or _TEAM_NAMES.get(raw2.replace(" da ", " "))
                    if canon and canon not in teams:
                        teams.append(canon)

        if teams:
            intent.entities["teams"] = teams
        if len(teams) >= 2:
            intent.entities["home"] = teams[0]
            intent.entities["away"] = teams[1]
            intent.entities["fixture"] = f"{teams[0]} x {teams[1]}"

        if len(teams) >= 2 and (talkish or temporal or re.search(r"\bjogo\b|\bpartida\b", folded)):
            if temporal == "tomorrow" or temporal == "next":
                intent.explicit_goal = "ASK_FUTURE_ANALYSIS"
                intent.implicit_goal = "analyze_upcoming_fixture"
                intent.understood_intent = "ASK_FUTURE_ANALYSIS"
                intent.implicit_meaning = (
                    f"Usuário quer comentário/análise de {teams[0]} x {teams[1]}"
                    f" com referência temporal ({temporal})."
                )
            else:
                intent.explicit_goal = "ASK_ANALYSIS"
                intent.implicit_goal = "analyze_fixture"
                intent.understood_intent = "ASK_ANALYSIS"
                intent.implicit_meaning = (
                    f"Usuário pede para falar/analisar {teams[0]} x {teams[1]}."
                )
            intent.rewrite_for_pipeline = f"analise {teams[0]} x {teams[1]}"
            intent.confidence = 0.9
            intent.signals = signals + ["cue_fixture_talk", f"temporal:{temporal}"]
            if ctx is not None:
                ctx[CUE_CTX_KEY] = intent.to_dict()
                ctx["cue_temporal"] = temporal
            return intent

        # Opinion / risk / explain (implicit)
        if re.search(r"\b(vale\s+a\s+pena)\b", folded):
            intent.explicit_goal = "ASK_RISK_EVAL"
            intent.implicit_goal = "evaluate_recommendation_risk"
            intent.understood_intent = "ASK_RISK_EVAL"
            intent.implicit_meaning = "Quer saber se a aposta/recomendação compensa o risco."
            intent.confidence = 0.86
        elif re.search(r"\b(por\s+que|porque|explique|me\s+explica)\b", folded):
            intent.explicit_goal = "ASK_EXPLANATION"
            intent.implicit_goal = "explain_last_view"
            intent.understood_intent = "ASK_EXPLANATION"
            intent.implicit_meaning = "Quer o racional por trás da última leitura."
            intent.confidence = 0.85
        elif re.search(r"\b(oq\s+acha|o\s+que\s+acha|o\s+q\s+acha)\b", folded):
            intent.explicit_goal = "ASK_OPINION"
            intent.implicit_goal = "opinion_on_active_or_pending"
            intent.understood_intent = "ASK_OPINION"
            intent.implicit_meaning = "Pede opinião — usar contexto ativo/pending."
            intent.confidence = 0.84
        elif re.search(r"\b(qual\s+parece\s+melhor|compare|qual\s+dos\s+dois)\b", folded):
            intent.explicit_goal = "COMPARE"
            intent.implicit_goal = "compare_markets_or_fixtures"
            intent.understood_intent = "COMPARE"
            intent.implicit_meaning = "Comparação implícita no contexto da conversa."
            intent.confidence = 0.84
        elif re.search(r"\b(nao\s+gostei|parece\s+ruim)\b", folded):
            intent.explicit_goal = "REJECT"
            intent.implicit_goal = "seek_alternative"
            intent.understood_intent = "REJECT"
            intent.implicit_meaning = "Rejeita recomendação atual."
            intent.confidence = 0.88
        elif re.search(r"\b(tem\s+algo\s+melhor|algo\s+melhor)\b", folded):
            intent.explicit_goal = "ASK_BETTER_OPTION"
            intent.implicit_goal = "prefer_better_market"
            intent.understood_intent = "ASK_BETTER_OPTION"
            intent.implicit_meaning = "Busca alternativa melhor."
            intent.confidence = 0.85
        else:
            intent.explicit_goal = "UNKNOWN"
            intent.confidence = 0.35
            intent.understood_intent = "UNKNOWN"
            intent.implicit_meaning = "Sem intenção clara — deixar pipeline seguir."

        if social:
            intent.signals.extend(social)
        if temporal:
            intent.signals.append(f"temporal:{temporal}")
        if teams:
            intent.signals.append("has_teams")

        if ctx is not None:
            ctx[CUE_CTX_KEY] = intent.to_dict()
            if temporal:
                ctx["cue_temporal"] = temporal
        return intent
    except Exception as exc:
        logger.warning("conversational_understanding fail-open: %s", exc)
        intent = ConversationIntent(
            explicit_goal="UNKNOWN",
            confidence=0.0,
            understood_intent="UNKNOWN",
            implicit_meaning=f"fail_open: {exc}",
            signals=["fail_open"],
        )
        if ctx is not None:
            ctx[CUE_CTX_KEY] = intent.to_dict()
        return intent
