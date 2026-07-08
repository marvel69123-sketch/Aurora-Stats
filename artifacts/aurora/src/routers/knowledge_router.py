"""
/aurora/knowledge — Aurora Knowledge Engine REST API.

Endpoints:
  POST /aurora/knowledge/save        → add a new knowledge item
  GET  /aurora/knowledge/search      → full-text search across all/selected categories
  GET  /aurora/knowledge/list        → paginated listing (optionally filtered by category)
  GET  /aurora/knowledge/categories  → category summary with item counts

Knowledge never expires. Aurora consults it before every recommendation.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.brain import get_brain_meta
from src.knowledge_db import (
    CATEGORIES,
    count_knowledge_items,
    get_categories_summary,
    list_all_knowledge_items,
    save_knowledge_item,
    search_knowledge_items,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class SaveKnowledgeRequest(BaseModel):
    category:    str          = Field(..., description=f"One of: {', '.join(CATEGORIES)}")
    title:       str          = Field(..., min_length=3,  max_length=200)
    description: str          = Field(..., min_length=10, max_length=2000)
    examples:    list[str]    = Field(default_factory=list, max_length=10)
    confidence:  float        = Field(default=0.8, ge=0.0, le=1.0)
    version:     str          = Field(default="1.0", max_length=20)
    source:      str          = Field(default="user", max_length=50)
    tags:        str          = Field(default="", max_length=300)


class KnowledgeItemResponse(BaseModel):
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
    updated_at:  str


class CategorySummary(BaseModel):
    category:       str
    total:          int
    avg_confidence: float
    last_updated:   str | None


def _parse_examples(raw: str) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(x) for x in parsed]
    except Exception:
        pass
    return [e.strip() for e in raw.split("|") if e.strip()]


def _to_response(row: dict) -> KnowledgeItemResponse:
    return KnowledgeItemResponse(
        id=int(row.get("id", 0)),
        category=row.get("category", ""),
        title=row.get("title", ""),
        description=row.get("description", ""),
        examples=_parse_examples(row.get("examples", "[]")),
        confidence=float(row.get("confidence", 0.8)),
        version=str(row.get("version", "1.0")),
        source=str(row.get("source", "user")),
        tags=str(row.get("tags", "")),
        created_at=str(row.get("created_at", "")),
        updated_at=str(row.get("updated_at", "")),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/knowledge/save",
    response_model=KnowledgeItemResponse,
    status_code=201,
    summary="Save Knowledge Item",
)
async def save_knowledge(body: SaveKnowledgeRequest) -> KnowledgeItemResponse:
    """
    Save a new knowledge item to Aurora's internal knowledge base.

    **Categories:** methodology, betting_rules, bankroll_rules, market_rules,
    live_rules, pre_match_rules, referee_rules, league_rules, team_rules,
    psychology, risk_management, red_flags, golden_rules.

    **Fields:**
    - `title` — short human-readable label (3–200 chars)
    - `description` — full rule or knowledge text (10–2000 chars)
    - `examples` — list of concrete usage examples
    - `confidence` — 0.0–1.0; Aurora weights higher-confidence items first
    - `version` — version tag (e.g. "1.0", "2.1")
    - `source` — who wrote this: "user", "aurora", "evolution", or any label
    - `tags` — comma-separated searchable labels

    Knowledge items **never expire** and are consulted before every prediction.
    Aurora seeds the knowledge base with {n} foundational rules at startup.
    """
    if body.category not in set(CATEGORIES):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid category '{body.category}'. Valid categories: {sorted(CATEGORIES)}",
        )
    try:
        row = save_knowledge_item(
            category=body.category,
            title=body.title,
            description=body.description,
            examples=body.examples,
            confidence=body.confidence,
            version=body.version,
            source=body.source,
            tags=body.tags,
        )
        return _to_response(row)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get(
    "/knowledge/search",
    summary="Search Knowledge Base",
)
async def search_knowledge(
    q:        str          = Query(..., min_length=2, description="Search query (searches title, description, tags)"),
    category: str | None   = Query(None, description="Restrict to a specific category"),
    limit:    int          = Query(20, ge=1, le=100),
) -> dict:
    """
    Full-text search across Aurora's knowledge base.

    Searches title, description, and tags with case-insensitive LIKE matching.
    Results are sorted by confidence descending so the highest-quality
    rules appear first.

    **Optional:** pass `category` to restrict search to a single category.
    """
    cats = [category] if category else None
    if category and category not in set(CATEGORIES):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid category '{category}'. Valid: {sorted(CATEGORIES)}",
        )
    results = search_knowledge_items(q, categories=cats, limit=limit)
    return {
        "query":    q,
        "category": category,
        "total":    len(results),
        "results":  [_to_response(r) for r in results],
        "brain":    get_brain_meta(),
    }


@router.get(
    "/knowledge/list",
    summary="List Knowledge Items",
)
async def list_knowledge(
    category: str | None = Query(None, description="Filter by category; omit for all categories"),
    limit:    int        = Query(50, ge=1, le=200),
    offset:   int        = Query(0,  ge=0),
) -> dict:
    """
    Paginated listing of Aurora's knowledge base.

    - Omit `category` to return items across all 13 categories.
    - Items are sorted by confidence descending within each category.
    - Aurora seeds {n} foundational rules at startup — they appear here.

    Use `GET /aurora/knowledge/categories` to see counts per category.
    """
    if category and category not in set(CATEGORIES):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid category '{category}'. Valid: {sorted(CATEGORIES)}",
        )
    rows  = list_all_knowledge_items(category=category, limit=limit, offset=offset)
    total = count_knowledge_items(category=category)
    return {
        "category": category,
        "total":    total,
        "limit":    limit,
        "offset":   offset,
        "items":    [_to_response(r) for r in rows],
        "brain":    get_brain_meta(),
    }


@router.get(
    "/knowledge/categories",
    summary="Knowledge Category Summary",
)
async def list_categories() -> dict:
    """
    Return all 13 knowledge categories with item counts and average confidence.

    Categories with zero items are listed with `total: 0` —
    they are valid but not yet populated.

    **The 13 categories:**
    | Category | Purpose |
    |---|---|
    | methodology | Core prediction model rules |
    | betting_rules | When to bet and when not to |
    | bankroll_rules | Stake sizing and bankroll management |
    | market_rules | Per-market knowledge (goals, corners, BTTS…) |
    | live_rules | In-play specific rules |
    | pre_match_rules | Before-kickoff specific rules |
    | referee_rules | Referee-specific tendencies |
    | league_rules | Per-league statistical tendencies |
    | team_rules | Team-specific patterns and profiles |
    | psychology | Cognitive biases to avoid |
    | risk_management | Exposure and drawdown controls |
    | red_flags | Signals that reduce or block recommendations |
    | golden_rules | Absolute rules that override everything |
    """
    summary = get_categories_summary()
    total   = count_knowledge_items()
    return {
        "total_items":  total,
        "categories":   [CategorySummary(**row) for row in summary],
        "all_categories": CATEGORIES,
        "brain":        get_brain_meta(),
    }
