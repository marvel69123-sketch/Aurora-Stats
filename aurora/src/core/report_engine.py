"""
Report Engine — human-readable text report assembly.

Generates the full plain-text match report used by GET /aurora/report.
Also produces a structured summary string used by GET /aurora/score.

All section builders were moved here from src/routers/report.py, which
is now a thin HTTP wrapper that calls this engine.

Public API
----------
  build_text(data, hn, an, decision) -> str   (full text report)
  build_summary(hn, an, methodology, market_result) -> str
"""
from __future__ import annotations

from src.core.market_engine import MarketResult
from src.core.methodology_engine import MethodologyResult


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _pct(val) -> str:
    if val is None:
        return "N/A"
    return str(val) if "%" in str(val) else f"{val}%"


def _val(val, default: str = "N/A") -> str:
    return str(val) if val is not None else default


def _bar(home_raw, away_raw, width: int = 20) -> str:
    try:
        h = int(str(home_raw).replace("%", ""))
        a = int(str(away_raw).replace("%", ""))
        total = h + a or 100
        hb = round(h / total * width)
        return f"[{'█' * hb}{'░' * (width - hb)}]"
    except Exception:
        return ""


def _form_display(form: str | None) -> str:
    if not form:
        return "N/A"
    icons = {"W": "✅", "D": "➖", "L": "❌"}
    return " ".join(icons.get(c, c) for c in form[-5:])


def _event_icon(event: dict) -> str:
    t = event.get("type", "")
    if t == "Goal":
        return "⚽"
    if t == "Card":
        return {"Yellow Card": "🟨", "Red Card": "🟥", "Yellow Red Card": "🟥"}.get(
            event.get("detail", ""), "🃏"
        )
    if t == "subst":
        return "🔄"
    if t == "Var":
        return "📺"
    return "•"


# ---------------------------------------------------------------------------
# Section builders (each returns a multi-line string)
# ---------------------------------------------------------------------------


def _header(data: dict) -> str:
    fx    = data["fixture"]
    lg    = data["league"]
    teams = data["teams"]
    venue = fx["venue"]
    venue_str = ", ".join(filter(None, [venue.get("name"), venue.get("city")]))
    lines = [
        "╔══════════════════════════════════════════════════════╗",
        "  MATCH REPORT",
        f"  {teams['home']['name']}  vs  {teams['away']['name']}",
        f"  {lg['name']} {lg.get('season', '')}  ·  {lg.get('round', '')}",
    ]
    if venue_str:
        lines.append(f"  {venue_str}")
    if fx.get("referee"):
        lines.append(f"  Referee: {fx['referee']}")
    lines.append("╚══════════════════════════════════════════════════════╝")
    return "\n".join(lines)


def _score_block(data: dict) -> str:
    fx    = data["fixture"]
    sc    = data["score"]
    teams = data["teams"]
    status = fx["status"]
    minute_str = f"  {status['minute']}'" if status.get("minute") else ""
    cur = sc["current"]
    lines = [
        "",
        "── RESULT " + "─" * 45,
        f"  {teams['home']['name']}  {_val(cur['home'], '0')}  –  {_val(cur['away'], '0')}  {teams['away']['name']}",
        f"  Status: {status['long']}{minute_str}",
    ]
    for period, label in [("halftime", "Half-time"), ("fulltime", "Full-time"),
                          ("extratime", "Extra time"), ("penalty", "Penalties")]:
        p = sc.get(period, {})
        if p.get("home") is not None:
            lines.append(f"  {label}: {_val(p['home'], '0')} – {_val(p['away'], '0')}")
    return "\n".join(lines)


