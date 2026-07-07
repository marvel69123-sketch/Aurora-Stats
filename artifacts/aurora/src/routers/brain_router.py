"""
/aurora/brain — AURORA_BRAIN knowledge system REST API.

File-based endpoints (existing, unchanged):
  GET  /aurora/brain                → version + section index
  GET  /aurora/brain/config         → typed operational parameters (JSON)
  POST /aurora/brain/reload         → clear file cache and re-read from disk

SQLite knowledge-engine endpoints (new):
  GET  /aurora/brain/search?q=      → full-text search across all 10 knowledge tables
  POST /aurora/brain/save           → save a new knowledge record

File-reader endpoint (must stay LAST — {section} is a wildcard):
  GET  /aurora/brain/{section}      → raw markdown for a brain file section

Route ordering is intentional: all explicit paths must appear before {section}.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from src.brain import (
    get_all_sections,
    get_brain_meta,
    get_config,
    get_section,
    get_version,
    reload_brain,
)
from src.knowledge_db import TABLES, save_knowledge, search_knowledge

router = APIRouter()

_VALID_SECTIONS = {
    "mission", "methodology", "bankroll", "betting_rules",
    "confidence", "markets", "learning", "glossary",
}


# ---------------------------------------------------------------------------
# GET /aurora/brain  — index
# ---------------------------------------------------------------------------

@router.get("/brain", summary="Brain Index")
async def brain_index():
    """
    Return the AURORA_BRAIN version, file-section index, knowledge-table index,
    and operational parameters summary.
    """
    ver = get_version()
    return {
        "brain": get_brain_meta(),
        "description": (
            "AURORA_BRAIN is the permanent knowledge and configuration system. "
            "Every prediction endpoint reads brain files before generating scores. "
            "The SQLite knowledge engine stores evolving notes, predictions, and rules."
        ),
        "file_sections": {s: f"/aurora/brain/{s}" for s in sorted(_VALID_SECTIONS)},
        "knowledge_tables": TABLES,
        "endpoints": {
            "config":  "/aurora/brain/config",
            "search":  "/aurora/brain/search?q=<query>",
            "save":    "POST /aurora/brain/save",
            "reload":  "POST /aurora/brain/reload",
        },
        "changelog": ver.get("changelog", []),
    }


# ---------------------------------------------------------------------------
# GET /aurora/brain/config  — typed operational parameters
# ---------------------------------------------------------------------------

@router.get("/brain/config", summary="Brain Operational Config")
async def brain_config():
    """
    Return the typed operational parameters parsed from version.json.

    These values are what prediction endpoints (e.g. /aurora/score) actually use
    for risk classification, signal blending, and market baseline rates.
    Updating version.json and calling POST /aurora/brain/reload applies changes
    immediately — no server restart required.
    """
    cfg = get_config()
    return {
        "brain_version": get_version().get("brain_version"),
        "confidence_thresholds": {
            "low_risk_min_confidence":    cfg.confidence.low_risk_min_confidence,
            "low_risk_min_probability":   cfg.confidence.low_risk_min_probability,
            "medium_risk_min_confidence": cfg.confidence.medium_risk_min_confidence,
            "medium_risk_min_probability": cfg.confidence.medium_risk_min_probability,
        },
        "betting_gates": {
            "min_confidence":         cfg.gates.min_confidence,
            "min_probability":        cfg.gates.min_probability,
            "min_overall_confidence": cfg.gates.min_overall_confidence,
            "allowed_risk_levels":    list(cfg.gates.allowed_risk_levels),
            "min_data_signals":       cfg.gates.min_data_signals,
        },
        "signal_weights": {
            "xg_blend_weight":        cfg.weights.xg_blend_weight,
            "standings_prior_weight": cfg.weights.standings_prior_weight,
            "form_weight_in_prior":   cfg.weights.form_weight_in_prior,
            "venue_weight_in_prior":  cfg.weights.venue_weight_in_prior,
            "max_live_score_weight":  cfg.weights.max_live_score_weight,
        },
        "market_baselines": {
            "avg_corners_per_90":  cfg.baselines.avg_corners_per_90,
            "avg_cards_per_90":    cfg.baselines.avg_cards_per_90,
            "default_home_gpg":    cfg.baselines.default_home_gpg,
            "default_away_gpg":    cfg.baselines.default_away_gpg,
            "draw_base_rate":      cfg.baselines.draw_base_rate,
            "max_goals_poisson":   cfg.baselines.max_goals_poisson,
        },
        "pre_match_confidence_cap": cfg.pre_match_confidence_cap,
    }


# ---------------------------------------------------------------------------
# GET /aurora/brain/search?q=  — SQLite full-text search  [NEW]
# ---------------------------------------------------------------------------

@router.get("/brain/search", summary="Search Knowledge Base")
async def brain_search(
    q: str = Query(..., min_length=1, description="Search query (searches title, content, tags)"),
    table: str | None = Query(None, description="Restrict search to one table (optional)"),
    limit: int = Query(20, ge=1, le=100, description="Max results per table"),
):
    """
    Full-text search across all 10 Aurora Brain knowledge tables.

    Searches **title**, **content**, and **tags** fields using case-insensitive
    LIKE matching. Results are sorted by `updated_at` descending.

    Optionally restrict to a single table with `?table=<name>`.

    **Knowledge tables:**
    methodology, betting_rules, bankroll_rules, market_rules, learning_history,
    predictions, bet_results, teams_notes, referee_notes, competitions_notes.

    **Example:**
    `GET /aurora/brain/search?q=poisson&table=methodology`
    """
    tables = None
    if table:
        if table not in TABLES:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown table '{table}'. Valid tables: {TABLES}",
            )
        tables = [table]

    results = search_knowledge(q, tables=tables, limit_per_table=limit)
    return {
        "query": q,
        "table_filter": table,
        "total": len(results),
        "results": results,
    }


# ---------------------------------------------------------------------------
# POST /aurora/brain/save  — persist new knowledge  [NEW]
# ---------------------------------------------------------------------------

class SaveKnowledgeRequest(BaseModel):
    table: str = Field(
        ...,
        description=(
            "Target knowledge table. One of: methodology, betting_rules, bankroll_rules, "
            "market_rules, learning_history, predictions, bet_results, "
            "teams_notes, referee_notes, competitions_notes."
        ),
    )
    title: str = Field(..., min_length=1, max_length=500, description="Short descriptive title")
    content: str = Field(..., min_length=1, description="Full knowledge content (markdown supported)")
    tags: str = Field(
        default="",
        description="Comma-separated tags e.g. 'poisson,corners,live'",
    )


@router.post("/brain/save", summary="Save Knowledge", status_code=201)
async def brain_save(body: SaveKnowledgeRequest):
    """
    Persist a new knowledge record to the Aurora Brain SQLite database.

    The record is immediately searchable via `GET /aurora/brain/search`.

    **Table options:**

    | Table | Use for |
    |-------|---------|
    | methodology | Model logic, signal decisions, Poisson parameters |
    | betting_rules | Stake sizing, gate thresholds, disqualifying conditions |
    | bankroll_rules | Bankroll management notes |
    | market_rules | Per-market insights and edge conditions |
    | learning_history | Calibration results, outcome tracking, lessons learned |
    | predictions | Saved prediction snapshots with rationale |
    | bet_results | Logged bet outcomes for calibration |
    | teams_notes | Per-team observations (style, form tendencies) |
    | referee_notes | Referee card/foul rate tendencies |
    | competitions_notes | League-specific quirks and baselines |

    **Example body:**
    ```json
    {
      "table": "teams_notes",
      "title": "Arsenal — high corner rate at home",
      "content": "Arsenal average 6.2 corners at home in 2025/26, highest in PL.",
      "tags": "arsenal,corners,home,premier-league"
    }
    ```
    """
    if body.table not in TABLES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown table '{body.table}'. Valid tables: {TABLES}",
        )

    record = save_knowledge(
        table=body.table,
        title=body.title,
        content=body.content,
        tags=body.tags,
    )
    return {
        "status": "saved",
        "table": body.table,
        "record": record,
    }


# ---------------------------------------------------------------------------
# POST /aurora/brain/reload  — hot-reload file brain
# ---------------------------------------------------------------------------

@router.post("/brain/reload", summary="Reload Brain Files")
async def brain_reload():
    """
    Clear the in-memory file-brain cache and re-read all /brain/*.md files from disk.

    Use this after editing brain files to apply changes immediately without
    restarting the server. Re-parses version.json and refreshes all operational
    parameters used by prediction endpoints.

    Does NOT affect the SQLite knowledge database.
    """
    reload_brain()
    ver = get_version()
    return {
        "status": "reloaded",
        "brain_version": ver.get("brain_version"),
        "sections_loaded": sorted(get_all_sections().keys()),
        "message": (
            "File-brain cache cleared and reloaded from disk. "
            "All prediction endpoints will use updated parameters. "
            "SQLite knowledge engine is unaffected."
        ),
    }


# ---------------------------------------------------------------------------
# GET /aurora/brain/{section}  — raw markdown  [MUST STAY LAST]
# ---------------------------------------------------------------------------

@router.get("/brain/{section}", response_class=PlainTextResponse, summary="Brain File Section")
async def brain_section(section: str):
    """
    Return the raw markdown content of a brain file section.

    Valid sections: mission, methodology, bankroll, betting_rules,
    confidence, markets, learning, glossary.

    This route is a wildcard and is intentionally registered last so that
    explicit paths (/brain/config, /brain/search, /brain/reload) are matched first.
    """
    if section not in _VALID_SECTIONS:
        raise HTTPException(
            status_code=404,
            detail=f"Section '{section}' not found. Valid file sections: {sorted(_VALID_SECTIONS)}",
        )
    content = get_section(section)
    if not content:
        raise HTTPException(status_code=404, detail=f"Section '{section}' is empty or missing.")
    return content
