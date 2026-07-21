"""
AURORA-PATCH-002A — Sports Language Layer (SLL).

Runs BEFORE Aurora routing. Additive. Feature-flagged.
Fail-open. Does not invent match stats/odds.
Does not touch FROZEN ownership/continuity/engines.
"""

from __future__ import annotations

import logging
import os
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Mandatory feature flag (default ON for local/eval; set 0 to rollback)
_FLAG_ENV = "ENABLE_SPORTS_LANGUAGE_LAYER"

# Below this → DO NOTHING (never force normalization)
MIN_APPLY_CONFIDENCE = 0.72

SPORTS_NICKNAMES: dict[str, str] = {
    # BR slang / short
    "mengao": "Flamengo",
    "mengo": "Flamengo",
    "fla": "Flamengo",
    "verdao": "Palmeiras",
    "timao": "Corinthians",
    "coringao": "Corinthians",
    "fogao": "Botafogo",
    "bota": "Botafogo",
    "flu": "Fluminense",
    "tricolor": "Sao Paulo",
    "galo": "Atletico Mineiro",
    "raposa": "Cruzeiro",
    "chape": "Chapecoense",
    "mira": "Mirassol",
    "inter": "Internacional",
    "colorado": "Internacional",
    "juve": "Juventus",
    # EU short
    "barca": "Barcelona",
    "real": "Real Madrid",
    "city": "Manchester City",
    "united": "Manchester United",
    "manutd": "Manchester United",
    "mancity": "Manchester City",
    "gunners": "Arsenal",
    "reds": "Liverpool",
    "chelsea": "Chelsea",
    "tottenham": "Tottenham",
    "spurs": "Tottenham",
    "bayern": "Bayern Munich",
    "dortmund": "Borussia Dortmund",
    "bvb": "Borussia Dortmund",
    "psg": "PSG",
    "milan": "AC Milan",
    "acmilan": "AC Milan",
    "intermilan": "Inter Milan",
    "atm": "Atletico Madrid",
}

# High-confidence nicknames (rarely collide with ordinary PT/EN)
_HIGH_CONF_NICKS = frozenset(
    {
        "mengao",
        "mengo",
        "verdao",
        "timao",
        "coringao",
        "fogao",
        "galo",
        "raposa",
        "chape",
        "flu",
        "fla",
        "bota",
        "mira",
        "barca",
        "juve",
        "bvb",
        "psg",
        "gunners",
        "spurs",
        "manutd",
        "mancity",
        "colorado",
    }
)

_COMPARE_SEP = re.compile(
    r"\s+(?:ou|x|×|vs\.?|versus|contra|entre)\s+",
    re.I,
)
_COMPARE_PHRASE = re.compile(
    r"(?:"
    r"mais\s+chance|"
    r"mais\s+forte|"
    r"quem\s+(?:e|é|tem)\s+mais|"
    r"quem\s+ganha|"
    r"quem\s+vence|"
    r"quem\s+leva|"
    r"melhor\s+(?:time|equipe)?|"
    r"melhor\s+fase|"
    r"em\s+melhor\s+fase|"
    r"quem\s+est[aá]\s+em\s+melhor"
    r")",
    re.I,
)
_EU_INTER_CUES = re.compile(
    r"\b(?:milan|juve|juventus|serie\s*a|italia|italy|nerazzurri|san\s*siro)\b",
    re.I,
)
_BR_INTER_CUES = re.compile(
    r"\b(?:gremio|grêmio|bahia|flamengo|brasileir|porto\s*alegre|colorado)\b",
    re.I,
)
_SPORT_LEX = re.compile(
    r"\b(?:"
    r"jogo|joga|partida|time|times|chance|favorito|aposta|fase|forma|"
    r"placar|gol|gols|brasileir|libertadores|champions|classico|clássico"
    r")\b",
    re.I,
)


def sll_enabled() -> bool:
    raw = (os.environ.get(_FLAG_ENV) or "1").strip().lower()
    return raw not in {"0", "false", "off", "no"}


def fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


