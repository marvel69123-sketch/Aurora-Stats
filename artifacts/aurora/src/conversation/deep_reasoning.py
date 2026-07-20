"""
Aurora v4.5 — Deep Reflection + Response Depth Engine + NL variations.

Builds:
  Intent → Hypotheses → Scenarios → Risks → Conclusion → Reply

Wraps v4.4 reflection (does not edit that module's public contract beyond
enriching chosen_answer / metadata). Fail-open. Additive.
"""

from __future__ import annotations

import logging
import random
import re
from dataclasses import asdict, dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

DEEP_CTX_KEY = "deep_reflection"

_OPINION_CHANGE_RE = re.compile(
    r"\b("
    r"mudaria\s+(?:a\s+)?(?:sua\s+)?opini[aã]o|"
    r"mudar\s+de\s+(?:opini[aã]o|ideia)|"
    r"o\s+que\s+faria\s+(?:voce\s+)?mudar|"
    r"o\s+que\s+te\s+faria\s+mudar|"
    r"o\s+que\s+me\s+faria\s+mudar|"
    r"invalidaria|"
    r"o\s+que\s+invalidaria|"
    r"abandonar\s+(?:esse\s+)?mercado|"
    r"o\s+que\s+te\s+faria\s+abandonar|"
    r"mudaria\s+sua\s+vis[aã]o|"
    r"o\s+que\s+mudaria\s+sua"
    r")\b",
    re.I,
)
_AGGRESSIVE_RE = re.compile(
    r"\b(mais\s+agressivo|algo\s+mais\s+agressivo|maior\s+risco)\b",
    re.I,
)


def detect_forced_deep_intent(message: str) -> str | None:
    """Force Deep Reasoning for opinion-changers / aggressive asks."""
    folded = (message or "").strip()
    if _OPINION_CHANGE_RE.search(folded):
        return "opinion_change"
    if _AGGRESSIVE_RE.search(folded):
        return "aggressive"
    return None


def _pick(options: list[str], ctx: dict[str, Any] | None) -> str:
    try:
        from src.conversation.response_variation_layer import pick_variant

        # Map legacy lists to variation families when possible
        return random.choice(options)
    except Exception:
        pass
    recent = list((ctx or {}).get("deep_nl_recent") or [])
    fresh = [o for o in options if o not in recent]
    choice = random.choice(fresh or options)
    if ctx is not None:
        ctx["deep_nl_recent"] = ([choice] + recent)[:10]
    return choice


def _v(family: str, ctx: dict[str, Any] | None) -> str:
    try:
        from src.conversation.response_variation_layer import pick_variant

        return pick_variant(family, ctx)
    except Exception:
        return family


@dataclass
class DeepReflection:
    user_goal: str = ""
    possible_interpretations: list[str] = field(default_factory=list)
    positive_factors: list[str] = field(default_factory=list)
    negative_factors: list[str] = field(default_factory=list)
    risk_scenarios: list[str] = field(default_factory=list)
    what_would_change_my_opinion: list[str] = field(default_factory=list)
    opinion_changers: list[str] = field(default_factory=list)
    conservative_alternative: str = ""
    aggressive_alternative: str = ""
    final_position: str = ""
    alternatives: list[str] = field(default_factory=list)
    experience_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _view(ctx: dict[str, Any] | None) -> dict[str, Any]:
    try:
        from src.conversation.reflection_credibility import _ctx_view

        return _ctx_view(ctx)
    except Exception:
        ctx = ctx or {}
        return {
            "active_fixture": ctx.get("last_match"),
            "active_market": ctx.get("last_market_label"),
            "home": ctx.get("last_home"),
            "away": ctx.get("last_away"),
            "last_risk_level": ctx.get("last_risk"),
            "last_recommendation": ctx.get("last_recommendation"),
        }


def _risk_bucket(level: str | None) -> str:
    t = (level or "").strip().lower()
    if t in {"high", "alto"}:
        return "high"
    if t in {"low", "baixo"}:
        return "low"
    return "medium"


