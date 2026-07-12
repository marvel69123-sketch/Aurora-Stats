# Aurora Brain — Learning & Evolution

Aurora is designed to improve over time. This file documents the learning roadmap,
calibration approach, and how the brain evolves without API changes.

## Design Contract

1. Brain files are **append-only** — never delete knowledge, only add or refine.
2. Every parameter change must be accompanied by a `version.json` bump.
3. Endpoint behaviour changes only through brain file updates — never hardcoded.
4. New brain sections can be added without changing any endpoint signature.

## Current Learning State: v1.0 (Static Rules)

Aurora 1.0 uses static thresholds derived from football analytics research.
No historical outcome tracking yet. All parameters are hand-tuned baselines.

## Calibration Plan (v1.1 target)

Track every prediction made against the actual outcome:

```
prediction_log:
  fixture_id, market, predicted_probability, actual_outcome, timestamp
```

Monthly calibration check:
- If predicted 70% events are happening at 70% rate → well-calibrated ✅
- If predicted 70% events happen at 55% rate → overconfident, reduce base weights
- If predicted 70% events happen at 85% rate → underconfident, increase weights

**Calibration target**: Brier score < 0.20 across all markets.

## Signal Weight Evolution (v1.2 target)

Current weights (from methodology.md) are fixed. Planned change:

```
weight_xg_poisson = 0.60  # will become dynamically adjusted per league
weight_standings_prior = 0.40  # will decrease as xG becomes more reliable
```

Each league will eventually have its own weight profile based on historical accuracy.

## New Signals Pipeline (v2.0)

| Signal | Priority | Status |
|--------|----------|--------|
| Head-to-head record | High | Planned |
| Player injury / suspension | High | Planned |
| Elo ratings | Medium | Planned |
| Weather conditions | Medium | Planned |
| Travel distance / rest days | Low | Planned |
| Referee card rate | Low | Planned |
| Stadium atmosphere (attendance) | Low | Research |

## Brain File Update Protocol

When updating any brain file:

1. Increment `brain_version` patch number in `version.json`
2. Add an entry to `version.json` changelog
3. Document what changed and why in this file (or the relevant section file)
4. Do NOT remove any existing rules — only append or supersede with a dated note

## What Aurora Learns From

- **Fixture outcomes**: Did the predicted winner win?
- **Market outcomes**: Did BTTS land when probability was 70%?
- **Confidence calibration**: Are Low-risk markets landing more than High-risk ones?
- **API data quality**: Are some leagues' xG values less reliable?

## Feedback Loop (Future)

Eventually, Aurora will expose a POST endpoint for logging outcomes:

```
POST /aurora/outcome
{
  "fixture_id": 12345,
  "market": "home_win",
  "predicted_probability": 68.3,
  "actual_outcome": true
}
```

This data will feed monthly recalibration runs that update `confidence.md` thresholds.
