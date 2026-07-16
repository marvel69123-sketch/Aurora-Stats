"""
Aurora v3.7.2 — Conversation Intelligence + context gates (additive).

Inbound CI layers:
  Message → Normalization → Conversation Context → Intent → Confidence

Router order (outside this module):
  Small Talk → cancel/expire/topic-switch → CI → FollowUp → NL/engines

Sacred rules:
  - NEVER invent fixtures / opponents / live stats.
  - Market terms NEVER enter team-alias expansion / resolver-shaped rewrites.
  - On doubt → clarify. High confidence → safe rewrite OR pass-through for FollowUp.
  - Generic low band must NOT steal Small Talk.
  - Does NOT edit Resolver, FollowUp engine, Integrity, engines, or payload schemas.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Literal

logger = logging.getLogger(__name__)

ConfidenceBand = Literal["high", "medium", "low"]
ResponseKind = Literal["clarify", "conversational"]

# Pending single-team / fixture clarification TTL
CI_PENDING_TTL_SECONDS = 5 * 60

_CANCEL_RESET_RE = re.compile(
    r"^(?:cancela(?:r)?|esquece(?:\s+isso)?|deixa\s+pra\s+l[aá]|outro\s+assunto|"
    r"muda(?:r)?\s+de\s+assunto|limpar?\s+contexto|reset(?:ar)?|"
    r"nova\s+conversa|zera(?:r)?(?:\s+contexto)?)\s*[!.?]*$",
    re.I,
)
_TOPIC_SWITCH_RE = re.compile(
    r"\b([A-Za-zÀ-ÿ0-9][A-Za-zÀ-ÿ0-9.\s-]{1,40}?)\s+(?:x|vs|versus)\s+"
    r"([A-Za-zÀ-ÿ0-9][A-Za-zÀ-ÿ0-9.\s-]{1,40})\b",
    re.I,
)


@dataclass
class MessageIntelResult:
    original: str
    message_for_pipeline: str
    confidence_band: ConfidenceBand
    confidence: float
    intent_hint: str | None = None
    needs_clarification: bool = False
    clarification_prompt: str | None = None
    conversational_reply: str | None = None
    response_kind: ResponseKind | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Market terms (never treat as teams) ────────────────────────────────────

_MARKET_TERMS: frozenset[str] = frozenset(
    {
        "gol",
        "gols",
        "escanteio",
        "escanteios",
        "corner",
        "corners",
        "canto",
        "cantos",
        "cartao",
        "cartoes",
        "cartão",
        "cartões",
        "card",
        "cards",
        "btts",
        "ambas",
        "ambos",
        "marcam",
        "over",
        "under",
        "handicap",
        "placar",
        "resultado",
        "mercado",
        "mercados",
        "odd",
        "odds",
        "linha",
        "linhas",
    }
)

_MARKET_TERM_RE = re.compile(
    r"\b("
    r"gols?|escanteios?|corners?|cantos?|cart[aã]o|cart[oõ]es?|cards?|"
    r"btts|ambas?\s+marcam|ambos\s+marcam|over|under|handicap|"
    r"placar|resultado|mercados?"
    r")\b",
    re.I,
)

# Pure market follow-up — keep as-is for FollowUp (do NOT inject team names)
_FOLLOW_MARKET_ONLY = re.compile(
    r"^(?:e\s+)?(?:pra\s+|para\s+)?"
    r"(gols?|escanteios?|corners?|cantos?|cart[oõ]es?|cart[aã]o|cards?|"
    r"btts|ambos(?:\s+marcam)?|ambas(?:\s+marcam)?|over|under|handicap|"
    r"placar|resultado)\s*\??$",
    re.I,
)


def _is_market_token(token: str) -> bool:
    t = _fold(token)
    if t in _MARKET_TERMS:
        return True
    # multi-word handled by caller via _MARKET_TERM_RE
    return False


# ── Normalization maps ─────────────────────────────────────────────────────

_SLANG: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\boq\b", re.I), "o que"),
    (re.compile(r"\bhj\b", re.I), "hoje"),
    (re.compile(r"\bpq\b", re.I), "porque"),
    (re.compile(r"\bpra\b", re.I), "para"),
    (re.compile(r"\btbm\b", re.I), "tambem"),
    (re.compile(r"\btc\b", re.I), "voce"),
    (re.compile(r"\bvc\b", re.I), "voce"),
    (re.compile(r"\btá\b", re.I), "ta"),
    (re.compile(r"\baí\b", re.I), "ai"),
    (re.compile(r"\bq\b", re.I), "que"),
]

_TYPOS: dict[str, str] = {
    "sanots": "santos",
    "santso": "santos",
    "botafog": "botafogo",
    "botafgo": "botafogo",
    "flamnegp": "flamengo",
    "flamenog": "flamengo",
    "palmerias": "palmeiras",
    "palmeria": "palmeiras",
    "barcelna": "barcelona",
    "barcelon": "barcelona",
    "real madird": "real madrid",
    "liverpol": "liverpool",
}

_NICK_EXTRA: dict[str, str] = {
    "fla": "Flamengo",
    "mengao": "Flamengo",
    "mengão": "Flamengo",
    "fogao": "Botafogo",
    "fogão": "Botafogo",
    "peixe": "Santos",
    "verdao": "Palmeiras",
    "verdão": "Palmeiras",
    "galo": "Atletico Mineiro",
    "timao": "Corinthians",
    "timão": "Corinthians",
}


def _fold(text: str) -> str:
    t = unicodedata.normalize("NFKD", (text or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^\w\sx/-]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _apply_slang(text: str) -> str:
    out = text
    for pat, repl in _SLANG:
        out = pat.sub(repl, out)
    return out


def _apply_typos(text: str) -> tuple[str, list[str]]:
    folded = _fold(text)
    applied: list[str] = []
    for wrong, right in sorted(_TYPOS.items(), key=lambda kv: -len(kv[0])):
        if wrong in folded:
            folded = re.sub(rf"\b{re.escape(wrong)}\b", right, folded)
            applied.append(f"{wrong}->{right}")
    return folded, applied


def _expand_nicknames(folded: str) -> tuple[str, list[str]]:
    """Expand nicknames using TEAM_ALIASES (read-only). Never expand market terms."""
    applied: list[str] = []
    try:
        from src.core.team_aliases import TEAM_ALIASES
    except Exception:
        TEAM_ALIASES = {}

    keys = sorted(
        set(list(_NICK_EXTRA.keys()) + list(TEAM_ALIASES.keys())),
        key=len,
        reverse=True,
    )
    out = f" {folded} "
    for key in keys:
        if len(key) < 3 and key not in _NICK_EXTRA:
            continue
        if key in {"fc", "sc", "cf", "afc", "the", "de", "do", "da"}:
            continue
        if _is_market_token(key) or key in _MARKET_TERMS:
            continue
        canon = _NICK_EXTRA.get(key) or TEAM_ALIASES.get(key)
        if not canon:
            continue
        # Never rewrite a market token into a club name
        if _is_market_token(str(canon)):
            continue
        pat = re.compile(rf"(?<!\w){re.escape(key)}(?!\w)", re.I)
        if pat.search(out):
            # Skip if this token is part of a pure market follow-up phrase
            out = pat.sub(str(canon), out)
            applied.append(f"{key}->{canon}")
    return re.sub(r"\s+", " ", out).strip(), applied


def normalize_layer(message: str) -> tuple[str, dict[str, Any]]:
    raw = (message or "").strip()
    step = _apply_slang(raw)
    folded, typos = _apply_typos(step)
    # Protect market-only phrases: do not nickname-expand inside them
    if _FOLLOW_MARKET_ONLY.match(folded) or (
        _MARKET_TERM_RE.search(folded)
        and not re.search(r"\bx\b|\bvs\b", folded)
        and len(folded.split()) <= 4
    ):
        meta = {
            "slang": True,
            "typos": typos,
            "nicknames": [],
            "normalized": folded,
            "market_protected": True,
        }
        return folded, meta

    expanded, nicks = _expand_nicknames(folded)
    meta = {"slang": True, "typos": typos, "nicknames": nicks, "normalized": expanded}
    return expanded, meta


# ── Intent layer ───────────────────────────────────────────────────────────

_INTENT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"\b(nao\s+gostei|nao\s+me\s+convenceu|esse\s+parece\s+ruim|"
            r"tem\s+algo\s+melhor|outra\s+opcao|outra\s+opção|algo\s+diferente|"
            r"algo\s+mais\s+seguro|mais\s+conservador|menor\s+risco)\b",
            re.I,
        ),
        "prefer_alt",
    ),
    (re.compile(r"\b(gols?|over|under|btts|ambos\s+marcam|ambas\s+marcam)\b", re.I), "goals"),
    (re.compile(r"\b(escanteios?|corners?|cantos?)\b", re.I), "corners"),
    (re.compile(r"\b(cart[oõ]es?|cart[aã]o|cards?)\b", re.I), "cards"),
    (
        re.compile(
            r"\b(esse\s+ta\s+melhor|esse\s+parece\s+melhor|esse\s+parece\s+pior|"
            r"qual\s+dos\s+dois|comparado\s+ao|o\s+anterior|"
            r"melhor\s+que\s+o\s+outro|melhor\s+q\s+o\s+outro)\b",
            re.I,
        ),
        "compare",
    ),
    (re.compile(r"\b(analis|acha|fala\s+d[oe]|o\s+que\s+acha)\b", re.I), "analyze"),
]


def intent_layer(normalized: str) -> str | None:
    for pat, name in _INTENT_PATTERNS:
        if pat.search(normalized):
            return name
    return None


# ── Context layer ──────────────────────────────────────────────────────────

_DEIXIS = re.compile(
    r"\b(esse\s+jogo(?:\s+ai)?|esse\s+ai|desse\s+jogo|o\s+jogo|"
    r"esse\s+confronto|nessa\s+partida)\b",
    re.I,
)
_COMPARE = re.compile(
    r"\b(mais\s+conservador|mais\s+seguro|esse\s+ta\s+melhor|"
    r"esse\s+parece\s+melhor|esse\s+parece\s+pior|o\s+anterior|comparado\s+ao|"
    r"qual\s+dos\s+dois|melhor\s+que\s+o\s+outro|melhor\s+q\s+o\s+outro|"
    r"nao\s+gostei|nao\s+me\s+convenceu|tem\s+algo\s+melhor|"
    r"outra\s+opcao|outra\s+opção|algo\s+diferente|esse\s+parece\s+ruim)\b",
    re.I,
)


def _fixture_label(ctx: dict[str, Any] | None, *, which: str = "last") -> str | None:
    if not ctx:
        return None
    if which == "prev":
        home = (ctx.get("prev_home") or "").strip()
        away = (ctx.get("prev_away") or "").strip()
        if home and away:
            return f"{home} x {away}"
        match = (ctx.get("prev_match") or ctx.get("prev_fixture") or "").strip()
        return match or None
    home = (ctx.get("last_home") or "").strip()
    away = (ctx.get("last_away") or "").strip()
    if home and away:
        return f"{home} x {away}"
    match = (ctx.get("last_match") or ctx.get("last_fixture") or "").strip()
    return match or None


def _recommended_market_label(ctx: dict[str, Any] | None) -> str | None:
    if not ctx:
        return None
    # Prefer explicit last recommendation string if present
    rec = ctx.get("last_recommendation") or ctx.get("last_final_recommendation")
    if isinstance(rec, str) and rec.strip():
        return rec.strip()[:120]
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


def shift_fixture_memory(ctx: dict[str, Any], home: str, away: str, match: str | None = None) -> None:
    """
    When a new fixture is saved, push current last_* → prev_*.
    Additive memory for comparisons — never invents teams.
    """
    new_match = (match or f"{home} x {away}").strip()
    old_match = (ctx.get("last_match") or ctx.get("last_fixture") or "").strip()
    old_home = (ctx.get("last_home") or "").strip()
    old_away = (ctx.get("last_away") or "").strip()
    if not old_match and not (old_home and old_away):
        return
    # Same fixture → do not shift
    if old_home and old_away and home and away:
        if old_home.lower() == home.lower() and old_away.lower() == away.lower():
            return
    if old_match and new_match and old_match.lower() == new_match.lower():
        return
    ctx["prev_home"] = old_home or None
    ctx["prev_away"] = old_away or None
    ctx["prev_match"] = old_match or None
    ctx["prev_fixture"] = old_match or None
    ctx["prev_market"] = ctx.get("last_market")
    ctx["prev_recommendation"] = ctx.get("last_recommendation") or ctx.get(
        "last_final_recommendation"
    )


def _prefer_alt_reply(fixture: str | None, market: str | None) -> str:
    bits = []
    if market:
        bits.append(f'Entendi — o mercado "{market}" não te convenceu.')
    else:
        bits.append("Entendi — esse mercado não te convenceu.")
    bits.append(
        "Talvez um mercado mais conservador faça mais sentido. "
        "Posso procurar outra alternativa."
    )
    if fixture:
        bits.append(f"Quer que eu busque opções mais seguras em {fixture}?")
    else:
        bits.append("Me diga o jogo e eu busco uma alternativa mais segura.")
    return " ".join(bits)


def _compare_reply(last_fx: str, prev_fx: str | None, market: str | None) -> str:
    if prev_fx and prev_fx.lower() != last_fx.lower():
        m = f" (último mercado em foco: {market})" if market else ""
        return (
            f"Comparando o que temos na conversa:{m}\n"
            f"• Atual: {last_fx}\n"
            f"• Anterior: {prev_fx}\n"
            "Sem inventar números novos — diga qual dos dois quer reanalisar "
            "ou peça um mercado mais conservador em um deles."
        )
    # Only one fixture known — compare within same match / markets, not invent second
    m = f" sobre {market}" if market else ""
    return (
        f"No momento só tenho contexto claro de {last_fx}{m}. "
        "Para comparar com outro jogo, analise o segundo confronto "
        "(ex.: Analisar Time A x Time B) e pergunte de novo."
    )


def context_layer(
    normalized: str,
    ctx: dict[str, Any] | None,
    intent_hint: str | None,
) -> tuple[str, dict[str, Any], ConfidenceBand | None]:
    """
    Enrich with short conversation memory. Never invents home/away.
    Returns (enriched_text, meta, forced_band_or_None).

    meta may include:
      conversational_reply — short-circuit natural language (no engine invent)
      pass_through_followup — keep market phrase for FollowUp gate
    """
    meta: dict[str, Any] = {"context_used": False}
    fixture = _fixture_label(ctx, which="last")
    prev_fx = _fixture_label(ctx, which="prev")
    market = _recommended_market_label(ctx)
    text = normalized

    # 1) Pure market follow-up — NEVER rewrite into "Team x Team Market"
    #    (that made "escanteios" look like a team entity).
    if _FOLLOW_MARKET_ONLY.match(text.strip()):
        if fixture:
            meta["context_used"] = True
            meta["fixture"] = fixture
            meta["market_focus"] = text.strip()
            meta["pass_through_followup"] = True
            # Keep market-only phrase for FollowUp; do not inject teams into string
            return text.strip(), meta, "high"
        meta["reason"] = "market_followup_without_fixture"
        return text, meta, "low"

    # 2) Prefer-alt / dislike human intents → conversational short-circuit
    if intent_hint == "prefer_alt" or re.search(
        r"\b(nao\s+gostei|nao\s+me\s+convenceu|tem\s+algo\s+melhor|"
        r"outra\s+opcao|outra\s+opção|algo\s+diferente|esse\s+parece\s+ruim|"
        r"algo\s+mais\s+seguro|mais\s+conservador)\b",
        text,
        re.I,
    ):
        if fixture or market:
            meta["context_used"] = bool(fixture or market)
            meta["fixture"] = fixture
            meta["conversational_reply"] = _prefer_alt_reply(fixture, market)
            return text, meta, "high"
        meta["reason"] = "prefer_alt_without_fixture"
        return text, meta, "low"

    # 3) Deixis
    if _DEIXIS.search(text) and not fixture:
        meta["reason"] = "deixis_without_fixture"
        return text, meta, "low"

    if _DEIXIS.search(text) and fixture:
        meta["context_used"] = True
        meta["fixture"] = fixture
        # Still avoid gluing market tokens as third "team"
        if intent_hint in {"goals", "corners", "cards"}:
            meta["pass_through_followup"] = True
            focus = {"goals": "e gols", "corners": "e escanteios", "cards": "e cartoes"}[
                intent_hint
            ]
            return focus, meta, "high"
        return f"analisar {fixture}", meta, "high"

    # 4) Comparisons across last / prev fixtures
    if intent_hint == "compare" or _COMPARE.search(text):
        if not fixture and not prev_fx:
            meta["reason"] = "compare_without_fixture"
            return text, meta, "low"
        meta["context_used"] = True
        meta["fixture"] = fixture
        meta["prev_fixture"] = prev_fx
        # Two known fixtures → conversational compare (no invented stats)
        if fixture and prev_fx:
            meta["conversational_reply"] = _compare_reply(fixture, prev_fx, market)
            return text, meta, "high"
        # Only one fixture — honest limitation, still helpful
        if fixture:
            meta["conversational_reply"] = _compare_reply(fixture, None, market)
            return text, meta, "high"
        meta["reason"] = "compare_without_fixture"
        return text, meta, "low"

    # 5) Single-team chatty analyze — confirm, never invent opponent
    #    Skip if the "team" is actually a market term
    single = re.search(
        r"(?:o\s+que\s+acha\s+d[oe]|fala\s+d[oe]|analis[ae]\s+(?:o|a)?)"
        r"\s+([A-Za-z0-9][A-Za-z0-9.-]{1,40})(?:\s+hoje)?\s*$",
        text,
        re.I,
    )
    if single and not re.search(r"\bx\b|\bvs\b", text, re.I):
        team = single.group(1).strip()
        if team and len(team) >= 3 and not _is_market_token(team):
            meta["single_team"] = team
            return text, meta, "medium"

    return text, meta, None


# ── Confidence layer ───────────────────────────────────────────────────────

def confidence_layer(
    band_hint: ConfidenceBand | None,
    norm_meta: dict[str, Any],
    ctx_meta: dict[str, Any],
    intent_hint: str | None,
) -> tuple[ConfidenceBand, float]:
    if band_hint == "low":
        return "low", 0.25
    if band_hint == "medium":
        return "medium", 0.55
    if band_hint == "high":
        return "high", 0.9

    score = 0.45
    if norm_meta.get("typos") or norm_meta.get("nicknames"):
        score += 0.2
    if ctx_meta.get("context_used"):
        score += 0.35
    if intent_hint:
        score += 0.05
    score = min(score, 0.95)

    if score >= 0.8:
        return "high", score
    if score >= 0.5:
        return "medium", score
    return "low", score


def is_cancel_reset(message: str) -> bool:
    """User wants to drop pending / fixture context."""
    return bool(_CANCEL_RESET_RE.match(_fold(message or "")))


def is_topic_switch(message: str) -> bool:
    """Explicit new A x B — leave prior fixture / pending behind."""
    return bool(_TOPIC_SWITCH_RE.search(message or ""))


def clear_fixture_context(ctx: dict[str, Any]) -> None:
    """Cancel/reset: drop sticky fixture memory + CI pending (in-place)."""
    for key in (
        "last_home",
        "last_away",
        "last_match",
        "last_fixture",
        "last_analysis",
        "last_market",
        "last_recommendation",
        "last_final_recommendation",
        "last_intent",
        "last_is_live",
        "last_minute",
        "last_confidence",
        "last_entities",
        "last_live_at",
        "prev_home",
        "prev_away",
        "prev_match",
        "prev_fixture",
        "prev_market",
        "prev_recommendation",
        "ci_pending",
    ):
        ctx.pop(key, None)


def set_ci_pending(
    ctx: dict[str, Any],
    *,
    kind: str,
    team: str | None = None,
) -> None:
    from datetime import datetime, timezone

    ctx["ci_pending"] = {
        "kind": kind,
        "team": team,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def get_ci_pending(ctx: dict[str, Any] | None) -> dict[str, Any] | None:
    if not ctx:
        return None
    pending = ctx.get("ci_pending")
    return pending if isinstance(pending, dict) else None


def ci_pending_expired(ctx: dict[str, Any] | None, *, ttl: int = CI_PENDING_TTL_SECONDS) -> bool:
    pending = get_ci_pending(ctx)
    if not pending:
        return False
    created = pending.get("created_at")
    if not created or not isinstance(created, str):
        return True
    try:
        from datetime import datetime, timezone

        ts = datetime.strptime(created, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - ts).total_seconds()
        return age > ttl
    except Exception:
        return True


def expire_ci_pending_if_needed(ctx: dict[str, Any]) -> bool:
    """Clear expired pending. Returns True if cleared."""
    if get_ci_pending(ctx) and ci_pending_expired(ctx):
        ctx.pop("ci_pending", None)
        return True
    return False


def _clarification_for(
    band: ConfidenceBand,
    ctx_meta: dict[str, Any],
    ctx: dict[str, Any] | None,
    original: str,
) -> str | None:
    """
    Only clarify when there is an explicit sports reason.
    Never steal Small Talk with a generic “diga os times” on low band.
    """
    fixture = ctx_meta.get("fixture") or _fixture_label(ctx)
    reason = ctx_meta.get("reason") or ""

    if band == "medium" and ctx_meta.get("single_team"):
        team = str(ctx_meta["single_team"]).strip()
        pretty = team.title() if team.islower() else team
        return (
            f"Você está se referindo a uma análise do {pretty}? "
            f"Me diga o adversário (ex.: {pretty} x Time B) para eu analisar com segurança."
        )
    if band == "medium" and fixture and reason:
        return f"Você está se referindo ao {fixture}?"
    if band == "low":
        if "deixis" in reason:
            return (
                "Qual jogo você quer dizer? "
                "Me diga os times (ex.: Botafogo x Santos) para eu continuar."
            )
        # Market/prefer/compare without fixture — clarify only with explicit reason
        if reason in {
            "market_followup_without_fixture",
            "prefer_alt_without_fixture",
            "compare_without_fixture",
        }:
            return (
                "Não tenho um confronto recente nesta conversa. "
                "Analise um jogo primeiro (ex.: Analisar Botafogo x Santos) "
                "e depois pergunte sobre gols, escanteios ou alternativas."
            )
        # Generic low (e.g. "oi", noise) → do NOT intercept; let Small Talk / NL run
        return None
    return None


def _base_soft_payload(
    intent_name: str,
    prompt: str,
    brain: dict[str, Any] | None = None,
    *,
    entities: dict[str, Any] | None = None,
) -> dict:
    return {
        "intent": intent_name,
        "entities": entities
        or {"conversation_intelligence": True},
        "match": None,
        "status": None,
        "is_live": False,
        "minute": None,
        "best_markets": [],
        "confidence": {
            "score": 0.0,
            "label": "insufficient",
            "explanation": "Resposta conversacional — sem inventar contexto.",
            "data_sources": [],
        },
        "risk": {"level": "Unknown", "flags": [], "invalidation_conditions": []},
        "bankroll_recommendation": {
            "recommended_stake_pct": 0.0,
            "method": "quarter-Kelly",
            "examples": {},
            "no_bet": True,
            "reasoning": "",
        },
        "positive_factors": [],
        "negative_factors": [],
        "historical_references": [],
        "knowledge_notes": [],
        "executive_summary": prompt,
        "final_recommendation": prompt,
        "aurora_version": "Copilot v1.0",
        "brain": brain or {},
        "fixture_quality": None,
        "fixture_status": None,
        "match_card": None,
    }


def build_clarification_payload(prompt: str, brain: dict[str, Any] | None = None) -> dict:
    return _base_soft_payload(
        "clarification",
        prompt,
        brain,
        entities={"clarification": True, "conversation_intelligence": True},
    )


def build_conversational_payload(prompt: str, brain: dict[str, Any] | None = None) -> dict:
    return _base_soft_payload(
        "conversation_assist",
        prompt,
        brain,
        entities={"conversation_assist": True, "conversation_intelligence": True},
    )


def process_inbound_message(
    message: str,
    ctx: dict[str, Any] | None = None,
) -> MessageIntelResult:
    """
    Run the v3.7.1 inbound intelligence pipeline.
    Fail-open: on internal errors return original message.
    """
    original = (message or "").strip()
    try:
        normalized, norm_meta = normalize_layer(original)
        hint = intent_layer(normalized)
        enriched, ctx_meta, band_hint = context_layer(normalized, ctx, hint)
        band, score = confidence_layer(band_hint, norm_meta, ctx_meta, hint)

        clarify = None
        conversational = ctx_meta.get("conversational_reply")
        needs = False
        kind: ResponseKind | None = None
        pipeline_msg = original

        if conversational and band == "high":
            kind = "conversational"
            pipeline_msg = original  # short-circuit; do not rewrite into engines
        elif band == "high" and ctx_meta.get("pass_through_followup"):
            # Keep market-only phrase (e.g. "e escanteios") for FollowUp
            pipeline_msg = enriched or normalized or original
        elif band == "high" and enriched and enriched != _fold(original):
            # Only allow analyze rewrites that do NOT append bare market tokens
            # after a fixture (avoids "Botafogo x Santos Escanteios")
            if _MARKET_TERM_RE.search(enriched) and re.search(
                r"\bx\b.+\b(gols?|escanteios?|cart)", enriched, re.I
            ):
                # Unsafe shape — fall back to pass-through market or original
                pipeline_msg = original
            else:
                pipeline_msg = enriched
        elif band == "high" and (norm_meta.get("typos") or norm_meta.get("nicknames")):
            pipeline_msg = normalized
        elif band in {"medium", "low"}:
            clarify = _clarification_for(band, ctx_meta, ctx, original)
            needs = bool(clarify)
            kind = "clarify" if needs else None
            pipeline_msg = normalized if not needs else original

        # Safe pass-through for typo/slang only (never for market follow-ups)
        if (
            not needs
            and not conversational
            and not ctx_meta.get("pass_through_followup")
            and band != "low"
            and (norm_meta.get("typos") or norm_meta.get("nicknames") or "o que" in normalized)
            and not ctx_meta.get("context_used")
            and not ctx_meta.get("single_team")
        ):
            pipeline_msg = normalized
            if band == "medium" and score < 0.6:
                band, score = "high", max(score, 0.82)

        return MessageIntelResult(
            original=original,
            message_for_pipeline=pipeline_msg,
            confidence_band=band,
            confidence=score,
            intent_hint=hint,
            needs_clarification=needs,
            clarification_prompt=clarify,
            conversational_reply=conversational if kind == "conversational" else None,
            response_kind=kind,
            metadata={
                "norm": norm_meta,
                "ctx": ctx_meta,
                "v": "3.7.2",
                "pending_team": ctx_meta.get("single_team"),
            },
        )
    except Exception as exc:
        logger.warning("message_intelligence fail-open: %s", exc)
        return MessageIntelResult(
            original=original,
            message_for_pipeline=original,
            confidence_band="high",
            confidence=0.0,
            metadata={"error": str(exc), "fail_open": True},
        )
