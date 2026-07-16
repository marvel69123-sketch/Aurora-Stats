"""
Aurora v3.7.6 — Conversation State Engine + State Driven Resolution.

Active short-term conversational memory. Fail-open. Reversible.

v3.7.6 adds:
  - market_history / fixture_history
  - sports aliases + light pre-resolve (before main Resolver)
  - contextual generation for conservative / aggressive / better / compare

Does NOT:
  - invent fixtures / opponents / live stats
  - edit FollowUp engine, Resolver, Integrity, payloads, or frozen modules
  - turn Aurora into Casual mode (infrastructure only)

Router-facing order (desired):
  Message → Normalization → Conversation State / Pre-Resolve → Intent → FollowUp → Engines
"""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Literal

logger = logging.getLogger(__name__)

CONVERSATION_STATE_TTL_SECONDS = 10 * 60
STATE_KEY = "conversation_state"

HumanIntent = Literal[
    "ASK_BETTER_OPTION",
    "ASK_CONSERVATIVE_OPTION",
    "ASK_AGGRESSIVE_OPTION",
    "ASK_EXPLANATION",
    "ASK_COMPARISON",
    "REJECT_MARKET",
    "CHANGE_TOPIC",
    "ASK_MORE_DETAILS",
    "ASK_MARKET_DETAILS",
]

ConversationMode = Literal["sports", "social", "idle", "clarify"]

# Soft fuzzy / nickname expansions — prefer shared SPORTS_ALIASES (v3.7.6)
try:
    from src.conversation.state_driven_resolution import SPORTS_ALIASES as _FUZZY_NICKS
except Exception:  # pragma: no cover
    _FUZZY_NICKS = {
        "fla": "Flamengo",
        "fogao": "Botafogo",
        "vascao": "Vasco",
        "peixe": "Santos",
        "vitoria ba": "Vitoria",
    }

HISTORY_MAX = 5

_MARKET_FOLLOW = re.compile(
    r"^(?:e\s+)?(?:pra\s+|para\s+)?"
    r"(gols?|escanteios?|corners?|cantos?|cart[oõ]es?|cart[aã]o|cards?|btts|"
    r"ambos\s+marcam|over|under)\s*\??$",
    re.I,
)

