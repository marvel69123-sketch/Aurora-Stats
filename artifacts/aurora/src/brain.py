"""
AURORA_BRAIN — Permanent knowledge loader.

Every endpoint that generates predictions should call `get_config()` to obtain
operational parameters from the brain files instead of using hardcoded constants.

Design rules:
- Brain files are NEVER overwritten by this module — read-only access only.
- The full brain content is cached after the first load (process lifetime).
- Clearing the cache (reload_brain()) re-reads all files — useful for hot-reloading
  brain updates without a server restart.
- Adding new .md files to /brain/ automatically makes them available via get_section().
- All .json files in /brain/ are loaded as typed configs (version.json → BrainConfig,
  methodology.json → MethodologyConfig). Adding new .json files is automatic.
- The operational_parameters block in version.json is the single source of truth for
  all numeric thresholds used by prediction endpoints.
- methodology.json is the single source of truth for Methodology v1 weights.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

BRAIN_DIR = Path(__file__).parent.parent / "brain"


# ---------------------------------------------------------------------------
# Raw loader — cached for process lifetime
# ---------------------------------------------------------------------------

@lru_cache(maxsize=None)
def _load_raw() -> dict:
    """
    Load every file in /brain/ into a dict keyed by filename stem.
    Markdown files → str value  (key = stem, e.g. "methodology").
    JSON files     → parsed dict (key = "_" + stem, e.g. "_version", "_methodology").
    Called once; subsequent calls hit the lru_cache.
    """
    brain: dict = {}

    if not BRAIN_DIR.exists():
        logger.warning("AURORA_BRAIN directory not found at %s", BRAIN_DIR)
        return brain

    for path in sorted(BRAIN_DIR.iterdir()):
        if path.suffix == ".md":
            try:
                brain[path.stem] = path.read_text(encoding="utf-8")
            except OSError as exc:
                logger.error("Failed to read brain file %s: %s", path, exc)
        elif path.suffix == ".json":
            try:
                brain[f"_{path.stem}"] = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                logger.error("Failed to parse %s: %s", path.name, exc)

    logger.info(
        "AURORA_BRAIN loaded — version=%s sections=%s",
        brain.get("_version", {}).get("brain_version", "unknown"),
        [k for k in brain if not k.startswith("_")],
    )
    return brain


def reload_brain() -> None:
    """Clear all caches so the next call re-reads all brain files from disk."""
    _load_raw.cache_clear()
    get_config.cache_clear()
    get_methodology_config.cache_clear()
    _load_raw()


# ---------------------------------------------------------------------------
# Public accessors
# ---------------------------------------------------------------------------

def get_section(name: str) -> str:
    """Return the markdown content of a brain section, or '' if not found."""
    return _load_raw().get(name, "")


def get_all_sections() -> dict[str, str]:
    """Return all markdown sections as {name: content}."""
    return {k: v for k, v in _load_raw().items() if not k.startswith("_") and isinstance(v, str)}


def get_version() -> dict:
    """Return the parsed version.json dict."""
    return _load_raw().get("_version", {})


def get_brain_meta() -> dict:
    """Compact metadata dict suitable for embedding in any API response."""
    ver = get_version()
    return {
        "brain_version": ver.get("brain_version", "unknown"),
        "last_updated": ver.get("last_updated"),
        "sections": ver.get("sections", []),
    }


# ---------------------------------------------------------------------------
# Typed config — BrainConfig (version.json operational_parameters)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ConfidenceThresholds:
    low_risk_min_confidence:    float = 7.0
    low_risk_min_probability:   float = 68.0
    medium_risk_min_confidence: float = 5.0
    medium_risk_min_probability: float = 52.0


@dataclass(frozen=True)
class BettingGates:
    min_confidence:          float = 5.0
    min_probability:         float = 52.0
    min_overall_confidence:  float = 4.0
    allowed_risk_levels:     tuple[str, ...] = ("Low", "Medium")
    min_data_signals:        int   = 2


@dataclass(frozen=True)
class SignalWeights:
    xg_blend_weight:         float = 0.60
    standings_prior_weight:  float = 0.40
    form_weight_in_prior:    float = 0.40
    venue_weight_in_prior:   float = 0.60
    max_live_score_weight:   float = 0.88


@dataclass(frozen=True)
class MarketBaselines:
    avg_corners_per_90: float = 10.5
    avg_cards_per_90:   float = 3.5
    default_home_gpg:   float = 1.2
    default_away_gpg:   float = 0.9
    draw_base_rate:     float = 0.12
    max_goals_poisson:  int   = 7


@dataclass(frozen=True)
class BrainConfig:
    confidence:              ConfidenceThresholds = field(default_factory=ConfidenceThresholds)
    gates:                   BettingGates         = field(default_factory=BettingGates)
    weights:                 SignalWeights         = field(default_factory=SignalWeights)
    baselines:               MarketBaselines       = field(default_factory=MarketBaselines)
    pre_match_confidence_cap: float = 6.5

    def risk_level(self, probability: float, confidence: float) -> str:
        """Classify a market as Low / Medium / High risk using brain thresholds."""
        ct = self.confidence
        if confidence >= ct.low_risk_min_confidence and probability >= ct.low_risk_min_probability:
            return "Low"
        if confidence >= ct.medium_risk_min_confidence and probability >= ct.medium_risk_min_probability:
            return "Medium"
        return "High"

    def is_actionable(self, probability: float, confidence: float, overall_confidence: float) -> bool:
        """Return True if a market passes all betting gates."""
        g = self.gates
        if overall_confidence < g.min_overall_confidence:
            return False
        if confidence < g.min_confidence:
            return False
        if probability < g.min_probability:
            return False
        return self.risk_level(probability, confidence) in g.allowed_risk_levels


@lru_cache(maxsize=None)
def get_config() -> BrainConfig:
    """
    Parse operational_parameters from version.json into a typed BrainConfig.
    Cached for process lifetime; call reload_brain() to refresh.
    """
    params = get_version().get("operational_parameters", {})

    ct_raw = params.get("confidence_thresholds", {})
    confidence = ConfidenceThresholds(
        low_risk_min_confidence=ct_raw.get("low_risk_min_confidence", 7.0),
        low_risk_min_probability=ct_raw.get("low_risk_min_probability", 68.0),
        medium_risk_min_confidence=ct_raw.get("medium_risk_min_confidence", 5.0),
        medium_risk_min_probability=ct_raw.get("medium_risk_min_probability", 52.0),
    )

    bg_raw = params.get("betting_gates", {})
    gates = BettingGates(
        min_confidence=bg_raw.get("min_confidence", 5.0),
        min_probability=bg_raw.get("min_probability", 52.0),
        min_overall_confidence=bg_raw.get("min_overall_confidence", 4.0),
        allowed_risk_levels=tuple(bg_raw.get("allowed_risk_levels", ["Low", "Medium"])),
        min_data_signals=bg_raw.get("min_data_signals", 2),
    )

    sw_raw = params.get("signal_weights", {})
    weights = SignalWeights(
        xg_blend_weight=sw_raw.get("xg_blend_weight", 0.60),
        standings_prior_weight=sw_raw.get("standings_prior_weight", 0.40),
        form_weight_in_prior=sw_raw.get("form_weight_in_prior", 0.40),
        venue_weight_in_prior=sw_raw.get("venue_weight_in_prior", 0.60),
        max_live_score_weight=sw_raw.get("max_live_score_weight", 0.88),
    )

    mb_raw = params.get("market_baselines", {})
    baselines = MarketBaselines(
        avg_corners_per_90=mb_raw.get("avg_corners_per_90", 10.5),
        avg_cards_per_90=mb_raw.get("avg_cards_per_90", 3.5),
        default_home_gpg=mb_raw.get("default_home_gpg", 1.2),
        default_away_gpg=mb_raw.get("default_away_gpg", 0.9),
        draw_base_rate=mb_raw.get("draw_base_rate", 0.12),
        max_goals_poisson=mb_raw.get("max_goals_poisson", 7),
    )

    return BrainConfig(
        confidence=confidence,
        gates=gates,
        weights=weights,
        baselines=baselines,
        pre_match_confidence_cap=params.get("pre_match_confidence_cap", 6.5),
    )


# ---------------------------------------------------------------------------
# Typed config — MethodologyConfig (brain/methodology.json)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CategoryWeights:
    """Per-category weights for Aurora Methodology v1. Must sum to 1.0."""
    match_context:       float = 0.05
    team_strength:       float = 0.10
    current_form:        float = 0.10
    motivation:          float = 0.05
    home_advantage:      float = 0.08
    away_performance:    float = 0.08
    xg_analysis:         float = 0.12
    live_momentum:       float = 0.10
    corners_pattern:     float = 0.06
    cards_pattern:       float = 0.06
    referee_influence:   float = 0.03
    tactical_style:      float = 0.04
    value_bet_detection: float = 0.08
    bankroll_risk:       float = 0.03
    historical_learning: float = 0.02

    def get(self, key: str, default: float = 0.0) -> float:
        return getattr(self, key, default)


@dataclass(frozen=True)
class MethodologyConfig:
    """
    Aurora Methodology v1 configuration — loaded from brain/methodology.json.
    All thresholds, weights, and scorer parameters live here.
    No values are hardcoded in the engine itself.
    """
    category_weights:    CategoryWeights = field(default_factory=CategoryWeights)

    # Gate thresholds
    min_score_to_recommend:        float = 5.5
    low_risk_above:                float = 7.0
    medium_risk_above:             float = 5.0

    # Blocking category thresholds {category_key: min_score_below_which_all_blocked}
    blocking_thresholds:           dict  = field(default_factory=lambda: {
        "bankroll_risk": 2.0, "historical_learning": 2.0
    })

    # Per-market pattern gates
    corners_min_pattern_score:     float = 3.0
    cards_min_pattern_score:       float = 3.0

    # Scorer parameters (passed through to each category scorer)
    scorers:                       dict  = field(default_factory=dict)


@lru_cache(maxsize=None)
def get_methodology_config() -> MethodologyConfig:
    """
    Parse brain/methodology.json into a typed MethodologyConfig.
    Cached for process lifetime; call reload_brain() to refresh.

    Falls back to safe defaults if the file is missing or malformed.
    """
    raw = _load_raw().get("_methodology", {})

    wt_raw = raw.get("category_weights", {})
    weights = CategoryWeights(
        match_context       = wt_raw.get("match_context",       0.05),
        team_strength       = wt_raw.get("team_strength",       0.10),
        current_form        = wt_raw.get("current_form",        0.10),
        motivation          = wt_raw.get("motivation",          0.05),
        home_advantage      = wt_raw.get("home_advantage",      0.08),
        away_performance    = wt_raw.get("away_performance",    0.08),
        xg_analysis         = wt_raw.get("xg_analysis",         0.12),
        live_momentum       = wt_raw.get("live_momentum",       0.10),
        corners_pattern     = wt_raw.get("corners_pattern",     0.06),
        cards_pattern       = wt_raw.get("cards_pattern",       0.06),
        referee_influence   = wt_raw.get("referee_influence",   0.03),
        tactical_style      = wt_raw.get("tactical_style",      0.04),
        value_bet_detection = wt_raw.get("value_bet_detection", 0.08),
        bankroll_risk       = wt_raw.get("bankroll_risk",       0.03),
        historical_learning = wt_raw.get("historical_learning", 0.02),
    )

    thresh = raw.get("thresholds", {})
    risk_bands = thresh.get("risk_bands", {})

    blocking_raw = thresh.get("blocking_categories", {})
    blocking = {k: float(v) for k, v in blocking_raw.items()} if blocking_raw else {
        "bankroll_risk": 2.0, "historical_learning": 2.0
    }

    mkt_gates = thresh.get("market_gates", {})

    return MethodologyConfig(
        category_weights=weights,
        min_score_to_recommend=float(thresh.get("min_score_to_recommend", 5.5)),
        low_risk_above=float(risk_bands.get("low_above", 7.0)),
        medium_risk_above=float(risk_bands.get("medium_above", 5.0)),
        blocking_thresholds=blocking,
        corners_min_pattern_score=float(mkt_gates.get("corners_min_pattern_score", 3.0)),
        cards_min_pattern_score=float(mkt_gates.get("cards_min_pattern_score", 3.0)),
        scorers=raw.get("scorers", {}),
    )
