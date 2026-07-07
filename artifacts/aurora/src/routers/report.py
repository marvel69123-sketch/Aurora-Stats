from fastapi import APIRouter, Query
from fastapi.responses import PlainTextResponse
from src.routers.analyze import analyze_fixture

router = APIRouter()

# ── Emoji helpers ────────────────────────────────────────────────────────────

_EVENT_ICON = {
    "Goal": "⚽",
    "Card": {"Yellow Card": "🟨", "Red Card": "🟥", "Yellow Red Card": "🟥"},
    "subst": "🔄",
    "Var": "📺",
}


def _event_icon(event: dict) -> str:
    t = event.get("type", "")
    if t == "Goal":
        return "⚽"
    if t == "Card":
        return _EVENT_ICON["Card"].get(event.get("detail", ""), "🃏")
    if t == "subst":
        return "🔄"
    if t == "Var":
        return "📺"
    return "•"


# ── Stat helpers ─────────────────────────────────────────────────────────────

def _pct(val) -> str:
    if val is None:
        return "N/A"
    return str(val) if "%" in str(val) else f"{val}%"


def _val(val, default="N/A") -> str:
    return str(val) if val is not None else default


def _bar(home_raw, away_raw, width: int = 20) -> str:
    """ASCII possession bar."""
    try:
        h = int(str(home_raw).replace("%", ""))
        a = int(str(away_raw).replace("%", ""))
        total = h + a or 100
        h_blocks = round(h / total * width)
        a_blocks = width - h_blocks
        return f"[{'█' * h_blocks}{'░' * a_blocks}]"
    except Exception:
        return ""


def _form_display(form: str | None) -> str:
    if not form:
        return "N/A"
    icons = {"W": "✅", "D": "➖", "L": "❌"}
    return " ".join(icons.get(c, c) for c in form[-5:])


# ── Section builders ─────────────────────────────────────────────────────────

def _header(data: dict) -> str:
    fx = data["fixture"]
    lg = data["league"]
    teams = data["teams"]
    venue = fx["venue"]
    venue_str = ", ".join(filter(None, [venue.get("name"), venue.get("city")]))
    lines = [
        "╔══════════════════════════════════════════════════════╗",
        f"  MATCH REPORT",
        f"  {teams['home']['name']}  vs  {teams['away']['name']}",
        f"  {lg['name']} {lg['season']}  ·  {lg.get('round', '')}",
    ]
    if venue_str:
        lines.append(f"  {venue_str}")
    if fx.get("referee"):
        lines.append(f"  Referee: {fx['referee']}")
    lines.append("╚══════════════════════════════════════════════════════╝")
    return "\n".join(lines)


def _score_block(data: dict) -> str:
    fx = data["fixture"]
    sc = data["score"]
    teams = data["teams"]
    status = fx["status"]
    minute_str = f"  {status['minute']}'" if status.get("minute") else ""
    current = sc["current"]
    home_goals = _val(current["home"], "0")
    away_goals = _val(current["away"], "0")

    lines = [
        "",
        "── RESULT " + "─" * 45,
        f"  {teams['home']['name']}  {home_goals}  –  {away_goals}  {teams['away']['name']}",
        f"  Status: {status['long']}{minute_str}",
    ]
    ht = sc.get("halftime", {})
    if ht.get("home") is not None or ht.get("away") is not None:
        lines.append(f"  Half-time: {_val(ht['home'], '0')} – {_val(ht['away'], '0')}")
    ft = sc.get("fulltime", {})
    if ft.get("home") is not None or ft.get("away") is not None:
        lines.append(f"  Full-time: {_val(ft['home'], '0')} – {_val(ft['away'], '0')}")
    et = sc.get("extratime", {})
    if et.get("home") is not None:
        lines.append(f"  Extra time: {_val(et['home'])} – {_val(et['away'])}")
    pen = sc.get("penalty", {})
    if pen.get("home") is not None:
        lines.append(f"  Penalties: {_val(pen['home'])} – {_val(pen['away'])}")
    return "\n".join(lines)


