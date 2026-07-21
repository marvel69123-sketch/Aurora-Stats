"""
AURORA-RESPONSE-SELECTOR-001 — Deterministic Response Candidate Selector.

Replaces the early-claim / soft-hold *race* with collect → priority select.
Does NOT rewrite reasoning engines, SLL, CSL, entity_safety, or the internal
logic of ownership_stability / sport_continuity_guard — those remain as
fallback generators (low priority).

Feature flag: ENABLE_RESPONSE_SELECTOR (default ON; 0/false/off = legacy race).
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

_FLAG_ENV = "ENABLE_RESPONSE_SELECTOR"

# Priority bands (RESPONSE-001)
PRIORITY_CLARIFY = 100
PRIORITY_SPORT_INTENT_SKILL = 90
PRIORITY_CONTINUITY = 80
PRIORITY_ANALYZE = 70
PRIORITY_SOFT_HOLD = 40
PRIORITY_SOCIAL = 20

OWNER_SPORT_INTENT_SKILL = "sport_intent_skill"
OWNER_CONTINUITY = "conversation_continuity"
OWNER_PRONOUN = "pronoun_continuity"
OWNER_ADVANCED = "advanced_football_continuity"
OWNER_SCG = "sport_continuity_guard"
OWNER_OWNERSHIP = "ownership_stability"

_USELESS = frozenset({"", "?", "…", "...", ".", "!"})


def response_selector_enabled() -> bool:
    raw = (os.environ.get(_FLAG_ENV) or "1").strip().lower()
    return raw not in {"0", "false", "off", "no"}


@dataclass
class ResponseCandidate:
    owner: str
    text: str
    priority: int
    confidence: float
    metadata: dict = field(default_factory=dict)
    fallback: bool = False


def select_response(
    candidates: list[ResponseCandidate] | None,
) -> ResponseCandidate | None:
    """
    Deterministic selector: highest priority, then confidence.
    Skips empty / crumb texts when any viable alternative exists.
    """
    if not candidates:
        return None
    pool = [c for c in candidates if isinstance(c, ResponseCandidate)]
    if not pool:
        return None

    def _viable(c: ResponseCandidate) -> bool:
        t = (c.text or "").strip()
        if not t or t in _USELESS:
            return False
        if re.fullmatch(r"(?i)interessante\.?\s*\??", t):
            return False
        return True

    viable = [c for c in pool if _viable(c)]
    use = viable if viable else pool
    use.sort(key=lambda c: (int(c.priority), float(c.confidence)), reverse=True)
    winner = use[0]
    logger.warning(
        "[AUDIT] ResponseSelector: winner owner=%s priority=%s conf=%.2f "
        "fallback=%s pool=%s",
        winner.owner,
        winner.priority,
        float(winner.confidence),
        winner.fallback,
        [(c.owner, c.priority, round(float(c.confidence), 2)) for c in use[:8]],
    )
    return winner


def candidate_from_payload(
    payload: dict[str, Any] | None,
    *,
    owner: str,
    priority: int,
    confidence: float,
    fallback: bool = False,
    extra_meta: dict[str, Any] | None = None,
) -> ResponseCandidate | None:
    if not isinstance(payload, dict):
        return None
    text = str(
        payload.get("executive_summary")
        or payload.get("final_recommendation")
        or ""
    ).strip()
    meta: dict[str, Any] = {"payload": payload}
    if extra_meta:
        meta.update(extra_meta)
    return ResponseCandidate(
        owner=owner,
        text=text,
        priority=int(priority),
        confidence=float(confidence),
        metadata=meta,
        fallback=bool(fallback),
    )


def payload_from_candidate(candidate: ResponseCandidate) -> dict[str, Any] | None:
    """Materialize a Copilot payload from the winning candidate."""
    if not isinstance(candidate, ResponseCandidate):
        return None
    raw = candidate.metadata.get("payload")
    if isinstance(raw, dict):
        out = dict(raw)
    else:
        out = _minimal_sport_payload(candidate.text, candidate.owner)

    summary = (candidate.text or "").strip() or str(out.get("executive_summary") or "")
    out["executive_summary"] = summary
    out["final_recommendation"] = str(out.get("final_recommendation") or summary)

    ents = dict(out.get("entities") or {})
    ents["response_owner"] = candidate.owner
    ents["response_selector"] = True
    ents["response_selector_owner"] = candidate.owner
    ents["response_selector_priority"] = int(candidate.priority)
    ents["response_selector_confidence"] = float(candidate.confidence)
    ents["response_selector_fallback"] = bool(candidate.fallback)
    if candidate.fallback:
        ents.setdefault("continuity_followup", True)
    if candidate.owner == OWNER_SPORT_INTENT_SKILL:
        ents["response_selector_skip_honesty"] = True
        ents["sport_intent_authored"] = True
        ents["rewrite_locked"] = True
        ents["turn_owner"] = "SPORT"
        ents["followup"] = True
        ents["followup_before_fallback"] = True
        ents["continuity_followup"] = True
        ents["final_response"] = True
        ents["continuity_draft"] = summary[:2000]
        for k, v in (candidate.metadata or {}).items():
            if k != "payload" and k not in ents:
                ents[k] = v
    else:
        ents.setdefault("turn_owner", "SPORT")
        ents.setdefault("rewrite_locked", True)
    out["entities"] = ents
    out["intent"] = str(out.get("intent") or "follow_up")
    return out


def _minimal_sport_payload(text: str, owner: str) -> dict[str, Any]:
    return {
        "intent": "follow_up",
        "entities": {
            "followup": True,
            "turn_owner": "SPORT",
            "rewrite_locked": True,
            "response_owner": owner,
            "show_header": False,
        },
        "executive_summary": text,
        "final_recommendation": text,
        "best_markets": [],
        "confidence": {
            "score": 3.5,
            "label": "adequate",
            "explanation": "Response selector skill / hold candidate.",
            "data_sources": ["ResponseSelector"],
        },
        "risk": {"level": "Medium", "flags": [], "invalidation_conditions": []},
        "bankroll_recommendation": {
            "recommended_stake_pct": 0.0,
            "method": "quarter-Kelly",
            "examples": {},
            "no_bet": True,
            "reasoning": "Selector candidate — sem novo stake.",
        },
        "knowledge_notes": [f"response_selector owner={owner}"],
        "aurora_version": "Aurora v3.3.2-beta",
        "brain": {},
    }


# ── Generators (wrappers — do not alter OS / SCG internals) ───────────────


def _teams_fixture(ctx: dict[str, Any]) -> tuple[list[str], str | None]:
    teams: list[str] = []
    fixture: str | None = None
    try:
        from src.conversation.sport_intent_layer import _csl_teams, _fixture_label

        teams = list(_csl_teams(ctx) or [])
        fixture = _fixture_label(ctx, teams)
    except Exception:
        pass
    if not teams:
        try:
            from src.conversation.conversation_continuity import (
                _fixture_from_ctx,
                _team_from_ctx,
            )

            t = _team_from_ctx(ctx)
            fx = _fixture_from_ctx(ctx)
            if t:
                teams = [t]
            if fx:
                fixture = fixture or fx
                if " x " in fx or " vs " in fx.lower():
                    parts = re.split(r"\s+x\s+|\s+vs\s+", fx, flags=re.I)
                    teams = [p.strip() for p in parts if p.strip()] or teams
        except Exception:
            pass
    if not fixture and isinstance(ctx.get("last_match"), str):
        fixture = ctx["last_match"].strip() or fixture
    return teams, fixture


def _session_ready_for_skill(ctx: dict[str, Any]) -> bool:
    """True when a prior sport turn exists — never steal fresh A x B openers."""
    cont = ctx.get("conversation_continuity")
    if isinstance(cont, dict) and cont.get("active") and int(cont.get("turns_left") or 0) > 0:
        return True
    if isinstance(ctx.get("last_match"), str) and ctx["last_match"].strip():
        return True
    if isinstance(ctx.get("last_analysis"), dict) and ctx["last_analysis"]:
        return True
    csl = ctx.get("csl") if isinstance(ctx.get("csl"), dict) else {}
    if csl.get("injected"):
        return True
    try:
        from src.conversation.sport_continuity_guard import sport_anchor_active

        if sport_anchor_active(ctx):
            return True
    except Exception:
        pass
    try:
        from src.conversation.ownership_stability import owner_lock_active

        if owner_lock_active(ctx):
            return True
    except Exception:
        pass
    return False


def generate_sport_intent_skill(
    message: str,
    ctx: dict[str, Any] | None,
) -> ResponseCandidate | None:
    """
    Author a real executive_summary from sport_intent metadata.
    No new NLP / no engine calls — template authoring only.
    Skips calendar_query (out of scope for this layer).
    Skips fresh fixture openers (let analyze_match own them).
    """
    if not isinstance(ctx, dict):
        return None
    try:
        from src.conversation.sport_intent_layer import (
            BET_VIABILITY,
            COMPARE_STRENGTH,
            HOME_AWAY_ANALYSIS,
            MARKET_QUESTION,
            RECENT_FORM,
            CTX_KEY,
            fold,
            sport_intents_enabled,
        )

        if not sport_intents_enabled():
            return None
        if not _session_ready_for_skill(ctx):
            return None
        blob = ctx.get(CTX_KEY)
        if not isinstance(blob, dict) or not blob.get("intent"):
            return None
        intent = str(blob.get("intent") or "")
        conf = float(blob.get("confidence") or 0.0)
        if conf < 0.75:
            return None
        # No calendar work in this layer
        if intent == "calendar_query":
            return None
        # Never author on bare/new fixture openers
        routed = str(blob.get("routed_text") or message or "")
        folded = fold(routed)
        raw = fold(str(ctx.get("raw_user_message") or message or ""))
        if (" x " in folded or " vs " in folded) and not (
            ctx.get("csl") if isinstance(ctx.get("csl"), dict) else {}
        ).get("injected"):
            # opener-style compare rewrite — leave to analyze unless FU-injected
            if intent == COMPARE_STRENGTH and (
                folded.startswith("analisar ") or " x " in raw
            ):
                return None
        # Let continuity own bare market short FUs
        if intent == MARKET_QUESTION and not blob.get("rewritten"):
            raw_msg = str(ctx.get("raw_user_message") or message or "")
            if re.match(
                r"^(?:e\s+)?(?:os\s+)?(?:gols?|escanteios?|cantos?|corners?|"
                r"cart[oõ]es?|mercados?|btts|over|under)"
                r"(?:\s+\d+(?:[.,]\d+)?)?\s*\??$",
                raw_msg.strip(),
                re.I,
            ):
                return None

        teams, fixture = _teams_fixture(ctx)
        if not teams and not fixture:
            return None

        text = _author_skill_text(intent, teams, fixture, message)
        if not text:
            return None

        return ResponseCandidate(
            owner=OWNER_SPORT_INTENT_SKILL,
            text=text,
            priority=PRIORITY_SPORT_INTENT_SKILL,
            confidence=conf,
            metadata={
                "sport_intent": intent,
                "sport_skill": blob.get("skill"),
                "sport_intent_confidence": conf,
            },
            fallback=False,
        )
    except Exception as exc:
        logger.warning("response_selector: sport_intent skill skipped (%s)", exc)
        return None


def _author_skill_text(
    intent: str,
    teams: list[str],
    fixture: str | None,
    message: str,
) -> str | None:
    label = fixture or (" x ".join(teams[:2]) if len(teams) >= 2 else (teams[0] if teams else None))
    if not label:
        return None
    a = teams[0] if teams else label
    b = teams[1] if len(teams) >= 2 else None

    if intent == "recent_form":
        if b:
            return (
                f"Comparando a **fase recente** de **{a}** e **{b}** "
                f"(contexto: {label}).\n\n"
                f"Ainda sem fechar um placar numérico inventado neste turno — "
                f"posso afunilar em estatísticas, mando de campo ou mercados "
                f"se você escolher o recorte."
            )
        return (
            f"Sobre a **fase recente** de **{a}**.\n\n"
            f"Me diga se quer o recorte em resultados recentes, mando de campo "
            f"ou um confronto específico — sem inventar números."
        )

    if intent == "compare_strength":
        if b:
            return (
                f"Comparativo de força: **{a}** vs **{b}** ({label}).\n\n"
                f"Posso priorizar favoritismo, forma recente ou mercados — "
                f"diga o ângulo que prefere, sem inventar odds."
            )
        return (
            f"Comparativo no contexto de **{label}**.\n\n"
            f"Confirme o outro time ou o mercado que quer comparar."
        )

    if intent == "bet_viability":
        return (
            f"Viabilidade de aposta no contexto de **{label}**.\n\n"
            f"**No-bet** por padrão até haver sinais suficientes "
            f"(mercado, odd e confiança). Quer olhar gols, ambas marcam "
            f"ou um mercado específico?"
        )

    if intent == "home_away_analysis":
        return (
            f"Leitura de **mando de campo** em **{label}**.\n\n"
            f"Posso focar desempenho em casa/fora de "
            f"**{a}**"
            + (f" e **{b}**" if b else "")
            + " — sem inventar estatísticas não confirmadas."
        )

    if intent == "market_question":
        return (
            f"Mercados no confronto **{label}**.\n\n"
            f"Ainda sem lista numérica fechada neste turno — diga gols, "
            f"escanteios, cartões ou BTTS para eu priorizar o recorte."
        )

    return None


def generate_continuity(
    message: str,
    ctx: dict[str, Any] | None,
    *,
    brain: dict[str, Any] | None = None,
) -> ResponseCandidate | None:
    try:
        from src.conversation.conversation_continuity import (
            is_active_sport_followup,
            try_contextual_short_followup,
        )

        if not is_active_sport_followup(ctx, message):
            return None
        payload = try_contextual_short_followup(message, ctx, brain=brain)
        return candidate_from_payload(
            payload,
            owner=OWNER_CONTINUITY,
            priority=PRIORITY_CONTINUITY,
            confidence=0.94,
            fallback=False,
        )
    except Exception as exc:
        logger.warning("response_selector: continuity skipped (%s)", exc)
        return None


def generate_pronoun(
    message: str,
    ctx: dict[str, Any] | None,
    *,
    brain: dict[str, Any] | None = None,
) -> ResponseCandidate | None:
    try:
        from src.conversation.pronoun_continuity import try_pronoun_continuity

        payload = try_pronoun_continuity(message, ctx, brain=brain)
        return candidate_from_payload(
            payload,
            owner=OWNER_PRONOUN,
            priority=PRIORITY_CONTINUITY,
            confidence=0.93,
            fallback=False,
        )
    except Exception as exc:
        logger.warning("response_selector: pronoun skipped (%s)", exc)
        return None


def generate_advanced(
    message: str,
    ctx: dict[str, Any] | None,
    *,
    brain: dict[str, Any] | None = None,
) -> ResponseCandidate | None:
    try:
        from src.conversation.advanced_football_continuity import (
            try_advanced_football_continuity,
        )

        payload = try_advanced_football_continuity(message, ctx, brain=brain)
        return candidate_from_payload(
            payload,
            owner=OWNER_ADVANCED,
            priority=PRIORITY_CONTINUITY,
            confidence=0.92,
            fallback=False,
        )
    except Exception as exc:
        logger.warning("response_selector: advanced skipped (%s)", exc)
        return None


def generate_sport_continuity_guard(
    message: str,
    ctx: dict[str, Any] | None,
    *,
    brain: dict[str, Any] | None = None,
) -> ResponseCandidate | None:
    """SCG remains; soft/minimal holds marked fallback."""
    try:
        from src.conversation.sport_continuity_guard import try_sport_continuity_claim

        payload = try_sport_continuity_claim(message, ctx, brain=brain)
        if not isinstance(payload, dict):
            return None
        ents = payload.get("entities") or {}
        owner = str(ents.get("response_owner") or OWNER_SCG)
        # Resolver-backed replies stay high; pure SCG holds are fallback
        is_hold = owner in {OWNER_SCG, OWNER_OWNERSHIP} or bool(
            ents.get("sport_continuity_minimal_hold")
        )
        if owner in {OWNER_CONTINUITY, OWNER_PRONOUN, OWNER_ADVANCED}:
            priority = PRIORITY_CONTINUITY
            fallback = False
            conf = 0.935
        elif is_hold:
            priority = PRIORITY_SOFT_HOLD
            fallback = True
            conf = 0.80
            owner = OWNER_SCG
        else:
            priority = PRIORITY_CONTINUITY
            fallback = False
            conf = 0.90
        return candidate_from_payload(
            payload,
            owner=owner,
            priority=priority,
            confidence=conf,
            fallback=fallback,
        )
    except Exception as exc:
        logger.warning("response_selector: SCG skipped (%s)", exc)
        return None


def generate_ownership_stability(
    message: str,
    ctx: dict[str, Any] | None,
    *,
    brain: dict[str, Any] | None = None,
) -> ResponseCandidate | None:
    """
    ownership_stability remains — always treated as fallback generator.
    Continuity-backed OS stamps keep continuity priority if guard says so;
    soft holds stay at PRIORITY_SOFT_HOLD.
    """
    try:
        from src.conversation.ownership_stability import try_ownership_stability_claim

        payload = try_ownership_stability_claim(message, ctx, brain=brain)
        if not isinstance(payload, dict):
            return None
        ents = payload.get("entities") or {}
        guard = str(ents.get("ownership_stability_guard") or "")
        if guard in {"continuity", "pronoun", "advanced"}:
            # Prefer the dedicated generators; still allow as mid-high fallback
            owner_map = {
                "continuity": OWNER_CONTINUITY,
                "pronoun": OWNER_PRONOUN,
                "advanced": OWNER_ADVANCED,
            }
            return candidate_from_payload(
                payload,
                owner=owner_map.get(guard, OWNER_OWNERSHIP),
                priority=PRIORITY_CONTINUITY,
                confidence=0.91,
                fallback=True,
                extra_meta={"ownership_stability_guard": guard},
            )
        # Soft hold / forced hold → low priority fallback
        return candidate_from_payload(
            payload,
            owner=OWNER_OWNERSHIP,
            priority=PRIORITY_SOFT_HOLD,
            confidence=0.85,
            fallback=True,
            extra_meta={"ownership_stability_guard": guard or "owner_lock_hold"},
        )
    except Exception as exc:
        logger.warning("response_selector: ownership_stability skipped (%s)", exc)
        return None


def collect_early_candidates(
    message: str,
    ctx: dict[str, Any] | None,
    *,
    brain: dict[str, Any] | None = None,
) -> list[ResponseCandidate]:
    """Run generators; fail-open per generator."""
    out: list[ResponseCandidate] = []
    generators = (
        ("sport_intent_skill", lambda: generate_sport_intent_skill(message, ctx)),
        ("continuity", lambda: generate_continuity(message, ctx, brain=brain)),
        ("pronoun", lambda: generate_pronoun(message, ctx, brain=brain)),
        ("advanced", lambda: generate_advanced(message, ctx, brain=brain)),
        ("scg", lambda: generate_sport_continuity_guard(message, ctx, brain=brain)),
        ("ownership", lambda: generate_ownership_stability(message, ctx, brain=brain)),
    )
    for name, gen in generators:
        try:
            cand = gen()
            if isinstance(cand, ResponseCandidate):
                out.append(cand)
        except Exception as exc:
            logger.warning("response_selector: generator %s fail-open (%s)", name, exc)
    return out


def try_select_early_response(
    message: str,
    ctx: dict[str, Any] | None,
    *,
    brain: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """
    Router entry: collect candidates → select → materialize payload.
    Returns None when disabled or no viable candidate (legacy path may continue).
    """
    if not response_selector_enabled():
        return None
    try:
        pool = collect_early_candidates(message, ctx, brain=brain)
        if isinstance(ctx, dict):
            ctx["_response_selector_pool"] = [
                {
                    "owner": c.owner,
                    "priority": c.priority,
                    "confidence": c.confidence,
                    "fallback": c.fallback,
                    "text_prefix": (c.text or "")[:80],
                }
                for c in pool
            ]
        winner = select_response(pool)
        if winner is None:
            return None
        payload = payload_from_candidate(winner)
        if payload is None:
            return None
        # Stamp sport intent metadata when present
        try:
            from src.conversation.sport_intent_layer import note_sport_intent_on_payload

            payload = note_sport_intent_on_payload(ctx, payload) or payload
        except Exception:
            pass
        return payload
    except Exception as exc:
        logger.warning("try_select_early_response fail-open: %s", exc)
        return None
