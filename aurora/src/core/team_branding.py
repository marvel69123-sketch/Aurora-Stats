"""
Static branding for known clubs/national teams — logos when fixture is missing.

Used only to enrich PARTIAL analyze payloads (presentation). Does not change
methodology / market / confidence engines.
"""

from __future__ import annotations

from typing import Any

# Official media CDN used by API-Football
_LOGO = "https://media.api-sports.io/football/teams/{tid}.png"

# Canonical fold key → API-Football team id + display hints
TEAM_BRANDING: dict[str, dict[str, Any]] = {
    "arsenal": {"id": 42, "name": "Arsenal", "country": "England", "league": "Premier League"},
    "chelsea": {"id": 49, "name": "Chelsea", "country": "England", "league": "Premier League"},
    "liverpool": {"id": 40, "name": "Liverpool", "country": "England", "league": "Premier League"},
    "manchester united": {"id": 33, "name": "Manchester United", "country": "England", "league": "Premier League"},
    "manchester city": {"id": 50, "name": "Manchester City", "country": "England", "league": "Premier League"},
    "tottenham": {"id": 47, "name": "Tottenham", "country": "England", "league": "Premier League"},
    "barcelona": {"id": 529, "name": "Barcelona", "country": "Spain", "league": "La Liga"},
    "real madrid": {"id": 541, "name": "Real Madrid", "country": "Spain", "league": "La Liga"},
    "atletico madrid": {"id": 530, "name": "Atletico Madrid", "country": "Spain", "league": "La Liga"},
    "bayern munich": {"id": 157, "name": "Bayern Munich", "country": "Germany", "league": "Bundesliga"},
    "borussia dortmund": {"id": 165, "name": "Borussia Dortmund", "country": "Germany", "league": "Bundesliga"},
    "paris saint-germain": {"id": 85, "name": "Paris Saint-Germain", "country": "France", "league": "Ligue 1"},
    "juventus": {"id": 496, "name": "Juventus", "country": "Italy", "league": "Serie A"},
    "ac milan": {"id": 489, "name": "AC Milan", "country": "Italy", "league": "Serie A"},
    "inter milan": {"id": 505, "name": "Inter Milan", "country": "Italy", "league": "Serie A"},
    "flamengo": {"id": 127, "name": "Flamengo", "country": "Brazil", "league": "Serie A"},
    "palmeiras": {"id": 121, "name": "Palmeiras", "country": "Brazil", "league": "Serie A"},
    "santos": {"id": 128, "name": "Santos", "country": "Brazil", "league": "Serie A"},
    "brazil": {"id": 6, "name": "Brazil", "country": "Brazil", "league": "International"},
    "argentina": {"id": 26, "name": "Argentina", "country": "Argentina", "league": "International"},
    "england": {"id": 10, "name": "England", "country": "England", "league": "International"},
    "france": {"id": 2, "name": "France", "country": "France", "league": "International"},
    "germany": {"id": 25, "name": "Germany", "country": "Germany", "league": "International"},
    "spain": {"id": 9, "name": "Spain", "country": "Spain", "league": "International"},
}


def _fold_key(name: str) -> str:
    from src.core.entity_resolver import fold, normalize_team_name

    canonical = normalize_team_name(name or "")
    return fold(canonical or name or "")


def lookup_branding(name: str | None) -> dict[str, Any] | None:
    if not name:
        return None
    from src.core.entity_resolver import fold

    key = _fold_key(name)
    hit = TEAM_BRANDING.get(key)
    if hit:
        return dict(hit)
    raw = fold(name)
    hit = TEAM_BRANDING.get(raw)
    return dict(hit) if hit else None


def logo_url_for_team(name: str | None, team_id: int | None = None) -> str | None:
    if team_id and int(team_id) > 0:
        return _LOGO.format(tid=int(team_id))
    brand = lookup_branding(name)
    if brand and brand.get("id"):
        return _LOGO.format(tid=int(brand["id"]))
    return None


def enrich_analyze_teams(
    data: dict[str, Any],
    *,
    home: str | None = None,
    away: str | None = None,
) -> dict[str, Any]:
    """
    Fill missing logos / names / light competition hints on analyze payloads.
    Safe no-op when data already has logos from a real fixture.
    """
    if not isinstance(data, dict):
        return data
    teams = dict(data.get("teams") or {})
    home_t = dict(teams.get("home") or {})
    away_t = dict(teams.get("away") or {})

    h_name = home or home_t.get("name")
    a_name = away or away_t.get("name")
    h_brand = lookup_branding(h_name)
    a_brand = lookup_branding(a_name)

    if h_brand:
        home_t["name"] = home_t.get("name") or h_brand["name"]
        if not home_t.get("logo"):
            home_t["logo"] = _LOGO.format(tid=int(h_brand["id"]))
        if not home_t.get("id"):
            home_t["id"] = int(h_brand["id"])
    if a_brand:
        away_t["name"] = away_t.get("name") or a_brand["name"]
        if not away_t.get("logo"):
            away_t["logo"] = _LOGO.format(tid=int(a_brand["id"]))
        if not away_t.get("id"):
            away_t["id"] = int(a_brand["id"])

    teams["home"] = home_t
    teams["away"] = away_t
    data["teams"] = teams

    league = dict(data.get("league") or {})
    league_name = (league.get("name") or "").strip()
    if not league_name or league_name.lower() in {"unknown", "n/a", ""}:
        # Prefer shared domestic league when both sides share one
        if h_brand and a_brand and h_brand.get("league") == a_brand.get("league"):
            league["name"] = h_brand["league"]
            league["country"] = h_brand.get("country") or a_brand.get("country")
        elif h_brand and a_brand:
            # International clash
            if h_brand.get("league") == "International" or a_brand.get("league") == "International":
                league["name"] = "International"
                league["country"] = "World"
        data["league"] = league

    return data