def _stats_block(data: dict) -> str:
    teams = data["teams"]
    hs = data["statistics"]["home"]
    as_ = data["statistics"]["away"]
    hn = teams["home"]["name"]
    an = teams["away"]["name"]

    col_w = max(len(hn), len(an), 22) + 2
    h_col = hn.center(col_w)
    a_col = an.center(col_w)
    label_w = 20

    def row(label: str, hv, av) -> str:
        hv_s = _val(hv).center(col_w)
        av_s = _val(av).center(col_w)
        return f"  {label:<{label_w}}{hv_s}{av_s}"

    h_poss = hs.get("possession")
    a_poss = as_.get("possession")
    bar = _bar(h_poss, a_poss)

    lines = [
        "",
        "── STATISTICS " + "─" * 40,
        f"  {'':20}{h_col}{a_col}",
        "  " + "─" * (label_w + col_w * 2),
        row("Possession", _pct(h_poss), _pct(a_poss)),
        f"  {'':20}  {bar}",
        row("Shots (total)", hs.get("shots_total"), as_.get("shots_total")),
        row("Shots on target", hs.get("shots_on_target"), as_.get("shots_on_target")),
        row("Shots off target", hs.get("shots_off_target"), as_.get("shots_off_target")),
        row("Blocked shots", hs.get("blocked_shots"), as_.get("blocked_shots")),
        row("Corners", hs.get("corners"), as_.get("corners")),
        row("Fouls", hs.get("fouls"), as_.get("fouls")),
        row("Offsides", hs.get("offsides"), as_.get("offsides")),
        row("Saves", hs.get("saves"), as_.get("saves")),
        row("Passes (total)", hs.get("passes_total"), as_.get("passes_total")),
        row("Pass accuracy", _pct(hs.get("pass_accuracy")), _pct(as_.get("pass_accuracy"))),
        row("xG", _val(hs.get("xg")), _val(as_.get("xg"))),
    ]
    return "\n".join(lines)


def _cards_block(data: dict) -> str:
    teams = data["teams"]
    hs = data["statistics"]["home"]
    as_ = data["statistics"]["away"]
    hn = teams["home"]["name"]
    an = teams["away"]["name"]

    def card_str(stats: dict) -> str:
        y = _val(stats.get("yellow_cards"), "0")
        r = _val(stats.get("red_cards"), "0")
        parts = []
        if int(y) > 0:
            parts.append(f"🟨 {y} yellow")
        if int(r) > 0:
            parts.append(f"🟥 {r} red")
        return ", ".join(parts) if parts else "none"

    return "\n".join([
        "",
        "── CARDS " + "─" * 44,
        f"  {hn}: {card_str(hs)}",
        f"  {an}: {card_str(as_)}",
    ])


def _events_block(data: dict, max_events: int = 20) -> str:
    events = data.get("events", [])
    if not events:
        return "\n── MATCH EVENTS " + "─" * 37 + "\n  No events recorded."

    lines = ["", "── MATCH EVENTS " + "─" * 37]
    count = 0
    for e in events:
        if count >= max_events:
            remaining = len(events) - count
            lines.append(f"  … +{remaining} more events")
            break
        icon = _event_icon(e)
        minute = f"{e.get('minute', '?')}"
        if e.get("extra_minute"):
            minute += f"+{e['extra_minute']}"
        player = e.get("player") or ""
        team = e.get("team") or ""
        detail = e.get("detail") or e.get("type") or ""
        assist = e.get("assist")
        assist_str = f" (assist: {assist})" if assist else ""
        lines.append(f"  {minute:>5}'  {icon}  {detail} – {player}{assist_str}  [{team}]")
        count += 1
    return "\n".join(lines)


