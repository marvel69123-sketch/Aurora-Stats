"""
Phase 8.4-A.10 — Pronoun Continuity Layer.

Resolves short implicit references ("e dele?", "e o outro?", "e esse time?")
against the prior fixture / team / entity BEFORE GeneralAssistant / fallback.

Fail-open. Does not modify Market Engine, Opinion Renderer, Calendar,
Partial Analysis, or Ownership modules.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any

logger = logging.getLogger(__name__)

CTX_KEY = "pronoun_continuity"
RESOLVE_KEY = "pronoun_resolve"

# (pattern, pronoun_value, resolve_mode)
# resolve_mode: fixture | other_team | focus_team
_PRONOUN_SPECS: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"^\s*e\s+(?:o\s+)?dele\s*\??\s*$", re.I), "dele", "fixture"),
    (re.compile(r"^\s*e\s+(?:a\s+)?dela\s*\??\s*$", re.I), "dela", "fixture"),
    (re.compile(r"^\s*e\s+desse\s*\??\s*$", re.I), "desse", "fixture"),
    (re.compile(r"^\s*e\s+do\s+outro\s*\??\s*$", re.I), "do_outro", "other_team"),
    (re.compile(r"^\s*e\s+(?:o\s+)?outro\s*\??\s*$", re.I), "o_outro", "other_team"),
    (re.compile(r"^\s*e\s+esse\s+time\s*\??\s*$", re.I), "esse_time", "focus_team"),
    (re.compile(r"^\s*e\s+ele\s*\??\s*$", re.I), "ele", "fixture"),
    (re.compile(r"^\s*d(?:ele|ela)\s*\??\s*$", re.I), "dele", "fixture"),
]


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


def detect_pronoun(message: str | None) -> tuple[str, str] | None:
    """Return (pronoun_value, resolve_mode) or None."""
    folded = _fold(message or "")
    if not folded or len(folded.split()) > 5:
        return None
    for pat, value, mode in _PRONOUN_SPECS:
        if pat.match(folded):
            return value, mode
    return None


def get_pronoun_memory(ctx: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(ctx, dict):
        return {}
    raw = ctx.get(CTX_KEY)
    return dict(raw) if isinstance(raw, dict) else {}


def _split_fixture(label: str | None) -> tuple[str | None, str | None]:
    if not isinstance(label, str) or not label.strip():
        return None, None
    text = label.strip()
    for sep in (" vs ", " x ", " VS ", " X ", " v "):
        if sep in text:
            left, right = text.split(sep, 1)
            home, away = left.strip(), right.strip()
            if home and away:
                return home, away
    low = _fold(text)
    for sep in (" vs ", " x ", " v "):
        if sep in low:
            # rebuild from original with case-insensitive split
            m = re.split(r"\s+(?:vs|x|v)\s+", text, maxsplit=1, flags=re.I)
            if len(m) == 2 and m[0].strip() and m[1].strip():
                return m[0].strip(), m[1].strip()
    return None, None


def _gather_context(ctx: dict[str, Any]) -> dict[str, Any]:
    mem = get_pronoun_memory(ctx)
    home = mem.get("last_home") if isinstance(mem.get("last_home"), str) else None
    away = mem.get("last_away") if isinstance(mem.get("last_away"), str) else None
    team = mem.get("last_team") if isinstance(mem.get("last_team"), str) else None
    fixture = (
        mem.get("last_fixture") if isinstance(mem.get("last_fixture"), str) else None
    )
    invalid = bool(mem.get("entity_invalid"))
    quality = mem.get("fixture_quality")

    # Continuity window
    try:
        from src.conversation.conversation_continuity import get_continuity

        cont = get_continuity(ctx)
        if isinstance(cont.get("last_team"), str) and cont["last_team"].strip():
            team = team or cont["last_team"].strip()
        if isinstance(cont.get("last_fixture"), str) and cont["last_fixture"].strip():
            fixture = fixture or cont["last_fixture"].strip()
    except Exception:
        pass

    # Short memory
    try:
        from src.conversation.short_conversation_memory import get_short_memory

        sm = get_short_memory(ctx)
        if isinstance(sm.get("last_team"), str) and sm["last_team"].strip():
            team = team or sm["last_team"].strip()
        if isinstance(sm.get("last_fixture"), str) and sm["last_fixture"].strip():
            fixture = fixture or sm["last_fixture"].strip()
    except Exception:
        pass

    # Session last_match / last_analysis
    lm = ctx.get("last_match") or ctx.get("last_fixture")
    if isinstance(lm, str) and lm.strip():
        fixture = fixture or lm.strip()
    la = ctx.get("last_analysis") if isinstance(ctx.get("last_analysis"), dict) else {}
    if la:
        ents = la.get("entities") if isinstance(la.get("entities"), dict) else {}
        if isinstance(ents.get("home"), str):
            home = home or ents["home"].strip()
        if isinstance(ents.get("away"), str):
            away = away or ents["away"].strip()
        if isinstance(ents.get("team"), str):
            team = team or ents["team"].strip()
        q = la.get("fixture_quality") or ents.get("fixture_quality")
        if q:
            quality = quality or q
        if ents.get("entity_invalid") is True or q == "INVALID":
            invalid = True

    if (not home or not away) and fixture:
        h2, a2 = _split_fixture(fixture)
        home = home or h2
        away = away or a2
    if not team and home:
        team = home

    # Focus team (who was last discussed)
    focus = mem.get("focus_team") if isinstance(mem.get("focus_team"), str) else None
    focus = focus or team or home

    return {
        "home": home,
        "away": away,
        "team": team,
        "focus_team": focus,
        "fixture": fixture,
        "entity_invalid": invalid,
        "fixture_quality": quality,
    }


def note_pronoun_memory(
    ctx: dict[str, Any] | None,
    message: str,
    payload: dict[str, Any] | None,
) -> None:
    """Persist fixture/team/invalid flags for the next pronoun turn."""
    if not isinstance(ctx, dict):
        return
    try:
        mem = get_pronoun_memory(ctx)
        ents = dict(payload.get("entities") or {}) if isinstance(payload, dict) else {}
        home = ents.get("home") if isinstance(ents.get("home"), str) else None
        away = ents.get("away") if isinstance(ents.get("away"), str) else None
        team = ents.get("team") if isinstance(ents.get("team"), str) else None
        fixture = None
        if isinstance(payload, dict):
            match = payload.get("match")
            if isinstance(match, str) and match.strip():
                fixture = match.strip()
            elif isinstance(match, dict):
                mh, ma = match.get("home"), match.get("away")
                if mh and ma:
                    fixture = f"{mh} x {ma}"
                    home = home or (str(mh) if mh else None)
                    away = away or (str(ma) if ma else None)
        if home and away and not fixture:
            fixture = f"{home} x {away}"
        if not home or not away:
            h2, a2 = _split_fixture(fixture or ctx.get("last_match"))
            home = home or h2
            away = away or a2
        quality = None
        if isinstance(payload, dict):
            quality = payload.get("fixture_quality") or ents.get("fixture_quality")
        status = (
            payload.get("fixture_status") if isinstance(payload, dict) else None
        )
        invalid = bool(
            ents.get("entity_invalid") is True
            or quality == "INVALID"
            or status in ("FICTIONAL", "NOT_FOUND")
        )

        # Only refresh subject on sport-ish turns (keep prior on GA crumbs)
        intent = str(payload.get("intent") or "") if isinstance(payload, dict) else ""
        sportish = intent in {
            "analyze_match",
            "follow_up",
            "match_opinion",
            "partial_analysis",
        } or bool(
            ents.get("preliminary_analysis")
            or ents.get("continuity_followup")
            or ents.get("pronoun_resolved")
            or home
            or away
            or fixture
        )
        if sportish:
            if home:
                mem["last_home"] = home.strip()
            if away:
                mem["last_away"] = away.strip()
            if team or home:
                mem["last_team"] = (team or home or "").strip() or mem.get("last_team")
            if fixture:
                mem["last_fixture"] = fixture.strip()
            elif ctx.get("last_match") and isinstance(ctx.get("last_match"), str):
                mem["last_fixture"] = ctx["last_match"].strip()
            mem["focus_team"] = (team or home or mem.get("focus_team") or "").strip() or None
            mem["fixture_quality"] = quality or mem.get("fixture_quality")
            mem["entity_invalid"] = invalid
            if isinstance(message, str) and message.strip() and not detect_pronoun(message):
                mem["last_user_question"] = message.strip()[:240]
        ctx[CTX_KEY] = mem
        ctx.pop(RESOLVE_KEY, None)
    except Exception as exc:
        logger.warning("note_pronoun_memory fail-open: %s", exc)


def _stamp_audit(
    payload: dict[str, Any],
    *,
    pronoun_value: str,
    resolved: bool,
    entity: str | None,
    fixture: str | None,
    before_fallback: bool = True,
) -> dict[str, Any]:
    out = dict(payload)
    ents = dict(out.get("entities") or {})
    ents["pronoun_detected"] = True
    ents["pronoun_value"] = pronoun_value
    ents["pronoun_resolved"] = bool(resolved)
    ents["pronoun_entity"] = entity
    ents["pronoun_fixture"] = fixture
    ents["pronoun_before_fallback"] = bool(before_fallback)
    if resolved and fixture:
        ents["followup_context_found"] = True
        ents["followup_resolved_fixture"] = fixture
        ents["followup_before_fallback"] = True
        ents["continuity_followup"] = True
        if entity:
            ents["followup_resolved_team"] = entity
            ents["entity_resolved"] = True
            ents["team"] = entity
    out["entities"] = ents
    return out


def _invalid_payload(
    pronoun_value: str,
    fixture: str | None,
    brain: dict[str, Any] | None,
) -> dict[str, Any]:
    label = fixture or "esse confronto"
    text = (
        f"Não consigo continuar a partir de **{label}** — "
        f"as entidades não são válidas para análise de futebol.\n\n"
        f"Me diga um time ou um jogo real e eu sigo sem inventar dados."
    )
    payload: dict[str, Any] = {
        "intent": "analyze_match",
        "fixture_quality": "INVALID",
        "entities": {
            "entity_invalid": True,
            "fixture_quality": "INVALID",
            "has_analysis": False,
            "show_header": False,
            "pronoun_continuity": True,
            "response_owner": "pronoun_continuity",
            "final_response": True,
            "rewrite_locked": True,
        },
        "executive_summary": text,
        "final_recommendation": text,
        "best_markets": [],
        "confidence": {
            "score": 0.0,
            "label": "invalid",
            "explanation": "Pronome sobre fixture INVALID — sem inventar contexto.",
            "data_sources": ["Pronoun Continuity"],
        },
        "risk": {"level": "High", "flags": ["invalid_entities"], "invalidation_conditions": []},
        "bankroll_recommendation": {
            "recommended_stake_pct": 0.0,
            "method": "quarter-Kelly",
            "examples": {},
            "no_bet": True,
            "reasoning": "INVALID — sem stake.",
        },
        "knowledge_notes": [f"Pronoun Continuity: INVALID reuse blocked value={pronoun_value}"],
        "aurora_version": "Aurora v3.3.2-beta",
        "brain": brain or {},
    }
    return _stamp_audit(
        payload,
        pronoun_value=pronoun_value,
        resolved=True,
        entity=None,
        fixture=fixture,
        before_fallback=True,
    )


def _reuse_payload(
    *,
    pronoun_value: str,
    mode: str,
    entity: str,
    fixture: str | None,
    ctx: dict[str, Any],
    brain: dict[str, Any] | None,
) -> dict[str, Any]:
    label = fixture or entity
    if mode == "other_team":
        text = (
            f"Seguindo no contexto de **{label}**, focando em **{entity}** "
            f"(o outro lado do confronto).\n\n"
            f"Posso afunilar mercados, forma recente ou um recorte específico "
            f"desse time — sem inventar estatísticas ausentes."
        )
    elif mode == "focus_team":
        text = (
            f"Mantendo o contexto de **{label}**, com foco em **{entity}**.\n\n"
            f"Quer mercados, placar, favorito ou um ponto específico desse time?"
        )
    else:
        text = (
            f"Estou reutilizando o contexto anterior: **{label}**.\n\n"
            f"Posso continuar a leitura, mercados ou um recorte de **{entity}** "
            f"— diga o ângulo que prefere."
        )

    # Prefer FollowUp engine reuse when prior analysis exists (no invention)
    payload: dict[str, Any] | None = None
    la = ctx.get("last_analysis") if isinstance(ctx.get("last_analysis"), dict) else {}
    if la and (la.get("best_markets") or la.get("executive_summary")):
        try:
            from src.core.follow_up_engine import is_followup, resolve as fu_resolve

            engine_msg = "mais detalhes"
            if is_followup(engine_msg):
                payload = fu_resolve(engine_msg, ctx, brain or {})
        except Exception as fu_exc:
            logger.warning(
                "[AUDIT] PronounContinuity: follow_up_engine skip (%s)", fu_exc
            )
            payload = None

    if isinstance(payload, dict):
        summary = str(payload.get("executive_summary") or "").strip()
        if not summary or summary in {"?", "…", "..."} or len(summary) < 12:
            payload = None

    if not isinstance(payload, dict):
        markets = []
        if isinstance(la.get("best_markets"), list):
            markets = [m for m in la["best_markets"] if isinstance(m, dict)][:5]
        payload = {
            "intent": "follow_up",
            "entities": {
                "followup": True,
                "pronoun_continuity": True,
                "has_analysis": True,
                "show_header": False,
                "response_owner": "pronoun_continuity",
                "final_response": True,
                "home": _gather_context(ctx).get("home"),
                "away": _gather_context(ctx).get("away"),
            },
            "executive_summary": text,
            "final_recommendation": text,
            "best_markets": markets,
            "confidence": {
                "score": 4.0 if markets else 3.0,
                "label": "adequate" if markets else "weak",
                "explanation": "Follow-up pronominal (continuidade de contexto).",
                "data_sources": ["Pronoun Continuity"],
            },
            "risk": {"level": "Medium", "flags": [], "invalidation_conditions": []},
            "bankroll_recommendation": {
                "recommended_stake_pct": 0.0,
                "method": "quarter-Kelly",
                "examples": {},
                "no_bet": True,
                "reasoning": "Pronoun follow-up — sem novo stake.",
            },
            "knowledge_notes": [
                f"Pronoun Continuity: value={pronoun_value} entity={entity} fixture={fixture}"
            ],
            "aurora_version": "Aurora v3.3.2-beta",
            "brain": brain or {},
            "match": fixture,
        }

    payload = _stamp_audit(
        payload,
        pronoun_value=pronoun_value,
        resolved=True,
        entity=entity,
        fixture=fixture,
        before_fallback=True,
    )
    ents = dict(payload.get("entities") or {})
    ents["rewrite_locked"] = True
    ents["turn_owner"] = ents.get("turn_owner") or "SPORT"
    ents["continuity_draft"] = str(payload.get("executive_summary") or "")[:2000]
    payload["entities"] = ents
    try:
        from src.conversation.turn_ownership import mark_owner

        payload = mark_owner(payload, "SPORT", rewrite_locked=True) or payload
    except Exception:
        pass
    return payload


def try_pronoun_continuity(
    message: str,
    ctx: dict[str, Any] | None,
    *,
    brain: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """
    Claim short pronoun follow-ups BEFORE GA / Natural / IntelligenceFallback.
    """
    try:
        if not isinstance(ctx, dict):
            return None
        raw = str(ctx.get("raw_user_message") or message or "")
        detected = detect_pronoun(raw) or detect_pronoun(message)
        if not detected:
            return None
        pronoun_value, mode = detected

        try:
            from src.conversation.conversation_repair import is_repair_signal

            if is_repair_signal(raw):
                return None
        except Exception:
            pass

        info = _gather_context(ctx)
        fixture = info.get("fixture")
        home = info.get("home")
        away = info.get("away")
        focus = info.get("focus_team") or info.get("team") or home

        logger.warning(
            "[AUDIT] PronounContinuity: detected value=%s mode=%s fixture=%r "
            "home=%r away=%r invalid=%s before_fallback=True",
            pronoun_value,
            mode,
            fixture,
            home,
            away,
            info.get("entity_invalid"),
        )

        if info.get("entity_invalid") or info.get("fixture_quality") == "INVALID":
            # Only treat as INVALID pronoun reuse when we actually have a prior label
            if fixture or home or away:
                payload = _invalid_payload(pronoun_value, fixture, brain)
                ctx[RESOLVE_KEY] = {
                    "original": raw,
                    "pronoun_value": pronoun_value,
                    "resolved": True,
                    "invalid": True,
                    "fixture": fixture,
                }
                return payload

        if not fixture and not home and not focus:
            logger.warning(
                "[AUDIT] PronounContinuity: no prior context for %r — skip",
                raw[:40],
            )
            return None

        # Resolve entity
        entity: str | None = None
        if mode == "other_team" and home and away:
            focus_l = _fold(str(focus or home))
            if focus_l == _fold(home):
                entity = away
            elif focus_l == _fold(away):
                entity = home
            else:
                entity = away  # default: the other side vs home focus
        elif mode == "focus_team":
            entity = focus or home or away
        else:
            # fixture reuse — entity is focus team, fixture preserved
            entity = focus or home or away

        if not entity:
            return None

        # Normalize fixture label
        if not fixture and home and away:
            fixture = f"{home} x {away}"

        payload = _reuse_payload(
            pronoun_value=pronoun_value,
            mode=mode,
            entity=entity,
            fixture=fixture,
            ctx=ctx,
            brain=brain,
        )
        ctx[RESOLVE_KEY] = {
            "original": raw,
            "pronoun_value": pronoun_value,
            "resolved": True,
            "entity": entity,
            "fixture": fixture,
            "mode": mode,
        }
        # Update focus for chained "e o outro?"
        mem = get_pronoun_memory(ctx)
        if mode == "other_team":
            mem["focus_team"] = entity
        ctx[CTX_KEY] = mem

        logger.warning(
            "[AUDIT] PronounContinuity: RESOLVED value=%s entity=%r fixture=%r "
            "before_fallback=True",
            pronoun_value,
            entity,
            fixture,
        )
        try:
            from src.conversation.pipeline_trace import trace as _ptrace

            _ptrace(
                "PRONOUN_CONTINUITY",
                value=pronoun_value,
                entity=entity,
                fixture=str(fixture)[:60] if fixture else None,
                before_fallback=True,
            )
        except Exception:
            pass
        return payload
    except Exception as exc:
        logger.warning("try_pronoun_continuity fail-open: %s", exc)
        return None


def is_pronoun_followup(message: str | None) -> bool:
    return detect_pronoun(message) is not None
