"""
P2b Wave 3 — Calendar enrichment from confirmed fixture/league facts.
Never invents opponents or kickoffs.
"""

from __future__ import annotations

from typing import Any


def _iso_date(kickoff: Any) -> str | None:
    if not kickoff:
        return None
    s = str(kickoff)
    if "T" in s:
        return s.split("T", 1)[0]
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    return None


def build_calendar_context(data: dict[str, Any] | None) -> dict[str, Any] | None:
    """
    Build calendar card from analyze payload (+ optional calendar list).
    Confirmed only when fixture date or league round is present.
    """
    if not isinstance(data, dict):
        return None

    # Explicit calendar list from ingest (fixtures by date / team next)
    explicit = data.get("calendar")
    entries: list[dict[str, Any]] = []
    if isinstance(explicit, list):
        for row in explicit:
            if not isinstance(row, dict):
                continue
            fx = row.get("fixture") or row
            teams = row.get("teams") or {}
            date = (fx.get("date") if isinstance(fx, dict) else None) or row.get("date")
            home = (teams.get("home") or {}).get("name") if isinstance(teams, dict) else row.get("home")
            away = (teams.get("away") or {}).get("name") if isinstance(teams, dict) else row.get("away")
            if date or (home and away):
                entries.append(
                    {
                        "date": date,
                        "home": home,
                        "away": away,
                        "fixture_id": (fx.get("id") if isinstance(fx, dict) else row.get("id")),
                        "status": (
                            ((fx.get("status") or {}).get("short"))
                            if isinstance(fx, dict)
                            else row.get("status")
                        ),
                    }
                )

    fx = data.get("fixture") or {}
    league = data.get("league") or {}
    teams = data.get("teams") or {}
    kickoff = fx.get("date")
    day = _iso_date(kickoff)
    round_name = league.get("round")
    league_name = league.get("name")
    venue = None
    if isinstance(fx.get("venue"), dict):
        venue = fx["venue"].get("name")

    if not day and not round_name and not entries:
        return None

    return {
        "match_date": day,
        "kickoff": kickoff,
        "league": league_name,
        "round": round_name,
        "season": league.get("season"),
        "venue": venue,
        "home": (teams.get("home") or {}).get("name"),
        "away": (teams.get("away") or {}).get("name"),
        "fixture_id": fx.get("id") if fx.get("id") not in (None, 0, "0") else None,
        "nearby": entries[:10],
        "source": "fixture+league" if not entries else "fixture+calendar_list",
    }


def calendar_coverage(value: Any, quality: str) -> float:
    if quality not in {"confirmed", "stale"} or not isinstance(value, dict):
        return 0.0
    score = 0.0
    if value.get("match_date") or value.get("kickoff"):
        score += 0.5
    if value.get("round") or value.get("league"):
        score += 0.25
    if value.get("nearby"):
        score += 0.25
    if quality == "stale":
        score *= 0.5
    return round(min(1.0, score), 4)
