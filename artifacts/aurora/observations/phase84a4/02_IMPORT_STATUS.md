# Phase 8.4-A.4 — Import status

## Lazy import of `match_opinion_renderer`

| Check | Result |
|-------|--------|
| Import success | **YES** — `match_opinion_import_ok=true` |
| Import error | **null** — no fail-open exception |
| `wants_match_opinion_render` | **true** → render executed |
| Audit log | `[AUDIT] MatchOpinionRenderer: team='Fluminense' …` |
| Natural stage | `renderer_stage=match_opinion_renderer` |
| Natural summary prefix (ctx) | starts with opinion prose (“O que eu acho do jogo do Fluminense…”) |

## Fail-open?

**Not on import.** The mop path completed successfully inside NaturalConversation.

The user-visible wrong text is **not** caused by a silent import failure.
