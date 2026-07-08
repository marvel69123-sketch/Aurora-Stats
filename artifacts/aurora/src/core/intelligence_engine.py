"""
Aurora Intelligence Engine — professional analyst reasoning pipeline.

Transforms raw engine outputs into structured, natural-language analysis
that reads like a professional sports analyst wrote it.

11 sections produced:
  executive_summary        — 3-4 sentence overview of the opportunity
  main_factors             — top 5 factors that drove the recommendation
  positive_factors         — signals that support the bet
  negative_factors         — signals that argue against it
  risk_factors             — specific risks to be aware of
  recommended_stake        — quarter-Kelly stake with full reasoning
  alternative_markets      — next-best options with explanations
  confidence_explanation   — why the confidence score is what it is
  invalidation_conditions  — what would make this analysis wrong
  learning_references      — how Aurora's track record informs this call
  historical_matches       — similar past fixtures from memory

Public API
----------
  generate(hn, an, league, data, mv1, dc, meth, knowledge,
           learning_stats, mem_ctx) -> IntelligenceReport
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class IntelligenceReport:
    fixture_id:         int
    match:              str
    date:               str
    status:             str
    minute:             int | None
    is_live:            bool

    primary_recommendation: str
    overall_confidence: float
    risk_level:         str

    # ── 11 natural-language sections ────────────────────────────────────────
    executive_summary:       str
    main_factors:            list[str]
    positive_factors:        list[str]
    negative_factors:        list[str]
    risk_factors:            list[str]
    recommended_stake:       str
    alternative_markets:     list[str]
    confidence_explanation:  str
    invalidation_conditions: list[str]
    learning_references:     list[str]
    historical_matches:      list[str]

    knowledge_notes:    list[str]
    generated_at:       str
    aurora_version:     str = "Intelligence Engine v1.0"


# ---------------------------------------------------------------------------
# Vocabulary helpers — choose context-aware adjectives / phrases
# ---------------------------------------------------------------------------

_CATEGORY_LABELS: dict[str, str] = {
    "match_context":       "Match Context",
    "team_strength":       "Team Strength",
    "current_form":        "Current Form",
    "motivation":          "Motivation & Stakes",
    "home_advantage":      "Home Advantage",
    "away_performance":    "Away Performance",
    "xg_analysis":         "Expected Goals Analysis",
    "live_momentum":       "Live Momentum",
    "referee_tendency":    "Referee Tendency",
    "tactical_patterns":   "Tactical Patterns",
    "player_availability": "Player Availability",
    "historical_h2h":      "Head-to-Head Record",
    "weather_impact":      "Weather Impact",
    "bankroll_risk":       "Portfolio Risk",
    "learning_calibration":"Learning Calibration",
}

_MARKET_LABELS: dict[str, str] = {
    "home_win": "Home Win",
    "draw": "Draw",
    "away_win": "Away Win",
    "btts_yes": "Both Teams To Score — Yes",
    "btts_no": "Both Teams To Score — No",
    "dnb_home": "Draw No Bet — Home",
    "dnb_away": "Draw No Bet — Away",
    "dc_1x": "Double Chance 1X",
    "dc_x2": "Double Chance X2",
    "dc_12": "Double Chance 12",
    "ah_home": "Asian Handicap — Home −0.5",
    "ah_away": "Asian Handicap — Away +0.5",
    "over_15_goals": "Over 1.5 Goals",
    "over_25_goals": "Over 2.5 Goals",
    "over_35_goals": "Over 3.5 Goals",
    "over_45_goals": "Over 4.5 Goals",
    "under_25_goals": "Under 2.5 Goals",
    "over_85_corners": "Over 8.5 Corners",
    "over_95_corners": "Over 9.5 Corners",
    "over_35_cards": "Over 3.5 Cards",
    "over_45_cards": "Over 4.5 Cards",
    "player_to_score": "Anytime Goalscorer",
    "player_assist": "Anytime Assist",
}


def _label(market_id: str) -> str:
    return _MARKET_LABELS.get(market_id, market_id.replace("_", " ").title())


def _confidence_adjective(c: float) -> str:
    if c >= 8.5: return "exceptional"
    if c >= 7.5: return "strong"
    if c >= 6.5: return "solid"
    if c >= 5.5: return "moderate"
    if c >= 4.5: return "limited"
    return "low"


def _ev_phrase(ev: float) -> str:
    if ev >= 15: return f"a substantial +{ev:.1f}% edge over the bookmaker"
    if ev >= 10: return f"a healthy +{ev:.1f}% expected value"
    if ev >= 5:  return f"a positive +{ev:.1f}% edge"
    if ev >= 0:  return f"a marginal +{ev:.1f}% edge"
    return f"a negative EV of {ev:.1f}% (below threshold)"


def _risk_phrase(risk: str) -> str:
    return {"Low": "well-controlled risk profile", "Medium": "moderate risk level",
            "High": "elevated risk"}.get(risk, risk.lower())


def _score_label(score: float) -> str:
    if score >= 8.5: return "excellent"
    if score >= 7.0: return "strong"
    if score >= 5.5: return "adequate"
    if score >= 4.0: return "weak"
    return "very weak"


def _probability_phrase(p: float) -> str:
    if p >= 75: return f"a high {p:.0f}% probability"
    if p >= 60: return f"a solid {p:.0f}% probability"
    if p >= 50: return f"a marginal {p:.0f}% probability"
    return f"a {p:.0f}% probability"


# ---------------------------------------------------------------------------
# Section generators
# ---------------------------------------------------------------------------


def _exec_summary(
    hn: str, an: str, league: str | None,
    best_market_name: str, probability: float, ev: float,
    overall_conf: float, mv1_score: float, risk: str,
    is_live: bool, minute: int | None, h_score: int, a_score: int,
    has_xg: bool, has_standings: bool, dc_actionable: int,
    mv1_passed: bool,
) -> str:
    league_str = f" ({league})" if league else ""
    conf_adj = _confidence_adjective(overall_conf)
    ev_phrase = _ev_phrase(ev)

    # Opening line — live or pre-match
    if is_live and minute:
        score_str = f"{h_score}–{a_score}"
        opening = (
            f"{hn} vs {an}{league_str} is currently live in minute {minute}, "
            f"with the score at {score_str}."
        )
    else:
        opening = f"{hn} vs {an}{league_str} is the subject of Aurora's pre-match analysis."

    # Recommendation sentence
    if mv1_passed and dc_actionable > 0:
        rec = (
            f"Aurora's {conf_adj}-confidence assessment ({overall_conf:.1f}/10) identifies "
            f"**{best_market_name}** as the primary opportunity, carrying "
            f"{_probability_phrase(probability)} and {ev_phrase}."
        )
    else:
        rec = (
            f"Aurora's methodology score of {mv1_score:.1f}/10 does not clear the minimum "
            f"threshold for a confident recommendation at this time — exercise caution before "
            f"acting on any market in this fixture."
        )

    # Data quality sentence
    sources = []
    if has_xg:      sources.append("live expected-goals (xG) data")
    if has_standings: sources.append("season standings")
    if is_live:     sources.append("live match events")
    if sources:
        data_str = f"The assessment integrates {', '.join(sources)}, " \
                   f"processed through Aurora's three-layer Poisson model."
    else:
        data_str = (
            "The assessment relies on season-average goal rates "
            "(xG data is unavailable, increasing uncertainty across all goal markets)."
        )

    # Verdict
    if dc_actionable >= 4:
        verdict = (
            f"A total of {dc_actionable} markets pass Aurora's full methodology gate, "
            f"offering good breadth of opportunity with a {_risk_phrase(risk)}."
        )
    elif dc_actionable >= 2:
        verdict = (
            f"{dc_actionable} markets clear Aurora's gates. "
            f"The risk profile is {_risk_phrase(risk)} — size stakes accordingly."
        )
    elif dc_actionable == 1:
        verdict = (
            "This is a selective, single-market opportunity. "
            f"Only one market clears Aurora's full filter at a {_risk_phrase(risk)}."
        )
    else:
        verdict = (
            "No markets currently pass Aurora's full methodology filter. "
            "The analysis below explains the key blockers and what would need to change."
        )

    return " ".join([opening, rec, data_str, verdict])


def _main_factors(categories: dict, mv1_score: float) -> list[str]:
    """Top 5 categories by weighted contribution."""
    ranked = sorted(
        categories.items(),
        key=lambda kv: -kv[1].contribution,
    )[:7]

    lines = []
    for i, (key, cs) in enumerate(ranked, 1):
        label = _CATEGORY_LABELS.get(key, key.replace("_", " ").title())
        score_lbl = _score_label(cs.score)
        lines.append(
            f"{i}. **{label}** — {score_lbl} score of {cs.score:.1f}/10 "
            f"(weighted contribution {cs.contribution:.2f}). {cs.reason}"
        )
    return lines


def _positive_factors(hn: str, an: str, categories: dict) -> list[str]:
    """Categories scoring ≥ 7.0 — signals that support the recommendation."""
    positives = [
        (k, v) for k, v in categories.items() if v.score >= 7.0
    ]
    positives.sort(key=lambda kv: -kv[1].score)

    lines = []
    for key, cs in positives:
        label = _CATEGORY_LABELS.get(key, key.replace("_", " ").title())
        lines.append(
            f"• **{label}** ({cs.score:.1f}/10): {cs.reason}"
        )
    if not lines:
        lines.append(
            f"• No category scores above 7.0 in this fixture — "
            f"the overall opportunity is marginal across all dimensions."
        )
    return lines


def _negative_factors(categories: dict) -> list[str]:
    """Categories scoring < 5.5 — signals that argue against the bet."""
    negatives = [
        (k, v) for k, v in categories.items() if v.score < 5.5
    ]
    negatives.sort(key=lambda kv: kv[1].score)

    lines = []
    for key, cs in negatives:
        label = _CATEGORY_LABELS.get(key, key.replace("_", " ").title())
        lines.append(
            f"• **{label}** ({cs.score:.1f}/10): {cs.reason} "
            f"— this category is dragging the overall score down."
        )
    if not lines:
        lines.append(
            "• All methodology categories score above 5.5 — "
            "there are no significant negative signals in this fixture."
        )
    return lines


def _risk_factors(
    knowledge: Any,
    categories: dict,
    has_xg: bool, has_standings: bool, has_referee: bool,
    is_live: bool, minute: int | None, risk: str,
    mv1_score: float,
) -> list[str]:
    """Specific risks — from knowledge red flags, low categories, and model limits."""
    lines: list[str] = []

    # Knowledge red flags triggered
    for flag in knowledge.red_flags_triggered:
        lines.append(f"⚠ {flag}")

    # Very low-scoring categories (< 4.0) are serious concerns
    critical = [(k, v) for k, v in categories.items() if v.score < 4.0]
    for key, cs in sorted(critical, key=lambda kv: kv[1].score):
        label = _CATEGORY_LABELS.get(key, key.replace("_", " ").title())
        lines.append(
            f"⚠ **{label}** scores only {cs.score:.1f}/10 — "
            f"this is a critical weakness in the current analysis: {cs.reason}"
        )

    # Data gaps
    if not has_xg:
        lines.append(
            "⚠ **No xG data** — goal market probabilities are based on season-average "
            "goals per game rather than shot quality. All goal and BTTS estimates carry "
            "an additional 15–20% margin of uncertainty."
        )
    if not has_standings:
        lines.append(
            "⚠ **No standings data** — team strength cannot be calibrated against "
            "their league position. Aurora falls back to default league priors."
        )
    if not has_referee:
        lines.append(
            "⚠ **Referee unassigned** — card and penalty markets cannot be calibrated "
            "to a specific official. Card market confidence is reduced."
        )

    # Live-specific timing risk
    if is_live and minute and minute < 30:
        lines.append(
            f"⚠ **Early live data (minute {minute})** — fewer than 30 minutes played "
            f"means statistical signals are still volatile. "
            f"Wait until minute 30+ for higher reliability."
        )

    # Overall methodology score risk
    if mv1_score < 5.5:
        lines.append(
            f"⚠ **Methodology score {mv1_score:.1f}/10 is below the recommended threshold of 5.5.** "
            f"Aurora's gate is set to block recommendations below this level. "
            f"Any bet in this fixture carries above-average model uncertainty."
        )
    elif risk == "High":
        lines.append(
            "⚠ **Risk Level: High** — even with a passing methodology score, "
            "the market risk level is elevated. Use smaller-than-normal stake sizes."
        )

    if not lines:
        lines.append(
            "• No critical risk flags identified. Standard model uncertainty applies to all predictions "
            "(football outcomes are inherently probabilistic — even 80% probability bets lose 20% of the time)."
        )
    return lines


def _stake_pct(ev: float, confidence: float, risk: str) -> float:
    """Quarter-Kelly inspired stake sizing (% of bankroll)."""
    if ev <= 0:
        return 0.0

    # Base by confidence (0–10 scale)
    if confidence >= 8.5:   base = 3.5
    elif confidence >= 7.5: base = 3.0
    elif confidence >= 6.5: base = 2.5
    elif confidence >= 5.5: base = 2.0
    elif confidence >= 4.5: base = 1.5
    else:                   base = 1.0

    # EV modifier
    if ev >= 15:   ev_mult = 1.4
    elif ev >= 10: ev_mult = 1.2
    elif ev >= 5:  ev_mult = 1.0
    elif ev >= 2:  ev_mult = 0.8
    else:          ev_mult = 0.6

    # Risk modifier
    risk_mult = {"Low": 1.1, "Medium": 1.0, "High": 0.65}.get(risk, 1.0)

    raw = base * ev_mult * risk_mult
    capped = min(max(raw, 0.5), 5.0)
    return round(capped * 2) / 2  # round to nearest 0.5%


def _recommended_stake(
    best_market_name: str, probability: float, ev: float,
    confidence: float, risk: str, mv1_passed: bool,
) -> str:
    if not mv1_passed or ev <= 0:
        return (
            "**No stake recommended.** Aurora's methodology has not identified a market "
            "with positive expected value that passes all confidence and risk gates. "
            "Placing a bet in this fixture would be acting against the model's advice. "
            "Wait for richer data (live stats, confirmed lineups) before reconsidering."
        )

    pct = _stake_pct(ev, confidence, risk)
    on_1000  = round(pct * 10, 1)   # £10 per 1%
    on_5000  = round(pct * 50, 1)   # £50 per 1%
    on_10000 = round(pct * 100, 1)  # £100 per 1%

    # Kelly reasoning explanation
    if pct >= 3.0:
        sizing_context = (
            f"This is a relatively large stake, reflecting the combination of "
            f"{_confidence_adjective(confidence)} confidence ({confidence:.1f}/10) and "
            f"positive expected value of +{ev:.1f}%."
        )
    elif pct >= 2.0:
        sizing_context = (
            f"This is a standard stake for a {_confidence_adjective(confidence)}-confidence "
            f"opportunity. The +{ev:.1f}% edge justifies active participation."
        )
    elif pct >= 1.0:
        sizing_context = (
            f"This is a reduced stake reflecting the {_risk_phrase(risk)} "
            f"and {_confidence_adjective(confidence)} confidence level. "
            f"The model sees value but with limited conviction."
        )
    else:
        sizing_context = (
            f"This is a speculative stake only. The {_confidence_adjective(confidence)} "
            f"confidence ({confidence:.1f}/10) means the model has limited data to "
            f"support a larger position."
        )

    return (
        f"**Aurora recommends a {pct:.1f}% stake** on **{best_market_name}** "
        f"using quarter-Kelly bankroll methodology.\n\n"
        f"Reference stake sizes by bankroll:\n"
        f"• £1,000 bankroll → **£{on_1000:.0f}**\n"
        f"• £5,000 bankroll → **£{on_5000:.0f}**\n"
        f"• £10,000 bankroll → **£{on_10000:.0f}**\n\n"
        f"{sizing_context} "
        f"This sizing applies Aurora's quarter-Kelly discipline: full Kelly × 0.25, "
        f"adjusted for confidence and risk, capped at 5% per bet. "
        f"**Never exceed 5% of your bankroll on a single bet, regardless of confidence.**"
    )


def _alternative_markets(dc_markets: list, primary_id: str | None, limit: int = 4) -> list[str]:
    """Top alternative markets (excluding primary) with full reasoning."""
    lines: list[str] = []
    shown = 0
    for mkt in dc_markets:
        if shown >= limit:
            break
        if primary_id and mkt.market_id == primary_id:
            continue
        if not mkt.actionable:
            continue
        lbl = _label(mkt.market_id)
        ev_str = f"+{mkt.expected_value:.1f}%" if mkt.expected_value >= 0 else f"{mkt.expected_value:.1f}%"
        lines.append(
            f"**#{mkt.rank} — {lbl}**: {mkt.probability:.0f}% probability · "
            f"EV {ev_str} · Confidence {mkt.confidence:.1f}/10 · Risk: {mkt.risk}. "
            f"{mkt.explanation}"
        )
        shown += 1

    if not lines:
        lines.append(
            "No alternative actionable markets identified. "
            "All other markets either fail the confidence gate or show negative expected value."
        )
    return lines


def _confidence_explanation(
    confidence: float, mv1_score: float, has_xg: bool,
    has_standings: bool, has_referee: bool, is_live: bool,
    minute: int | None, categories: dict,
) -> str:
    conf_adj = _confidence_adjective(confidence)
    score_adj = _score_label(mv1_score)

    # What data was available
    data_lines = []
    if has_xg:          data_lines.append("live expected-goals (xG) data ✓")
    else:               data_lines.append("xG data ✗ (using goals-per-game fallback)")
    if has_standings:   data_lines.append("league standings ✓")
    else:               data_lines.append("standings data ✗ (using league priors)")
    if has_referee:     data_lines.append("referee profile ✓")
    else:               data_lines.append("referee unassigned ✗")
    if is_live and minute: data_lines.append(f"live match data (minute {minute}) ✓")

    data_str = "; ".join(data_lines)

    # Best and worst scoring categories
    best_cats = sorted(categories.items(), key=lambda kv: -kv[1].score)[:2]
    worst_cats = sorted(categories.items(), key=lambda kv: kv[1].score)[:2]

    best_str = " and ".join(
        f"{_CATEGORY_LABELS.get(k, k)} ({v.score:.1f})" for k, v in best_cats
    )
    worst_str = " and ".join(
        f"{_CATEGORY_LABELS.get(k, k)} ({v.score:.1f})" for k, v in worst_cats
    )

    return (
        f"Aurora's **{confidence:.1f}/10 confidence score** ({conf_adj}) reflects both the "
        f"quality of available data and the strength of the underlying signals.\n\n"
        f"**Data availability:** {data_str}.\n\n"
        f"**Methodology score:** {mv1_score:.1f}/10 ({score_adj}) — this is the average of "
        f"15 weighted category scores. "
        f"The strongest contributions came from {best_str}. "
        f"The weakest areas were {worst_str}.\n\n"
        f"Confidence is not win probability. A {confidence:.1f}/10 confidence score means "
        f"Aurora has {conf_adj} data quality and signal consistency — not that the outcome "
        f"is {confidence * 10:.0f}% certain. Football is inherently probabilistic."
    )


def _invalidation_conditions(
    best_market_name: str, hn: str, an: str,
    is_live: bool, has_xg: bool, has_standings: bool,
    knowledge: Any, categories: dict,
    mv1_score: float,
) -> list[str]:
    """Conditions that would invalidate or significantly weaken this analysis."""
    lines: list[str] = []

    # Universal invalidations
    if not is_live:
        lines.append(
            f"**Lineup change**: If a key striker or starting goalkeeper is ruled out "
            f"for either {hn} or {an} in the confirmed lineup, re-run this analysis "
            f"with the updated team news — player availability can shift goal market "
            f"probabilities by 8–15%."
        )

    lines.append(
        f"**In-play goal early**: A goal in the first 20 minutes significantly "
        f"changes the tactical shape of the match. All pre-match probability estimates "
        f"should be treated as invalidated and the live analysis re-consulted."
    )

    if is_live:
        lines.append(
            "**Red card**: A red card completely reshapes the match. "
            "Aurora's current analysis does not account for a numerical disadvantage. "
            "If a red card occurs, discard this recommendation and run a live re-analysis."
        )

    if not has_xg:
        lines.append(
            "**xG data becomes available**: Once live expected-goals data is present, "
            "the Poisson model will produce materially different probability estimates. "
            "Re-run the analysis when xG data is populated."
        )

    # Knowledge-based invalidation conditions
    for item in knowledge.relevant_items:
        tags = item.tags.lower()
        if "new manager" in tags or "rotation" in tags:
            lines.append(
                f"**Rotation or tactical change**: The {item.title} knowledge rule "
                f"flags that squad rotation or a new manager's first appearances "
                f"create high variance not modelled by season averages."
            )
            break

    lines.append(
        "**Late odds movement (>15% shortening)**: If bookmaker odds shorten by more "
        "than 15% without public news explaining it, this may indicate inside information "
        "about team news or match conditions. Treat sharp late movement as a caution signal."
    )

    lines.append(
        "**Venue or weather change**: A neutral venue removes the home advantage "
        "component entirely. Heavy rain (>5mm/h) or wind above 30 mph can shift "
        "corner and goal market baselines by 5–20%."
    )

    if mv1_score < 6.5:
        lines.append(
            f"**Methodology score improvement**: The current score of {mv1_score:.1f}/10 "
            f"is below Aurora's high-confidence threshold of 6.5. If more data becomes "
            f"available (live stats, referee confirmed, lineups released), run again — "
            f"the recommendation may strengthen or disappear."
        )

    return lines


def _learning_references(
    learning_stats: dict,
    best_market_id: str | None,
    league: str | None,
) -> list[str]:
    """Aurora's historical performance context for this market and league."""
    lines: list[str] = []
    total = learning_stats.get("total_predictions", 0)

    if total == 0:
        lines.append(
            "Aurora has not yet resolved any predictions in this session. "
            "Learning references will populate as matches finish and outcomes are recorded."
        )
        return lines

    acc = learning_stats.get("current_accuracy")
    roi = learning_stats.get("roi_pct")
    wins = learning_stats.get("wins", 0)
    losses = learning_stats.get("losses", 0)
    pending = learning_stats.get("pending", 0)
    best_mkt = learning_stats.get("best_market")
    worst_mkt = learning_stats.get("worst_market")
    best_lge = learning_stats.get("best_league")

    acc_str = f"{acc:.1f}%" if acc is not None else "not yet computed"
    roi_str = f"{roi:+.1f}%" if roi is not None else "not yet computed"

    lines.append(
        f"**Overall track record**: {total} predictions logged — "
        f"{wins} wins, {losses} losses, {pending} pending. "
        f"Current accuracy: {acc_str}. ROI: {roi_str}."
    )

    # Market-specific history
    breakdown = learning_stats.get("market_breakdown", [])
    if best_market_id and breakdown:
        mkt_match = next(
            (r for r in breakdown if r.get("rule", "").startswith(best_market_id[:12])),
            None
        )
        if mkt_match:
            mkt_acc = mkt_match.get("accuracy", 0)
            mkt_w = mkt_match.get("wins", 0)
            mkt_l = mkt_match.get("losses", 0)
            mkt_label = _label(best_market_id)
            lines.append(
                f"**{mkt_label} historical accuracy**: {mkt_acc:.1f}% "
                f"({mkt_w}W / {mkt_l}L across resolved predictions)."
            )

    if best_mkt:
        lines.append(f"**Aurora's best-performing market**: {_label(best_mkt)} — highest historical accuracy.")
    if worst_mkt and worst_mkt != best_mkt:
        lines.append(f"**Aurora's lowest-performing market**: {_label(worst_mkt)} — approach with extra caution.")
    if best_lge and league and best_lge.lower() == league.lower():
        lines.append(
            f"**League alignment**: {league} is Aurora's highest-accuracy league in the current dataset. "
            f"Historical performance here is above average."
        )
    elif best_lge:
        lines.append(f"**Highest-accuracy league**: {best_lge} — current fixture league may differ.")

    return lines


