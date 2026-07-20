"""
P3-D.2 Commitment Recovery MVP — exit empty-commitment collapse.

After hypothesis abandonment:
  1. At most ONE escape ask (budget).
  2. Then explicit uncommitted state (non-ask).
  3. Rebuild commitment from substantive user content (anti-reactivation intact).

Fail-open. Additive.
"""

from __future__ import annotations

import re
import time
import unicodedata
from typing import Any

CTX_KEY = "belief_state_mvp"

_UNCOMMITTED_REPLIES = (
    (
        "Sem hipótese ativa agora. Não vou te perguntar de novo — "
        "quando disser o foco em uma frase, eu sigo."
    ),
    (
        "Contexto de compromisso zerado. Continuo aqui; "
        "é só falar o assunto quando quiser."
    ),
    (
        "Fico em modo aberto, sem travar no fio antigo e sem checklist. "
        "Manda o próximo pedido quando estiver pronto."
    ),
    (
        "Não retenho a leitura anterior. Estou sem compromisso ativo — "
        "pode seguir direto no que importar."
    ),
    (
        "Hipótese antiga fora e sem nova ainda. "
        "Sem repetir pergunta: quando vier o foco, avanço."
    ),
)


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9à-ú]{3,}", _fold(text))}


def _jaccard(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _norm_goal(text: str) -> str:
    return _fold(text)[:160]


def _get_belief(ctx: dict[str, Any] | None) -> dict[str, Any]:
    from src.conversation.belief_revision import get_belief

    return get_belief(ctx)


def _bump(st: dict[str, Any], key: str) -> None:
    c = st.setdefault("counters", {})
    c[key] = int(c.get(key) or 0) + 1


def commitment_status(ctx: dict[str, Any] | None) -> str:
    return str(_get_belief(ctx).get("commitment_status") or "none")


def is_uncommitted(ctx: dict[str, Any] | None) -> bool:
    return commitment_status(ctx) in {"recovering", "uncommitted"}


def can_emit_escape(ctx: dict[str, Any] | None) -> bool:
    st = _get_belief(ctx)
    return (
        str(st.get("commitment_status") or "") == "recovering"
        and int(st.get("escape_budget") or 0) > 0
    )


def _enter_uncommitted(ctx: dict[str, Any], *, action: str = "uncommitted") -> None:
    st = _get_belief(ctx)
    st["commitment_status"] = "uncommitted"
    st["escape_budget"] = 0
    st["block_reanswer_template"] = False
    st["last_action"] = action
    st["updated_at"] = time.time()
    ctx[CTX_KEY] = st


def uncommitted_reply(ctx: dict[str, Any] | None = None) -> str:
    """Explicit no-commitment — non-ask, ends escape regime (P3-D.4 diversified)."""
    # P3-D.4 — anchors + fingerprint/speech-act-aware bank
    try:
        from src.conversation.response_diversification import diversify_recovery_line

        best = diversify_recovery_line(ctx)
    except Exception:
        best = _UNCOMMITTED_REPLIES[0]
        if isinstance(ctx, dict):
            st = _get_belief(ctx)
            c = st.setdefault("counters", {})
            idx = int(c.get("uncommitted_replies") or 0)
            c["uncommitted_replies"] = idx + 1
            recent = list(st.get("recent_escape_sigs") or [])
            best = _UNCOMMITTED_REPLIES[idx % len(_UNCOMMITTED_REPLIES)]
            best_score = 1.0
            for cand in _UNCOMMITTED_REPLIES:
                score = max((_jaccard(cand, r) for r in recent), default=0.0)
                if score < best_score:
                    best_score = score
                    best = cand
                    if score == 0.0:
                        break
            st["last_escape_sig"] = best[:200]
            recent.append(best[:200])
            st["recent_escape_sigs"] = recent[-8:]
    if isinstance(ctx, dict):
        st = _get_belief(ctx)
        c = st.setdefault("counters", {})
        c["uncommitted_replies"] = int(c.get("uncommitted_replies") or 0) + 1
        st["last_escape_sig"] = best[:200]
        recent = list(st.get("recent_escape_sigs") or [])
        recent.append(best[:200])
        st["recent_escape_sigs"] = recent[-8:]
        _enter_uncommitted(ctx, action="uncommitted")
    return best


def message_can_rebuild(message: str) -> bool:
    from src.conversation.belief_revision import contradiction_signals

    folded = _fold(message or "")
    if not folded:
        return False
    toks = [t for t in re.findall(r"[a-z0-9à-ú]{2,}", folded)]
    sig = contradiction_signals(message)
    content_toks = [
        t
        for t in toks
        if t
        not in {
            "nao",
            "não",
            "isso",
            "voce",
            "você",
            "entendeu",
            "errado",
            "para",
            "repetir",
            "preste",
            "atencao",
            "atenção",
            "aff",
            "ja",
            "já",
            "falei",
            "parece",
            "robo",
            "robô",
            "foi",
        }
    ]
    if sig["contradiction_score"] >= 0.4 and len(content_toks) < 2:
        return False
    if len(toks) >= 4 and len(content_toks) >= 2:
        return True
    if len(content_toks) >= 3:
        return True
    if any(
        x in folded
        for x in (
            "quero",
            "vamos",
            "falar",
            "sobre",
            "me ajuda",
            "desabaf",
            "flamengo",
            "palmeiras",
            "produtividade",
        )
    ) and len(content_toks) >= 2:
        return True
    return False


def try_rebuild_commitment(
    ctx: dict[str, Any] | None,
    message: str,
    *,
    hyp_type: str = "chat",
) -> dict[str, Any]:
    from src.conversation.belief_revision import set_hypothesis

    if not isinstance(ctx, dict):
        return {"rebuilt": False, "reason": "no_ctx"}
    st = _get_belief(ctx)
    if str(st.get("commitment_status") or "") not in {"recovering", "uncommitted"}:
        return {"rebuilt": False, "reason": "not_uncommitted"}
    if not message_can_rebuild(message):
        return {"rebuilt": False, "reason": "no_rebuild_signal"}
    before = list(st.get("abandoned_texts") or [])
    set_hypothesis(ctx, message, hyp_type=hyp_type, confidence=0.65, force=False)
    st = _get_belief(ctx)
    hyp = st.get("active_hypothesis")
    if isinstance(hyp, dict) and hyp.get("status") == "active":
        try:
            pcs = ctx.setdefault("perception_conversation_state", {})
            if isinstance(pcs, dict):
                pcs["current_goal"] = {
                    "text": str(hyp.get("text") or message)[:240],
                    "type": hyp_type,
                    "set_at": time.time(),
                }
        except Exception:
            pass
        _bump(st, "commitment_rebuilds")
        st["last_action"] = "rebuild"
        st["updated_at"] = time.time()
        ctx[CTX_KEY] = st
        return {"rebuilt": True, "reason": "ok", "text": hyp.get("text")}
    if st.get("last_action") == "reactivation_blocked" or any(
        _jaccard(_norm_goal(message), a) >= 0.9 for a in before
    ):
        return {"rebuilt": False, "reason": "reactivation_blocked"}
    return {"rebuilt": False, "reason": "set_failed"}


def recovery_reply(ctx: dict[str, Any] | None = None) -> str:
    """One escape ask max, then explicit uncommitted."""
    from src.conversation.belief_revision import abandon_open_reply

    if can_emit_escape(ctx):
        text = abandon_open_reply(ctx)
        st = _get_belief(ctx)
        st["escape_budget"] = 0
        _bump(st, "escape_emitted")
        st["last_escape_sig"] = text[:200]
        recent = list(st.get("recent_escape_sigs") or [])
        recent.append(text[:200])
        st["recent_escape_sigs"] = recent[-8:]
        st["commitment_status"] = "uncommitted"
        st["block_reanswer_template"] = False
        st["last_action"] = "abandon_acked"
        st["updated_at"] = time.time()
        if isinstance(ctx, dict):
            ctx[CTX_KEY] = st
        return text
    return uncommitted_reply(ctx)