def _lineups_block(data: dict) -> str:
    lineups = data.get("lineups", {})
    teams = data["teams"]
    lines = ["", "── LINEUPS " + "─" * 42]

    for side in ("home", "away"):
        lu = lineups.get(side)
        team_name = teams[side]["name"]
        if not lu:
            lines.append(f"\n  {team_name}: lineup not available")
            continue
        formation = lu.get("formation") or "?"
        coach = lu.get("coach", {}) or {}
        coach_name = coach.get("name") or "Unknown"
        lines.append(f"\n  {team_name}  ({formation})  ·  Coach: {coach_name}")
        xi = lu.get("starting_xi") or []
        if xi:
            lines.append("  Starting XI:")
            for p in xi:
                num = p.get("number", "?")
                pos = p.get("position") or "?"
                name = p.get("name") or "?"
                lines.append(f"    {num:>2}. [{pos}]  {name}")
        subs = lu.get("substitutes") or []
        if subs:
            names = ", ".join(p.get("name", "?") for p in subs[:5])
            if len(subs) > 5:
                names += f" (+{len(subs)-5})"
            lines.append(f"  Bench: {names}")

    return "\n".join(lines)


def _standings_block(data: dict) -> str:
    lg = data["league"]
    std = data.get("standings", {})
    teams = data["teams"]

    if not std.get("home") and not std.get("away"):
        return ""

    lines = ["", f"── STANDINGS  ({lg['name']} {lg['season']}) " + "─" * 20]
    hdr = f"  {'#':>3}  {'Team':<26}  {'Pts':>4}  {'P':>3}  {'W':>3}  {'D':>3}  {'L':>3}  {'GD':>4}  Form"
    lines.append(hdr)
    lines.append("  " + "─" * 68)

    for side in ("home", "away"):
        s = std.get(side)
        if not s:
            continue
        team_name = teams[side]["name"]
        gd = s.get("goal_difference")
        gd_str = f"+{gd}" if gd is not None and gd > 0 else str(gd) if gd is not None else "N/A"
        form_str = _form_display(s.get("form"))
        lines.append(
            f"  {_val(s.get('rank')):>3}  {team_name:<26}  "
            f"{_val(s.get('points')):>4}  "
            f"{_val(s.get('played')):>3}  "
            f"{_val(s.get('won')):>3}  "
            f"{_val(s.get('drawn')):>3}  "
            f"{_val(s.get('lost')):>3}  "
            f"{gd_str:>4}  "
            f"{form_str}"
        )
    return "\n".join(lines)


# ── Analysis sections ────────────────────────────────────────────────────────

def _tactical_summary(data: dict) -> str:
    teams = data["teams"]
    lineups = data.get("lineups", {})
    hs = data["statistics"]["home"]
    as_ = data["statistics"]["away"]
    hn = teams["home"]["name"]
    an = teams["away"]["name"]

    lines = ["", "── TACTICAL SUMMARY " + "─" * 33]

    home_form = lineups.get("home", {}) or {}
    away_form = lineups.get("away", {}) or {}
    hf = home_form.get("formation", "?")
    af = away_form.get("formation", "?")

    lines.append(f"  {hn} set up in a {hf}, {an} in a {af}.")

    h_poss_raw = hs.get("possession")
    a_poss_raw = as_.get("possession")
    try:
        h_poss = int(str(h_poss_raw).replace("%", ""))
        a_poss = int(str(a_poss_raw).replace("%", ""))
        dominant = hn if h_poss >= a_poss else an
        other = an if h_poss >= a_poss else hn
        poss_diff = abs(h_poss - a_poss)
        if poss_diff >= 15:
            lines.append(f"  {dominant} dominated possession ({max(h_poss, a_poss)}% vs {min(h_poss, a_poss)}%), "
                         f"dictating the tempo and pinning {other} deep.")
        elif poss_diff >= 5:
            lines.append(f"  {dominant} held the slight possession edge ({max(h_poss, a_poss)}% vs {min(h_poss, a_poss)}%), "
                         f"though {other} pressed effectively on the counter.")
        else:
            lines.append(f"  Possession was closely contested ({h_poss}% vs {a_poss}%) — a tactical battle for midfield control.")
    except Exception:
        pass

    h_shots = hs.get("shots_total") or 0
    a_shots = as_.get("shots_total") or 0
    h_sot = hs.get("shots_on_target") or 0
    a_sot = as_.get("shots_on_target") or 0

    if h_shots and a_shots:
        attack_edge = hn if h_shots > a_shots else an
        lines.append(f"  {attack_edge} generated more shots ({max(h_shots, a_shots)} vs {min(h_shots, a_shots)}), "
                     f"with on-target accuracy of {round(h_sot/h_shots*100) if h_shots else 0}% "
                     f"vs {round(a_sot/a_shots*100) if a_shots else 0}%.")

    h_fouls = hs.get("fouls") or 0
    a_fouls = as_.get("fouls") or 0
    if h_fouls + a_fouls > 0:
        physical = hn if h_fouls > a_fouls else an
        if abs(h_fouls - a_fouls) >= 4:
            lines.append(f"  {physical} were the more physical side, committing {max(h_fouls, a_fouls)} fouls.")

    h_passes = hs.get("passes_total") or 0
    a_passes = as_.get("passes_total") or 0
    if h_passes and a_passes:
        pass_team = hn if h_passes > a_passes else an
        lines.append(f"  {pass_team} completed more passes ({max(h_passes, a_passes)} vs {min(h_passes, a_passes)}), "
                     f"maintaining structure in build-up play.")

    return "\n".join(lines)


