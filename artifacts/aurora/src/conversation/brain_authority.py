"""
Aurora Brain Authority — DeepThinking as Source of Truth.

Gates text-producing layers (Natural / CRL / ensure_non_empty) so the new
brain controls replies. Fail-open. Additive. Does NOT edit frozen Reasoner
core logic beyond consulting ctx flags.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any

logger = logging.getLogger(__name__)

_BOUNDARY_FLAG = "brain_boundary_cleared"
_BLOCK_HYDRATE = "block_hydrate_legacy"

_CALENDAR_KINDS = frozenset({"calendar", "fixture", "kickoff", "outlook"})
_OPINION_KINDS = frozenset({"opinion", "moment", "historical"})


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


def get_thinking(ctx: dict[str, Any] | None) -> dict[str, Any]:
    if not ctx:
        return {}
    raw = ctx.get("deep_thinking")
    return dict(raw) if isinstance(raw, dict) else {}


def topic_kind(ctx: dict[str, Any] | None) -> str | None:
    return get_thinking(ctx).get("topic_kind")


def is_calendar_authority(ctx: dict[str, Any] | None) -> bool:
    return topic_kind(ctx) in _CALENDAR_KINDS


def is_opinion_authority(ctx: dict[str, Any] | None) -> bool:
    return topic_kind(ctx) in _OPINION_KINDS


def _active_fixture_teams(ctx: dict[str, Any] | None) -> set[str]:
    if not ctx:
        return set()
    names: set[str] = set()
    for key in ("last_home", "last_away"):
        v = (ctx.get(key) or "").strip()
        if v:
            names.add(_fold(v))
    match = _fold(str(ctx.get("last_match") or ctx.get("last_fixture") or ""))
    for part in re.split(r"\s+[x×]\s+|\s+vs\.?\s+", match):
        p = part.strip()
        if p:
            names.add(p)
    try:
        state = ctx.get("conversation_state") or {}
        fx = _fold(str(state.get("active_fixture") or ""))
        for part in re.split(r"\s+[x×]\s+|\s+vs\.?\s+", fx):
            p = part.strip()
            if p:
                names.add(p)
    except Exception:
        pass
    return {n for n in names if n}


def compute_boundary_score(
    message: str,
    ctx: dict[str, Any] | None,
    *,
    recovery: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Score whether this turn should clear sticky fixture.
    Soft follow-ups (horário/amanhã/anterior/como ele) → low score (same topic).
    Entity pivot (e o Santos) → high score (new topic).
    """
    out = {"score": 0.0, "clear": False, "reason": "keep", "same_topic": True}
    try:
        from src.conversation.conversation_focus import get_focus

        folded = _fold(message)
        focus = get_focus(ctx)
        recovery = recovery or ((ctx or {}).get("context_recovery") or {})
        thinking = get_thinking(ctx)
        teams = list(recovery.get("teams") or [])
        if thinking.get("topic_team") and thinking["topic_team"] not in teams:
            teams.append(thinking["topic_team"])
        for t in thinking.get("topic_teams") or []:
            if t and t not in teams:
                teams.append(t)

        # Reference resolver already marked same-topic follow-up
        ref = (ctx or {}).get("reference_resolution") or {}
        ref_reason = str(ref.get("reason") or "")
        if ref.get("resolved") and (
            ref_reason.startswith(
                (
                    "horario_",
                    "calendar_continue",
                    "team_calendar_",
                    "pronoun_",
                    "anterior_",
                )
            )
            or ref_reason in {"soft_followup_same_topic"}
        ):
            out.update(
                {
                    "score": 0.05,
                    "clear": False,
                    "reason": f"resolved_same_topic:{ref_reason}",
                    "same_topic": True,
                }
            )
            return out

        # Soft same-topic follow-ups (original phrasing)
        soft = bool(
            re.search(
                r"\b(e\s+o\s+horario|o\s+horario|e\s+amanha|amanha|"
                r"e\s+hoje|e\s+o\s+anterior|o\s+anterior|"
                r"como\s+(?:ele|ela)\s+|como\s+esta\s+atualmente)\b",
                folded,
            )
        )
        if soft and (
            focus.get("topic_team")
            or focus.get("topic_fixture")
            or (
                ctx
                and (ctx.get("last_match") or ctx.get("last_home"))
            )
        ):
            out.update(
                {
                    "score": 0.1,
                    "clear": False,
                    "reason": "soft_followup_same_topic",
                    "same_topic": True,
                }
            )
            return out

        prior = _active_fixture_teams(ctx)
        focus_fx = _fold(str(focus.get("topic_fixture") or ""))
        # Explicit A x B — only NEW fixture (not rewrite of same focus)
        if re.search(r"\b\w+\s+(?:x|vs\.?)\s+\w+\b", folded) or re.search(
            r"\bversus\b", folded
        ):
            if focus_fx and focus_fx in folded:
                out.update(
                    {
                        "score": 0.05,
                        "clear": False,
                        "reason": "same_fixture_restated",
                        "same_topic": True,
                    }
                )
                return out
            out.update(
                {
                    "score": 0.95,
                    "clear": True,
                    "reason": "explicit_new_fixture_phrase",
                    "same_topic": False,
                }
            )
            return out

        # Entity pivot with new team
        if teams and prior and {_fold(t) for t in teams}.isdisjoint(prior):
            out.update(
                {
                    "score": 0.92,
                    "clear": True,
                    "reason": "entity_shift_new_team",
                    "same_topic": False,
                }
            )
            return out
        # Also compare against conversation_focus teams
        focus_teams = {_fold(t) for t in (focus.get("topic_teams") or []) if t}
        if focus.get("topic_team"):
            focus_teams.add(_fold(str(focus["topic_team"])))
        if teams and focus_teams and {_fold(t) for t in teams}.isdisjoint(focus_teams):
            out.update(
                {
                    "score": 0.9,
                    "clear": True,
                    "reason": "entity_shift_vs_focus",
                    "same_topic": False,
                }
            )
            return out

        kind = thinking.get("topic_kind")
        if kind in _CALENDAR_KINDS and teams and prior:
            if {_fold(t) for t in teams}.isdisjoint(prior):
                out.update(
                    {
                        "score": 0.9,
                        "clear": True,
                        "reason": "calendar_new_team",
                        "same_topic": False,
                    }
                )
                return out

        if kind in _OPINION_KINDS and teams and prior:
            if {_fold(t) for t in teams}.isdisjoint(prior):
                out.update(
                    {
                        "score": 0.88,
                        "clear": True,
                        "reason": "opinion_new_team",
                        "same_topic": False,
                    }
                )
                return out

        if re.search(
            r"\b(joga\s+que\s+horas|tem\s+jogo|proximo\s+jogo)\b", folded
        ) and teams and prior:
            if {_fold(t) for t in teams}.isdisjoint(prior):
                out.update(
                    {
                        "score": 0.9,
                        "clear": True,
                        "reason": "schedule_new_team",
                        "same_topic": False,
                    }
                )
                return out

        return out
    except Exception as exc:
        logger.warning("compute_boundary_score fail-open: %s", exc)
        return out


