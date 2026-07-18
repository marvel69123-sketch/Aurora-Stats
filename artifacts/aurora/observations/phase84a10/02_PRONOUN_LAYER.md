# 8.4-A.10 — Pronoun Continuity Layer

## Module

`src/conversation/pronoun_continuity.py`

## Pipeline position

```
raw message
→ short_memory_resolve
→ continuity_resolve (+ early mercados/placar claim)
→ Pronoun Continuity claim   ← NEW (before MasterIntent / GA / fallback)
→ MasterIntent / engines…
→ note_pronoun_memory (persist fixture/team/invalid)
```

## Detection

Short messages only (≤5 tokens), patterns include:

| Utterance | `pronoun_value` | Mode |
|-----------|-----------------|------|
| e dele? / dele? | `dele` | fixture reuse |
| e dela? | `dela` | fixture reuse |
| e desse? | `desse` | fixture reuse |
| e ele? | `ele` | fixture reuse |
| e o outro? / e do outro? | `o_outro` / `do_outro` | other team |
| e esse time? | `esse_time` | focus team |

## Context sources (in order)

1. `pronoun_continuity` session memory (`note_pronoun_memory`)
2. Conversation continuity window
3. Short conversation memory
4. `ctx.last_match` / `last_analysis`

## INVALID guard

If prior turn marked `entity_invalid` / `fixture_quality=INVALID`, pronoun resolves to a **refusal** (no markets, no invented analysis). Does not fabricate a real fixture.

## Audit fields

- `pronoun_detected`
- `pronoun_value`
- `pronoun_resolved`
- `pronoun_entity`
- `pronoun_fixture`
- `pronoun_before_fallback`

Also stamps `followup_context_found` / `entity_resolved` when applicable.

## Out of scope (untouched)

Market Engine, Opinion Renderer, Calendar, Partial Analysis, Ownership modules.
