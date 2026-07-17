"""
Aurora v4.7 — NeedWebReasoner + lightweight Web Intelligence (fail-open).

Principle:
  Not every question needs the web.
  Web never blocks the system (timeout + fallback).

Does NOT alter frozen engines. Additive.
"""

from __future__ import annotations

import asyncio
import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Literal

logger = logging.getLogger(__name__)

WebNeed = Literal["none", "optional", "required"]
WebMode = Literal["none", "light", "deep", "research"]

WEB_TIMEOUT_S = 2.8


def decide_web_mode(
    message: str,
    ctx: dict[str, Any] | None = None,
) -> WebMode:
    """NONE | LIGHT | DEEP | RESEARCH from DeepThinking + message."""
    thinking = (ctx or {}).get("deep_thinking") if isinstance(ctx, dict) else {}
    thinking = thinking if isinstance(thinking, dict) else {}
    if thinking.get("web_mode") in {"none", "light", "deep", "research"}:
        return thinking["web_mode"]  # type: ignore[return-value]
    folded = _fold(message)
    kind = thinking.get("topic_kind")
    if thinking.get("web_need") == "none" or kind in {
        "calendar",
        "fixture",
        "kickoff",
        "emotional",
    }:
        return "none"
    if re.search(
        r"\b(analise\s+detalhada|analise\s+completa|pesquisa\s+profunda|"
        r"faca\s+uma\s+analise|relatorio\s+detalhado)\b",
        folded,
    ):
        return "research"
    if kind == "moment" or re.search(
        r"\b(como\s+esta|atualmente|momento\s+atual)\b", folded
    ):
        return "deep"
    if kind in {"opinion", "historical", "outlook"} or thinking.get("needs_web"):
        return "light" if kind == "opinion" else "deep"
    if thinking.get("web_need") in {"optional", "required"}:
        return "deep" if thinking.get("web_need") == "required" else "light"
    return "none"


def synthesize_web_context(
    *,
    snippets: list[str],
    team: str | None,
    mode: WebMode,
    message: str,
) -> dict[str, Any]:
    """WEB builds knowledge for the brain — does not write the answer."""
    facts: list[str] = []
    narratives: list[str] = []
    recent: list[str] = []
    conf = 0.0
    for snip in snippets:
        clean = re.sub(r"\s+", " ", (snip or "")).strip()
        if not clean:
            continue
        short = clean[:220]
        facts.append(short)
        if re.search(
            r"\b(hoje|ontem|semana|mes|202[4-9]|contrato|lesao|tecnico|classific)\b",
            _fold(short),
        ):
            recent.append(short[:160])
        narratives.append(short[:180])
    if facts:
        conf = (
            min(0.55 + 0.15 * len(facts), 0.9)
            if mode == "research"
            else min(0.45 + 0.12 * len(facts), 0.75)
        )
    return {
        "facts": facts[:5],
        "narratives": narratives[:3],
        "recent_events": recent[:3],
        "confidence": round(conf, 2),
        "team": team,
        "mode": mode,
        "query_hint": (message or "")[:80],
    }


def build_reasoning_from_web(
    web_context: dict[str, Any],
    *,
    team: str | None = None,
    moment: bool = False,
) -> str:
    """Draft born FROM web_context (or local fail-open)."""
    team_name = team or web_context.get("team") or "esse time"
    facts = web_context.get("facts") or []
    recent = web_context.get("recent_events") or []
    conf = float(web_context.get("confidence") or 0)
    if facts and conf >= 0.4:
        fact_line = recent[0] if recent else facts[0]
        return (
            f"Olhando o {team_name} agora, o que pesa no meu raciocínio "
            f"não é só a camisa — é o recorte público recente.\n\n"
            f"O que aparece no contexto: {fact_line.rstrip('.')}. "
            f"Isso me faz enxergar o momento com mais nuance — "
            f"{'identidade e regularidade' if moment else 'leitura sem veredito engessado'} "
            f"em vez de opinião automática.\n\n"
            f"Se quiser, a gente aprofunda o próximo confronto do {team_name}."
        )
    try:
        from src.conversation.brain_authority import opinion_local_reasoning

        return opinion_local_reasoning(str(team_name), moment=moment)
    except Exception:
        return (
            f"Sobre o {team_name}: sem um recorte fresco confirmado, "
            f"eu olharia momento, elenco e adversário antes de cravar."
        )