def _stats_block(data: dict) -> str:
    teams = data["teams"]
    hs = data["statistics"]["home"]
    as_ = data["statistics"]["away"]
    hn = teams["home"]["name"]
    an = teams["away"]["name"]

    col_w   = max(len(hn), len(an), 22) + 2
    h_col   = hn.center(col_w)
    a_col   = an.center(col_w)
    label_w = 20

    def row(label, hv, av):
        return f"  {label:<{label_w}}{_val(hv).center(col_w)}{_val(av).center(col_w)}"

    h_poss = hs.get("possession")
    a_poss = as_.get("possession")
    return "\n".join([
        "", "── STATISTICS " + "─" * 40,
        f"  {'':20}{h_col}{a_col}",
        "  " + "─" * (label_w + col_w * 2),
        row("Possession", _pct(h_poss), _pct(a_poss)),
        f"  {'':20}  {_bar(h_poss, a_poss)}",
        row("Shots (total)",    hs.get("shots_total"),    as_.get("shots_total")),
        row("Shots on target",  hs.get("shots_on_target"), as_.get("shots_on_target")),
        row("Shots off target", hs.get("shots_off_target"), as_.get("shots_off_target")),
        row("Blocked shots",    hs.get("blocked_shots"),  as_.get("blocked_shots")),
        row("Corners",          hs.get("corners"),         as_.get("corners")),
        row("Fouls",            hs.get("fouls"),           as_.get("fouls")),
        row("Offsides",         hs.get("offsides"),        as_.get("offsides")),
        row("Saves",            hs.get("saves"),           as_.get("saves")),
        row("Passes (total)",   hs.get("passes_total"),   as_.get("passes_total")),
        row("Pass accuracy",    _pct(hs.get("pass_accuracy")), _pct(as_.get("pass_accuracy"))),
        row("xG",               _val(hs.get("xg")),       _val(as_.get("xg"))),
    ])


def _cards_block(data: dict) -> str:
    teams = data["teams"]
    hs  = data["statistics"]["home"]
    as_ = data["statistics"]["away"]
    hn  = teams["home"]["name"]
    an  = teams["away"]["name"]

    def card_str(stats):
        y = _val(stats.get("yellow_cards"), "0")
        r = _val(stats.get("red_cards"), "0")
        parts = []
        try:
            if int(y) > 0: parts.append(f"🟨 {y} yellow")
            if int(r) > 0: parts.append(f"🟥 {r} red")
        except Exception:
            pass
        return ", ".join(parts) if parts else "none"

    return "\n".join([
        "", "── CARDS " + "─" * 44,
        f"  {hn}: {card_str(hs)}",
        f"  {an}: {card_str(as_)}",
    ])


def _events_block(data: dict, max_events: int = 20) -> str:
    events = data.get("events", [])
    if not events:
        return "\n── MATCH EVENTS " + "─" * 37 + "\n  No events recorded."
    lines = ["", "── MATCH EVENTS " + "─" * 37]
    for i, e in enumerate(events):
        if i >= max_events:
            lines.append(f"  … +{len(events) - i} more events")
            break
        minute = str(e.get("minute", "?"))
        if e.get("extra_minute"):
            minute += f"+{e['extra_minute']}"
        assist = e.get("assist")
        assist_str = f" (assist: {assist})" if assist else ""
        lines.append(
            f"  {minute:>5}'  {_event_icon(e)}  "
            f"{e.get('detail') or e.get('type') or ''}  "
            f"– {e.get('player') or ''}{assist_str}  [{e.get('team') or ''}]"
        )
    return "\n".join(lines)


def _lineups_block(data: dict) -> str:
    lineups = data.get("lineups", {})
    teams   = data["teams"]
    lines   = ["", "── LINEUPS " + "─" * 42]
    for side in ("home", "away"):
        lu   = lineups.get(side)
        name = teams[side]["name"]
        if not lu:
            lines.append(f"\n  {name}: lineup not available")
            continue
        coach = (lu.get("coach") or {}).get("name") or "Unknown"
        lines.append(f"\n  {name}  ({lu.get('formation', '?')})  ·  Coach: {coach}")
        xi = lu.get("starting_xi") or []
        if xi:
            lines.append("  Starting XI:")
            for p in xi:
                lines.append(f"    {p.get('number', '?'):>2}. [{p.get('position', '?')}]  {p.get('name', '?')}")
        subs = lu.get("substitutes") or []
        if subs:
            names = ", ".join(p.get("name", "?") for p in subs[:5])
            if len(subs) > 5:
                names += f" (+{len(subs)-5})"
            lines.append(f"  Bench: {names}")
    return "\n".join(lines)


def _standings_block(data: dict) -> str:
    lg  = data["league"]
    std = data.get("standings", {})
    if not std.get("home") and not std.get("away"):
        return ""
    lines = ["", f"── STANDINGS  ({lg['name']} {lg.get('season', '')}) " + "─" * 20]
    lines.append(f"  {'#':>3}  {'Team':<26}  {'Pts':>4}  {'P':>3}  {'W':>3}  {'D':>3}  {'L':>3}  {'GD':>4}  Form")
    lines.append("  " + "─" * 68)
    teams = data["teams"]
    for side in ("home", "away"):
        s = std.get(side)
        if not s:
            continue
        gd  = s.get("goal_difference")
        gd_str = (f"+{gd}" if gd is not None and gd > 0 else str(gd) if gd is not None else "N/A")
        lines.append(
            f"  {_val(s.get('rank')):>3}  {teams[side]['name']:<26}  "
            f"{_val(s.get('points')):>4}  {_val(s.get('played')):>3}  "
            f"{_val(s.get('won')):>3}  {_val(s.get('drawn')):>3}  "
            f"{_val(s.get('lost')):>3}  {gd_str:>4}  {_form_display(s.get('form'))}"
        )
    return "\n".join(lines)


