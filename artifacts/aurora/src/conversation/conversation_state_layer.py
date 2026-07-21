"""
AURORA-CSL-001 — Conversation State Layer (CSL).

Façade only. Stores explicit sports conversation slots and may rewrite
underspecified follow-ups using prior teams. Does NOT replace engines,
routing, ownership, continuity, SLL, entity_safety, or sport_referent_frame.

Feature flag: ENABLE_CSL (default ON; set 0/false/off to rollback).
"""

from __future__ import annotations

import logging
import os
import re
import unicodedata
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

_FLAG_ENV = "ENABLE_CSL"
CTX_KEY = "csl"

# Bare follow-ups that need team context injected
_BARE_FOLLOWUP = re.compile(
    r"(?:"
    r"quem\s+est[aá]\s+(?:melhor|em\s+melhor)|"
    r"quem\s+(?:e|é)\s+melhor|"
    r"quem\s+leva|"
    r"quem\s+ganha\??$|"
    r"melhor\s+(?:fase|forma|time)|"
    r"em\s+melhor\s+(?:fase|forma)|"
    r"e\s+a\s+(?:forma|fase)\??|"
    r"e\s+agora\??|"
    r"comparando\??|"
    r"entre\s+eles|"
    r"e\s+o\s+outro\??|"
    r"qual\s+(?:dos\s+dois|melhor)"
    r")",
    re.I,
)

_HAS_ENTRE = re.compile(r"^\s*entre\b", re.I)
_DATE_HINT = re.compile(
    r"\b(hoje|amanh[aã]|semana\s+que\s+vem|proxima\s+rodada|"
    r"pr[oó]xima\s+segunda|domingo|s[aá]bado)\b",
    re.I,
)
_COMPARE_SEP = re.compile(
    r"\s+(?:ou|x|×|vs\.?|versus|contra|entre)\s+",
    re.I,
)


def csl_enabled() -> bool:
    raw = (os.environ.get(_FLAG_ENV) or "1").strip().lower()
    return raw not in {"0", "false", "off", "no"}


def fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


@dataclass
class CSLState:
    teams: list[str] = field(default_factory=list)
    fixture: str | None = None
    topic: str | None = None
    last_intent: str | None = None
    phase: str = "OPEN"
    date_context: str | None = None
    episode_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    # Observability extras
    injected: bool = False
    raw_text: str | None = None
    contextualized_text: str | None = None
    skipped_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["contract"] = {
            "teams": list(self.teams)[:4],
            "topic": self.topic,
            "last_intent": self.last_intent,
            "date_context": self.date_context,
            "episode_id": self.episode_id,
            "fixture": self.fixture,
            "phase": self.phase,
        }
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> CSLState:
        data = dict(data or {})
        teams = data.get("teams") or []
        if not isinstance(teams, list):
            teams = []
        clean = [str(t).strip() for t in teams if isinstance(t, str) and t.strip()]
        return cls(
            teams=clean[:4],
            fixture=data.get("fixture") if isinstance(data.get("fixture"), str) else None,
            topic=data.get("topic") if isinstance(data.get("topic"), str) else None,
            last_intent=(
                data.get("last_intent")
                if isinstance(data.get("last_intent"), str)
                else None
            ),
            phase=str(data.get("phase") or "OPEN"),
            date_context=(
                data.get("date_context")
                if isinstance(data.get("date_context"), str)
                else None
            ),
            episode_id=str(data.get("episode_id") or uuid.uuid4()),
            injected=bool(data.get("injected")),
            raw_text=data.get("raw_text") if isinstance(data.get("raw_text"), str) else None,
            contextualized_text=(
                data.get("contextualized_text")
                if isinstance(data.get("contextualized_text"), str)
                else None
            ),
            skipped_reason=(
                data.get("skipped_reason")
                if isinstance(data.get("skipped_reason"), str)
                else None
            ),
        )


def get_csl(ctx: dict[str, Any] | None) -> CSLState:
    if not isinstance(ctx, dict):
        return CSLState()
    raw = ctx.get(CTX_KEY)
    if isinstance(raw, dict):
        return CSLState.from_dict(raw)
    return CSLState()


