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
) -> WebDecision:
    """
    CASO 1 none — analyze / odds / stats / calendar API
    CASO 2 optional — team opinion / how is the team
    CASO 3 required — historical world-cup style questions
    """
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
        r"fase\s+d[oe]|noticias?\s+d[oe])\b",
        folded,
    ):
        return WebDecision("optional", "team_or_club_moment")

    return WebDecision("none", "default_no_web")


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
    # Never dump as "According to source"
    lead = "No momento, o que mais aparece no contexto público é: "
    return lead + clean


async def maybe_enrich_with_web(
    message: str,
    payload: dict[str, Any],
    *,
    intent: str | None = None,
    ctx: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Optionally append a short human narrative note from the web.
    Never invents markets. Never blocks.
    WEB failure → original payload narrative untouched.
    """
    try:
        if not isinstance(payload, dict):
            return payload

        original_summary = payload.get("executive_summary")
        original_final = payload.get("final_recommendation")

        ents = dict(payload.get("entities") or {})
        # Never enrich presence / profile / emotional turns
        if (
            ents.get("emotional")
            or ents.get("profile_memory")
            or ents.get("human_presence")
            or ents.get("social")
        ):
            meta = dict(payload.get("response_metadata") or {})
            meta["need_web"] = {
                "need": "none",
                "reason": "presence_or_profile",
                "topic": None,
                "status": "skipped",
            }
            payload["response_metadata"] = meta
            return payload

        decision = decide_need_web(message, intent=intent, entities=ents)
        meta = dict(payload.get("response_metadata") or {})
        meta["need_web"] = decision.to_dict()

        if decision.need == "none":
            payload["response_metadata"] = meta
            return payload

        topic = decision.topic or ents.get("team") or message[:80]
        query = str(topic)
        if decision.reason == "team_narrative" and topic:
            query = f"{topic} futebol momento atual"
        elif decision.reason == "historical_narrative":
            query = f"{message} futebol"

        try:
            snippet = await asyncio.wait_for(
                _duckduckgo_snippet(query),
                timeout=WEB_TIMEOUT_S + 0.2,
            )
        except Exception:
            snippet = None

        if not snippet:
            # Fail-open: restore exact narrative
            payload["executive_summary"] = original_summary
            payload["final_recommendation"] = original_final
            meta["need_web"]["status"] = "fallback_no_web"
            payload["response_metadata"] = meta
            return payload

        note = _humanize_web_note(snippet, decision.topic)
        if note:
            # Cap note so optional enrich doesn't turn a short chat into a report
            if len(note) > 280:
                note = note[:280].rsplit(" ", 1)[0].rstrip() + "…"
            summary = str(original_summary or "").rstrip()
            combined = (summary + "\n\n" + note) if summary else note
            payload["executive_summary"] = combined
            if original_final == original_summary or not original_final:
                payload["final_recommendation"] = combined
            meta["need_web"]["status"] = "enriched"
            meta["need_web"]["note_len"] = len(note)
        else:
            payload["executive_summary"] = original_summary
            payload["final_recommendation"] = original_final
            meta["need_web"]["status"] = "empty"

        payload["response_metadata"] = meta
        return payload
    except Exception as exc:
        logger.warning("maybe_enrich_with_web fail-open: %s", exc)
        return payload


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
