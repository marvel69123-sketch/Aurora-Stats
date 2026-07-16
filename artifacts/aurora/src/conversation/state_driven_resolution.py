"""
Aurora v3.7.6 — State Driven Resolution (additive).

Active use of conversation_state:
  - sports alias expansion
  - light pre-resolve (before main Resolver — does NOT edit Resolver)
  - contextual option generation from active_* + histories

Sacred rules:
  - NEVER invent fixtures / opponents / live stats / odds
  - Single-team → clarify opponent
  - Fail-open
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

HISTORY_MAX = 5

# Additive sports aliases (conversation layer only — Resolver untouched)
SPORTS_ALIASES: dict[str, str] = {
    "fla": "Flamengo",
    "mengao": "Flamengo",
    "fogao": "Botafogo",
    "vascao": "Vasco",
    "vasco gama": "Vasco",
    "vasco da gama": "Vasco",
    "peixe": "Santos",
    "trikas": "Sao Paulo",
    "tricolor": "Sao Paulo",
    "galo": "Atletico Mineiro",
    "timao": "Corinthians",
    "verdao": "Palmeiras",
    "vitoria ba": "Vitoria",
    "vitória ba": "Vitoria",
    "leao": "Fortaleza",
    "leão": "Fortaleza",
    "furacao": "Athletico Paranaense",
    "furacão": "Athletico Paranaense",
    "flu": "Fluminense",
}

_FIXTURE_RE = re.compile(
    r"\b([A-Za-zÀ-ÿ0-9][A-Za-zÀ-ÿ0-9.\s-]{1,40}?)\s+(?:x|vs|versus)\s+"
    r"([A-Za-zÀ-ÿ0-9][A-Za-zÀ-ÿ0-9.\s-]{1,40})\b",
    re.I,
)

_SINGLE_TEAM_RE = re.compile(
    r"(?:o\s+que\s+acha\s+d[oe]|fala\s+d[oe]|analis[ae]\s+(?:o|a)?|"
    r"como\s+(?:esta|está)\s+(?:o|a)?)\s+"
    r"([A-Za-zÀ-ÿ0-9][A-Za-zÀ-ÿ0-9.\s-]{1,40}?)(?:\s+hoje)?\s*$",
    re.I,
)

_MARKET_TOKENS = {
    "gol",
    "gols",
    "escanteio",
    "escanteios",
    "cartao",
    "cartoes",
    "corner",
    "corners",
    "btts",
    "over",
    "under",
    "mercado",
}


def _fold(text: str) -> str:
    t = unicodedata.normalize("NFKD", (text or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^\w\sx/-]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _pretty(name: str) -> str:
    n = (name or "").strip()
    if not n:
        return n
    # Keep known multi-word canons
    return " ".join(p[:1].upper() + p[1:] if p else p for p in n.split())


def resolve_alias(token: str) -> tuple[str, str | None]:
    """Return (display_name, alias_key_or_None). Never invents."""
    folded = _fold(token)
    if not folded or folded in _MARKET_TOKENS:
        return token.strip(), None
    # longer keys first
    for key in sorted(SPORTS_ALIASES.keys(), key=len, reverse=True):
        if folded == _fold(key) or folded.startswith(_fold(key) + " "):
            return SPORTS_ALIASES[key], key
    # try TEAM_ALIASES read-only
    try:
        from src.core.team_aliases import TEAM_ALIASES

        if folded in TEAM_ALIASES:
            return str(TEAM_ALIASES[folded]), folded
        for key in sorted(TEAM_ALIASES.keys(), key=len, reverse=True):
            if len(key) < 3:
                continue
            if folded == _fold(key):
                return str(TEAM_ALIASES[key]), key
    except Exception:
        pass
    return _pretty(token), None


def expand_sports_aliases(message: str) -> tuple[str, list[str]]:
    """Expand aliases inside a message. Does not add opponents."""
    applied: list[str] = []
    folded = _fold(message or "")
    if re.search(r"\bhj\b", folded):
        folded = re.sub(r"\bhj\b", "hoje", folded)
        applied.append("hj->hoje")

    keys = sorted(
        set(list(SPORTS_ALIASES.keys()) ),
        key=len,
        reverse=True,
    )
    out = f" {folded} "
    for key in keys:
        canon = SPORTS_ALIASES[key]
        pat = re.compile(rf"(?<!\w){re.escape(_fold(key))}(?!\w)")
        if pat.search(out):
            out = pat.sub(f" {_fold(canon)} ", out)
            applied.append(f"{key}->{canon}")
    return re.sub(r"\s+", " ", out).strip(), applied


@dataclass
class PreResolveResult:
    original: str
    rewritten: str
    home: str | None = None
    away: str | None = None
    fixture_label: str | None = None
    aliases_applied: list[str] = field(default_factory=list)
    needs_opponent: bool = False
    single_team: str | None = None
    confidence: float = 0.0
    reused_active_fixture: bool = False
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def pre_resolve(message: str, ctx: dict[str, Any] | None = None) -> PreResolveResult:
    """
    Light pre-resolver BEFORE the main Resolver.
    - Expands sports aliases
    - Extracts explicit A x B
    - Reuses active_fixture for market-only follow-ups (metadata only)
    - NEVER invents a second team
    """
    original = (message or "").strip()
    expanded, aliases = expand_sports_aliases(original)
    result = PreResolveResult(
        original=original,
        rewritten=expanded or original,
        aliases_applied=aliases,
    )

    # Market-only follow-up → reuse active fixture context (no rewrite into Team x Team Market)
    from src.conversation.conversation_state import active_fixture, get_state

    fx = active_fixture(ctx)
    market_only = bool(
        re.match(
            r"^(?:e\s+)?(?:pra\s+|para\s+)?"
            r"(gols?|escanteios?|corners?|cantos?|cart[oõ]es?|cart[aã]o|cards?|btts|"
            r"ambos\s+marcam|over|under)\s*\??$",
            _fold(expanded),
            re.I,
        )
    )
    if market_only and fx:
        result.fixture_label = fx
        result.reused_active_fixture = True
        result.confidence = 0.92
        result.notes.append("reuse_active_fixture_for_market_followup")
        st = get_state(ctx)
        result.home = st.get("active_home")
        result.away = st.get("active_away")
        # Keep market phrase for FollowUp — do not inject teams into rewritten
        result.rewritten = expanded
        return result

    m = _FIXTURE_RE.search(expanded)
    if m:
        raw_home, raw_away = m.group(1).strip(), m.group(2).strip()
        # Drop leading verbs accidentally captured by the left team group
        raw_home = re.sub(
            r"^(?:analisar|analise|analisa|ver|veja|checar|olha(?:r)?)\s+",
            "",
            raw_home,
            flags=re.I,
        ).strip()
        home, a1 = resolve_alias(raw_home)
        away, a2 = resolve_alias(raw_away)
        if a1:
            aliases.append(f"{a1}->{home}")
        if a2:
            aliases.append(f"{a2}->{away}")
        # Guard: market token as "team" → ignore pair
        if _fold(home) in _MARKET_TOKENS or _fold(away) in _MARKET_TOKENS:
            result.notes.append("rejected_market_as_team")
            result.aliases_applied = aliases
            return result
        label = f"{home} x {away}"
        # Rewrite only the fixture span to canonical names
        rewritten = expanded[: m.start()] + f"{home} x {away}" + expanded[m.end() :]
        # Restore analyze prefix casing lightly
        result.rewritten = re.sub(r"\s+", " ", rewritten).strip()
        result.home = home
        result.away = away
        result.fixture_label = label
        result.aliases_applied = aliases
        result.confidence = 0.9 if (a1 or a2 or aliases) else 0.85
        result.notes.append("explicit_fixture")
        return result

    # Single team chat — clarify, never invent
    sm = _SINGLE_TEAM_RE.search(expanded)
    if sm and not re.search(r"\bx\b|\bvs\b", expanded, re.I):
        team_raw = sm.group(1).strip()
        team, ak = resolve_alias(team_raw)
        if _fold(team) not in _MARKET_TOKENS and len(_fold(team)) >= 3:
            result.needs_opponent = True
            result.single_team = team
            result.aliases_applied = aliases + ([f"{ak}->{team}"] if ak else [])
            result.confidence = 0.55
            result.notes.append("single_team_needs_opponent")
            # Prefer canonical team name in rewritten for downstream clarify
            result.rewritten = expanded.replace(team_raw, team, 1) if team_raw != team else expanded
            return result

    result.aliases_applied = aliases
    result.confidence = 0.4 if aliases else 0.2
    return result


def _risk_rank(level: str | None) -> int:
    if not level:
        return 2
    t = str(level).strip().lower()
    if t in {"low", "baixo", "conservador"}:
        return 1
    if t in {"medium", "medio", "médio", "moderado"}:
        return 2
    if t in {"high", "alto", "agressivo"}:
        return 3
    return 2


def _market_family(market: str | None) -> str:
    m = _fold(market or "")
    if "escanteio" in m or "corner" in m or "canto" in m:
        return "corners"
    if "cart" in m:
        return "cards"
    if "btts" in m or "ambos" in m:
        return "btts"
    if "under" in m or "menos" in m:
        return "goals_under"
    if "over" in m or "mais" in m or "gol" in m:
        return "goals_over"
    return "generic"


def suggest_alternatives(
    *,
    bias: str,
    active_market: str | None,
    last_risk: str | None,
    market_history: list[dict[str, Any]] | None = None,
) -> list[str]:
    """
    Textual alternative suggestions — NOT live odds, NOT invented fixtures.
    bias: conservative | aggressive | better
    """
    family = _market_family(active_market)
    tried = {
        _fold(str(h.get("market") or ""))
        for h in (market_history or [])
        if isinstance(h, dict)
    }
    if active_market:
        tried.add(_fold(active_market))

    if bias == "conservative":
        pool = {
            "corners": [
                "linha de escanteios mais baixa",
                "under de escanteios",
                "stake reduzida no mercado atual",
            ],
            "cards": [
                "under de cartões",
                "linha de cartões mais baixa",
                "stake reduzida",
            ],
            "btts": [
                "under 2.5 gols",
                "1X / Dupla chance",
                "stake reduzida em BTTS",
            ],
            "goals_over": [
                "under 2.5 gols",
                "over com linha mais baixa",
                "stake reduzida",
            ],
            "goals_under": [
                "under com linha mais confortável",
                "Dupla chance",
                "stake reduzida",
            ],
            "generic": [
                "mercado de menor risco (under / dupla chance)",
                "linha mais baixa",
                "stake reduzida",
            ],
        }[family]
    elif bias == "aggressive":
        pool = {
            "corners": [
                "over de escanteios com linha mais alta",
                "escanteios no 2º tempo",
                "stake um pouco maior (se o perfil permitir)",
            ],
            "cards": [
                "over de cartões",
                "cartões no 2º tempo",
                "linha mais alta",
            ],
            "btts": [
                "over 2.5 / 3.5 gols",
                "BTTS + over",
                "resultado exato (alto risco)",
            ],
            "goals_over": [
                "over com linha mais alta",
                "BTTS",
                "over no 2º tempo",
            ],
            "goals_under": [
                "over 2.5 (inversão de viés)",
                "BTTS",
                "linha mais arriscada",
            ],
            "generic": [
                "over / BTTS",
                "linha mais alta",
                "mercado de maior risco",
            ],
        }[family]
    else:  # better — diversify away from current
        pool = {
            "corners": ["gols (over/under)", "BTTS", "cartões"],
            "cards": ["gols", "escanteios", "BTTS"],
            "btts": ["over/under gols", "escanteios", "dupla chance"],
            "goals_over": ["escanteios", "BTTS", "under (hedge)"],
            "goals_under": ["escanteios", "BTTS", "over (se mudar o viés)"],
            "generic": ["gols", "escanteios", "cartões"],
        }[family]

    # Prefer suggestions not already echoed as market labels in history
    out: list[str] = []
    for s in pool:
        if _fold(s) not in tried:
            out.append(s)
        if len(out) >= 3:
            break
    if not out:
        out = list(pool)[:3]

    # Risk-aware nudge
    if bias == "conservative" and _risk_rank(last_risk) >= 3:
        out.insert(0, "reduzir exposição — o risco atual está alto")
    if bias == "aggressive" and _risk_rank(last_risk) <= 1:
        out.insert(0, "subir um degrau de risco com controle de stake")
    return out[:3]


def build_state_driven_reply(
    intent: str,
    ctx: dict[str, Any] | None,
) -> str | None:
    """
    Richer contextual generation using active_* + market_history + fixture_history.
    """
    from src.conversation.conversation_state import (
        active_fixture,
        active_market,
        get_state,
        hydrate_from_legacy,
    )

    if ctx is not None:
        hydrate_from_legacy(ctx)
    state = get_state(ctx)
    fixture = state.get("active_fixture") or active_fixture(ctx)
    market = state.get("active_market") or active_market(ctx)
    risk = state.get("last_risk_level")
    rec = state.get("last_recommendation")
    prev_kind = state.get("last_reply_kind")
    m_hist = list(state.get("market_history") or [])
    f_hist = list(state.get("fixture_history") or [])

    if intent == "ASK_CONSERVATIVE_OPTION":
        if not fixture and not market:
            return None
        alts = suggest_alternatives(
            bias="conservative",
            active_market=market if isinstance(market, str) else None,
            last_risk=risk if isinstance(risk, str) else None,
            market_history=m_hist,
        )
        lines = ["Beleza — perfil mais conservador, usando o estado da conversa."]
        if market:
            lines.append(f'Mercado atual: "{market}".')
        if risk:
            lines.append(f"Risco atual: {risk}.")
        if rec:
            lines.append(f"Última recomendação: {rec[:120]}.")
        if fixture:
            lines.append(f"Jogo ativo: {fixture}.")
        lines.append("Alternativas mais seguras (sugestão contextual, sem odds inventadas):")
        for a in alts:
            lines.append(f"• {a}")
        if prev_kind == "REJECT_MARKET":
            lines.append("Sigo no conservador — sem repetir o menu anterior.")
        return "\n".join(lines)

    if intent == "ASK_AGGRESSIVE_OPTION":
        if not fixture and not market:
            return None
        alts = suggest_alternatives(
            bias="aggressive",
            active_market=market if isinstance(market, str) else None,
            last_risk=risk if isinstance(risk, str) else None,
            market_history=m_hist,
        )
        lines = ["Certo — perfil mais agressivo, ancorado no estado atual."]
        if market:
            lines.append(f'Saindo de: "{market}".')
        if risk:
            lines.append(f"Risco atual: {risk}.")
        if fixture:
            lines.append(f"Jogo ativo: {fixture}.")
        lines.append("Caminhos mais agressivos (sem inventar números):")
        for a in alts:
            lines.append(f"• {a}")
        return "\n".join(lines)

    if intent == "ASK_BETTER_OPTION":
        if not fixture and not market:
            return None
        alts = suggest_alternatives(
            bias="better",
            active_market=market if isinstance(market, str) else None,
            last_risk=risk if isinstance(risk, str) else None,
            market_history=m_hist,
        )
        lines = ["Sim — posso buscar algo melhor com base no que já vimos."]
        if market:
            lines.append(f'Mercado em foco: "{market}".')
        if rec:
            lines.append(f"Recomendação lembrada: {rec[:120]}.")
        if m_hist:
            recent = [
                str(h.get("market"))
                for h in m_hist[:3]
                if isinstance(h, dict) and h.get("market")
            ]
            if recent:
                lines.append("Já comentados nesta conversa: " + "; ".join(recent) + ".")
        if fixture:
            lines.append(f"Confronto ativo: {fixture}.")
        lines.append("Outras frentes possíveis:")
        for a in alts:
            lines.append(f"• {a}")
        lines.append("Diga se quer viés conservador, agressivo ou outro mercado.")
        return "\n".join(lines)

    if intent == "ASK_COMPARISON":
        if not fixture and not f_hist:
            return None
        prev_fx = None
        if f_hist:
            top = f_hist[0]
            if isinstance(top, dict):
                prev_fx = top.get("fixture")
        if not prev_fx and ctx:
            ph = (ctx.get("prev_home") or "").strip()
            pa = (ctx.get("prev_away") or "").strip()
            if ph and pa:
                prev_fx = f"{ph} x {pa}"
            else:
                prev_fx = (ctx.get("prev_match") or ctx.get("prev_fixture") or "").strip() or None

        lines = ["Comparando com o histórico da conversa (sem inventar estatísticas):"]
        if fixture:
            mbit = f" — mercado: {market}" if market else ""
            rbit = f" — risco: {risk}" if risk else ""
            lines.append(f"• Atual: {fixture}{mbit}{rbit}")
        if prev_fx and str(prev_fx).lower() != str(fixture or "").lower():
            prev_m = None
            if f_hist and isinstance(f_hist[0], dict):
                prev_m = f_hist[0].get("market")
            pbit = f" — mercado: {prev_m}" if prev_m else ""
            lines.append(f"• Anterior: {prev_fx}{pbit}")
            lines.append("Qual dos dois quer aprofundar?")
        else:
            lines.append(
                "Só tenho um confronto claro no estado ativo. "
                "Analise outro jogo para eu comparar os dois."
            )
        return "\n".join(lines)

    return None