def _experience_notes(view: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    try:
        from src.conversation.prediction_memory import get_experience, get_market_history

        fx = view.get("active_fixture")
        mkt = view.get("active_market")
        home = view.get("home")
        if mkt:
            hist = get_market_history(str(mkt), limit=5)
            if hist:
                notes.append(
                    f"Já olhei {mkt} em {len(hist)} momento(s) anteriores nesta memória passiva."
                )
            exp = get_experience(str(mkt), "market")
            if exp and int(exp.get("times_seen") or 0) >= 2:
                notes.append(
                    f"Esse mercado já apareceu {exp.get('times_seen')}x na minha memória de experiência."
                )
        if home:
            exp_t = get_experience(str(home), "team")
            if exp_t and int(exp_t.get("times_seen") or 0) >= 2:
                notes.append(
                    f"{home} já esteve no radar {exp_t.get('times_seen')}x — sem tratar isso como prova."
                )
        if fx:
            exp_f = get_experience(str(fx), "fixture")
            if exp_f and int(exp_f.get("times_seen") or 0) >= 1:
                notes.append("Esse confronto já ficou registrado na memória de experiência.")
    except Exception:
        pass
    return notes[:3]


def _alts(view: dict[str, Any], bias: str = "conservative") -> list[str]:
    try:
        from src.conversation.state_driven_resolution import suggest_alternatives

        return suggest_alternatives(
            bias=bias,
            active_market=str(view.get("active_market") or "") or None,
            last_risk=str(view.get("last_risk_level") or "") or None,
            market_history=list(view.get("market_history") or []),
        )
    except Exception:
        home = view.get("home")
        if home:
            return [f"{home} empate anula", "linha mais baixa", "stake reduzida"]
        return ["linha mais baixa", "dupla chance", "stake reduzida"]


def build_deep_reflection(
    message: str,
    ctx: dict[str, Any] | None,
    *,
    intent_key: str,
) -> DeepReflection:
    view = _view(ctx)
    fx = view.get("active_fixture") or "o jogo ativo"
    mkt = view.get("active_market") or "o mercado em discussão"
    home = view.get("home") or "o mandante"
    away = view.get("away") or "o visitante"
    bucket = _risk_bucket(view.get("last_risk_level"))

    deep = DeepReflection(
        user_goal=intent_key,
        possible_interpretations=[
            "quer recomendação clara",
            "quer segurança / risco",
            "quer opinião com cenário",
        ],
    )

    # Positive / negative factors (heuristic, not invented stats)
    deep.positive_factors = [
        f"há um caminho claro em {mkt}" if view.get("active_market") else f"há contexto suficiente em {fx}",
        "o confronto já está ancorado na conversa — não preciso reabrir tudo",
    ]
    if bucket == "low":
        deep.positive_factors.append("o risco percebido está mais contido")
    elif bucket == "medium":
        deep.positive_factors.append("ainda vejo margem para trabalhar com filtro")

    deep.negative_factors = [
        "falta uma margem mais confortável para convicção alta",
        f"se o ritmo de {fx} travar, a leitura enfraquece",
    ]
    if bucket == "high":
        deep.negative_factors.insert(0, "o risco percebido está mais alto do que eu gostaria")

    deep.risk_scenarios = [
        f"Se {home} marcar cedo, o jogo pode abrir e alguns mercados ganham outro valor.",
        f"Se o jogo ficar truncado entre {home} e {away}, mercados de volume perdem força.",
        "Se houver expulsão, o plano muda rápido — eu reduziria confiança na hora.",
    ]

    deep.what_would_change_my_opinion = [
        f"{home} perder intensidade ofensiva",
        f"o jogo ficar excessivamente truncado entre {home} e {away}",
        "haver uma expulsão que mude o plano tático",
        "as odds perderem valor / a entrada deixar de compensar o risco",
    ]
    deep.opinion_changers = list(deep.what_would_change_my_opinion)

    alts = _alts(view, "conservative")
    if home and not any("empate" in a.lower() for a in alts):
        alts = [f"{home} empate anula"] + alts
    deep.alternatives = alts[:3]
    deep.conservative_alternative = alts[0] if alts else "stake reduzida / linha mais baixa"

    agg = _alts(view, "aggressive")
    deep.aggressive_alternative = agg[0] if agg else "linha mais alta / stake maior"

    if intent_key == "opinion_change":
        deep.final_position = "revisavel"
        deep.possible_interpretations = [
            "quer invalidadores claros",
            "quer saber quando abandonar o mercado",
            "quer cenários de mudança de opinião",
        ]
    elif intent_key == "aggressive":
        deep.final_position = "agressiva_com_filtro"
    elif bucket == "low":
        deep.final_position = "levemente_positiva"
    elif bucket == "high":
        deep.final_position = "cautelosa"
    else:
        deep.final_position = (
            "cautelosa"
            if intent_key in {"worry", "why", "conservative"}
            else "levemente_positiva_com_filtro"
        )

    deep.experience_notes = _experience_notes(view)

    if ctx is not None:
        ctx[DEEP_CTX_KEY] = deep.to_dict()
    return deep


def _strip_banned_phrases(text: str) -> str:
    try:
        from src.conversation.response_variation_layer import scrub_banned

        text = scrub_banned(text)
    except Exception:
        pass
    out = text
    replacements = [
        (r"\bmercado em foco\b", "caminho que estou olhando"),
        (r"\bfaz sentido continuar\b", "ainda faz sentido seguir"),
        (r"\bna lógica atual\b", "do jeito que vejo agora"),
        (r"\bna minha leitura\b", "do meu ponto de vista"),
        (r"\bo quadro\b", "o cenário"),
    ]
    for pat, repl in replacements:
        out = re.sub(pat, repl, out, flags=re.I)
    return out


def render_opinion_change_reply(
    deep: DeepReflection,
    ctx: dict[str, Any] | None,
) -> str:
    opener = _v("opener_opinion_change", ctx)
    lines = [opener.rstrip(":"), ""]
    changers = deep.opinion_changers or deep.what_would_change_my_opinion
    for c in changers[:5]:
        item = c.strip()
        if not item.startswith(("o ", "a ", "haver", "as ")):
            # keep natural bullet text
            pass
        lines.append(f"• {item};")
    lines.append("")
    lines.append(_v("closing_change", ctx))
    if deep.conservative_alternative:
        lines.append("")
        lines.append(_v("alt_safe", ctx))
        lines.append(f"• {deep.conservative_alternative}")
    return _strip_banned_phrases("\n".join(lines).strip())


def render_depth_reply(
    deep: DeepReflection,
    ctx: dict[str, Any] | None,
    *,
    intent_key: str,
) -> str:
    """Response Depth Engine — WHY / RISKS / ALTERNATIVES / SCENARIOS."""
    if intent_key == "opinion_change":
        return render_opinion_change_reply(deep, ctx)

    pos = deep.final_position
    if intent_key == "aggressive" or pos == "agressiva_com_filtro":
        opener = _v("alt_agg", ctx).rstrip(":") + "."
        if not opener[0].isupper():
            opener = opener[0].upper() + opener[1:]
        opener = "Eu consideraria um viés mais agressivo — com filtro."
    elif pos in {"levemente_positiva", "levemente_positiva_com_filtro"}:
        opener = _v("opener_lean_pos", ctx)
    elif pos == "cautelosa":
        opener = _v("opener_cautious", ctx)
    else:
        opener = _v("opener_neutral", ctx)

    exp_line = ""
    if deep.experience_notes:
        exp_line = deep.experience_notes[0]

    sections: list[str] = [opener]
    if exp_line and intent_key in {"worth_it", "opinion", "why", "aggressive"}:
        sections.append(exp_line)

    sections.append(_v("favor", ctx))
    for f in deep.positive_factors[:3]:
        sections.append(f"• {f}")

    sections.append("")
    sections.append(_v("worry", ctx).rstrip("...").rstrip(":") + ":")
    for f in deep.negative_factors[:3]:
        sections.append(f"• {f}")

    sections.append("")
    sections.append(_v("scenario", ctx))
    for s in deep.risk_scenarios[:3]:
        sections.append(f"• {s}")

    sections.append("")
    sections.append(_v("change", ctx))
    for s in (deep.opinion_changers or deep.what_would_change_my_opinion)[:3]:
        sections.append(f"• {s}")

    if deep.alternatives and intent_key in {
        "worth_it",
        "opinion",
        "conservative",
        "alternative",
        "why",
        "worry",
        "aggressive",
    }:
        sections.append("")
        if intent_key == "aggressive":
            sections.append(_v("alt_agg", ctx))
            sections.append(f"• {deep.aggressive_alternative or deep.alternatives[0]}")
        else:
            sections.append(_v("alt_safe", ctx))
            for a in deep.alternatives[:2]:
                sections.append(f"• {a}")

    try:
        from src.conversation.context_reinforcement import context_anchor_line

        anchor = context_anchor_line(ctx)
        if anchor and intent_key not in {"social"}:
            sections.append("")
            sections.append(anchor)
    except Exception:
        pass

    text = "\n".join(sections).strip()
    text = _strip_banned_phrases(text)
    # P3-D.4 — suppress only here; anti_sticky diversify_reply records once
    try:
        from src.conversation.response_diversification import suppress_sport_boilerplate

        text = suppress_sport_boilerplate(ctx, text)
    except Exception:
        pass
    return text


def should_use_depth(intent_key: str) -> bool:
    return intent_key in {
        "worth_it",
        "why",
        "opinion",
        "worry",
        "conservative",
        "alternative",
        "opinion_change",
        "aggressive",
    }


def run_deep_reasoning(
    message: str,
    ctx: dict[str, Any] | None = None,
    draft_reply: str | None = None,
):
    """
    Run v4.4 reflection, then deepen chosen answers for recommendation intents.
    Returns ReflectionResult (v4.4 type) with deeper chosen_answer when applicable.
    """
    try:
        from src.conversation.reflection_credibility import run_reflection

        base = run_reflection(message, ctx, draft_reply)
        intent_key = str(base.user_real_intent or "")

        # v4.5.1 — force deep for opinion-changers even if reflection was shallow
        forced = detect_forced_deep_intent(message)
        if forced:
            intent_key = forced
            base.user_real_intent = forced
            base.signals = list(base.signals or []) + ["v4.5.1_forced_deep", forced]

        if intent_key == "social":
            if ctx is not None and base.to_dict():
                data = base.to_dict()
                data["deep"] = None
                ctx["conversation_reflection"] = data
            return base

        if not should_use_depth(intent_key):
            if ctx is not None and base.to_dict():
                data = base.to_dict()
                data["deep"] = None
                ctx["conversation_reflection"] = data
            return base

        deep = build_deep_reflection(message, ctx, intent_key=intent_key)
        depth_reply = render_depth_reply(deep, ctx, intent_key=intent_key)

        base.chosen_answer = depth_reply
        base.humanized_reply = depth_reply
        base.why_this_answer = (
            f"Deep reflection: position={deep.final_position}; "
            f"changers={len(deep.opinion_changers)}; alts={len(deep.alternatives)}"
        )
        base.risks = list(deep.negative_factors)[:3] + list(deep.opinion_changers)[:2]
        if deep.final_position.startswith("levemente_positiva"):
            base.position = "favorable"
        elif deep.final_position == "cautelosa":
            base.position = "cautious"
        elif intent_key == "opinion_change":
            base.position = "neutral"
        base.display_mode = "REASONING"
        base.thinking_label = (
            "Comparando invalidadores..."
            if intent_key == "opinion_change"
            else "Comparando cenários..."
        )
        base.signals = list(base.signals or []) + ["v4.5_deep_reasoning", "v4.5.1"]
        base.confidence = max(float(base.confidence or 0), 0.86)

        if ctx is not None:
            data = base.to_dict()
            data["deep"] = deep.to_dict()
            ctx["conversation_reflection"] = data
            ctx[DEEP_CTX_KEY] = deep.to_dict()

        return base
    except Exception as exc:
        logger.warning("run_deep_reasoning fail-open: %s", exc)
        try:
            from src.conversation.reflection_credibility import run_reflection

            return run_reflection(message, ctx, draft_reply)
        except Exception:
            from src.conversation.reflection_credibility import ReflectionResult

            return ReflectionResult(
                user_real_intent="fail_open",
                why_this_answer=str(exc),
                display_mode="FOLLOW_UP",
                signals=["fail_open"],
            )
