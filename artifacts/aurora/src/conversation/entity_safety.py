"""
AURORA-PATCH-001 — Entity Safety Layer.

Defensive gates against entity corruption before sports reasoning.
Fail-open on unexpected errors. Does not invent match facts.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# R2 thresholds
CONF_HIGH = 0.85
CONF_MED = 0.55
CONF_LOW = 0.43
CONF_DROP = 0.35

# Portuguese / EN tokens that must NEVER fuzzy-map to clubs (R1).
# Exact slang aliases (bota, chape, galo, …) still resolve via exact typo map.
ENTITY_STOPWORDS: frozenset[str] = frozenset(
    {
        # FOUNDATION-002 collisions
        "chance",
        "chances",
        "mata",
        "gols",
        "gol",
        "goal",
        "goals",
        "tudo",
        "todo",
        "toda",
        "todos",
        "todas",
        "tipo",
        "tipos",
        "both",
        "bets",
        "bet",
        "bora",
        "just",
        "into",
        "minha",
        "meu",
        "more",
        "forte",
        "fortes",
        "melhor",
        "melhores",
        "pior",
        "piores",
        "entre",
        "contra",
        "versus",
        "ou",
        "quem",
        "tem",
        "mais",
        "menos",
        "amanha",
        "hoje",
        "agora",
        "depois",
        "antes",
        "quando",
        "onde",
        "como",
        "esta",
        "esse",
        "essa",
        "isso",
        "aquele",
        "aquela",
        "favorito",
        "favorita",
        "probabilidade",
        "probabilidades",
        "placar",
        "odds",
        "odd",
        "mercado",
        "mercados",
        "analise",
        "analisar",
        "partida",
        "partidas",
        "jogo",
        "jogos",
        "time",
        "times",
        "serie",
        "liga",
        "copa",
        "final",
        "fase",
        "grupo",
        "ida",
        "volta",
        "ranking",
        "tabela",
        "classificacao",
        "classificados",
        "over",
        "under",
        "home",
        "away",
        "live",
        "next",
        "last",
        "form",
        "score",
        "win",
        "lose",
        "draw",
        "teams",
        "city",  # bare English — compounds handled by aliases elsewhere
        "united",
        "central",
        "union",
        "river",
        "nacional",
        "america",
        "sport",  # bare EN; alias path still exact-maps "sport"→Sport Recife via TEAM_ALIASES
        "real",  # bare PT adj; exact TEAM_ALIASES still applies when resolver runs intentionally
        "athletic",
        "into",
        "from",
        "with",
        "that",
        "this",
        "have",
        "will",
        "would",
        "could",
        "should",
        "about",
        "after",
        "before",
        "very",
        "much",
        "many",
        "some",
        "any",
        "all",
        "also",
        "only",
        "just",
        "even",
        "still",
        "already",
        "again",
        "aqui",
        "ali",
        "la",
        "lá",
        "ai",
        "aí",
        "bem",
        "mal",
        "sim",
        "nao",
        "não",
        "pra",
        "pro",
        "por",
        "para",
        "com",
        "sem",
        "dos",
        "das",
        "nos",
        "nas",
        "uma",
        "uns",
        "umas",
        "ele",
        "ela",
        "eles",
        "elas",
        "voce",
        "você",
        "voces",
        "vocês",
        "quero",
        "ver",
        "acha",
        "achou",
        "pode",
        "podem",
        "sera",
        "será",
        "vai",
        "vao",
        "vão",
        "tá",
        "ta",
        "to",
        "tô",
        "ne",
        "né",
        "kk",
        "kkk",
        "aff",
        "ok",
        "okay",
    }
)

# Comparison / pair separators (R5)
_PAIR_SEP = re.compile(
    r"\s+(?:x|×|vs\.?|versus|contra|ou|entre)\s+",
    re.I,
)
_COMPARE_PHRASE = re.compile(
    r"(?:"
    r"mais\s+chance|"
    r"mais\s+forte|"
    r"quem\s+(?:e|é|tem)\s+mais|"
    r"quem\s+ganha|"
    r"quem\s+vence|"
    r"melhor\s+(?:time|equipe)?"
    r")",
    re.I,
)

# BR cues → prefer Mineiro for bare "atletico"
_BR_CUES = re.compile(
    r"\b(?:bahia|flamengo|palmeiras|corinthians|santos|botafogo|fluminense|"
    r"sao\s*paulo|vasco|gremio|internacional|cruzeiro|fortaleza|brasileir|"
    r"serie\s*a|brasileirao|mineiro|galo)\b",
    re.I,
)
_EU_CUES = re.compile(
    r"\b(?:madrid|laliga|la\s*liga|spain|espanha|champions|premier|"
    r"barcelona|atletico\s+madrid|atm)\b",
    re.I,
)


def fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


def is_entity_stopword(token: str) -> bool:
    t = fold(token)
    if not t:
        return True
    if t in ENTITY_STOPWORDS:
        return True
    # Also treat classic recovery common words as stopwords for fuzzy
    return False


@dataclass
class ScoredEntity:
    raw: str
    canon: str
    confidence: float
    source: str
    grounded: bool = False
    notes: list[str] = field(default_factory=list)


@dataclass
class SafetyVerdict:
    ok: bool
    teams: list[ScoredEntity] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)
    comparison: tuple[str, str] | None = None
    allow_ownership_lock: bool = False
    notes: list[str] = field(default_factory=list)

    def canons(self) -> list[str]:
        return [t.canon for t in self.teams if t.confidence >= CONF_DROP]

    def high_canons(self) -> list[str]:
        return [t.canon for t in self.teams if t.confidence >= CONF_HIGH]


def token_in_message(token: str, message: str) -> bool:
    """True if folded token appears as a whole word / substring of a word in message."""
    msg = fold(message)
    tok = fold(token)
    if not tok or not msg:
        return False
    if re.search(rf"(?<!\w){re.escape(tok)}(?!\w)", msg):
        return True
    # Multi-word canon: all significant parts present
    parts = [p for p in tok.split() if len(p) >= 3 and p not in ENTITY_STOPWORDS]
    if len(parts) >= 2:
        return all(p in msg for p in parts)
    return False


def canon_grounded_in_message(canon: str, message: str, raw: str | None = None) -> bool:
    """Entity is grounded if raw token or distinctive canon parts appear in user text."""
    if raw and token_in_message(raw, message):
        # Raw was a stopword that somehow mapped — not grounded as a club mention
        if is_entity_stopword(raw):
            return False
        return True
    c = fold(canon)
    msg = fold(message)
    if not c or not msg:
        return False
    # Distinctive tokens from canon (skip generic atletico/real alone without cue)
    parts = [p for p in re.findall(r"[a-z0-9]+", c) if len(p) >= 4]
    if not parts:
        return token_in_message(canon, message)
    # At least one distinctive part must appear OR full compact form
    if any(token_in_message(p, message) for p in parts):
        return True
    compact = re.sub(r"\s+", "", c)
    return compact in re.sub(r"\s+", "", msg)


def score_alias_hit(raw: str, canon: str, message: str, *, exact: bool) -> float:
    """R2 — confidence for a resolved entity."""
    raw_f = fold(raw)
    msg = fold(message)
    if is_entity_stopword(raw) and not exact:
        return 0.0
    if raw_f == "atletico" or raw_f == "atlético":
        if _BR_CUES.search(msg) and not _EU_CUES.search(msg):
            # Prefer Mineiro in BR context
            if "mineiro" in fold(canon) or "atletico mineiro" in fold(canon):
                return 0.91
            if "madrid" in fold(canon):
                return 0.43
        if _EU_CUES.search(msg) and not _BR_CUES.search(msg):
            if "madrid" in fold(canon):
                return 0.91
            if "mineiro" in fold(canon):
                return 0.43
        # Bare / ambiguous atletico
        if "mineiro" in fold(canon):
            return 0.55
        if "madrid" in fold(canon):
            return 0.43
        return CONF_LOW
    if exact:
        base = 0.95
    else:
        base = 0.72
    if not canon_grounded_in_message(canon, message, raw=raw):
        return min(base, CONF_LOW)
    return base


def extract_comparison_pair(message: str) -> tuple[str, str] | None:
    """R5 — extract A/B sides from comparison phrasing."""
    text = message or ""
    m = _PAIR_SEP.search(text)
    if m:
        left = text[: m.start()].strip()
        right = text[m.end() :].strip()
        # Take last 1–3 tokens on left, first 1–3 on right (avoid eating the whole sentence)
        left_toks = re.findall(r"[A-Za-zÀ-ÿ0-9]+", left)
        right_toks = re.findall(r"[A-Za-zÀ-ÿ0-9]+", right)
        if not left_toks or not right_toks:
            return None
        # Prefer last non-stopword token(s) on left
        def _side(toks: list[str], from_end: bool) -> str:
            seq = list(reversed(toks)) if from_end else list(toks)
            picked: list[str] = []
            for t in seq:
                if is_entity_stopword(t) and fold(t) not in {"atletico", "atlético"}:
                    if picked:
                        break
                    continue
                picked.append(t)
                if len(picked) >= 2:
                    break
            if from_end:
                picked.reverse()
            return " ".join(picked) if picked else toks[-1 if from_end else 0]

        l = _side(left_toks, from_end=True)
        r = _side(right_toks, from_end=False)
        if l and r and fold(l) != fold(r):
            return l, r
    return None


def looks_like_comparison(message: str) -> bool:
    if _PAIR_SEP.search(message or ""):
        return True
    return bool(_COMPARE_PHRASE.search(message or ""))


def filter_recovery_teams(
    message: str,
    teams: list[str],
    *,
    raw_notes: list[str] | None = None,
) -> SafetyVerdict:
    """
    Drop teams that came from stopword fuzzy or are ungrounded.
    Attaches confidence scores (R1 + R2).
    """
    notes_in = list(raw_notes or [])
    fuzzy_map: dict[str, str] = {}
    for n in notes_in:
        if n.startswith("fuzzy:") and "->" in n:
            try:
                _, rest = n.split(":", 1)
                src, dst = rest.split("->", 1)
                fuzzy_map[fold(dst)] = src.strip()
            except ValueError:
                pass

    scored: list[ScoredEntity] = []
    rejected: list[str] = []
    msg = message or ""

    for canon in teams:
        raw = fuzzy_map.get(fold(canon))
        from_fuzzy_stop = bool(raw and is_entity_stopword(raw))
        if from_fuzzy_stop:
            rejected.append(f"{raw}->{canon}")
            continue

        # Prefer a grounded raw token from the user message
        if raw is None:
            for tok in re.findall(r"[A-Za-zÀ-ÿ0-9]+", msg):
                tf = fold(tok)
                if is_entity_stopword(tok) and tf not in {"atletico", "atlético"}:
                    continue
                if tf in fold(canon) or fold(canon).startswith(tf[: min(4, len(tf))]):
                    raw = tok
                    break

        exact = fold(canon) not in fuzzy_map  # not produced by fuzzy note
        conf = score_alias_hit(raw or canon, canon, msg, exact=bool(raw) and exact)
        grounded = canon_grounded_in_message(canon, msg, raw=raw)
        if conf < CONF_DROP or not grounded:
            rejected.append(canon)
            continue
        scored.append(
            ScoredEntity(
                raw=raw or canon,
                canon=canon,
                confidence=conf,
                source="recovery",
                grounded=grounded,
            )
        )

    # Comparison sides boost: ensure both sides considered
    pair = extract_comparison_pair(msg)
    cmp_tuple: tuple[str, str] | None = None
    if pair:
        cmp_tuple = pair
        for side in pair:
            if is_entity_stopword(side):
                continue
            # side may still need resolution upstream; record as grounded raw
            if not any(fold(side) in fold(s.raw) or fold(side) in fold(s.canon) for s in scored):
                scored.append(
                    ScoredEntity(
                        raw=side,
                        canon=side[:1].upper() + side[1:] if side else side,
                        confidence=0.80,
                        source="comparison_operator",
                        grounded=True,
                        notes=["comparison_side"],
                    )
                )

    high = [s for s in scored if s.confidence >= CONF_MED]
    allow_lock = bool(high) and all(s.grounded for s in high)
    # Never lock ownership on ungrounded-only sets
    if rejected and not high:
        allow_lock = False

    return SafetyVerdict(
        ok=True,
        teams=scored,
        rejected=rejected,
        comparison=cmp_tuple,
        allow_ownership_lock=allow_lock,
        notes=[f"rejected={rejected}"] if rejected else [],
    )


def ownership_lock_permitted(message: str, ctx: dict[str, Any] | None) -> bool:
    """
    R3 — do not allow NEW ownership lock when the current message looks like a
    fresh multi-team / comparison query whose entities are not yet validated,
    or when ctx carries ungrounded focus teams.
    Short continuity follow-ups still permitted.
    """
    try:
        ctx = ctx if isinstance(ctx, dict) else {}
        msg = message or ""
        # Short FU → allow lock preserve
        if len(msg.split()) <= 4 and not looks_like_comparison(msg):
            return True
        if looks_like_comparison(msg) or _COMPARE_PHRASE.search(msg):
            # R3 — never take a NEW ownership lock on fresh A/B comparisons
            return False
        focus = fold(str(ctx.get("conversation_focus_team") or ctx.get("last_team") or ""))
        if focus and not canon_grounded_in_message(focus, msg):
            # Message introduces new content not matching sticky focus
            if len(msg.split()) >= 5:
                return False
        return True
    except Exception as exc:
        logger.debug("ownership_lock_permitted fail-open: %s", exc)
        return True


def central_entities_from_payload(payload: dict[str, Any] | None) -> list[str]:
    if not isinstance(payload, dict):
        return []
    ents = payload.get("entities") if isinstance(payload.get("entities"), dict) else {}
    out: list[str] = []
    for key in (
        "team",
        "resolved_team",
        "followup_resolved_team",
        "home",
        "away",
    ):
        v = ents.get(key)
        if isinstance(v, str) and v.strip():
            out.append(v.strip())
    srf = ents.get("srf") if isinstance(ents.get("srf"), dict) else {}
    ft = srf.get("focus_team")
    if isinstance(ft, str) and ft.strip():
        out.append(ft.strip())
    match = payload.get("match") if isinstance(payload.get("match"), dict) else {}
    for key in ("home", "away", "home_team", "away_team"):
        v = match.get(key)
        if isinstance(v, str) and v.strip():
            out.append(v.strip())
    # dedupe
    seen: set[str] = set()
    uniq: list[str] = []
    for e in out:
        k = fold(e)
        if k not in seen:
            seen.add(k)
            uniq.append(e)
    return uniq


def judge_entity_overlap(
    user_message: str,
    payload: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    R4 — Entity extracted ∩ entity present in user input.
    Returns overlap stats for judge_rubric.
    """
    entities = central_entities_from_payload(payload)
    if not entities:
        return {
            "has_central_entity": False,
            "overlap_ok": True,
            "missing": [],
            "entities": [],
        }
    missing = [
        e
        for e in entities
        if not canon_grounded_in_message(e, user_message or "")
    ]
    return {
        "has_central_entity": True,
        "overlap_ok": len(missing) == 0,
        "missing": missing,
        "entities": entities,
    }
