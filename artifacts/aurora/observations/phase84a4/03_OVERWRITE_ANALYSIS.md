# Phase 8.4-A.4 — Overwrite analysis

## Proven overwrite chain

```
NaturalConversation
  → executive_summary = match_opinion prose
  → entities.response_type = match_opinion
  → turn_owner = NONE  (not locked)

↓ can_presence_claim(payload) == True   # owner is None

IntelligenceFallback (kind=local_team_thinking)
  → REPLACES entire payload
  → overwrite_by = intelligence_fallback
  → async compose skipped (event loop already running → reply=None)
  → sync plan_response + render_from_plan
  → executive_summary = "**Fluminense** leitura rápida" + Momento sections

↓ late NRF
  → intent stamped small_talk
  → text kept (still leitura rápida)
```

## What is overwritten

| Field | Before IntelFallback | After |
|-------|----------------------|-------|
| `executive_summary` | mop opinion prose | team-summary template |
| `entities.response_type` | `match_opinion` | still `match_opinion`* |
| ownership | unlocked | still unlocked |

\* Forensic `setdefault` + intel not clearing type — **flag lies; text is the truth.**

## Why IntelFallback is allowed to claim

`turn_ownership.can_presence_claim`:

- returns True when `get_owner(payload) is None`
- Natural `team_opinion` never sets `turn_owner` / `rewrite_locked`
- `should_skip_competing_social` therefore does **not** block IntelFallback

## Secondary detail (sync render)

Inside IntelFallback with running loop:

```python
if loop and loop.is_running():
    reply = None  # cannot await compose_intelligent_reply
# → render_from_plan / render_forced_useful
```

`render_dynamic` else-branch (non `match_analysis` / non `team_moment`) still uses titles:

`leitura rápida` / `panorama` — even when planner says `match_opinion`.