_INTENT_SPECS: list[tuple[re.Pattern[str], HumanIntent]] = [
    (
        re.compile(
            r"\b(nao\s+gostei(?:\s+d(?:esse|isso|este)?(?:\s+mercado)?)?|"
            r"nao\s+me\s+convenceu|esse\s+parece\s+ruim)\b",
            re.I,
        ),
        "REJECT_MARKET",
    ),
    # Comparison before conservative — "qual dos dois é mais seguro?" is compare
    (
        re.compile(
            r"\b(compare(?:\s+os\s+dois)?|comparar|comparado\s+ao|qual\s+dos\s+dois|"
            r"esse\s+ta\s+melhor|esse\s+parece\s+melhor|esse\s+parece\s+pior|"
            r"melhor\s+q(?:ue)?\s+o\s+outro|o\s+anterior)\b",
            re.I,
        ),
        "ASK_COMPARISON",
    ),
    (
        re.compile(
            r"\b(algo\s+mais\s+conservador|mais\s+conservador|mais\s+seguro|"
            r"menor\s+risco|opcao\s+conservadora|opção\s+conservadora)\b",
            re.I,
        ),
        "ASK_CONSERVATIVE_OPTION",
    ),
    (
        re.compile(
            r"\b(algo\s+mais\s+agressivo|mais\s+agressivo|maior\s+risco|"
            r"opcao\s+agressiva|opção\s+agressiva)\b",
            re.I,
        ),
        "ASK_AGGRESSIVE_OPTION",
    ),
    (
        re.compile(
            r"\b(tem\s+algo\s+melhor|algo\s+melhor|outra\s+opcao|outra\s+opção|"
            r"algo\s+diferente)\b",
            re.I,
        ),
        "ASK_BETTER_OPTION",
    ),
    (
        re.compile(
            r"\b(explique\s+melhor|explica\s+melhor|por\s+que\??|porque\??|"
            r"porquê\??|me\s+explica)\b",
            re.I,
        ),
        "ASK_EXPLANATION",
    ),
    (
        re.compile(
            r"\b(detalhe\s+mais|mais\s+detalhes?|pode\s+detalhar|"
            r"quero\s+mais\s+detalhe)\b",
            re.I,
        ),
        "ASK_MORE_DETAILS",
    ),
    (
        re.compile(
            r"\b(outro\s+assunto|muda(?:r)?\s+de\s+assunto|cancela(?:r)?|"
            r"esquece(?:\s+isso)?|nova\s+conversa|limpar?\s+contexto)\b",
            re.I,
        ),
        "CHANGE_TOPIC",
    ),
]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _utcnow_iso() -> str:
    return _utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _fold(text: str) -> str:
    t = unicodedata.normalize("NFKD", (text or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^\w\sx/-]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def empty_state() -> dict[str, Any]:
    return {
        "active_fixture": None,
        "active_home": None,
        "active_away": None,
        "active_market": None,
        "active_team": None,
        "active_topic": None,
        "last_intent": None,
        "last_recommendation": None,
        "last_risk_level": None,
        "pending_question": False,
        "conversation_mode": "idle",
        "last_message_time": None,
        "last_reply_kind": None,
        "market_history": [],
        "fixture_history": [],
        "updated_at": None,
    }


def get_state(ctx: dict[str, Any] | None) -> dict[str, Any]:
    if not ctx:
        return empty_state()
    raw = ctx.get(STATE_KEY)
    if not isinstance(raw, dict):
        return empty_state()
    base = empty_state()
    base.update({k: raw.get(k, base.get(k)) for k in base})
    return base


def set_state(ctx: dict[str, Any], state: dict[str, Any]) -> None:
    merged = empty_state()
    merged.update(state or {})
    merged["updated_at"] = _utcnow_iso()
    merged["last_message_time"] = merged.get("last_message_time") or merged["updated_at"]
    ctx[STATE_KEY] = merged


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts or not isinstance(ts, str):
        return None
    try:
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except Exception:
        return None


def is_state_expired(
    ctx: dict[str, Any] | None,
    *,
    ttl: int = CONVERSATION_STATE_TTL_SECONDS,
) -> bool:
    state = get_state(ctx)
    if not state.get("active_fixture") and not state.get("active_market"):
        # Nothing conversational to expire
        stamp = state.get("last_message_time") or state.get("updated_at")
        if not stamp:
            return False
    stamp = state.get("last_message_time") or state.get("updated_at")
    dt = _parse_iso(stamp if isinstance(stamp, str) else None)
    if dt is None:
        # Missing stamp with active fields → treat as expired (fail-safe)
        return bool(state.get("active_fixture") or state.get("active_market"))
    return (_utcnow() - dt).total_seconds() > ttl


def clear_conversational_fields(
    ctx: dict[str, Any],
    *,
    keep_history: bool = True,
) -> None:
    """
    Clear short-term conversational context only.
    By default keeps market_history / fixture_history (TTL expire).
    Cancel/reset should call with keep_history=False.
    Legacy prev_* / last_analysis outside state are untouched here.
    """
    prev = get_state(ctx)
    state = empty_state()
    if keep_history:
        state["market_history"] = list(prev.get("market_history") or [])
        state["fixture_history"] = list(prev.get("fixture_history") or [])
    state["conversation_mode"] = "idle"
    state["updated_at"] = _utcnow_iso()
    state["last_message_time"] = state["updated_at"]
    ctx[STATE_KEY] = state


def expire_conversation_state_if_needed(ctx: dict[str, Any]) -> bool:
    """Expire active conversational fields after TTL. Returns True if cleared."""
    if not ctx.get(STATE_KEY):
        return False
    if not is_state_expired(ctx):
        return False
    clear_conversational_fields(ctx)
    logger.warning("[AUDIT] ConversationState: EXPIRED — conversational fields cleared")
    return True


def hydrate_from_legacy(ctx: dict[str, Any]) -> dict[str, Any]:
    """
    Ensure conversation_state mirrors last_* when state is empty but legacy
    fixture memory exists. Never invents teams.
    """
    state = get_state(ctx)
    if state.get("active_fixture") or state.get("active_market"):
        return state

    home = (ctx.get("last_home") or "").strip() or None
    away = (ctx.get("last_away") or "").strip() or None
    match = (ctx.get("last_match") or ctx.get("last_fixture") or "").strip() or None
    if home and away:
        match = match or f"{home} x {away}"
    if not match and not (home and away):
        return state

    market = _market_label_from_ctx(ctx)
    risk = _risk_from_ctx(ctx)
    rec = ctx.get("last_recommendation") or ctx.get("last_final_recommendation")
    if isinstance(rec, str):
        rec = rec.strip()[:200] or None
    else:
        rec = None

    state.update(
        {
            "active_fixture": match,
            "active_home": home,
            "active_away": away,
            "active_market": market,
            "active_topic": "markets" if market else "fixture",
            "last_recommendation": rec,
            "last_risk_level": risk,
            "conversation_mode": "sports",
            "pending_question": False,
            "last_message_time": ctx.get("updated_at") or _utcnow_iso(),
            "updated_at": ctx.get("updated_at") or _utcnow_iso(),
        }
    )
    ctx[STATE_KEY] = state
    return state


def _market_label_from_ctx(ctx: dict[str, Any] | None) -> str | None:
    if not ctx:
        return None
    markets = ctx.get("last_market")
    if isinstance(markets, list) and markets:
        top = markets[0]
        if isinstance(top, dict):
            name = top.get("market") or top.get("name")
            if name:
                return str(name)
    if isinstance(markets, dict):
        name = markets.get("market") or markets.get("name")
        if name:
            return str(name)
    return None


def _risk_from_ctx(ctx: dict[str, Any] | None) -> str | None:
    if not ctx:
        return None
    analysis = ctx.get("last_analysis")
    if isinstance(analysis, dict):
        risk = analysis.get("risk")
        if isinstance(risk, dict):
            level = risk.get("level")
            if level:
                return str(level)
        # best market risk
        markets = analysis.get("best_markets")
        if isinstance(markets, list) and markets and isinstance(markets[0], dict):
            r = markets[0].get("risk")
            if r:
                return str(r)
    return None


def _push_history(items: list[Any], entry: dict[str, Any], *, max_n: int = HISTORY_MAX) -> list[Any]:
    out = [entry] + [x for x in items if isinstance(x, dict)]
    return out[:max_n]


def apply_after_analysis(
    ctx: dict[str, Any],
    home: str,
    away: str,
    match: str | None,
    payload: dict[str, Any] | None = None,
) -> None:
    """Replace active fixture/market and push histories. Additive."""
    payload = payload or {}
    label = (match or f"{home} x {away}").strip()
    markets = payload.get("best_markets")
    market_name = None
    risk = None
    if isinstance(markets, list) and markets and isinstance(markets[0], dict):
        market_name = markets[0].get("market") or markets[0].get("name")
        risk = markets[0].get("risk")
    if not risk:
        r = payload.get("risk")
        if isinstance(r, dict):
            risk = r.get("level")
    rec = payload.get("final_recommendation")
    if isinstance(rec, str):
        rec = rec.strip()[:200] or None
    else:
        rec = None

    state = get_state(ctx)
    old_fx = state.get("active_fixture")
    old_home = state.get("active_home")
    old_away = state.get("active_away")
    old_market = state.get("active_market")
    old_risk = state.get("last_risk_level")
    old_rec = state.get("last_recommendation")
    f_hist = list(state.get("fixture_history") or [])
    m_hist = list(state.get("market_history") or [])

    # Push previous active fixture when switching
    if old_fx and str(old_fx).lower() != label.lower():
        f_hist = _push_history(
            f_hist,
            {
                "fixture": old_fx,
                "home": old_home,
                "away": old_away,
                "market": old_market,
                "risk": old_risk,
                "recommendation": old_rec,
                "at": state.get("updated_at") or _utcnow_iso(),
            },
        )

    # Push market into history (new or change)
    if market_name:
        m_hist = _push_history(
            m_hist,
            {
                "market": str(market_name),
                "risk": str(risk) if risk else None,
                "recommendation": rec,
                "fixture": label,
                "at": _utcnow_iso(),
            },
        )

    state.update(
        {
            "active_fixture": label,
            "active_home": home,
            "active_away": away,
            "active_market": str(market_name) if market_name else None,
            "active_team": None,
            "active_topic": "markets" if market_name else "fixture",
            "last_intent": "ANALYZE_MATCH",
            "last_recommendation": rec,
            "last_risk_level": str(risk) if risk else None,
            "pending_question": False,
            "conversation_mode": "sports",
            "last_reply_kind": None,
            "fixture_history": f_hist,
            "market_history": m_hist,
            "last_message_time": _utcnow_iso(),
            "updated_at": _utcnow_iso(),
        }
    )
    ctx[STATE_KEY] = state


def note_small_talk(ctx: dict[str, Any]) -> None:
    """Mark social turn without wiping sports memory."""
    state = get_state(ctx)
    # Preserve sports fields; only mode/time change
    if state.get("active_fixture") or state.get("active_market"):
        state["conversation_mode"] = "sports"  # sports context still active
    else:
        state["conversation_mode"] = "social"
    state["last_message_time"] = _utcnow_iso()
    state["updated_at"] = state["last_message_time"]
    ctx[STATE_KEY] = state


def note_pending_team(ctx: dict[str, Any], team: str) -> None:
    state = get_state(ctx)
    state["active_team"] = team
    state["pending_question"] = True
    state["conversation_mode"] = "clarify"
    state["last_intent"] = "ASK_MORE_DETAILS"
    state["last_message_time"] = _utcnow_iso()
    state["updated_at"] = state["last_message_time"]
    ctx[STATE_KEY] = state


def touch_intent(ctx: dict[str, Any], intent: HumanIntent | str, *, reply_kind: str | None = None) -> None:
    state = get_state(ctx)
    state["last_intent"] = intent
    if reply_kind:
        state["last_reply_kind"] = reply_kind
    if state.get("active_fixture") or state.get("active_market"):
        state["conversation_mode"] = "sports"
    state["last_message_time"] = _utcnow_iso()
    state["updated_at"] = state["last_message_time"]
    ctx[STATE_KEY] = state


def detect_human_intent(message: str) -> HumanIntent | None:
    folded = _fold(message or "")
    if not folded:
        return None
    if _MARKET_FOLLOW.match(folded):
        return "ASK_MARKET_DETAILS"
    for pat, intent in _INTENT_SPECS:
        if pat.search(folded):
            return intent
    return None


def expand_fuzzy_terms(message: str) -> tuple[str, list[str]]:
    """
    Light fuzzy understanding via sports aliases (v3.7.6).
    Never invents a second team / fixture.
    """
    try:
        from src.conversation.state_driven_resolution import expand_sports_aliases

        return expand_sports_aliases(message)
    except Exception:
        applied: list[str] = []
        folded = _fold(message or "")
        if re.search(r"\bhj\b", folded):
            folded = re.sub(r"\bhj\b", "hoje", folded)
            applied.append("hj->hoje")
        keys = sorted(_FUZZY_NICKS.keys(), key=len, reverse=True)
        out = f" {folded} "
        for key in keys:
            canon = _FUZZY_NICKS[key]
            pat = re.compile(rf"(?<!\w){re.escape(_fold(key))}(?!\w)", re.I)
            if pat.search(out):
                out = pat.sub(f" {_fold(canon)} ", out)
                applied.append(f"{key}->{canon}")
        return re.sub(r"\s+", " ", out).strip(), applied


def pre_resolve_message(message: str, ctx: dict[str, Any] | None = None):
    """Public wrapper — light pre-resolve before main Resolver."""
    from src.conversation.state_driven_resolution import pre_resolve

    return pre_resolve(message, ctx)


def active_fixture(ctx: dict[str, Any] | None) -> str | None:
    state = get_state(ctx)
    fx = state.get("active_fixture")
    if isinstance(fx, str) and fx.strip():
        return fx.strip()
    # legacy fallback (still no invent)
    if not ctx:
        return None
    home = (ctx.get("last_home") or "").strip()
    away = (ctx.get("last_away") or "").strip()
    if home and away:
        return f"{home} x {away}"
    match = (ctx.get("last_match") or ctx.get("last_fixture") or "").strip()
    return match or None


def active_market(ctx: dict[str, Any] | None) -> str | None:
    state = get_state(ctx)
    m = state.get("active_market")
    if isinstance(m, str) and m.strip():
        return m.strip()
    return _market_label_from_ctx(ctx)


def build_human_reply(
    intent: HumanIntent,
    ctx: dict[str, Any] | None,
) -> str | None:
    """
    Contextual replies that use active_market / risk / recommendation / histories.
    v3.7.6: prefer state-driven generation for option/compare intents.
    """
    hydrate_from_legacy(ctx) if ctx is not None else None

    # Active state-driven generation (conservative / aggressive / better / compare)
    if intent in {
        "ASK_CONSERVATIVE_OPTION",
        "ASK_AGGRESSIVE_OPTION",
        "ASK_BETTER_OPTION",
        "ASK_COMPARISON",
    }:
        try:
            from src.conversation.state_driven_resolution import build_state_driven_reply

            driven = build_state_driven_reply(intent, ctx)
            if driven:
                return driven
        except Exception as exc:
            logger.warning("state_driven_reply fallback: %s", exc)

    state = get_state(ctx)
    fixture = state.get("active_fixture") or active_fixture(ctx)
    market = state.get("active_market") or active_market(ctx)
    risk = state.get("last_risk_level")
    rec = state.get("last_recommendation")

    if intent == "REJECT_MARKET":
        if not fixture and not market:
            return None
        lines = ["Entendi."]
        if market:
            lines.append(f"Mercado atual:\n{market}.")
        elif rec:
            lines.append(f"Última recomendação:\n{rec}.")
        if risk:
            lines.append(f"Risco em foco: {risk}.")
        if fixture:
            lines.append(f"Jogo: {fixture}.")
        lines.append(
            "Posso procurar:\n"
            "• algo mais conservador\n"
            "• algo mais agressivo\n"
            "• outro tipo de mercado"
        )
        return "\n".join(lines)

    if intent == "ASK_EXPLANATION":
        if not fixture and not market and not rec:
            return None
        bits = ["Vou explicar com o que temos na conversa — sem inventar números novos."]
        if market:
            bits.append(f'Mercado em foco: "{market}".')
        if risk:
            bits.append(f"Risco associado: {risk}.")
        if rec:
            bits.append(f"Recomendação anterior: {rec[:160]}.")
        if fixture:
            bits.append(f"Confronto: {fixture}.")
        bits.append(
            "Se quiser o racional completo de novo, peça para reanalisar o jogo "
            "ou detalhar o mercado."
        )
        return " ".join(bits)

    if intent == "ASK_MORE_DETAILS":
        if not fixture and not market:
            return None
        bits = ["Posso detalhar mais."]
        if market:
            bits.append(f'Foque no mercado "{market}" — diga o que quer aprofundar.')
        if fixture:
            bits.append(f"Contexto ativo: {fixture}.")
        bits.append("Exemplos: risco, stake, ou um mercado vizinho (gols / escanteios).")
        return " ".join(bits)

    if intent == "CHANGE_TOPIC":
        return (
            "Beleza — mudando de assunto. "
            "Contexto conversacional limpo. Pode começar de novo."
        )

    # ASK_MARKET_DETAILS handled as pass-through in CI / FollowUp
    return None


def should_pass_market_followup(message: str, ctx: dict[str, Any] | None) -> bool:
    """True when 'e gols?' etc. can reuse active_fixture."""
    if not _MARKET_FOLLOW.match(_fold(message or "")):
        return False
    return bool(active_fixture(ctx))


def sync_state_after_turn(
    ctx: dict[str, Any],
    *,
    intent: HumanIntent | str | None = None,
    reply_kind: str | None = None,
    pending_team: str | None = None,
) -> None:
    """Lightweight post-turn bookkeeping (fail-open safe)."""
    try:
        if pending_team:
            note_pending_team(ctx, pending_team)
        if intent:
            touch_intent(ctx, intent, reply_kind=reply_kind or str(intent))
        else:
            state = get_state(ctx)
            state["last_message_time"] = _utcnow_iso()
            state["updated_at"] = state["last_message_time"]
            ctx[STATE_KEY] = state
    except Exception as exc:
        logger.warning("conversation_state sync skipped: %s", exc)
