# P3-D.4 — Response Diversification MVP

**Objective:** Eliminate pragmatic loops caused by finite response banks.

**Destroy classification (vs post–commitment recovery):** **PARTIAL**

Loop cut is large and the ≤0.35 target is met; avg break improves but stays early (SUCCESS bar needs break≥10 or +5).

## Implemented (only these)

| # | Lever | Behavior |
|---|--------|----------|
| 1 | **Fingerprint cooldown** | Hash/Jaccard of recent replies; blocked reuse for ~8 turns |
| 2 | **Speech-act cooldown** | `sport_analysis`, `uncommitted_status`, etc. cannot re-fire in a short window |
| 3 | **Recovery diversification** | Expanded uncommitted bank + cooldown-aware pick + format pivot |
| 4 | **Sport boilerplate suppression** | After first deep-analysis template in window → short conversational variants |
| 5 | **Context anchors before uncommitted** | Prefer team / last-user snip anchors before hollow uncommitted lines |

## Files

| File | Change |
|------|--------|
| `src/conversation/response_diversification.py` | **New** — cooldowns, banks, suppress, anchors, `diversify_reply` |
| `src/conversation/commitment_recovery.py` | `uncommitted_reply` → `diversify_recovery_line` |
| `src/conversation/perception_conversation_state.py` | `anti_sticky_reply` final pass → `diversify_reply` |
| `src/conversation/deep_reasoning.py` | `suppress_sport_boilerplate` on depth render |
| `src/conversation/response_variation_layer.py` | `pick_variant` respects fingerprint cooldown |
| `src/conversation/belief_revision.py` | `_looks_recovery` recognizes new diversified phrases |

## Destroy delta (commitment recovery → diversification)

| Metric | Before | After |
|--------|-------:|------:|
| Loop_Rate | 0.5453 | **0.1820** (−66.6% rel) |
| HPS | 64.38 | **72.03** (+7.65) |
| Target Loop ≤0.35 | miss | **met** |
| Avg break turn | 6.16 | **8.42** (+2.26) |
| L50 avg loop | 0.182 | **0.120** |
| L500 avg loop | 0.666 | **0.266** |
| L1000 avg loop | 0.621 | **0.163** |

### Residual (post-D.4 pattern scan)

- `uncommitted_explicit` loop mass ≈ **0%** (was 67.8%) — hollow bank loops largely broken.
- Remaining loop mass dominated by **`sport_analysis_boilerplate`** (~71% of *remaining* loops; absolute loop volume much lower).
- `legacy_clarify_triage` next (~15%), especially `poucas_palavras`.

## Classification rationale

- **PARTIAL** under shared bars: loop cut ≥15% / HPS up, but SUCCESS also requires break≥10 or break gain≥5 (here break=8.4, gain=+2.3).
- Practically: strongest loop reduction since belief MVP; finite-bank hollow collapse addressed; sport-template sticky remains the main residual attractor.

## Not in scope

- Sports engine rewrite / invented stats  
- Multi-hypothesis / belief stacks  
- Personality / new memories  

## Artifacts

- `response_diversification_patch.md` (this file)
- `response_diversification_destroy_report.json`
- `human_perception_delta.json`
- Baseline: `baselines/pre_response_diversification_perception_metrics.json`