def set_csl(ctx: dict[str, Any] | None, state: CSLState) -> None:
    if not isinstance(ctx, dict):
        return
    try:
        ctx[CTX_KEY] = state.to_dict()
    except Exception:
        pass


def _log(state: CSLState, *, event: str) -> None:
    try:
        logger.warning(
            "[CSL] event=%s teams=%s fixture=%r topic=%s phase=%s "
            "intent=%s date=%r injected=%s episode=%s skip=%s raw=%r ctx_text=%r",
            event,
            state.teams,
            state.fixture,
            state.topic,
            state.phase,
            state.last_intent,
            state.date_context,
            state.injected,
            (state.episode_id or "")[:8],
            state.skipped_reason,
            (state.raw_text or "")[:80],
            (state.contextualized_text or "")[:80],
        )
    except Exception:
        pass


def _teams_from_sll(ctx: dict[str, Any]) -> list[str]:
    sll = ctx.get("sll")
    if not isinstance(sll, dict):
        return []
    clubs = sll.get("clubs") or []
    out: list[str] = []
    if isinstance(clubs, list):
        for c in clubs:
            if isinstance(c, str) and c.strip() and c.strip() not in out:
                out.append(c.strip())
    return out[:4]


def _teams_from_legacy_ctx(ctx: dict[str, Any]) -> list[str]:
    """Façade read-through — never writes into FROZEN blobs."""
    out: list[str] = []
    for key in ("last_home", "last_away"):
        v = ctx.get(key)
        if isinstance(v, str) and v.strip() and v.strip() not in out:
            out.append(v.strip())
    match = ctx.get("last_match") or ctx.get("last_fixture")
    if isinstance(match, str) and match.strip():
        parts = re.split(r"\s+(?:x|vs\.?|versus)\s+", match, maxsplit=1, flags=re.I)
        if len(parts) == 2:
            for p in parts:
                t = p.strip()
                if t and t not in out:
                    out.append(t)
    return out[:4]


def _fixture_from_ctx(ctx: dict[str, Any]) -> str | None:
    for key in ("last_match", "last_fixture"):
        v = ctx.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _date_from_message(message: str) -> str | None:
    m = _DATE_HINT.search(message or "")
    return m.group(0).lower() if m else None


def _infer_topic(message: str, *, is_compare: bool, sll: dict | None) -> str | None:
    ask = None
    if isinstance(sll, dict):
        ask = sll.get("ask_kind")
    msg = fold(message)
    if is_compare or ask in {"compare", "form_compare"}:
        return "comparison"
    if ask == "calendar" or _DATE_HINT.search(message or ""):
        return "calendar"
    if ask == "form" or re.search(r"\b(fase|forma|momento)\b", msg):
        return "form"
    if ask == "bet" or re.search(r"\b(aposta|odds?|vale\s+a\s+pena)\b", msg):
        return "bet"
    if re.search(r"\banalisa|analisar|confronto\b", msg):
        return "fixture"
    return None


def _infer_phase(topic: str | None, *, injected: bool, has_teams: bool) -> str:
    if injected:
        return "FOLLOWUP"
    if topic == "comparison" and has_teams:
        return "COMPARE"
    if topic == "calendar":
        return "CALENDAR"
    if topic == "form":
        return "FORM"
    if topic == "fixture" and has_teams:
        return "FIXTURE"
    if has_teams:
        return "SLOT_READY"
    return "OPEN"


def _message_has_team_overlap(message: str, teams: list[str]) -> bool:
    msg = fold(message)
    if not msg:
        return False
    for t in teams:
        tf = fold(t)
        if not tf:
            continue
        if tf in msg:
            return True
        parts = tf.split()
        if len(parts) >= 2 and all(p in msg for p in parts):
            return True
    return False


def _looks_bare_followup(message: str) -> bool:
    text = (message or "").strip()
    if not text or len(text) > 80:
        return False
    if _HAS_ENTRE.search(text):
        return False
    if _COMPARE_SEP.search(text):
        return False
    return bool(_BARE_FOLLOWUP.search(text))


