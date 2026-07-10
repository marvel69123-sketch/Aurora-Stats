# Aurora Brain — Bankroll Management

Bankroll management is the discipline that separates sustainable betting from gambling.
Aurora's scoring engine is paired with conservative staking rules by default.

## Default Staking System: Flat Staking

The safest starting system for most users.

```
Stake per bet = BANKROLL × FLAT_STAKE_PCT
```

| Parameter | Default | Notes |
|-----------|---------|-------|
| FLAT_STAKE_PCT | 2.0% | Per-bet stake as % of current bankroll |
| MAX_CONCURRENT_BETS | 3 | Maximum open positions at once |
| MAX_DAILY_EXPOSURE | 6.0% | Total bankroll at risk per day |
| STOP_LOSS_DAY | 10.0% | Stop betting for the day if daily loss hits this |
| STOP_LOSS_WEEK | 20.0% | Stop betting for the week if weekly loss hits this |

## Kelly Criterion (Advanced)

For users who want stake sizing proportional to edge:

```
Kelly fraction = (b × p - q) / b

Where:
  b = decimal odds - 1
  p = Aurora probability / 100
  q = 1 - p
```

Aurora recommends using **fractional Kelly** (25–50% of full Kelly) to reduce variance.

```
Recommended stake = BANKROLL × Kelly fraction × 0.25
```

## Risk Level → Stake Multiplier

Aurora's risk levels map to stake adjustments:

| Risk Level | Stake Multiplier | Notes |
|------------|-----------------|-------|
| Low | 1.0× | Full flat stake |
| Medium | 0.6× | Reduced stake |
| High | 0.0× | Do not bet |

## Rules

1. Never increase stake size after a loss (no martingale).
2. Never bet on High-risk markets regardless of probability.
3. Recalculate bankroll base weekly, not after each bet.
4. Keep a minimum reserve of 50% of starting bankroll always.
5. If bankroll drops below 30% of starting value, pause all activity.

## Record Keeping

Every bet should be logged with:
- Fixture ID, market, odds taken, stake, result
- Aurora's predicted probability at time of bet
- Actual outcome (for calibration)