def _fold(text: str) -> str:
    raw = unicodedata.normalize("NFKD", text or "")
    raw = "".join(c for c in raw if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", raw.lower()).strip()


@dataclass
class WebDecision:
    need: WebNeed
    reason: str
    topic: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"need": self.need, "reason": self.reason, "topic": self.topic}


def decide_need_web(
    message: str,
    *,
    intent: str | None = None,
    entities: dict[str, Any] | None = None,
    ctx: dict[str, Any] | None = None,
) -> WebDecision:
    """
    CASO 1 none — analyze / odds / stats / calendar API
    CASO 2 optional — team opinion / how is the team
    CASO 3 required — historical world-cup style questions

    DeepThinking Decision Engine overrides when present on ctx.
    """
    # ── DeepThinking CONTROL (not cosmetic) ─────────────────────────────
    try:
        thinking = (ctx or {}).get("deep_thinking") if isinstance(ctx, dict) else None
        if isinstance(thinking, dict) and thinking.get("web_need") in {
            "none",
            "optional",
            "required",
        }:
            wn = thinking["web_need"]
            topic = thinking.get("topic_team")
            if thinking.get("topic_kind") == "historical":
                topic = topic or "copa_mundo"
            return WebDecision(
                wn,  # type: ignore[arg-type]
                f"deep_thinking:{thinking.get('topic_kind') or 'decide'}",
                str(topic) if topic else None,
            )
    except Exception:
        pass

    folded = _fold(message)
    ents = entities or {}

    # Never web for social / emotional / capabilities
    if intent in {
        "small_talk",
        "greeting",
        "emotional",
        "capabilities",
        "help",
        "identity",
    }:
        return WebDecision("none", "social_or_meta")

    if ents.get("natural_kind") in {
        "calendar_today",
        "calendar_tomorrow",
        "calendar_round",
        "had_games_today",
        "capabilities",
        "hobbies",
    }:
        return WebDecision("none", "calendar_or_meta_uses_api")

    # Explicit analysis / markets → API only
    if intent in {"analyze_match", "live_opportunities", "follow_up"}:
        return WebDecision("none", "analysis_api_only")
    if re.search(
        r"\b(analis[ae]|estatistic|odds|probabilidade|classificacao|"
        r"escanteio|over|under|btts)\b",
        folded,
    ):
        return WebDecision("none", "stats_markets_api")

    # historical from entities
    if ents.get("historical_copa") or ents.get("natural_kind") == "historical_copa":
        return WebDecision("required", "historical_narrative", "copa_mundo")

    # World-cup / historical narrative → required (still fail-open)
    if re.search(
        r"\b(copa\s+(?:do\s+mundo\s+)?(?:de\s+)?20\d{2}|mundial\s+de\s+20\d{2}|"
        r"o\s+que\s+achou\s+da\s+copa)\b",
        folded,
    ):
        topic = "copa_mundo"
        return WebDecision("required", "historical_narrative", topic)

    # Team moment / what happened → optional enrich
    if ents.get("natural_kind") == "team_opinion" or ents.get("opinion_time"):
        team = str(ents.get("team") or "")
        return WebDecision("optional", "team_narrative", team or None)

    if re.search(
        r"\b(como\s+esta\s+o|o\s+que\s+aconteceu\s+com|momento\s+d[oe]|"
        r"fase\s+d[oe]|noticias?\s+d[oe]|atualmente)\b",
        folded,
    ):
        return WebDecision("optional", "team_or_club_moment")

    return WebDecision("none", "default_no_web")


