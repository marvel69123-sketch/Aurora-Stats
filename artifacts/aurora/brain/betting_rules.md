# Aurora Brain — Betting Rules

These rules define the gates a market must pass before Aurora considers it actionable.
Endpoints read these thresholds to decide which markets to recommend.

## Minimum Thresholds (Hard Gates)

| Rule | Threshold | Description |
|------|-----------|-------------|
| MIN_CONFIDENCE | 5.0 | Market confidence must be ≥ this to recommend |
| MIN_PROBABILITY | 52.0% | Probability must be ≥ this to recommend |
| MIN_OVERALL_CONFIDENCE | 4.0 | If overall match confidence < 4.0, recommend nothing |
| ALLOWED_RISK_LEVELS | Low, Medium | Never recommend High-risk markets |
| MIN_DATA_SIGNALS | 2 | At least 2 signals (standings, xG, live) must be present |

## Market-Specific Rules

### Match Result (1X2)
- Avoid recommending draws unless confidence ≥ 6.0 (draws are volatile)
- Home/away win markets are reliable only when probability gap > 15%

### Both Teams to Score (BTTS)
- Most reliable in live matches where both teams have shots on target
- Pre-match BTTS is reliable only when both teams score > 1.3 G/game

### Over/Under Goals
- Over 2.5: most reliable when combined xG ≥ 2.0
- Avoid over markets when a team has a clean sheet in 60%+ of home/away games

### Corners
- Over 8.5 corners: reliable only in live matches after 20+ minutes
- Pre-match corner markets are always Low-confidence (≤ 4.5) — use with caution

### Cards
- Over 4.5 cards: reliable only after 30+ minutes with ≥ 15 fouls committed
- Pre-match card markets are always Low-confidence (≤ 4.0) — use with caution

## Disqualifying Conditions

Do NOT recommend any market if:
- Match status is "Not Started" AND no standings data available
- Overall confidence < 4.0
- The fixture is a friendly (unreliable statistics)
- API data is clearly stale (last update > 5 minutes ago in a live match)

## Golden Rules

1. Value over volume — one high-confidence bet beats five medium ones.
2. Never chase losses with lower-confidence bets.
3. Markets with probability > 85% are often priced poorly by bookmakers — check implied odds.
4. Live markets are more reliable than pre-match when the score and minute are known.
