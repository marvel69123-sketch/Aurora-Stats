"""
Aurora Brain Activation — Deep Thinking Decision Engine + tight Response Review.

DeepThinking CONTROLS NeedWeb, depth, response_mode, inference — not just logs.
Review only enriches on strong template evidence.

Fail-open. Additive. Does NOT edit frozen Reasoner/CIL/CRL modules.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any, Literal

logger = logging.getLogger(__name__)

Depth = Literal["simple", "medium", "deep"]
ResponseMode = Literal["brief", "normal", "detailed"]
WebNeed = Literal["none", "optional", "required"]

_STRONG_TEMPLATE = [
    re.compile(r"\bposso ajudar com\b", re.I),
    re.compile(r"\bo que posso fazer\b", re.I),
    re.compile(r"\bdigite um confronto\b", re.I),
    re.compile(r"\bn[aã]o entendi\b", re.I),
    re.compile(r"^\?\s*$"),
]


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


def run_deep_thinking_engine(
    message: str,
    ctx: dict[str, Any] | None = None,
    *,
    recovery: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Decision engine. Output drives NeedWeb / draft depth / review gates.
    """
    decision: dict[str, Any] = {
        "user_real_want": "ainda ambíguo",
        "needs_web": False,
        "web_need": "none",  # none | optional | required
        "depth": "medium",
        "response_mode": "normal",
        "needs_context_completion": False,
        "needs_inference": False,
        "surface_risk": 0.0,
        "topic_team": None,
        "topic_kind": None,  # opinion | moment | outlook | calendar | historical | emotional | other
        "questions": [
            "O que o usuário realmente quer?",
            "Existe contexto implícito?",
            "Posso inferir algo?",
            "Preciso WEB?",
            "Minha resposta parece automática?",
        ],
    }
    try:
        recovery = recovery or ((ctx or {}).get("context_recovery") or {})
        goal = recovery.get("inferred_goal")
        teams = list(recovery.get("teams") or [])
        temporal = recovery.get("temporal")
        folded = _fold(message)
        conf = float(recovery.get("confidence") or 0)

        # ── Classify want ──────────────────────────────────────────────
        if any(x in folded for x in ("orgulho", "obrigad", "ajuda muito", "melhor criacao", "maior criacao")):
            decision.update(
                {
                    "user_real_want": "conexão emocional",
                    "topic_kind": "emotional",
                    "web_need": "none",
                    "needs_web": False,
                    "depth": "simple",
                    "response_mode": "brief",
                    "surface_risk": 0.05,
                }
            )
        elif goal == "historical_narrative" or (
            "copa" in folded and re.search(r"20\d{2}|achou", folded)
        ):
            decision.update(
                {
                    "user_real_want": "opinião/narrativa histórica sobre a Copa",
                    "topic_kind": "historical",
                    "web_need": "required",
                    "needs_web": True,
                    "depth": "deep",
                    "response_mode": "detailed",
                    "needs_inference": True,
                    "surface_risk": 0.2,
                }
            )
        elif goal == "team_opinion" or re.search(
            r"\b(o\s+que\s+(?:voce\s+)?acha|oq\s+acha|achou|como\s+esta|"
            r"momento|atualmente)\b",
            folded,
        ):
            team = teams[0] if teams else None
            moment = temporal == "now" or bool(
                re.search(r"\b(agora|agr|atualmente|momento)\b", folded)
            )
            decision.update(
                {
                    "user_real_want": (
                        f"opinião + {'momento atual' if moment else 'contexto'} "
                        f"sobre {team or 'o time'}"
                    ),
                    "topic_kind": "moment" if moment else "opinion",
                    "topic_team": team,
                    "web_need": "optional",
                    "needs_web": True,
                    "depth": "deep" if moment else "medium",
                    "response_mode": "detailed" if moment else "normal",
                    "needs_inference": conf >= 0.7 or bool(team),
                    "needs_context_completion": conf >= 0.7,
                    "surface_risk": 0.15 if team else 0.45,
                }
            )
        elif goal == "match_outlook" or re.search(
            r"\b(ganha|vence|empata)\b", folded
        ):
            team = teams[0] if teams else None
            decision.update(
                {
                    "user_real_want": f"outlook do jogo de hoje ({team or 'time'})",
                    "topic_kind": "outlook",
                    "topic_team": team,
                    "web_need": "optional",
                    "needs_web": True,
                    "depth": "medium",
                    "response_mode": "normal",
                    "needs_inference": True,
                    "needs_context_completion": True,
                    "surface_risk": 0.25,
                }
            )
        elif goal in {"calendar_or_fixture"} or (
            teams and temporal in {"today", "tomorrow"}
        ):
            team = teams[0] if teams else None
            decision.update(
                {
                    "user_real_want": f"ver jogo/agenda ({team or 'times'})",
                    "topic_kind": "calendar",
                    "topic_team": team,
                    "web_need": "none",
                    "needs_web": False,
                    "depth": "simple",
                    "response_mode": "brief",
                    "needs_inference": conf >= 0.7,
                    "needs_context_completion": conf >= 0.7,
                    "surface_risk": 0.1 if conf >= 0.7 else 0.5,
                }
            )
        else:
            decision["surface_risk"] = 0.55
            decision["needs_inference"] = conf >= 0.55
            if teams:
                decision["topic_team"] = teams[0]
                decision["needs_context_completion"] = True

        if conf >= 0.7:
            decision["needs_inference"] = True
            decision["surface_risk"] = min(float(decision["surface_risk"]), 0.25)

        if ctx is not None:
            ctx["deep_thinking"] = decision

        logger.warning(
            "[AUDIT] DeepThinking: user_real_want=%r needs_web=%s web_need=%s "
            "depth=%s response_mode=%s inference=%s surface_risk=%.2f team=%r",
            decision.get("user_real_want"),
            decision.get("needs_web"),
            decision.get("web_need"),
            decision.get("depth"),
            decision.get("response_mode"),
            decision.get("needs_inference"),
            float(decision.get("surface_risk") or 0),
            decision.get("topic_team"),
        )
    except Exception as exc:
        logger.warning("run_deep_thinking_engine fail-open: %s", exc)
    return decision


