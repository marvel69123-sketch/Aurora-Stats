"""
P2b Wave 1 — Normalized Match Bundle.
P2b Wave 2 — xG / events / live enrichment hooks (additive).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

SignalQuality = Literal[
    "confirmed", "inferred", "missing", "stale", "rate_limited", "empty"
]


@dataclass
class SignalSlot:
    name: str
    value: Any = None
    quality: SignalQuality = "missing"
    source: str = "none"
    fetched_at: float | None = None
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "quality": self.quality,
            "source": self.source,
            "fetched_at": self.fetched_at,
            "note": self.note,
        }


@dataclass
class NormalizedMatchBundle:
    home: str | None = None
    away: str | None = None
    fixture_id: int | None = None
    status_short: str | None = None
    kickoff: str | None = None
    league_id: int | None = None
    season: int | None = None
    signals: dict[str, SignalSlot] = field(default_factory=dict)
    rate_limited: bool = False
    user_wants_live: bool = False
    binding_quality: str = "NONE"
    meta: dict[str, Any] = field(default_factory=dict)

    def slot(self, name: str) -> SignalSlot:
        if name not in self.signals:
            self.signals[name] = SignalSlot(name=name)
        return self.signals[name]

    def set_signal(
        self,
        name: str,
        value: Any,
        *,
        quality: SignalQuality,
        source: str,
        fetched_at: float | None = None,
        note: str | None = None,
    ) -> None:
        self.signals[name] = SignalSlot(
            name=name,
            value=value,
            quality=quality,
            source=source,
            fetched_at=fetched_at,
            note=note,
        )

    def confirmed_names(self) -> list[str]:
        return [n for n, s in self.signals.items() if s.quality == "confirmed"]

    def missing_names(self) -> list[str]:
        return [
            n
            for n, s in self.signals.items()
            if s.quality in {"missing", "empty", "rate_limited"}
        ]

    def inferred_names(self) -> list[str]:
        return [n for n, s in self.signals.items() if s.quality == "inferred"]

    def completion_rate(self) -> float:
        """Wave 1 critical completion (unchanged contract)."""
        critical = ("fixture", "teams", "statistics", "standings", "status")
        present = 0
        for name in critical:
            s = self.signals.get(name)
            if s and s.quality == "confirmed":
                present += 1
        return round(present / len(critical), 4)

    def wave2_completion_rate(self) -> float:
        """Wave 2 — includes xG, events, live_momentum."""
        names = (
            "fixture",
            "teams",
            "statistics",
            "standings",
            "status",
            "xg",
            "events",
            "live_momentum",
        )
        present = 0
        for name in names:
            s = self.signals.get(name)
            if s and s.quality in {"confirmed", "stale"}:
                # stale still counts as recovered coverage (not empty)
                present += 1 if s.quality == "confirmed" else 0.5
            elif s and s.quality == "inferred" and name == "xg":
                present += 0.25
        return round(present / len(names), 4)

    def xg_coverage(self) -> float:
        s = self.signals.get("xg")
        if not s:
            return 0.0
        if s.quality == "confirmed":
            val = s.value if isinstance(s.value, dict) else {}
            sides = sum(
                1
                for k in ("home", "away")
                if val.get(k) not in (None, "", 0, "0")
            )
            return round(sides / 2.0, 4)
        if s.quality == "stale":
            return 0.5
        if s.quality == "inferred":
            return 0.25
        return 0.0

    def event_coverage(self) -> float:
        s = self.signals.get("events")
        if not s:
            return 0.0
        if s.quality == "confirmed":
            return 1.0
        if s.quality == "stale":
            return 0.5
        return 0.0

    def odds_coverage(self) -> float:
        from src.data.odds import odds_coverage as _oc

        s = self.signals.get("odds")
        if not s:
            return 0.0
        return _oc(s.value, s.quality)

    def calendar_coverage(self) -> float:
        from src.data.calendar import calendar_coverage as _cc

        s = self.signals.get("calendar")
        if not s:
            return 0.0
        return _cc(s.value, s.quality)

    def lineup_coverage(self) -> float:
        from src.data.lineups_norm import lineup_coverage as _lc

        s = self.signals.get("lineups")
        if not s:
            return 0.0
        return _lc(s.value, s.quality)

    def injury_coverage(self) -> float:
        from src.data.injuries import injury_coverage as _ic

        s = self.signals.get("injuries")
        if not s:
            return 0.0
        return _ic(s.value, s.quality)

    def wave3_completion_rate(self) -> float:
        names = (
            "odds",
            "calendar",
            "lineups",
            "injuries",
            "narrative",
        )
        present = 0.0
        for name in names:
            s = self.signals.get(name)
            if not s:
                continue
            if s.quality == "confirmed":
                present += 1.0
            elif s.quality == "stale":
                present += 0.5
        return round(present / len(names), 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "home": self.home,
            "away": self.away,
            "fixture_id": self.fixture_id,
            "status_short": self.status_short,
            "kickoff": self.kickoff,
            "league_id": self.league_id,
            "season": self.season,
            "signals": {k: v.to_dict() for k, v in self.signals.items()},
            "rate_limited": self.rate_limited,
            "user_wants_live": self.user_wants_live,
            "binding_quality": self.binding_quality,
            "completion_rate": self.completion_rate(),
            "wave2_completion_rate": self.wave2_completion_rate(),
            "wave3_completion_rate": self.wave3_completion_rate(),
            "xg_coverage": self.xg_coverage(),
            "event_coverage": self.event_coverage(),
            "odds_coverage": self.odds_coverage(),
            "calendar_coverage": self.calendar_coverage(),
            "lineup_coverage": self.lineup_coverage(),
            "injury_coverage": self.injury_coverage(),
            "meta": dict(self.meta),
        }


def _has_stats_payload(stats: Any) -> bool:
    if not isinstance(stats, dict):
        return False
    home = stats.get("home") or {}
    away = stats.get("away") or {}
    if not isinstance(home, dict) or not isinstance(away, dict):
        return False
    # any numeric-ish field
    for side in (home, away):
        for k, v in side.items():
            if k in {"team_id", "name"}:
                continue
            if v not in (None, "", 0, "0"):
                return True
    return False


def build_nmb_from_analyze_payload(
    data: dict[str, Any] | None,
    *,
    binding_quality: str = "PARTIAL",
    user_wants_live: bool = False,
    rate_limited: bool = False,
) -> NormalizedMatchBundle:
    """Build NMB from existing analyze.py payload shape — no invention."""
    nmb = NormalizedMatchBundle(
        binding_quality=binding_quality,
        user_wants_live=user_wants_live,
        rate_limited=rate_limited,
    )
    if not isinstance(data, dict):
        nmb.set_signal("fixture", None, quality="missing", source="analyze")
        nmb.set_signal("teams", None, quality="missing", source="analyze")
        return nmb

    teams = data.get("teams") or {}
    home = (teams.get("home") or {}).get("name")
    away = (teams.get("away") or {}).get("name")
    nmb.home = str(home) if home else None
    nmb.away = str(away) if away else None
    if nmb.home and nmb.away:
        nmb.set_signal(
            "teams",
            {"home": nmb.home, "away": nmb.away},
            quality="confirmed",
            source="analyze",
        )
    else:
        nmb.set_signal("teams", None, quality="missing", source="analyze")

    fx = data.get("fixture") or {}
    fid = fx.get("id")
    try:
        nmb.fixture_id = int(fid) if fid not in (None, 0, "0") else None
    except (TypeError, ValueError):
        nmb.fixture_id = None
    status = (fx.get("status") or {})
    if isinstance(status, dict):
        nmb.status_short = str(status.get("short") or "") or None
    nmb.kickoff = fx.get("date")
    league = data.get("league") or {}
    try:
        nmb.league_id = int(league["id"]) if league.get("id") is not None else None
    except (TypeError, ValueError):
        nmb.league_id = None
    try:
        nmb.season = int(league["season"]) if league.get("season") is not None else None
    except (TypeError, ValueError):
        nmb.season = None

    if nmb.fixture_id:
        nmb.set_signal(
            "fixture",
            {"id": nmb.fixture_id, "date": nmb.kickoff},
            quality="confirmed",
            source="analyze",
        )
        nmb.binding_quality = "FULL" if binding_quality == "FULL" else "PARTIAL"
    else:
        nmb.set_signal(
            "fixture",
            None,
            quality="missing",
            source="analyze",
            note="no fixture_id",
        )

    if nmb.status_short:
        nmb.set_signal(
            "status",
            {"short": nmb.status_short, "elapsed": status.get("elapsed") if isinstance(status, dict) else None},
            quality="confirmed",
            source="analyze",
        )
    else:
        nmb.set_signal("status", None, quality="missing", source="analyze")

    stats = data.get("statistics")
    if _has_stats_payload(stats):
        nmb.set_signal("statistics", stats, quality="confirmed", source="analyze")
    else:
        nmb.set_signal("statistics", stats, quality="missing", source="analyze")

    standings = data.get("standings") or {}
    if (standings.get("home") or standings.get("away")):
        nmb.set_signal("standings", standings, quality="confirmed", source="analyze")
    else:
        nmb.set_signal("standings", standings, quality="missing", source="analyze")

    # Wave 2 — normalize events (append-only, stable ids)
    from src.data.events_norm import event_coverage, normalize_events

    raw_events = data.get("events")
    norm_events = normalize_events(raw_events if isinstance(raw_events, list) else [])
    if norm_events:
        nmb.set_signal(
            "events",
            norm_events,
            quality="confirmed",
            source="analyze",
            note=f"normalized:{event_coverage(norm_events)['count']}",
        )
    else:
        nmb.set_signal("events", [], quality="missing", source="analyze")

    # Wave 3 — lineup normalization (keeps confirmed-only semantics)
    from src.data.lineups_norm import normalize_lineups

    lineups_raw = data.get("lineups") or {}
    lineups = normalize_lineups(lineups_raw) or {}
    if lineups.get("home") or lineups.get("away"):
        nmb.set_signal("lineups", lineups, quality="confirmed", source="lineups_norm")
    else:
        nmb.set_signal("lineups", lineups_raw, quality="missing", source="analyze")

    score = data.get("score") or {}
    cur = score.get("current") or {}
    if cur.get("home") is not None or cur.get("away") is not None:
        nmb.set_signal("score", score, quality="confirmed", source="analyze")
    else:
        nmb.set_signal("score", score, quality="missing", source="analyze")

    referee = None
    if isinstance(fx, dict):
        referee = fx.get("referee")
    if referee:
        nmb.set_signal("referee", referee, quality="confirmed", source="analyze")
    else:
        nmb.set_signal("referee", None, quality="missing", source="analyze")

    # Wave 2 — xG integration (confirmed from stats; optional inferred GPG)
    from src.data.xg import resolve_xg_slot

    xg_val, xg_q, xg_src, xg_note = resolve_xg_slot(
        stats, standings, allow_inferred=True
    )
    nmb.set_signal(
        "xg",
        xg_val,
        quality=xg_q,  # type: ignore[arg-type]
        source=xg_src,
        note=xg_note,
    )

    # Provenance overlays from ingest (stale / rate_limited)
    prov = data.get("_signal_provenance") or {}
    if isinstance(prov, dict):
        for name, info in prov.items():
            if not isinstance(info, dict):
                continue
            slot = nmb.signals.get(name) or nmb.slot(name)
            src = str(info.get("source") or slot.source)
            q = str(info.get("quality") or "")
            if q == "stale" and slot.quality == "confirmed":
                slot.quality = "stale"
                slot.note = "served_from_stale_cache"
            elif q == "rate_limited" and slot.quality in {"missing", "empty"}:
                slot.quality = "rate_limited"
            slot.source = src
            if info.get("fetched_at") is not None:
                try:
                    slot.fetched_at = float(info["fetched_at"])
                except (TypeError, ValueError):
                    pass

    if rate_limited:
        nmb.rate_limited = True
        for name in ("statistics", "standings", "events"):
            s = nmb.slot(name)
            if s.quality == "missing":
                s.quality = "rate_limited"
                s.note = "rate_limited_or_fetch_failed"

    # Wave 2 — live enrichment
    from src.data.live_enrichment import build_live_momentum, live_enrichment_quality

    home_id = None
    away_id = None
    try:
        home_id = int((teams.get("home") or {}).get("id") or 0) or None
        away_id = int((teams.get("away") or {}).get("id") or 0) or None
    except (TypeError, ValueError):
        pass
    status_dict = status if isinstance(status, dict) else {}
    # prefer minute key from analyze mapping
    momentum = build_live_momentum(
        status_short=nmb.status_short,
        status=status_dict,
        score=score if isinstance(score, dict) else None,
        events=norm_events,
        home_id=home_id,
        away_id=away_id,
    )
    ev_q = _q_name(nmb, "events")
    st_q = _q_name(nmb, "status")
    lm_q = live_enrichment_quality(
        momentum, events_quality=ev_q, status_quality=st_q
    )
    nmb.set_signal(
        "live_momentum",
        momentum,
        quality=lm_q,  # type: ignore[arg-type]
        source="live_enrichment",
        note=None if momentum else "no_live_context",
    )

    # Wave 3 — odds / calendar / injuries / narrative
    from src.data.calendar import build_calendar_context
    from src.data.injuries import resolve_injuries_slot
    from src.data.narrative import build_contextual_narrative, narrative_quality
    from src.data.odds import resolve_odds_slot

    odds_val, odds_q, odds_src, odds_note = resolve_odds_slot(data)
    nmb.set_signal(
        "odds",
        odds_val,
        quality=odds_q,  # type: ignore[arg-type]
        source=odds_src,
        note=odds_note,
    )

    cal = build_calendar_context(data)
    if cal:
        nmb.set_signal("calendar", cal, quality="confirmed", source=str(cal.get("source") or "calendar"))
    else:
        nmb.set_signal("calendar", None, quality="missing", source="none")

    inj_val, inj_q, inj_src, inj_note = resolve_injuries_slot(
        data,
        home_id=home_id,
        away_id=away_id,
        home_name=nmb.home,
        away_name=nmb.away,
    )
    nmb.set_signal(
        "injuries",
        inj_val,
        quality=inj_q,  # type: ignore[arg-type]
        source=inj_src,
        note=inj_note,
    )

    # Re-apply provenance for wave3 signals if present
    if isinstance(prov, dict):
        for name in ("odds", "injuries", "calendar", "lineups"):
            info = prov.get(name)
            if not isinstance(info, dict):
                continue
            slot = nmb.signals.get(name) or nmb.slot(name)
            q = str(info.get("quality") or "")
            if q == "stale" and slot.quality == "confirmed":
                slot.quality = "stale"
                slot.note = "served_from_stale_cache"
            elif q == "rate_limited" and slot.quality in {"missing", "empty"}:
                slot.quality = "rate_limited"
            if info.get("source"):
                slot.source = str(info["source"])

    narrative = build_contextual_narrative(nmb)
    nmb.set_signal(
        "narrative",
        narrative,
        quality=narrative_quality(narrative),  # type: ignore[arg-type]
        source="narrative",
        note=None if narrative else "insufficient_confirmed_context",
    )

    # Freshness after wave2+wave3 slots
    from src.data.freshness import propagate_freshness

    propagate_freshness(nmb)
    nmb.meta["wave"] = "p2b_wave2"  # Wave 2 contract tag preserved
    nmb.meta["wave3"] = "p2b_wave3"
    nmb.meta["xg_coverage"] = nmb.xg_coverage()
    nmb.meta["event_coverage"] = nmb.event_coverage()
    nmb.meta["wave2_completion_rate"] = nmb.wave2_completion_rate()
    nmb.meta["odds_coverage"] = nmb.odds_coverage()
    nmb.meta["calendar_coverage"] = nmb.calendar_coverage()
    nmb.meta["lineup_coverage"] = nmb.lineup_coverage()
    nmb.meta["injury_coverage"] = nmb.injury_coverage()
    nmb.meta["wave3_completion_rate"] = nmb.wave3_completion_rate()

    return nmb


def _q_name(nmb: NormalizedMatchBundle, name: str) -> str:
    s = nmb.signals.get(name)
    return str(s.quality) if s else "missing"
