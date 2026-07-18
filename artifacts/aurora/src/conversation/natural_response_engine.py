"""
Natural Response Engine V2 — expression layer (perception, not understanding).

Additive. Fail-open.
Does NOT modify MasterIntentRouter / HCE / FactPolicy / LivePipeline / ContextIsolation.

Tone: professional analyst, lightly friendly. Controlled variability.
"""

from __future__ import annotations

import hashlib
import logging
import re
import unicodedata
from typing import Any

logger = logging.getLogger(__name__)

HISTORY_KEY = "nre_recent_replies"
HISTORY_MAX = 6

_ARTIFICIAL = re.compile(
    r"("
    r"o contexto atual|"
    r"com o contexto atual|"
    r"o [uú]til [eé]|o [uú]til agora|"
    r"o caminho honesto|"
    r"a leitura pede|"
    r"como chega|"
    r"o recorte recente|"
    r"Certo\. Estou aqui|"
    r"Pode falar comigo normalmente"
    r")",
    re.I,
)


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


def _pick(pool: list[str], ctx: dict[str, Any] | None, salt: str) -> str:
    """Controlled variation — avoid last few replies when possible."""
    if not pool:
        return ""
    hist = []
    if isinstance(ctx, dict):
        hist = [str(x).strip() for x in (ctx.get(HISTORY_KEY) or []) if x]

    # Prefer options not used recently
    fresh = [p for p in pool if p.strip() not in hist]
    choices = fresh or pool
    # Stable-ish pick from message salt + turn counter (not pure random chaos)
    turn = 0
    if isinstance(ctx, dict):
        turn = int(ctx.get("nre_turn") or 0)
        ctx["nre_turn"] = turn + 1
    digest = hashlib.md5(f"{salt}:{turn}:{len(hist)}".encode("utf-8")).hexdigest()
    idx = int(digest[:8], 16) % len(choices)
    return choices[idx]


def _remember(ctx: dict[str, Any] | None, text: str) -> None:
    if not isinstance(ctx, dict) or not text:
        return
    hist = list(ctx.get(HISTORY_KEY) or [])
    hist.append(text.strip()[:120])
    ctx[HISTORY_KEY] = hist[-HISTORY_MAX:]


# ── Social intent detection ───────────────────────────────────────────────

_ACK = re.compile(
    r"^(?:ok|okay|blz|beleza|show|perfeito|certo|combinado|fechou|entendi|"
    r"uhum|ahm|isso|pode|pode\s+ser|boa|que\s+bom|top|massa|suave|tranquilo|"
    r"kk+|haha+|rsrs+)\s*[!?.]*$",
    re.I,
)
_THANKS = re.compile(
    r"^(?:obrigad[oa]|valeu|vlw|thanks|thank\s+you|valeu\s+demais|"
    r"muito\s+obrigad[oa])\s*[!?.]*$",
    re.I,
)
_FAREWELL = re.compile(
    r"^(?:tchau|xau|flw|falou|ate\s+logo|até\s+logo|ate\s+mais|até\s+mais|"
    r"ate\s+amanha|até\s+amanhã|ate\s+a\s+proxima|até\s+a\s+próxima|"
    r"fui|me\s+cuido|tmj)\s*[!?.]*$",
    re.I,
)
_GOODNIGHT = re.compile(
    r"^(?:boa\s+noite)(?:\s+\w+){0,2}\s*[!?.]*$",
    re.I,
)
_GOODMORNING = re.compile(
    r"^(?:bom\s+dia)(?:\s+\w+){0,2}\s*[!?.]*$",
    re.I,
)
_GOODAFTERNOON = re.compile(
    r"^(?:boa\s+tarde)(?:\s+\w+){0,2}\s*[!?.]*$",
    re.I,
)
_LAUGH = re.compile(r"^(?:kk+|haha+|rsrs+|hehe+)\s*[!?.]*$", re.I)

