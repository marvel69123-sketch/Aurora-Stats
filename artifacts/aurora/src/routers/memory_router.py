"""
/aurora/memory — Aurora Memory Engine REST API.

Endpoints:
  GET  /aurora/memory                → collection stats overview
  GET  /aurora/memory/search         → full-text search across all collections
  POST /aurora/memory/save           → manually save a memory entry
  GET  /aurora/memory/history        → paginated history (all or one collection)
  GET  /aurora/memory/context        → recall context for a fixture (home+away)
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.memory_db import (
    COLLECTIONS,
    collection_stats,
    get_history,
    recall,
    recall_context,
    remember,
    search_memory,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class SaveMemoryRequest(BaseModel):
    collection:  str = Field(..., description=f"One of: {', '.join(COLLECTIONS)}")
    content:     dict = Field(default_factory=dict, description="Structured payload (any JSON object)")
    summary:     str  = Field(default="", description="Human-readable one-line summary")
    key:         str | None = Field(None, description="Optional unique key within the collection (enables upsert)")
    tags:        list[str] = Field(default_factory=list, description="Tags for search and filtering")
    fixture_id:  int | None = None
    league:      str | None = None
    team:        str | None = None
    market:      str | None = None
    confidence:  float | None = Field(None, ge=0.0, le=10.0)
    importance:  int = Field(default=5, ge=1, le=10, description="1 (low) to 10 (critical)")


class MemoryEntryResponse(BaseModel):
    id:          int
    collection:  str
    key:         str | None
    tags:        list[str]
    content:     dict
    summary:     str
    fixture_id:  int | None
    league:      str | None
    team:        str | None
    market:      str | None
    confidence:  float | None
    importance:  int
    created_at:  str
    updated_at:  str | None


class SaveMemoryResponse(BaseModel):
    id:          int
    collection:  str
    created_at:  str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/memory", tags=["Memory"], summary="Memory Overview")
async def memory_overview():
    """
    Return a summary of all 14 memory collections — entry counts and latest activity.
    """
    return {
        "collections":      COLLECTIONS,
        "total_collections": len(COLLECTIONS),
        "stats":            collection_stats(),
    }


@router.get("/memory/search", tags=["Memory"], summary="Search Memory")
async def memory_search(
    q:          str   = Query(..., min_length=1, description="Search query (searches summary, content, tags)"),
    collection: str   = Query(None, description="Limit search to one collection"),
    league:     str   = Query(None, description="Filter by league"),
    team:       str   = Query(None, description="Filter by team"),
    limit:      int   = Query(20, ge=1, le=100),
    offset:     int   = Query(0,  ge=0),
):
    """
    Full-text search across Aurora's memory.

    Searches: `summary`, `content` (JSON body), and `tags`.
    Optionally filter by collection, league, or team.
    """
    if collection and collection not in COLLECTIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown collection '{collection}'. Valid: {COLLECTIONS}",
        )

    results = search_memory(
        query=q,
        collection=collection,
        league=league,
        team=team,
        limit=limit,
        offset=offset,
    )
    return {
        "query":      q,
        "collection": collection or "all",
        "total":      len(results),
        "limit":      limit,
        "offset":     offset,
        "results":    results,
    }


@router.post("/memory/save", tags=["Memory"], summary="Save Memory Entry")
async def memory_save(body: SaveMemoryRequest) -> SaveMemoryResponse:
    """
    Manually save an entry to any memory collection.

    If `key` is provided and an entry with that key already exists in the
    collection, the existing record is updated (upsert behaviour).
    """
    if body.collection not in COLLECTIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown collection '{body.collection}'. Valid: {COLLECTIONS}",
        )

    entry_id = remember(
        collection=body.collection,
        content=body.content,
        summary=body.summary,
        key=body.key,
        tags=body.tags,
        fixture_id=body.fixture_id,
        league=body.league,
        team=body.team,
        market=body.market,
        confidence=body.confidence,
        importance=body.importance,
    )

    # Retrieve the saved entry for timestamps
    saved = recall(body.collection, limit=1)
    created_at = saved[0]["created_at"] if saved else ""

    return SaveMemoryResponse(
        id=entry_id,
        collection=body.collection,
        created_at=created_at,
    )


@router.get("/memory/history", tags=["Memory"], summary="Memory History")
async def memory_history(
    collection: str = Query("all", description="Collection name or 'all'"),
    limit:      int = Query(50, ge=1, le=200),
    offset:     int = Query(0,  ge=0),
):
    """
    Return paginated memory history, newest entries first.

    Pass `collection=all` (default) to see everything, or a specific
    collection name to filter.
    """
    coll = None if collection == "all" else collection
    if coll and coll not in COLLECTIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown collection '{coll}'. Valid: {COLLECTIONS}",
        )
    return get_history(collection=coll, limit=limit, offset=offset)


@router.get("/memory/context", tags=["Memory"], summary="Recall Pre-Match Context")
async def memory_context(
    home:   str = Query(..., description="Home team name"),
    away:   str = Query(..., description="Away team name"),
    league: str = Query(None, description="League name"),
):
    """
    Retrieve Aurora's memory context for a given fixture.

    Returns past lessons, team profiles, league profile, and winning/failing
    patterns relevant to these teams and league. Used internally before every
    recommendation, exposed here for transparency.
    """
    ctx = recall_context(hn=home, an=away, league=league)
    return {
        "home":    home,
        "away":    away,
        "league":  league,
        "context": ctx,
    }


@router.get("/memory/collections", tags=["Memory"], summary="List Collections")
async def list_collections():
    """List all 14 memory collections with their descriptions."""
    descriptions = {
        "methodologies":     "Methodology version history and configuration snapshots",
        "betting_patterns":  "Every recommendation Aurora has generated",
        "successful_patterns": "Patterns associated with winning predictions",
        "failed_patterns":   "Patterns associated with losing predictions",
        "bankroll_sessions": "Daily bankroll session summaries",
        "user_preferences":  "User-level preferences and settings",
        "market_statistics": "Aggregate statistics per betting market",
        "referee_profiles":  "Referee card and foul rate tendencies",
        "league_profiles":   "League-level scoring and style aggregates",
        "team_profiles":     "Team-level appearance and performance summaries",
        "player_profiles":   "Player-level statistical notes",
        "tactical_patterns": "Formation and tactical trend observations",
        "lessons_learned":   "Post-match analysis and lessons from finished fixtures",
        "daily_logs":        "Daily activity log entries",
    }
    stats = {s["collection"]: s for s in collection_stats()}
    return {
        "collections": [
            {
                "name":        col,
                "description": descriptions.get(col, ""),
                "total":       stats.get(col, {}).get("total", 0),
                "latest":      stats.get(col, {}).get("latest"),
            }
            for col in COLLECTIONS
        ]
    }
