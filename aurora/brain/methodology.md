# Aurora Brain — Methodology

Aurora uses a layered, multi-signal model to estimate match outcome probabilities.
Signals are blended in priority order, with live data overriding pre-match estimates.

## Signal Hierarchy (highest → lowest priority)

| Priority | Signal | Weight |
|----------|--------|--------|
| 1 | Current score × time elapsed | Up to 88% at 90' |
| 2 | Expected goals (xG) via Poisson model | 60% blend when available |
| 3 | Venue win-rate from standings | 60% of prior |
| 4 | Recent form (last 5 results) | 40% of prior |
| 5 | League baseline rates (corners, cards) | Fallback only |

## Match Result Model

Aurora uses a **Poisson distribution** to estimate goal probabilities:

```
P(team scores k goals) = e^(-λ) × λ^k / k!
```

Where λ (lambda) is:
- xG from the live match (if available)
- Season goals-per-game from standings (fallback)
- League average (last fallback)

Win/draw/loss probabilities are computed by summing joint Poisson probabilities
over all scoreline combinations up to 7 goals per team.

## Live Adjustment

When a match is in progress, the current score is blended in:

```
time_weight = min(0.88, minute / 90 × 0.88)
final_prob = prior × (1 - time_weight) + score_signal × time_weight
```

A team leading at 80' gets 88% weight on "win" signal; at 45' only 44%.

## Pre-Match Cap

For upcoming fixtures with no live stats, confidence is capped at **6.5 / 10**
to prevent overconfidence from sparse data.

## Normalization

All win/draw/loss probabilities are normalized to sum to 100% after blending:

```
p_norm = p / (p_home + p_draw + p_away)
```

## Poisson Parameters by Market

| Market | Lambda source | Over threshold |
|--------|--------------|----------------|
| Over 2.5 goals | combined xG or season avg | 3+ goals |
| BTTS | per-team Poisson scoring probability | both ≥ 1 goal |
| Over 8.5 corners | current pace extrapolated to 90' | 9+ corners |
| Over 4.5 cards | current rate + foul intensity factor | 5+ cards |

## Future Methodology Improvements (Learning Pipeline)

See `learning.md` for the roadmap. Planned additions:
- Head-to-head historical records
- Player availability / injury adjustments
- Weather and pitch conditions
- Elo rating integration
- Calibration against historical outcomes
