"""
Aurora Brain Upgrade — Context Recovery Engine.

Users type messy / incomplete / typo-heavy messages.
Recover intent + entities BEFORE asking for clarification.

Fail-open. Additive. Does NOT edit State / Reasoner / CIL / CRL / Resolver.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Common typos / slang → canonical team (folded keys)
_TYPO_TEAMS: dict[str, str] = {
    "santus": "Santos",
    "sanots": "Santos",
    "snts": "Santos",
    "santoss": "Santos",
    "corinthas": "Corinthians",
    "corintians": "Corinthians",
    "corinthian": "Corinthians",
    "timo": "Corinthians",
    "botafg": "Botafogo",
    "bota": "Botafogo",
    "botafogo": "Botafogo",
    "fogao": "Botafogo",
    "fla": "Flamengo",
    "flamengo": "Flamengo",
    "mengao": "Flamengo",
    "bahia": "Bahia",
    "palmeiras": "Palmeiras",
    "verdao": "Palmeiras",
    "sao paulo": "Sao Paulo",
    "saopaulo": "Sao Paulo",
    "tricolor": "Sao Paulo",
    "vasco": "Vasco",
    "fluminense": "Fluminense",
    "flu": "Fluminense",
    "gremio": "Gremio",
    "grêmio": "Gremio",
    "inter": "Internacional",
    "internacional": "Internacional",
    "cruzeiro": "Cruzeiro",
    "atletico": "Atletico Mineiro",
    "galo": "Atletico Mineiro",
    "fortaleza": "Fortaleza",
    "vitoria": "Vitoria",
    "chape": "Chapecoense",
    "chapecoense": "Chapecoense",
    "mirassol": "Mirassol",
    "mira": "Mirassol",
    "juventus": "Juventus",
    "juve": "Juventus",
}

_SLANG: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bhj\b", re.I), "hoje"),
    (re.compile(r"\bagr\b", re.I), "agora"),
    (re.compile(r"\boq\b", re.I), "o que"),
    (re.compile(r"\bvc\b", re.I), "voce"),
    (re.compile(r"\btbm\b", re.I), "tambem"),
    (re.compile(r"\bpq\b", re.I), "porque"),
    (re.compile(r"\btb\b", re.I), "tambem"),
    (re.compile(r"\bqnd\b", re.I), "quando"),
    (re.compile(r"\btd\b", re.I), "tudo"),
    (re.compile(r"\bmsm\b", re.I), "mesmo"),
    (re.compile(r"\bblz\b", re.I), "beleza"),
    (re.compile(r"\bvlw\b", re.I), "valeu"),
    (re.compile(r"\bpfv\b", re.I), "por favor"),
    (re.compile(r"\bmt\b", re.I), "muito"),
    (re.compile(r"\bqorf\b", re.I), "quero"),
    (re.compile(r"\bjgo\b", re.I), "jogo"),
    (re.compile(r"\bjogu\b", re.I), "jogo"),
    (re.compile(r"\bve\b", re.I), "ver"),
    (re.compile(r"\bq\b", re.I), "que"),
    (re.compile(r"\bvier\b", re.I), "ver"),
    (re.compile(r"\bqueorf\b", re.I), "quero"),
    (re.compile(r"\bquero\s+f\b", re.I), "quero"),
]


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


def _lev(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


_COMMON_WORDS = {
    "jogo",
    "jogos",
    "partida",
    "partidas",
    "time",
    "times",
    "hoje",
    "amanha",
    "agora",
    "quero",
    "ver",
    "acha",
    "achou",
    "como",
    "esta",
    "voce",
    "que",
    "para",
    "com",
    "sem",
    "mais",
    "menos",
    "bom",
    "boa",
    "copa",
}


def _is_blocked_fuzzy_token(t: str) -> bool:
    """R1 — common PT/EN words must never fuzzy-map to clubs."""
    if t in _COMMON_WORDS:
        return True
    try:
        from src.conversation.entity_safety import is_entity_stopword

        return bool(is_entity_stopword(t))
    except Exception:
        return False


def fuzzy_resolve_team(token: str) -> str | None:
    """Resolve typo / slang token to canonical team name."""
    t = _fold(token)
    if not t:
        return None
    # Exact slang / typo map first (bota, chape, galo, …) — never blocked by stopwords
    if t in _TYPO_TEAMS:
        return _TYPO_TEAMS[t]
    if _is_blocked_fuzzy_token(t):
        return None
    if len(t) < 4:
        return None
    # fuzzy against known keys — avoid matching common words to clubs
    best: tuple[int, str] | None = None
    for key, canon in _TYPO_TEAMS.items():
        if len(key) < 4:
            continue
        if abs(len(key) - len(t)) > 2:
            continue
        # Prefer same starting letter for distance-2 matches
        d = _lev(t, key)
        if d == 0:
            return canon
        if d == 1 and (best is None or d < best[0]):
            best = (d, canon)
        elif d == 2 and t[0] == key[0] and (best is None or best[0] > 2):
            best = (d, canon)
    return best[1] if best else None


def expand_slang(text: str) -> str:
    out = text or ""
    for pat, repl in _SLANG:
        out = pat.sub(repl, out)
    return out


@dataclass
class RecoveryResult:
    original: str
    recovered: str
    teams: list[str] = field(default_factory=list)
    inferred_goal: str | None = None
    temporal: str | None = None
    confidence: float = 0.0
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "original": self.original,
            "recovered": self.recovered,
            "teams": list(self.teams),
            "inferred_goal": self.inferred_goal,
            "temporal": self.temporal,
            "confidence": self.confidence,
            "notes": list(self.notes),
        }


def recover_context(message: str, ctx: dict[str, Any] | None = None) -> RecoveryResult:
    """
    Infer cleaned message + entities from messy user text.
    Never raises.
    """
    original = message or ""
    try:
        expanded = expand_slang(original)
        folded = _fold(expanded)
        notes: list[str] = []
        if expanded != original:
            notes.append("slang_expanded")

        # Token-level fuzzy team fix
        tokens = re.findall(r"[A-Za-zÀ-ÿ0-9]+", expanded)
        teams: list[str] = []
        recovered = expanded
        for tok in tokens:
            canon = fuzzy_resolve_team(tok)
            if canon and canon not in teams:
                # Only replace if token looks wrong / alias
                if _fold(tok) != _fold(canon) and _fold(tok) not in {
                    _fold(c) for c in (canon,)
                }:
                    # replace whole-word typo
                    recovered = re.sub(
                        rf"(?<!\w){re.escape(tok)}(?!\w)",
                        canon,
                        recovered,
                        count=1,
                        flags=re.I,
                    )
                    notes.append(f"fuzzy:{tok}->{canon}")
                teams.append(canon)

        # Also scan known typo keys in folded recovered
        folded_r = _fold(recovered)
        for key, canon in sorted(_TYPO_TEAMS.items(), key=lambda kv: -len(kv[0])):
            if re.search(rf"(?<!\w){re.escape(key)}(?!\w)", folded_r):
                if canon not in teams:
                    teams.append(canon)

        # A vs B / A x B / A ou B / contra / entre — pair sides (R5)
        vs_m = re.search(
            r"(?<!\w)([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9.-]{2,20})\s+"
            r"(?:x|vs\.?|versus|contra|ou|entre)\s+"
            r"([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9.-]{2,20})(?!\w)",
            recovered,
            flags=re.I,
        )
        if vs_m:
            for raw_side in (vs_m.group(1), vs_m.group(2)):
                side = raw_side.strip(" .,!?")
                if _fold(side) in _COMMON_WORDS or _is_blocked_fuzzy_token(_fold(side)):
                    continue
                canon = fuzzy_resolve_team(side)
                if not canon and len(side) >= 4:
                    canon = side[:1].upper() + side[1:].lower()
                if canon and canon not in teams:
                    teams.append(canon)
                    notes.append(f"vs_side:{canon}")
        else:
            # Phrase comparisons: "mais chance … A ou B"
            try:
                from src.conversation.entity_safety import extract_comparison_pair

                pair = extract_comparison_pair(recovered)
                if pair:
                    for side in pair:
                        if _fold(side) in _COMMON_WORDS or _is_blocked_fuzzy_token(
                            _fold(side)
                        ):
                            continue
                        canon = fuzzy_resolve_team(side)
                        if not canon and len(side) >= 3:
                            canon = side[:1].upper() + side[1:].lower()
                        if canon and canon not in teams:
                            teams.append(canon)
                            notes.append(f"cmp_side:{canon}")
            except Exception:
                pass

        # PATCH-001 — drop stopword-fuzzy / ungrounded teams before focus
        try:
            from src.conversation.entity_safety import filter_recovery_teams

            _verdict = filter_recovery_teams(original, teams, raw_notes=notes)
            if _verdict.rejected:
                notes.append(f"safety_rejected:{','.join(_verdict.rejected)}")
            _safe_canons = [
                s.canon
                for s in _verdict.teams
                if s.grounded and s.confidence >= 0.55
            ]
            if _safe_canons or _verdict.rejected:
                teams = []
                for c in _safe_canons:
                    if c not in teams:
                        teams.append(c)
            for s in _verdict.teams:
                notes.append(f"entity_conf:{s.canon}={s.confidence:.2f}")
        except Exception as _saf_exc:
            notes.append(f"entity_safety_skip:{_saf_exc}")

        temporal = None
        if re.search(r"\bhoje\b", folded_r):
            temporal = "today"
        elif re.search(r"\bamanha\b", folded_r):
            temporal = "tomorrow"
        elif re.search(r"\b(agora|atualmente|momento)\b", folded_r):
            temporal = "now"

        goal = None
        conf = 0.4
        topic_kind_hint = None

        # Kickoff / hours
        if re.search(
            r"\b(joga\s+que\s+horas|que\s+horas|horario\s+d[oe]|que\s+horas\s+joga)\b",
            folded_r,
        ):
            goal = "kickoff_lookup"
            topic_kind_hint = "kickoff"
            conf = 0.82
            if teams:
                recovered = f"{teams[0]} joga que horas?"
                notes.append("completed:kickoff")
        # Phase 8.2-E — recent-match / opinion BEFORE calendar ("jogo do" must not steal)
        elif re.search(
            r"("
            r"o\s*que\s+(?:voce\s+)?(?:achou|acha)\s+"
            r"(?:d[oe]\s+)?(?:jogo|partida|atuacao)|"
            r"o\s*que\s+(?:voce\s+)?(?:achou|acha)\s+da\s+atuacao|"
            r"como\s+foi\s+(?:o\s+|a\s+)?(?:jogo|partida|atuacao)|"
            r"como\s+foi\s+a\s+atuacao|"
            r"como\s+(?:voce\s+)?viu\s+(?:o\s+)?(?:ultimo\s+|ultima\s+)?(?:jogo|partida)|"
            r"\bjogou\s+bem\b|"
            r"(?:achou|opiniao).{0,48}\b(?:ontem|ultimo|ultima)\b|"
            r"\b(?:ontem|ultimo|ultima).{0,48}\b(?:achou|opiniao|como\s+foi|jogou\s+bem)\b|"
            r"\bachou\s+d[oe]\s+(?:jogo|partida|atuacao)\b|"
            r"\bachou\s+da\s+atuacao\b|"
            r"\batuacao\s+d[oe]\b"
            r")",
            folded_r,
        ) or (
            re.search(
                r"\b(o\s*que\s+(?:voce\s+)?acha|oq\s+acha|achou|atuacao)\b",
                folded_r,
            )
            and re.search(
                r"\b(jogo|partida|atuacao|ontem|ultimo|ultima|como\s+foi)\b",
                folded_r,
            )
        ):
            goal = "team_opinion"
            conf = 0.88
            topic_kind_hint = "opinion"
            # Keep original phrasing so Natural sees ontem/jogo/atuação
            recovered = original
            notes.append("completed:recent_match_opinion")
        # opinion / moment (general — still before bare calendar)
        elif re.search(
            r"\b(o\s+que\s+(?:voce\s+)?acha|oq\s+acha|achou|momento|"
            r"como\s+esta|como\s+vai)\b",
            folded_r,
        ):
            goal = "team_opinion"
            conf = 0.8
            topic_kind_hint = "moment" if temporal == "now" else "opinion"
            if teams and temporal == "now":
                recovered = f"o que acha do {teams[0]} agora"
                notes.append("completed:opinion_now")
            elif teams:
                recovered = f"o que acha do {teams[0]}"
                notes.append("completed:opinion")
        # Calendar / fixture (preserve A x B — never collapse to one team)
        elif re.search(
            r"\b(quero\s+(?:saber\s+)?(?:sobre\s+)?(?:o\s+)?jogo|"
            r"quero\s+ver|ver\s+o\s+jogo|tem\s+jogo|jogo\s+d[oe]|"
            r"partidas?\s+d[oe]|proximo\s+jogo|"
            r"quando\s+(?:e|eh|é)\s+o\s+proximo\s+jogo)\b",
            folded_r,
        ) or (vs_m and temporal):
            goal = "calendar_or_fixture"
            conf = 0.78
            when = "hoje" if temporal == "today" else (
                "amanhã" if temporal == "tomorrow" else ""
            )
            if len(teams) >= 2:
                topic_kind_hint = "fixture"
                recovered = f"jogo {teams[0]} x {teams[1]}" + (f" {when}" if when else "")
                notes.append("completed:fixture_pair")
                conf = 0.9
            elif teams and temporal == "today":
                topic_kind_hint = "calendar"
                recovered = f"jogo do {teams[0]} hoje"
                notes.append("completed:team_today")
                conf = 0.85
            elif teams:
                topic_kind_hint = "calendar"
                recovered = f"jogo do {teams[0]}" + (f" {when}" if when else "")
                notes.append("completed:team_calendar")
            elif re.search(r"\b(tem\s+jogo|proximo\s+jogo|quando\s+(?:e|eh|é)\s+o\s+proximo)\b", folded_r):
                topic_kind_hint = "calendar"
                notes.append("completed:calendar_generic")
        # win today?
        elif re.search(r"\b(ganha|vence|empata)\b", folded_r) and teams:
            goal = "match_outlook"
            topic_kind_hint = "outlook"
            conf = 0.78
            if temporal == "today":
                recovered = f"o {teams[0]} ganha hoje?"
                notes.append("completed:win_today")
        # bare "bota hj"
        elif teams and temporal and len(tokens) <= 3:
            goal = "calendar_or_fixture"
            topic_kind_hint = "calendar"
            conf = 0.82
            when = "hoje" if temporal == "today" else "amanhã"
            recovered = f"jogo do {teams[0]} {when}"
            notes.append("completed:bare_team_time")
        # "e o santos?" / "e do flamengo?" — entity pivot
        elif teams and re.search(r"\be\s+(?:o|a|do|da)\s+\w+", folded_r):
            goal = "team_opinion"
            topic_kind_hint = "opinion"
            conf = 0.78
            recovered = f"o que acha do {teams[0]}"
            notes.append("completed:entity_pivot")

        # Historical / copa
        if re.search(r"\bcopa\b", folded_r) and re.search(r"\b20\d{2}\b", folded_r):
            goal = "historical_narrative"
            topic_kind_hint = "historical"
            conf = max(conf, 0.88)
            notes.append("historical_copa")

        if recovered != original:
            notes.append("message_rewritten")

        result = RecoveryResult(
            original=original,
            recovered=recovered.strip() or original,
            teams=teams[:2],
            inferred_goal=goal,
            temporal=temporal,
            confidence=conf,
            notes=notes,
        )
        if ctx is not None:
            data = result.to_dict()
            if topic_kind_hint:
                data["topic_kind_hint"] = topic_kind_hint
            ctx["context_recovery"] = data
        return result
    except Exception as exc:
        logger.warning("context_recovery fail-open: %s", exc)
        return RecoveryResult(original=original, recovered=original, confidence=0.0)


def apply_recovery_to_message(
    message: str,
    ctx: dict[str, Any] | None = None,
    *,
    min_confidence: float = 0.7,
) -> str:
    """Return recovered message if confident enough; else original."""
    try:
        result = recover_context(message, ctx)
        if (
            result.confidence >= min_confidence
            and result.recovered
            and result.recovered.strip() != (message or "").strip()
        ):
            logger.warning(
                "[AUDIT] ContextRecovery: %r → %r goal=%s teams=%s conf=%.2f notes=%s",
                message,
                result.recovered,
                result.inferred_goal,
                result.teams,
                result.confidence,
                result.notes,
            )
            return result.recovered
        logger.warning(
            "[AUDIT] ContextRecovery: keep_original conf=%.2f notes=%s",
            result.confidence,
            result.notes,
        )
        return message
    except Exception as exc:
        logger.warning("apply_recovery_to_message fail-open: %s", exc)
        return message
