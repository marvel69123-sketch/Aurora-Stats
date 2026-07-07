# Aurora Brain — Glossary

Definitions for football and betting terms used throughout Aurora's outputs.

## Football Terms

| Term | Definition |
|------|-----------|
| xG (Expected Goals) | Statistical measure of shot quality. 1.0 xG = shots that would on average produce 1 goal. |
| xGA | Expected Goals Against — xG created by the opponent. |
| BTTS | Both Teams to Score — both teams score ≥ 1 goal. |
| Clean Sheet | A team concedes 0 goals in the match. |
| Form | Recent results sequence. W=Win, D=Draw, L=Loss. Shown last-5 most recent. |
| GD | Goal Difference = Goals For − Goals Against (cumulative). |
| GPG | Goals Per Game — season average: Goals For ÷ Matches Played. |
| H2H | Head to Head — historical results between two specific teams. |
| Lineup | Starting XI (11 players) and substitutes named before kick-off. |
| Formation | Tactical shape (e.g. 4-3-3, 4-2-3-1). Numbered outfield only (excl. goalkeeper). |
| Half-time | End of first 45 minutes. Extra time added by referee. |
| Full-time | End of 90 minutes. Extra time and penalties may follow. |
| AET | After Extra Time — match decided during 30 minutes of added extra time. |
| PEN | Penalties — match decided by penalty shoot-out. |
| Elo | Rating system adapted from chess; higher Elo = stronger team. |

## Betting Terms

| Term | Definition |
|------|-----------|
| Probability | Likelihood of an outcome expressed as 0–100%. |
| Decimal Odds | European format. Stake × odds = total return. Implied prob = 1 / odds. |
| Fractional Odds | UK format. 5/1 means win 5 for every 1 staked (profit only). |
| Implied Probability | The probability a bookmaker's odds imply: 1 / decimal_odds × 100. |
| Edge | The gap between Aurora's probability and the bookmaker's implied probability. Positive edge = value bet. |
| Value Bet | A bet where your estimated probability > bookmaker's implied probability. |
| Kelly Criterion | Optimal stake size formula: (bp − q) / b where b = odds−1, p = win prob, q = 1−p. |
| Bankroll | Total funds set aside exclusively for betting. |
| Flat Staking | Betting a fixed % of bankroll regardless of confidence. |
| Martingale | Doubling stake after a loss. Aurora explicitly prohibits this. |
| Accumulator | Combining multiple selections into one bet. All must win. Higher risk. |
| Asian Handicap | Handicap betting that eliminates the draw. |
| Over/Under | Betting on whether a statistic (goals, corners, cards) exceeds a line. |
| Live Betting | Betting after a match has kicked off, with continuously updating odds. |

## Aurora-Specific Terms

| Term | Definition |
|------|-----------|
| Brain | The /brain folder containing Aurora's permanent knowledge and configuration. |
| Signal | A data input used to influence probability estimates (xG, score, form, etc.). |
| Prior | The pre-match probability estimate before any live data is available. |
| Confidence | A 0–10 score reflecting how much data backs a probability estimate. |
| Risk Level | Low / Medium / High — derived from confidence AND probability together. |
| Market Score | The combined output: probability + confidence + risk + explanation for one market. |
| Time Weight | The weight given to current score vs pre-match model, scaled by match minute. |
| Brain Version | Semantic version of the brain files. See version.json. |