_ACK_POOL = [
    "Perfeito.",
    "Show.",
    "Entendido.",
    "Boa.",
    "Combinado.",
    "Certo.",
    "Fechado.",
    "Ok.",
]
_ACK_WARM = [
    "Perfeito 👍",
    "Show.",
    "Boa.",
    "Combinado.",
    "Entendido.",
]
_THANKS_POOL = [
    "Disponha.",
    "Por nada.",
    "Imagina.",
    "Quando quiser.",
    "Tamo junto.",
]
_LAUGH_POOL = [
    "😄",
    "Haha.",
    "Boa 😄",
]
_FAREWELL_POOL = [
    "Até mais!",
    "Até a próxima.",
    "Falou — qualquer coisa é só chamar.",
    "Até logo.",
    "Quando quiser olhar um jogo, estou por aqui.",
]
_GOODNIGHT_POOL = [
    "Boa noite.",
    "Boa noite — até a próxima.",
    "Boa noite. Descanso aí.",
    "Boa noite. Quando quiser analisar algum jogo, estou por aqui.",
]
_GOODMORNING_POOL = [
    "Bom dia.",
    "Bom dia — em que posso ajudar?",
    "Bom dia. Se quiser olhar um jogo, é só falar.",
]
_GOODAFTERNOON_POOL = [
    "Boa tarde.",
    "Boa tarde — em que posso ajudar?",
    "Boa tarde. Pode mandar o jogo quando quiser.",
]


def classify_social_expression(message: str) -> str | None:
    folded = _fold(message)
    if not folded:
        return None
    if _LAUGH.match(folded):
        return "laugh"
    if _THANKS.match(folded):
        return "thanks"
    if _FAREWELL.match(folded):
        return "farewell"
    if _GOODNIGHT.match(folded):
        return "goodnight"
    if _GOODMORNING.match(folded):
        return "goodmorning"
    if _GOODAFTERNOON.match(folded):
        return "goodafternoon"
    if _ACK.match(folded):
        return "ack"
    return None


def scrub_artificial(text: str) -> str:
    t = text or ""
    if not _ARTIFICIAL.search(t):
        return t
    # Soften known robotic openers without inventing sport content
    t = re.sub(
        r"Certo\.\s*Estou aqui[^.]*\.\s*",
        "",
        t,
        flags=re.I,
    )
    t = re.sub(
        r"Pode falar comigo normalmente[^.]*\.\s*",
        "",
        t,
        flags=re.I,
    )
    t = re.sub(r"\bo [uú]til agora [eé]\b", "o foco agora é", t, flags=re.I)
    t = re.sub(r"\bo mais [uú]til agora [eé]\b", "o foco agora é", t, flags=re.I)
    t = re.sub(r"\bo contexto atual\b", "neste momento", t, flags=re.I)
    t = re.sub(r"\bo caminho honesto\b", "com cuidado", t, flags=re.I)
    t = re.sub(r"\ba leitura pede\b", "faz sentido olhar", t, flags=re.I)
    return re.sub(r"\s+", " ", t).strip() or t


def render_social(kind: str, message: str, ctx: dict[str, Any] | None) -> str:
    salt = f"{kind}:{_fold(message)}"
    if kind == "laugh":
        return _pick(_LAUGH_POOL, ctx, salt)
    if kind == "thanks":
        return _pick(_THANKS_POOL, ctx, salt)
    if kind == "farewell":
        return _pick(_FAREWELL_POOL, ctx, salt)
    if kind == "goodnight":
        return _pick(_GOODNIGHT_POOL, ctx, salt)
    if kind == "goodmorning":
        return _pick(_GOODMORNING_POOL, ctx, salt)
    if kind == "goodafternoon":
        return _pick(_GOODAFTERNOON_POOL, ctx, salt)
    if kind == "ack":
        # Mild warmth sometimes (emoji pool smaller)
        use_warm = (int(hashlib.md5(salt.encode()).hexdigest()[:2], 16) % 5) == 0
        pool = _ACK_WARM if use_warm else _ACK_POOL
        return _pick(pool, ctx, salt)
    return "Certo."