# Back-compat alias
def run_pre_response_thinking(
    message: str,
    ctx: dict[str, Any] | None = None,
    *,
    recovery: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return run_deep_thinking_engine(message, ctx, recovery=recovery)


def get_thinking(ctx: dict[str, Any] | None) -> dict[str, Any]:
    if not ctx:
        return {}
    raw = ctx.get("deep_thinking")
    return dict(raw) if isinstance(raw, dict) else {}


def apply_depth_to_text(text: str, thinking: dict[str, Any] | None) -> str:
    """Formatter hook: trim or keep based on response_mode / depth."""
    body = (text or "").strip()
    if not body or not thinking:
        return body
    mode = thinking.get("response_mode") or "normal"
    parts = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    if mode == "brief" and len(parts) > 2:
        return "\n\n".join(parts[:2])
    if mode == "detailed":
        return body  # keep full
    # normal — cap runaway essays
    if len(parts) > 5:
        return "\n\n".join(parts[:5])
    return body


def looks_like_strong_template(text: str) -> bool:
    """Strict: only clear help-menu / empty / pitch patterns."""
    body = (text or "").strip()
    if not body or body in {"?", ".", "-", "…", "..."}:
        return True
    for pat in _STRONG_TEMPLATE:
        if pat.search(body):
            return True
    return False


def _enrich_template(
    text: str,
    *,
    message: str,
    ctx: dict[str, Any] | None,
    prefs: dict[str, Any] | None,
) -> str:
    thinking = get_thinking(ctx)
    web = (ctx or {}).get("web_thinking") or (ctx or {}).get("last_need_web") or {}
    team = thinking.get("topic_team")
    extras: list[str] = []
    if team:
        extras.append(
            f"Pensando no {team}: o que importa é o momento — identidade no campo "
            f"e o próximo adversário — mais do que um rótulo pronto."
        )
    if web.get("summary") and web.get("used_in_reasoning"):
        # already woven — don't re-append
        pass
    elif web.get("summary"):
        extras.append(
            f"Isso me faz enxergar o contexto assim: {str(web['summary'])[:180]}"
        )
    if not extras:
        extras.append(
            "Deixa eu ir além do automático: me diga se você quer papo de arquibancada "
            "ou uma leitura mais fina do jogo."
        )
    enriched = (text or "").rstrip() + "\n\n" + extras[0]
    try:
        from src.conversation.presence_humanization import apply_presence_humanization

        return apply_presence_humanization(enriched, prefs, family_hint="team_opinion")
    except Exception:
        return enriched


def review_and_enrich_payload(
    payload: dict[str, Any],
    *,
    message: str,
    ctx: dict[str, Any] | None = None,
    prefs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Enrich ONLY with strong template evidence AND short text AND surface_risk.
    """
    try:
        if not isinstance(payload, dict):
            return payload
        ents = payload.get("entities") or {}
        thinking = get_thinking(ctx)
        surface = float(thinking.get("surface_risk") or 0.3)

        if ents.get("emotional") or ents.get("profile_memory"):
            meta = dict(payload.get("response_metadata") or {})
            meta["response_review"] = {
                "skipped": True,
                "reason": "presence",
                "surface_risk": surface,
                "review_applied": False,
                "thinking_verdict": "pensou",
            }
            payload["response_metadata"] = meta
            logger.warning(
                "[AUDIT] Review: surface_risk=%.2f thinking_verdict=pensou review_applied=False",
                surface,
            )
            return payload

        summary = str(payload.get("executive_summary") or "")
        # Apply depth/mode from thinking
        trimmed = apply_depth_to_text(summary, thinking)
        if trimmed != summary:
            payload["executive_summary"] = trimmed
            if payload.get("final_recommendation") == summary:
                payload["final_recommendation"] = trimmed
            summary = trimmed

        # Unknown thinking → higher surface risk (template rescue allowed)
        if not thinking:
            surface = 0.5

        strong = looks_like_strong_template(summary)
        should_enrich = (
            strong
            and len(summary) < 220
            and surface > 0.35
            and payload.get("intent") not in {"emotional"}
        )

        review = {
            "looks_template": strong,
            "surface_risk": surface,
            "review_applied": False,
            "thinking_verdict": "automatico" if strong else "pensou",
            "enriched": False,
        }

        if should_enrich:
            new_text = _enrich_template(summary, message=message, ctx=ctx, prefs=prefs)
            if new_text and new_text != summary:
                payload["executive_summary"] = new_text
                if payload.get("final_recommendation") == summary or not payload.get(
                    "final_recommendation"
                ):
                    payload["final_recommendation"] = new_text
                review["review_applied"] = True
                review["enriched"] = True
                review["thinking_verdict"] = "pensou"
                review["looks_template"] = False
        else:
            # Blocked enrich — log why
            if strong and not should_enrich:
                review["blocked_reason"] = (
                    f"len={len(summary)} surface={surface:.2f} (need len<220 & surface>0.35)"
                )

        logger.warning(
            "[AUDIT] Review: surface_risk=%.2f thinking_verdict=%s review_applied=%s "
            "template=%s blocked=%s",
            surface,
            review.get("thinking_verdict"),
            review.get("review_applied"),
            strong,
            review.get("blocked_reason"),
        )

        meta = dict(payload.get("response_metadata") or {})
        meta["response_review"] = review
        payload["response_metadata"] = meta
        return payload
    except Exception as exc:
        logger.warning("review_and_enrich_payload fail-open: %s", exc)
        return payload


# legacy name used by older tests
def looks_like_template(text: str) -> bool:
    return looks_like_strong_template(text)