def _tactical_summary(data: dict) -> str:
    teams   = data["teams"]
    lineups = data.get("lineups", {})
    hs = data["statistics"]["home"]
    as_ = data["statistics"]["away"]
    hn = teams["home"]["name"]
    an = teams["away"]["name"]
    lines = ["", "── TACTICAL SUMMARY " + "─" * 33]
    hf = (lineups.get("home") or {}).get("formation", "?")
    af = (lineups.get("away") or {}).get("formation", "?")
    lines.append(f"  {hn} set up in a {hf}, {an} in a {af}.")
    try:
        hp = int(str(hs.get("possession") or 0).replace("%", ""))
        ap = int(str(as_.get("possession") or 0).replace("%", ""))
        dominant = hn if hp >= ap else an
        other    = an if hp >= ap else hn
        diff = abs(hp - ap)
        if diff >= 15:
            lines.append(f"  {dominant} dominated possession ({max(hp, ap)}% vs {min(hp, ap)}%), pinning {other} deep.")
        elif diff >= 5:
            lines.append(f"  {dominant} held a slight possession edge ({max(hp, ap)}% vs {min(hp, ap)}%).")
        else:
            lines.append(f"  Possession was closely contested ({hp}% vs {ap}%).")
    except Exception:
        pass
    hs_t = hs.get("shots_total") or 0
    as_t = as_.get("shots_total") or 0
    hs_o = hs.get("shots_on_target") or 0
    as_o = as_.get("shots_on_target") or 0
    if hs_t and as_t:
        edge = hn if hs_t > as_t else an
        lines.append(
            f"  {edge} generated more shots ({max(hs_t, as_t)} vs {min(hs_t, as_t)}), "
            f"on-target: {round(hs_o/hs_t*100) if hs_t else 0}% vs {round(as_o/as_t*100) if as_t else 0}%."
        )
    hf_c = hs.get("fouls") or 0
    af_c = as_.get("fouls") or 0
    if hf_c + af_c > 0 and abs(hf_c - af_c) >= 4:
        physical = hn if hf_c > af_c else an
        lines.append(f"  {physical} were the more physical side, committing {max(hf_c, af_c)} fouls.")
    hp_c = hs.get("passes_total") or 0
    ap_c = as_.get("passes_total") or 0
    if hp_c and ap_c:
        pass_team = hn if hp_c > ap_c else an
        lines.append(f"  {pass_team} completed more passes ({max(hp_c, ap_c)} vs {min(hp_c, ap_c)}).")
    return "\n".join(lines)


def _momentum_block(data: dict) -> str:
    events = data.get("events", [])
    teams  = data["teams"]
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
        first = goals[0]
        lines.append(f"  {first.get('team', '?')} drew first blood in the {first.get('minute', '?')}' — early psychological edge.")
        if len(goals) > 1:
            hg = sum(1 for g in goals if g.get("team") == hn)
            ag = sum(1 for g in goals if g.get("team") == an)
            lines.append(f"  {hn} scored {hg} goal{'s' if hg != 1 else ''}; {an} scored {ag} goal{'s' if ag != 1 else ''}.")
        late = [g for g in goals if g.get("minute") and g["minute"] >= 75]
        if late:
            lines.append(f"  {len(late)} late goal{'s' if len(late) > 1 else ''} in the final 15 minutes shaped the result.")
    reds = [c for c in cards if c.get("detail") in ("Red Card", "Yellow Red Card")]
    for rc in reds:
        lines.append(f"  🟥 {rc.get('player')} ({rc.get('team')}) red card in the {rc.get('minute', '?')}'.")
    try:
        h_xg = float(str(hs.get("xg") or 0))
        a_xg = float(str(as_.get("xg") or 0))
        h_act = data["score"]["current"]["home"] or 0
        a_act = data["score"]["current"]["away"] or 0
        if abs(h_xg - h_act) > 0.8:
            lines.append(f"  {hn} {'over' if h_act > h_xg else 'under'}performed xG ({h_xg:.2f} xG, {h_act} goals).")
        if abs(a_xg - a_act) > 0.8:
            lines.append(f"  {an} {'over' if a_act > a_xg else 'under'}performed xG ({a_xg:.2f} xG, {a_act} goals).")
    except Exception:
        pass
    return "\n".join(lines)


