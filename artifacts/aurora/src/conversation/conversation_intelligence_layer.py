"""
Aurora v4.2 — Conversation Intelligence Layer (CIL).

Understands what the user is *trying to do* (not only what was typed):
  message → intent → hypotheses → select → plan → feed CRL

Does NOT edit frozen modules (State / Reasoner / CRL / FollowUp / Resolver / engines).
Fail-open. Additive. Internal thought is audit-only.

Pipeline position:
  Reasoner → CIL → CRL → CI → FollowUp → Engines
"""

from __future__ import annotations

import logging
import random
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

logger = logging.getLogger(__name__)

CIL_THOUGHT_KEY = "conversation_thought"
CIL_GOAL_KEY = "conversation_goal"
CIL_LAST_OPENERS_KEY = "cil_recent_openers"

GoalType = Literal[
    "COMPARE_MARKETS",
    "COMPARE_FIXTURES",
    "ASK_OPINION",
    "ASK_EXPLANATION",
    "ASK_BEST_OPTION",
    "ASK_SAFER_OPTION",
    "ASK_RISKIER_OPTION",
    "CHANGE_SUBJECT",
    "CONTINUE_PENDING",
    "FOLLOWUP_MARKET",
    "REJECT_MARKET",
    "CLARIFY_FIXTURE",
    "FULL_ANALYSIS",
    "SMALL_TALK",
    "UNKNOWN",
]