def _teams_from_compare_message(message: str) -> list[str]:
    """Pull A/B sides from an explicit compare when SLL did not expand."""
    text = message or ""
    # Strip leading analisar for routing-shaped text
    text = re.sub(r"^\s*analisar\s+", "", text, flags=re.I)
    m = re.search(
        r"(?<!\w)([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9._-]{2,40})"
        r"\s+(?:ou|x|×|vs\.?|versus|contra)\s+"
        r"([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9._-]{2,40})(?!\w)",
        text,
        flags=re.I,
    )
    if not m:
        return []
    a, b = m.group(1).strip(" .,!?"), m.group(2).strip(" .,!?")
    if fold(a) == fold(b):
        return []
    # Expand compact routing tokens if present
    compact_map = {
        "mancity": "Manchester City",
        "manutd": "Manchester United",
        "realmadrid": "Real Madrid",
        "atleticomineiro": "Atletico Mineiro",
        "atleticomadrid": "Atletico Madrid",
        "acmilan": "AC Milan",
        "intermilan": "Inter Milan",
        "saopaulo": "Sao Paulo",
    }

    def _f(x: str) -> str:
        return fold(x).replace("_", "")

    a2 = compact_map.get(_f(a), a)
    b2 = compact_map.get(_f(b), b)
    return [a2, b2]


def hydrate_csl_from_context(ctx: dict[str, Any] | None) -> CSLState:
    """Build/merge CSL from existing session ctx + SLL (read-only façade)."""
    state = get_csl(ctx)
    if not isinstance(ctx, dict):
        return state

    sll_teams = _teams_from_sll(ctx)
    legacy = _teams_from_legacy_ctx(ctx)
    merged: list[str] = []
    for t in list(state.teams) + sll_teams + legacy:
        if t and t not in merged:
            merged.append(t)
    state.teams = merged[:4]

    if not state.fixture:
        state.fixture = _fixture_from_ctx(ctx)

    if not state.last_intent and isinstance(ctx.get("last_intent"), str):
        state.last_intent = ctx.get("last_intent")

    sll = ctx.get("sll") if isinstance(ctx.get("sll"), dict) else None
    if sll and sll.get("is_compare") and not state.topic:
        state.topic = "comparison"

    return state


def contextualize_followup(message: str, state: CSLState) -> str | None:
    """
    If bare follow-up and >=2 teams known:
      'Quem está melhor?' → 'Entre Flamengo e Palmeiras, quem está melhor?'
    """
    if len(state.teams) < 2:
        return None
    if not _looks_bare_followup(message):
        return None
    if _message_has_team_overlap(message, state.teams):
        return None
    a, b = state.teams[0], state.teams[1]
    q = (message or "").strip().rstrip("?").strip()
    if not q:
        return None
    suffix = "?" if (message or "").strip().endswith("?") else ""
    body = q[:1].lower() + q[1:] if q else q
    return f"Entre {a} e {b}, {body}{suffix}"