def should_clear_topic_boundary(
    message: str,
    ctx: dict[str, Any] | None,
    *,
    recovery: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    """
    True when entities/intent changed enough that prior fixture must die.
    Uses boundary_score so soft follow-ups stay on-topic.
    """
    try:
        if not ctx:
            return False, "no_ctx"
        has_prior = bool(
            ctx.get("last_match")
            or ctx.get("last_fixture")
            or ctx.get("last_home")
            or (
                isinstance(ctx.get("conversation_state"), dict)
                and ctx["conversation_state"].get("active_fixture")
            )
            or (ctx.get("conversation_focus") or {}).get("topic_fixture")
        )
        if not has_prior:
            return False, "no_prior_fixture"

        scored = compute_boundary_score(message, ctx, recovery=recovery)
        if ctx is not None:
            ctx["boundary_score"] = scored
        logger.warning(
            "[AUDIT] BoundaryScore: score=%.2f clear=%s reason=%s",
            float(scored.get("score") or 0),
            scored.get("clear"),
            scored.get("reason"),
        )
        if scored.get("clear") and float(scored.get("score") or 0) >= 0.75:
            return True, str(scored.get("reason") or "boundary")
        return False, str(scored.get("reason") or "keep")
    except Exception as exc:
        logger.warning("should_clear_topic_boundary fail-open: %s", exc)
        return False, "error"


def apply_topic_boundary(
    ctx: dict[str, Any],
    *,
    reason: str,
) -> None:
    """Clear fixture memory and block hydrate_from_legacy for this turn."""
    try:
        from src.conversation.message_intelligence import clear_fixture_context

        clear_fixture_context(ctx)
        ctx[_BOUNDARY_FLAG] = True
        ctx[_BLOCK_HYDRATE] = True
        ctx["topic_boundary_reason"] = reason
        try:
            from src.conversation.conversation_focus import clear_focus_on_boundary

            clear_focus_on_boundary(ctx)
        except Exception:
            pass
        logger.warning(
            "[AUDIT] TopicBoundary: CLEARED fixture context reason=%s",
            reason,
        )
    except Exception as exc:
        logger.warning("apply_topic_boundary fail-open: %s", exc)


def hydrate_allowed(ctx: dict[str, Any] | None) -> bool:
    if not ctx:
        return True
    if ctx.get(_BLOCK_HYDRATE) or ctx.get(_BOUNDARY_FLAG):
        return False
    return True


def crl_may_continue_fixture(ctx: dict[str, Any] | None) -> bool:
    """
    DeepThinking SoT: calendar/fixture/kickoff/opinion/moment/new boundary
    → CRL must NOT short-circuit with 'continuar nesse confronto'.
    """
    if not hydrate_allowed(ctx):
        return False
    try:
        from src.conversation.human_inference import is_match_analysis

        if is_match_analysis(ctx):
            return False
    except Exception:
        pass
    if topic_kind(ctx) == "match_analysis":
        return False
    if is_calendar_authority(ctx):
        return False
    if is_opinion_authority(ctx):
        return False
    thinking = get_thinking(ctx)
    if thinking.get("user_real_want") and "agenda" in str(
        thinking.get("user_real_want")
    ).lower():
        return False
    try:
        recovery = (ctx or {}).get("context_recovery") or {}
        teams = list(recovery.get("teams") or [])
        if thinking.get("topic_team"):
            teams.append(thinking["topic_team"])
        prior = _active_fixture_teams(ctx)
        if teams and prior and {_fold(t) for t in teams}.isdisjoint(prior):
            return False
    except Exception:
        pass
    return True


def natural_may_emit_opinion(ctx: dict[str, Any] | None) -> bool:
    """Block opinion blurbs when DT says calendar/fixture."""
    if is_calendar_authority(ctx):
        return False
    return True


def calendar_empty_reply(
    *,
    team: str | None = None,
    teams: list[str] | None = None,
    kind: str | None = None,
) -> str:
    pair = teams or ([team] if team else [])
    if len(pair) >= 2:
        label = f"{pair[0]} x {pair[1]}"
        return (
            f"Entendi: você quer o jogo {label} — agenda/horário, não opinião.\n\n"
            f"Não consegui localizar esse confronto com segurança agora. "
            f"Se quiser, confirma a competição ou me diga se é hoje mesmo que "
            f"você está olhando."
        )
    if team:
        if kind == "kickoff":
            return (
                f"Você quer saber que horas o {team} joga.\n\n"
                f"Não achei o horário confirmado neste momento. "
                f"Me passa o adversário (ex.: {team} x Time B) ou a competição "
                f"que eu busco o kickoff com mais precisão."
            )
        return (
            f"Entendi: você quer saber se o {team} tem jogo (agenda), "
            f"não uma opinião sobre o time.\n\n"
            f"Não consegui localizar a partida agora. Se tiver o adversário "
            f"ou o campeonato, eu afunilo."
        )
    return (
        "Entendi que você quer agenda/horário de jogo.\n\n"
        "Não consegui localizar a partida pedida agora. Me diga o time "
        "(ou o confronto A x B) que eu busco de novo."
    )


def opinion_local_reasoning(
    team: str,
    *,
    moment: bool = False,
    variant: int | None = None,
) -> str:
    """
    Fail-open local reasoning with rotating variants — never the same opener.
    """
    if variant is None:
        import random

        variant = random.randint(0, 4)

    openers_moment = [
        (
            f"No momento do {team}, eu olharia menos o hype e mais o jogo: "
            f"está impondo ritmo? O elenco responde pressão? A torcida vê plano "
            f"ou só reação?\n\n"
            f"Sem cravar: fase pesa mais que fama. Regularidade muda a conversa; "
            f"oscilação pede cautela.\n\n"
            f"Se quiser, pegamos o próximo confronto do {team} e aprofundamos."
        ),
        (
            f"Falando do {team} agora: eu separaria narrativa de evidência. "
            f"Identidade ofensiva, capacidade de sustentar 90 minutos e o "
            f"adversário da semana importam mais do que o rótulo.\n\n"
            f"Minha leitura é de nuance — não de veredito engessado.\n\n"
            f"Me passa um jogo específico que a opinião fica bem mais afiada."
        ),
        (
            f"Sobre o {team} neste instante: o que me interessa é se o time "
            f"está encontrando cara própria ou vivendo de impulso.\n\n"
            f"Quando a regularidade aparece, a conversa muda; quando trava, "
            f"eu evitaria conclusão rápida.\n\n"
            f"Quer olhar um confronto recente juntos?"
        ),
        (
            f"Eu vejo o {team} pelo ângulo do momento — pressão, transição e "
            f"clareza de ideia — não só pela tabela.\n\n"
            f"Sem um recorte fresco na mesa, prefiro raciocínio aberto a tip "
            f"cego.\n\n"
            f"Se tiver o próximo adversário, a gente aprofunda de verdade."
        ),
        (
            f"Do jeito que eu leio o {team} hoje: o peso está no ritmo e na "
            f"resposta do elenco, não no discurso pronto.\n\n"
            f"Isso me faz tratar o assunto com nuance — fase boa ou oscilação "
            f"mudam o tom da conversa.\n\n"
            f"Pode ser papo de arquibancada ou leitura mais fina; me diga."
        ),
    ]
    openers_opinion = [
        (
            f"Sobre o {team}: eu evitaria opinião engessada. O que pesa é "
            f"momento, adversário e se o time sustenta ideia de jogo — não "
            f"só a camisa.\n\n"
            f"Se me der um confronto específico, a leitura fica bem mais afiada."
        ),
        (
            f"Do {team} eu gosto de conversar com nuance: identidade, intensidade "
            f"e o contexto do próximo jogo importam mais que um rótulo.\n\n"
            f"Sem o placar na mesa, eu prefiro raciocinar a cravar."
        ),
        (
            f"Minha forma de olhar o {team} é simples: menos fama, mais jogo. "
            f"Como chega, como pressiona, como reage quando o plano falha.\n\n"
            f"Quer escolher um confronto pra gente afiar isso?"
        ),
        (
            f"Eu trato o {team} como assunto vivo — fases mudam rápido. "
            f"Por isso a opinião precisa de recorte (adversário, momento, elenco).\n\n"
            f"Me diga o jogo que você tem em mente."
        ),
        (
            f"Com honestidade sobre o {team}: camisa não decide sozinha. "
            f"Eu olharia ritmo, equilíbrio e se a torcida vê um plano.\n\n"
            f"Com um confronto na mesa, a conversa sobe de nível."
        ),
    ]
    pool = openers_moment if moment else openers_opinion
    return pool[int(variant) % len(pool)]


def reasoning_variants_count() -> int:
    return 5


def should_block_analysis_engines(ctx: dict[str, Any] | None) -> bool:
    """DeepThinking SoT — conversational topics must not fall into analyze engines."""
    # Human Inference: match_analysis MUST reach analyze engines
    try:
        from src.conversation.human_inference import is_match_analysis

        if is_match_analysis(ctx):
            return False
    except Exception:
        pass
    kind = topic_kind(ctx)
    if kind == "match_analysis":
        return False
    return kind in {
        "calendar",
        "fixture",
        "kickoff",
        "opinion",
        "moment",
        "historical",
        "outlook",
    }


def ensure_fallback_for_thinking(
    message: str,
    ctx: dict[str, Any] | None,
) -> str:
    """ensure_non_empty SoT — never 'Pensando no…' for calendar."""
    thinking = get_thinking(ctx)
    kind = thinking.get("topic_kind")
    team = thinking.get("topic_team")
    recovery = (ctx or {}).get("context_recovery") or {}
    teams = list(recovery.get("teams") or [])
    if team and team not in teams:
        teams = [team] + teams

    if kind in _CALENDAR_KINDS:
        return calendar_empty_reply(
            team=team or (teams[0] if teams else None),
            teams=teams[:2],
            kind=kind,
        )
    if kind == "moment":
        return opinion_local_reasoning(str(team or teams[0] if teams else "esse time"), moment=True)
    if kind in {"opinion", "historical"}:
        if kind == "historical":
            try:
                from src.conversation.intelligence_fallback import build_copa_opinion

                return build_copa_opinion()
            except Exception:
                pass
        return opinion_local_reasoning(str(team or (teams[0] if teams else "esse time")))

    if teams:
        return opinion_local_reasoning(str(teams[0]))
    return (
        "Deixa eu pensar com calma no que você perguntou.\n\n"
        "Pelo que entendi, você quer uma leitura esportiva — não um menu "
        "genérico. Me dá time, jogo ou tema que eu aprofundo com honestidade."
    )
