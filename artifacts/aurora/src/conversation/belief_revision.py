"""
P3-C.10 Belief Revision MVP + P3-D.2 Commitment Recovery hooks.

Implements:
  1. Hypothesis confidence
  2. Contradiction signals
  3. Hypothesis abandonment
  4. Anti-reactivation
  5. Jaccard repetition guard
  6. Commitment recovery (escape budget + uncommitted) via commitment_recovery.py

Does NOT: multi-hypothesis stacks, advanced decay, new memories,
sports engines, personality changes.

Fail-open. Additive.
"""

from __future__ import annotations

import logging
import re
import time
import unicodedata
import uuid
from typing import Any

logger = logging.getLogger(__name__)

CTX_KEY = "belief_state_mvp"
ABANDON_CONF = 0.20
CHALLENGE_SCORE = 0.25
ABANDON_SCORE = 0.55
JACCARD_BAN = 0.85

_HARD_NEG = re.compile(
    r"("
    r"nao\s+foi\s+isso|não\s+foi\s+isso|"
    r"nao\s+(?:e|é)\s+isso|não\s+(?:e|é)\s+isso|"
    r"voce\s+nao\s+entendeu|você\s+não\s+entendeu|"
    r"isso\s+esta\s+errado|isso\s+está\s+errado|"
    r"interpretou\s+errado"
    r")",
    re.I,
)
_LOOP = re.compile(
    r"("
    r"para\s+de\s+repet|"
    r"parece\s+um\s+robo|parece\s+um\s+robô|"
    r"voce\s+esta\s+em\s+loop|"
    r"ja\s+falei|já\s+falei"
    r")",
    re.I,
)
_ATTN = re.compile(
    r"(preste\s+atencao|preste\s+atenção|releia|\baff+\b)",
    re.I,
)
_CORR = re.compile(
    r"("
    r"corrigindo|errai|na\s+verdade|ignore\s+o\s+anterior|"
    r"nao,\s+eu\s+quis|não,\s+eu\s+quis|"
    r"era\s+o\s+outro|troca\s+pro|esquece|deixa\s+pra\s+la|deixa\s+pra\s+lá|"
    r"outro\s+assunto|zera"
    r")",
    re.I,
)


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9à-ú]{3,}", _fold(text))}