def _momentum_block(data: dict) -> str:
    events = data.get("events", [])
    teams = data["teams"]
    hn = teams["home"]["name"]
    an = teams["away"]["name"]
    hs = data["statistics"]["home"]
    as_ = data["statistics"]["away"]

    lines = ["", "── MOMENTUM " + "─" * 41]

    goals = [e for e in events if e.get("type") == "Goal"]
    cards = [e for e in events if e.get("type") == "Card"]

    if not goals:
        lines.append("  No goals scored — the match was goalless for both sides.")
    else:
        first_goal = goals[0]
        first_team = first_goal.get("team", "?")
        first_min = first_goal.get("minute", "?")
        lines.append(f"  {first_team} drew first blood in the {first_min}' — "
                     f"establishing early psychological dominance.")

        if len(goals) > 1:
            h_goals = sum(1 for g in goals if g.get("team") == hn)
            a_goals = sum(1 for g in goals if g.get("team") == an)
            lines.append(f"  {hn} scored {h_goals} goal{'s' if h_goals != 1 else ''}; "
                         f"{an} scored {a_goals} goal{'s' if a_goals != 1 else ''}.")

        late_goals = [g for g in goals if g.get("minute") and g["minute"] >= 75]
        if late_goals:
            lines.append(f"  {len(late_goals)} late goal{'s' if len(late_goals) > 1 else ''} in the final 15 minutes "
                         f"shaped the result — both sides pressed hard to the final whistle.")

    red_cards = [c for c in cards if c.get("detail") in ("Red Card", "Yellow Red Card")]
    if red_cards:
        for rc in red_cards:
            lines.append(f"  🟥 {rc.get('player')} ({rc.get('team')}) received a red card in the "
                         f"{rc.get('minute', '?')}' — a potential turning point.")

    try:
        h_xg = float(str(hs.get("xg") or 0))
        a_xg = float(str(as_.get("xg") or 0))
        h_actual = data["score"]["current"]["home"] or 0
        a_actual = data["score"]["current"]["away"] or 0
        if abs(h_xg - h_actual) > 0.8:
            side = hn
            direction = "over" if h_actual > h_xg else "under"
            lines.append(f"  {side} {direction}performed their xG ({h_xg:.2f} xG, {h_actual} actual goals).")
        if abs(a_xg - a_actual) > 0.8:
            side = an
            direction = "over" if a_actual > a_xg else "under"
            lines.append(f"  {side} {direction}performed their xG ({a_xg:.2f} xG, {a_actual} actual goals).")
    except Exception:
        pass

    return "\n".join(lines)