def _is_robotic_social_reply(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return True
    if _ARTIFICIAL.search(t):
        return True
    if t.startswith("Oi! Eu sou a Aurora"):
        return True
    if "Pode falar comigo normalmente" in t:
        return True
    if t.startswith("Certo. Estou aqui"):
        return True
    if t.startswith("Entendi. Posso te ajudar"):
        return True
    return False


def apply_natural_response(
    message: str,
    payload: dict[str, Any] | None,
    ctx: dict[str, Any] | None = None,
    *,
    force_social: bool = False,
) -> dict[str, Any] | None:
    """
    Expression pass over a conversational payload.
    Returns updated payload or original.
    """
    try:
        if not isinstance(payload, dict):
            return payload

        ents = dict(payload.get("entities") or {})
        # Phase 8.4-A.9 — never rewrite capabilities onboarding into small_talk
        if (
            ents.get("assistant_capabilities")
            or ents.get("assistant_kind") == "capabilities"
            or payload.get("intent") in {"assistant_capabilities", "capabilities"}
        ):
            return payload
        # Never rewrite sport analysis / markets / live numbers
        if ents.get("has_analysis") or payload.get("best_markets") or payload.get("match"):
            if not ents.get("human_conversation") and not ents.get("general_assistant"):
                return payload
        kind = classify_social_expression(message)
        text = str(payload.get("executive_summary") or "")
        hce_kind = str(ents.get("hce_kind") or "")

        # Continuity that must keep HCE wording (need fixture / bankroll confirm)
        if hce_kind in {
            "await_fixture",
            "short_await_fixture",
            "resume_await_fixture",
            "market_before_fixture",
            "memory_bankroll_pending",
            "memory_bankroll_saved",
            "memory_stake_guidance",
            "meta_question",
            "soft_followup",
            "conversation_repair",
        }:
            cleaned = scrub_artificial(text)
            if cleaned != text:
                payload = dict(payload)
                payload["executive_summary"] = cleaned
                payload["final_recommendation"] = cleaned
                ents["natural_response_v2"] = "scrub"
                payload["entities"] = ents
            return payload

        # Pure social expression — always prefer NRE over robotic / repeated sport ACKs
        if kind in {
            "ack",
            "thanks",
            "farewell",
            "goodnight",
            "goodmorning",
            "goodafternoon",
            "laugh",
        }:
            natural = render_social(kind, message, ctx)
            _remember(ctx, natural)
            payload = dict(payload)
            payload["executive_summary"] = natural
            payload["final_recommendation"] = natural
            ents["natural_response_v2"] = kind
            ents["show_header"] = False
            payload["entities"] = ents
            payload["intent"] = "small_talk"
            logger.warning("[AUDIT] NRE_v2: social kind=%s reply=%r", kind, natural[:80])
            return payload

        # Generic scrub for remaining conversational text
        cleaned = scrub_artificial(text)
        if cleaned != text:
            payload = dict(payload)
            payload["executive_summary"] = cleaned
            payload["final_recommendation"] = cleaned
            ents["natural_response_v2"] = "scrub"
            payload["entities"] = ents
        return payload
    except Exception as exc:
        logger.warning("apply_natural_response fail-open: %s", exc)
        return payload


def try_natural_social_payload(
    message: str,
    ctx: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """
    Short-circuit pure social expression when upstream would be robotic.
    Used as expression-first for ACK/farewell before weak GA/HCE short_loose sticks.
    """
    try:
        kind = classify_social_expression(message)
        if not kind:
            return None
        # Defer to HCE if there's an active expectation that needs short-answer resolve
        st = (ctx or {}).get("human_conversation_state") or {}
        expected = str(st.get("last_expected_action") or "")
        if expected in {"awaiting_fixture", "awaiting_bankroll_confirm"} and kind == "ack":
            return None
        if expected == "awaiting_fixture" and kind in {"ack"}:
            return None

        text = render_social(kind, message, ctx)
        _remember(ctx, text)
        try:
            from src.brain import get_brain_meta

            brain = get_brain_meta()
        except Exception:
            brain = {}
        logger.warning("[AUDIT] NRE_v2: direct social kind=%s", kind)
        return {
            "intent": "small_talk",
            "entities": {
                "natural_response_v2": kind,
                "general_assistant": True,
                "assistant_kind": "natural_social",
                "has_analysis": False,
                "show_header": False,
                "skip_llm": True,
            },
            "match": None,
            "is_live": False,
            "executive_summary": text,
            "final_recommendation": text,
            "best_markets": [],
            "confidence": {
                "score": 0.0,
                "label": "insufficient",
                "explanation": "Resposta social natural (NRE v2).",
                "data_sources": ["NaturalResponseEngineV2"],
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
            "brain": brain,
            "response_metadata": {
                "mode": "natural_response_v2",
                "source": kind,
                "show_header": False,
            },
        }
    except Exception as exc:
        logger.warning("try_natural_social_payload fail-open: %s", exc)
        return None
