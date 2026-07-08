"""
Aurora Knowledge Engine — consult internal knowledge before every recommendation.

The engine searches the knowledge_items table across all 13 categories
and returns a KnowledgeContext that enriches every decision:

  • golden_rules  — always applied, never skipped
  • red_flags     — signals that reduce confidence or block bets
  • relevant_items — contextually relevant rules for this specific match

Public API
----------
  consult(hn, an, league, is_live, has_xg, has_referee, meth_score) -> KnowledgeContext
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

CATEGORIES = [
    "methodology",
    "betting_rules",
    "bankroll_rules",
    "market_rules",
    "live_rules",
    "pre_match_rules",
    "referee_rules",
    "league_rules",
    "team_rules",
    "psychology",
    "risk_management",
    "red_flags",
    "golden_rules",
]


@dataclass
class KnowledgeItem:
    id:          int
    category:    str
    title:       str
    description: str
    examples:    list[str]
    confidence:  float
    version:     str
    source:      str
    tags:        str
    created_at:  str


@dataclass
class KnowledgeContext:
    """Knowledge retrieved and applied before a decision is generated."""

    golden_rules:     list[KnowledgeItem] = field(default_factory=list)
    red_flags:        list[KnowledgeItem] = field(default_factory=list)
    relevant_items:   list[KnowledgeItem] = field(default_factory=list)

    red_flags_triggered: list[str]        = field(default_factory=list)
    golden_rules_applied: list[str]       = field(default_factory=list)
    knowledge_notes:  list[str]           = field(default_factory=list)

    @property
    def total_consulted(self) -> int:
        return len(self.golden_rules) + len(self.red_flags) + len(self.relevant_items)

    def to_notes(self) -> list[str]:
        notes = []
        for rule in self.golden_rules:
            notes.append(f"[GOLDEN RULE] {rule.title}: {rule.description[:120]}")
        for flag in self.red_flags_triggered:
            notes.append(f"[RED FLAG] {flag}")
        for item in self.relevant_items[:5]:
            notes.append(f"[{item.category.upper().replace('_', ' ')}] {item.title}: {item.description[:100]}")
        return notes


def _to_item(row: dict) -> KnowledgeItem:
    import json as _json
    ex = row.get("examples", "[]") or "[]"
    try:
        examples = _json.loads(ex) if ex.startswith("[") else [e.strip() for e in ex.split("|") if e.strip()]
    except Exception:
        examples = [ex] if ex else []
    return KnowledgeItem(
        id=int(row.get("id", 0)),
        category=row.get("category", ""),
        title=row.get("title", ""),
        description=row.get("description", ""),
        examples=examples,
        confidence=float(row.get("confidence", 0.8)),
        version=str(row.get("version", "1.0")),
        source=str(row.get("source", "aurora")),
        tags=str(row.get("tags", "")),
        created_at=str(row.get("created_at", "")),
    )


def consult(
    hn:           str,
    an:           str,
    league:       str | None = None,
    is_live:      bool = False,
    has_xg:       bool = False,
    has_referee:  bool = False,
    meth_score:   float = 0.0,
) -> KnowledgeContext:
    """
    Search knowledge before generating a recommendation.

    Strategy
    --------
    1. Always fetch golden_rules (override everything)
    2. Always fetch red_flags and evaluate which are triggered
    3. Search for team/league specific knowledge
    4. Fetch live_rules or pre_match_rules based on match state
    5. Fetch referee_rules if referee data is available
    6. Fetch risk_management + psychology top items
    """
    from src.knowledge_db import search_knowledge_items, list_category_items

    ctx = KnowledgeContext()

    try:
        # ── 1. Golden rules — always applied ──────────────────────────────────
        golden = list_category_items("golden_rules", limit=20)
        ctx.golden_rules = [_to_item(r) for r in golden]
        ctx.golden_rules_applied = [item.title for item in ctx.golden_rules]

        # ── 2. Red flags — check which are triggered ───────────────────────────
        red = list_category_items("red_flags", limit=30)
        ctx.red_flags = [_to_item(r) for r in red]

        triggered: list[str] = []
        for flag in ctx.red_flags:
            desc_lower = flag.description.lower() + " " + flag.tags.lower()
            # Missing xG data
            if not has_xg and ("xg" in desc_lower or "expected goal" in desc_lower):
                triggered.append(f"{flag.title} — no xG data available")
            # Low methodology score
            if meth_score < 4.0 and ("low score" in desc_lower or "low methodology" in desc_lower or "confidence" in desc_lower):
                triggered.append(f"{flag.title} — methodology score {meth_score:.1f}/10")
            # No referee data
            if not has_referee and "referee" in desc_lower:
                triggered.append(f"{flag.title} — referee unassigned")
        ctx.red_flags_triggered = triggered

        # ── 3. Team/league specific ────────────────────────────────────────────
        relevant: list[KnowledgeItem] = []
        if hn:
            team_results = search_knowledge_items(hn, categories=["team_rules", "league_rules"], limit=3)
            relevant.extend(_to_item(r) for r in team_results)
        if an:
            team_results = search_knowledge_items(an, categories=["team_rules", "league_rules"], limit=3)
            relevant.extend(_to_item(r) for r in team_results)
        if league:
            league_results = search_knowledge_items(league, categories=["league_rules", "referee_rules"], limit=4)
            relevant.extend(_to_item(r) for r in league_results)

        # ── 4. Live vs pre-match rules ─────────────────────────────────────────
        if is_live:
            live_items = list_category_items("live_rules", limit=5)
            relevant.extend(_to_item(r) for r in live_items)
        else:
            pre_items = list_category_items("pre_match_rules", limit=5)
            relevant.extend(_to_item(r) for r in pre_items)

        # ── 5. Referee rules ───────────────────────────────────────────────────
        if has_referee:
            ref_items = list_category_items("referee_rules", limit=3)
            relevant.extend(_to_item(r) for r in ref_items)

        # ── 6. Betting rules + psychology + risk (top 2 each) ─────────────────
        for cat in ("betting_rules", "psychology", "risk_management"):
            items = list_category_items(cat, limit=2)
            relevant.extend(_to_item(r) for r in items)

        # De-duplicate by id and sort by confidence desc
        seen: set[int] = set()
        deduped: list[KnowledgeItem] = []
        for item in relevant:
            if item.id not in seen:
                seen.add(item.id)
                deduped.append(item)
        deduped.sort(key=lambda x: -x.confidence)
        ctx.relevant_items = deduped

        ctx.knowledge_notes = ctx.to_notes()

    except Exception as exc:
        logger.error("Knowledge engine consult failed: %s", exc)

    return ctx