def _historical_matches(mem_ctx: dict, hn: str, an: str, league: str | None) -> list[str]:
    """Relevant past fixtures from Aurora's memory store."""
    lines: list[str] = []

    if not mem_ctx or not mem_ctx.get("has_context"):
        lines.append(
            "No historical match data found in Aurora's memory for these teams or league. "
            "Predictions are based solely on current-season data and league priors. "
            "Memory will populate as Aurora tracks more fixtures."
        )
        return lines

    lessons = mem_ctx.get("past_lessons", [])
    if lessons:
        lines.append(f"**Past lessons recorded ({len(lessons)}):**")
        for lesson in lessons[:3]:
            summary = lesson.get("summary", "")
            if summary:
                lines.append(f"  • {summary}")

    league_profile = mem_ctx.get("league_profile")
    if league_profile:
        lp_summary = league_profile.get("summary", "")
        if lp_summary:
            lines.append(f"**League profile — {league or 'this competition'}:** {lp_summary}")

    winning = mem_ctx.get("winning_patterns", [])
    if winning:
        lines.append("**Patterns that worked in this context:**")
        for p in winning[:2]:
            s = p.get("summary", "")
            if s:
                lines.append(f"  ✓ {s}")

    losing = mem_ctx.get("losing_patterns", [])
    if losing:
        lines.append("**Patterns to avoid:**")
        for p in losing[:2]:
            s = p.get("summary", "")
            if s:
                lines.append(f"  ✗ {s}")

    team_h = mem_ctx.get("team_home")
    team_a = mem_ctx.get("team_away")
    if team_h:
        th_summary = team_h.get("summary", "")
        if th_summary:
            lines.append(f"**{hn} profile from memory:** {th_summary}")
    if team_a:
        ta_summary = team_a.get("summary", "")
        if ta_summary:
            lines.append(f"**{an} profile from memory:** {ta_summary}")

    if not lines:
        lines.append(
            "Memory context exists but contains no actionable summaries yet. "
            "Aurora's memory deepens as more matches are analysed."
        )
    return lines


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def generate(
    hn:             str,
    an:             str,
    league:         str | None,
    data:           dict,
    mv1:            Any,   # MethodologyV1Result
    dc:             Any,   # DecisionCenterResult
    meth:           Any,   # MethodologyResult
    knowledge:      Any,   # KnowledgeContext
    learning_stats: dict,
    mem_ctx:        dict,
) -> IntelligenceReport:
    """
    Orchestrate all 11 NL sections and return an IntelligenceReport.

    All data parameters must be pre-computed by the caller (intelligence_router).
    This function is pure — it reads data and generates text, no side effects.
    """
    fx      = data.get("fixture", {})
    fid     = int(fx.get("id", 0))
    date    = str(fx.get("date", ""))
    status  = fx.get("status", {}).get("long", "Unknown")
    minute  = fx.get("status", {}).get("elapsed") or 0
    is_live = bool(minute and minute > 0)

    # Best market
    best = dc.best
    primary_id   = best.market_id   if best else None
    best_name    = _label(primary_id) if primary_id else "No actionable market"
    best_prob    = best.probability  if best else 0.0
    best_ev      = best.expected_value if best else 0.0
    best_conf    = best.confidence   if best else 0.0
    best_risk    = best.risk         if best else mv1.risk

    overall_conf = mv1.confidence
    mv1_score    = mv1.overall_score
    risk         = mv1.risk
    mv1_passed   = mv1.passed

    has_xg       = meth.has_xg
    has_standings = meth.has_standings
    has_referee  = bool(fx.get("referee"))
    h_score      = meth.h_goals
    a_score      = meth.a_goals
    cats         = mv1.categories

    try:
        return IntelligenceReport(
            fixture_id=fid,
            match=f"{hn} vs {an}",
            date=date,
            status=status,
            minute=minute if minute else None,
            is_live=is_live,
            primary_recommendation=best_name,
            overall_confidence=round(overall_conf, 2),
            risk_level=risk,

            executive_summary=_exec_summary(
                hn, an, league,
                best_name, best_prob, best_ev,
                overall_conf, mv1_score, risk,
                is_live, minute, h_score, a_score,
                has_xg, has_standings, dc.total_actionable, mv1_passed,
            ),
            main_factors=_main_factors(cats, mv1_score),
            positive_factors=_positive_factors(hn, an, cats),
            negative_factors=_negative_factors(cats),
            risk_factors=_risk_factors(
                knowledge, cats,
                has_xg, has_standings, has_referee,
                is_live, minute, risk, mv1_score,
            ),
            recommended_stake=_recommended_stake(
                best_name, best_prob, best_ev,
                best_conf, best_risk, mv1_passed,
            ),
            alternative_markets=_alternative_markets(dc.all_markets, primary_id),
            confidence_explanation=_confidence_explanation(
                overall_conf, mv1_score,
                has_xg, has_standings, has_referee,
                is_live, minute, cats,
            ),
            invalidation_conditions=_invalidation_conditions(
                best_name, hn, an,
                is_live, has_xg, has_standings,
                knowledge, cats, mv1_score,
            ),
            learning_references=_learning_references(learning_stats, primary_id, league),
            historical_matches=_historical_matches(mem_ctx, hn, an, league),

            knowledge_notes=knowledge.knowledge_notes,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    except Exception as exc:
        logger.error("Intelligence engine generate() failed: %s", exc, exc_info=True)
        raise
