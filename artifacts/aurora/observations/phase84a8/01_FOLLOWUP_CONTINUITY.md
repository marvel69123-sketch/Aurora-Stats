# 8.4-A.8 — Short Follow-up Continuity

## Goal

After `match_opinion` / `partial_analysis` / `team_summary`, short asks:

- mercados?
- placar?
- estatísticas?
- favorito?
- escalações?

must reuse prior context and must **not** be stolen by:

- `intelligence_fallback` (calendar_authority)
- calendar authority path
- presence / GA / HCE claims before the contextual resolver

## Root cause (pre-fix)

1. Continuity rewrote `mercados?` → `e os mercados do jogo do {team}?`
2. `"jogo do"` triggered HIE/Natural calendar
3. IntelFallback returned agenda empty reply (`overwrite_by=intelligence_fallback`)
4. After partial, MasterIntent treated the rewrite as non-sport → GA claimed before continuity follow-up

## Patch

| Area | Change |
|------|--------|
| `conversation_continuity.py` | Safe rewrites (no `jogo do`); expand kinds; arm after partial/team_summary; `try_contextual_short_followup` + audit stamps |
| `copilot_unified_router.py` | Early claim **before** MasterIntent/GA/HCE; second guard before presence; bypass GA when claimed |
| `intelligence_fallback.py` | Skip calendar_authority on active sport follow-up |
| `human_inference.py` | Continuity FU → `topic_kind=follow_up` (not calendar) |
| `follow_up_engine.py` | Bare short patterns for engine reuse when `last_analysis` exists |

## Audit fields (entities)

- `followup_context_found`
- `followup_source`
- `followup_resolved_team`
- `followup_resolved_fixture`
- `followup_before_fallback`

## Smoke

`scripts/phase84a8_followup_continuity_smoke.py` → **PASS**

## Late-layer protection

Credibility / formatter could collapse the executive to `"?"`. Continuity stores `continuity_draft` and `restore_continuity_draft` runs immediately before `CopilotResponse`.
