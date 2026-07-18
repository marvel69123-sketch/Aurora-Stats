# Phase 8.3-B — Conversation Continuity

## Problem

After repair (or opinion), short follow-ups lost sport context:

- `"sim"` → GeneralAssistant
- `"leitura rápida"` → GA / non-sport
- `"placar"` / `"e mercados?"` → no last-topic bind

GA stole valid 1–3 turn sport continuations.

## Fix (isolated)

New module `conversation_continuity.py`:

1. **Arm** window (max 3 turns) after:
   - `conversation_repair` / `repair_mode`
   - match-opinion render (`match_opinion_renderer` / `recent_match`)
   - HCE `short_sport_continue` / `soft_followup`
2. **Resolve** before MasterIntent (after short-memory pronouns):
   - affirm → last user sport question (or team opinion fallback)
   - leitura / placar / mercados → explicit sport rewrite with `last_team`
3. Team/question sourced from continuity → short memory → repair memory (read-only).

## Explicit non-changes

- Sports routing core
- Match-opinion renderer
- Conversation repair
- Short conversation memory
- Ownership 7.9
