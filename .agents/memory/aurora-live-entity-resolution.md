---
name: Aurora live entity resolution
description: Bugs and fixes for "analise X x Y ao vivo" — live markers, First Half + pré-jogo
---

## Problem

"analise sao bernardo x cuiaba ao vivo" found the match (API First Half / 1H) but still generated "análise pré-jogo".

## Root causes (fixed 2026-07-12)

1. `intelligence_engine._exec_summary` used `if is_live and minute:` — falsy minute forced pre-match text
2. `aurora/nl_router` missing `_LIVE_SUFFIX_RE` → away became "Cuiaba Ao Vivo"
3. `_name_match` / `_find_fixture` could miss live sweep or return NS fixture

## Fixes

- Gate live narrative on `is_live` only
- Strip ao vivo/live/agora; set `entities.is_live=True`
- Word-level name match + prefer LIVE_STATUSES
- Hard guarantee in copilot: API live ⇒ meth.is_live
- Sync critical files to `artifacts/aurora/` for Replit deploy

## Docs

See `AURORA_ARCHITECTURE.md` and `AURORA_AUDIT_REPORT.md`.
