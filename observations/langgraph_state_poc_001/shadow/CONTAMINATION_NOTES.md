# Phase 2 Shadow — Contamination Notes

Generated: 2026-07-21T05:48:54.258964+00:00

## Critical scenario
Flamengo×Palmeiras → Liverpool×Chelsea → Quem está melhor?

**Primary locus:** `before_langgraph` (code 1 = before LangGraph)

On T2 (Liverpool×Chelsea) with lagging multi-writer ctx still holding Flamengo×Palmeiras, OLD is wrong vs the user message while NEW (isolated LangGraph STS) correctly becomes Liverpool×Chelsea. Contamination locus is therefore (1) before_langgraph — legacy subject lag / sticky bleed entering the turn. Inside state layer (2) does not mis-classify this turn. After state commit (3) is N/A for Phase 2 live ctx (shadow never writes back). T3 soft FU with correct prior keeps Liverpool.

## Turn log
- T1 [seed] msg='Flamengo x Palmeiras' old.fx='Flamengo x Palmeiras' new.fx='Flamengo x Palmeiras' locus=None
- T2 [switch_with_lagging_old] msg='Liverpool x Chelsea' old.fx='Flamengo x Palmeiras' new.fx='Liverpool x Chelsea' locus='before_langgraph'
- T3 [soft_fu_after_clean_adopt] msg='Quem está melhor?' old.fx='Liverpool x Chelsea' new.fx='Liverpool x Chelsea' locus=None
- Contaminated soft-FU (OLD still Flamengo after intended Liverpool switch never landed in ctx): new.fx='Flamengo x Palmeiras' locus=None. Soft keep preserves contaminated OLD → healing requires correct prior (locus on switch turn = before_langgraph).

## Flags
- `ENABLE_LANGGRAPH_STATE` default / harness: **OFF**
- `ENABLE_LANGGRAPH_STATE_SHADOW` harness: **ON** (log-only)

Artifact: `shadow_compare.json`
