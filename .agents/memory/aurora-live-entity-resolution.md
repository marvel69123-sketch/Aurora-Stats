---
name: Aurora live entity resolution
description: Bugs and fixes for "analise X x Y ao vivo" — live markers absorbed into team name, missing national team aliases
---

## Problem

"analise Inglaterra x Noruega ao vivo" produced entities `{'home': 'Inglaterra', 'away': 'Noruega Ao Vivo'}` — two failures at once:
1. "ao vivo" absorbed into `right_raw` by `_clf_match` → no alias entry for "noruega ao vivo" → title-case → "Noruega Ao Vivo" → API 404
2. "inglaterra" had no alias entry → "Inglaterra" passed raw → team search also fails

## Fixes applied

**nl_router.py** (module level, after `_CMD_STRIP_RE`):
```python
_LIVE_SUFFIX_RE = re.compile(r"\s+(?:ao\s+vivo(?:\s+agora)?|agora|live)\s*$", re.IGNORECASE)
_LIVE_PREFIX_RE = re.compile(r"^(?:ao\s+vivo(?:\s+agora)?\s+|agora\s+|live\s+)", re.IGNORECASE)
```

In `_clf_match`, immediately after extracting `left_raw` / `right_raw`:
- Strip `_LIVE_SUFFIX_RE` from `right_raw`
- Strip `_LIVE_PREFIX_RE` from `left_raw`
- Set `is_live_request = True` if either stripped anything
- Return `{"home": home, "away": away, **({"is_live": True} if is_live_request else {})}`

**copilot_engine.py** `_TEAM_ALIASES`: added "inglaterra" → "England" and ~30 other missing national teams (European, CONMEBOL, Asian).

**analyze.py** `_name_match`: added word-level fallback — every word >2 chars of query must appear in api_name (handles partial club name matches).

## Why it matters

`_find_fixture` does a live sweep first (`live: all`) using `_name_match`. If the team name is corrupted ("Noruega Ao Vivo"), neither the live sweep nor the `/teams?search=` call returns results, causing a 404 that falls through to the LLM fallback — even when the fixture actually exists.

## Test to verify

```python
from src.core.nl_router import route
r = route("analise Inglaterra x Noruega ao vivo")
assert r.entities == {'home': 'England', 'away': 'Norway', 'is_live': True}
```
