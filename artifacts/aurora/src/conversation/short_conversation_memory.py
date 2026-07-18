"""
Phase 8.2-C — Short conversational memory (minimal).

Session-scoped only (lives on ctx / ConversationManager).
Resolves pronouns like "dele" using last_team / last_fixture BEFORE MasterIntent
so follow-ups do not fall into GeneralAssistant.

Fail-open. Does not modify repair / ownership / 7.9 / GA modules.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any

logger = logging.getLogger(__name__)

CTX_KEY = "short_conversation_memory"
RESOLVE_KEY = "short_memory_resolve"

_TEAM_PAT = re.compile(
    r"\b("
    r"fluminense|flamengo|botafogo|palmeiras|corinthians|"
    r"sao\s+paulo|santos|vasco|gremio|internacional|"
    r"atletico\s+mineiro|cruzeiro|bahia|fortaleza|"
    r"bragantino|cuiaba|juventude|vitoria|mirassol"
    r")\b",
    re.I,
)

_TEAM_TITLE = {
    "fluminense": "Fluminense",
    "flamengo": "Flamengo",
    "botafogo": "Botafogo",
    "palmeiras": "Palmeiras",
    "corinthians": "Corinthians",
    "sao paulo": "São Paulo",
    "santos": "Santos",
    "vasco": "Vasco",
    "gremio": "Grêmio",
    "internacional": "Internacional",
    "atletico mineiro": "Atlético Mineiro",
    "cruzeiro": "Cruzeiro",
    "bahia": "Bahia",
    "fortaleza": "Fortaleza",
    "bragantino": "Bragantino",
    "cuiaba": "Cuiabá",
    "juventude": "Juventude",
    "vitoria": "Vitória",
    "mirassol": "Mirassol",
}

_LAST_MATCH = re.compile(
    r"\b("
    r"(?:ultimo|ultima)\s+(?:jogo|partida)|"
    r"qual\s+foi\s+o\s+ultimo\s+jogo|"
    r"ultimo\s+jogo\s+d[oe]"
    r")\b",
    re.I,
)

_OPINION = re.compile(
    r"\b(o\s*que\s+(?:voce\s+)?(?:achou|acha)|achou|opiniao|como\s+foi)\b",
    re.I,
)

_ENTITY_SWITCH = re.compile(
    r"^\s*e\s+(?:o|a|do|da)\s+([A-Za-zÀ-ÿ][\wÀ-ÿ.-]{2,30})\s*\??\s*$",
    re.I,
)

# Pronoun follow-ups that need last_team / last_fixture
_PRONOUN_OPINION = re.compile(
    r"("
    r"o\s*que\s+(?:voce\s+)?(?:achou|acha)\s+(?:d(?:ele|ela|isso)|do\s+jogo)\b|"
    r"o\s*que\s+(?:voce\s+)?(?:achou|acha)\s+d(?:ele|ela)\b|"
    r"como\s+foi\s+(?:ele|ela|isso|o\s+jogo)\b|"
    r"^\s*e\s+(?:o\s+)?d(?:ele|ela)\s*\??\s*$|"
    r"^\s*d(?:ele|ela)\s*\??\s*$|"
    r"achou\s+d(?:ele|ela)\b"
    r")",
    re.I,
)


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


def _title_team(raw: str) -> str:
    key = _fold(raw)
    return _TEAM_TITLE.get(key) or (raw[:1].upper() + raw[1:] if raw else raw)


def _extract_team(text: str) -> str | None:
    m = _TEAM_PAT.search(_fold(text or ""))
    if not m:
        return None
    return _title_team(m.group(1))


def get_short_memory(ctx: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(ctx, dict):
        return {}
    raw = ctx.get(CTX_KEY)
    return dict(raw) if isinstance(raw, dict) else {}


def _question_type(message: str) -> str | None:
    folded = _fold(message)
    if not folded:
        return None
    if _LAST_MATCH.search(folded):
        return "last_match"
    if _ENTITY_SWITCH.match(message or ""):
        return "entity_switch"
    if _OPINION.search(folded):
        return "opinion"
    if re.search(r"\b(agenda|tem\s+jogo|proximo\s+jogo|jogos?\s+d[oe])\b", folded):
        return "calendar"
    if _extract_team(folded):
        return "team_talk"
    return None


def _extract_team_from_payload(payload: dict[str, Any] | None) -> str | None:
    if not isinstance(payload, dict):
        return None
    ents = dict(payload.get("entities") or {})
    team = ents.get("team")
    if isinstance(team, str) and team.strip():
        return team.strip()
    teams = ents.get("teams")
    if isinstance(teams, (list, tuple)) and teams:
        t0 = teams[0]
        if isinstance(t0, str) and t0.strip():
            return t0.strip()
    match = payload.get("match") if isinstance(payload.get("match"), dict) else {}
    for key in ("home", "away"):
        val = match.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _soft_fixture_label(team: str, qtype: str | None) -> str | None:
    if not team:
        return None
    if qtype == "last_match":
        return f"último jogo do {team}"
    return None


def note_short_memory(
    ctx: dict[str, Any] | None,
    message: str,
    payload: dict[str, Any] | None,
) -> None:
    """Persist minimal turn memory for the current session only."""
    if not isinstance(ctx, dict):
        return
    try:
        # Prefer original user text (pronoun resolve / pre-recovery raw)
        resolve = ctx.get(RESOLVE_KEY) if isinstance(ctx.get(RESOLVE_KEY), dict) else {}
        user_q = str(
            resolve.get("original")
            or ctx.get("raw_user_message")
            or message
            or ""
        ).strip()

        # Skip storing repair turns as the "subject" question
        try:
            from src.conversation.conversation_repair import is_repair_signal

            if is_repair_signal(user_q):
                mem = get_short_memory(ctx)
                if isinstance(payload, dict):
                    text = str(
                        payload.get("executive_summary")
                        or payload.get("final_recommendation")
                        or ""
                    ).strip()
                    if text:
                        mem["last_assistant_reply"] = text[:240]
                        ctx[CTX_KEY] = mem
                return
        except Exception:
            pass

        mem = get_short_memory(ctx)
        qtype = _question_type(user_q)
        team = (
            _extract_team_from_payload(payload)
            or _extract_team(user_q)
            or _extract_team(str(resolve.get("rewrite") or ""))
        )

        # Entity switch: "e o palmeiras?" updates subject; keep last_match frame
        sw = _ENTITY_SWITCH.match(user_q)
        if sw:
            switched = _extract_team(sw.group(1)) or _title_team(sw.group(1))
            if switched:
                team = switched
                qtype = "entity_switch"
                if mem.get("last_question_type") == "last_match" or mem.get(
                    "last_fixture"
                ):
                    mem["last_fixture"] = f"último jogo do {switched}"
                    mem["last_question_type"] = "last_match"
                else:
                    mem["last_question_type"] = "entity_switch"

        if user_q:
            mem["last_user_question"] = user_q[:240]
        if team:
            mem["last_team"] = team
        if qtype and qtype != "entity_switch":
            mem["last_question_type"] = qtype
        elif qtype == "entity_switch" and not mem.get("last_question_type"):
            mem["last_question_type"] = "entity_switch"

        if qtype == "last_match" and team:
            mem["last_fixture"] = _soft_fixture_label(team, "last_match")
        elif team and not mem.get("last_fixture") and mem.get("last_question_type") == "last_match":
            mem["last_fixture"] = _soft_fixture_label(team, "last_match")

        # Real fixture string from payload when present (never invent scores)
        if isinstance(payload, dict):
            match = payload.get("match")
            if isinstance(match, dict):
                home, away = match.get("home"), match.get("away")
                if home and away:
                    mem["last_fixture"] = f"{home} x {away}"
            text = str(
                payload.get("executive_summary")
                or payload.get("final_recommendation")
                or ""
            ).strip()
            if text:
                mem["last_assistant_reply"] = text[:240]

        ctx[CTX_KEY] = mem
        # Clear one-shot resolve marker
        ctx.pop(RESOLVE_KEY, None)
    except Exception as exc:
        logger.warning("note_short_memory fail-open: %s", exc)


def apply_short_memory_resolve(
    message: str,
    ctx: dict[str, Any] | None,
) -> str:
    """
    Rewrite pronoun follow-ups using short memory.
    Must run BEFORE MasterIntent so sport/opinion routing can see the team.
    """
    try:
        if not message or not isinstance(ctx, dict):
            return message

        try:
            from src.conversation.conversation_repair import is_repair_signal

            if is_repair_signal(message):
                return message
        except Exception:
            pass

        folded = _fold(message)
        if not _PRONOUN_OPINION.search(folded):
            return message

        mem = get_short_memory(ctx)
        team = mem.get("last_team")
        fixture = mem.get("last_fixture")
        qtype = mem.get("last_question_type")
        if not isinstance(team, str) or not team.strip():
            logger.warning(
                "[AUDIT] ShortMemory: pronoun follow-up without last_team msg=%r",
                message[:80],
            )
            return message
        team = team.strip()

        if isinstance(fixture, str) and fixture.strip():
            subject = fixture.strip()
        elif qtype == "last_match":
            subject = f"último jogo do {team}"
        else:
            subject = team

        # "e o dele?" / bare "dele?"
        if re.search(r"^\s*e\s+(?:o\s+)?d(?:ele|ela)\s*\??\s*$", folded) or re.search(
            r"^\s*d(?:ele|ela)\s*\??\s*$", folded
        ):
            if qtype == "last_match" or (
                isinstance(fixture, str) and "jogo" in _fold(str(fixture))
            ):
                rewrite = f"o que você achou do {subject}?"
            else:
                rewrite = f"e o {team}?"
        elif re.search(r"como\s+foi", folded):
            rewrite = f"como foi {subject}?"
        else:
            # o que achou/acha dele
            rewrite = f"o que você achou do {subject}?"

        ctx[RESOLVE_KEY] = {
            "original": message,
            "rewrite": rewrite,
            "last_team": team,
            "last_fixture": fixture,
            "reason": "pronoun_short_memory",
        }
        logger.warning(
            "[AUDIT] ShortMemory: %r → %r team=%r fixture=%r",
            message,
            rewrite,
            team,
            fixture,
        )
        try:
            from src.conversation.pipeline_trace import trace as _ptrace

            _ptrace(
                "SHORT_MEMORY",
                action="resolve",
                original=message[:80],
                rewrite=rewrite[:80],
                team=team,
            )
        except Exception:
            pass
        return rewrite
    except Exception as exc:
        logger.warning("apply_short_memory_resolve fail-open: %s", exc)
        return message
