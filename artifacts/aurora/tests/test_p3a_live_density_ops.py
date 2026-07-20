"""P3-A ops collector — unit tests (no API required)."""

from __future__ import annotations

from src.ops.live_density import (
    ProviderCall,
    get_collector,
    record_analyze_sample,
    reset_collector_for_tests,
    sample_from_analyze_payload,
)


def test_sample_resolved_premium():
    payload = {
        "fixture": {"id": 123, "date": "2026-07-01"},
        "league": {"id": 71, "name": "Serie A"},
        "teams": {"home": {"name": "A"}, "away": {"name": "B"}},
        "statistics": {"home": {"shots_total": 5}, "away": {}},
        "_partial": False,
        "_drs": {
            "drs": 72,
            "tier": "T3",
            "premium_analysis": True,
            "missing": ["odds"],
            "confirmed": ["fixture", "statistics"],
        },
        "_data_plane": {
            "xg_coverage": 0.5,
            "odds_coverage": 0.0,
            "lineup_coverage": 0.0,
            "event_coverage": 1.0,
            "premium_analysis": True,
        },
        "_nmb": {
            "signals": {
                "narrative": {"quality": "confirmed", "value": {"bullets": ["x"]}},
                "calendar": {
                    "quality": "confirmed",
                    "value": {"match_date": "2026-07-01"},
                },
                "statistics": {"quality": "confirmed"},
            },
            "xg_coverage": 0.5,
        },
        "_signal_provenance": {"statistics": {"source": "network", "quality": "confirmed"}},
    }
    s = sample_from_analyze_payload(payload, home="A", away="B", league_hint="BR")
    assert s.resolved is True
    assert s.tier == "T3"
    assert s.premium_analysis is True
    assert s.narrative_present is True
    assert s.calendar_empty is False


def test_sample_unresolved_soft_miss():
    payload = {
        "fixture": {"id": 0},
        "_partial": True,
        "league": {"name": "Unknown"},
        "_drs": {"drs": 5, "tier": "T0", "missing": ["fixture"], "confirmed": ["teams"]},
        "_nmb": {"signals": {}},
    }
    s = sample_from_analyze_payload(payload, home="A", away="B")
    assert s.resolved is False
    assert s.soft_miss is True
    assert s.drs == 5


def test_collector_summarize_rates():
    reset_collector_for_tests()
    record_analyze_sample(
        {
            "fixture": {"id": 1},
            "league": {"name": "EPL"},
            "_drs": {
                "drs": 80,
                "tier": "T4",
                "premium_analysis": True,
                "missing": [],
                "confirmed": ["fixture"],
            },
            "_data_plane": {"premium_analysis": True},
            "_nmb": {
                "signals": {
                    "narrative": {"quality": "confirmed"},
                    "calendar": {"quality": "confirmed", "value": {"match_date": "x"}},
                    "statistics": {"quality": "confirmed"},
                }
            },
            "_signal_provenance": {
                "statistics": {"source": "network", "quality": "confirmed"}
            },
            "statistics": {"home": {"shots_total": 1}, "away": {}},
        },
        home="L",
        away="C",
        league_hint="EPL",
    )
    record_analyze_sample(
        {
            "fixture": {"id": 0},
            "_partial": True,
            "league": {"name": "Fiction"},
            "_drs": {"drs": 0, "tier": "T0", "missing": ["fixture"], "confirmed": []},
            "_nmb": {"signals": {}},
        },
        home="Goku",
        away="Naruto",
        league_hint="Fiction",
    )
    get_collector().record_provider(
        ProviderCall(path="/fixtures", ok=True, latency_ms=120)
    )
    get_collector().record_provider(
        ProviderCall(path="/odds", ok=False, latency_ms=40, error="429")
    )
    summary = get_collector().summarize()
    assert summary["sample_count"] == 2
    assert summary["resolve_rate"] == 0.5
    assert summary["t3_t4_live_rate"] == 0.5
    assert summary["premium_fixture_rate"] == 0.5
    assert summary["provider"]["provider_failure_rate"] == 0.5
    assert "odds" in str(summary["provider"]["limiting_paths"]) or summary[
        "provider"
    ]["by_path"].get("/odds")
