# Aurora Brain — Markets

Definitions and thresholds for every market Aurora analyses.

## Match Result (1X2)

| Symbol | Outcome | Notes |
|--------|---------|-------|
| 1 | Home win | After 90' (or extra time/pens if included) |
| X | Draw | Exactly equal at full time |
| 2 | Away win | Away team wins |

Aurora returns probabilities for all three. They sum to 100%.

## Both Teams to Score (BTTS)

| Outcome | Condition |
|---------|-----------|
| Yes | Both teams score ≥ 1 goal |
| No | One or both teams score 0 goals |

**Threshold**: Default market is BTTS Yes. BTTS No is implied (100 - BTTS_Yes).

## Over / Under Goals

| Line | Goals Required |
|------|---------------|
| Over 0.5 | ≥ 1 goal total |
| Over 1.5 | ≥ 2 goals total |
| Over 2.5 | ≥ 3 goals total (Aurora's default) |
| Over 3.5 | ≥ 4 goals total |
| Over 4.5 | ≥ 5 goals total |

Aurora models **Over 2.5** as the primary goals market.
Combined λ = h_xg + a_xg (or h_gpg + a_gpg if xG unavailable).

## Corners

| Line | Corners Required |
|------|----------------|
| Over 7.5 | ≥ 8 corners |
| Over 8.5 | ≥ 9 corners (Aurora's default) |
| Over 9.5 | ≥ 10 corners |
| Over 10.5 | ≥ 11 corners |

Average corners per 90 minutes (baseline): **10.5**
Aurora uses current pace when live data is available.

## Cards

| Line | Cards Required |
|------|---------------|
| Over 2.5 | ≥ 3 cards |
| Over 3.5 | ≥ 4 cards |
| Over 4.5 | ≥ 5 cards (Aurora's default) |
| Over 5.5 | ≥ 6 cards |

Average cards per 90 minutes (baseline): **3.5**
Aurora counts yellow + red cards combined.
Red card = 1 card (not counted as 2).

## Upcoming Markets (Future)

These markets are planned but not yet scored:

| Market | Status |
|--------|--------|
| Asian Handicap | Planned |
| First Goalscorer | Planned |
| Correct Score | Planned |
| Half-time / Full-time | Planned |
| Double Chance | Planned |
| Clean Sheet | Planned |

## Market Reliability by Match Status

| Market | Pre-match | Live (< 30') | Live (30–70') | Live (> 70') | Finished |
|--------|-----------|-------------|--------------|-------------|---------|
| 1X2 | Medium | High | Very High | Very High | Certain |
| BTTS | Medium | Medium | High | Very High | Certain |
| Over 2.5 | Medium | Medium | High | Very High | Certain |
| Corners | Low | Medium | High | Very High | Certain |
| Cards | Low | Low | Medium | High | Certain |
