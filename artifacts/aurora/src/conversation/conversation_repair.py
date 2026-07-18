"""
Phase 8.2-A — Conversation Repair (isolated).

Detects human correction / frustration signals and answers in repair mode
instead of falling through to GeneralAssistant.reply_general().

Fail-open. Does not touch ownership / confidence / sports / 7.9 modules.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any

logger = logging.getLogger(__name__)

CTX_KEY = "repair_memory"

_REPAIR = re.compile(
    r"("
    r"nao\s+foi\s+(?:isso|essa|este|o\s+que)|"
    r"nao\s+era\s+(?:isso|essa|este)|"
    r"nao\s+(?:e|eh|é)\s+(?:isso|essa)|"
    r"voce\s+nao\s+entendeu|"
    r"nao\s+(?:voce\s+)?entendeu|"
    r"nao\s+entendeu\s+o\s+que|"
    r"pensa\s+um\s+pouco|"
    r"agora\s+entendeu|"
    r"voce\s+esta\s+em\s+loop|"
    r"para+a*\s+de\s+(?:repet|fica)|"
    r"para\s+de\s+fica(?:r)?\s+em\s+loop|"
    r"voce\s+interpretou\s+errado|"
    r"interpretou\s+errado|"
    r"voce\s+errou|"
    r"isso\s+nao\s+(?:e|eh|é)\s+o\s+que"
    r")",
    re.I,
)

_MATCH_OPINION = re.compile(
    r"("
    r"\bachou\b|\bopiniao\b|"
    r"o\s+que\s+(?:voce\s+)?acha|"
    r"ultimo\s+jogo|ontem|"
    r"partida"
    r")",
    re.I,
)

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


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


def is_repair_signal(message: str) -> bool:
    return bool(_REPAIR.search(_fold(message)))


def _title_team(raw: str) -> str:
    key = _fold(raw)
    return _TEAM_TITLE.get(key) or (raw[:1].upper() + raw[1:] if raw else raw)


def _extract_team_from_text(text: str) -> str | None:
    m = _TEAM_PAT.search(_fold(text or ""))
    if not m:
        return None
    return _title_team(m.group(1))


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


def get_repair_memory(ctx: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(ctx, dict):
        return {}
    raw = ctx.get(CTX_KEY)
    return dict(raw) if isinstance(raw, dict) else {}


def note_repair_memory(
    ctx: dict[str, Any] | None,
    message: str,
    payload: dict[str, Any] | None,
) -> None:
    """Minimal sticky memory for repair only: last Q, last team, last reply."""
    if not isinstance(ctx, dict):
        return
    try:
        mem = get_repair_memory(ctx)
        text = ""
        if isinstance(payload, dict):
            text = str(
                payload.get("executive_summary")
                or payload.get("final_recommendation")
                or ""
            ).strip()

        if is_repair_signal(message):
            mem["repair_active"] = True
            if text:
                mem["last_assistant_reply"] = text[:240]
            ctx[CTX_KEY] = mem
            return

        mem["repair_active"] = False
        q = (message or "").strip()
        if q:
            mem["last_user_question"] = q[:240]
        team = (
            _extract_team_from_payload(payload)
            or _extract_team_from_text(message)
            or mem.get("last_team")
        )
        if isinstance(team, str) and team.strip():
            mem["last_team"] = team.strip()
        if text:
            mem["last_assistant_reply"] = text[:240]
        ctx[CTX_KEY] = mem
    except Exception as exc:
        logger.warning("note_repair_memory fail-open: %s", exc)


def _build_repair_reply(message: str, ctx: dict[str, Any] | None) -> str:
    mem = get_repair_memory(ctx)
    team = mem.get("last_team")
    if not isinstance(team, str) or not team.strip():
        team = _extract_team_from_text(mem.get("last_user_question") or "") or None
    last_q = str(mem.get("last_user_question") or "").strip()
    folded = _fold(message)
    opinionish = bool(_MATCH_OPINION.search(_fold(last_q)))

    if re.search(r"agora\s+entendeu", folded):
        if team and opinionish:
            return (
                f"Estou alinhando de novo: você queria minha opinião sobre "
                f"o jogo do {team} — certo?\n\n"
                "Confirma isso ou me diz em uma frase o que você queria saber."
            )
        if team:
            return (
                f"Estou alinhando de novo com o {team}. "
                "Confirma o que exatamente você queria saber?"
            )
        return (
            "Ainda estou alinhando com o que você quis dizer. "
            "Pode confirmar em uma frase o que você queria saber?"
        )

    if re.search(r"pensa\s+um\s+pouco", folded):
        if team and opinionish:
            return (
                "Vou pensar de novo no que você pediu.\n\n"
                f"Você queria minha opinião sobre a partida do {team} — é isso?"
            )
        if team:
            return (
                "Vou pensar de novo no que você pediu.\n\n"
                f"O fio era o {team}. Pode confirmar o que você queria saber?"
            )
        if last_q:
            return (
                "Vou pensar de novo no que você pediu.\n\n"
                f"Você tinha dito: “{last_q[:100]}”. "
                "Pode confirmar o que exatamente queria?"
            )
        return (
            "Vou pensar de novo no que você pediu.\n\n"
            "Pode reformular em uma frase o que você queria saber?"
        )

    if re.search(r"loop|para+a*\s+de\s+(?:repet|fica)", folded):
        return (
            "Você tem razão — eu estava repetindo sem avançar.\n\n"
            + (
                f"Voltando ao ponto: opinião sobre o jogo do {team}?"
                if team and opinionish
                else (
                    f"Voltando ao {team}: o que você queria saber exatamente?"
                    if team
                    else "Pode confirmar o que você queria saber, sem eu reiniciar do zero?"
                )
            )
        )

    # Default correction / "não foi isso" / "não entendeu"
    if team and opinionish:
        return (
            "Acho que interpretei errado.\n\n"
            f"Você queria minha opinião sobre a partida de ontem do {team}?"
        )
    if team:
        return (
            "Acho que interpretei sua pergunta de forma errada.\n\n"
            f"Você queria falar sobre o {team} — pode confirmar o que exatamente "
            "você queria saber?"
        )
    if last_q:
        return (
            "Entendi que minha resposta anterior não foi o que você esperava.\n\n"
            f"Sobre “{last_q[:100]}” — pode reformular o que você queria saber?"
        )
    return (
        "Acho que interpretei sua pergunta de forma errada.\n\n"
        "Pode reformular ou confirmar o que exatamente você queria saber?"
    )


def _payload(text: str) -> dict[str, Any]:
    try:
        from src.brain import get_brain_meta

        brain = get_brain_meta()
    except Exception:
        brain = {}
    return {
        "intent": "conversation_repair",
        "entities": {
            "conversation_repair": True,
            "human_conversation": True,
            "hce_kind": "conversation_repair",
            "assistant_kind": "conversation_repair",
            "has_analysis": False,
            "show_header": False,
            "skip_llm": True,
            "repair_mode": True,
        },
        "match": None,
        "status": None,
        "is_live": False,
        "minute": None,
        "executive_summary": text,
        "best_markets": [],
        "confidence": {
            "score": 0.0,
            "label": "insufficient",
            "explanation": "Modo repair conversacional (correção humana).",
            "data_sources": ["ConversationRepair"],
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
        "final_recommendation": text,
        "aurora_version": "Copilot v1.0",
        "brain": brain,
        "response_metadata": {
            "mode": "conversation_repair",
            "source": "conversation_repair",
            "show_header": False,
        },
    }


def try_conversation_repair(
    message: str,
    ctx: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """
    If the user signals correction/frustration, return a repair payload.
    Otherwise None (pipeline continues — including GeneralAssistant).
    """
    try:
        if not is_repair_signal(message):
            return None
        text = _build_repair_reply(message, ctx)
        # Never ship the sticky GA template from this path
        if text.strip().startswith("Entendi. Posso te ajudar"):
            text = (
                "Acho que interpretei sua pergunta de forma errada.\n\n"
                "Pode reformular ou confirmar o que exatamente você queria saber?"
            )
        logger.warning(
            "[AUDIT] ConversationRepair: signal matched team=%r q=%r",
            get_repair_memory(ctx).get("last_team"),
            (get_repair_memory(ctx).get("last_user_question") or "")[:60],
        )
        try:
            from src.conversation.pipeline_trace import trace as _ptrace

            _ptrace(
                "ENGINE",
                engine="conversation_repair",
                kind="repair",
                fallback=False,
            )
        except Exception:
            pass
        return _payload(text)
    except Exception as exc:
        logger.warning("try_conversation_repair fail-open: %s", exc)
        return None