def _fold(text: str) -> str:
    t = unicodedata.normalize("NFKD", (text or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^\w\sx/-]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


@dataclass
class ConversationGoal:
    goal_type: GoalType | str = "UNKNOWN"
    goal_target: str = ""
    goal_subject: str = ""
    goal_confidence: float = 0.0
    alternatives: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Hypothesis:
    label: str
    goal_type: GoalType | str
    score: float
    why: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ConversationThought:
    """Internal audit only — never user-facing product copy."""

    user_intent: str = ""
    possible_interpretations: list[dict[str, Any]] = field(default_factory=list)
    selected_interpretation: str = ""
    reasoning: str = ""
    confidence: float = 0.0
    response_strategy: str = ""
    context_priority: list[str] = field(default_factory=list)
    reflection_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── Context priority ───────────────────────────────────────────────────────

def resolve_context_priority(ctx: dict[str, Any] | None) -> dict[str, Any]:
    """
    Rigid priority:
      pending_question → active_fixture → active_market → fixture_history → market_history
    """
    view: dict[str, Any] = {
        "pending_team": None,
        "pending_question": False,
        "active_fixture": None,
        "active_market": None,
        "last_recommendation": None,
        "last_risk_level": None,
        "fixture_history": [],
        "market_history": [],
        "priority_winner": "none",
    }
    if not ctx:
        return view

    try:
        from src.conversation.conversation_state import get_state

        state = get_state(ctx)
    except Exception:
        state = {}

    pending = bool(state.get("pending_question")) or bool(ctx.get("ci_pending"))
    team = state.get("active_team")
    if not team and isinstance(ctx.get("ci_pending"), dict):
        team = ctx["ci_pending"].get("team")
    view["pending_question"] = pending
    view["pending_team"] = team
    view["active_fixture"] = state.get("active_fixture") or ctx.get("last_match") or ctx.get("last_fixture")
    view["active_market"] = state.get("active_market")
    view["last_recommendation"] = state.get("last_recommendation") or ctx.get("last_recommendation")
    view["last_risk_level"] = state.get("last_risk_level")
    view["fixture_history"] = list(state.get("fixture_history") or [])
    # Merge durable market_history with ephemeral CIL market touches (follow-ups)
    m_hist = list(state.get("market_history") or [])
    for touch in list(ctx.get("cil_market_touches") or []):
        if isinstance(touch, dict) and touch.get("market"):
            m_hist = [touch] + m_hist
    view["market_history"] = m_hist

    if pending and team:
        view["priority_winner"] = "pending_question"
    elif view["active_fixture"]:
        view["priority_winner"] = "active_fixture"
    elif view["active_market"]:
        view["priority_winner"] = "active_market"
    elif view["fixture_history"]:
        view["priority_winner"] = "fixture_history"
    elif view["market_history"]:
        view["priority_winner"] = "market_history"
    return view


def _market_labels(ctx_view: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()
    for h in ctx_view.get("market_history") or []:
        if isinstance(h, dict) and h.get("market"):
            m = str(h["market"]).strip()
            key = m.lower()
            if m and key not in seen:
                seen.add(key)
                labels.append(m)
    am = ctx_view.get("active_market")
    if am and str(am).lower() not in seen:
        labels.insert(0, str(am))
    return labels


# ── Humanizer ──────────────────────────────────────────────────────────────

_OPENER_FAMILIES: dict[str, list[str]] = {
    "opinion": [
        "Se eu tivesse que escolher, ",
        "Particularmente, ",
        "Eu teria mais confiança em ",
        "Olhando frio, ",
        "Do jeito que o jogo se desenha, ",
    ],
    "caution": [
        "Eu ainda teria alguma reserva. ",
        "Não me sinto tão confortável aqui. ",
        "Com o que temos, eu iria com o pé no freio. ",
        "Tem um porém: ",
    ],
    "comparison": [
        "Entre os dois, ",
        "Se fosse para seguir um caminho, ",
        "Colocando lado a lado, ",
        "Na disputa direta, ",
    ],
    "alternative": [
        "Beleza — vamos mudar o ângulo. ",
        "Entendi o ponto. ",
        "Ok, então eu sairia desse caminho. ",
        "Faz sentido. ",
    ],
    "explain": [
        "O motivo principal: ",
        "A lógica que estou usando: ",
        "Resumindo o porquê: ",
        "O que pesa aqui: ",
    ],
    "clarify": [
        "Antes de cravar qualquer coisa: ",
        "Só para não inventar confronto: ",
        "Preciso de um detalhe: ",
    ],
    "neutral": [
        "Certo. ",
        "Ok. ",
        "Seguindo do ponto atual: ",
        "Mantendo o fio da conversa: ",
    ],
}

_BANNED_OPENERS = (
    "na minha leitura",
    "me parece",
    "eu vejo valor",
    "eu gosto mais",
)


def _pick_opener(family: str, ctx: dict[str, Any] | None) -> str:
    options = list(_OPENER_FAMILIES.get(family) or _OPENER_FAMILIES["neutral"])
    recent = []
    if ctx is not None:
        recent = list(ctx.get(CIL_LAST_OPENERS_KEY) or [])
    fresh = [o for o in options if o.strip() not in recent]
    choice = random.choice(fresh or options)
    if ctx is not None:
        updated = ([choice.strip()] + recent)[:6]
        ctx[CIL_LAST_OPENERS_KEY] = updated
    return choice


def _strip_robotic_openers(text: str) -> str:
    t = (text or "").strip()
    # Remove leading robotic stock phrases (repeat until stable)
    patterns = [
        r"^na\s+minha\s+leitura\b[,:]?\s*",
        r"^me\s+parece\s+que\s+",
        r"^me\s+parece\b[,:]?\s*",
        r"^eu\s+vejo\s+valor\s*(nisso|nisto)?\b[,.]?\s*",
        r"^eu\s+gosto\s+mais\s+de\s+",
        r"^porque[,]?\s*na\s+minha\s+leitura[,]?\s*",
    ]
    for _ in range(4):
        prev = t
        for pat in patterns:
            t = re.sub(pat, "", t, count=1, flags=re.I).strip()
        if t == prev:
            break
    return t[0].upper() + t[1:] if t else t


def humanize_text(
    text: str,
    *,
    family: str,
    ctx: dict[str, Any] | None = None,
) -> str:
    original = (text or "").strip()
    body = _strip_robotic_openers(original)
    # If stripping removed everything (pure template), rebuild a short neutral body
    if not body or len(body) < 8:
        body = {
            "opinion": "eu seguiria com o que está mais claro no contexto atual.",
            "caution": "ainda há margem para hesitar antes de cravar.",
            "comparison": "eu escolheria o caminho com leitura mais limpa.",
            "alternative": "vale testar outro ângulo sem repetir o mesmo relatório.",
            "explain": "o contexto ativo ainda sustenta essa direção.",
            "clarify": "preciso do adversário para não inventar o jogo.",
            "neutral": "podemos seguir a partir do que já está na conversa.",
        }.get(family, "podemos seguir a partir do que já está na conversa.")
    # If already starts with a varied opener family, keep
    low = _fold(body)
    for fam_opts in _OPENER_FAMILIES.values():
        for op in fam_opts:
            op_f = _fold(op).rstrip()
            if op_f and low.startswith(op_f):
                return body
    opener = _pick_opener(family, ctx)
    # Avoid "Eu teria mais confiança em Entre os dois"
    if opener.endswith(" em ") and body[:1].isupper():
        body = body[0].lower() + body[1:]
    return f"{opener}{body}"


# ── Hypothesis generation ──────────────────────────────────────────────────

def generate_hypotheses(
    message: str,
    ctx_view: dict[str, Any],
    base_reasoning: dict[str, Any] | None = None,
) -> list[Hypothesis]:
    folded = _fold(message)
    base_reasoning = base_reasoning or {}
    hyps: list[Hypothesis] = []
    markets = _market_labels(ctx_view)
    fx = ctx_view.get("active_fixture")
    pending = ctx_view.get("pending_question") and ctx_view.get("pending_team")
    f_hist = ctx_view.get("fixture_history") or []

    # Pending always strong when message is vague opinion / deixis
    if pending:
        hyps.append(
            Hypothesis(
                label="continue_pending_team",
                goal_type="CONTINUE_PENDING",
                score=0.95,
                why=f"pending_team={ctx_view.get('pending_team')} beats active_fixture",
            )
        )

    if re.search(r"\b(qual\s+parece\s+melhor|compare|qual\s+dos\s+dois|melhor\s+opcao)\b", folded):
        if len(markets) >= 2 or (fx and len(markets) >= 1 and re.search(r"gols?|escanteio|cart", " ".join(_fold(m) for m in markets))):
            # Boost market compare when multiple market touches in history
            m_score = 0.9 if len(markets) >= 2 else 0.72
            hyps.append(
                Hypothesis(
                    label="compare_markets_on_active_fixture",
                    goal_type="COMPARE_MARKETS",
                    score=m_score,
                    why=f"active_fixture={fx!r} with markets={markets[:4]}",
                )
            )
        if fx and f_hist:
            hyps.append(
                Hypothesis(
                    label="compare_fixtures",
                    goal_type="COMPARE_FIXTURES",
                    score=0.7 if len(markets) < 2 else 0.45,
                    why="fixture_history available",
                )
            )
        hyps.append(
            Hypothesis(
                label="compare_teams_vague",
                goal_type="COMPARE_FIXTURES",
                score=0.25,
                why="fallback team compare without clear pair",
            )
        )

    if re.search(r"\b(por\s+que|porque|explique|explica)\b", folded):
        hyps.append(
            Hypothesis(
                label="ask_explanation",
                goal_type="ASK_EXPLANATION",
                score=0.88,
                why="explanation cue",
            )
        )

    if re.search(r"\b(vale\s+a\s+pena|tem\s+algo\s+melhor|algo\s+melhor)\b", folded):
        hyps.append(
            Hypothesis(
                label="ask_best_option",
                goal_type="ASK_BEST_OPTION",
                score=0.86,
                why="better/worth-it cue",
            )
        )

    if re.search(r"\b(mais\s+conservador|mais\s+seguro|menor\s+risco)\b", folded):
        hyps.append(
            Hypothesis(
                label="ask_safer",
                goal_type="ASK_SAFER_OPTION",
                score=0.87,
                why="safer preference",
            )
        )

    if re.search(r"\b(mais\s+agressivo|maior\s+risco)\b", folded):
        hyps.append(
            Hypothesis(
                label="ask_riskier",
                goal_type="ASK_RISKIER_OPTION",
                score=0.87,
                why="riskier preference",
            )
        )

    if re.search(r"\b(nao\s+gostei|parece\s+ruim|nao\s+me\s+convenceu)\b", folded):
        hyps.append(
            Hypothesis(
                label="reject_market",
                goal_type="REJECT_MARKET",
                score=0.9,
                why="rejection cue",
            )
        )

    if re.search(
        r"^(?:e\s+)?(?:pra\s+|para\s+)?(gols?|escanteios?|cart)",
        folded,
    ):
        hyps.append(
            Hypothesis(
                label="followup_market",
                goal_type="FOLLOWUP_MARKET",
                score=0.92 if fx else 0.4,
                why="market follow-up phrase",
            )
        )

    if re.search(r"^(?:e\s+esse|esse)\??$", folded):
        hyps.append(
            Hypothesis(
                label="deixis_active",
                goal_type="ASK_OPINION",
                score=0.8 if fx or markets else 0.35,
                why="deixis toward active item",
            )
        )

    if re.search(r"\b(oq\s+acha|o\s+que\s+acha)\b", folded):
        if pending:
            pass  # already covered
        elif fx:
            hyps.append(
                Hypothesis(
                    label="opinion_on_active",
                    goal_type="ASK_OPINION",
                    score=0.82,
                    why="opinion with active fixture",
                )
            )
        else:
            hyps.append(
                Hypothesis(
                    label="opinion_needs_fixture",
                    goal_type="CLARIFY_FIXTURE",
                    score=0.7,
                    why="opinion without fixture",
                )
            )

    if re.search(r"\b(fala\s+d[oe]|analis[ae]\s+(?:o|a)?)\b", folded) and not re.search(
        r"\bx\b|\bvs\b", folded
    ):
        hyps.append(
            Hypothesis(
                label="single_team_pending",
                goal_type="CONTINUE_PENDING",
                score=0.85,
                why="single team discuss → need opponent",
            )
        )

    if re.search(r"\bx\b|\bvs\b", folded) and re.search(r"\banalis", folded):
        hyps.append(
            Hypothesis(
                label="full_analysis",
                goal_type="FULL_ANALYSIS",
                score=0.9,
                why="explicit analyze fixture",
            )
        )

    # Incorporate base reasoner as weak prior
    rtype = str((base_reasoning or {}).get("reasoning_type") or "")
    if rtype == "COMPARISON" and not any(h.goal_type == "COMPARE_MARKETS" for h in hyps):
        hyps.append(
            Hypothesis(
                label="reasoner_comparison",
                goal_type="COMPARE_FIXTURES",
                score=0.55,
                why="reasoner said COMPARISON",
            )
        )

    if not hyps:
        hyps.append(
            Hypothesis(
                label="unknown",
                goal_type="UNKNOWN",
                score=0.3,
                why="no strong cue",
            )
        )

    hyps.sort(key=lambda h: h.score, reverse=True)
    return hyps


def select_goal(
    hyps: list[Hypothesis],
    ctx_view: dict[str, Any],
) -> ConversationGoal:
    # Hard rule: pending wins over everything for opinion/deixis/continue
    if ctx_view.get("priority_winner") == "pending_question":
        pending_hyps = [h for h in hyps if h.goal_type == "CONTINUE_PENDING"]
        if pending_hyps:
            top = pending_hyps[0]
            return ConversationGoal(
                goal_type="CONTINUE_PENDING",
                goal_target=str(ctx_view.get("pending_team") or ""),
                goal_subject="opponent",
                goal_confidence=max(top.score, 0.93),
                alternatives=[h.label for h in hyps[1:4]],
            )

    top = hyps[0]
    markets = _market_labels(ctx_view)
    target = ""
    subject = ""
    if top.goal_type == "COMPARE_MARKETS":
        target = " vs ".join(markets[:2]) if len(markets) >= 2 else (markets[0] if markets else "")
        subject = str(ctx_view.get("active_fixture") or "")
    elif top.goal_type == "COMPARE_FIXTURES":
        subject = str(ctx_view.get("active_fixture") or "")
        if ctx_view.get("fixture_history") and isinstance(ctx_view["fixture_history"][0], dict):
            target = str(ctx_view["fixture_history"][0].get("fixture") or "")
    elif top.goal_type == "CONTINUE_PENDING":
        target = str(ctx_view.get("pending_team") or "")
        subject = "opponent"
    else:
        subject = str(ctx_view.get("active_fixture") or ctx_view.get("active_market") or "")

    return ConversationGoal(
        goal_type=top.goal_type,
        goal_target=target,
        goal_subject=subject,
        goal_confidence=float(top.score),
        alternatives=[h.label for h in hyps[1:4]],
    )


def _strategy_for_goal(goal: ConversationGoal) -> str:
    mapping = {
        "COMPARE_MARKETS": "COMPARISON_REPLY",
        "COMPARE_FIXTURES": "COMPARISON_REPLY",
        "ASK_EXPLANATION": "EXPLANATION_REPLY",
        "ASK_BEST_OPTION": "ALTERNATIVE_REPLY",
        "ASK_SAFER_OPTION": "ALTERNATIVE_REPLY",
        "ASK_RISKIER_OPTION": "ALTERNATIVE_REPLY",
        "REJECT_MARKET": "ALTERNATIVE_REPLY",
        "FOLLOWUP_MARKET": "CONVERSATIONAL_REPLY",
        "ASK_OPINION": "CONVERSATIONAL_REPLY",
        "CONTINUE_PENDING": "CONVERSATIONAL_REPLY",
        "CLARIFY_FIXTURE": "CONVERSATIONAL_REPLY",
        "FULL_ANALYSIS": "FULL_ANALYSIS",
        "SMALL_TALK": "QUICK_REPLY",
    }
    return mapping.get(str(goal.goal_type), "CONVERSATIONAL_REPLY")


def apply_goal_to_reasoning(
    goal: ConversationGoal,
    ctx_view: dict[str, Any],
    base_reasoning: dict[str, Any],
) -> dict[str, Any]:
    """Rewrite last_reasoning for CRL consumption — does not edit Reasoner module."""
    out = dict(base_reasoning or {})
    g = str(goal.goal_type)

    if g == "CONTINUE_PENDING":
        out.update(
            {
                "user_goal": "continue_pending_team_thread",
                "reasoning_type": "CLARIFY",
                "next_action": "ASK_OPPONENT",
                "requires_context": True,
                "missing_information": ["opponent"],
                "confidence": goal.goal_confidence,
                "active_fixture": None,  # pending beats stale fixture for CRL copy
                "thought": (
                    f"CIL: pending ({goal.goal_target}) tem prioridade sobre "
                    f"active_fixture={ctx_view.get('active_fixture')!r}. Pedir adversário."
                ),
            }
        )
        return out

    if g == "COMPARE_MARKETS":
        markets = _market_labels(ctx_view)
        out.update(
            {
                "user_goal": "compare_markets_on_active_fixture",
                "reasoning_type": "COMPARISON",
                "next_action": "COMPARE_HISTORY",
                "topic": "markets",
                "comparison_target": goal.goal_target or " vs ".join(markets[:2]),
                "requires_context": True,
                "missing_information": [],
                "confidence": goal.goal_confidence,
                "active_fixture": ctx_view.get("active_fixture"),
                "active_market": ctx_view.get("active_market"),
                "thought": (
                    "CIL: usuário provavelmente compara mercados no fixture ativo "
                    f"({ctx_view.get('active_fixture')}), não pede novo confronto. "
                    f"Mercados: {markets[:4]}."
                ),
                "signals": list(out.get("signals") or []) + ["cil_compare_markets"],
            }
        )
        return out

    if g == "COMPARE_FIXTURES":
        out.update(
            {
                "user_goal": "compare_options_or_fixtures",
                "reasoning_type": "COMPARISON",
                "next_action": "COMPARE_HISTORY",
                "comparison_target": goal.goal_target,
                "confidence": goal.goal_confidence,
                "active_fixture": ctx_view.get("active_fixture"),
                "signals": list(out.get("signals") or []) + ["cil_compare_fixtures"],
            }
        )
        return out

    if g == "ASK_EXPLANATION":
        out.update(
            {
                "reasoning_type": "EXPLANATION",
                "next_action": "EXPLAIN_LAST",
                "confidence": goal.goal_confidence,
                "active_fixture": ctx_view.get("active_fixture"),
                "active_market": ctx_view.get("active_market"),
            }
        )
        return out

    if g in {"ASK_BEST_OPTION", "ASK_SAFER_OPTION", "ASK_RISKIER_OPTION", "REJECT_MARKET"}:
        action = {
            "ASK_BEST_OPTION": "PREFER_BETTER",
            "ASK_SAFER_OPTION": "PREFER_CONSERVATIVE",
            "ASK_RISKIER_OPTION": "PREFER_AGGRESSIVE",
            "REJECT_MARKET": "SEEK_ALTERNATIVE",
        }[g]
        out.update(
            {
                "reasoning_type": "MARKET_REJECTION" if g == "REJECT_MARKET" else "PREFERENCE_SIGNAL",
                "next_action": action,
                "confidence": goal.goal_confidence,
                "active_fixture": ctx_view.get("active_fixture"),
                "active_market": ctx_view.get("active_market"),
            }
        )
        return out

    if g == "FOLLOWUP_MARKET":
        out.update(
            {
                "reasoning_type": "FOLLOWUP_MARKET",
                "next_action": "PASS_MARKET_FOLLOWUP",
                "confidence": goal.goal_confidence,
                "active_fixture": ctx_view.get("active_fixture"),
                "active_market": ctx_view.get("active_market"),
            }
        )
        return out

    if g == "ASK_OPINION":
        out.update(
            {
                "reasoning_type": "FOLLOWUP_FIXTURE",
                "next_action": "USE_ACTIVE_CONTEXT",
                "confidence": goal.goal_confidence,
                "active_fixture": ctx_view.get("active_fixture"),
                "active_market": ctx_view.get("active_market"),
            }
        )
        return out

    if g == "FULL_ANALYSIS":
        out.update(
            {
                "reasoning_type": "FOLLOWUP_FIXTURE",
                "next_action": "CONTINUE_PIPELINE",
                "confidence": goal.goal_confidence,
            }
        )
        return out

    return out


def reflect(
    goal: ConversationGoal,
    hyps: list[Hypothesis],
    ctx_view: dict[str, Any],
    draft_reply: str | None = None,
) -> tuple[ConversationGoal, list[str]]:
    notes: list[str] = []
    g = goal

    # Ignore context? pending must win
    if ctx_view.get("pending_question") and g.goal_type != "CONTINUE_PENDING":
        if any(h.goal_type == "CONTINUE_PENDING" for h in hyps):
            notes.append("reflection: pending ignored — replanning to CONTINUE_PENDING")
            g = ConversationGoal(
                goal_type="CONTINUE_PENDING",
                goal_target=str(ctx_view.get("pending_team") or ""),
                goal_subject="opponent",
                goal_confidence=0.94,
                alternatives=goal.alternatives,
            )

    # Compare markets preferred when history has 2+ markets and goal was fixture compare
    markets = _market_labels(ctx_view)
    if (
        g.goal_type == "COMPARE_FIXTURES"
        and len(markets) >= 2
        and ctx_view.get("active_fixture")
        and not (ctx_view.get("fixture_history"))
    ):
        notes.append("reflection: no second fixture — prefer COMPARE_MARKETS")
        g = ConversationGoal(
            goal_type="COMPARE_MARKETS",
            goal_target=" vs ".join(markets[:2]),
            goal_subject=str(ctx_view.get("active_fixture") or ""),
            goal_confidence=0.9,
            alternatives=goal.alternatives,
        )

    if draft_reply:
        low = draft_reply.lower()
        hits = sum(1 for b in _BANNED_OPENERS if b in low[:80])
        if hits >= 2:
            notes.append("reflection: draft looks repetitive/template-like")

    return g, notes


def build_cil_reply(
    goal: ConversationGoal,
    message: str,
    ctx: dict[str, Any] | None,
    ctx_view: dict[str, Any],
) -> str | None:
    """Optional reply override (humanized) for CRL short-circuit refinement."""
    g = str(goal.goal_type)
    fx = ctx_view.get("active_fixture")
    markets = _market_labels(ctx_view)
    mkt = ctx_view.get("active_market")
    rec = ctx_view.get("last_recommendation")

    if g == "CONTINUE_PENDING":
        team = goal.goal_target or ctx_view.get("pending_team") or "esse time"
        body = (
            f"você está falando do {team}. "
            "Me diga o adversário (ex.: Time A x Time B) — "
            "não vou puxar um jogo antigo nem inventar o confronto."
        )
        return humanize_text(body, family="clarify", ctx=ctx)

    if g == "COMPARE_MARKETS":
        if len(markets) >= 2:
            a, b = markets[0], markets[1]
            body = (
                f"no {fx or 'jogo ativo'}, eu ficaria entre {a} e {b}. "
                f"Hoje eu puxaria mais para {a}"
                + (f" — alinhado à última âncora ({str(rec)[:80]})" if rec else "")
                + ". Qual dos dois caminhos você quer aprofundar?"
            )
        elif markets:
            body = (
                f"no {fx or 'jogo ativo'}, o caminho mais claro que vejo é {markets[0]}. "
                "Se quiser, comparo com gols, escanteios ou cartões em cima desse mesmo confronto."
            )
        else:
            body = (
                f"no {fx or 'confronto ativo'}, me diga se a comparação é entre gols, "
                "escanteios ou outro mercado — sem reabrir o relatório inteiro."
            )
        return humanize_text(body, family="comparison", ctx=ctx)

    if g == "COMPARE_FIXTURES":
        prev = goal.goal_target
        body = (
            f"eu colocaria {fx} contra {prev}. "
            "Sem inventar números novos — qual dos dois você quer aprofundar?"
            if fx and prev
            else "só tenho um confronto claro agora; analise outro para eu comparar os dois."
        )
        return humanize_text(body, family="comparison", ctx=ctx)

    if g == "ASK_EXPLANATION":
        body = (
            f"o que mais pesa é o quadro de {mkt or 'mercado ativo'}"
            + (f" em {fx}" if fx else "")
            + (f", com risco {ctx_view.get('last_risk_level')}" if ctx_view.get("last_risk_level") else "")
            + ". Posso detalhar sem repetir o relatório completo."
        )
        return humanize_text(body, family="explain", ctx=ctx)

    if g in {"ASK_BEST_OPTION", "ASK_SAFER_OPTION", "ASK_RISKIER_OPTION", "REJECT_MARKET"}:
        bias = {
            "ASK_BEST_OPTION": "outra frente",
            "ASK_SAFER_OPTION": "um caminho mais seguro",
            "ASK_RISKIER_OPTION": "um caminho mais agressivo",
            "REJECT_MARKET": "uma alternativa",
        }[g]
        alts = []
        try:
            from src.conversation.state_driven_resolution import suggest_alternatives

            bmap = {
                "ASK_BEST_OPTION": "better",
                "ASK_SAFER_OPTION": "conservative",
                "ASK_RISKIER_OPTION": "aggressive",
                "REJECT_MARKET": "better",
            }
            alts = suggest_alternatives(
                bias=bmap[g],
                active_market=str(mkt) if mkt else None,
                last_risk=str(ctx_view.get("last_risk_level") or "") or None,
                market_history=list(ctx_view.get("market_history") or []),
            )
        except Exception:
            alts = ["under / linha mais baixa", "outro mercado", "stake reduzida"]
        lines = [
            humanize_text(
                f"eu sairia de {mkt or 'desse mercado'} e testaria {bias}.",
                family="alternative",
                ctx=ctx,
            )
        ]
        if fx:
            lines.append(f"Em {fx}:")
        for a in alts[:3]:
            lines.append(f"• {a}")
        return "\n".join(lines)

    if g == "FOLLOWUP_MARKET":
        focus = "escanteios"
        f = _fold(message)
        if re.search(r"\bgols?\b", f):
            focus = "gols"
        elif re.search(r"cart", f):
            focus = "cartões"
        body = (
            f"{focus} continua fazendo sentido"
            + (f" em {fx}" if fx else "")
            + ". Posso seguir nessa linha sem reabrir o relatório."
        )
        return humanize_text(body, family="opinion", ctx=ctx)

    if g == "ASK_OPINION":
        body = (
            f"eu manteria o foco em {fx or 'jogo ativo'}"
            + (f", com {mkt} no radar" if mkt else "")
            + ". Quer que eu aprofunde risco ou uma alternativa?"
        )
        return humanize_text(body, family="opinion", ctx=ctx)

    return None


def _record_market_touch(message: str, ctx: dict[str, Any]) -> None:
    """Ephemeral touch so 'e escanteios? / e gols?' can be compared later."""
    f = _fold(message)
    label = None
    if re.search(r"escanteio|corner|canto", f):
        label = "Escanteios"
    elif re.search(r"\bgols?\b|over|under|btts", f):
        label = "Gols"
    elif re.search(r"cart", f):
        label = "Cartões"
    if not label:
        return
    touches = [t for t in list(ctx.get("cil_market_touches") or []) if isinstance(t, dict)]
    if touches and str(touches[0].get("market", "")).lower() == label.lower():
        return
    touches.insert(0, {"market": label, "at": "touch"})
    ctx["cil_market_touches"] = touches[:6]


def run_intelligence(
    message: str,
    ctx: dict[str, Any] | None = None,
) -> ConversationThought:
    """
    Main CIL entry: hypotheses → goal → rewrite last_reasoning → thought.
    Fail-open: returns low-confidence UNKNOWN thought without raising.
    """
    try:
        ctx = ctx if ctx is not None else {}
        _record_market_touch(message, ctx)
        base = dict(ctx.get("last_reasoning") or {})
        ctx_view = resolve_context_priority(ctx)
        hyps = generate_hypotheses(message, ctx_view, base)
        goal = select_goal(hyps, ctx_view)
        goal, refl = reflect(goal, hyps, ctx_view)

        # If starting/continuing a single-team thread, capture pending team (API only)
        if goal.goal_type == "CONTINUE_PENDING":
            team = goal.goal_target or ctx_view.get("pending_team")
            if not team:
                try:
                    from src.conversation.state_driven_resolution import pre_resolve

                    pr = pre_resolve(message, ctx)
                    if pr.single_team:
                        team = pr.single_team
                except Exception:
                    team = None
            if team:
                goal.goal_target = str(team)
                try:
                    from src.conversation.conversation_state import note_pending_team

                    note_pending_team(ctx, str(team))
                    ctx_view = resolve_context_priority(ctx)
                except Exception:
                    pass

        rewritten = apply_goal_to_reasoning(goal, ctx_view, base)
        ctx["last_reasoning"] = rewritten
        ctx[CIL_GOAL_KEY] = goal.to_dict()

        strategy = _strategy_for_goal(goal)
        thought = ConversationThought(
            user_intent=str(goal.goal_type),
            possible_interpretations=[h.to_dict() for h in hyps[:5]],
            selected_interpretation=str(goal.goal_type),
            reasoning=(
                f"priority={ctx_view.get('priority_winner')}; "
                f"target={goal.goal_target!r}; subject={goal.goal_subject!r}; "
                f"alts={goal.alternatives}"
            ),
            confidence=float(goal.goal_confidence),
            response_strategy=strategy,
            context_priority=[
                "pending_question",
                "active_fixture",
                "active_market",
                "fixture_history",
                "market_history",
            ],
            reflection_notes=refl,
        )
        # Optional humanized override for later CRL refine
        override = build_cil_reply(goal, message, ctx, ctx_view)
        if override:
            ctx["cil_reply_override"] = override
            # Second reflection on draft
            goal2, refl2 = reflect(goal, hyps, ctx_view, override)
            if goal2.goal_type != goal.goal_type:
                rewritten = apply_goal_to_reasoning(goal2, ctx_view, base)
                ctx["last_reasoning"] = rewritten
                ctx[CIL_GOAL_KEY] = goal2.to_dict()
                thought.selected_interpretation = str(goal2.goal_type)
                thought.user_intent = str(goal2.goal_type)
                thought.response_strategy = _strategy_for_goal(goal2)
                override = build_cil_reply(goal2, message, ctx, ctx_view)
                if override:
                    ctx["cil_reply_override"] = override
            thought.reflection_notes = list(thought.reflection_notes) + refl2

        ctx[CIL_THOUGHT_KEY] = thought.to_dict()
        return thought
    except Exception as exc:
        logger.warning("conversation_intelligence_layer fail-open: %s", exc)
        thought = ConversationThought(
            user_intent="UNKNOWN",
            selected_interpretation="UNKNOWN",
            reasoning=f"fail_open: {exc}",
            confidence=0.0,
            response_strategy="FULL_ANALYSIS",
            reflection_notes=["fail_open"],
        )
        if ctx is not None:
            ctx[CIL_THOUGHT_KEY] = thought.to_dict()
        return thought


def refine_crl_reply(
    reply_text: str | None,
    ctx: dict[str, Any] | None,
) -> str | None:
    """
    Apply CIL humanized override / de-templatize CRL text.
    Does not modify CRL module — used by router after plan_response.
    """
    if ctx and ctx.get("cil_reply_override"):
        return str(ctx["cil_reply_override"])
    if not reply_text:
        return reply_text
    # Soft humanize CRL stock openers
    goal = (ctx or {}).get(CIL_GOAL_KEY) or {}
    g = str(goal.get("goal_type") or "")
    family = "neutral"
    if g.startswith("COMPARE"):
        family = "comparison"
    elif g == "ASK_EXPLANATION":
        family = "explain"
    elif g in {"ASK_BEST_OPTION", "ASK_SAFER_OPTION", "ASK_RISKIER_OPTION", "REJECT_MARKET"}:
        family = "alternative"
    elif g == "CONTINUE_PENDING":
        family = "clarify"
    elif g in {"FOLLOWUP_MARKET", "ASK_OPINION"}:
        family = "opinion"
    return humanize_text(reply_text, family=family, ctx=ctx)