def _betting_block(data: dict, market_result: MarketResult) -> str:
    sc     = data["score"]
    events = data.get("events", [])
    hs  = data["statistics"]["home"]
    as_ = data["statistics"]["away"]
    teams = data["teams"]
    h_goals = sc["current"]["home"] or 0
    a_goals = sc["current"]["away"] or 0
    total   = h_goals + a_goals
    h_cor = hs.get("corners") or 0
    a_cor = as_.get("corners") or 0
    tc    = h_cor + a_cor
    h_cards = (hs.get("yellow_cards") or 0) + (hs.get("red_cards") or 0)
    a_cards = (as_.get("yellow_cards") or 0) + (as_.get("red_cards") or 0)
    tk      = h_cards + a_cards

    def tick(v): return "✅" if v else "❌"

    btts   = h_goals > 0 and a_goals > 0
    o25    = total > 2
    o35    = total > 3
    h_cs   = a_goals == 0
    a_cs   = h_goals == 0
    lines = ["", "── BETTING INSIGHTS " + "─" * 33,
        f"  {tick(btts)}  BTTS: {'Yes' if btts else 'No'}",
        f"  {tick(o25)}   Over 2.5 Goals: {'Yes' if o25 else 'No'}  ({total} goals)",
        f"  {tick(o35)}   Over 3.5 Goals: {'Yes' if o35 else 'No'}",
        f"  {tick(h_cs)}  {teams['home']['name']} Clean Sheet: {'Yes' if h_cs else 'No'}",
        f"  {tick(a_cs)}  {teams['away']['name']} Clean Sheet: {'Yes' if a_cs else 'No'}",
    ]
    if tc > 0:
        lines.append(f"  {tick(tc >= 10)}  Over 9.5 Corners: {'Yes' if tc >= 10 else 'No'}  ({tc} total)")
    if tk > 0:
        lines.append(f"  {tick(tk >= 4)}  Over 3.5 Cards: {'Yes' if tk >= 4 else 'No'}  ({tk} total)")
    try:
        xg_total = float(str(hs.get("xg") or 0)) + float(str(as_.get("xg") or 0))
        lines.append(f"  📊  Combined xG: {xg_total:.2f}")
    except Exception:
        pass
    goals_ev = [e for e in events if e.get("type") == "Goal"]
    if goals_ev:
        f_g = goals_ev[0]
        lines.append(f"  ⚽  First Goalscorer: {f_g.get('player','?')} ({f_g.get('team','?')}, {f_g.get('minute','?')}')")
    if len(goals_ev) > 1:
        l_g = goals_ev[-1]
        lines.append(f"  ⚽  Last Goalscorer:  {l_g.get('player','?')} ({l_g.get('team','?')}, {l_g.get('minute','?')}')")

    # Aurora's top recommendation ───────────────────────────────────────────
    if market_result.recommended:
        best = market_result.recommended[0]
        lines += [
            "",
            f"  ⭐  Aurora's top pick: {best.label} ({best.probability:.0f}%,  confidence {best.confidence:.1f}/10, risk {best.risk})",
        ]
    elif market_result.best:
        b = market_result.best
        lines += [
            "",
            f"  ℹ️   Best market: {b.label} ({b.probability:.0f}%) — High risk, not recommended for action.",
        ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_summary(
    hn: str,
    an: str,
    methodology: MethodologyResult,
    market_result: MarketResult,
) -> str:
    """One-line summary string embedded in the /score response."""
    m    = methodology
    best = market_result.best
    score_str = f"{m.h_goals}–{m.a_goals}" if m.has_score else "upcoming"
    risk_str  = best.risk
    return (
        f"{hn} vs {an} [{score_str}] · "
        f"Confidence {round(best.confidence, 1)}/10 · "
        f"Best market: {best.label} ({best.probability:.0f}%) · "
        f"Risk: {risk_str}."
    )


def build_text(data: dict, hn: str, an: str, market_result: MarketResult) -> str:
    """Full plain-text match report for the /report endpoint."""
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
        _betting_block(data, market_result),
        "\n" + "═" * 54,
        "  Generated by Aurora · AURORA_BRAIN v1.0",
        "═" * 54,
    ]
    return "\n".join(s for s in sections if s)