def _betting_block(data: dict) -> str:
    sc = data["score"]
    events = data.get("events", [])
    hs = data["statistics"]["home"]
    as_ = data["statistics"]["away"]
    teams = data["teams"]

    h_goals = sc["current"]["home"] or 0
    a_goals = sc["current"]["away"] or 0
    total_goals = h_goals + a_goals

    btts = h_goals > 0 and a_goals > 0
    over_25 = total_goals > 2
    over_35 = total_goals > 3
    h_clean = a_goals == 0
    a_clean = h_goals == 0

    goals = [e for e in events if e.get("type") == "Goal"]
    h_corners = hs.get("corners") or 0
    a_corners = as_.get("corners") or 0
    total_corners = h_corners + a_corners
    h_cards = (hs.get("yellow_cards") or 0) + (hs.get("red_cards") or 0)
    a_cards = (as_.get("yellow_cards") or 0) + (as_.get("red_cards") or 0)
    total_cards = h_cards + a_cards

    try:
        h_xg = float(str(hs.get("xg") or 0))
        a_xg = float(str(as_.get("xg") or 0))
        xg_str = f"Combined xG: {h_xg + a_xg:.2f}"
    except Exception:
        xg_str = None

    lines = ["", "── BETTING INSIGHTS " + "─" * 33]

    def tick(val: bool) -> str:
        return "✅" if val else "❌"

    lines += [
        f"  {tick(btts)}  Both Teams to Score (BTTS): {'Yes' if btts else 'No'}",
        f"  {tick(over_25)}  Over 2.5 Goals: {'Yes' if over_25 else 'No'}  ({total_goals} goals scored)",
        f"  {tick(over_35)}  Over 3.5 Goals: {'Yes' if over_35 else 'No'}",
        f"  {tick(h_clean)}  {teams['home']['name']} Clean Sheet: {'Yes' if h_clean else 'No'}",
        f"  {tick(a_clean)}  {teams['away']['name']} Clean Sheet: {'Yes' if a_clean else 'No'}",
    ]

    if total_corners > 0:
        lines.append(f"  {'✅' if total_corners >= 10 else '❌'}  Over 9.5 Corners: "
                     f"{'Yes' if total_corners >= 10 else 'No'}  ({total_corners} total)")

    if total_cards > 0:
        lines.append(f"  {'✅' if total_cards >= 4 else '❌'}  Over 3.5 Cards: "
                     f"{'Yes' if total_cards >= 4 else 'No'}  ({total_cards} total)")

    if xg_str:
        lines.append(f"  📊  {xg_str}")

    if goals:
        first_scorer = goals[0]
        lines.append(f"  ⚽  First Goalscorer: {first_scorer.get('player', '?')} "
                     f"({first_scorer.get('team', '?')}, {first_scorer.get('minute', '?')}')")
    if len(goals) > 1:
        last_scorer = goals[-1]
        lines.append(f"  ⚽  Last Goalscorer: {last_scorer.get('player', '?')} "
                     f"({last_scorer.get('team', '?')}, {last_scorer.get('minute', '?')}')")

    return "\n".join(lines)


# ── Main endpoint ────────────────────────────────────────────────────────────

@router.get("/report", response_class=PlainTextResponse)
async def match_report(
    home: str = Query(..., description="Home team name (full or partial)"),
    away: str = Query(..., description="Away team name (full or partial)"),
):
    """
    Return a human-readable match report for the given home/away teams.
    Internally calls /aurora/analyze and formats all data as plain text.

    Sections: Match header, Score, Statistics, Cards, Events, Lineups,
    Standings, Tactical summary, Momentum, Betting insights.
    """
    data = await analyze_fixture(home=home, away=away)

    sections = [
        _header(data),
        _score_block(data),
        _stats_block(data),
        _cards_block(data),
        _events_block(data),
        _lineups_block(data),
        _standings_block(data),
        _tactical_summary(data),
        _momentum_block(data),
        _betting_block(data),
        "\n" + "═" * 54,
        f"  Generated by Aurora · API-Football",
        "═" * 54,
    ]

    return "\n".join(sections)
