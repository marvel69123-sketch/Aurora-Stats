"""
Aurora v3.7 — Conversation Intelligence Foundation (additive).

Pipeline (inbound only):
  Message → Normalization → Conversation Context → Intent → Confidence

Sacred rules:
  - NEVER invent fixtures / opponents / live stats.
  - On doubt → clarify (medium/low). High confidence → rewrite for downstream.
  - Does NOT edit Resolver, FollowUp engine, Integrity, engines, or payloads schema.
  - Frozen modules remain untouched; this only rewrites the inbound string or
    returns a clarification payload.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Literal

logger = logging.getLogger(__name__)

ConfidenceBand = Literal["high", "medium", "low"]


@dataclass
class MessageIntelResult:
    original: str
    message_for_pipeline: str
    confidence_band: ConfidenceBand
    confidence: float
    intent_hint: str | None = None
    needs_clarification: bool = False
    clarification_prompt: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


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
]

# Common misspellings → alias keys (never invent fixtures)
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
    # isolated "q" → "que" (avoid eating "x")
    out = re.sub(r"(?<!\w)q(?!\w)", "que", out, flags=re.I)
    return out


def _apply_typos(text: str) -> tuple[str, list[str]]:
    folded = _fold(text)
    applied: list[str] = []
    for wrong, right in sorted(_TYPOS.items(), key=lambda kv: -len(kv[0])):
        if wrong in folded:
            # replace in original-ish folded space then rebuild
            folded = re.sub(rf"\b{re.escape(wrong)}\b", right, folded)
            applied.append(f"{wrong}->{right}")
    return folded, applied


def _expand_nicknames(folded: str) -> tuple[str, list[str]]:
    """Expand nicknames using TEAM_ALIASES (read-only) + local extras."""
    applied: list[str] = []
    try:
        from src.core.team_aliases import TEAM_ALIASES
    except Exception:
        TEAM_ALIASES = {}

    # Prefer longer keys first
    keys = sorted(
        set(list(_NICK_EXTRA.keys()) + list(TEAM_ALIASES.keys())),
        key=len,
        reverse=True,
    )
    out = f" {folded} "
    for key in keys:
        if len(key) < 3 and key not in _NICK_EXTRA:
            continue
        # skip generic words
        if key in {"fc", "sc", "cf", "afc", "the", "de", "do", "da"}:
            continue
        canon = _NICK_EXTRA.get(key) or TEAM_ALIASES.get(key)
        if not canon:
            continue
        pat = re.compile(rf"(?<!\w){re.escape(key)}(?!\w)", re.I)
        if pat.search(out):
            out = pat.sub(str(canon), out)
            applied.append(f"{key}->{canon}")
    return re.sub(r"\s+", " ", out).strip(), applied


def normalize_layer(message: str) -> tuple[str, dict[str, Any]]:
    raw = (message or "").strip()
    step = _apply_slang(raw)
    folded, typos = _apply_typos(step)
    expanded, nicks = _expand_nicknames(folded)
    meta = {"slang": True, "typos": typos, "nicknames": nicks, "normalized": expanded}
    return expanded, meta


# ── Intent layer ───────────────────────────────────────────────────────────

_INTENT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(gols?|over|under|btts|ambos\s+marcam)\b", re.I), "goals"),
    (re.compile(r"\b(escanteios?|corners?|cantos?)\b", re.I), "corners"),
    (re.compile(r"\b(cart[oõ]es?|cards?)\b", re.I), "cards"),
    (re.compile(
        r"\b(mais\s+conservador|mais\s+seguro|menor\s+risco|seguro)\b", re.I
    ), "safer"),
    (re.compile(
        r"\b(esse\s+ta\s+melhor|esse\s+parece\s+melhor|qual\s+dos\s+dois|"
        r"comparado\s+ao|o\s+anterior|nao\s+gostei)\b",
        re.I,
    ), "compare"),
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
_FOLLOW_MARKET = re.compile(
    r"^(?:e\s+)?(?:pra\s+|para\s+)?(gols?|escanteios?|corners?|cart[oõ]es?|"
    r"btts|ambos(?:\s+marcam)?|over|under)\b",
    re.I,
)
_COMPARE = re.compile(
    r"\b(mais\s+conservador|mais\s+seguro|esse\s+ta\s+melhor|"
    r"esse\s+parece\s+melhor|o\s+anterior|comparado\s+ao|"
    r"qual\s+dos\s+dois|nao\s+gostei\s+desse\s+mercado)\b",
    re.I,
)


def _fixture_label(ctx: dict[str, Any] | None) -> str | None:
    if not ctx:
        return None
    home = (ctx.get("last_home") or "").strip()
    away = (ctx.get("last_away") or "").strip()
    if home and away:
        return f"{home} x {away}"
    match = (ctx.get("last_match") or ctx.get("last_fixture") or "").strip()
    return match or None


def context_layer(
    normalized: str,
    ctx: dict[str, Any] | None,
    intent_hint: str | None,
) -> tuple[str, dict[str, Any], ConfidenceBand | None]:
    """
    Enrich with short conversation memory. Never invents home/away.
    Returns (enriched_text, meta, forced_band_or_None).
    """
    meta: dict[str, Any] = {"context_used": False}
    fixture = _fixture_label(ctx)
    text = normalized

    # Deixis without context → must clarify (do not invent)
    if _DEIXIS.search(text) and not fixture:
        meta["reason"] = "deixis_without_fixture"
        return text, meta, "low"

    if _DEIXIS.search(text) and fixture:
        meta["context_used"] = True
        meta["fixture"] = fixture
        if intent_hint in {"goals", "corners", "cards"}:
            focus = {
                "goals": "gols",
                "corners": "escanteios",
                "cards": "cartoes",
            }[intent_hint]
            return f"analisar {fixture} foco em {focus}", meta, "high"
        return f"analisar {fixture}", meta, "high"

    # Market follow-up: "e pra gols?" / "e escanteios?"
    m = _FOLLOW_MARKET.search(text.strip())
    if m and fixture:
        focus = m.group(1).lower()
        meta["context_used"] = True
        meta["fixture"] = fixture
        meta["market_focus"] = focus
        return f"analisar {fixture} — {focus}", meta, "high"

    if m and not fixture:
        meta["reason"] = "market_followup_without_fixture"
        return text, meta, "low"

    # Comparative / preference follow-ups
    if _COMPARE.search(text) and fixture:
        meta["context_used"] = True
        meta["fixture"] = fixture
        if intent_hint == "safer" or re.search(r"conservador|seguro", text, re.I):
            return (
                f"sobre {fixture}: algo mais conservador / menor risco",
                meta,
                "high",
            )
        if re.search(r"nao\s+gostei", text, re.I):
            return (
                f"sobre {fixture}: nao gostei desse mercado, alternativas",
                meta,
                "high",
            )
        return (
            f"sobre {fixture}: comparar com o anterior / qual e mais seguro",
            meta,
            "high",
        )

    if _COMPARE.search(text) and not fixture:
        meta["reason"] = "compare_without_fixture"
        return text, meta, "low"

    # Single-team chatty analyze: "o que acha do Santos hoje" / "fala do Flamengo"
    single = re.search(
        r"(?:o\s+que\s+acha\s+d[oe]|fala\s+d[oe]|analis[ae]\s+(?:o|a)?)"
        r"\s+([A-Za-z0-9][A-Za-z0-9.-]{1,40})(?:\s+hoje)?\s*$",
        text,
        re.I,
    )
    if single and not re.search(r"\bx\b|\bvs\b", text, re.I):
        team = single.group(1).strip()
        if team and len(team) >= 3:
            meta["single_team"] = team
            # Medium: confirm — never invent opponent
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


def _clarification_for(
    band: ConfidenceBand,
    ctx_meta: dict[str, Any],
    ctx: dict[str, Any] | None,
    original: str,
) -> str | None:
    fixture = ctx_meta.get("fixture") or _fixture_label(ctx)
    if band == "medium" and ctx_meta.get("single_team"):
        team = str(ctx_meta["single_team"]).strip()
        pretty = team.title() if team.islower() else team
        return (
            f"Você está se referindo a uma análise do {pretty}? "
            f"Me diga o adversário (ex.: {pretty} x Time B) para eu analisar com segurança."
        )
    if band == "medium" and fixture:
        return f"Você está se referindo ao {fixture}?"
    if band == "low":
        if "deixis" in (ctx_meta.get("reason") or ""):
            return (
                "Qual jogo você quer dizer? "
                "Me diga os times (ex.: Botafogo x Santos) para eu continuar."
            )
        if "without_fixture" in (ctx_meta.get("reason") or ""):
            return (
                "Não tenho um confronto recente nesta conversa. "
                "Analise um jogo primeiro (ex.: Analisar Botafogo x Santos) "
                "e depois pergunte sobre gols ou escanteios."
            )
        return (
            "Não entendi com segurança. "
            "Pode reformular com os times do jogo?"
        )
    return None


def build_clarification_payload(prompt: str, brain: dict[str, Any] | None = None) -> dict:
    """CopilotResponse-compatible clarification — never invents markets/fixtures."""
    return {
        "intent": "clarification",
        "entities": {"clarification": True, "conversation_intelligence": True},
        "match": None,
        "status": None,
        "is_live": False,
        "minute": None,
        "best_markets": [],
        "confidence": {
            "score": 0.0,
            "label": "insufficient",
            "explanation": "Pedido de esclarecimento — sem inventar contexto.",
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


def process_inbound_message(
    message: str,
    ctx: dict[str, Any] | None = None,
) -> MessageIntelResult:
    """
    Run the v3.7 inbound intelligence pipeline.
    Fail-open: on internal errors return original message, high-pass unused.
    """
    original = (message or "").strip()
    try:
        normalized, norm_meta = normalize_layer(original)
        hint = intent_layer(normalized)
        enriched, ctx_meta, band_hint = context_layer(normalized, ctx, hint)
        band, score = confidence_layer(band_hint, norm_meta, ctx_meta, hint)

        clarify = None
        needs = False
        pipeline_msg = original

        if band == "high" and enriched and enriched != _fold(original):
            # Use enriched human-readable form (already folded expansions)
            pipeline_msg = enriched
        elif band == "high" and (norm_meta.get("typos") or norm_meta.get("nicknames")):
            pipeline_msg = normalized
        elif band in {"medium", "low"}:
            clarify = _clarification_for(band, ctx_meta, ctx, original)
            needs = bool(clarify)
            # medium single-team: still pass normalized typos to pipeline if user
            # continues — but when clarifying we short-circuit in the router.
            pipeline_msg = normalized if not needs else original

        # Safe pass-through: if we only fixed slang/typos with no ambiguity
        if (
            not needs
            and band != "low"
            and (norm_meta.get("typos") or norm_meta.get("nicknames") or "o que" in normalized)
            and not ctx_meta.get("context_used")
        ):
            # Chatty single-team already handled as medium; other rewrites OK
            if not ctx_meta.get("single_team"):
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
            metadata={
                "norm": norm_meta,
                "ctx": ctx_meta,
                "v": "3.7",
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
