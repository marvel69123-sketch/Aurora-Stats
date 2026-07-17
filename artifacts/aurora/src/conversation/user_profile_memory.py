"""
Aurora v4.6 — User Profile Memory (lightweight).

Stores a simple About You profile on conversation context / SQLite.
No login. Supports forget commands.

Uses ctx["about_you"] — never overwrites betting ctx["user_profile"]
(bankroll / risk / experience from conversation_engine).
Fail-open. Additive.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any

logger = logging.getLogger(__name__)

# Separate from betting profile (ctx["user_profile"])
PROFILE_KEY = "about_you"


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


def empty_profile() -> dict[str, str]:
    return {
        "name": "",
        "role": "",
        "favorite_team": "",
        "project": "",
    }


def get_profile(ctx: dict[str, Any] | None) -> dict[str, str]:
    if not ctx:
        return empty_profile()
    raw = ctx.get(PROFILE_KEY)
    if not isinstance(raw, dict):
        return empty_profile()
    base = empty_profile()
    for k in base:
        if raw.get(k):
            base[k] = str(raw[k])[:80]
    return base


def get_profile_name(ctx: dict[str, Any] | None) -> str | None:
    name = get_profile(ctx).get("name") or ""
    return name.strip() or None


def save_profile(ctx: dict[str, Any], patch: dict[str, Any]) -> dict[str, str]:
    cur = get_profile(ctx)
    for k in empty_profile():
        if k in patch and patch[k] is not None:
            cur[k] = str(patch[k])[:80]
    ctx[PROFILE_KEY] = cur
    return cur


def clear_profile(ctx: dict[str, Any]) -> None:
    ctx[PROFILE_KEY] = empty_profile()


def detect_forget_command(message: str) -> bool:
    folded = _fold(message)
    return bool(
        re.search(
            r"\b(esqueca\s+isso|apague\s+minhas\s+informacoes|"
            r"apague\s+tudo\s+sobre\s+mim|apagar\s+meu\s+perfil|"
            r"esquece\s+meu\s+nome|limpar\s+perfil|"
            r"forget\s+my\s+(?:name|profile)|forget\s+me)\b",
            folded,
        )
    )


def detect_profile_teach(message: str) -> dict[str, str] | None:
    """Lightweight 'meu nome é X' / 'meu time é Y' extraction."""
    folded = _fold(message)
    original = message or ""
    out: dict[str, str] = {}
    m = re.search(
        r"\b(?:meu\s+nome\s+[eé]|me\s+chamo|pode\s+me\s+chamar\s+de)\s+([A-Za-zÀ-ÿ][\wÀ-ÿ\s-]{1,40})",
        original,
        re.I,
    )
    if m:
        out["name"] = m.group(1).strip(" .,!")[:40]
    # Team: match on folded (accents) then recover title from original when possible
    m2 = re.search(
        r"\b(?:meu\s+time(?:\s+do\s+coracao)?\s+e|torco\s+(?:pro|para\s+o|pelo))\s+((?:o\s+|a\s+)?[a-z0-9][\w\s-]{1,40})",
        folded,
    )
    if m2:
        team = m2.group(1).strip(" .,!")
        team = re.sub(r"^(o|a)\s+", "", team).strip()
        out["favorite_team"] = (team[:1].upper() + team[1:])[:40] if team else ""
        if not out["favorite_team"]:
            out.pop("favorite_team", None)
    m3 = re.search(
        r"\b(?:estou\s+testando|meu\s+projeto\s+[eé]|trabalho\s+(?:na|no|em))\s+([A-Za-zÀ-ÿ][\wÀ-ÿ\s-]{1,40})",
        original,
        re.I,
    )
    if m3 and "aurora" in folded:
        out["project"] = "Aurora"
    elif m3:
        out["project"] = m3.group(1).strip(" .,!")[:40]
    return out or None


def greeting_prefix(ctx: dict[str, Any] | None) -> str | None:
    """Optional warm reopen line — not a full reply."""
    try:
        prof = get_profile(ctx)
        name = (prof.get("name") or "").strip()
        if not name:
            return None
        team = (prof.get("favorite_team") or "").strip()
        if team:
            return f"Bom te ver novamente, {name} — e vamos que o {team} anime o dia."
        project = (prof.get("project") or "").strip()
        if project:
            return f"Bom te ver novamente, {name}. Como estão os testes da {project} hoje?"
        return f"Bom te ver novamente, {name}."
    except Exception:
        return None


def try_profile_commands(
    message: str,
    ctx: dict[str, Any] | None,
    prefs: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Handle forget / teach profile. Returns soft payload or None."""
    try:
        if ctx is None:
            return None
        if detect_forget_command(message):
            clear_profile(ctx)
            reply = "Pronto — apaguei as informações pessoais que eu tinha guardado aqui."
        else:
            patch = detect_profile_teach(message)
            if not patch:
                return None
            save_profile(ctx, patch)
            bits = []
            if patch.get("name"):
                bits.append(f"vou te chamar de {patch['name']}")
            if patch.get("favorite_team"):
                bits.append(f"anotei o {patch['favorite_team']} como seu time")
            if patch.get("project"):
                bits.append(f"lembrei do projeto {patch['project']}")
            reply = "Combinado — " + ", ".join(bits) + "."

        try:
            from src.conversation.presence_humanization import apply_presence_humanization

            reply = apply_presence_humanization(reply, prefs, family_hint="thanks")
        except Exception:
            pass
        from src.conversation.message_intelligence import build_conversational_payload

        payload = build_conversational_payload(reply, {})
        payload["intent"] = "small_talk"
        ents = dict(payload.get("entities") or {})
        ents.update(
            {
                "profile_memory": True,
                "show_header": False,
                "has_analysis": False,
                "natural_conversation": True,
            }
        )
        payload["entities"] = ents
        payload["best_markets"] = []
        payload["match_card"] = None
        return payload
    except Exception as exc:
        logger.warning("try_profile_commands fail-open: %s", exc)
        return None