def jaccard(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _empty() -> dict[str, Any]:
    return {
        "active_hypothesis": None,
        "abandoned_ids": [],
        "abandoned_texts": [],
        "block_reanswer_template": False,
        "last_action": None,
        # P3-D.2 commitment recovery
        "commitment_status": "none",  # none|committed|recovering|uncommitted
        "escape_budget": 0,
        "counters": {
            "contradiction_hits": 0,
            "abandons": 0,
            "confidence_updates": 0,
            "jaccard_blocks": 0,
            "reactivation_blocked": 0,
            "escape_emitted": 0,
            "uncommitted_replies": 0,
            "commitment_rebuilds": 0,
        },
        "updated_at": time.time(),
    }


def get_belief(ctx: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(ctx, dict):
        return _empty()
    st = ctx.get(CTX_KEY)
    if not isinstance(st, dict):
        st = _empty()
        ctx[CTX_KEY] = st
    for k, v in _empty().items():
        st.setdefault(k, v if not isinstance(v, dict) else dict(v))
    st.setdefault("counters", _empty()["counters"])
    return st


def _bump(st: dict[str, Any], key: str) -> None:
    c = st.setdefault("counters", {})
    c[key] = int(c.get(key) or 0) + 1


def _norm_goal(text: str) -> str:
    return _fold(text)[:160]


def contradiction_signals(message: str) -> dict[str, Any]:
    """Return matched classes + contradiction_score 0..1."""
    folded = _fold(message)
    classes: list[str] = []
    score = 0.0
    if _HARD_NEG.search(folded):
        classes.append("HARD_NEGATION")
        score += 0.45
    if _LOOP.search(folded):
        classes.append("LOOP_COMPLAINT")
        score += 0.40
    if _ATTN.search(folded):
        classes.append("ATTENTION_DEMAND")
        score += 0.25
    if _CORR.search(folded):
        classes.append("EXPLICIT_CORRECTION")
        score += 0.55
    # soft bare nao after context handled by caller weight
    if folded in {"nao", "não", "no"}:
        classes.append("SOFT_MISMATCH")
        score += 0.15
    score = min(1.0, score)
    return {"classes": classes, "contradiction_score": round(score, 3)}


def _new_hyp(text: str, *, hyp_type: str = "chat", confidence: float = 0.70) -> dict[str, Any]:
    return {
        "id": uuid.uuid4().hex[:12],
        "text": (text or "")[:240],
        "type": hyp_type,
        "confidence": max(0.0, min(0.95, float(confidence))),
        "status": "active",
        "same_answer_streak": 0,
        "last_answer_sig": None,
        "created_at": time.time(),
        "updated_at": time.time(),
    }


def set_hypothesis(
    ctx: dict[str, Any] | None,
    text: str | None,
    *,
    hyp_type: str = "chat",
    confidence: float = 0.70,
    force: bool = False,
) -> dict[str, Any]:
    """Set/replace active hypothesis. Anti-reactivation of abandoned texts."""
    if not isinstance(ctx, dict):
        return _empty()
    st = get_belief(ctx)
    raw = (text or "").strip()
    if not raw:
        return st
    norm = _norm_goal(raw)
    abandoned_texts = [_fold(x) for x in (st.get("abandoned_texts") or [])]
    abandoned_ids = list(st.get("abandoned_ids") or [])

    active = st.get("active_hypothesis")
    if isinstance(active, dict) and active.get("status") == "active":
        # Same hypothesis — keep, maybe bump confidence slightly if force affirm
        if _norm_goal(str(active.get("text") or "")) == norm and not force:
            return st

    # Anti-reactivation: blocked unless force AND clearly new wording
    if norm in abandoned_texts and not force:
        _bump(st, "reactivation_blocked")
        st["last_action"] = "reactivation_blocked"
        st["updated_at"] = time.time()
        ctx[CTX_KEY] = st
        return st
    if any(jaccard(norm, a) >= 0.9 for a in abandoned_texts) and not force:
        _bump(st, "reactivation_blocked")
        st["last_action"] = "reactivation_blocked"
        st["updated_at"] = time.time()
        ctx[CTX_KEY] = st
        return st

    st["active_hypothesis"] = _new_hyp(raw, hyp_type=hyp_type, confidence=confidence)
    st["block_reanswer_template"] = False
    st["commitment_status"] = "committed"
    st["escape_budget"] = 0
    st["last_action"] = "set"
    st["updated_at"] = time.time()
    ctx[CTX_KEY] = st
    return st


def abandon_hypothesis(ctx: dict[str, Any] | None, *, reason: str = "escape") -> dict[str, Any]:
    if not isinstance(ctx, dict):
        return _empty()
    st = get_belief(ctx)
    active = st.get("active_hypothesis")
    if isinstance(active, dict) and active.get("id"):
        active["status"] = "abandoned"
        active["updated_at"] = time.time()
        ids = list(st.get("abandoned_ids") or [])
        texts = list(st.get("abandoned_texts") or [])
        hid = str(active.get("id"))
        if hid not in ids:
            ids.append(hid)
        nt = _norm_goal(str(active.get("text") or ""))
        if nt and nt not in texts:
            texts.append(nt)
        st["abandoned_ids"] = ids[-20:]
        st["abandoned_texts"] = texts[-20:]
        _bump(st, "abandons")
    st["active_hypothesis"] = None
    st["block_reanswer_template"] = True
    # P3-D.2 — enter recovery: at most one escape ask, then uncommitted
    st["commitment_status"] = "recovering"
    st["escape_budget"] = 1
    st["last_action"] = f"abandon:{reason}"
    st["updated_at"] = time.time()
    ctx[CTX_KEY] = st
    try:
        pcs = ctx.get("perception_conversation_state")
        if isinstance(pcs, dict):
            prev = pcs.get("current_goal")
            if prev:
                pcs["previous_goal"] = prev
            pcs["current_goal"] = None
            pcs["menus_disabled"] = True
    except Exception:
        pass
    return st


def apply_user_turn(ctx: dict[str, Any] | None, message: str) -> dict[str, Any]:
    """
    Update confidence / abandon based on contradiction signals.
    Call once per user message (fail-open).
    """
    if not isinstance(ctx, dict):
        return {"action": "noop", "contradiction_score": 0.0, "classes": []}
    st = get_belief(ctx)
    sig = contradiction_signals(message)
    score = float(sig["contradiction_score"])
    classes = list(sig["classes"])
    active = st.get("active_hypothesis")

    if score >= CHALLENGE_SCORE:
        _bump(st, "contradiction_hits")

    if not isinstance(active, dict) or active.get("status") != "active":
        st["updated_at"] = time.time()
        ctx[CTX_KEY] = st
        return {
            "action": "no_active",
            "contradiction_score": score,
            "classes": classes,
            "confidence": None,
        }

    conf = float(active.get("confidence") or 0.5)
    if score > 0:
        conf -= 0.50 * score
        if "LOOP_COMPLAINT" in classes:
            conf -= 0.12
            st["block_reanswer_template"] = True
        if "HARD_NEGATION" in classes or "EXPLICIT_CORRECTION" in classes:
            conf = min(conf, 0.35)
            st["block_reanswer_template"] = True
        _bump(st, "confidence_updates")

    conf = max(0.0, min(0.95, conf))
    active["confidence"] = round(conf, 3)
    # Keep status=active until abandon so soft-assume gates on confidence only.
    if score >= CHALLENGE_SCORE and conf < 0.45:
        active["status"] = "challenged"
    elif conf < 0.45:
        active["status"] = "weakened"
    else:
        active["status"] = "active"
    active["updated_at"] = time.time()
    st["active_hypothesis"] = active

    hard = "HARD_NEGATION" in classes or "EXPLICIT_CORRECTION" in classes
    loop_stuck = "LOOP_COMPLAINT" in classes and int(active.get("same_answer_streak") or 0) >= 2
    must_abandon = (
        hard
        or score >= ABANDON_SCORE
        or conf < ABANDON_CONF
        or loop_stuck
    )

    action = "continue"
    if must_abandon:
        reason = "correction" if "EXPLICIT_CORRECTION" in classes else (
            "contradiction" if (hard or score >= ABANDON_SCORE) else "low_confidence"
        )
        abandon_hypothesis(ctx, reason=reason)
        st = get_belief(ctx)
        action = "abandon"
    elif score >= CHALLENGE_SCORE:
        st["block_reanswer_template"] = True
        st["last_action"] = "challenge"
        st["updated_at"] = time.time()
        ctx[CTX_KEY] = st
        return {
            "action": "challenge",
            "contradiction_score": score,
            "classes": classes,
            "confidence": conf,
        }

    st["last_action"] = action
    st["updated_at"] = time.time()
    ctx[CTX_KEY] = st
    return {
        "action": action,
        "contradiction_score": score,
        "classes": classes,
        "confidence": (st.get("active_hypothesis") or {}).get("confidence")
        if action != "abandon"
        else 0.0,
    }


_ABANDON_REPLIES = (
    (
        "Ok — soltei aquela leitura. Não vou insistir nela.\n\n"
        "Me diga em uma frase o que você quer agora (sem lista de opções)."
    ),
    (
        "Certo, abandonei o fio anterior.\n\n"
        "O que você quer de fato agora? Uma frase basta."
    ),
    (
        "Tudo bem — não vou repetir a mesma resposta.\n\n"
        "Recomece do zero: o que você precisa?"
    ),
    (
        "Desculpa a insistência. Hipótese antiga fora.\n\n"
        "Fala o próximo pedido em uma frase, sem menu."
    ),
    (
        "Parei. Sem travar no mesmo ponto.\n\n"
        "Me diga só o foco atual."
    ),
    (
        "Beleza — reset limpo da interpretação.\n\n"
        "Qual é o assunto novo?"
    ),
    (
        "Entendi a correção. Não retomo o chute anterior.\n\n"
        "Manda o pedido atual, direto."
    ),
    (
        "Saí do modo insistente.\n\n"
        "Quer continuar sobre outra coisa — diga qual."
    ),
    (
        "Aquela hipótese morreu aqui.\n\n"
        "Reformule o que você precisa em uma linha."
    ),
    (
        "Sem reabrir o mesmo enquadro.\n\n"
        "Qual é a próxima coisa que eu devo fazer por você?"
    ),
)


def abandon_open_reply(ctx: dict[str, Any] | None = None) -> str:
    """Non-menu escape line after abandonment — picks low-Jaccard variant."""
    if not isinstance(ctx, dict):
        return _ABANDON_REPLIES[0]
    st = get_belief(ctx)
    c = st.setdefault("counters", {})
    idx = int(c.get("abandon_replies") or 0)
    c["abandon_replies"] = idx + 1
    recent = list(st.get("recent_escape_sigs") or [])
    best = _ABANDON_REPLIES[idx % len(_ABANDON_REPLIES)]
    best_score = 1.0
    for cand in _ABANDON_REPLIES:
        score = max((jaccard(cand, r) for r in recent), default=0.0)
        if score < best_score:
            best_score = score
            best = cand
            if score == 0.0:
                break
    st["updated_at"] = time.time()
    ctx[CTX_KEY] = st
    return best


def should_use_abandon_reply(ctx: dict[str, Any] | None) -> bool:
    """True when soft-assume must yield to recovery / uncommitted path."""
    st = get_belief(ctx)
    la = str(st.get("last_action") or "")
    if la == "abandon" or la.startswith("abandon:"):
        return True
    if la == "challenge":
        return True
    # P3-D.2 — recovering/uncommitted without active hyp
    if str(st.get("commitment_status") or "") in {"recovering", "uncommitted"}:
        hyp = st.get("active_hypothesis")
        if not (isinstance(hyp, dict) and hyp.get("status") == "active"):
            return True
    active = st.get("active_hypothesis")
    return active is None and bool(st.get("block_reanswer_template"))


def active_confidence(ctx: dict[str, Any] | None) -> float | None:
    hyp = get_belief(ctx).get("active_hypothesis")
    if isinstance(hyp, dict) and hyp.get("status") == "active":
        return float(hyp.get("confidence") or 0)
    return None


def allow_soft_assume(ctx: dict[str, Any] | None) -> bool:
    """Soft assume only if active hyp exists with enough confidence and not blocked."""
    st = get_belief(ctx)
    if str(st.get("commitment_status") or "") in {"recovering", "uncommitted"}:
        return False
    if st.get("block_reanswer_template"):
        return False
    la = str(st.get("last_action") or "")
    if la == "abandon" or la.startswith("abandon:") or la == "challenge":
        return False
    hyp = st.get("active_hypothesis")
    if not isinstance(hyp, dict):
        return False
    if hyp.get("status") not in {"active"}:
        return False
    return float(hyp.get("confidence") or 0) >= 0.45


def guard_reply_text(ctx: dict[str, Any] | None, text: str) -> str:
    """
    Jaccard repetition guard + commitment-recovery rewrite (P3-D.2).
    """
    if not isinstance(ctx, dict):
        return text
    st = get_belief(ctx)
    cleaned = text or ""
    fold = _fold(cleaned)

    def _looks_recovery(f: str) -> bool:
        return any(
            k in f
            for k in (
                "soltei",
                "abandonei",
                "hipótese antiga",
                "hipotese antiga",
                "reset limpo",
                "modo insistente",
                "sem reabrir",
                "sem hipótese ativa",
                "sem hipotese ativa",
                "compromisso zerado",
                "modo aberto",
                "sem compromisso ativo",
                "sem compromisso preso",
                "sem nova ainda",
                "nao vou te perguntar de novo",
                "não vou te perguntar de novo",
                "sem repetir pergunta",
                "zerei o enquadro",
                "estado limpo",
                "ancorando no que voce",
                "ancorando no que você",
                "pegando o fio de",
                "mudando o formato",
                "sem template preso",
                "espaco aberto pra recomecar",
                "espaço aberto pra recomeçar",
            )
        )

    # P3-D.2 — recovering/uncommitted: one escape max, then explicit uncommitted
    if should_use_abandon_reply(ctx) and not allow_soft_assume(ctx):
        if _looks_recovery(fold):
            # Caller already emitted recovery line — don't spend budget twice
            return cleaned
        try:
            from src.conversation.commitment_recovery import recovery_reply

            return recovery_reply(ctx)
        except Exception:
            cleaned = abandon_open_reply(ctx)
            st["last_action"] = "abandon_acked"
            st["commitment_status"] = "uncommitted"
            st["escape_budget"] = 0
            st["block_reanswer_template"] = False
            ctx[CTX_KEY] = st
            return cleaned

    hyp = st.get("active_hypothesis")
    if not isinstance(hyp, dict):
        if str(st.get("commitment_status") or "") in {"recovering", "uncommitted"} or st.get(
            "last_action"
        ) in {"abandon_acked", "uncommitted"}:
            if _looks_recovery(fold):
                return cleaned
            try:
                from src.conversation.commitment_recovery import recovery_reply

                return recovery_reply(ctx)
            except Exception:
                return cleaned
        return cleaned

    prev = hyp.get("last_answer_sig")
    if prev and jaccard(str(prev), cleaned) >= JACCARD_BAN:
        _bump(st, "jaccard_blocks")
        st["block_reanswer_template"] = True
        hyp["same_answer_streak"] = int(hyp.get("same_answer_streak") or 0) + 1
        hyp["confidence"] = round(
            max(0.0, float(hyp.get("confidence") or 0.5) - 0.15), 3
        )
        if hyp["same_answer_streak"] >= 3 or float(hyp["confidence"]) < ABANDON_CONF:
            abandon_hypothesis(ctx, reason="jaccard_streak")
            try:
                from src.conversation.commitment_recovery import recovery_reply

                return recovery_reply(ctx)
            except Exception:
                return abandon_open_reply(ctx)
        try:
            from src.conversation.commitment_recovery import recovery_reply

            return (
                "Mudando de fato o caminho — sem repetir o mesmo texto.\n\n"
                + recovery_reply(ctx)
            )
        except Exception:
            return abandon_open_reply(ctx)

    hyp["same_answer_streak"] = 0
    hyp["last_answer_sig"] = cleaned[:200]
    hyp["updated_at"] = time.time()
    st["active_hypothesis"] = hyp
    st["updated_at"] = time.time()
    ctx[CTX_KEY] = st
    return cleaned


def stamp_belief(payload: dict[str, Any] | None, ctx: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return payload
    try:
        st = get_belief(ctx)
        hyp = st.get("active_hypothesis")
        ents = dict(payload.get("entities") or {})
        ents["belief_mvp"] = {
            "has_active": isinstance(hyp, dict) and hyp.get("status") == "active",
            "confidence": (hyp or {}).get("confidence") if isinstance(hyp, dict) else None,
            "status": (hyp or {}).get("status") if isinstance(hyp, dict) else None,
            "last_action": st.get("last_action"),
            "block_reanswer": bool(st.get("block_reanswer_template")),
            "commitment_status": st.get("commitment_status"),
            "escape_budget": st.get("escape_budget"),
            "counters": dict(st.get("counters") or {}),
        }
        payload["entities"] = ents
    except Exception:
        pass
    return payload