@dataclass
class SLLResult:
    raw_text: str
    normalized_text: str
    resolved_aliases: list[str] = field(default_factory=list)
    clubs: list[str] = field(default_factory=list)
    ask_kind: str | None = None
    is_compare: bool = False
    confidence: float = 0.0
    applied: bool = False
    skipped_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_text": self.raw_text,
            "normalized_text": self.normalized_text,
            "resolved_aliases": list(self.resolved_aliases),
            "clubs": list(self.clubs),
            "ask_kind": self.ask_kind,
            "is_compare": self.is_compare,
            "confidence": self.confidence,
            "applied": self.applied,
            "skipped_reason": self.skipped_reason,
        }


def resolve_nickname(token: str, message: str | None = None) -> str | None:
    """Resolve a single token to a club canon (shared helper)."""
    t = fold(token)
    if not t:
        return None
    msg = fold(message or "")

    if t in {"inter", "internacional"}:
        if _EU_INTER_CUES.search(msg) and not _BR_INTER_CUES.search(msg):
            return "Inter Milan"
        if t == "internacional":
            return "Internacional"
        if _BR_INTER_CUES.search(msg) or not _EU_INTER_CUES.search(msg):
            return "Internacional"
        return "Inter Milan"

    if t == "atm":
        if re.search(r"\b(?:bahia|brasileir|galo|mineiro)\b", msg):
            return "Atletico Mineiro"
        return "Atletico Madrid"

    if t == "real":
        # Only in compare / sport context
        if not (
            _COMPARE_SEP.search(msg)
            or re.search(r"\b(?:barca|barcelona|madrid)\b", msg)
            or _SPORT_LEX.search(msg)
        ):
            return None

    if t in {"city", "united"}:
        # Only when compare/sport signal present (avoid English prose)
        if not (_COMPARE_SEP.search(msg) or _COMPARE_PHRASE.search(msg) or _SPORT_LEX.search(msg)):
            return None

    return SPORTS_NICKNAMES.get(t)


def _detect_ask_kind(message: str, is_compare: bool) -> str | None:
    msg = fold(message)
    if is_compare or _COMPARE_PHRASE.search(message or ""):
        if re.search(r"\bfase|forma|momento\b", msg):
            return "form_compare" if is_compare else "form"
        if re.search(r"\bchance|favorito|ganha|vence|melhor\b", msg):
            return "compare"
        return "compare" if is_compare else None
    if re.search(r"\bjoga|jogo\s+hoje|amanha|calendario|agenda\b", msg):
        return "calendar"
    if re.search(r"\bfase|forma|momento|ta\s+bem|tá\s+bem\b", msg):
        return "form"
    if re.search(r"\baposta|vale\s+a\s+pena|odds?\b", msg):
        return "bet"
    return None


def _score_confidence(
    *,
    aliases: list[str],
    clubs: list[str],
    is_compare: bool,
    ask_kind: str | None,
    raw_tokens_folded: list[str],
) -> float:
    if not aliases and not (is_compare and len(clubs) >= 2):
        return 0.0
    conf = 0.55
    high_hits = sum(1 for t in raw_tokens_folded if t in _HIGH_CONF_NICKS)
    if high_hits:
        conf = 0.90
    if is_compare and len(clubs) >= 2:
        conf = max(conf, 0.88)
    if ask_kind in {"compare", "form_compare", "calendar", "form"}:
        conf = max(conf, 0.80) if aliases else conf
    # Single low-trust alias alone (e.g. only "real" without pair) → suppress
    if len(aliases) == 1 and not is_compare:
        only = fold(aliases[0].split("→")[0]) if "→" in aliases[0] else ""
        if only in {"real", "city", "united", "inter", "tricolor", "atm"}:
            return 0.40
    return min(conf, 0.95)


def _token_already_inside_canon(message: str, tok: str, canon: str) -> bool:
    """True when tok is a word of multi-word canon already present in message."""
    if " " not in (canon or ""):
        return False
    parts = [fold(p) for p in canon.split()]
    if fold(tok) not in parts:
        return False
    return bool(re.search(rf"(?<!\w){re.escape(canon)}(?!\w)", message or "", re.I))


