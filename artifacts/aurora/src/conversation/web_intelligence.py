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

WEB_TIMEOUT_S = 2.8


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
    EARLY web fetch — BEFORE draft. Stores ctx['web_thinking'].
    Controlled by DeepThinking.needs_web / web_need.
    """
    audit: dict[str, Any] = {
        "need": "none",
        "reason": "not_run",
        "query": None,
        "result_count": 0,
        "summary": None,
        "used_in_reasoning": False,
        "changed_reasoning": False,
        "status": "skipped",
    }
    try:
        thinking = (ctx or {}).get("deep_thinking") or {}
        decision = decide_need_web(message, ctx=ctx)
        audit.update(decision.to_dict())
        if decision.need == "none":
            audit["status"] = "skipped"
            logger.warning(
                "[AUDIT] WebInfluence: summary_used=False changed_reasoning=False "
                "need=none (pre-draft skip)"
            )
            if ctx is not None:
                ctx["web_thinking"] = audit
                ctx["last_need_web"] = audit
            return audit

        topic = decision.topic or thinking.get("topic_team") or message[:80]
        if decision.reason.startswith("deep_thinking") and thinking.get("topic_kind") == "historical":
            query = f"Copa do Mundo futebol {message}"
        elif decision.need == "optional" and topic:
            query = f"{topic} futebol momento atual noticias"
        else:
            query = f"{message} futebol"
        audit["query"] = query

        try:
            snippet = await asyncio.wait_for(
                _duckduckgo_snippet(query),
                timeout=WEB_TIMEOUT_S + 0.2,
            )
        except Exception:
            snippet = None

        if snippet:
            short = re.sub(r"\s+", " ", snippet)[:200]
            audit["summary"] = short
            audit["result_count"] = 1
            audit["status"] = "ready_for_reasoning"
            logger.warning(
                "[AUDIT] WebInfluence: pre-draft ready query=%r summary=%r",
                query,
                short[:80],
            )
        else:
            audit["status"] = "fallback_no_web"
            audit["result_count"] = 0
            logger.warning(
                "[AUDIT] WebInfluence: summary_used=False changed_reasoning=False "
                "status=fallback_no_web query=%r",
                query,
            )

        if ctx is not None:
            ctx["web_thinking"] = audit
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
    """
    WEB alters reasoning — weave into draft BEFORE finalization.
    Returns (new_draft, changed).
    """
    try:
        web = (ctx or {}).get("web_thinking") or {}
        summary = (web.get("summary") or "").strip()
        if not summary or web.get("status") not in {"ready_for_reasoning", "enriched"}:
            return draft, False

        thinking = (ctx or {}).get("deep_thinking") or {}
        team_name = team or thinking.get("topic_team") or "esse time"
        # Reasoning bridge — not a raw append dump
        bridge = (
            f"Minha percepção sobre o {team_name}, olhando o momento e o que aparece "
            f"no contexto público recente ({summary.rstrip('.')}), é que isso muda "
            f"o peso da conversa: eu não trato só a camisa — trato o agora."
        )
        body = (draft or "").strip()
        # Insert bridge after first paragraph when possible
        parts = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
        if len(parts) >= 2:
            woven = parts[0] + "\n\n" + bridge + "\n\n" + "\n\n".join(parts[1:])
        elif body:
            woven = body + "\n\n" + bridge
        else:
            woven = bridge

        web["used_in_reasoning"] = True
        web["changed_reasoning"] = True
        web["summary_used"] = True
        web["status"] = "woven"
        if ctx is not None:
            ctx["web_thinking"] = web
            ctx["last_need_web"] = web
        logger.warning(
            "[AUDIT] WebInfluence: summary_used=True changed_reasoning=True "
            "summary=%r",
            summary[:80],
        )
        return woven, True
    except Exception as exc:
        logger.warning("weave_web_into_draft fail-open: %s", exc)
        return draft, False


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