def apply_csl_resolve(message: str, ctx: dict[str, Any] | None = None) -> str:
    """
    Turn-start CSL entry: hydrate slots, optionally contextualize follow-up.
    Fail-open. Never raises.
    """
    raw = message or ""
    if not csl_enabled():
        state = get_csl(ctx)
        state.raw_text = raw
        state.skipped_reason = "flag_disabled"
        state.injected = False
        set_csl(ctx, state)
        _log(state, event="skip_flag")
        return raw

    try:
        if not isinstance(ctx, dict):
            return raw

        if ctx.get("fiction_context_hard_reset") or ctx.get("sport_pipeline_blocked"):
            state = hydrate_csl_from_context(ctx)
            state.raw_text = raw
            state.skipped_reason = "pipeline_blocked"
            state.injected = False
            set_csl(ctx, state)
            _log(state, event="skip_blocked")
            return raw

        state = hydrate_csl_from_context(ctx)
        state.raw_text = raw
        state.injected = False
        state.contextualized_text = None
        state.skipped_reason = None

        sll = ctx.get("sll") if isinstance(ctx.get("sll"), dict) else None
        is_compare = bool(
            (sll and sll.get("is_compare")) or _COMPARE_SEP.search(raw)
        )
        date_hint = _date_from_message(raw)
        if date_hint:
            state.date_context = date_hint

        topic = _infer_topic(raw, is_compare=is_compare, sll=sll)
        if topic:
            state.topic = topic

        # New explicit compare with teams from SLL → refresh slots
        if sll and sll.get("applied") and sll.get("clubs"):
            clubs = [str(c) for c in (sll.get("clubs") or []) if isinstance(c, str)]
            if len(clubs) >= 2:
                state.teams = clubs[:4]
                state.fixture = f"{clubs[0]} x {clubs[1]}"
                state.topic = state.topic or "comparison"
                state.last_intent = "fixture_compare"
                state.phase = "COMPARE"
        elif is_compare and len(state.teams) < 2:
            sides = _teams_from_compare_message(raw)
            if len(sides) >= 2:
                state.teams = sides[:4]
                state.fixture = f"{sides[0]} x {sides[1]}"
                state.topic = state.topic or "comparison"
                state.last_intent = state.last_intent or "fixture_compare"
                state.phase = "COMPARE"

        injected = contextualize_followup(raw, state)
        out = raw
        if injected:
            out = injected
            state.injected = True
            state.contextualized_text = injected
            state.phase = "FOLLOWUP"
            state.topic = state.topic or "comparison"
            state.last_intent = state.last_intent or "followup_compare"
        else:
            state.phase = _infer_phase(
                state.topic, injected=False, has_teams=len(state.teams) >= 1
            )
            if not state.teams and not topic:
                state.skipped_reason = "no_slots"

        set_csl(ctx, state)
        _log(state, event="resolve")
        return out
    except Exception as exc:
        logger.warning("[CSL] fail-open resolve: %s", exc)
        return raw


def note_csl_after_response(
    ctx: dict[str, Any] | None,
    message: str,
    payload: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """
    End-of-turn: update CSL from payload/ctx. Additive stamp on payload entities.
    Does not modify ownership/continuity modules.
    """
    if not csl_enabled():
        return payload
    if not isinstance(ctx, dict):
        return payload
    try:
        if ctx.get("fiction_context_hard_reset"):
            cleared = CSLState(phase="OPEN", skipped_reason="hard_reset")
            set_csl(ctx, cleared)
            _log(cleared, event="clear_reset")
            return payload

        state = hydrate_csl_from_context(ctx)
        ents: dict[str, Any] = {}
        if isinstance(payload, dict):
            ents = dict(payload.get("entities") or {})

        home = ents.get("home")
        away = ents.get("away")
        team = ents.get("team")
        refreshed: list[str] = []
        for v in (home, away):
            if isinstance(v, str) and v.strip() and v.strip() not in refreshed:
                refreshed.append(v.strip())
        if isinstance(team, str) and team.strip() and team.strip() not in refreshed:
            if len(refreshed) < 2:
                refreshed.append(team.strip())
        if len(refreshed) >= 2:
            state.teams = refreshed[:4]
            state.fixture = f"{refreshed[0]} x {refreshed[1]}"
        elif refreshed and not state.teams:
            state.teams = refreshed[:4]

        match = None
        if isinstance(payload, dict):
            match = payload.get("match")
        if isinstance(match, str) and match.strip():
            state.fixture = match.strip()
        elif not state.fixture:
            state.fixture = _fixture_from_ctx(ctx)

        intent = None
        if isinstance(payload, dict):
            intent = payload.get("intent")
        if isinstance(intent, str) and intent.strip():
            state.last_intent = intent.strip()
        elif isinstance(ctx.get("last_intent"), str):
            state.last_intent = ctx["last_intent"]

        if state.teams and len(state.teams) >= 2:
            state.topic = state.topic or "comparison"
            state.phase = "FOLLOWUP" if state.injected else "SLOT_READY"
        elif state.teams:
            state.phase = "SLOT_READY"

        date_hint = _date_from_message(message or "")
        if date_hint:
            state.date_context = date_hint

        set_csl(ctx, state)
        _log(state, event="note")

        if isinstance(payload, dict):
            ents = dict(payload.get("entities") or {})
            ents["csl"] = state.to_dict().get("contract")
            payload["entities"] = ents
        return payload
    except Exception as exc:
        logger.warning("[CSL] fail-open note: %s", exc)
        return payload
