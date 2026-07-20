"""
P3 Perception Conversation State — goal persistence for human perception.

Requested schema (current_goal, previous_goal, entities, frustration_level,
clarify_count, repair_count, state_streak).

Does NOT replace sports `conversation_state.py` (market/fixture memory).
Fail-open. Does not invent fixtures / odds / sports engine outputs.
"""

from __future__ import annotations

import logging
import re
import time
import unicodedata
from typing import Any

logger = logging.getLogger(__name__)

CTX_KEY = "perception_conversation_state"
TTL_SECONDS = 60 * 60

# Caps (user rules: >1 → assume / re-answer)
CLARIFY_CAP = 1
REPAIR_CAP = 1
STICKY_JACCARD = 0.88

_MENU_MARKERS = (
    "escolhe uma opção",
    "escolhe uma opcao",
    "analisar um confronto",
    "você está falando de",
    "voce esta falando de",
    "seleção / time",
    "selecao / time",
    "jogo específico",
    "jogo especifico",
    "em uma frase: você quer analisar",
    "em uma frase: voce quer analisar",
    "ainda não peguei o objetivo",
    "ainda nao peguei o objetivo",
)

_FRUST = re.compile(
    r"("
    r"voce\s+nao\s+entendeu|nao\s+entendeu|"
    r"para\s+de\s+repet|"
    r"preste\s+atencao|presta\s+atencao|"
    r"parece\s+um\s+robo|parece\s+um\s+robô|"
    r"isso\s+esta\s+errado|isso\s+está\s+errado|"
    r"ja\s+falei|já\s+falei|"
    r"voce\s+esta\s+me\s+frustr|"
    r"\baff+\b|"
    r"releia|"
    r"nao\s+foi\s+isso|"
    r"responde\s+direito"
    r")",
    re.I,
)


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9à-ú]{2,}", _fold(text))}


