# Aurora Brain — Confidence Scoring

Confidence (0–10) reflects how much data Aurora has to back its probability estimates.
It is NOT a measure of how likely an outcome is — that's what probability is for.

## Confidence = Data Richness

Each available signal adds to the base confidence score:

| Signal | Confidence Boost |
|--------|-----------------|
| Base (always present) | +3.0 |
| Match statistics available (shots, possession, etc.) | +1.3 |
| xG (expected goals) data available | +1.3 |
| Standings data available for both teams | +1.3 |
| Match events available (goals, cards) | +1.3 |
| Match is live or finished (actual score known) | +1.3 |

Maximum raw confidence: **3.0 + 5 × 1.3 = 9.5**, capped at **10.0**.

Pre-match matches are capped at **6.5** (no live data, no match stats).

## Risk Level Thresholds

Risk level is derived from BOTH confidence AND probability:

| Risk | Condition |
|------|-----------|
| Low | confidence ≥ 7.0 AND probability ≥ 68% |
| Medium | confidence ≥ 5.0 AND probability ≥ 52% |
| High | anything else |

## Per-Market Confidence Adjustments

Not all markets have equal data quality:

| Market | Confidence Modifier |
|--------|-------------------|
| Match result (1X2) | Base confidence |
| BTTS | Base + 0.8 if xG available |
| Over 2.5 goals | Base + 0.8 if xG available |
| Over 8.5 corners | Capped at 8.0 (live) or 4.5 (pre-match) |
| Over 4.5 cards | Capped at 8.0 (live) or 4.0 (pre-match) |
| Draw | Base × 0.85 (draws are harder to predict) |

## Interpreting Confidence Scores

| Score | Interpretation |
|-------|---------------|
| 9.0–10.0 | Extremely data-rich (live, xG, standings all present). Very trustworthy model. |
| 7.0–8.9 | Data-rich. Model is well-supported. Low-risk markets are actionable. |
| 5.0–6.9 | Moderate data. Use Medium-risk markets cautiously. |
| 3.0–4.9 | Thin data (pre-match, no xG). Informational only. |
| < 3.0 | Insufficient data. Do not use for any betting decision. |

## Confidence Is Not Certainty

A confidence of 10.0 means Aurora has all the data it can get.
It does NOT mean the prediction is correct. Football is inherently unpredictable.
Always treat probabilities as estimates, not guarantees.
