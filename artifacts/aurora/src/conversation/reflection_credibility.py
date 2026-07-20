"""
Aurora v4.4 — Reflection + Credibility Layer.

Makes Aurora feel like she thinks before answering — without faking intelligence.

Pipeline (conceptual):
  Intent → Hypotheses → Reflection → Conclusion → Reply

Also controls display credibility:
  SOCIAL / FOLLOW_UP / REASONING / FULL_ANALYSIS

Additive. Fail-open.
Does NOT edit State / Reasoner / CIL / CRL / FollowUp / Resolver / Engines.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

logger = logging.getLogger(__name__)

REFLECTION_CTX_KEY = "conversation_reflection"
CREDIBILITY_META_KEY = "credibility"

DisplayMode = Literal["SOCIAL", "FOLLOW_UP", "REASONING", "FULL_ANALYSIS"]
Position = Literal["cautious", "favorable", "neutral", "reject", "none"]


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


def _ctx_view(ctx: dict[str, Any] | None) -> dict[str, Any]:
    ctx = ctx or {}
    out: dict[str, Any] = {
        "active_fixture": None,
        "active_market": None,
        "last_recommendation": None,
        "last_risk_level": None,
        "market_history": [],
        "home": None,
        "away": None,
    }
    try:
        from src.conversation.conversation_state import get_state

        st = get_state(ctx) or {}
        out["active_fixture"] = st.get("active_fixture") or ctx.get("last_match")
        out["active_market"] = st.get("active_market") or ctx.get("last_market")
        out["last_recommendation"] = st.get("last_recommendation") or ctx.get(
            "last_recommendation"
        )
        out["last_risk_level"] = st.get("last_risk_level") or ctx.get("last_risk")
        out["market_history"] = list(st.get("market_history") or [])
        out["home"] = st.get("active_home") or ctx.get("last_home")
        out["away"] = st.get("active_away") or ctx.get("last_away")
    except Exception:
        out["active_fixture"] = ctx.get("last_match")
        out["active_market"] = ctx.get("last_market")
        out["last_recommendation"] = ctx.get("last_recommendation")
        out["last_risk_level"] = ctx.get("last_risk")
    # Parse home/away from fixture label if missing
    fx = str(out.get("active_fixture") or "")
    if (not out.get("home") or not out.get("away")) and " x " in fx.lower():
        parts = re.split(r"\s+[xX]\s+", fx, maxsplit=1)
        if len(parts) == 2:
            out["home"] = out.get("home") or parts[0].strip()
            out["away"] = out.get("away") or parts[1].strip()
    return out


@dataclass
class ReflectionResult:
    user_real_intent: str = ""
    possible_answers: list[str] = field(default_factory=list)
    chosen_answer: str | None = None
    why_this_answer: str = ""
    confidence: float = 0.0
    position: Position = "none"
    risks: list[str] = field(default_factory=list)
    display_mode: DisplayMode = "FOLLOW_UP"
    thinking_label: str | None = None
    humanized_reply: str | None = None
    signals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── Intent classification for reflection ───────────────────────────────────

_SOCIAL_RE = re.compile(
    r"^(oi|ola|ol[aá]|tudo\s+bem|bom\s+dia|boa\s+tarde|boa\s+noite|"
    r"obrigad[oa]|valeu|flw|tchau|ate\s+mais|falou)\b",
    re.I,
)
_WORTH_IT_RE = re.compile(r"\b(vale\s+a\s+pena)\b", re.I)
_WHY_RE = re.compile(r"\b(por\s+que|porque|explique|me\s+explica)\b", re.I)
_CONSERVATIVE_RE = re.compile(
    r"\b(mais\s+conservador|mais\s+seguro|menor\s+risco|algo\s+mais\s+conservador)\b",
    re.I,
)
_WORRY_RE = re.compile(
    r"\b(o\s+que\s+mais\s+te\s+preocupa|o\s+que\s+te\s+preocupa|"
    r"qual\s+seu\s+medo|o\s+que\s+te\s+incomoda|preocupa)\b",
    re.I,
)
_OPINION_RE = re.compile(r"\b(oq\s+acha|o\s+que\s+acha|o\s+q\s+acha)\b", re.I)


def _detect_reflection_intent(
    message: str,
    ctx: dict[str, Any] | None,
) -> tuple[str, DisplayMode]:
    """Return (user_real_intent_key, display_mode_hint)."""
    cue = (ctx or {}).get("conversation_intent") or (ctx or {}).get("cue") or {}
    if isinstance(cue, dict):
        social = cue.get("social_intents") or []
        goal = str(cue.get("explicit_goal") or "")
        if goal == "SOCIAL" or social:
            return "social", "SOCIAL"
        if goal == "ASK_RISK_EVAL":
            return "worth_it", "REASONING"
        if goal == "ASK_EXPLANATION":
            return "why", "REASONING"
        if goal in {"ASK_OPINION"}:
            return "opinion", "REASONING"
        if goal in {"ASK_BETTER_OPTION", "REJECT"}:
            return "alternative", "FOLLOW_UP"

    folded = _fold(message)
    if _SOCIAL_RE.search(folded) or cue.get("explicit_goal") == "SOCIAL":
        return "social", "SOCIAL"
    if re.search(
        r"\b(mudaria\s+(?:a\s+)?(?:sua\s+)?opini|"
        r"mudar\s+de\s+(?:opini|ideia)|"
        r"invalidaria|abandonar\s+(?:esse\s+)?mercado|"
        r"o\s+que\s+faria\s+(?:voce\s+)?mudar|"
        r"o\s+que\s+te\s+faria\s+mudar)\b",
        folded,
    ):
        return "opinion_change", "REASONING"
    if _WORTH_IT_RE.search(folded):
        return "worth_it", "REASONING"
    if _WORRY_RE.search(folded):
        return "worry", "REASONING"
    if _WHY_RE.search(folded):
        return "why", "REASONING"
    if _CONSERVATIVE_RE.search(folded):
        return "conservative", "FOLLOW_UP"
    if re.search(r"\b(mais\s+agressivo|algo\s+mais\s+agressivo)\b", folded):
        return "aggressive", "FOLLOW_UP"
    if _OPINION_RE.search(folded):
        return "opinion", "REASONING"
    if re.search(r"\b(algo\s+melhor|nao\s+gostei)\b", folded):
        return "alternative", "FOLLOW_UP"

    thought = (ctx or {}).get("conversation_thought") or {}
    goal = ""
    if isinstance(thought, dict):
        goal = str(thought.get("user_intent") or "")
    if goal in {"ASK_BEST_OPTION", "ASK_SAFER_OPTION", "ASK_RISKIER_OPTION", "REJECT_MARKET"}:
        return "alternative", "FOLLOW_UP"
    if goal == "ASK_EXPLANATION":
        return "why", "REASONING"

    reasoning = (ctx or {}).get("last_reasoning") or {}
    if isinstance(reasoning, dict):
        mode_hint = str(reasoning.get("next_action") or "")
        if mode_hint in {"PREFER_CONSERVATIVE", "SEEK_ALTERNATIVE", "PREFER_BETTER"}:
            return "alternative", "FOLLOW_UP"

    return "generic_followup", "FOLLOW_UP"


def _risk_human(level: str | None) -> str:
    t = (level or "").strip().lower()
    if t in {"high", "alto"}:
        return "mais arriscado"
    if t in {"medium", "medio", "médio", "moderado"}:
        return "jogo equilibrado / risco moderado"
    if t in {"low", "baixo"}:
        return "perfil mais contido"
    return "incerto"


def _alts(bias: str, view: dict[str, Any]) -> list[str]:
    try:
        from src.conversation.state_driven_resolution import suggest_alternatives

        return suggest_alternatives(
            bias=bias,
            active_market=str(view.get("active_market") or "") or None,
            last_risk=str(view.get("last_risk_level") or "") or None,
            market_history=list(view.get("market_history") or []),
        )
    except Exception:
        if bias == "conservative":
            return ["under / linha mais baixa", "dupla chance", "stake reduzida"]
        return ["outra linha", "outro mercado", "stake reduzida"]


# ── Opinion Engine — position-taking replies ───────────────────────────────

def _reply_worth_it(view: dict[str, Any]) -> tuple[str, Position, list[str], str]:
    mkt = view.get("active_market") or "esse mercado"
    fx = view.get("active_fixture")
    risk = _risk_human(view.get("last_risk_level"))
    risks = [
        "entrada sem margem clara",
        f"leitura ainda {risk}",
    ]
    if fx:
        risks.append(f"cenário de {fx} pode virar rápido")

    body = (
        "Sendo sincera, eu teria cautela.\n\n"
        f"Vejo alguns pontos positivos em {mkt}"
        + (f" ({fx})" if fx else "")
        + ", mas não é um mercado que me daria muita confiança agora.\n\n"
        "O que eu faria: reduzir stake ou esperar um sinal mais limpo "
        "antes de entrar com convicção."
    )
    why = (
        f"Posição cautelosa porque o risco percebido é {risk} "
        f"e a pergunta pede recomendação + segurança, não só eco do mercado."
    )
    return body, "cautious", risks, why


def _reply_why(view: dict[str, Any]) -> tuple[str, Position, list[str], str]:
    mkt = view.get("active_market")
    fx = view.get("active_fixture")
    risk = _risk_human(view.get("last_risk_level"))
    risks = ["ritmo do jogo travar", "entrada sem invalidadores claros"]

    factors = []
    if mkt:
        factors.append(f"o que mais me chama atenção continua sendo {mkt}")
    else:
        factors.append("o que mais me chama atenção é o equilíbrio do confronto")
    factors.append(f"o risco que eu enxergo hoje é {risk}")
    if fx:
        factors.append(f"no contexto de {fx}, eu evitaria tratar isso como certeza")

    body = (
        "O que me faz pensar assim:\n"
        f"• Fatores: {factors[0]}.\n"
        f"• Risco: {factors[1]}.\n"
        f"• Cenário: {factors[2] if len(factors) > 2 else 'se o jogo ficar truncado, a leitura muda'}."
        "\n\n"
        "Se eu tivesse que escolher agora, seria cautelosa — "
        "não porque está 'errado', mas porque ainda falta uma margem mais confortável."
    )
    why = "Explicação com fatores/risco/cenário em vez de só repetir o nome do mercado."
    return body, "cautious", risks, why


def _reply_conservative(view: dict[str, Any]) -> tuple[str, Position, list[str], str]:
    fx = view.get("active_fixture")
    home = view.get("home")
    alts = _alts("conservative", view)
    concrete = alts[0] if alts else "uma linha mais baixa"
    # Prefer a concrete team-tied safer market when we have home
    if home:
        concrete_primary = f"{home} empate anula"
    else:
        concrete_primary = concrete

    body = (
        "Se eu quisesse reduzir risco, "
        f"olharia para {concrete_primary}"
        + (f" em {fx}" if fx else "")
        + ".\n\n"
        "Também faria sentido:\n"
        + "\n".join(f"• {a}" for a in alts[:2])
        + "\n\n"
        "Não é a aposta mais excitante — mas é o tipo de caminho "
        "que eu escolheria se quisesse dormir mais tranquila."
    )
    why = "Sugestão concreta conservadora ancorada no fixture/mercado ativos."
    risks = ["ainda assim pode empatar/virar", "linha conservadora também erra"]
    return body, "cautious", risks, why


def _reply_worry(view: dict[str, Any]) -> tuple[str, Position, list[str], str]:
    fx = view.get("active_fixture")
    mkt = view.get("active_market")
    body = (
        "O que mais me preocupa aqui é o ritmo do jogo.\n\n"
        "Se ele ficar travado, alguns mercados perdem valor rápido"
        + (f" — inclusive {mkt}" if mkt else "")
        + ".\n\n"
        + (
            f"Em {fx}, eu ficaria de olho nisso antes de aumentar confiança."
            if fx
            else "Eu ficaria de olho nisso antes de aumentar confiança."
        )
    )
    why = "Preocupação explícita (ritmo) com consequência nos mercados — raciocínio, não template."
    risks = ["jogo truncado", "mercado perde valor", "entrada precoce"]
    return body, "cautious", risks, why


def _reply_opinion(view: dict[str, Any]) -> tuple[str, Position, list[str], str]:
    fx = view.get("active_fixture") or "esse jogo"
    mkt = view.get("active_market")
    body = (
        "Se eu tivesse que escolher, eu seria cautelosa em "
        f"{fx}.\n\n"
        + (
            f"O que mais me chama atenção é {mkt} — mas não me anima o suficiente "
            "para entrar sem filtro.\n\n"
            if mkt
            else "Ainda não me anima o suficiente para entrar sem filtro.\n\n"
        )
        + "Quer que eu olhe um caminho mais seguro ou aprofunde o risco?"
    )
    why = "Opinião com posição clara + convite de follow-up."
    return body, "cautious", ["equilíbrio do confronto", "falta de margem"], why


def _reply_alternative(view: dict[str, Any], message: str) -> tuple[str, Position, list[str], str]:
    folded = _fold(message)
    bias = "better"
    if "conservador" in folded or "seguro" in folded:
        bias = "conservative"
    elif "agressivo" in folded:
        bias = "aggressive"
    alts = _alts(bias, view)
    mkt = view.get("active_market") or "desse mercado"
    fx = view.get("active_fixture")
    opener = (
        "Se eu tivesse que escolher outra frente, "
        if bias != "conservative"
        else "Se eu quisesse reduzir risco, "
    )
    pick = alts[0] if alts else "uma linha diferente"
    body = (
        f"{opener}eu sairia de {mkt} e olharia para {pick}"
        + (f" em {fx}" if fx else "")
        + ".\n"
        + "\n".join(f"• {a}" for a in alts[:3])
    )
    why = f"Alternativa concreta com bias={bias}."
    return body, "neutral", ["alternativa também pode falhar"], why


def build_opinion_reply(
    intent_key: str,
    message: str,
    ctx: dict[str, Any] | None,
) -> tuple[str | None, Position, list[str], str]:
    view = _ctx_view(ctx)
    if intent_key == "worth_it":
        return _reply_worth_it(view)
    if intent_key == "why":
        return _reply_why(view)
    if intent_key == "conservative":
        return _reply_conservative(view)
    if intent_key == "worry":
        return _reply_worry(view)
    if intent_key == "opinion":
        return _reply_opinion(view)
    if intent_key == "alternative":
        return _reply_alternative(view, message)
    if intent_key == "opinion_change":
        # Shallow fallback — deep layer overrides with richer copy
        changers = [
            "perda de intensidade ofensiva",
            "jogo excessivamente truncado",
            "expulsão",
            "odds sem valor",
        ]
        body = "Eu mudaria minha visão caso:\n" + "\n".join(f"• {c};" for c in changers)
        body += "\n\nEsses cenários alterariam significativamente minha leitura atual."
        return body, "neutral", changers, "opinion_change_fallback"
    if intent_key == "aggressive":
        return _reply_alternative(view, "algo mais agressivo")
    return None, "none", [], ""


# ── Humanization (jargon → human) ──────────────────────────────────────────

_JARGON_REPLACEMENTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bna minha leitura\b", re.I), "do meu ponto de vista"),
    (re.compile(r"\bmercado em foco\b", re.I), "caminho que estou olhando"),
    (re.compile(r"\bo quadro\b", re.I), "o cenário"),
    (re.compile(r"\bquadro ainda aponta\b", re.I), "cenário ainda aponta"),
    (re.compile(r"\brisco high\b", re.I), "mais arriscado"),
    (re.compile(r"\brisco em foco\s+High\b", re.I), "leitura mais arriscada"),
    (re.compile(r"\brisco em foco\s+Medium\b", re.I), "jogo equilibrado"),
    (re.compile(r"\brisco em foco\s+Low\b", re.I), "perfil mais contido"),
    (re.compile(r"\brisco em foco\s+(\w+)\b", re.I), r"risco que eu vejo (\1)"),
]


def humanize_jargon(text: str) -> str:
    out = text or ""
    for pat, repl in _JARGON_REPLACEMENTS:
        out = pat.sub(repl, out)
    return out


# ── Reflection Engine ──────────────────────────────────────────────────────

def run_reflection(
    message: str,
    ctx: dict[str, Any] | None = None,
    draft_reply: str | None = None,
) -> ReflectionResult:
    """
    Reflect before final reply. May produce a stronger opinionated answer.
    Fail-open: returns soft result on errors.
    """
    try:
        intent_key, mode_hint = _detect_reflection_intent(message, ctx)
        view = _ctx_view(ctx)

        result = ReflectionResult(
            user_real_intent=intent_key,
            display_mode=mode_hint,
            confidence=0.55,
            signals=["v4.4_reflection"],
        )

        if intent_key == "social":
            result.display_mode = "SOCIAL"
            result.chosen_answer = None  # keep HPL text
            result.why_this_answer = "Turno social — presença humana, sem relatório."
            result.confidence = 0.95
            result.thinking_label = None
            result.humanized_reply = humanize_jargon(draft_reply or "")
            if ctx is not None:
                ctx[REFLECTION_CTX_KEY] = result.to_dict()
            return result

        # Hypotheses (internal)
        result.possible_answers = [
            "ecoar mercado ativo",
            "assumir posição com cautela",
            "pedir mais contexto",
        ]

        opinion, position, risks, why = build_opinion_reply(intent_key, message, ctx)
        result.position = position
        result.risks = risks
        result.why_this_answer = why

        # Prefer opinion engine when we have reflective intents + context
        has_context = bool(view.get("active_fixture") or view.get("active_market"))
        strong = intent_key in {
            "worth_it",
            "why",
            "conservative",
            "worry",
            "opinion",
            "alternative",
        }

        if opinion and (has_context or intent_key in {
            "worth_it", "why", "worry", "opinion", "conservative",
            "opinion_change", "aggressive",
        }):
            result.chosen_answer = opinion
            result.confidence = 0.82 if has_context else 0.7
            result.display_mode = "REASONING" if intent_key in {
                "worth_it",
                "why",
                "worry",
                "opinion",
                "opinion_change",
            } else "FOLLOW_UP"
            result.thinking_label = (
                "Comparando possibilidades..."
                if intent_key in {"worth_it", "alternative", "conservative"}
                else "Pensando no contexto..."
            )
            result.possible_answers.append(opinion[:120])
        elif draft_reply:
            # Soft humanize only
            result.chosen_answer = None
            result.humanized_reply = humanize_jargon(draft_reply)
            result.display_mode = mode_hint if mode_hint != "SOCIAL" else "FOLLOW_UP"
            result.thinking_label = "Considerando o contexto..."
            result.confidence = 0.6
            result.why_this_answer = "Mantive draft e humanizei jargão."
        else:
            result.why_this_answer = "Sem draft nem opinião forte — fail-open."
            result.display_mode = "FOLLOW_UP"

        if result.chosen_answer:
            result.humanized_reply = humanize_jargon(result.chosen_answer)
            result.chosen_answer = result.humanized_reply
        elif result.humanized_reply:
            result.humanized_reply = humanize_jargon(result.humanized_reply)

        # Full analysis pass-through signal
        crl = (ctx or {}).get("last_response_plan") or {}
        if isinstance(crl, dict) and crl.get("mode") == "FULL_ANALYSIS":
            result.display_mode = "FULL_ANALYSIS"
            result.thinking_label = None
            result.chosen_answer = None

        if ctx is not None:
            ctx[REFLECTION_CTX_KEY] = result.to_dict()
        return result
    except Exception as exc:
        logger.warning("reflection_credibility fail-open: %s", exc)
        return ReflectionResult(
            user_real_intent="fail_open",
            why_this_answer=str(exc),
            display_mode="FOLLOW_UP",
            confidence=0.0,
            signals=["fail_open"],
        )


def resolve_display_mode(
    payload: dict[str, Any] | None,
    reflection: ReflectionResult | None,
    ctx: dict[str, Any] | None = None,
) -> DisplayMode:
    payload = payload or {}
    intent = str(payload.get("intent") or "")
    ents = payload.get("entities") or {}
    meta = payload.get("response_metadata") or {}

    if reflection and reflection.display_mode == "SOCIAL":
        return "SOCIAL"
    if intent in {
        "small_talk",
        "greeting",
        "identity",
        "help",
        "capabilities",
        "emotional",
    }:
        return "SOCIAL"
    if ents.get("social") or ents.get("human_presence") or ents.get("natural_conversation"):
        return "SOCIAL"
    if ents.get("has_analysis") is False and intent == "conversation_assist":
        # Calendar / team opinion soft replies — no analysis chrome
        if ents.get("natural_kind") or meta.get("has_analysis") is False:
            return "SOCIAL"
    if meta.get("crl_mode") == "QUICK_REPLY" and ents.get("social"):
        return "SOCIAL"

    if intent in {
        "analyze_match",
        "live_opportunities",
        "live_team_analysis",
    }:
        return "FULL_ANALYSIS"
    if meta.get("crl_mode") == "FULL_ANALYSIS" or meta.get("mode") == "FULL_ANALYSIS":
        return "FULL_ANALYSIS"
    if payload.get("best_markets") and intent == "follow_up":
        # Follow-up with markets can still be analysis-ish
        if reflection and reflection.display_mode == "REASONING":
            return "REASONING"
        return "FULL_ANALYSIS"

    if reflection and reflection.display_mode in {"REASONING", "FOLLOW_UP", "FULL_ANALYSIS"}:
        return reflection.display_mode

    if meta.get("crl_mode") in {
        "EXPLANATION_REPLY",
        "ALTERNATIVE_REPLY",
        "COMPARISON_REPLY",
        "CONVERSATIONAL_REPLY",
        "QUICK_REPLY",
    }:
        return "FOLLOW_UP"

    if intent in {"conversation_assist", "clarification"}:
        return "FOLLOW_UP"

    return "FOLLOW_UP"


def apply_credibility_to_payload(
    payload: dict[str, Any],
    reflection: ReflectionResult | None = None,
    ctx: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Mutates payload for credibility display + optional reply upgrade.
    Fail-open: returns payload unchanged on error.
    """
    try:
        if not isinstance(payload, dict):
            return payload

        mode = resolve_display_mode(payload, reflection, ctx)
        meta = dict(payload.get("response_metadata") or {})
        ents = dict(payload.get("entities") or {})

        show_confidence = mode == "FULL_ANALYSIS"
        show_resumo_chrome = mode == "FULL_ANALYSIS"
        show_header = mode == "FULL_ANALYSIS"
        thinking = None
        if reflection and mode in {"FOLLOW_UP", "REASONING"}:
            thinking = reflection.thinking_label
        if mode == "FOLLOW_UP" and not thinking:
            thinking = "Considerando o contexto..."
        if mode == "REASONING" and not thinking:
            thinking = "Pensando no contexto..."

        credibility = {
            "display_mode": mode,
            "show_confidence": show_confidence,
            "show_resumo_chrome": show_resumo_chrome,
            "show_header": show_header,
            "show_badges": mode == "FULL_ANALYSIS",
            "thinking_label": thinking if mode != "SOCIAL" else None,
            "source": "conversation.reflection_credibility",
        }
        meta["credibility"] = credibility
        meta["show_header"] = show_header
        if reflection:
            meta["reflection"] = {
                "user_real_intent": reflection.user_real_intent,
                "chosen_answer": (reflection.chosen_answer or "")[:240] or None,
                "why_this_answer": reflection.why_this_answer,
                "confidence": reflection.confidence,
                "position": reflection.position,
                "risks": list(reflection.risks or [])[:5],
                "display_mode": reflection.display_mode,
            }

        # Upgrade reply text when reflection produced a better answer
        if reflection and reflection.chosen_answer and mode != "SOCIAL":
            payload["executive_summary"] = reflection.chosen_answer
            payload["final_recommendation"] = reflection.chosen_answer
        elif reflection and reflection.humanized_reply and mode != "SOCIAL":
            # Only soft-replace if draft looked jargon-heavy
            cur = str(payload.get("executive_summary") or "")
            if cur and reflection.humanized_reply != cur:
                # Apply jargon humanization always for short-circuit modes
                if mode in {"FOLLOW_UP", "REASONING"}:
                    payload["executive_summary"] = humanize_jargon(cur)
                    payload["final_recommendation"] = humanize_jargon(
                        str(payload.get("final_recommendation") or cur)
                    )

        if mode == "SOCIAL":
            payload["best_markets"] = []
            payload["match_card"] = None
            payload["positive_factors"] = []
            payload["negative_factors"] = []
            # Neutral confidence so FE never paints analysis chrome
            payload["confidence"] = {
                "score": 0.0,
                "label": "insufficient",
                "explanation": "",
                "data_sources": [],
            }
            payload["risk"] = {
                "level": "Unknown",
                "flags": [],
                "invalidation_conditions": [],
            }
            br = dict(payload.get("bankroll_recommendation") or {})
            br["no_bet"] = True
            br["reasoning"] = ""
            br["recommended_stake_pct"] = 0.0
            payload["bankroll_recommendation"] = br
            ents["show_header"] = False
            ents["social"] = True
            # P2.5-S — never demote sport-owned turns to small_talk
            _sport_owned = (
                str(ents.get("dialog_mode") or "").upper() == "SPORT"
                or ents.get("p25_sport_understanding")
                or ents.get("team_opinion_path")
                or str(ents.get("turn_owner") or "").upper() == "SPORT"
                or ents.get("natural_kind") in {"team_opinion", "team_calendar", "kickoff_lookup"}
            )
            if not _sport_owned and payload.get("intent") not in {
                "small_talk",
                "greeting",
                "identity",
                "help",
                "capabilities",
                "assistant_capabilities",
                "emotional",
            }:
                payload["intent"] = "small_talk"

        elif mode in {"FOLLOW_UP", "REASONING"}:
            # Soft conversational: hide analysis chrome via metadata;
            # also neutralize badge triggers (caution from no_bet).
            ents["show_header"] = False
            # Keep no_bet True but FE will respect show_badges=False
            conf = dict(payload.get("confidence") or {})
            # Avoid fake moderate confidence display on follow-ups
            if float(conf.get("score") or 0) > 0 and not payload.get("best_markets"):
                conf["score"] = 0.0
                conf["label"] = "insufficient"
                conf["explanation"] = ""
                payload["confidence"] = conf

        payload["response_metadata"] = meta
        payload["entities"] = ents

        if ctx is not None and reflection:
            ctx[REFLECTION_CTX_KEY] = reflection.to_dict()
            ctx["credibility"] = credibility

        return payload
    except Exception as exc:
        logger.warning("apply_credibility_to_payload fail-open: %s", exc)
        return payload


def reflect_and_apply(
    message: str,
    payload: dict[str, Any],
    ctx: dict[str, Any] | None = None,
    draft_reply: str | None = None,
) -> dict[str, Any]:
    """Convenience: reflect then stamp credibility on payload."""
    draft = draft_reply or str((payload or {}).get("executive_summary") or "")
    reflection = run_reflection(message, ctx, draft)
    return apply_credibility_to_payload(payload, reflection, ctx)
