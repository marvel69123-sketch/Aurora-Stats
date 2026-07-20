"""
P2b Wave 3 — Injury context (confirmed provider rows only).
Never invents absences.
"""

from __future__ import annotations

from typing import Any


def _row_from_api(item: dict[str, Any]) -> dict[str, Any] | None:
    player = item.get("player") or {}
    team = item.get("team") or {}
    fixture = item.get("fixture") or {}
    name = player.get("name") if isinstance(player, dict) else item.get("player_name")
    if not name and not item.get("reason"):
        return None
    return {
        "player": name,
        "player_id": player.get("id") if isinstance(player, dict) else item.get("player_id"),
        "team": team.get("name") if isinstance(team, dict) else item.get("team"),
        "team_id": team.get("id") if isinstance(team, dict) else item.get("team_id"),
        "reason": item.get("reason") or (player.get("reason") if isinstance(player, dict) else None),
        "type": item.get("type") or (player.get("type") if isinstance(player, dict) else None),
        "fixture_id": fixture.get("id") if isinstance(fixture, dict) else item.get("fixture_id"),
    }


def normalize_injuries(raw: Any) -> dict[str, Any] | None:
    """
    Accept list of injury dicts or API {response: [...]}.
    """
    rows: list = []
    if isinstance(raw, dict):
        if isinstance(raw.get("response"), list):
            rows = raw["response"]
        elif isinstance(raw.get("home"), list) or isinstance(raw.get("away"), list):
            # already side-split
            home = [_row_from_api(x) for x in (raw.get("home") or []) if isinstance(x, dict)]
            away = [_row_from_api(x) for x in (raw.get("away") or []) if isinstance(x, dict)]
            home = [h for h in home if h]
            away = [a for a in away if a]
            if not home and not away:
                return None
            return {
                "home": home,
                "away": away,
                "total": len(home) + len(away),
                "source": raw.get("source") or "payload",
            }
        else:
            return None
    elif isinstance(raw, list):
        rows = raw
    else:
        return None

    out: list[dict[str, Any]] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        row = _row_from_api(item)
        if row:
            out.append(row)
    if not out:
        return None
    return {
        "home": [],  # side split deferred when team ids unknown
        "away": [],
        "all": out,
        "total": len(out),
        "source": "api_football",
    }


def split_injuries_by_team(
    bundle: dict[str, Any] | None,
    *,
    home_id: int | None,
    away_id: int | None,
    home_name: str | None = None,
    away_name: str | None = None,
) -> dict[str, Any] | None:
    if not bundle:
        return None
    if bundle.get("home") or bundle.get("away"):
        if bundle.get("total", 0) > 0 or bundle.get("home") or bundle.get("away"):
            return bundle
    all_rows = list(bundle.get("all") or [])
    home: list[dict[str, Any]] = []
    away: list[dict[str, Any]] = []
    hn = (home_name or "").lower()
    an = (away_name or "").lower()
    for row in all_rows:
        tid = row.get("team_id")
        tname = str(row.get("team") or "").lower()
        if home_id is not None and tid == home_id:
            home.append(row)
        elif away_id is not None and tid == away_id:
            away.append(row)
        elif hn and tname == hn:
            home.append(row)
        elif an and tname == an:
            away.append(row)
    return {
        "home": home,
        "away": away,
        "all": all_rows,
        "total": len(all_rows),
        "source": bundle.get("source") or "api_football",
    }


def resolve_injuries_slot(
    data: dict[str, Any] | None,
    *,
    home_id: int | None = None,
    away_id: int | None = None,
    home_name: str | None = None,
    away_name: str | None = None,
) -> tuple[Any, str, str, str | None]:
    if not isinstance(data, dict):
        return None, "missing", "none", None
    raw = data.get("injuries")
    if raw is None:
        raw = data.get("_injuries_raw")
    norm = normalize_injuries(raw)
    if not norm:
        return None, "missing", "none", None
    split = split_injuries_by_team(
        norm,
        home_id=home_id,
        away_id=away_id,
        home_name=home_name,
        away_name=away_name,
    )
    return split, "confirmed", str((split or {}).get("source") or "injuries"), None


def injury_coverage(value: Any, quality: str) -> float:
    if quality not in {"confirmed", "stale"} or not isinstance(value, dict):
        return 0.0
    total = int(value.get("total") or 0)
    if total <= 0:
        # empty confirmed list still means "checked" — weak coverage
        return 0.15 if quality == "confirmed" else 0.0
    # density cap
    score = min(1.0, 0.35 + 0.15 * min(total, 4))
    if quality == "stale":
        score *= 0.5
    return round(score, 4)
