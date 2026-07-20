"""
P2b Wave 3 — Odds integration for NMB.

Normalizes provider odds payloads. Never invents prices or EV.
"""

from __future__ import annotations

from typing import Any


def _f(val: Any) -> float | None:
    try:
        if val is None or val == "":
            return None
        return float(val)
    except (TypeError, ValueError):
        return None


def _pick_1x2(bet: dict[str, Any]) -> dict[str, float | None] | None:
    name = str(bet.get("name") or "").lower()
    if name not in {"match winner", "1x2", "full time result", "result"}:
        return None
    home = draw = away = None
    for v in bet.get("values") or []:
        if not isinstance(v, dict):
            continue
        label = str(v.get("value") or "").strip().lower()
        odd = _f(v.get("odd"))
        if label in {"home", "1"}:
            home = odd
        elif label in {"draw", "x"}:
            draw = odd
        elif label in {"away", "2"}:
            away = odd
    if home is None and draw is None and away is None:
        return None
    return {"home": home, "draw": draw, "away": away}


def normalize_odds_payload(raw: Any) -> dict[str, Any] | None:
    """
    Accept analyze-shaped odds or API-Football /odds response.
    Returns None when no confirmed prices exist.
    """
    if raw is None:
        return None

    # Already normalized
    if isinstance(raw, dict) and raw.get("1x2") and isinstance(raw["1x2"], dict):
        x = raw["1x2"]
        if any(_f(x.get(k)) is not None for k in ("home", "draw", "away")):
            return {
                "1x2": {
                    "home": _f(x.get("home")),
                    "draw": _f(x.get("draw")),
                    "away": _f(x.get("away")),
                },
                "bookmaker": raw.get("bookmaker"),
                "live": bool(raw.get("live")),
                "multi": bool(raw.get("multi")),
                "markets": list(raw.get("markets") or ["1x2"]),
                "source": raw.get("source") or "payload",
            }

    # API-Football: {response: [{bookmakers: [{bets: [...]}]}]}
    rows = None
    if isinstance(raw, dict):
        if isinstance(raw.get("response"), list):
            rows = raw["response"]
        elif isinstance(raw.get("bookmakers"), list):
            rows = [raw]
    if isinstance(raw, list):
        rows = raw
    if not rows:
        return None

    best_1x2 = None
    book_name = None
    markets: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        for bm in row.get("bookmakers") or []:
            if not isinstance(bm, dict):
                continue
            for bet in bm.get("bets") or []:
                if not isinstance(bet, dict):
                    continue
                mname = str(bet.get("name") or "")
                if mname and mname not in markets:
                    markets.append(mname)
                picked = _pick_1x2(bet)
                if picked and best_1x2 is None:
                    best_1x2 = picked
                    book_name = bm.get("name")
    if not best_1x2:
        return None
    return {
        "1x2": best_1x2,
        "bookmaker": book_name,
        "live": False,
        "multi": len(markets) > 1,
        "markets": markets[:12],
        "source": "api_football",
    }


def resolve_odds_slot(data: dict[str, Any] | None) -> tuple[Any, str, str, str | None]:
    if not isinstance(data, dict):
        return None, "missing", "none", None
    raw = data.get("odds")
    if raw is None and isinstance(data.get("_odds_raw"), (dict, list)):
        raw = data.get("_odds_raw")
    norm = normalize_odds_payload(raw)
    if not norm:
        return None, "missing", "none", None
    return norm, "confirmed", str(norm.get("source") or "odds"), None


def odds_coverage(value: Any, quality: str) -> float:
    if quality == "confirmed" and isinstance(value, dict) and value.get("1x2"):
        sides = sum(
            1
            for k in ("home", "draw", "away")
            if (value.get("1x2") or {}).get(k) is not None
        )
        return round(sides / 3.0, 4)
    if quality == "stale":
        return 0.5
    return 0.0