def apply_sports_language_layer(
    message: str,
    ctx: dict[str, Any] | None = None,
) -> SLLResult:
    """
    Pre-router SLL entrypoint.
    Low confidence → applied=False, normalized_text == raw_text.
    """
    raw = message or ""
    result = SLLResult(raw_text=raw, normalized_text=raw)

    if not sll_enabled():
        result.skipped_reason = "flag_disabled"
        _stamp(ctx, result)
        _log(result)
        return result

    try:
        is_compare = bool(_COMPARE_SEP.search(raw))
        ask_kind = _detect_ask_kind(raw, is_compare)
        result.is_compare = is_compare
        result.ask_kind = ask_kind

        tokens = re.findall(r"[A-Za-zÀ-ÿ0-9]+", raw)
        aliases: list[str] = []
        clubs: list[str] = []
        out = raw
        seen: set[str] = set()

        for tok in tokens:
            tf = fold(tok)
            if tf in seen:
                continue
            seen.add(tf)
            # Compact routing tokens: keep text, record canon only
            if tf in _COMPACT_TO_CANON:
                canon_c = _COMPACT_TO_CANON[tf]
                if canon_c not in clubs:
                    clubs.append(canon_c)
                continue
            # Display compact (ManCity) → same
            tf_disp = fold(tok.replace("_", ""))
            if tf_disp in _COMPACT_TO_CANON and tok[0:1].isupper():
                canon_c = _COMPACT_TO_CANON[tf_disp]
                if canon_c not in clubs:
                    clubs.append(canon_c)
                continue
            canon = resolve_nickname(tok, raw)
            if not canon:
                continue
            # Skip if token already is the canon (or substring of multiword)
            if tf == fold(canon):
                if canon not in clubs:
                    clubs.append(canon)
                continue
            # Prevent double-expand: "City" inside already-canonical
            # "Manchester City" must not become "Manchester Manchester City"
            if _token_already_inside_canon(out, tok, canon):
                if canon not in clubs:
                    clubs.append(canon)
                continue
            new_out = re.sub(
                rf"(?<!\w){re.escape(tok)}(?!\w)",
                canon,
                out,
                count=1,
                flags=re.I,
            )
            if new_out != out:
                aliases.append(f"{tok}→{canon}")
                out = new_out
            if canon not in clubs:
                clubs.append(canon)

        # Also capture already-canonical club tokens appearing as sides
        # (handled above when tf == fold(canon) for nicknames that equal canon — rare)

        conf = _score_confidence(
            aliases=aliases,
            clubs=clubs,
            is_compare=is_compare,
            ask_kind=ask_kind,
            raw_tokens_folded=[fold(t) for t in tokens],
        )
        result.resolved_aliases = aliases
        result.clubs = clubs
        result.confidence = conf

        if conf < MIN_APPLY_CONFIDENCE:
            result.skipped_reason = "low_confidence"
            result.applied = False
            result.normalized_text = raw
            _stamp(ctx, result)
            _log(result)
            return result

        if not aliases and out == raw:
            # Nothing to rewrite — still stamp compare metadata if useful
            result.skipped_reason = "no_alias_rewrite"
            result.applied = False
            result.normalized_text = raw
            _stamp(ctx, result)
            _log(result)
            return result

        result.normalized_text = out
        result.applied = True
        result.skipped_reason = None

        # Compare with 2 clubs → routing-friendly rewrite (before MasterIntent)
        if is_compare and len(clubs) >= 2:
            rw = rewrite_compare_for_routing(out, clubs)
            if rw:
                result.normalized_text = rw

        _stamp(ctx, result)
        _log(result)
        return result
    except Exception as exc:
        logger.warning("[SLL] fail-open: %s", exc)
        result.skipped_reason = f"error:{exc}"
        result.applied = False
        _stamp(ctx, result)
        return result


def _stamp(ctx: dict[str, Any] | None, result: SLLResult) -> None:
    if not isinstance(ctx, dict):
        return
    try:
        ctx["sll"] = result.to_dict()
        ctx["raw_user_message"] = result.raw_text
        if result.applied:
            ctx["sll_normalized_message"] = result.normalized_text
    except Exception:
        pass


def _log(result: SLLResult) -> None:
    try:
        logger.warning(
            "[SLL] raw=%r normalized=%r aliases=%s clubs=%s "
            "compare=%s ask_kind=%s conf=%.2f applied=%s skip=%s",
            result.raw_text[:80],
            result.normalized_text[:80],
            result.resolved_aliases,
            result.clubs,
            result.is_compare,
            result.ask_kind,
            result.confidence,
            result.applied,
            result.skipped_reason,
        )
    except Exception:
        pass


# ── Back-compat helpers used by context_recovery (additive) ─────────────


