"""
/aurora/brain — Expose the AURORA_BRAIN knowledge system via REST.

Endpoints:
  GET /aurora/brain              → version + section index
  GET /aurora/brain/config       → typed operational parameters (JSON)
  GET /aurora/brain/{section}    → raw markdown for a single section
  POST /aurora/brain/reload      → clear cache and re-read all files from disk
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

from src.brain import (
    get_all_sections,
    get_brain_meta,
    get_config,
    get_section,
    get_version,
    reload_brain,
)

router = APIRouter()

_VALID_SECTIONS = {
    "mission", "methodology", "bankroll", "betting_rules",
    "confidence", "markets", "learning", "glossary",
}


# ---------------------------------------------------------------------------
# GET /aurora/brain  — index + version
# ---------------------------------------------------------------------------

@router.get("/brain", summary="Brain Index")
async def brain_index():
    """
    Return the AURORA_BRAIN version, section index, and operational parameters summary.

    The brain is the permanent knowledge system that governs all Aurora predictions.
    Parameters in `operational_parameters` are loaded by every prediction endpoint.
    """
    ver = get_version()
    cfg = get_config()
    return {
        "brain": get_brain_meta(),
        "description": (
            "AURORA_BRAIN is the permanent knowledge and configuration system. "
            "Every prediction endpoint reads these files before generating scores. "
            "Brain files live in /brain/ and are never overwritten by the API."
        ),
        "sections": {
            s: f"/aurora/brain/{s}"
            for s in sorted(_VALID_SECTIONS)
        },
        "config_endpoint": "/aurora/brain/config",
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
    Updating version.json and calling /aurora/brain/reload will take effect
    immediately — no server restart required.
    """
    cfg = get_config()
    return {
        "brain_version": get_version().get("brain_version"),
        "confidence_thresholds": {
            "low_risk_min_confidence": cfg.confidence.low_risk_min_confidence,
            "low_risk_min_probability": cfg.confidence.low_risk_min_probability,
            "medium_risk_min_confidence": cfg.confidence.medium_risk_min_confidence,
            "medium_risk_min_probability": cfg.confidence.medium_risk_min_probability,
        },
        "betting_gates": {
            "min_confidence": cfg.gates.min_confidence,
            "min_probability": cfg.gates.min_probability,
            "min_overall_confidence": cfg.gates.min_overall_confidence,
            "allowed_risk_levels": list(cfg.gates.allowed_risk_levels),
            "min_data_signals": cfg.gates.min_data_signals,
        },
        "signal_weights": {
            "xg_blend_weight": cfg.weights.xg_blend_weight,
            "standings_prior_weight": cfg.weights.standings_prior_weight,
            "form_weight_in_prior": cfg.weights.form_weight_in_prior,
            "venue_weight_in_prior": cfg.weights.venue_weight_in_prior,
            "max_live_score_weight": cfg.weights.max_live_score_weight,
        },
        "market_baselines": {
            "avg_corners_per_90": cfg.baselines.avg_corners_per_90,
            "avg_cards_per_90": cfg.baselines.avg_cards_per_90,
            "default_home_gpg": cfg.baselines.default_home_gpg,
            "default_away_gpg": cfg.baselines.default_away_gpg,
            "draw_base_rate": cfg.baselines.draw_base_rate,
            "max_goals_poisson": cfg.baselines.max_goals_poisson,
        },
        "pre_match_confidence_cap": cfg.pre_match_confidence_cap,
    }


# ---------------------------------------------------------------------------
# GET /aurora/brain/{section}  — raw markdown
# ---------------------------------------------------------------------------

@router.get("/brain/{section}", response_class=PlainTextResponse, summary="Brain Section")
async def brain_section(section: str):
    """
    Return the raw markdown content of a brain section.

    Valid sections: mission, methodology, bankroll, betting_rules,
    confidence, markets, learning, glossary.
    """
    if section not in _VALID_SECTIONS:
        raise HTTPException(
            status_code=404,
            detail=f"Section '{section}' not found. Valid sections: {sorted(_VALID_SECTIONS)}",
        )
    content = get_section(section)
    if not content:
        raise HTTPException(status_code=404, detail=f"Section '{section}' is empty or missing.")
    return content


# ---------------------------------------------------------------------------
# POST /aurora/brain/reload  — hot-reload brain from disk
# ---------------------------------------------------------------------------

@router.post("/brain/reload", summary="Reload Brain")
async def brain_reload():
    """
    Clear the in-memory brain cache and re-read all files from disk.

    Use this after manually editing brain files to apply changes immediately
    without restarting the server. Automatically re-parses version.json
    and refreshes all operational parameters used by prediction endpoints.
    """
    reload_brain()
    ver = get_version()
    return {
        "status": "reloaded",
        "brain_version": ver.get("brain_version"),
        "sections_loaded": sorted(get_all_sections().keys()),
        "message": "Brain cache cleared and reloaded from disk. All endpoints will use updated parameters.",
    }
