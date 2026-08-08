"""
Aurora v4.7.2 — User Profile Memory (single source of truth: ctx['about_you']).

About You from Identity Center (localStorage → request.about_you → ctx).
Supports teach / forget / query ("qual meu nome?", "para qual time eu torço?").

Never overwrites betting ctx["user_profile"].
Fail-open. Additive.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any

logger = logging.getLogger(__name__)

PROFILE_KEY = "about_you"
GREETING_SENT_KEY = "about_you_greeting_sent"


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
    ctx.pop(GREETING_SENT_KEY, None)


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
    m2 = re.search(
        r"\b(?:meu\s+time(?:\s+do\s+coracao)?\s+e|torco\s+(?:pro|para\s+o|pelo))\s+((?:o\s+|a\s+)?[a-z0-9][\w\s-]{1,40})",
        folded,
    )
    if m2:
        team = m2.group(1).strip(" .,!")
        team = re.sub(r"^(o|a)\s+", "", team).strip()
        if team:
            out["favorite_team"] = (team[:1].upper() + team[1:])[:40]
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


def detect_profile_query(message: str) -> str | None:
    """
    Return query kind: name | team | project | role | summary | None
    """
    folded = _fold(message)
    if re.search(
        r"\b(qual\s+(?:e\s+)?meu\s+nome|como\s+(?:e\s+)?meu\s+nome|"
        r"voce\s+sabe\s+meu\s+nome|qual\s+o\s+meu\s+nome)\b",
        folded,
    ):
        return "name"
    if re.search(
        r"\b("
        r"para\s+qual\s+time\s+eu\s+torc\w*|"
        r"qual\s+(?:e\s+)?meu\s+time|"
        r"qual\s+time\s+eu\s+torc\w*|"
        r"voce\s+sabe\s+(?:meu\s+time|para\s+quem\s+eu\s+torc\w*)|"
        r"qual\s+(?:e\s+)?(?:o\s+)?meu\s+time\s+(?:do\s+coracao|favorito)"
        r")\b",
        folded,
    ):
        return "team"
    if re.search(
        r"\b(qual\s+(?:e\s+)?meu\s+projeto|em\s+que\s+projeto|"
        r"voce\s+lembra\s+(?:do\s+meu\s+)?projeto)\b",
        folded,
    ):
        return "project"
    if re.search(
        r"\b(qual\s+(?:e\s+)?meu\s+(?:papel|role)|o\s+que\s+voce\s+sabe\s+sobre\s+mim|"
        r"me\s+conta\s+(?:o\s+)?que\s+voce\s+sabe\s+(?:de|sobre)\s+mim)\b",
        folded,
    ):
        return "summary"
    return None


def build_profile_query_reply(kind: str, ctx: dict[str, Any] | None) -> str:
    prof = get_profile(ctx)
    if kind == "name":
        name = (prof.get("name") or "").strip()
        if name:
            return f"Seu nome aqui é {name}."
        return (
            "Ainda não tenho seu nome guardado. "
            "Você pode preencher em Sobre Você no Identity Center, "
            "ou me dizer: “meu nome é …”."
        )
    if kind == "team":
        team = (prof.get("favorite_team") or "").strip()
        if team:
            return f"Pelo que anotei, você torce para o {team}."
        return (
            "Ainda não sei para qual time você torce. "
            "Pode salvar no Identity Center ou me dizer: “meu time é …”."
        )
    if kind == "project":
        project = (prof.get("project") or "").strip()
        if project:
            return f"Lembro do projeto {project}."
        return "Ainda não anotei um projeto seu. Pode me dizer qual é?"
    # summary
    bits = []
    if prof.get("name"):
        bits.append(f"nome: {prof['name']}")
    if prof.get("role"):
        bits.append(f"papel: {prof['role']}")
    if prof.get("favorite_team"):
        bits.append(f"time: {prof['favorite_team']}")
    if prof.get("project"):
        bits.append(f"projeto: {prof['project']}")
    if bits:
        return "Do que guardei sobre você: " + "; ".join(bits) + "."
    return (
        "Ainda não tenho informações suas salvas. "
        "No Identity Center → Sobre Você dá para preencher nome, time e projeto."
    )


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


def consume_greeting_prefix(
    ctx: dict[str, Any] | None,
    *,
    social_intents: list[str] | None = None,
) -> str | None:
    """
    Return greeting prefix at most ONCE per session.
    Only for GREETING turns — never farewell / wellbeing-only.
    """
    try:
        if not isinstance(ctx, dict):
            return None
        if ctx.get(GREETING_SENT_KEY):
            return None
        social = list(social_intents or [])
        # Must be a greeting; skip pure farewell / thanks
        if social:
            if "FAREWELL" in social and "GREETING" not in social:
                return None
            if "THANKS" in social and "GREETING" not in social:
                return None
            if "GREETING" not in social and "WELLBEING" in social:
                # "como você está" alone — no reopen greeting spam
                return None
            if "GREETING" not in social:
                return None
        prefix = greeting_prefix(ctx)
        if prefix:
            ctx[GREETING_SENT_KEY] = True
        return prefix
    except Exception:
        return None


def _soft_payload(reply: str, *, entities: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        from src.conversation.message_intelligence import build_conversational_payload

        payload = build_conversational_payload(reply, {})
    except Exception:
        payload = {
            "intent": "small_talk",
            "entities": {},
            "best_markets": [],
            "executive_summary": reply,
            "final_recommendation": reply,
            "confidence": {
                "score": 0.0,
                "label": "insufficient",
                "explanation": "",
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
            "brain": {},
        }
    payload["intent"] = "small_talk"
    ents = dict(payload.get("entities") or {})
    ents.update(
        {
            "profile_memory": True,
            "show_header": False,
            "has_analysis": False,
            "natural_conversation": True,
            "skip_llm": True,
        }
    )
    if entities:
        ents.update(entities)
    payload["entities"] = ents
    payload["best_markets"] = []
    payload["match_card"] = None
    payload["executive_summary"] = reply
    payload["final_recommendation"] = reply
    return payload


def try_profile_commands(
    message: str,
    ctx: dict[str, Any] | None,
    prefs: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Handle forget / teach / query. Returns soft payload or None."""
    try:
        if ctx is None:
            return None

        if detect_forget_command(message):
            clear_profile(ctx)
            reply = "Pronto — apaguei as informações pessoais que eu tinha guardado aqui."
            try:
                from src.conversation.presence_humanization import apply_presence_humanization

                reply = apply_presence_humanization(reply, prefs, family_hint="thanks")
            except Exception:
                pass
            return _soft_payload(reply)

        # Teach BEFORE query — "meu time do coração é X" must save, not ask
        patch = detect_profile_teach(message)
        if patch:
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
            return _soft_payload(reply)

        qkind = detect_profile_query(message)
        if qkind:
            reply = build_profile_query_reply(qkind, ctx)
            try:
                from src.conversation.presence_humanization import apply_presence_humanization

                reply = apply_presence_humanization(reply, prefs, family_hint="thanks")
            except Exception:
                pass
            return _soft_payload(reply, entities={"profile_query": qkind})

        return None
    except Exception as exc:
        logger.warning("try_profile_commands fail-open: %s", exc)
        return None