async def gather_web_for_thinking(
    message: str,
    ctx: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    EARLY web fetch + synthesis — BEFORE draft.
    NeedWeb → Gather → Synthesis → reasoning uses web_context.
    """
    audit: dict[str, Any] = {
        "need": "none",
        "mode": "none",
        "reason": "not_run",
        "query": None,
        "result_count": 0,
        "summary": None,
        "web_context": None,
        "used_in_reasoning": False,
        "changed_reasoning": False,
        "status": "skipped",
    }
    try:
        thinking = (ctx or {}).get("deep_thinking") or {}
        mode = decide_web_mode(message, ctx)
        audit["mode"] = mode
        decision = decide_need_web(message, ctx=ctx)
        audit["reason"] = decision.reason
        audit["topic"] = decision.topic
        audit["need"] = decision.need if mode != "none" else "none"

        if mode == "none" or decision.need == "none":
            audit["status"] = "skipped"
            audit["need"] = "none"
            logger.warning(
                "[AUDIT] WebInfluence: mode=none summary_used=False changed_reasoning=False"
            )
            if ctx is not None:
                ctx["web_thinking"] = audit
                ctx["web_context"] = None
                ctx["last_need_web"] = audit
            return audit

        topic = (
            decision.topic
            or thinking.get("topic_team")
            or thinking.get("topic_fixture")
            or message[:80]
        )
        if mode == "research":
            queries = [
                f"{topic} futebol 2026 desempenho analise",
                f"{topic} temporada atual noticias",
                f"{topic} elenco tecnico momento",
            ]
        elif mode == "deep":
            queries = [
                f"{topic} futebol momento atual noticias",
                f"{topic} resultados recentes",
            ]
        else:
            queries = [f"{topic} futebol momento atual"]

        snippets: list[str] = []
        sources_used: list[str] = []
        used_query = queries[0]
        for q in queries:
            used_query = q
            try:
                snippet = await asyncio.wait_for(
                    _duckduckgo_snippet(q),
                    timeout=WEB_TIMEOUT_S + 0.2,
                )
            except Exception:
                snippet = None
            if snippet:
                snippets.append(snippet)
                if "duckduckgo" not in sources_used:
                    sources_used.append("duckduckgo")
            if mode == "light" and snippets:
                break
            if mode == "deep" and len(snippets) >= 1:
                break
            if mode == "research" and len(snippets) >= 2:
                break

        # Secondary knowledge for DEEP/RESEARCH when DDG is empty — real extract.
        if mode in {"deep", "research"} and len(snippets) < (2 if mode == "research" else 1):
            wiki_topic = str(
                thinking.get("topic_team")
                or decision.topic
                or topic
                or message
            )[:80]
            try:
                wiki = await asyncio.wait_for(
                    _wikipedia_summary(wiki_topic),
                    timeout=WEB_TIMEOUT_S + 0.2,
                )
            except Exception:
                wiki = None
            if wiki:
                snippets.append(wiki)
                sources_used.append("wikipedia")
                if not used_query:
                    used_query = f"wikipedia:{wiki_topic}"

        audit["query"] = used_query
        audit["sources_used"] = sources_used
        team = thinking.get("topic_team") or (str(topic).split()[0] if topic else None)
        web_ctx = synthesize_web_context(
            snippets=snippets,
            team=str(team) if team else None,
            mode=mode,
            message=message,
        )
        audit["web_context"] = web_ctx
        audit["result_count"] = len(snippets)

        if snippets:
            short = re.sub(r"\s+", " ", snippets[0])[:200]
            audit["summary"] = short
            audit["status"] = "ready_for_reasoning"
            audit["changed_reasoning"] = True
            logger.warning(
                "[AUDIT] WebSynthesis: mode=%s facts=%d conf=%.2f sources=%s query=%r",
                mode,
                len(web_ctx.get("facts") or []),
                float(web_ctx.get("confidence") or 0),
                sources_used,
                used_query,
            )
        else:
            audit["status"] = "fallback_no_web"
            audit["sources_used"] = []
            web_ctx["confidence"] = 0.0
            audit["changed_reasoning"] = True
            audit["local_reasoning"] = True
            logger.warning(
                "[AUDIT] WebSynthesis: mode=%s status=fallback_no_web "
                "local_reasoning query=%r",
                mode,
                used_query,
            )

        if ctx is not None:
            ctx["web_thinking"] = audit
            ctx["web_context"] = web_ctx
            ctx["last_need_web"] = audit
        return audit
    except Exception as exc:
        logger.warning("gather_web_for_thinking fail-open: %s", exc)
        if ctx is not None:
            ctx["web_thinking"] = audit
        return audit


def weave_web_into_draft(
    draft: str,
    ctx: dict[str, Any] | None = None,
    *,
    team: str | None = None,
) -> tuple[str, bool]:
    """Prefer web_context synthesis over raw snippet append."""
    try:
        thinking = (ctx or {}).get("deep_thinking") or {}
        team_name = team or thinking.get("topic_team") or "esse time"
        moment = thinking.get("topic_kind") == "moment"
        web_ctx = (ctx or {}).get("web_context")
        web = (ctx or {}).get("web_thinking") or {}

        if isinstance(web_ctx, dict) and (
            web_ctx.get("facts")
            or web.get("status") == "fallback_no_web"
            or web.get("local_reasoning")
        ):
            reasoned = build_reasoning_from_web(
                web_ctx, team=str(team_name), moment=moment
            )
            if reasoned:
                web = dict(web)
                web["used_in_reasoning"] = True
                web["changed_reasoning"] = True
                web["summary_used"] = bool(web_ctx.get("facts"))
                web["status"] = "woven"
                if ctx is not None:
                    ctx["web_thinking"] = web
                    ctx["last_need_web"] = web
                logger.warning(
                    "[AUDIT] WebInfluence: summary_used=%s changed_reasoning=True "
                    "via=web_synthesis",
                    bool(web_ctx.get("facts")),
                )
                return reasoned, True

        summary = (web.get("summary") or "").strip()
        if not summary or web.get("status") not in {"ready_for_reasoning", "enriched"}:
            return draft, False

        bridge = (
            f"Minha percepção sobre o {team_name}, olhando o momento e o que aparece "
            f"no contexto público recente ({summary.rstrip('.')}), é que isso muda "
            f"o peso da conversa: eu não trato só a camisa — trato o agora."
        )
        body = (draft or "").strip()
        parts = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
        if len(parts) >= 2:
            woven = parts[0] + "\n\n" + bridge + "\n\n" + "\n\n".join(parts[1:])
        elif body:
            woven = body + "\n\n" + bridge
        else:
            woven = bridge
        web = dict(web)
        web["used_in_reasoning"] = True
        web["changed_reasoning"] = True
        web["summary_used"] = True
        web["status"] = "woven"
        if ctx is not None:
            ctx["web_thinking"] = web
            ctx["last_need_web"] = web
        return woven, True
    except Exception as exc:
        logger.warning("weave_web_into_draft fail-open: %s", exc)
        return draft, False


async def _wikipedia_summary(topic: str) -> str | None:
    """Secondary knowledge source for RESEARCH/DEEP — fail-open."""
    try:
        import httpx

        raw = (topic or "").strip()
        if not raw:
            return None
        folded = _fold(raw)
        # Known Brazilian clubs → canonical PT titles (knowledge, not fluff)
        club_map = {
            "flamengo": "Clube_de_Regatas_do_Flamengo",
            "botafogo": "Botafogo_de_Futebol_e_Regatas",
            "santos": "Santos_Futebol_Clube",
            "bahia": "Esporte_Clube_Bahia",
            "gremio": "Grêmio_Foot-Ball_Porto_Alegrense",
            "mirassol": "Mirassol_Futebol_Clube",
            "juventus": "Juventus_Football_Club",
        }
        candidates: list[tuple[str, str]] = []
        for key, title in club_map.items():
            if key in folded:
                candidates.append(("pt", title))
                candidates.append(("en", title))
                break
        slug = raw.replace(" ", "_")[:80]
        if not candidates:
            candidates = [("pt", slug), ("en", slug)]
        headers = {"Accept": "application/json", "User-Agent": "AuroraStats/1.0"}
        async with httpx.AsyncClient(timeout=WEB_TIMEOUT_S) as client:
            for lang, cand in candidates[:4]:
                url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{cand}"
                resp = await client.get(url, headers=headers)
                if resp.status_code != 200:
                    continue
                data = resp.json()
                extract = (data.get("extract") or "").strip()
                if extract and len(extract) > 40:
                    return extract[:450]
        return None
    except Exception as exc:
        logger.warning("wikipedia summary fail-open: %s", exc)
        return None


async def _duckduckgo_snippet(query: str) -> str | None:
    """
    Best-effort public snippet via DuckDuckGo Instant Answer API.
    No API key. Timeout-bound. Fail-open → None.
    """
    try:
        import httpx

        url = "https://api.duckduckgo.com/"
        params = {"q": query, "format": "json", "no_html": 1, "skip_disambig": 1}
        async with httpx.AsyncClient(timeout=WEB_TIMEOUT_S) as client:
            resp = await client.get(url, params=params)
        if resp.status_code != 200:
            return None
        data = resp.json()
        text = (data.get("AbstractText") or "").strip()
        if text:
            return text[:320]
        # Related topics fallback
        related = data.get("RelatedTopics") or []
        for item in related[:3]:
            if isinstance(item, dict) and item.get("Text"):
                return str(item["Text"])[:320]
        return None
    except Exception as exc:
        logger.warning("web snippet fail-open: %s", exc)
        return None


def _humanize_web_note(snippet: str, topic: str | None) -> str:
    clean = re.sub(r"\s+", " ", snippet or "").strip()
    if not clean:
        return ""
    # Feed thinking — not a raw dump
    lead = (
        "Isso ajuda meu raciocínio: no contexto público recente, "
    )
    return lead + clean


async def maybe_enrich_with_web(
    message: str,
    payload: dict[str, Any],
    *,
    intent: str | None = None,
    ctx: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Late WEB pass — SKIP if pre-draft already wove reasoning.
    Prefer gather_web_for_thinking + weave_web_into_draft.
    """
    try:
        if not isinstance(payload, dict):
            return payload

        # Already influenced reasoning — do NOT append again
        web_early = (ctx or {}).get("web_thinking") if isinstance(ctx, dict) else None
        if isinstance(web_early, dict) and (
            web_early.get("used_in_reasoning")
            or web_early.get("changed_reasoning")
            or web_early.get("status") == "woven"
        ):
            meta = dict(payload.get("response_metadata") or {})
            audit = dict(web_early)
            audit["late_pass"] = "skipped_already_woven"
            meta["need_web"] = audit
            if ctx is not None:
                ctx["last_need_web"] = audit
            payload["response_metadata"] = meta
            logger.warning(
                "[AUDIT] WebInfluence: summary_used=%s changed_reasoning=%s "
                "late_pass=skipped_already_woven",
                bool(web_early.get("summary_used") or web_early.get("summary")),
                bool(web_early.get("changed_reasoning")),
            )
            return payload

        original_summary = payload.get("executive_summary")
        original_final = payload.get("final_recommendation")

        ents = dict(payload.get("entities") or {})
        if (
            ents.get("emotional")
            or ents.get("profile_memory")
            or ents.get("human_presence")
            or ents.get("social")
        ):
            meta = dict(payload.get("response_metadata") or {})
            audit = {
                "need": "none",
                "reason": "presence_or_profile",
                "topic": None,
                "query": None,
                "result_count": 0,
                "summary": None,
                "used_in_response": False,
                "status": "skipped",
            }
            meta["need_web"] = audit
            if ctx is not None:
                ctx["last_need_web"] = audit
            payload["response_metadata"] = meta
            return payload

        # Prefer early web summary if ready but not yet woven into this payload
        if (
            isinstance(web_early, dict)
            and web_early.get("summary")
            and web_early.get("status") == "ready_for_reasoning"
        ):
            team = (ents.get("team") or (ctx or {}).get("deep_thinking", {}).get("topic_team"))
            woven, changed = weave_web_into_draft(
                str(original_summary or ""),
                ctx,
                team=str(team) if team else None,
            )
            if changed:
                payload["executive_summary"] = woven
                if original_final == original_summary or not original_final:
                    payload["final_recommendation"] = woven
                meta = dict(payload.get("response_metadata") or {})
                meta["need_web"] = dict((ctx or {}).get("web_thinking") or web_early)
                payload["response_metadata"] = meta
                return payload

        # historical_copa entity → required
        if ents.get("historical_copa") or ents.get("natural_kind") == "historical_copa":
            decision = WebDecision("required", "historical_narrative", "copa_mundo")
        else:
            decision = decide_need_web(
                message, intent=intent, entities=ents, ctx=ctx
            )
        meta = dict(payload.get("response_metadata") or {})
        audit = decision.to_dict()
        audit.update(
            {
                "query": None,
                "result_count": 0,
                "summary": None,
                "used_in_response": False,
            }
        )
        meta["need_web"] = audit

        if decision.need == "none":
            audit["status"] = "skipped"
            logger.warning(
                "[AUDIT] NeedWeb: decision=%s reason=%s query=%r result_count=0 "
                "summary=%r used_in_response=False status=skipped",
                decision.need,
                decision.reason,
                None,
                None,
            )
            if ctx is not None:
                ctx["last_need_web"] = audit
            payload["response_metadata"] = meta
            return payload

        topic = decision.topic or ents.get("team") or message[:80]
        query = str(topic)
        if decision.reason == "team_narrative" and topic:
            query = f"{topic} futebol momento atual noticias"
        elif decision.reason == "historical_narrative":
            query = f"Copa do Mundo {topic or ''} futebol resumo"
        if "copa" in _fold(message):
            query = f"{message} futebol"
        audit["query"] = query
        meta["need_web"] = audit

        logger.warning(
            "[AUDIT] NeedWeb: decision=%s reason=%s query=%r (fetching…)",
            decision.need,
            decision.reason,
            query,
        )

        try:
            snippet = await asyncio.wait_for(
                _duckduckgo_snippet(query),
                timeout=WEB_TIMEOUT_S + 0.2,
            )
        except Exception as fetch_exc:
            logger.warning(
                "[AUDIT] NeedWeb: decision=%s query=%r result_count=0 "
                "summary=%r used_in_response=False status=error err=%s",
                decision.need,
                query,
                None,
                fetch_exc,
            )
            snippet = None

        if not snippet:
            payload["executive_summary"] = original_summary
            payload["final_recommendation"] = original_final
            audit["status"] = "fallback_no_web"
            audit["result_count"] = 0
            audit["used_in_response"] = False
            # Local thinking note when web required/optional fails
            if decision.need == "required" and is_empty_ish(original_summary):
                try:
                    from src.conversation.intelligence_fallback import build_copa_opinion

                    local = build_copa_opinion()
                    payload["executive_summary"] = local
                    payload["final_recommendation"] = local
                    audit["used_in_response"] = False
                    audit["summary"] = "local_thinking_fallback"
                except Exception:
                    pass
            meta["need_web"] = audit
            if ctx is not None:
                ctx["last_need_web"] = audit
            logger.warning(
                "[AUDIT] NeedWeb: decision=%s reason=%s query=%r result_count=0 "
                "summary=%r used_in_response=%s status=fallback_no_web",
                decision.need,
                decision.reason,
                query,
                audit.get("summary"),
                audit.get("used_in_response"),
            )
            payload["response_metadata"] = meta
            return payload

        note = _humanize_web_note(snippet, decision.topic)
        short_sum = re.sub(r"\s+", " ", snippet or "")[:160]
        audit["summary"] = short_sum
        if note:
            if len(note) > 320:
                note = note[:320].rsplit(" ", 1)[0].rstrip() + "…"
            summary = str(original_summary or "").rstrip()
            # Weave into thinking — prefer insert before closing invite
            if summary:
                combined = summary + "\n\n" + note
            else:
                combined = note
            payload["executive_summary"] = combined
            if original_final == original_summary or not original_final:
                payload["final_recommendation"] = combined
            audit["status"] = "enriched"
            audit["note_len"] = len(note)
            audit["result_count"] = 1
            audit["used_in_response"] = True
            logger.warning(
                "[AUDIT] NeedWeb: decision=%s reason=%s query=%r result_count=1 "
                "summary=%r used_in_response=True status=enriched",
                decision.need,
                decision.reason,
                query,
                short_sum[:80],
            )
        else:
            payload["executive_summary"] = original_summary
            payload["final_recommendation"] = original_final
            audit["status"] = "empty"
            audit["result_count"] = 0
            audit["used_in_response"] = False
            logger.warning(
                "[AUDIT] NeedWeb: decision=%s reason=%s query=%r result_count=0 "
                "summary=%r used_in_response=False status=empty",
                decision.need,
                decision.reason,
                query,
                None,
            )

        meta["need_web"] = audit
        if ctx is not None:
            ctx["last_need_web"] = audit
        payload["response_metadata"] = meta
        return payload
    except Exception as exc:
        logger.warning("maybe_enrich_with_web fail-open: %s", exc)
        return payload


def is_empty_ish(text: Any) -> bool:
    t = str(text or "").strip()
    return (not t) or t in {"?", ".", "-", "…", "..."}


# ── Future Semantic Cache stub (not fully implemented) ─────────────────────

_CACHE_ENTITIES = (
    "Botafogo",
    "Bahia",
    "Flamengo",
    "Brasileirão",
    "Libertadores",
)


def semantic_cache_plan() -> dict[str, Any]:
    """Architecture stub for Background Refresh — no live cache yet."""
    return {
        "status": "prepared_not_active",
        "entities": list(_CACHE_ENTITIES),
        "layers": ["semantic_cache", "background_refresh"],
        "note": "v4.7 preparation only — no weights/engines changed.",
    }
