# Phase 8.4-A.1 — Git diff vs `origin/main` (pre-push)

## Summary

```text
match_opinion_renderer.py          NEW (~144 lines) — not on remote
natural_conversation.py            +mop wire before RI / force_type team_summary
response_intelligence.py           +match_opinion bypass
user_expectation.py                +answer_bias match_opinion
response_planner.py                +answer_type match_opinion
football_expectations.py           +sections/depth for match_opinion
intelligence_fallback.py           +force_type match_opinion when wants mop
context_recovery.py                +atuação pattern expansions
human_inference.py                 +atuação pattern expansions
scripts/phase83a_*.py              NEW smoke
observations/phase83a/             NEW docs
observations/phase84a/             NEW audit (8.4-A)
observations/phase84a1/            NEW deploy recovery docs
```

Working-tree stat (modified tracked files only, pre-add):

```text
8 files changed, 154 insertions(+), 32 deletions(-)
+ untracked: match_opinion_renderer.py, smoke, observations
```

## Critical behavioral delta

**Before (prod):**

```python
compose_intelligent_reply(..., force_type="team_summary")
→ "**Fluminense** — panorama"
```

**After (this deploy):**

```python
if wants_match_opinion_render(...):
    render_match_opinion(...)
    entities["response_type"] = "match_opinion"
# else legacy RI
```
