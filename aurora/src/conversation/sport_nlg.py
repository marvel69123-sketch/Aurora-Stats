"""
SPORT-NLG-001 — Sports Analyst Natural Language Generation (presentation).

Rule-based surface realization inspired by Athena NLG (structured content →
prose) and Rasa response templates (slots from dialogue state). No LLM.

Inputs (from existing payload/ctx only):
  intent · reasoning · confidence · context

Output:
  human sports-analyst prose for executive_summary.

Never invents odds, scores, xG, or markets. Fail-open.
Feature flag: ENABLE_SPORT_NLG (default OFF — set 1/true/on to enable).
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

_FLAG_ENV = "ENABLE_SPORT_NLG"

# Middleware / robotic openings we replace when rewriting
_ROBOTIC_OPENERS = re.compile(
    r"(?is)^(?:\s*)(?:"
    r"comparando\s+a\s+\*{0,2}fase\s+recente\*{0,2}|"
    r"comparativo\s+de\s+for[cç]a\s*:|"
    r"viabilidade\s+de\s+aposta\s+no\s+contexto|"
    r"leitura\s+de\s+\*{0,2}mando\s+de\s+campo\*{0,2}|"
    r"mercados\s+no\s+confronto|"
    r"mantendo\s+(?:foco|o\s+contexto)|"
    r"continuando\s+sobre|"
    r"assumindo\s+(?:o\s+time|que\s+voc[eê])|"
    r"no-bet\s*:\s*sinais\s+insuficientes|"
    r"com\s+\*{0,2}dados\s+parciais\*{0,2}"
    r")"
)


def sport_nlg_enabled() -> bool:
    """Default OFF per SPORT-NLG-001 contract."""
    raw = (os.environ.get(_FLAG_ENV) or "0").strip().lower()
    return raw in {"1", "true", "on", "yes"}


@dataclass
class SportNlgInput:
    intent: str = ""
    sport_intent: str | None = None
    reasoning: list[str] = field(default_factory=list)
    confidence_label: str = ""
    confidence_score: float | None = None
    confidence_explanation: str = ""
    fixture: str | None = None
    teams: list[str] = field(default_factory=list)
    draft: str = ""
    no_bet: bool = True
    missing_signals: list[str] = field(default_factory=list)
    available_signals: list[str] = field(default_factory=list)


def extract_nlg_input(
    payload: dict[str, Any] | None,
    ctx: dict[str, Any] | None = None,
    *,
    message: str | None = None,
) -> SportNlgInput:
    """Pull intent / reasoning / confidence / context — never fabricate facts."""
    inp = SportNlgInput()
    if not isinstance(payload, dict):
        return inp

    ents = payload.get("entities") if isinstance(payload.get("entities"), dict) else {}
    conf = payload.get("confidence") if isinstance(payload.get("confidence"), dict) else {}
    br = (
        payload.get("bankroll_recommendation")
        if isinstance(payload.get("bankroll_recommendation"), dict)
        else {}
    )

    inp.intent = str(payload.get("intent") or "")
    inp.sport_intent = (
        str(ents.get("sport_intent") or "").strip() or None
    )
    if not inp.sport_intent and isinstance(ctx, dict):
        blob = ctx.get("sport_intents")
        if isinstance(blob, dict) and blob.get("intent"):
            inp.sport_intent = str(blob.get("intent"))

    inp.draft = str(payload.get("executive_summary") or "").strip()
    inp.no_bet = bool(br.get("no_bet", True))

    # Confidence (as reported — do not invent score)
    inp.confidence_label = str(conf.get("label") or "").strip()
    try:
        if conf.get("score") is not None:
            inp.confidence_score = float(conf["score"])
    except (TypeError, ValueError):
        inp.confidence_score = None
    inp.confidence_explanation = str(conf.get("explanation") or "").strip()

    # Reasoning = only existing payload signals
    for key in ("positive_factors", "negative_factors", "knowledge_notes"):
        raw = payload.get(key)
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, str) and item.strip():
                    inp.reasoning.append(item.strip()[:240])
                elif isinstance(item, dict):
                    t = str(item.get("text") or item.get("note") or item.get("factor") or "")
                    if t.strip():
                        inp.reasoning.append(t.strip()[:240])
    # Prefer structured factors over confidence boilerplate in reasoning bullets
    expl = inp.confidence_explanation
    if expl and not re.match(
        r"(?i)^(?:confian[cç]a|follow-up|parcial|response\s+selector|soft)",
        expl,
    ):
        inp.reasoning.append(expl[:240])

    # Honesty / inference signals already on payload
    hb = ents.get("honesty_block") if isinstance(ents.get("honesty_block"), dict) else {}
    for key, attr in (("lack", "missing_signals"), ("have", "available_signals")):
        vals = hb.get(key) or []
        if isinstance(vals, list):
            setattr(
                inp,
                attr,
                [str(x).strip() for x in vals if str(x).strip()][:6],
            )

    # Context labels
    teams: list[str] = []
    fixture = (
        ents.get("followup_resolved_fixture")
        or ents.get("resolved_fixture")
        or ents.get("referent_fixture")
        or payload.get("match")
    )
    if isinstance(fixture, str) and fixture.strip():
        inp.fixture = _clean_fixture_label(fixture.strip())
    for t in (
        ents.get("team"),
        ents.get("followup_resolved_team"),
        ents.get("home"),
        ents.get("away"),
    ):
        if isinstance(t, str) and t.strip() and t.strip() not in teams:
            teams.append(t.strip())
    if isinstance(ctx, dict):
        csl = ctx.get("csl") if isinstance(ctx.get("csl"), dict) else {}
        for t in csl.get("teams") or []:
            if isinstance(t, str) and t.strip() and t.strip() not in teams:
                teams.append(t.strip())
        if not inp.fixture and isinstance(csl.get("fixture"), str):
            inp.fixture = _clean_fixture_label(csl["fixture"].strip()) or inp.fixture
        if not inp.fixture and isinstance(ctx.get("last_match"), str):
            inp.fixture = _clean_fixture_label(ctx["last_match"].strip()) or inp.fixture
    if len(teams) < 2 and inp.fixture and (" x " in inp.fixture or " vs " in inp.fixture.lower()):
        parts = re.split(r"\s+x\s+|\s+vs\s+", inp.fixture, flags=re.I)
        for p in parts:
            if p.strip() and p.strip() not in teams:
                teams.append(p.strip())
    inp.teams = teams[:4]

    _ = message  # reserved for future slotting; unused to avoid NLP creep
    return inp


def render_sport_analyst(inp: SportNlgInput) -> str:
    """
    Realize analyst prose from structured input.
    Prefer rewriting robotic drafts; keep substantive drafts with light polish.
    """
    if not isinstance(inp, SportNlgInput):
        return ""

    draft = (inp.draft or "").strip()
    if not draft or draft in {"?", "…", "..."}:
        return _compose_from_slots(inp)

    # Substantive analysis already present — light de-roboticize only
    if _looks_substantive(draft) and not _ROBOTIC_OPENERS.match(draft):
        return _light_polish(draft, inp)

    # Middleware / skill-shell drafts → full analyst realization
    if _ROBOTIC_OPENERS.match(draft) or _looks_middleware(draft):
        return _compose_from_slots(inp, seed_draft=draft)

    return _light_polish(draft, inp)


def apply_sport_nlg(
    payload: dict[str, Any] | None,
    ctx: dict[str, Any] | None = None,
    *,
    message: str | None = None,
) -> dict[str, Any] | None:
    """Presentation pass. Fail-open. No engine calls."""
    if not sport_nlg_enabled():
        return payload
    if not isinstance(payload, dict):
        return payload

    try:
        ents = dict(payload.get("entities") or {})
        # Never touch pure social / identity / capabilities
        intent = str(payload.get("intent") or "")
        if intent in {"small_talk", "identity", "greeting", "assistant_capabilities"}:
            return payload
        if ents.get("assistant_capabilities") or ents.get("clarification_mode"):
            # Keep clarify prompts crisp
            if ents.get("clarification_mode") and not ents.get("has_analysis"):
                return payload

        sportish = intent in {
            "analyze_match",
            "follow_up",
            "match_opinion",
            "live_opportunities",
            "live_team_analysis",
        } or bool(
            ents.get("sport_intent_authored")
            or ents.get("continuity_followup")
            or ents.get("preliminary_analysis")
            or ents.get("has_analysis")
            or ents.get("response_selector")
        )
        if not sportish:
            return payload

        inp = extract_nlg_input(payload, ctx, message=message)
        text = render_sport_analyst(inp)
        if not text or not text.strip():
            return payload

        # Credibility: never drop numbers that already existed in draft
        text = _preserve_numeric_claims(inp.draft, text)

        out = dict(payload)
        out["executive_summary"] = text.strip()
        # Keep final_recommendation aligned when it was a mirror of summary
        prev_final = str(payload.get("final_recommendation") or "").strip()
        prev_sum = str(inp.draft or "").strip()
        if not prev_final or prev_final == prev_sum or len(prev_final) < 12:
            out["final_recommendation"] = text.strip()

        ents["sport_nlg"] = True
        ents["sport_nlg_intent"] = inp.sport_intent or inp.intent
        if ents.get("continuity_draft"):
            ents["continuity_draft"] = text.strip()[:2000]
        out["entities"] = ents

        logger.warning(
            "[AUDIT] SportNLG: applied sport_intent=%s intent=%s len=%d→%d",
            inp.sport_intent,
            inp.intent,
            len(prev_sum),
            len(text),
        )
        return out
    except Exception as exc:
        logger.warning("sport_nlg fail-open: %s", exc)
        return payload


# ── Internals ─────────────────────────────────────────────────────────────


def _clean_fixture_label(label: str | None) -> str | None:
    """Drop skill-rewrite residue from fixture strings (presentation only)."""
    if not label:
        return None
    t = str(label).strip()
    t = re.sub(
        r"\s*\((?:comparativo(?:\s+de\s+for[cç]a)?|forma\s+recente)[^)]*\)\s*$",
        "",
        t,
        flags=re.I,
    )
    t = re.sub(r"\s+comparativo\s+de\s+for[cç]a\s*$", "", t, flags=re.I)
    return t.strip() or None


def _looks_substantive(draft: str) -> bool:
    """Heuristic: longer analysis with bullets or multiple sentences of content."""
    t = draft.strip()
    if len(t) < 80:
        return False
    if t.count("•") >= 2 or t.count("\n") >= 3:
        return True
    # Has numeric odds/prob already → treat as substantive
    if re.search(r"\d+(?:[.,]\d+)?\s*%|\bodds?\b|\bxG\b", t, re.I):
        return True
    return len(t) >= 220


def _looks_middleware(draft: str) -> bool:
    low = draft.lower()
    markers = (
        "sem inventar",
        "ainda sem fechar",
        "ainda sem lista",
        "me diga se quer",
        "diga o ângulo",
        "diga gols",
        "posso afunilar",
        "posso priorizar",
        "posso focar",
        "no contexto de",
        "sinais insuficientes",
        "continuando sobre",
        "mantendo foco",
        "mantendo o contexto",
    )
    hits = sum(1 for m in markers if m in low)
    return hits >= 2 or (hits >= 1 and len(draft) < 280)


def _label(inp: SportNlgInput) -> str:
    if inp.fixture:
        return inp.fixture
    if len(inp.teams) >= 2:
        return f"{inp.teams[0]} x {inp.teams[1]}"
    if inp.teams:
        return inp.teams[0]
    return "este confronto"


def _team_pair(inp: SportNlgInput) -> tuple[str | None, str | None]:
    if len(inp.teams) >= 2:
        return inp.teams[0], inp.teams[1]
    if inp.fixture:
        parts = re.split(r"\s+x\s+|\s+vs\s+", inp.fixture, flags=re.I)
        if len(parts) >= 2:
            return parts[0].strip(), parts[1].strip()
    if inp.teams:
        return inp.teams[0], None
    return None, None


def _confidence_clause(inp: SportNlgInput) -> str:
    label = (inp.confidence_label or "").lower()
    if label in {"weak", "insufficient", "low"}:
        return "A leitura ainda é **cautelosa** — faltam sinais para cravar."
    if label in {"adequate", "moderate", "medium"}:
        return "Confiança **moderada** com o que já temos em mão."
    if label in {"strong", "high", "good"}:
        return "Há **boa confiança** nos sinais disponíveis."
    if inp.confidence_score is not None:
        try:
            s = float(inp.confidence_score)
            # Heuristic bands without inventing a new score scale story
            if s <= 3.5:
                return "Por ora a confiança segue **baixa**."
            if s <= 6.5:
                return "A confiança está em um nível **moderado**."
            return "Os sinais disponíveis sustentam uma leitura **mais firme**."
        except (TypeError, ValueError):
            pass
    return ""


def _gap_clause(inp: SportNlgInput) -> str:
    if inp.missing_signals:
        joined = ", ".join(inp.missing_signals[:4])
        return f"Ainda não fechei: {joined}."
    if inp.no_bet:
        return "Sem stake recomendado até completar sinais (mercado, odd e confiança)."
    return ""


def _reason_bullets(inp: SportNlgInput, *, limit: int = 3) -> list[str]:
    out: list[str] = []
    for r in inp.reasoning:
        # Drop internal audit crumbs / confidence boilerplate
        low = r.lower()
        if low.startswith("response_selector") or low.startswith("8.4"):
            continue
        if "fail-open" in low or "softsections" in low:
            continue
        if low.startswith("confian") or "follow-up contextual" in low:
            continue
        if "response selector" in low or "hold candidate" in low:
            continue
        if "soft sections" in low or "preenchidas defensivamente" in low:
            continue
        # Avoid dumping huge methodology paragraphs
        if len(r) > 180:
            r = r[:177].rsplit(" ", 1)[0] + "…"
        if r and r not in out:
            out.append(r)
        if len(out) >= limit:
            break
    return out


def _compose_from_slots(
    inp: SportNlgInput,
    *,
    seed_draft: str | None = None,
) -> str:
    label = _label(inp)
    a, b = _team_pair(inp)
    frame = (inp.sport_intent or inp.intent or "").strip()
    parts: list[str] = []

    # Opening — analyst voice by frame
    if frame == "recent_form":
        if a and b:
            parts.append(
                f"Olhando a **fase recente** de **{a}** e **{b}** "
                f"no contexto de **{label}**."
            )
        else:
            parts.append(f"Olhando a **fase recente** em **{label}**.")
        parts.append(
            "Não vou inventar sequência de resultados sem dados fechados — "
            "a leitura fica qualitativa até entrarem estatísticas confirmadas."
        )
    elif frame == "compare_strength":
        if a and b:
            parts.append(
                f"No mano a mano entre **{a}** e **{b}** ({label}), "
                f"o comparativo de força ainda depende dos sinais que já temos."
            )
        else:
            parts.append(
                f"Para comparar forças em **{label}**, preciso do recorte certo "
                f"(favoritismo, forma ou mercado)."
            )
    elif frame == "bet_viability":
        parts.append(
            f"Sobre **valer a aposta** em **{label}**: a postura correta agora "
            f"é conservadora."
        )
        parts.append(
            "**No-bet** até haver mercado, odd e confiança alinhados — "
            "sem forçar entrada."
        )
    elif frame == "home_away_analysis":
        if a and b:
            parts.append(
                f"No **mando de campo** de **{label}**, o ponto é como "
                f"**{a}** e **{b}** se comportam em casa e fora."
            )
        else:
            parts.append(
                f"No **mando de campo** de **{label}**, o desempenho "
                f"casa/fora é o recorte que importa."
            )
        parts.append(
            "Sem estatísticas confirmadas de mando, evito cravar domínio."
        )
    elif frame == "market_question":
        parts.append(
            f"Para mercados em **{label}**, preciso do recorte "
            f"(gols, escanteios, cartões ou BTTS) antes de priorizar."
        )
    elif frame in {"analyze_match", "match_opinion"} or inp.intent == "analyze_match":
        parts.append(f"Leitura de analista para **{label}**.")
    else:
        parts.append(f"Seguindo o fio de **{label}**.")

    # Reasoning already present in payload
    bullets = _reason_bullets(inp)
    if bullets:
        parts.append("O que já conta a favor/contra nesta conversa:")
        for bult in bullets:
            parts.append(f"• {bult}")

    # Available signals
    if inp.available_signals:
        parts.append(
            "Sinais em mão: " + ", ".join(inp.available_signals[:5]) + "."
        )

    gap = _gap_clause(inp)
    if gap:
        parts.append(gap)

    conf = _confidence_clause(inp)
    if conf:
        parts.append(conf)

    # Soft next step (no invented content) — only if draft invited a choice
    seed = (seed_draft or inp.draft or "").lower()
    if any(
        k in seed
        for k in ("afunilar", "priorizar", "escolha", "recorte", "mercado específico")
    ):
        parts.append(
            "Se quiser, escolhemos o próximo recorte: forma, mando ou um mercado."
        )

    text = "\n\n".join(p for p in parts if p and p.strip())
    return text.strip()


def _light_polish(draft: str, inp: SportNlgInput) -> str:
    """De-roboticize without changing factual claims."""
    text = draft
    replacements = [
        (
            re.compile(r"(?i)\bcom\s+\*{0,2}dados\s+parciais\*{0,2}\s*…?"),
            "Com o que já dá para ler (ainda parcial)",
        ),
        (
            re.compile(r"(?i)\bsinais\s+dispon[ií]veis\s*:"),
            "O que já tenho:",
        ),
        (
            re.compile(r"(?i)\bainda\s+n[aã]o\s+tenho\s*:"),
            "Ainda falta:",
        ),
        (
            re.compile(r"(?i)\bno-bet\s*:\s*sinais\s+insuficientes\s+para\s+stake\.?"),
            "Por ora, **no-bet** — sinais insuficientes para stake.",
        ),
        (
            re.compile(r"(?i)\bpara\s+subir\s+confian[cç]a\s*:"),
            "Para ganhar confiança:",
        ),
        (
            re.compile(r"(?i)\bleitura\s+preliminar\s*\(qualitativa\)\s*:"),
            "Leitura preliminar:",
        ),
        (
            re.compile(r"(?i)\bnota\s+do\s+motor\s*\(quando\s+dispon[ií]vel\)\s*:"),
            "Nota da análise:",
        ),
        (
            re.compile(r"(?i)\bmantendo\s+foco\s+"),
            "Continuando em ",
        ),
        (
            re.compile(r"(?i)\bcontinuando\s+sobre\s+\*{0,2}"),
            "Ainda no fio de ",
        ),
    ]
    for pat, repl in replacements:
        text = pat.sub(repl, text)

    # Optional short confidence coda if draft lacked one and we have a label
    if inp.confidence_label and "confiança" not in text.lower():
        coda = _confidence_clause(inp)
        if coda and len(text) < 900:
            text = text.rstrip() + "\n\n" + coda

    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _preserve_numeric_claims(original: str, rewritten: str) -> str:
    """
    If the original contained percents/odds-like numbers missing from rewrite,
    append a short factual line — never invent new numbers.
    """
    if not original or not rewritten:
        return rewritten
    nums = re.findall(
        r"\b\d+(?:[.,]\d+)?\s*%|\b(?:odd|odds)\s*[:=]?\s*\d+(?:[.,]\d+)?",
        original,
        flags=re.I,
    )
    if not nums:
        return rewritten
    missing = [n for n in nums if n not in rewritten]
    if not missing:
        return rewritten
    # Keep at most 3 original numeric tokens as a fidelity appendix
    uniq: list[str] = []
    for n in missing:
        if n not in uniq:
            uniq.append(n)
        if len(uniq) >= 3:
            break
    appendix = "Números já citados na análise: " + ", ".join(uniq) + "."
    return rewritten.rstrip() + "\n\n" + appendix