def jaccard(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def token_count(message: str | None) -> int:
    return len([w for w in re.findall(r"\S+", (message or "").strip())])


def is_short_message(message: str | None) -> bool:
    return token_count(message) <= 3 and bool((message or "").strip())


def is_frustration(message: str | None) -> bool:
    return bool(_FRUST.search(_fold(message or "")))


def looks_like_menu(text: str | None) -> bool:
    low = _fold(text or "")
    return any(m in low for m in _MENU_MARKERS)


def _empty_state() -> dict[str, Any]:
    return {
        "current_goal": None,
        "previous_goal": None,
        "entities": {},
        "frustration_level": 0.0,
        "clarify_count": 0,
        "repair_count": 0,
        "state_streak": 0,
        "last_state": None,
        "last_reply_sig": None,
        "last_user_message": None,
        "menus_disabled": False,
        "updated_at": time.time(),
        "counters": {
            "infer_short": 0,
            "assume_clarify": 0,
            "reanswer_repair": 0,
            "menu_blocked": 0,
            "sticky_blocked": 0,
            "clarify_expired": 0,
            "goal_set": 0,
        },
    }


def get_perception_state(ctx: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(ctx, dict):
        return _empty_state()
    st = ctx.get(CTX_KEY)
    if not isinstance(st, dict):
        st = _empty_state()
        ctx[CTX_KEY] = st
        return st
    ts = float(st.get("updated_at") or 0)
    if ts and (time.time() - ts) > TTL_SECONDS:
        st = _empty_state()
        ctx[CTX_KEY] = st
    for k, v in _empty_state().items():
        st.setdefault(k, v if not isinstance(v, dict) else dict(v))
    st.setdefault("counters", _empty_state()["counters"])
    return st


def _touch(st: dict[str, Any]) -> None:
    st["updated_at"] = time.time()


def _bump(st: dict[str, Any], key: str) -> None:
    c = st.setdefault("counters", {})
    c[key] = int(c.get(key) or 0) + 1


def set_goal(
    ctx: dict[str, Any] | None,
    goal: str | None,
    *,
    goal_type: str = "chat",
    entities: dict[str, Any] | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Persist conversational goal. Menus never become goals."""
    if not isinstance(ctx, dict):
        return _empty_state()
    st = get_perception_state(ctx)
    text = (goal or "").strip()
    if not text or looks_like_menu(text):
        return st
    # Don't overwrite a strong goal with a tiny ack unless forced
    if (
        not force
        and st.get("current_goal")
        and token_count(text) <= 3
        and goal_type in {"ack", "short"}
    ):
        return st
    prev = st.get("current_goal")
    if prev and prev != text:
        st["previous_goal"] = prev
    st["current_goal"] = {
        "text": text[:240],
        "type": goal_type,
        "set_at": time.time(),
    }
    if entities:
        ents = dict(st.get("entities") or {})
        ents.update({k: v for k, v in entities.items() if v is not None})
        st["entities"] = ents
    _bump(st, "goal_set")
    _touch(st)
    ctx[CTX_KEY] = st
    # P3-C.10 — sync single active hypothesis (no stacks)
    try:
        from src.conversation.belief_revision import set_hypothesis

        set_hypothesis(ctx, text, hyp_type=goal_type, confidence=0.70, force=force)
    except Exception:
        pass
    return st


def note_user_message(ctx: dict[str, Any] | None, message: str) -> dict[str, Any]:
    if not isinstance(ctx, dict):
        return _empty_state()
    st = get_perception_state(ctx)
    st["last_user_message"] = (message or "")[:240]
    if is_frustration(message):
        st["frustration_level"] = min(
            1.0, float(st.get("frustration_level") or 0) + 0.35
        )
        st["menus_disabled"] = True
    elif float(st.get("frustration_level") or 0) > 0:
        st["frustration_level"] = max(
            0.0, float(st.get("frustration_level") or 0) - 0.05
        )
    # P3-C.10 belief revision — contradiction / confidence / abandon
    belief_action = None
    try:
        from src.conversation.belief_revision import apply_user_turn

        belief_action = apply_user_turn(ctx, message)
    except Exception:
        belief_action = None

    # Short messages don't set a new goal — they inherit (unless belief abandoned)
    abandoned = bool(
        isinstance(belief_action, dict) and belief_action.get("action") == "abandon"
    )
    # P3-D.2 — try rebuild commitment while recovering/uncommitted
    rebuilt = False
    try:
        from src.conversation.commitment_recovery import (
            is_uncommitted,
            try_rebuild_commitment,
        )

        if is_uncommitted(ctx) and not abandoned:
            folded = _fold(message)
            gtype = "chat"
            if any(x in folded for x in ("torço", "torco", "time", "jogo", "flamengo", "palmeiras")):
                gtype = "sport_chat"
            if any(x in folded for x in ("ansioso", "triste", "desabafar", "eufor")):
                gtype = "emotion"
            if any(x in folded for x in ("conversar", "brainstorm", "me ajuda a pensar", "conta")):
                gtype = "casual"
            rb = try_rebuild_commitment(ctx, message, hyp_type=gtype)
            rebuilt = bool(isinstance(rb, dict) and rb.get("rebuilt"))
            if rebuilt:
                st = get_perception_state(ctx)
    except Exception:
        rebuilt = False

    if (
        not abandoned
        and not rebuilt
        and not is_short_message(message)
        and not is_frustration(message)
    ):
        folded = _fold(message)
        gtype = "chat"
        if any(x in folded for x in ("torço", "torco", "time", "jogo", "flamengo", "palmeiras")):
            gtype = "sport_chat"
        if any(x in folded for x in ("ansioso", "triste", "desabafar", "eufor")):
            gtype = "emotion"
        if any(x in folded for x in ("conversar", "brainstorm", "me ajuda a pensar", "conta")):
            gtype = "casual"
        set_goal(ctx, message, goal_type=gtype)
        st = get_perception_state(ctx)
    elif abandoned:
        st = get_perception_state(ctx)
        st["current_goal"] = None
    _touch(st)
    ctx[CTX_KEY] = st
    return st


def note_state(ctx: dict[str, Any] | None, state_name: str) -> dict[str, Any]:
    if not isinstance(ctx, dict):
        return _empty_state()
    st = get_perception_state(ctx)
    last = st.get("last_state")
    if last == state_name:
        st["state_streak"] = int(st.get("state_streak") or 0) + 1
    else:
        st["state_streak"] = 1
        st["last_state"] = state_name
    if state_name in {"CLARIFICATION", "UNKNOWN"}:
        st["clarify_count"] = int(st.get("clarify_count") or 0) + 1
    if state_name == "REPAIR":
        st["repair_count"] = int(st.get("repair_count") or 0) + 1
    if state_name not in {"CLARIFICATION", "UNKNOWN", "REPAIR"}:
        # progress — decay caps
        if state_name in {"SMALL_TALK", "IDENTITY", "SPORT", "ANSWER"}:
            st["clarify_count"] = 0
            if state_name != "REPAIR":
                st["repair_count"] = max(0, int(st.get("repair_count") or 0) - 1)
            if float(st.get("frustration_level") or 0) < 0.4:
                st["menus_disabled"] = False
    _touch(st)
    ctx[CTX_KEY] = st
    return st


def menus_disabled(ctx: dict[str, Any] | None) -> bool:
    st = get_perception_state(ctx)
    return bool(st.get("menus_disabled") or float(st.get("frustration_level") or 0) >= 0.35)


def should_assume_after_clarify(ctx: dict[str, Any] | None) -> bool:
    return int(get_perception_state(ctx).get("clarify_count") or 0) > CLARIFY_CAP


def should_reanswer_after_repair(ctx: dict[str, Any] | None) -> bool:
    return int(get_perception_state(ctx).get("repair_count") or 0) > REPAIR_CAP


def clarify_or_unknown_expired(ctx: dict[str, Any] | None) -> bool:
    st = get_perception_state(ctx)
    return (
        int(st.get("clarify_count") or 0) > CLARIFY_CAP
        or (st.get("last_state") in {"CLARIFICATION", "UNKNOWN"} and int(st.get("state_streak") or 0) >= 2)
    )


def current_goal_text(ctx: dict[str, Any] | None) -> str | None:
    # P3-C.10: commitment only while soft-assume allowed; never resurrect abandoned
    try:
        from src.conversation.belief_revision import (
            allow_soft_assume,
            get_belief,
            should_use_abandon_reply,
        )

        bel = get_belief(ctx)
        hyp = bel.get("active_hypothesis")
        if should_use_abandon_reply(ctx):
            return None
        if isinstance(hyp, dict):
            # Active belief exists — gate on confidence / block / status
            if not allow_soft_assume(ctx):
                return None
        else:
            la = str(bel.get("last_action") or "")
            if bel.get("block_reanswer_template") or la == "abandon" or la.startswith(
                "abandon:"
            ):
                return None
    except Exception:
        pass
    st = get_perception_state(ctx)
    g = st.get("current_goal")
    if isinstance(g, dict):
        t = g.get("text")
        return str(t) if t else None
    if isinstance(g, str) and g.strip():
        return g.strip()
    return None


def goal_type(ctx: dict[str, Any] | None) -> str:
    st = get_perception_state(ctx)
    g = st.get("current_goal")
    if isinstance(g, dict):
        return str(g.get("type") or "chat")
    return "chat"


def build_goal_answer(
    ctx: dict[str, Any] | None,
    *,
    reason: str = "assume",
) -> str:
    """Contentful reply from persisted goal — never a sports triage menu."""
    # P3-C.10 / P3-D.2 — abandoned / uncommitted → recovery (not infinite escape)
    try:
        from src.conversation.belief_revision import (
            allow_soft_assume,
            should_use_abandon_reply,
        )
        from src.conversation.commitment_recovery import recovery_reply

        if should_use_abandon_reply(ctx):
            return recovery_reply(ctx)
        if reason in {"repair_reanswer", "assume"} and not allow_soft_assume(ctx):
            if current_goal_text(ctx) is None:
                return recovery_reply(ctx)
    except Exception:
        pass

    goal = current_goal_text(ctx)
    if not goal:
        try:
            from src.conversation.commitment_recovery import recovery_reply

            return recovery_reply(ctx)
        except Exception:
            return (
                "Me diga em uma frase o que você quer agora — sem lista de opções."
            )

    gtype = goal_type(ctx)
    st = get_perception_state(ctx)
    ents = dict(st.get("entities") or {})
    team = ents.get("team")
    # Rotate phrasing so soft-assume does not Jaccard-lock
    n = int(st.get("goal_answer_n") or 0)
    st["goal_answer_n"] = n + 1
    _touch(st)
    if isinstance(ctx, dict):
        ctx[CTX_KEY] = st

    heads_repair = (
        "Sem rodeio — retomando direto.",
        "Ok, vou responder sem repetir o mesmo bloco.",
        "Retomo o ponto, com outro ângulo.",
    )
    heads_short = (
        "Seguindo do ponto anterior.",
        "Continuando de onde paramos.",
        "Pegando o fio curto da última fala.",
    )
    heads_assume = (
        "Vou assumir o fio da conversa pra gente avançar.",
        "Seguindo com o que parece ser o pedido.",
        "Avançando no assunto sem menu.",
        "Mantendo continuidade, sem travar no template.",
    )
    if reason == "repair_reanswer":
        head = heads_repair[n % len(heads_repair)]
    elif reason == "short_infer":
        head = heads_short[n % len(heads_short)]
    else:
        head = heads_assume[n % len(heads_assume)]

    gshort = goal[:120]
    gmed = goal[:140]

    if gtype == "emotion":
        variants = (
            f"{head}\n\nSobre “{gshort}”: estou contigo nisso. "
            "Pode desabafar ou me dizer o que te ajudaria agora — "
            "sem eu te jogar num menu de opções.",
            f"{head}\n\nSobre esse sentimento (“{gshort[:80]}”): fico no assunto com você. "
            "Quer desabafo livre ou um próximo passo concreto?",
            f"{head}\n\nNão vou te empurrar opções. Em cima de “{gshort[:80]}”, "
            "me diga se prefere escuta ou sugestão prática.",
        )
        body = variants[n % len(variants)]
    elif gtype == "sport_chat" and team:
        variants = (
            f"{head}\n\nVoltando ao {team}: opinião de torcida/leitura leve, "
            f"sem inventar placar nem odd. Prioridade sobre o {team}: forma, rivalidade ou papo?",
            f"{head}\n\nNo {team} eu sigo em modo conversa (sem número inventado). "
            "Quer foco em momento do time, clássico ou só sensação?",
            f"{head}\n\nFalando do {team} sem menu: te respondo direto. "
            "O que puxar agora — forma recente, rival ou vibe?",
        )
        body = variants[n % len(variants)]
    elif gtype == "sport_chat":
        variants = (
            f"{head}\n\nContinuando: “{gshort}”. "
            "Conversa esportiva — opinião e contexto, sem inventar número. "
            "Foco: time, clássico ou sensação?",
            f"{head}\n\nNo fio “{gshort[:80]}” respondo em papo de esporte, "
            "sem placar/odd inventados. O que você quer priorizar?",
            f"{head}\n\nSigo em “{gshort[:80]}” sem checklist. "
            "Me diga só o recorte (time / jogo / feeling).",
        )
        body = variants[n % len(variants)]
    elif gtype == "casual":
        variants = (
            f"{head}\n\nOk — “{gshort}”. Vamos por partes, de forma direta. "
            "Quer 3 caminhos curtos ou que eu escolha um e aprofunde?",
            f"{head}\n\nPegando “{gshort[:80]}”: posso ir direto ao ponto "
            "ou listar duas alternativas curtas — o que prefere?",
            f"{head}\n\nSobre “{gshort[:80]}”, avanço sem menu. "
            "Quer que eu proponha um caminho e aprofunde?",
        )
        body = variants[n % len(variants)]
    else:
        variants = (
            f"{head}\n\nEntendi que o pedido era: “{gmed}”. "
            "Vou responder em cima disso. Se não for exatamente, me corrige em uma frase "
            "— sem lista de opções.",
            f"{head}\n\nTrato “{gmed}” como o alvo. "
            "Resposta direta; se errei o enquadro, corrige em uma linha.",
            f"{head}\n\nAssunto: “{gmed}”. "
            "Sigo nisso agora. Se mudou, diga o novo foco sem checklist.",
        )
        body = variants[n % len(variants)]
    return body


def strip_menus(text: str) -> str:
    """If a template still looks like a menu, replace with safe non-menu line."""
    if not looks_like_menu(text):
        return text
    return (
        "Prefiro avançar sem menu. Me diga em uma frase o que você quer "
        "continuar — eu sigo o fio da conversa."
    )


def anti_sticky_reply(
    ctx: dict[str, Any] | None,
    text: str,
) -> str:
    if not isinstance(ctx, dict):
        return strip_menus(text)
    st = get_perception_state(ctx)
    prev = st.get("last_reply_sig")
    cleaned = strip_menus(text)
    if prev and jaccard(str(prev), cleaned) >= STICKY_JACCARD:
        _bump(st, "sticky_blocked")
        goal = current_goal_text(ctx)
        cleaned = build_goal_answer(ctx, reason="assume")
        if goal and goal[:40] in _fold(str(prev)):
            cleaned = (
                "Mudando o ângulo pra não repetir.\n\n"
                + cleaned
            )
    # P3-C.10 — belief Jaccard guard + abandon rewrite
    try:
        from src.conversation.belief_revision import guard_reply_text

        cleaned = guard_reply_text(ctx, cleaned)
    except Exception:
        pass
    # P3-D.4 — fingerprint / speech-act cooldown + sport suppress
    try:
        from src.conversation.response_diversification import diversify_reply

        cleaned = diversify_reply(ctx, cleaned)
    except Exception:
        pass
    st["last_reply_sig"] = cleaned[:200]
    _touch(st)
    ctx[CTX_KEY] = st
    return cleaned


def stamp_entities(payload: dict[str, Any] | None, ctx: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return payload
    try:
        st = get_perception_state(ctx)
        ents = dict(payload.get("entities") or {})
        ents["perception_state"] = {
            "clarify_count": st.get("clarify_count"),
            "repair_count": st.get("repair_count"),
            "frustration_level": st.get("frustration_level"),
            "menus_disabled": st.get("menus_disabled"),
            "has_goal": bool(st.get("current_goal")),
            "state_streak": st.get("state_streak"),
            "counters": dict(st.get("counters") or {}),
        }
        payload["entities"] = ents
    except Exception:
        pass
    try:
        from src.conversation.belief_revision import stamp_belief

        stamp_belief(payload, ctx)
    except Exception:
        pass
    return payload
