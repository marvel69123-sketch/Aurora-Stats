"""
v3.5.2 — Live stats integrity: never invent cards/zeros; match by team.id.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.routers.live import (
    _build_team_stats_for_id,
    _resolve_cards,
    _team_stat_list,
)


def _swapped_raw_stats():
    """Away block listed first — index 0/1 would swap sides incorrectly."""
    return [
        {
            "team": {"id": 200, "name": "Away FC"},
            "statistics": [
                {"type": "Ball Possession", "value": "40%"},
                {"type": "Total Shots", "value": 5},
                {"type": "Yellow Cards", "value": 1},
                {"type": "Red Cards", "value": 0},
            ],
        },
        {
            "team": {"id": 100, "name": "Home FC"},
            "statistics": [
                {"type": "Ball Possession", "value": "60%"},
                {"type": "Total Shots", "value": 12},
                {"type": "Yellow Cards", "value": 3},
                {"type": "Red Cards", "value": 0},
            ],
        },
    ]


def test_team_stats_matched_by_id_not_index():
    raw = _swapped_raw_stats()
    home = _build_team_stats_for_id(raw, 100)
    away = _build_team_stats_for_id(raw, 200)
    assert home["possession"] == "60%"
    assert away["possession"] == "40%"
    assert home["shots_total"] == 12
    assert away["shots_total"] == 5


def test_missing_team_block_returns_nulls_not_other_side():
    raw = _swapped_raw_stats()
    missing = _build_team_stats_for_id(raw, 999)
    assert missing["possession"] is None
    assert missing["shots_total"] is None


def test_cards_from_statistics_zero_is_real():
    raw = _swapped_raw_stats()
    home_list = _team_stat_list(raw, 100)
    away_list = _team_stat_list(raw, 200)
    assert _resolve_cards(
        home_list, [], 100, stats_type="Yellow Cards", event_details=("Yellow Card",)
    ) == 3
    assert _resolve_cards(
        away_list, [], 200, stats_type="Yellow Cards", event_details=("Yellow Card",)
    ) == 1
    assert _resolve_cards(
        home_list, [], 100, stats_type="Red Cards", event_details=("Red Card",)
    ) == 0


def test_cards_null_when_no_stats_and_empty_events():
    """Empty events must NOT invent yellow_cards=0."""
    assert (
        _resolve_cards(
            None, [], 100, stats_type="Yellow Cards", event_details=("Yellow Card",)
        )
        is None
    )
    assert (
        _resolve_cards(
            [], [], 100, stats_type="Yellow Cards", event_details=("Yellow Card",)
        )
        is None
    )


def test_cards_from_events_only_when_events_present():
    events = [
        {"type": "Card", "detail": "Yellow Card", "team": {"id": 100}},
        {"type": "Card", "detail": "Yellow Card", "team": {"id": 100}},
        {"type": "Card", "detail": "Red Card", "team": {"id": 200}},
    ]
    assert (
        _resolve_cards(
            None, events, 100, stats_type="Yellow Cards", event_details=("Yellow Card",)
        )
        == 2
    )
    assert (
        _resolve_cards(
            None,
            events,
            200,
            stats_type="Red Cards",
            event_details=("Red Card", "Yellow Red Card"),
        )
        == 1
    )
