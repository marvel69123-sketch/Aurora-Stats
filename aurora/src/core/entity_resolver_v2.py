"""
P2.5 — Entity Resolver v2.

Span-aware multi-word fixture parsing, SRF binding, ambiguity scoring,
pronoun resolution, fixture/topic switch detection.

Does not modify frozen P0/P1 modules or confidence/methodology engines.
Never invents opponents or fixtures.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Literal

logger = logging.getLogger(__name__)

Action = Literal["ASSUME", "CLARIFY", "NONE"]

AMBIGUOUS_TEAMS = {
    "barcelona": ["FC Barcelona", "Barcelona SC"],
    "united": ["Manchester United", "Newcastle United", "Sheffield United"],
    "santos": ["Santos FC", "Santos Laguna"],
    "athletic": ["Athletic Club", "Atletico Madrid"],
    "sport": ["Sport Recife", "Sporting CP"],
    "city": ["Manchester City", "Melbourne City"],
}

# Span-aware: capture multi-word sides (Real Madrid, Sao Paulo). Single-token forbidden.
_FIXTURE_SPAN = re.compile(
    r"(?P<home>.+?)\s+(?:x|vs\.?|versus)\s+(?P<away>.+)",
    re.I,
)

_SWITCH = re.compile(
    r"(?:agora\s+falando\s+d[oe]\s+|mudando\s+para\s+|vamos\s+falar\s+d[oe]\s+)"
    r"(.+)",
    re.I,
)

# Explicit side ask → CLARIFY when two sides plausible
_SIDE_ASK = re.compile(
    r"como\s+(?:ele|ela)\s+(?:est[aá]|joga|jogando)",
    re.I,
)

# Short pronoun FUs — ASSUME fixture (align with pronoun_continuity; do not steal A.18)
_SHORT_PRONOUN_FU = re.compile(
    r"^\s*(?:e\s+(?:o\s+)?(?:dele|dela|ele)|e\s+desse|e\s+(?:o\s+)?outro|"
    r"e\s+do\s+outro|e\s+esse\s+time|d(?:ele|ela))\s*\??\s*$",
    re.I,
)

_SIDE_PRONOUN = re.compile(
    r"(?:"
    r"como\s+(?:ele|ela)\s+(?:est[aá]|joga)|"
    r"\be\s+(?:dele|dela)\b|"
    r"\be\s+ele\b|"
    r"\bo\s+outro\b|"
    r"\be\s+o\s+outro\b|"
    r"\bo\s+advers[aá]rio\b"
    r")",
    re.I,
)

_PLURAL_DEIXIS = re.compile(
    r"(?:"
    r"como\s+eles\s+(?:est[aã]o|jogam)|"
    r"eles\s+est[aã]o|"
    r"\b(?:esse|este)\s+time\b|"
    r"\be\s+esse\s+time\b"
    r")",
    re.I,
)

_SHORT_FU = re.compile(
    r"^(?:e\s+agora|agora|mercados?|xg|press[aã]o|estat[ií]sticas?|"
    r"placar|favorito|o\s+jogo\s+mudou|quem\s+est[aá]\s+melhor|"
    r"stake|value|edge|kelly|confian[cç]a)"
    r"[\s?!.,]*$",
    re.I,
)

_JOGO_ASK = re.compile(r"como\s+est[aá]\s+o\s+jogo", re.I)

_STOP = frozenset(
    {
        "oi",
        "ola",
        "olá",
        "obrigado",
        "valeu",
        "ok",
        "sim",
        "nao",
        "não",
        "aff",
        "isso",
        "agora",
    }
)


@dataclass
class BindResult:
    action: Action
    ambiguity_score: float = 0.0
    assumptions: list[str] = field(default_factory=list)
    clarify_reason: str | None = None
    clarify_prompt: str | None = None
    referent_fixture: str | None = None
    referent_team: str | None = None
    candidates: list[str] = field(default_factory=list)
    binding_quality: str = "NONE"
    focus_kind: str = "NONE"
    srf: dict[str, Any] = field(default_factory=dict)

    def to_entities(self) -> dict[str, Any]:
        return {
            "entity_v2": True,
            "bind_action": self.action,
            "ambiguity_score": self.ambiguity_score,
            "binding_quality": self.binding_quality,
            "focus_kind": self.focus_kind,
            "bind_assumptions": list(self.assumptions),
            "clarify_reason": self.clarify_reason,
            "referent_fixture": self.referent_fixture,
            "referent_team": self.referent_team,
            "bind_candidates": list(self.candidates),
            "srf": {
                "focus_kind": self.srf.get("focus_kind"),
                "fixture_label": self.srf.get("fixture_label"),
                "focus_team": self.srf.get("focus_team"),
                "binding_quality": self.srf.get("binding_quality"),
            },
        }


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    t = re.sub(r"\s+", " ", raw.lower()).strip()
    return t.replace(" vs ", " x ").replace(" versus ", " x ")


def parse_fixture_span(message: str | None) -> tuple[str, str] | None:
    """
    Span-aware multi-word fixture parse.
    Rejects naive single-token-only patterns by allowing spaces in sides.
    """
    raw = (message or "").strip().rstrip(".!?…")
    if not raw or " x " not in _fold(raw) and not re.search(r"\s+(?:vs\.?|versus)\s+", raw, re.I):
        # still try regex
        pass
    m = _FIXTURE_SPAN.search(raw)
    if not m:
        return None
    home = m.group("home").strip().rstrip(".!?")
    away = m.group("away").strip().rstrip(".!?")
    # strip leading verbs like "analisar"
    home = re.sub(
        r"^(?:analisar|analise|análise|sobre|do|da|de)\s+",
        "",
        home,
        flags=re.I,
    ).strip()
    if not home or not away:
        return None
    if len(home.split()) > 5 or len(away.split()) > 5:
        return None
    if len(home) < 2 or len(away) < 2:
        return None
    return home, away


def _normalize_team(name: str, message: str = "") -> tuple[str, float, list[str]]:
    """Return (canonical, score, candidates). Never invents outside alias/fuzzy."""
    folded = _fold(name)
    # ENTITY-EDGE-001 — league-aware resolve for bare collisions when flagged
    try:
        from src.core.entity_edge import entity_edge_enabled, resolve_edge_entity

        if entity_edge_enabled():
            edge = resolve_edge_entity(name, message=message or name)
            if edge.canonical and edge.source in {
                "edge_explicit",
                "edge_league",
                "alias",
                "rapidfuzz",
                "edge_default",
            }:
                cands = list(edge.candidates) or [edge.canonical]
                return edge.canonical, float(edge.confidence or 0.9), cands
    except Exception:
        pass
    if folded in AMBIGUOUS_TEAMS:
        cands = list(AMBIGUOUS_TEAMS[folded])
        return name.strip(), 0.45, cands
    try:
        from src.core.entity_resolver import fuzzy_correct_team, normalize_team_name

        exact = normalize_team_name(name, message=message)
        if exact and _fold(exact) != folded:
            return exact, 0.95, [exact]
        hit, score = fuzzy_correct_team(name, message=message)
        if hit:
            return hit, float(score), [hit]
        if exact:
            return exact, 0.9, [exact]
    except Exception:
        pass
    return name.strip(), 0.55, [name.strip()]


def ambiguity_score(best: float, second: float = 0.0, *, bare_ambiguous: bool = False) -> float:
    margin = max(0.0, best - second)
    score = 1.0 - margin
    if bare_ambiguous:
        score = max(score, 0.7)
    return round(min(1.0, max(0.0, score)), 3)


def _is_ambiguous_name(name: str) -> bool:
    return _fold(name) in AMBIGUOUS_TEAMS


def resolve_referent(
    message: str,
    ctx: dict[str, Any] | None = None,
) -> BindResult:
    """
    Deterministic bind decision for this turn.
    Updates SRF on ASSUME commits; CLARIFY does not invent.
    """
    from src.conversation.sport_referent_frame import (
        bump,
        get_srf,
        project_from_ctx,
        set_fixture,
        set_focus_team,
        set_team,
        tick_ttl,
    )

    if not isinstance(ctx, dict):
        ctx = {}

    tick_ttl(ctx)
    project_from_ctx(ctx)
    srf = get_srf(ctx)
    folded = _fold(message)

    # Fiction / post-fiction: do not sport-assume
    try:
        from src.conversation.dialog_mode import CTX_KEY as DM_KEY
        from src.conversation.dialog_mode import is_fiction_message

        if is_fiction_message(message):
            return BindResult(action="NONE", srf=get_srf(ctx), clarify_reason="fiction")
        blob = ctx.get(DM_KEY)
        if isinstance(blob, dict) and blob.get("post_fiction_release"):
            if not parse_fixture_span(message):
                return BindResult(
                    action="CLARIFY",
                    ambiguity_score=0.85,
                    clarify_reason="post_fiction_needs_new_anchor",
                    clarify_prompt=(
                        "O contexto esportivo anterior foi limpo.\n\n"
                        "Me diga um confronto real (Time A x Time B) para continuar."
                    ),
                    srf=get_srf(ctx),
                )
    except Exception:
        pass

    # 1) Explicit multi-word fixture
    fx = parse_fixture_span(message)
    if fx:
        h_raw, a_raw = fx
        h, hs, _ = _normalize_team(h_raw, message=message)
        a, as_, _ = _normalize_team(a_raw, message=message)
        if _is_ambiguous_name(h_raw) or _is_ambiguous_name(a_raw):
            # still bind pair but mark ambiguity if either side bare-ambiguous alone
            pass
        set_fixture(ctx, h, a, quality="PARTIAL", source="fixture_span")
        bump(ctx, "assumed")
        srf = get_srf(ctx)
        return BindResult(
            action="ASSUME",
            ambiguity_score=ambiguity_score(max(hs, as_), 0.0),
            referent_fixture=srf.get("fixture_label"),
            binding_quality="PARTIAL",
            focus_kind="FIXTURE",
            srf=srf,
        )

    # 2) Topic switch
    sw = _SWITCH.search(message or "")
    if sw:
        team_raw = sw.group(1).strip().rstrip(".!?…")
        # if switch contains fixture span
        fx2 = parse_fixture_span(team_raw)
        if fx2:
            h, a = fx2
            hn, _, _ = _normalize_team(h, message=message)
            an, _, _ = _normalize_team(a, message=message)
            set_fixture(ctx, hn, an, quality="PARTIAL", source="switch_fixture")
            bump(ctx, "switched")
            srf = get_srf(ctx)
            return BindResult(
                action="ASSUME",
                assumptions=[f"Mudança de foco para {srf.get('fixture_label')}"],
                referent_fixture=srf.get("fixture_label"),
                binding_quality="PARTIAL",
                focus_kind="FIXTURE",
                srf=srf,
            )
        canon, score, cands = _normalize_team(team_raw, message=message)
        amb = _is_ambiguous_name(team_raw) or score < 0.7
        if amb and len(cands) > 1:
            set_team(ctx, team_raw, ambiguous=True, source="switch")
            bump(ctx, "clarified")
            return BindResult(
                action="CLARIFY",
                ambiguity_score=ambiguity_score(score, 0.4, bare_ambiguous=True),
                clarify_reason="ambiguous_club_on_switch",
                clarify_prompt=(
                    f"**{team_raw}** é ambíguo. Qual você quer?\n"
                    + "\n".join(f"- {c}" for c in cands[:4])
                ),
                candidates=cands,
                binding_quality="AMBIGUOUS",
                focus_kind="TEAM",
                srf=get_srf(ctx),
            )
        assumptions = [f"Mudança de foco para {canon} (sem confronto)"]
        set_team(ctx, canon, ambiguous=False, source="switch", assumptions=assumptions)
        bump(ctx, "assumed")
        srf = get_srf(ctx)
        return BindResult(
            action="ASSUME",
            ambiguity_score=ambiguity_score(score, 0.2),
            assumptions=assumptions,
            referent_team=canon,
            binding_quality="TEAM_ONLY",
            focus_kind="TEAM",
            srf=srf,
        )

    # 3) Bare team token
    bare = folded.rstrip("?!.,")
    if (
        bare
        and bare not in _STOP
        and len(bare.split()) <= 3
        and not _SHORT_FU.match(message or "")
        and not _SIDE_PRONOUN.search(message or "")
        and not _PLURAL_DEIXIS.search(message or "")
        and not _JOGO_ASK.search(message or "")
        and "x" not in bare
    ):
        if _is_ambiguous_name(bare):
            cands = list(AMBIGUOUS_TEAMS[bare])
            set_team(ctx, bare, ambiguous=True, source="bare_team")
            bump(ctx, "clarified")
            return BindResult(
                action="CLARIFY",
                ambiguity_score=0.72,
                clarify_reason="ambiguous_team",
                clarify_prompt=(
                    f"**{bare.title()}** é ambíguo — pode ser mais de um clube. Qual?\n"
                    + "\n".join(f"- {c}" for c in cands)
                ),
                candidates=cands,
                binding_quality="AMBIGUOUS",
                focus_kind="TEAM",
                srf=get_srf(ctx),
            )
        # Known / fuzzy team?
        canon, score, cands = _normalize_team(bare, message=message)
        looks_team = score >= 0.74 or bare in {
            "flamengo",
            "palmeiras",
            "corinthians",
            "liverpool",
            "chelsea",
            "bayern",
            "juventus",
            "psg",
            "real madrid",
            "manchester city",
        }
        if looks_team and len(bare) >= 4:
            set_team(ctx, canon, source="bare_team")
            bump(ctx, "assumed")
            srf = get_srf(ctx)
            return BindResult(
                action="ASSUME",
                ambiguity_score=ambiguity_score(score, 0.1),
                referent_team=canon,
                binding_quality="TEAM_ONLY",
                focus_kind="TEAM",
                srf=srf,
            )

    kind = str(srf.get("focus_kind") or "NONE")
    quality = str(srf.get("binding_quality") or "NONE")

    # 4) "Como está o jogo?"
    if _JOGO_ASK.search(message or ""):
        if kind == "FIXTURE":
            label = srf.get("fixture_label")
            assumptions = [f"Assumindo que você fala de {label}"]
            bump(ctx, "assumed")
            return BindResult(
                action="ASSUME",
                ambiguity_score=float(srf.get("ambiguity_score") or 0.1),
                assumptions=assumptions,
                referent_fixture=label,
                binding_quality=quality,
                focus_kind="FIXTURE",
                srf=srf,
            )
        bump(ctx, "clarified")
        return BindResult(
            action="CLARIFY",
            ambiguity_score=0.75,
            clarify_reason="jogo_needs_fixture",
            clarify_prompt=(
                "Qual jogo você quer?\n"
                "Ex.: Flamengo x Palmeiras"
            ),
            binding_quality=quality,
            focus_kind=kind,
            srf=srf,
        )

    # 5) Pronouns / deixis
    # Short FUs (e dele? / e o outro?) with FIXTURE → ASSUME fixture (A.18/pronoun path).
    # Explicit "como ele está jogando?" → CLARIFY sides (never silent home default).
    if _SHORT_PRONOUN_FU.match(message or "") and kind == "FIXTURE":
        assumptions = [f"Continuando em {srf.get('fixture_label')}"]
        bump(ctx, "assumed")
        return BindResult(
            action="ASSUME",
            assumptions=assumptions,
            referent_fixture=srf.get("fixture_label"),
            referent_team=srf.get("focus_team"),
            binding_quality=quality,
            focus_kind="FIXTURE",
            srf=srf,
        )

    if _SIDE_ASK.search(message or "") or _SIDE_PRONOUN.search(message or ""):
        if kind == "FIXTURE":
            focus = srf.get("focus_team")
            if isinstance(focus, str) and focus.strip():
                assumptions = [
                    f"Falando de {focus} em {srf.get('fixture_label')}"
                ]
                bump(ctx, "assumed")
                return BindResult(
                    action="ASSUME",
                    assumptions=assumptions,
                    referent_team=focus,
                    referent_fixture=srf.get("fixture_label"),
                    binding_quality=quality,
                    focus_kind="FIXTURE",
                    srf=srf,
                )
            # Explicit side question without focus → CLARIFY
            if _SIDE_ASK.search(message or "") or re.search(
                r"\badvers[aá]rio\b", folded
            ):
                bump(ctx, "clarified")
                return BindResult(
                    action="CLARIFY",
                    ambiguity_score=0.5,
                    clarify_reason="side_pronoun_two_plausible",
                    clarify_prompt=(
                        f"Você quer o momento do **{srf.get('home')}** ou do "
                        f"**{srf.get('away')}**?"
                    ),
                    referent_fixture=srf.get("fixture_label"),
                    binding_quality=quality,
                    focus_kind="FIXTURE",
                    srf=srf,
                )
            # Other side deixis with fixture → ASSUME fixture (no invent side)
            assumptions = [f"Assumindo o jogo {srf.get('fixture_label')}"]
            bump(ctx, "assumed")
            return BindResult(
                action="ASSUME",
                assumptions=assumptions,
                referent_fixture=srf.get("fixture_label"),
                binding_quality=quality,
                focus_kind="FIXTURE",
                srf=srf,
            )
        if kind == "TEAM":
            if re.search(r"\bo\s+outro\b|\badvers", folded):
                # Never invent opponent
                bump(ctx, "clarified")
                return BindResult(
                    action="CLARIFY",
                    ambiguity_score=0.7,
                    clarify_reason="opponent_deixis_team_only",
                    clarify_prompt=(
                        f"Estou com o time **{srf.get('focus_team')}**, mas sem adversário.\n"
                        "Me diga o confronto (Time A x Time B)."
                    ),
                    referent_team=srf.get("focus_team"),
                    binding_quality="TEAM_ONLY",
                    focus_kind="TEAM",
                    srf=srf,
                )
            assumptions = [f"Assumindo o time {srf.get('focus_team')}"]
            bump(ctx, "assumed")
            return BindResult(
                action="ASSUME",
                assumptions=assumptions,
                referent_team=srf.get("focus_team"),
                binding_quality="TEAM_ONLY",
                focus_kind="TEAM",
                srf=srf,
            )
        bump(ctx, "clarified")
        return BindResult(
            action="CLARIFY",
            ambiguity_score=0.85,
            clarify_reason="pronoun_no_frame",
            clarify_prompt="De qual time ou jogo você está falando?",
            srf=srf,
        )

    # 6) Plural deixis / eles
    if _PLURAL_DEIXIS.search(message or "") or folded.startswith("como eles"):
        if kind == "FIXTURE":
            assumptions = [f"Assumindo contexto de {srf.get('fixture_label')}"]
            bump(ctx, "assumed")
            return BindResult(
                action="ASSUME",
                assumptions=assumptions,
                referent_fixture=srf.get("fixture_label"),
                referent_team=srf.get("focus_team"),
                binding_quality=quality,
                focus_kind="FIXTURE",
                srf=srf,
            )
        if kind == "TEAM":
            assumptions = [f"Assumindo {srf.get('focus_team')}"]
            bump(ctx, "assumed")
            return BindResult(
                action="ASSUME",
                assumptions=assumptions,
                referent_team=srf.get("focus_team"),
                binding_quality="TEAM_ONLY",
                focus_kind="TEAM",
                srf=srf,
            )
        bump(ctx, "clarified")
        return BindResult(
            action="CLARIFY",
            ambiguity_score=0.8,
            clarify_reason="plural_no_frame",
            clarify_prompt="De qual jogo/time você está falando?",
            srf=srf,
        )

    # 7) Short FU
    if _SHORT_FU.match(message or "") or folded in {"e agora?", "e agora", "agora?"}:
        if kind == "FIXTURE":
            bump(ctx, "assumed")
            return BindResult(
                action="ASSUME",
                referent_fixture=srf.get("fixture_label"),
                binding_quality=quality,
                focus_kind="FIXTURE",
                srf=srf,
            )
        if kind == "TEAM":
            if re.search(r"mercado|melhor|stake|value|edge|kelly", folded):
                bump(ctx, "clarified")
                return BindResult(
                    action="CLARIFY",
                    ambiguity_score=0.55,
                    clarify_reason="markets_need_fixture",
                    clarify_prompt=(
                        f"Para mercados/comparação preciso do confronto completo.\n"
                        f"Ex.: {srf.get('focus_team')} x Adversário"
                    ),
                    referent_team=srf.get("focus_team"),
                    binding_quality="TEAM_ONLY",
                    focus_kind="TEAM",
                    srf=srf,
                )
            assumptions = [f"Continuando sobre {srf.get('focus_team')}"]
            bump(ctx, "assumed")
            return BindResult(
                action="ASSUME",
                assumptions=assumptions,
                referent_team=srf.get("focus_team"),
                binding_quality="TEAM_ONLY",
                focus_kind="TEAM",
                srf=srf,
            )
        bump(ctx, "clarified")
        return BindResult(
            action="CLARIFY",
            ambiguity_score=0.85,
            clarify_reason="short_fu_no_frame",
            clarify_prompt="Me diga o jogo (Time A x Time B) ou o time.",
            srf=srf,
        )

    # 8) Soft maintain
    if kind != "NONE":
        return BindResult(
            action="ASSUME",
            assumptions=[
                f"Mantendo foco {srf.get('fixture_label') or srf.get('focus_team')}"
            ],
            referent_fixture=srf.get("fixture_label"),
            referent_team=srf.get("focus_team"),
            binding_quality=quality,
            focus_kind=kind,
            srf=srf,
        )

    return BindResult(action="NONE", srf=srf)


def build_clarify_payload(bind: BindResult, message: str | None = None) -> dict[str, Any]:
    """Clarification payload for Entity v2 CLARIFY — never invents fixtures."""
    try:
        from src.brain import get_brain_meta

        brain = get_brain_meta()
    except Exception:
        brain = {}
    text = bind.clarify_prompt or (
        "Não quero assumir o confronto errado.\n\n"
        "Me diga Time A x Time B, ou escolha o time com clareza."
    )
    if bind.assumptions:
        text = " / ".join(bind.assumptions) + "\n\n" + text
    return {
        "intent": "clarification",
        "match": None,
        "status": None,
        "is_live": False,
        "minute": None,
        "executive_summary": text,
        "final_recommendation": text,
        "best_markets": [],
        "confidence": {
            "score": 0.0,
            "label": "insufficient",
            "explanation": "Entity Resolver v2 — clarification required.",
            "data_sources": ["EntityResolverV2"],
        },
        "risk": {"level": "Unknown", "flags": [], "invalidation_conditions": []},
        "bankroll_recommendation": {
            "recommended_stake_pct": 0.0,
            "method": "quarter-Kelly",
            "examples": {},
            "no_bet": True,
            "reasoning": "Awaiting referent clarification.",
        },
        "positive_factors": [],
        "negative_factors": [],
        "historical_references": [],
        "knowledge_notes": [],
        "aurora_version": "Copilot v1.0",
        "brain": brain,
        "response_metadata": {"mode": "clarification", "source": "entity_resolver_v2"},
        "entities": {
            **bind.to_entities(),
            "clarification_mode": True,
            "response_owner": "entity_resolver_v2",
            "turn_owner": "CLARIFICATION",
            "rewrite_locked": True,
            "has_analysis": False,
            "show_header": False,
            "skip_llm": True,
            "p25_entity_v2": True,
        },
    }


def try_entity_v2_clarify_claim(
    message: str,
    ctx: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Early claim only when action=CLARIFY (does not steal ASSUME sport path)."""
    try:
        bind = resolve_referent(message, ctx)
        if bind.action != "CLARIFY":
            # Still stamp bind metadata on ctx for later enrich
            if isinstance(ctx, dict):
                ctx["entity_v2_last_bind"] = bind.to_entities()
            return None
        payload = build_clarify_payload(bind, message)
        if isinstance(ctx, dict):
            ctx["entity_v2_last_bind"] = bind.to_entities()
        return payload
    except Exception as exc:
        logger.warning("entity_v2 clarify claim fail-open: %s", exc)
        return None


def stamp_bind_on_payload(
    payload: dict[str, Any] | None,
    ctx: dict[str, Any] | None,
    message: str | None = None,
) -> dict[str, Any] | None:
    """Attach bind metadata / update SRF after sport replies."""
    if not isinstance(payload, dict):
        return payload
    try:
        from src.conversation.sport_referent_frame import get_srf, note_from_payload

        note_from_payload(ctx, payload)
        ents = dict(payload.get("entities") or {})
        last = (ctx or {}).get("entity_v2_last_bind") if isinstance(ctx, dict) else None
        if isinstance(last, dict):
            ents.update({k: v for k, v in last.items() if k != "srf"})
        srf = get_srf(ctx)
        ents["srf"] = {
            "focus_kind": srf.get("focus_kind"),
            "fixture_label": srf.get("fixture_label"),
            "focus_team": srf.get("focus_team"),
            "binding_quality": srf.get("binding_quality"),
        }
        ents["p25_entity_v2"] = True
        payload["entities"] = ents
    except Exception as exc:
        logger.warning("entity_v2 stamp fail-open: %s", exc)
    return payload
