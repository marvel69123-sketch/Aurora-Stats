"""
Confidence Engine — data-richness scoring.

Confidence (0–10) reflects how much data backs a prediction, NOT how likely
it is to be correct. Formula from brain/confidence.md:

  base = 3.0 + count(available signals) × 1.3

Signal checklist: has_stats, has_xg, has_standings, has_events, is_live_or_finished

Pre-match cap comes from brain config (pre_match_confidence_cap, default 6.5).
Per-market adjustments applied afterwards (see run()).

Public API
----------
  run(methodology, cfg) -> ConfidenceResult
"""
from __future__ import annotations

from dataclasses import dataclass

from src.brain import BrainConfig
from src.core.methodology_engine import MethodologyResult


@dataclass
class ConfidenceResult:
    """Per-signal and per-market confidence scores."""

    overall:      float   # 0–10, base confidence for 1X2 markets
    stats_conf:   float   # for BTTS / Over 2.5 (boosted if xG present)
    corner_conf:  float   # for Over 8.5 corners (lower pre-match)
    card_conf:    float   # for Over 4.5 cards (lowest pre-match)
    signal_count: int     # how many of the 5 signals fired


def run(methodology: MethodologyResult, cfg: BrainConfig) -> ConfidenceResult:
    """
    Compute confidence scores from the methodology result.

    Parameters
    ----------
    methodology : output of methodology_engine.run()
    cfg         : BrainConfig with pre_match_confidence_cap
    """
    m = methodology

    signals = [
        m.has_stats,
        m.has_xg,
        m.has_standings,
        m.has_events,
        m.is_live or m.is_finished,
    ]
    signal_count = sum(signals)
    base_conf    = 3.0 + signal_count * 1.3

    if not (m.is_live or m.is_finished):
        base_conf = min(base_conf, cfg.pre_match_confidence_cap)

    overall = min(10.0, base_conf)

    # Per-market adjustments ────────────────────────────────────────────────
    # xG boosts BTTS and Over 2.5 (better scoring-rate estimate)
    stats_conf = min(10.0, overall + (0.8 if m.has_xg else 0.0))

    # Corners and cards are less reliable pre-match; cap them
    is_in_play = m.is_live or m.is_finished
    corner_conf = min(8.0, overall - 1.0) if is_in_play else 4.5
    card_conf   = min(8.0, overall - 1.0) if is_in_play else 4.0

    return ConfidenceResult(
        overall=overall,
        stats_conf=stats_conf,
        corner_conf=corner_conf,
        card_conf=card_conf,
        signal_count=signal_count,
    )