def expand_sports_language(message: str) -> tuple[str, list[str]]:
    """Legacy helper — prefers full layer when flag on."""
    r = apply_sports_language_layer(message, None)
    if r.applied:
        # Notes must use ASCII "->" so context_recovery can parse canons
        notes: list[str] = []
        for a in r.resolved_aliases:
            if "→" in a:
                src, dst = a.split("→", 1)
                notes.append(f"nick:{src.strip()}->{dst.strip()}")
            elif "->" in a:
                src, dst = a.split("->", 1)
                notes.append(f"nick:{src.strip()}->{dst.strip()}")
            else:
                notes.append(f"nick:{a}")
        return r.normalized_text, notes
    # Fall back to raw expand without confidence gate for recovery internals
    notes: list[str] = []
    out = message or ""
    for tok in re.findall(r"[A-Za-zÀ-ÿ0-9]+", message or ""):
        canon = resolve_nickname(tok, message)
        if not canon or fold(tok) == fold(canon):
            continue
        if fold(tok) not in SPORTS_NICKNAMES and fold(tok) not in {
            "inter",
            "internacional",
            "atm",
        }:
            continue
        new_out = re.sub(
            rf"(?<!\w){re.escape(tok)}(?!\w)",
            canon,
            out,
            count=1,
            flags=re.I,
        )
        if new_out != out:
            notes.append(f"nick:{tok}->{canon}")
            out = new_out
    return out, notes


# Compact single-token routing forms (survive HI _PAIR / space splitters).
# Keep text as these tokens; map to canons for metadata only.
_COMPACT_TO_CANON: dict[str, str] = {
    "mancity": "Manchester City",
    "manutd": "Manchester United",
    "realmadrid": "Real Madrid",
    "atleticomineiro": "Atletico Mineiro",
    "atleticomadrid": "Atletico Madrid",
    "acmilan": "AC Milan",
    "intermilan": "Inter Milan",
    "saopaulo": "Sao Paulo",
    "bayernmunich": "Bayern Munich",
    "borussiadortmund": "Borussia Dortmund",
}
_CANON_TO_COMPACT: dict[str, str] = {fold(v): k for k, v in _COMPACT_TO_CANON.items()}
# Prefer readable PascalCase in rewrites
_COMPACT_DISPLAY: dict[str, str] = {
    "mancity": "ManCity",
    "manutd": "ManUtd",
    "realmadrid": "RealMadrid",
    "atleticomineiro": "AtleticoMineiro",
    "atleticomadrid": "AtleticoMadrid",
    "acmilan": "ACMilan",
    "intermilan": "InterMilan",
    "saopaulo": "SaoPaulo",
    "bayernmunich": "BayernMunich",
    "borussiadortmund": "Dortmund",
}


def routing_token(canon: str) -> str:
    """Single-token label for compare rewrites (HI-safe)."""
    key = fold(canon)
    compact = _CANON_TO_COMPACT.get(key)
    if compact:
        return _COMPACT_DISPLAY.get(compact, compact)
    # Already single token
    if " " not in (canon or ""):
        return canon
    # Fallback: strip spaces
    return re.sub(r"\s+", "", canon)


def rewrite_compare_for_routing(message: str, teams: list[str]) -> str | None:
    if len(teams) < 2:
        return None
    msg = message or ""
    if not re.search(r"\b(?:ou|vs\.?|versus|contra|entre|x)\b", msg, re.I):
        if not re.search(
            r"mais\s+chance|quem\s+ganha|quem\s+(?:e|é)\s+mais|mais\s+forte",
            msg,
            re.I,
        ):
            return None
    a, b = teams[0], teams[1]
    if fold(a) == fold(b):
        return None
    return f"analisar {routing_token(a)} x {routing_token(b)}"


def apply_sports_language_to_ctx(
    message: str,
    ctx: dict[str, Any] | None,
    *,
    teams: list[str] | None = None,
) -> dict[str, Any]:
    if not isinstance(ctx, dict):
        return {}
    try:
        bucket = ctx.setdefault("sports_language", {})
        if not isinstance(bucket, dict):
            return {}
        bucket["last_message"] = (message or "")[:120]
        if teams:
            bucket["teams"] = list(teams)[:6]
        return bucket
    except Exception:
        return {}
